#!/usr/bin/env bash
# Shared helper sourced by module run.sh scripts to read their own arguments.
#
# The runner passes each module's YAML section as opaque JSON in
# BENCHMARK_COMPONENT_CONFIG. Modules own their arguments — the runner does
# not assemble module-specific CLI flags.
#
# Usage: cfg_get <jq-filter> [default]
cfg_get() {
    local filter="$1" default="${2-}"
    local value
    value="$(printf '%s' "${BENCHMARK_COMPONENT_CONFIG:-{}}" | jq -r "${filter} // empty")"
    printf '%s' "${value:-$default}"
}
