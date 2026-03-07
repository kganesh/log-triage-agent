"""The tools, tested without a model.

Line numbers are the unit of citation in this project, so most of these tests
are about getting them right at the edges.
"""

import pytest

from logtriage.tools import LogFile, build_tools

LOG = "sample_logs/checkout-service.log"


@pytest.fixture
def log() -> LogFile:
    return LogFile(LOG)


@pytest.fixture
def tools(log):
    return {tool.name: tool for tool in build_tools(log)}


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(FileNotFoundError, match="no log file at"):
        LogFile(tmp_path / "nothing.log")


class TestLineNumbers:
    def test_line_one_is_the_first_line(self, log):
        """1-based, to match an editor and `grep -n`. An off-by-one here would
        make every citation in the report wrong."""
        assert log.line(1).startswith("2026-03-04 09:00:00")

    def test_the_last_line_is_addressable(self, log):
        assert log.line(len(log)) is not None

    def test_out_of_range_is_none_rather_than_an_error(self, log):
        assert log.line(0) is None
        assert log.line(len(log) + 1) is None
        assert log.line(-3) is None

    def test_a_log_line_parses_into_fields(self, log):
        fields = log.parsed(1)
        assert fields["level"] == "INFO"
        assert fields["logger"] == "http.access"


class TestSearch:
    def test_a_match_is_returned_with_its_line_number(self, tools):
        result = tools["search_log"].invoke({"pattern": "pool resized"})
        assert result.startswith("87: ")

    def test_search_is_case_insensitive(self, tools):
        assert "87: " in tools["search_log"].invoke({"pattern": "POOL RESIZED"})

    def test_no_match_says_so_rather_than_returning_nothing(self, tools):
        result = tools["search_log"].invoke({"pattern": "kubernetes"})
        assert "no lines match" in result

    def test_a_bad_regex_is_reported_not_raised(self, tools):
        """The agent should get an error it can read and correct."""
        result = tools["search_log"].invoke({"pattern": "unclosed("})
        assert "bad regular expression" in result

    def test_results_are_capped(self, tools):
        """An uncapped search on a common pattern returns the whole file, which
        puts the agent back to reading everything at once."""
        result = tools["search_log"].invoke({"pattern": "2026", "max_results": 5})
        assert len(result.splitlines()) <= 6  # 5 hits plus the count note
        assert "showing 5" in result


class TestReadAndContext:
    def test_a_range_is_inclusive_at_both_ends(self, tools):
        result = tools["read_lines"].invoke({"start": 10, "end": 12})
        assert [line.split(":")[0] for line in result.splitlines()] == ["10", "11", "12"]

    def test_a_range_past_the_end_is_clipped_not_refused(self, tools, log):
        result = tools["read_lines"].invoke({"start": len(log) - 1, "end": len(log) + 50})
        assert len(result.splitlines()) == 2

    def test_a_start_past_the_end_says_how_long_the_file_is(self, tools, log):
        result = tools["read_lines"].invoke({"start": len(log) + 10, "end": len(log) + 20})
        assert f"has {len(log)} lines" in result

    def test_around_line_marks_the_line_it_centres_on(self, tools):
        result = tools["around_line"].invoke({"number": 54, "context": 2})
        marked = [line for line in result.splitlines() if line.startswith(">")]
        assert len(marked) == 1
        assert " 54: " in marked[0]

    def test_context_is_clipped_at_the_start_of_the_file(self, tools):
        result = tools["around_line"].invoke({"number": 2, "context": 10})
        assert result.splitlines()[0].strip().startswith("1:")


class TestSummary:
    def test_the_summary_counts_levels_and_loggers(self, tools):
        result = tools["level_summary"].invoke({})
        assert "ERROR" in result
        assert "db.pool" in result
        assert "covering 2026-03-04 09:00:00" in result
