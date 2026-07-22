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
