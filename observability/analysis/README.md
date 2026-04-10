# observability/analysis

Pipeline de traitement des métriques au format OpenMetrics vers des
CSV structurés, prêts pour l'analyse comparative des optimiseurs.

---

## Architecture générale

```
flux OpenMetrics  ──┬──> container_timeseries.py ──> container_timeseries.csv
                    ├──> container_metadata.py   ──> container_metadata.csv
                    │                                        v
                    ├──> pod_metadata.py         ──> pod_metadata.csv ──┐
                    │                                                   ├──> pod_timeseries.py ──> pod_timeseries.csv
                    ├───────────────────────────────────────────────────┘
                    ├──> node_timeseries.py      ──> node_timeseries.csv
                    ├──> node_metadata.py        ──> node_metadata.csv
                    ├──> controller_timeseries.py──> controller_timeseries.csv
                    └──> controller_metadata.py  ──> controller_metadata.csv
```

Les 7 premiers scripts lisent un flux OpenMetrics depuis **stdin** et écrivent sur **stdout**
(pipe unix classique). `pod_timeseries.py` est une exception : il agrège trois CSV
déjà produits et prend leurs chemins en arguments.

---

## Usage

```bash
# Depuis un fichier
cat <flux.om> | ./run_all.sh <output_dir>

# Exemples
cat output/test-complet/metrics.om | ./run_all.sh output/test-complet/raffined/

# Depuis un scrape live, sans passer par un fichier
python3 utils/scraper/scraper.py http://127.0.0.1:9090 15 | ./run_all.sh output/test-live/

# Manuellement, script par script (depuis un fichier)
python3 container_timeseries.py < flux.om > container_timeseries.csv

# pod_timeseries (multi-entrées)
python3 pod_timeseries.py container_timeseries.csv container_metadata.csv pod_metadata.csv > pod_timeseries.csv
```

### Split / merge des CSV (gestion de la taille)

Les CSV peuvent être découpés en fichiers numérotés pour gérer les gros volumes :

```bash
# Découper en tranches de 50 000 lignes de données
cat container_timeseries.csv | ./csv_split.sh output/container_timeseries --lines=50000
# → output/container_timeseries/container_timeseries_1.csv
# → output/container_timeseries/container_timeseries_2.csv ...

# Reconstruire le flux original (inverse exact)
./csv_merge.sh output/container_timeseries | wc -l

# run_all.sh détecte automatiquement les dossiers splittes
# et les merge à la volée via process substitution bash
```

Chaque fichier splitte est un CSV valide autonome (header inclus).
`csv_merge | csv_split` ou `csv_split | csv_merge` est une opération identité.

---

## Modèle de données

### Principe général

Chaque catégorie (containers, pods, nœuds, controllers) est représentée par
deux fichiers complémentaires :

| Fichier | Contenu | Granularité temporelle |
|---|---|---|
| `*_timeseries.csv` | Métriques qui évoluent dans le temps | Une ligne par (entité, timestamp) |
| `*_metadata.csv`   | Données figées à la création | Une ligne par entité |

Les métadonnées ne sont collectées qu'une fois (dernière valeur vue dans le scrape)
car elles ne changent pas pendant la durée d'un test.

### Lignes creuses dans les timeseries

Les métriques proviennent de plusieurs sources avec des cycles de scrape
indépendants et non synchronisés :

- **cAdvisor** : métriques temps réel des containers (CPU, mémoire, réseau)
- **node_exporter** : métriques système des nœuds (CPU, mémoire, pression PSI)
- **kube-state-metrics** : état déclaratif Kubernetes (allocatable, condition, replicas)

Ces sources ont des timestamps différents pour le même nœud ou pod. Plutôt que de
fusionner et perdre de l'information, les CSV conservent toutes les lignes, certaines
colonnes étant vides (cellule vide entre virgules = `NaN` en pandas/numpy/R).

**Pour une vue consolidée**, utiliser une interpolation linéaire pondérée par la
proximité temporelle entre le point précédent et le point suivant pour chaque colonne.
Ne jamais détruire l'information brute avant d'en avoir besoin.

### Clés uniques

