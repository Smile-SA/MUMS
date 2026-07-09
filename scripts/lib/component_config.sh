#!/usr/bin/env bash
# Shared helper sourced by module run.sh scripts to read their own arguments.
#
# The runner passes each module's YAML section in BENCHMARK_COMPONENT_CONFIG,
# serialized as YAML flow style (a strict subset of YAML 1.2, also valid
# JSON). Modules own their arguments — the runner does not assemble
# module-specific CLI flags.
#
# This helper is the abstraction boundary for the wire format: modules must
# use cfg_get instead of parsing BENCHMARK_COMPONENT_CONFIG themselves, so
# swapping the jq backend (e.g. for yq) changes this file only.
#
# Usage: cfg_get <jq-filter> [default]
cfg_get() {
    local filter="$1" default="${2-}"
    local value
    value="$(printf '%s' "${BENCHMARK_COMPONENT_CONFIG:-{}}" | jq -r "${filter} // empty")"
    printf '%s' "${value:-$default}"
}
