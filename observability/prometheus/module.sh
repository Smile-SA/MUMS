name: observability.prometheus
type: observability
entrypoint: run.sh

dependencies:
  python: []
  commands:
    - kubectl
    - curl
  utils:
    - prometheus
    - scraper