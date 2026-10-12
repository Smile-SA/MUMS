#!/usr/bin/env python3
"""Compare benchmark runs from their summaries (<data_dir>/summary/*.csv).

The first run is the reference. For every indicator found in the runs'
summaries, gives each run's value, its change against the reference, and a
verdict from the indicator's `goal` (minimize / maximize / none). Knows nothing
about the indicators themselves: any module adding a summary file is compared
too.

Usage:
  compare.py <reference_data_dir> <data_dir> [<data_dir> ...] [-v] [-m [FILE]] [-c [FILE]]
  compare.py -g NAME <data_dir>... -g NAME <data_dir>... [--alpha A] [-v] [-m [FILE]] [-c [FILE]]

  <data_dir>: the data directory of a run (holding its standard data, summary/
  included). Glob patterns are accepted, expanded by the shell or, if quoted, by
  this script (e.g. 'path/to/runs-*/data'); order is kept. The first one is the
  reference; a directory given twice is compared once; one without summary is
  left out (with a warning). Each run is named after its path, without the parts
  all paths share (e.g. a common parent, or a common last directory).

Groups (-g, repeated): runs of the same configuration, e.g. 5 repetitions each. The
first group is the reference. For each indicator: each group's median and
interquartile range, the change of medians, and a verdict only when the
difference is significant (two-sided Mann-Whitney U test, p < --alpha, default
0.05); "~" otherwise. With 3 runs per group, no difference can reach p < 0.05
(the smallest possible p is 0.1); with 5 per group, it is 0.008.

Outputs (at least one, any combination):
  -v, --verbose          aligned report on the console
  -m, --markdown [FILE]  Markdown report (default file: comparison.md)
  -c, --csv [FILE]       every value in long form (default file: comparison.csv)
"""

from __future__ import annotations

import argparse
import csv
import glob
import itertools
import math
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- data


def summary_dir(data_dir: Path) -> Path:
    return data_dir / "summary"


def run_labels(data_dirs: list[Path]) -> list[str]:
    """Each directory's path, without the leading and trailing parts all share."""
    parts = [Path(d).resolve().parts for d in data_dirs]
    if len(parts) < 2:
        return [Path(d).name for d in data_dirs]
    shortest = min(len(p) for p in parts)
    head = 0
    while head < shortest - 1 and len({p[head] for p in parts}) == 1:
        head += 1
    tail = 0
    while tail < shortest - head - 1 and len({p[-1 - tail] for p in parts}) == 1:
        tail += 1
    return ["/".join(p[head:len(p) - tail]) for p in parts]


def read_summaries(run: Path) -> dict[tuple[str, str], dict[str, str]]:
    """(summary file, metric) -> row, for every summary file of the run."""
    rows = {}
    for path in sorted(summary_dir(run).glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                rows[(path.stem, row["metric"])] = row
    return rows


def num(value: str | None) -> float | None:
    try:
        return float(value) if value not in ("", None) else None
    except ValueError:
        return None


@dataclass
class Cell:
    value: float | None
    raw: str  # the value as written in the summary
    change: str = ""  # "+12.3%", or an absolute change when the reference is 0
    verdict: str = ""  # "better", "worse", "=" or ""


@dataclass
class Row:
    source: str
    metric: str
    unit: str
    goal: str
    reference: Cell
    cells: list[Cell]  # one per compared run


@dataclass
class Comparison:
    runs: list[str]  # run names, reference first
    rows: list[Row] = field(default_factory=list)

    def sources(self) -> list[str]:
        return list(dict.fromkeys(row.source for row in self.rows))



def verdict(goal: str, reference: float | None, value: float | None) -> str:
    if reference is None or value is None or goal not in ("minimize", "maximize"):
        return ""
    if value == reference:
        return "="
    improved = value < reference if goal == "minimize" else value > reference
    return "better" if improved else "worse"


def change(reference: float | None, value: float | None) -> str:
    if reference is None or value is None:
        return ""
    if reference == 0:
        return "" if value == 0 else f"{value - reference:+.3g}"
    return f"{(value - reference) / abs(reference):+.1%}"


def compare(runs: list[Path], summaries: list[dict]) -> Comparison:
    comparison = Comparison(runs=run_labels(runs))
    keys = []
    for summary in summaries:
        keys.extend(k for k in summary if k not in keys)
    for source, metric in keys:
        found = [s.get((source, metric)) for s in summaries]
        info = next(r for r in found if r)
        ref = Cell(num(found[0]["value"]) if found[0] else None,
                   found[0]["value"] if found[0] else "")
        cells = []
        for row in found[1:]:
            value = num(row["value"]) if row else None
            cells.append(Cell(value, row["value"] if row else "", change(ref.value, value),
                              verdict(info["goal"], ref.value, value)))
        comparison.rows.append(Row(source, metric, info["unit"], info["goal"], ref, cells))
    return comparison


# ------------------------------------------------------------------------ outputs

MARKS = {"better": "✓", "worse": "✗"}
LEGEND = ("✓ better, ✗ worse than the reference (from each indicator's goal); "
          "changes are relative to the reference. Single runs: no significance test, "
          "compare groups of repetitions (-g) to conclude.")


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.4g}"