| Fichier | Clé unique |
|---|---|
| `container_timeseries` | `(timestamp, pod, namespace, container)` |
| `container_metadata`   | `(pod, namespace, container)` |
| `pod_timeseries`       | `(timestamp, pod, namespace)` |
| `pod_metadata`         | `(pod, namespace)` |
| `node_timeseries`      | `(timestamp, node)` |
| `node_metadata`        | `(node)` |
| `controller_timeseries`| `(timestamp, controller_kind, controller_name, namespace)` |
| `controller_metadata`  | `(controller_kind, controller_name, namespace)` |

**Note sur les pods recréés** : quand un pod meurt et est recréé par son controller,
Un nouveau pod avec un nom différent apparaît dans `pod_timeseries` sur un nœud différent.
`pod_metadata` avec le même `controller_name` indiquent une migration ou un redémarrage.

---

## Catégorie 1 — Containers et Pods

### `container_timeseries.csv`
Clé : `(timestamp, pod, namespace, container)`

| Colonne | Description | Source |
|---|---|---|
| `timestamp` | Timestamp du scrape Prometheus (ms Unix) | — |
| `pod` | Nom du pod | labels |
| `namespace` | Namespace Kubernetes | labels |
| `container` | Nom du container | labels |
| `node` | Nœud d'exécution | labels cAdvisor |
| `cpu_usage_rate` | Consommation CPU (cores/s), rate du counter cumulatif | `container_cpu_usage_seconds_total` |
| `memory_working_set_bytes` | Mémoire active (référence Kubernetes pour OOM/limits) | `container_memory_working_set_bytes` |
| `memory_rss_bytes` | Mémoire RSS du process (heap+stack, sans cache) | `container_memory_rss` |
| `cpu_throttled_ratio` | Proportion de périodes CFS où le container a été throttlé | `container_cpu_cfs_throttled_seconds_total` / `container_cpu_cfs_periods_total` |
| `network_receive_bytes_rate` | Débit réseau entrant (bytes/s) | `container_network_receive_bytes_total` |
| `network_transmit_bytes_rate` | Débit réseau sortant (bytes/s) | `container_network_transmit_bytes_total` |
| `oom_events_total` | Nombre d'OOM kills cumulés | `container_oom_events_total` |
| `restarts_total` | Nombre de restarts cumulés | `kube_pod_container_status_restarts_total` |

**Note sur les rates** : `cpu_usage_rate` et les débits réseau sont des dérivées
discrètes `(v2 - v1) / (t2 - t1)`. Le premier point de chaque série n'a pas de rate
calculable → cellule vide.

---

### `container_metadata.csv`
Clé : `(pod, namespace, container)`

| Colonne | Description | Source |
|---|---|---|
| `pod` | Nom du pod | — |
| `namespace` | Namespace Kubernetes | — |
| `container` | Nom du container | — |

| `image` | Image Docker du container | `kube_pod_container_info` |
| `cpu_request` | CPU garanti (cores) | `kube_pod_container_resource_requests{resource="cpu"}` |
| `memory_request` | Mémoire garantie (bytes) | `kube_pod_container_resource_requests{resource="memory"}` |
| `cpu_limit` | Plafond CPU — throttling si dépassé (cores) | `kube_pod_container_resource_limits{resource="cpu"}` |
| `memory_limit` | Plafond mémoire — OOM kill si dépassé (bytes) | `kube_pod_container_resource_limits{resource="memory"}` |

**Requests vs Limits** :
- `request` = ressource garantie par le scheduler, utilisée pour le placement
- `cpu_limit` = plafond souple (throttling CFS si dépassé, pas de kill)
- `memory_limit` = plafond dur (OOM kill immédiat si dépassé)
- Un container sans limit peut consommer tout ce qui est disponible (BestEffort)

---

### `pod_timeseries.csv`
Clé : `(timestamp, pod, namespace)`

Agrégation de `container_timeseries` par pod. Généré par `pod_timeseries.py`.

