"""The citation check.

The negative cases are the ones that matter. A model returns a plausible line
number readily; the question is whether the quoted text is actually on it.
"""

import pytest

from logtriage.agent import verify
from logtriage.models import Finding, IncidentReport
from logtriage.tools import LogFile

LOG = "sample_logs/checkout-service.log"
LINE_54 = (
    "2026-03-04 09:01:12,155 ERROR [db.pool] connection pool exhausted: "
    "50/50 in use, 0 available, queue depth 18, waited 30000ms"
)


@pytest.fixture
def log() -> LogFile:
    return LogFile(LOG)


def a_report(**overrides) -> IncidentReport:
    return IncidentReport(
        **{
            "summary": "The connection pool was exhausted.",
            "root_cause": Finding(
                statement="The pool ran out of connections.",
                line_numbers=[54],
                quote="connection pool exhausted: 50/50 in use",
            ),
            **overrides,
        }
    )


def test_a_correct_citation_passes(log):
    assert verify(a_report(), log) == []


def test_a_quote_that_is_not_on_the_cited_line_is_caught(log):
    """The line number is real and the claim is true. The quote is not there."""
    report = a_report(
        root_cause=Finding(
            statement="The pool ran out of connections.",
            line_numbers=[54],
            quote="the connection pool became fully exhausted",
        )
    )
    problems = verify(report, log)
    assert len(problems) == 1
    assert "is not on line(s) [54]" in problems[0]


def test_a_line_number_past_the_end_of_the_file_is_caught(log):
    report = a_report(
        root_cause=Finding(statement="Something happened.", line_numbers=[9999], quote="anything")
    )
    assert "the file has" in verify(report, log)[0]


def test_one_correct_line_among_several_is_enough(log):
    """A finding may rest on a range of lines and quote only one of them."""
    report = a_report(
        root_cause=Finding(
            statement="The pool ran out.",
            line_numbers=[52, 53, 54],
            quote="connection pool exhausted",
        )
    )
    assert verify(report, log) == []


def test_a_quote_spanning_whitespace_still_matches(log):
    """Tool output prefixes each line with its number, so spacing may differ."""
    report = a_report(
        root_cause=Finding(
            statement="The pool ran out.",
            line_numbers=[54],
            quote="pool exhausted:    50/50   in use",
        )
    )
    assert verify(report, log) == []


def test_every_section_of_the_report_is_checked(log):
    """Symptoms and ruled-out findings are cited as often as the root cause."""
    report = a_report(
        symptoms=[Finding(statement="A", line_numbers=[55], quote="not on that line")],
        ruled_out=[Finding(statement="B", line_numbers=[85], quote="also wrong")],
    )
    assert len(verify(report, log)) == 2


def test_a_resolution_is_checked_when_present(log):
    report = a_report(
        resolution=Finding(
            statement="Pool resized.", line_numbers=[87], quote="max connections 50 -> 200"
        )
    )
    assert verify(report, log) == []
    assert LINE_54.startswith("2026-03-04 09:01:12")
