# Tests d'intégration

Ce dépôt contient une architecture modulaire pour déployer des stacks Kubernetes distribuées, générer du trafic et tester des algorithmes d'optimisation.

## Dépendances

**Système :**
- `kind`
- `kubectl`
- `helm`
- `docker`
- `git`

**Python (hôte) :**
- `locust`
- `faker`

**Optionnel :**
- Grafana (local, pour visualiser les métriques)

## Structure
```
tests/
├─ envs/           # Création/destruction de clusters, monitoring et collecte de logs
├─ utils/          # Utilitaires partagés (helm, metallb, prometheus)
├─ stacks/         # Stacks distribuées (déploiement)
├─ traffic/        # Scripts de génération de trafic
├─ optimizers/     # Algorithmes de placement / optimisation
├─ grafana.sh      # Port-forward Prometheus + provisionnement datasource Grafana
└─ run_test.sh     # Orchestrateur principal
```

- Chaque dossier de stack contient : `prepare.sh` (téléchargement des charts) et `deploy.sh` (déploiement sur le cluster).
- Chaque dossier de traffic contient : `run.sh` (génération de trafic depuis la machine hôte).
- Les stacks "ready" sont directement utilisables pour générer du trafic et collecter des métriques.
- Les stacks "frameworks" nécessitent une configuration supplémentaire pour produire du trafic réel (Kafka, Flink, Spark).

## Types de scripts et spécifications

| Type de script | Description                                                    | Paramètres attendus |
|----------------|----------------------------------------------------------------|---------------------|
| **env**        | Créer/détruire un cluster, collecter les logs                  | `create <seed>` → retourne KUBECONFIG <br> `destroy <seed>` <br> `collect_logs <seed> <output_dir>` |
| **stack**      | Déployer une application distribuée sur le cluster             | `<KUBECONFIG> <SEED>` |
| **traffic**    | Générer du trafic réaliste depuis la machine hôte              | `<KUBECONFIG> <SEED>` |
| **optimizer**  | Déployer et exécuter un algorithme de placement/optimisation   | `<KUBECONFIG> <SEED>` |

> Tous les scripts acceptent des options supplémentaires via `$@` et peuvent ignorer celles qui ne les concernent pas.

## Exécution d'un test
```bash
./run_test.sh <env_script> <stack_script> <traffic_script> <optimizer_script> <output_dir> [seed] [options ...]
```

- `$env_script` : crée/détruit le cluster et collecte les logs
- `$stack_script` : déploie la stack
- `$traffic_script` : génère du trafic depuis la machine hôte
- `$optimizer_script` : déploie l'algorithme d'optimisation
- `$output_dir` : dossier de collecte des logs
- `[seed]` : optionnel, pour la reproductibilité
- `[options ...]` : transmis à tous les sous-scripts

## Notes

- Le trafic est généré depuis la machine hôte (hors cluster) afin de ne pas fausser les métriques de ressources observées par l'optimiseur.
- La structure est modulaire : il est facile d'ajouter de nouveaux environnements, stacks, scénarios de trafic ou optimiseurs.
