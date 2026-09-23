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
    # Deliberately not `${BENCHMARK_COMPONENT_CONFIG:-{}}` -- with the
    # variable set (the normal case), bash's parameter-expansion parser
    # matches the closing `}` of the literal `{}` as the end of the
    # expansion itself, appending a stray literal `}` after the real value
    # and breaking jq. Escaping the braces doesn't help either: it fixes the
    # set case but then leaves a literal backslash in the unset case. Doing
    # the fallback as a plain empty-string check sidesteps the parser
    # ambiguity entirely.
    local raw="${BENCHMARK_COMPONENT_CONFIG:-}"
    if [ -z "$raw" ]; then
        raw="{}"
    fi
    local value
    value="$(printf '%s' "$raw" | jq -r "${filter} // empty")"
    printf '%s' "${value:-$default}"
}