| Colonne | Agrégation |
|---|---|
| `cpu_usage_rate` | Somme des containers |
| `memory_working_set_bytes` | Somme des containers |
| `memory_rss_bytes` | Somme des containers |
| `cpu_throttled_ratio` | Moyenne pondérée par `cpu_request` de chaque container |
| `network_receive_bytes_rate` | Somme des containers |
| `network_transmit_bytes_rate` | Somme des containers |
| `oom_events_total` | Somme des containers |
| `restarts_total` | Somme des containers |

---

### `pod_metadata.csv`
Clé : `(pod, namespace)`

| Colonne | Description | Source |
|---|---|---|
| `pod` | Nom du pod | — |
| `namespace` | Namespace Kubernetes | — |

| `node` | Nœud d'exécution | `kube_pod_info` |
| `controller_kind` | Type du controller parent (`ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`, vide si static pod) | `kube_pod_owner` |
| `controller_name` | Nom du controller parent | `kube_pod_owner` |
| `qos_class` | Classe QoS (`Guaranteed`, `Burstable`, `BestEffort`) | `kube_pod_status_qos_class` |
| `created_time` | Timestamp de création dans etcd (s Unix) | `kube_pod_created` |
| `scheduled_time` | Timestamp de décision de placement par le scheduler (s Unix) | `kube_pod_status_scheduled_time` |
| `running_time` | Timestamp de démarrage des containers (s Unix) | `kube_pod_status_initialized_time` |
| `ready_time` | Timestamp où le pod est prêt à recevoir du trafic (s Unix) | `kube_pod_status_ready_time` |
| `succeeded_time` | Premier scrape où phase=Succeeded (nullable, ±15s) | `kube_pod_status_phase` |
| `failed_time` | Premier scrape où phase=Failed (nullable, ±15s) | `kube_pod_status_phase` |

**Phases des pods** : les phases sont strictement unidirectionnelles,
`Pending → Running → Succeeded/Failed`. Pas d'aller-retour possible.
Un container qui redémarre reste en phase `Running` — les restarts sont
capturés dans `container_timeseries.restarts_total`.