def cell_text(cell: Cell) -> str:
    text = fmt(cell.value)
    if cell.change:
        text += f" ({cell.change})"
    if cell.verdict in MARKS:
        text += f" {MARKS[cell.verdict]}"
    return text


def split_name(name: str, width: int = 22) -> list[str]:
    """A run name on several lines, cut at "-", each line at most `width` long
    when possible."""
    lines, current = [], ""
    for part in name.split("-"):
        piece = part if not current else "-" + part
        if current and len(current) + len(piece) > width:
            lines.append(current + "-")
            current = part
        else:
            current += piece
    lines.append(current)
    return lines


class Output:
    """A way of writing a comparison."""

    def write(self, comparison: Comparison) -> None:
        raise NotImplementedError


class ConsoleOutput(Output):
    """Aligned report on the console: one table per summary file."""

    def write(self, comparison: Comparison) -> None:
        print(f"Reference: {comparison.runs[0]}")
        for name in comparison.runs[1:]:
            print(f"  compared: {name}")
        print(f"\n{LEGEND}")
        for source in comparison.sources():
            rows = [r for r in comparison.rows if r.source == source]
            headers = [["Metric"], ["Unit"],
                       [*split_name(comparison.runs[0]), "(reference)"],
                       *(split_name(name) for name in comparison.runs[1:])]
            body = [[r.metric, r.unit, fmt(r.reference.value), *(cell_text(c) for c in r.cells)]
                    for r in rows]
            widths = [max(max(len(x) for x in h), *(len(line[i]) for line in body))
                      for i, h in enumerate(headers)]
            height = max(len(h) for h in headers)
            print(f"\n{source}")
            for level in range(height):
                print("  ".join(
                    (h[level] if level < len(h) else "").ljust(w) if i < 2
                    else (h[level] if level < len(h) else "").rjust(w)
                    for i, (h, w) in enumerate(zip(headers, widths, strict=True))
                ).rstrip())
            print("  ".join("-" * w for w in widths))
            for line in body:
                print("  ".join(
                    text.ljust(w) if i < 2 else text.rjust(w)
                    for i, (text, w) in enumerate(zip(line, widths, strict=True))
                ).rstrip())


class MarkdownOutput(Output):
    """Markdown report (full run names on several lines with <br>)."""

    def __init__(self, path: Path):
        self.path = path

    def write(self, comparison: Comparison) -> None:
        lines = ["# Benchmark comparison", "", f"Reference: `{comparison.runs[0]}`", ""]
        lines += [f"- compared: `{name}`" for name in comparison.runs[1:]]
        lines += ["", LEGEND]
        for source in comparison.sources():
            header = ["Metric", "Unit",
                      "<br>".join([*split_name(comparison.runs[0]), "(reference)"]),
                      *("<br>".join(split_name(name)) for name in comparison.runs[1:])]
            lines += ["", f"## {source}", "", "| " + " | ".join(header) + " |",
                      "|---|---|" + "---:|" * (len(header) - 2)]
            for r in (r for r in comparison.rows if r.source == source):
                cells = [r.metric, r.unit, fmt(r.reference.value),
                         *(cell_text(c) for c in r.cells)]
                lines.append("| " + " | ".join(cells) + " |")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Markdown report: {self.path}", file=sys.stderr)


