#!/bin/bash
# Usage: ./pull.sh <repo_name> <repo_url> <chart> <version>
#
# If repo_name is "oci", the `helm repo add` step is skipped and repo_url is
# used directly as the chart source. The chart argument is then ignored.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

REPO_NAME=$1
REPO_URL=$2
CHART=$3
VERSION=$4

if [ -z "$REPO_NAME" ] || [ -z "$REPO_URL" ] || [ -z "$CHART" ] || [ -z "$VERSION" ]; then
    echo "Usage: $0 <repo_name> <repo_url> <chart> <version>" >&2
    exit 1
fi

mkdir -p "$CHART_REPOSITORY"

if [[ "$REPO_NAME" == oci ]]; then
    # OCI mode: REPO_URL is the full chart URL; REPO_NAME and CHART are ignored.
    echo "=== Pulling OCI chart: $REPO_URL version $VERSION ===" >&2
    helm pull "$REPO_URL" \
        --version "$VERSION" \
        --destination "$CHART_REPOSITORY" \
        --untar
else
    echo "=== Adding Helm repo: $REPO_NAME ===" >&2
    helm repo add "$REPO_NAME" "$REPO_URL"
    helm repo update "$REPO_NAME"

    echo "=== Pulling chart: $CHART version $VERSION ===" >&2
    helm pull "$CHART" \
        --version "$VERSION" \
        --destination "$CHART_REPOSITORY" \
        --untar
fi

echo "=== Chart available in $CHART_REPOSITORY ===" >&2
