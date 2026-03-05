"""The agent, and the check on what it reports.

LangChain's `create_agent` supplies the loop. That is the main difference from
writing one by hand: the tool-calling cycle, the message history and the
structured final answer are all handled by the framework, and this module only
supplies the tools, the prompt and the check.

The check is the part that is not framework work. `verify` reads the report,
looks up each cited line in the file, and confirms the quoted text is really
there. A line number on its own is easy for a model to get wrong and impossible
for a reader to trust.
"""

from __future__ import annotations

import re

from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse

from logtriage.models import IncidentReport
from logtriage.tools import LogFile, build_tools

DEFAULT_MODEL = "global.anthropic.claude-sonnet-4-6"
DEFAULT_REGION = "us-east-1"

SYSTEM_PROMPT = """\
You are helping an on-call engineer understand a log file.

Work through the file with the tools. Start with `level_summary` to see its
shape. Then find the errors, and read around them to see what happened at the
same time.

Look for the earliest event that explains the later ones. A log usually contains
many effects and one cause. The most frequent error is normally an effect.

Report every claim with the line numbers it rests on, and quote one of those
lines exactly, character for character. The quote is checked against the file.

If an error is real but unrelated to the main incident, put it in `ruled_out`.
The next person reading this log will notice it too, and saying why it does not
matter saves them the work.
"""


def build_report_agent(
    log: LogFile,
    model: str = DEFAULT_MODEL,
    region: str = DEFAULT_REGION,
    max_tokens: int = 8_000,
):
    """An agent bound to one log file, returning an `IncidentReport`."""
    llm = ChatBedrockConverse(model=model, region_name=region, max_tokens=max_tokens)
    return create_agent(
        model=llm,
        tools=build_tools(log),
        system_prompt=SYSTEM_PROMPT,
        response_format=IncidentReport,
    )


def _normalise(text: str) -> str:
    """Collapse whitespace so a quote copied from tool output still matches.

    Tool output prefixes each line with its number, so a model may include or
    drop surrounding spaces. Nothing else is normalised. Lowercasing would start
    accepting quotes that are close but not exact.
    """
    return re.sub(r"\s+", " ", text).strip()


def verify(report: IncidentReport, log: LogFile) -> list[str]:
    """Problems with the report's citations. An empty list means all of them check out."""
    problems: list[str] = []

    for finding in report.all_findings:
        label = finding.statement[:48]

        out_of_range = [n for n in finding.line_numbers if log.line(n) is None]
        if out_of_range:
            problems.append(
                f"{label!r} cites line(s) {out_of_range} but the file has {len(log)} lines"
            )
            continue

        quote = _normalise(finding.quote)
        cited = [_normalise(log.line(n) or "") for n in finding.line_numbers]
        if not any(quote in text for text in cited):
            problems.append(
                f"{label!r} quotes {finding.quote[:60]!r}, "
                f"which is not on line(s) {finding.line_numbers}"
            )

    return problems


def triage(log: LogFile, **kwargs) -> tuple[IncidentReport, list[str], dict]:
    """Run the agent over a log file and check what it reports.

    Returns the report, any citation problems, and token usage.
    """
    agent = build_report_agent(log, **kwargs)
    result = agent.invoke({"messages": [{"role": "user", "content": f"Triage {log.path.name}."}]})

    report: IncidentReport = result["structured_response"]
    usage = _usage(result.get("messages", []))
    return report, verify(report, log), usage


def _usage(messages: list) -> dict:
    """Add up token usage across every model call in the run."""
    total = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    for message in messages:
        data = getattr(message, "usage_metadata", None)
        if data:
            total["input_tokens"] += data.get("input_tokens", 0)
            total["output_tokens"] += data.get("output_tokens", 0)
            total["calls"] += 1
    return total