class CsvOutput(Output):
    """Every value in long form, one row per (run, indicator)."""

    def __init__(self, path: Path):
        self.path = path

    def write(self, comparison: Comparison) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["run", "source", "metric", "unit", "goal", "value", "reference",
                             "change", "verdict"])
            for r in comparison.rows:
                for name, c in zip(comparison.runs[1:], r.cells, strict=True):
                    writer.writerow([name, r.source, r.metric, r.unit, r.goal, c.raw,
                                     r.reference.raw, c.change, c.verdict])
        print(f"CSV: {self.path}", file=sys.stderr)



# ------------------------------------------------------------------------- groups


def quantile(sorted_values: list[float], q: float) -> float:
    """Quantile by linear interpolation (sorted, non-empty input)."""
    pos = (len(sorted_values) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def _ranks(values: list[float]) -> list[float]:
    """Ranks starting at 1, ties given their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def mann_whitney(reference: list[float], values: list[float],
                 max_exact: int = 20000, samples: int = 20000) -> tuple[float, float] | None:
    """Two-sided Mann-Whitney U test, by permutation: exact when the number of ways
    to split the runs is small, else on `samples` random splits (fixed seed).
    Returns (p-value, U of `values` minus its mean under no difference: < 0 when
    `values` tends to be lower), or None with fewer than 2 runs on a side."""
    n, m = len(values), len(reference)
    if n < 2 or m < 2:
        return None
    ranks = _ranks([*values, *reference])
    mean_u = n * m / 2

    def u(indices) -> float:
        return sum(ranks[i] for i in indices) - n * (n + 1) / 2

    observed = u(range(n)) - mean_u
    total = math.comb(n + m, n)
    if total <= max_exact:
        splits = itertools.combinations(range(n + m), n)
        count = sum(1 for split in splits if abs(u(split) - mean_u) >= abs(observed) - 1e-9)
        return count / total, observed
    rng = random.Random(0)
    count = sum(
        1 for _ in range(samples)
        if abs(u(rng.sample(range(n + m), n)) - mean_u) >= abs(observed) - 1e-9
    )
    return (count + 1) / (samples + 1), observed


@dataclass
class Stats:
    values: list[float]

    @property
    def n(self) -> int:
        return len(self.values)

    def q(self, q: float) -> float:
        return quantile(sorted(self.values), q)

    @property
    def median(self) -> float:
        return statistics.median(self.values)


@dataclass
class GroupCell:
    stats: Stats | None
    change: str = ""
    p_value: float | None = None
    verdict: str = ""  # "better", "worse", "~" (not significant) or ""


@dataclass
class GroupRow:
    source: str
    metric: str
    unit: str
    goal: str
    reference: Stats | None
    cells: list[GroupCell]  # one per compared group


@dataclass
class GroupComparison:
    groups: list[tuple[str, int]]  # (name, runs with a summary), reference first
    alpha: float
    rows: list[GroupRow] = field(default_factory=list)

    def sources(self) -> list[str]:
        return list(dict.fromkeys(row.source for row in self.rows))


def group_verdict(goal: str, test: tuple[float, float] | None, alpha: float) -> str:
    if test is None or goal not in ("minimize", "maximize"):
        return ""
    p_value, direction = test
    if p_value >= alpha or direction == 0:
        return "~"
    lower = direction < 0
    return "better" if lower == (goal == "minimize") else "worse"


def compare_groups(groups: list[tuple[str, list[dict]]], alpha: float) -> GroupComparison:
    comparison = GroupComparison([(name, len(runs)) for name, runs in groups], alpha)
    keys: list[tuple[str, str]] = []
    for _, runs in groups:
        for summary in runs:
            keys.extend(k for k in summary if k not in keys)
    for source, metric in keys:
        info = next(s[(source, metric)] for _, runs in groups for s in runs
                    if (source, metric) in s)
        per_group = []
        for _, runs in groups:
            values = [v for v in (num(s[(source, metric)]["value"]) for s in runs
                                  if (source, metric) in s) if v is not None]
            per_group.append(Stats(values) if values else None)
        reference = per_group[0]
        cells = []
        for stats in per_group[1:]:
            cell = GroupCell(stats)
            if stats is not None and reference is not None:
                cell.change = change(reference.median, stats.median)
                test = mann_whitney(reference.values, stats.values)
                cell.p_value = test[0] if test else None
                cell.verdict = group_verdict(info["goal"], test, alpha)
            cells.append(cell)
        comparison.rows.append(GroupRow(source, metric, info["unit"], info["goal"],
                                        reference, cells))
    return comparison


GROUP_MARKS = {"better": "✓", "worse": "✗", "~": "~"}


def group_legend(alpha: float) -> str:
    return (f"median [Q1–Q3] (n runs); change of medians against the reference group; "
            f"✓ better / ✗ worse: significant difference (Mann-Whitney U, p < {alpha:g}); "
            "~ no significant difference.")


def stats_text(stats: Stats | None) -> str:
    if stats is None:
        return ""
    return f"{fmt(stats.median)} [{fmt(stats.q(0.25))}–{fmt(stats.q(0.75))}] ({stats.n})"


def group_cell_text(cell: GroupCell) -> str:
    text = stats_text(cell.stats)
    if cell.change:
        text += f" {cell.change}"
    if cell.verdict:
        text += f" {GROUP_MARKS[cell.verdict]}"
    if cell.p_value is not None:
        text += f" p={cell.p_value:.2g}"
    return text


def _group_table(comparison: GroupComparison, source: str) -> tuple[list[str], list[list[str]]]:
    header = ["Metric", "Unit", f"{comparison.groups[0][0]} (reference)",
              *(name for name, _ in comparison.groups[1:])]
    body = [[r.metric, r.unit, stats_text(r.reference), *(group_cell_text(c) for c in r.cells)]
            for r in comparison.rows if r.source == source]
    return header, body


class GroupConsoleOutput:
    def write(self, comparison: GroupComparison) -> None:
        for i, (name, n) in enumerate(comparison.groups):
            print(f"{'Reference group' if i == 0 else 'Group'}: {name} ({n} runs)")
        print(f"\n{group_legend(comparison.alpha)}")
        for source in comparison.sources():
            header, body = _group_table(comparison, source)
            widths = [max(len(header[i]), *(len(line[i]) for line in body))
                      for i in range(len(header))]
            print(f"\n{source}")
            for line in (header, ["-" * w for w in widths], *body):
                print("  ".join(text.ljust(w) if i < 2 else text.rjust(w)
                                for i, (text, w) in enumerate(zip(line, widths, strict=True)))
                      .rstrip())


class GroupMarkdownOutput:
    def __init__(self, path: Path):
        self.path = path

    def write(self, comparison: GroupComparison) -> None:
        lines = ["# Benchmark comparison (groups)", "", "| Group | Runs |", "|---|---:|"]
        for i, (name, n) in enumerate(comparison.groups):
            lines.append(f"| `{name}`{' (reference)' if i == 0 else ''} | {n} |")
        lines += ["", group_legend(comparison.alpha)]
        for source in comparison.sources():
            header, body = _group_table(comparison, source)
            lines += ["", f"## {source}", "", "| " + " | ".join(header) + " |",
                      "|---|---|" + "---:|" * (len(header) - 2)]
            lines += ["| " + " | ".join(line) + " |" for line in body]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Markdown report: {self.path}", file=sys.stderr)


class GroupCsvOutput:
    def __init__(self, path: Path):
        self.path = path

    def write(self, comparison: GroupComparison) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["group", "source", "metric", "unit", "goal", "runs", "median",
                             "q1", "q3", "reference_runs", "reference_median", "change",
                             "p_value", "verdict"])
            for r in comparison.rows:
                ref = r.reference
                for (name, _), c in zip(comparison.groups[1:], r.cells, strict=True):
                    st = c.stats
                    writer.writerow([
                        name, r.source, r.metric, r.unit, r.goal,
                        st.n if st else 0, fmt(st.median) if st else "",
                        fmt(st.q(0.25)) if st else "", fmt(st.q(0.75)) if st else "",
                        ref.n if ref else 0, fmt(ref.median) if ref else "", c.change,
                        f"{c.p_value:.4g}" if c.p_value is not None else "", c.verdict,
                    ])
        print(f"CSV: {self.path}", file=sys.stderr)


# --------------------------------------------------------------------------- main


def expand(patterns: list[str]) -> list[Path]:
    """Glob patterns -> paths, in order, each once."""
    paths: list[Path] = []
    for pattern in patterns:
        for match in sorted(glob.glob(pattern)) or [pattern]:
            if Path(match).resolve() not in [p.resolve() for p in paths]:
                paths.append(Path(match))
    return paths


def main_groups(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    groups = []
    for name, *patterns in args.group:
        if not patterns:
            parser.error(f"group {name!r}: give its data directories")
        summaries = []
        for run in expand(patterns):
            summary = read_summaries(run)
            if summary:
                summaries.append(summary)
            else:
                print(f"[WARN] no summary in {summary_dir(run)}: left out", file=sys.stderr)
        if not summaries:
            parser.error(f"group {name!r}: no run with a summary")
        groups.append((name, summaries))
    if len(groups) < 2:
        parser.error("give at least two groups (-g NAME DIR... -g NAME DIR...)")
    comparison = compare_groups(groups, args.alpha)
    outputs = [GroupConsoleOutput()] if args.verbose else []
    if args.markdown:
        outputs.append(GroupMarkdownOutput(Path(args.markdown)))
    if args.csv:
        outputs.append(GroupCsvOutput(Path(args.csv)))
    for output in outputs:
        output.write(comparison)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare runs from their summaries (<data_dir>/summary/*.csv; first one: "
        "reference).",
        epilog="At least one output: -v, -m or -c (any combination).",
    )
    parser.add_argument(
        "runs", nargs="*", help="Data directories of the runs (glob patterns accepted)."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Aligned console report.")
    parser.add_argument("-m", "--markdown", nargs="?", const="comparison.md", metavar="FILE",
                        help="Markdown report (default: comparison.md).")
    parser.add_argument("-c", "--csv", nargs="?", const="comparison.csv", metavar="FILE",
                        help="All values in long form (default: comparison.csv).")
    parser.add_argument("-g", "--group", nargs="+", action="append", metavar=("NAME", "DIR"),
                        help="A group of runs: its name, then their data directories (glob "
                        "patterns accepted). Repeat for each group; the first is the reference.")
    parser.add_argument("--alpha", type=float, default=0.05,
                        help="Significance level of the group test (default: 0.05).")
    args = parser.parse_args()

    # An optional file name right before the runs may have taken the first run:
    # a directory is never an output file.
    for option, default in (("markdown", "comparison.md"), ("csv", "comparison.csv")):
        value = getattr(args, option)
        if value and Path(value).is_dir():
            args.runs.insert(0, value)
            setattr(args, option, default)

    if not (args.verbose or args.markdown or args.csv):
        parser.error("no output chosen: use -v (console), -m [FILE] (Markdown) "
                     "and/or -c [FILE] (CSV)")
    if args.group:
        if args.runs:
            parser.error("give either runs or groups (-g), not both")
        return main_groups(parser, args)

    outputs: list[Output] = []
    if args.verbose:
        outputs.append(ConsoleOutput())
    if args.markdown:
        outputs.append(MarkdownOutput(Path(args.markdown)))
    if args.csv:
        outputs.append(CsvOutput(Path(args.csv)))
    if not outputs:
        parser.error("no output chosen: use -v (console), -m [FILE] (Markdown) "
                     "and/or -c [FILE] (CSV)")

    runs = expand(args.runs)
    if not runs:
        parser.error("no data directory given")
    kept = []
    for run in runs:
        summary = read_summaries(run)
        if summary:
            kept.append((run, summary))
        else:
            print(f"[WARN] no summary in {summary_dir(run)}: left out", file=sys.stderr)
    if not kept or kept[0][0] != runs[0]:
        parser.error(f"the reference has no summary: {summary_dir(runs[0])}")
    if len(kept) < 2:
        parser.error("no run with a summary to compare to the reference")

    comparison = compare([run for run, _ in kept], [summary for _, summary in kept])
    for output in outputs:
        output.write(comparison)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
