"""`logtriage <file>` — read a log, explain the incident, check the citations."""

from __future__ import annotations

import argparse
import sys

from logtriage.agent import DEFAULT_MODEL, DEFAULT_REGION, triage
from logtriage.models import Finding, IncidentReport
from logtriage.tools import LogFile


def _finding(finding: Finding, indent: str = "  ") -> list[str]:
    lines = [f"{indent}{finding.statement}"]
    numbers = ", ".join(str(n) for n in finding.line_numbers)
    lines.append(f'{indent}  line {numbers}: "{finding.quote[:88]}"')
    return lines


def render(report: IncidentReport, problems: list[str], usage: dict) -> str:
    out = ["SUMMARY", f"  {report.summary}", "", "ROOT CAUSE"]
    out += _finding(report.root_cause)

    if report.symptoms:
        out += ["", f"SYMPTOMS ({len(report.symptoms)})"]
        for finding in report.symptoms:
            out += _finding(finding)

    if report.resolution:
        out += ["", "RESOLUTION"]
        out += _finding(report.resolution)

    if report.ruled_out:
        out += ["", f"RULED OUT ({len(report.ruled_out)})"]
        for finding in report.ruled_out:
            out += _finding(finding)

    out += [""]
    if problems:
        out.append(f"CITATIONS  {len(problems)} could not be verified")
        out += [f"  {problem}" for problem in problems]
    else:
        checked = sum(len(f.line_numbers) for f in report.all_findings)
        out.append(
            f"CITATIONS  all {len(report.all_findings)} findings check out ({checked} lines)"
        )

    out.append(
        f"  {usage['calls']} model calls, "
        f"{usage['input_tokens']:,} in + {usage['output_tokens']:,} out tokens"
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="logtriage", description=__doc__)
    parser.add_argument("logfile")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--region", default=DEFAULT_REGION)
    args = parser.parse_args(argv)

    try:
        log = LogFile(args.logfile)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1

    report, problems, usage = triage(log, model=args.model, region=args.region)
    print(render(report, problems, usage))

    # Non-zero when a citation does not check out. The report may still be
    # readable, but it is no longer something to act on without checking.
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
