# Catalogue

The modules and utils that come with the platform. Each one's README gives its
actions, arguments, data and known limitations.

## Modules

| Type | Module | What it does |
|---|---|---|
| environment | [`kind`](../modules/environment/kind/README.md) | a local Kubernetes cluster in Docker, with kind, and MetalLB for load balancers |
| observability | [`prometheus-live-scraper`](../modules/observability/prometheus-live-scraper/README.md) | installs Prometheus in the cluster and collects its metrics for the whole run (`openmetrics`) |
| stack | [`online-boutique-v0.10.1`](../modules/stack/online-boutique-v0.10.1/README.md) | deploys Online Boutique, Google's microservices demo, in version 0.10.1 |
| traffic | [`online-boutique-locust`](../modules/traffic/online-boutique-locust/README.md) | load on Online Boutique with Locust, following a load shape (`http-requests`) |
| optimizer | [`no-optimization`](../modules/optimizer/no-optimization/README.md) | does nothing: Kubernetes' default scheduler, the reference point |
| optimizer | [`koordinator`](../modules/optimizer/koordinator/README.md) | installs Koordinator (QoS-based scheduling and rescheduling) in the cluster |
| optimizer | [`hots`](../modules/optimizer/hots/README.md) | runs HOTS against the live cluster, through hots-connector and a Kafka broker |
| disruption | [`no-disruption`](../modules/disruption/no-disruption/README.md) | does nothing: the cluster runs undisturbed |
| post-processing | [`essential-tables`](../modules/post-processing/essential-tables/README.md) | turns the raw metrics into eight tables on containers, pods, nodes and controllers (`essential-tables`) |
| post-processing | [`basic-evaluation`](../modules/post-processing/basic-evaluation/README.md) | summarizes a run in comparable indicators: requests, latencies, errors, node usage, availability (`summary`) |
| post-processing | [`pod-based-node-evaluation`](../modules/post-processing/pod-based-node-evaluation/README.md) | node usage computed from their pods, against allocatable, for nodes sharing a machine (`summary`) |
| post-processing | [`reference-comparison`](../modules/post-processing/reference-comparison/README.md) | compares a run's summaries with a reference run's (`comparison`) |

## Utils

| Util | What it does |
|---|---|
| [`helm`](../utils/helm/README.md) | fetches Helm charts at a given version into a local repository, and installs them |
| [`metallb`](../utils/metallb/README.md) | installs MetalLB in a cluster, so that `LoadBalancer` services get an IP |
| [`kafka`](../utils/kafka/README.md) | a single-node Kafka broker in Docker, on the host |
| [`compare`](../utils/compare/README.md) | compares runs from their summaries (also run by `mums compare`) |

## Scenarios

| Scenario | What it runs |
|---|---|
| `configs/smoke-test.yaml` | the whole chain for one minute, to check that everything works |
| `configs/baseline-online-boutique-15min.yaml` | 15 minutes with Kubernetes' default scheduler, evaluated |
| `configs/koordinator-online-boutique-15min.yaml` | the same with Koordinator |
| `configs/hots-online-boutique-15min.yaml` | the same with HOTS |
