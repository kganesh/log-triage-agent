"""Four tools for navigating a log file.

The set is deliberately small. Each tool answers one question an engineer asks
when reading a log:

    what kinds of errors are in here?   ->  level_summary
    where does this string appear?      ->  search_log
    what does that section say?         ->  read_lines
    what else happened at that moment?  ->  around_line

A single "read the whole file" tool would be simpler and would defeat the
exercise. The agent has to navigate, and the line numbers it collects while
navigating are what it later cites.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from langchain_core.tools import tool

_LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+"
    r"(?P<level>[A-Z]+)\s+\[(?P<logger>[^\]]+)\]\s+(?P<message>.*)$"
)

MAX_RESULTS = 40
"""Cap on lines returned by one call.

An uncapped search on a matching pattern would return the whole file in one
tool result, which puts the agent back to reading everything at once.
"""


class LogFile:
    """A log file loaded once and addressed by 1-based line number.

    Line numbers are the unit of citation, so they are 1-based to match what an
    editor and `grep -n` show. An off-by-one here would make every citation in
    the report wrong in a way that is tedious to notice.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"no log file at {self.path}")
        self.lines = self.path.read_text().splitlines()

    def __len__(self) -> int:
        return len(self.lines)

    def line(self, number: int) -> str | None:
        """The text of line `number`, or None if it is out of range."""
        if 1 <= number <= len(self.lines):
            return self.lines[number - 1]
        return None

    def parsed(self, number: int) -> dict | None:
        text = self.line(number)
        if text is None:
            return None
        match = _LOG_LINE.match(text)
        return match.groupdict() if match else None


def build_tools(log: LogFile) -> list:
    """Bind the tools to one log file.

    The file is captured in the closure rather than passed as a tool argument.
    A path argument would let the agent read any file on disk, and would add a
    parameter it has no way to get right.
    """

    @tool
    def level_summary() -> str:
        """Count log lines by level and by logger. Start here to see the shape of the file."""
        levels: Counter = Counter()
        loggers: Counter = Counter()
        for number in range(1, len(log) + 1):
            fields = log.parsed(number)
            if fields:
                levels[fields["level"]] += 1
                loggers[fields["logger"]] += 1

        first, last = log.parsed(1), log.parsed(len(log))
        span = ""
        if first and last:
            span = f"\ncovering {first['ts']} to {last['ts']}"

        return (
            f"{len(log)} lines{span}\n\n"
            "by level:\n"
            + "\n".join(f"  {level:<6} {count}" for level, count in levels.most_common())
            + "\n\nby logger:\n"
            + "\n".join(f"  {name:<14} {count}" for name, count in loggers.most_common())
        )

    @tool
    def search_log(pattern: str, max_results: int = 20) -> str:
        """Find lines matching a regular expression.

        Args:
            pattern: a Python regular expression, case-insensitive.
            max_results: how many matches to return.
        """
        try:
            matcher = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            return f"bad regular expression: {exc}"

        hits = [
            f"{number}: {log.line(number)}"
            for number in range(1, len(log) + 1)
            if matcher.search(log.line(number) or "")
        ]
        if not hits:
            return f"no lines match {pattern!r}"

        capped = min(max_results, MAX_RESULTS)
        shown = hits[:capped]
        note = f"\n({len(hits)} matches, showing {len(shown)})" if len(hits) > len(shown) else ""
        return "\n".join(shown) + note

    @tool
    def read_lines(start: int, end: int) -> str:
        """Read a range of lines, inclusive, by 1-based line number."""
        if start < 1 or end < start:
            return f"bad range {start}-{end}"
        if start > len(log):
            return f"the file has {len(log)} lines; {start} is past the end"

        end = min(end, start + MAX_RESULTS - 1, len(log))
        return "\n".join(f"{n}: {log.line(n)}" for n in range(start, end + 1))

    @tool
    def around_line(number: int, context: int = 8) -> str:
        """Read the lines just before and after a line, to see what else happened then.

        Args:
            number: the 1-based line to centre on.
            context: how many lines to show on each side.
        """
        if log.line(number) is None:
            return f"the file has {len(log)} lines; {number} is out of range"

        context = min(context, MAX_RESULTS // 2)
        start = max(1, number - context)
        end = min(len(log), number + context)
        return "\n".join(
            f"{'>' if n == number else ' '} {n}: {log.line(n)}" for n in range(start, end + 1)
        )

    return [level_summary, search_log, read_lines, around_line]