**Temps en Pending** = `scheduled_time - created_time`
**Temps de démarrage** = `ready_time - scheduled_time` (inclut le pull d'image)

---

## Catégorie 2 — Nœuds

### `node_timeseries.csv`
Clé : `(timestamp, node)`

| Colonne | Description | Source |
|---|---|---|
| `timestamp` | Timestamp du scrape (ms Unix) | — |
| `node` | Nom du nœud | labels |
| `cpu_usage_ratio` | Ratio d'utilisation CPU (0-1) = `1 - rate(idle) / sum(all modes)` | `node_cpu_seconds_total` |
| `memory_used_bytes` | Mémoire utilisée = MemTotal - MemAvailable | `node_memory_MemTotal/MemAvailable_bytes` |
| `memory_allocatable_bytes` | Mémoire allouable aux pods | `kube_node_status_allocatable{resource="memory"}` |
| `cpu_pressure_waiting_seconds_total` | Temps cumulé où des tâches attendent du CPU (PSI) | `node_pressure_cpu_waiting_seconds_total` |
| `memory_pressure_waiting_seconds_total` | Temps cumulé où des tâches attendent de la mémoire (PSI) | `node_pressure_memory_waiting_seconds_total` |
| `memory_pressure_stalled_seconds_total` | Temps cumulé où des tâches sont bloquées sur la mémoire (PSI) | `node_pressure_memory_stalled_seconds_total` |
| `condition_ready` | 1 si le nœud est Ready, 0 sinon | `kube_node_status_condition{condition="Ready"}` |
| `unschedulable` | 1 si le nœud est cordonné (drain en cours) | `kube_node_spec_unschedulable` |
| `up` | 1 si le nœud répond au scrape, 0 si inaccessible | `up{job="kubernetes-nodes"}` |

**Détection de panne** : `up=0` signale une inaccessibilité réseau au prochain scrape
(~15s). `condition_ready=0` ou `Unknown` arrive après ~40s (délai du node controller).
Les deux sont complémentaires.

---

### `node_metadata.csv`
Clé : `(node)`

| Colonne | Description | Source |
|---|---|---|
| `node` | Nom du nœud | — |
| `cpu_allocatable` | CPU allouable aux pods (cores) | `kube_node_status_allocatable{resource="cpu"}` |
| `memory_allocatable` | Mémoire allouable aux pods (bytes) | `kube_node_status_allocatable{resource="memory"}` |
| `architecture` | Architecture CPU (ex: `amd64`) | `kube_node_info` |
| `os` | OS (ex: `linux`) | `kube_node_info` |
| `kernel_version` | Version du kernel | `kube_node_info` |
| `taints` | Taints du nœud (JSON) | `kube_node_spec_taint` |
| `created_time` | Timestamp d'enregistrement du nœud (s Unix) | `kube_node_created` |

**Allocatable vs Capacity** : `allocatable` est ce qui est réellement disponible pour
les pods (capacity moins les ressources réservées au système). C'est la référence
correcte pour évaluer la pression sur un nœud.

---

## Catégorie 3 — Controllers

### `controller_timeseries.csv`
Clé : `(timestamp, controller_kind, controller_name, namespace)`

| Colonne | Description | Source |
|---|---|---|
| `timestamp` | Timestamp du scrape (ms Unix) | — |
| `controller_kind` | `ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job` | — |
| `controller_name` | Nom du controller | labels |
| `namespace` | Namespace Kubernetes | labels |
| `replicas_desired` | Nombre de replicas souhaités | `kube_*_spec_replicas` / `kube_daemonset_status_desired_*` |
| `replicas_ready` | Nombre de replicas prêts à recevoir du trafic | `kube_*_status_ready_replicas` / `kube_daemonset_status_number_ready` |

**Disponibilité applicative** : `replicas_ready / replicas_desired` à chaque instant
est le KPI principal de disponibilité. Une valeur < 1 indique une dégradation de
service — causée par un rescheduling, un crash, ou une migration.

---

### `controller_metadata.csv`
Clé : `(controller_kind, controller_name, namespace)`

| Colonne | Description | Source |
|---|---|---|
| `controller_kind` | Type du controller | — |
| `controller_name` | Nom du controller | — |
| `namespace` | Namespace Kubernetes | — |
| `parent_kind` | Type du parent (ex: `Deployment` pour un `ReplicaSet`) | `kube_replicaset_owner` |
| `parent_name` | Nom du parent | `kube_replicaset_owner` |
| `replicas_desired` | Nombre de replicas souhaités (valeur initiale) | `kube_*_spec_replicas` |

---

## Scripts

| Script | Rôle | Entrée | Sortie |
|---|---|---|---|
| `run_all.sh` | Orchestre la génération des 8 CSV | stdin (OpenMetrics) + `output_dir` | 8 fichiers CSV |
| `container_timeseries.py` | Séries temporelles containers | stdin (OpenMetrics) | stdout (CSV) |
| `container_metadata.py` | Métadonnées containers | stdin (OpenMetrics) | stdout (CSV) |
| `pod_metadata.py` | Métadonnées pods | stdin (OpenMetrics) | stdout (CSV) |
| `node_timeseries.py` | Séries temporelles nœuds | stdin (OpenMetrics) | stdout (CSV) |
| `node_metadata.py` | Métadonnées nœuds | stdin (OpenMetrics) | stdout (CSV) |
| `controller_timeseries.py` | Séries temporelles controllers | stdin (OpenMetrics) | stdout (CSV) |
| `controller_metadata.py` | Métadonnées controllers | stdin (OpenMetrics) | stdout (CSV) |
| `pod_timeseries.py` | Agrégation container→pod | 3 fichiers CSV (args) | stdout (CSV) |
| `csv_split.sh` | Découpe un CSV en fichiers numérotés | stdin (CSV) + dossier | `dossier/basename_N.csv` |
| `csv_merge.sh` | Reconstruit un flux CSV depuis un dossier | dossier | stdout (CSV) |

---

## Voir aussi

- `A_VERIFIER.txt` — points en suspens et améliorations futures
- `../../observability/prometheus/` — scripts de scraping et port-forward
- `../../utils/scraper/scraper.py` — scraper Prometheus → OpenMetrics (.om)
