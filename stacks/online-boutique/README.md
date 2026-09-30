# stacks.online-boutique

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

kubectl, and `utils.helm`. The dependency script fetches the chart (version in
`chart-version`, a git tag: `v0.10.1`) from the GitHub repository, since it is not
published on a Helm repository, and installs `git` if needed to do so.

## Known limitations

- Fixed release name and namespace: one Online Boutique per cluster.
- The frontend is exposed as a `LoadBalancer` service: the environment must
  provide load balancers (e.g. MetalLB in `envs.kind`).
