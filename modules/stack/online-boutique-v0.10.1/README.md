# online-boutique-v0.10.1

Stack module: deploys [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo)
(Google's microservices demo: 11 services and a Redis cart) in the cluster.

## Actions

- `deploy <kubeconfig> <seed>`: installs the Helm chart (release `onlineboutique`,
  namespace `online-boutique`, values in `values.yaml`), then waits until all its
  pods are `Ready` (timeout 300 s). On failure, prints the pods and events.
  The seed is not used: the deployment is deterministic.
- No `delete`: the application goes away with the environment.

## Arguments

None.

## Data produced

None: a stack deploys an application, it does not produce data. Reaching the
application from outside (frontend URL, `LoadBalancer` IP) is the traffic
module's concern.

## Configuration

`values.yaml`: Helm values. The chart's own load generator is disabled
(`loadGenerator.create: false`): load comes from the traffic module.

## Dependencies

kubectl, git, and the util `helm`. The dependency script fetches the chart
(version in `chart-version`, a git tag: `v0.10.1`) from the GitHub repository with
git, since it is not published on a Helm repository; it installs git if it is
missing.

## Version

The application version is fixed in `chart-version` (a git tag of
microservices-demo). To benchmark another version, copy this module, change its
`name` in `module.yaml` (e.g. `online-boutique-v0.11.0`: two modules cannot
share a name) and its `chart-version`.

## Files

`run.sh` (actions), `values.yaml` (Helm values), `chart-version`,
`dependencies.sh`, `module.yaml`.

## Known limitations

- Fixed release name and namespace: one Online Boutique per cluster.
- The frontend is exposed as a `LoadBalancer` service: the environment must
  provide load balancers.
