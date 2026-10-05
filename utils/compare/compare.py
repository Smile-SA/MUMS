#!/usr/bin/env python3
"""Compare benchmark runs from their summaries (<data_dir>/summary/*.csv).

The first run is the reference. For every indicator found in the runs'
summaries, gives each run's value, its change against the reference, and a
verdict from the indicator's `goal` (minimize / maximize / none). Knows nothing
about the indicators themselves: any module adding a summary file is compared
too.

Usage:
  compare.py <reference_data_dir> <data_dir> [<data_dir> ...] [-v] [-m [FILE]] [-c [FILE]]

  <data_dir>: the data directory of a run (holding its standard data, summary/
  included). Glob patterns are accepted, expanded by the shell or, if quoted, by
  this script (e.g. 'path/to/runs-*/data'); order is kept. The first one is the
  reference; a directory given twice is compared once; one without summary is
  left out (with a warning). Each run is named after its path, without the parts
  all paths share (e.g. a common parent, or a common last directory).

Outputs (at least one, any combination):
  -v, --verbose          aligned report on the console
  -m, --markdown [FILE]  Markdown report (default file: comparison.md)
  -c, --csv [FILE]       every value in long form (default file: comparison.csv)
"""

from __future__ import annotations

import argparse
import csv
import glob
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

    def count(self, run_index: int, verdict: str) -> int:
        return sum(1 for row in self.rows if row.cells[run_index - 1].verdict == verdict)


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
          "changes are relative to the reference.")


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
        print(f"Reference: {comparison.runs[0]}\n")
        width = max(len(name) for name in comparison.runs[1:])
        for i, name in enumerate(comparison.runs[1:], start=1):
            print(f"  {name:<{width}}  better: {comparison.count(i, 'better'):>3}"
                  f"   worse: {comparison.count(i, 'worse'):>3}")
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
        lines = ["# Benchmark comparison", "", f"Reference: `{comparison.runs[0]}`", "",
                 "| Run | Better | Worse |", "|---|---:|---:|"]
        for i, name in enumerate(comparison.runs[1:], start=1):
            lines.append(f"| `{name}` | {comparison.count(i, 'better')} "
                         f"| {comparison.count(i, 'worse')} |")
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


# --------------------------------------------------------------------------- main


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
    args = parser.parse_args()

    # An optional file name right before the runs may have taken the first run:
    # a directory is never an output file.
    for option, default in (("markdown", "comparison.md"), ("csv", "comparison.csv")):
        value = getattr(args, option)
        if value and Path(value).is_dir():
            args.runs.insert(0, value)
            setattr(args, option, default)

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

    runs: list[Path] = []
    for pattern in args.runs:
        for match in sorted(glob.glob(pattern)) or [pattern]:
            if Path(match).resolve() not in [r.resolve() for r in runs]:
                runs.append(Path(match))
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
