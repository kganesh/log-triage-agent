"""The shape of an incident report.

Every claim carries the line numbers it came from and one exact quote. Without
the quote, a line number is easy to get wrong and impossible to check. With it,
checking is a substring test.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """One claim about the log, with the evidence for it."""

    statement: str = Field(description="What happened, in one sentence.")
    line_numbers: list[int] = Field(
        min_length=1,
        description="The 1-based line numbers this claim is based on.",
    )
    quote: str = Field(
        min_length=1,
        description=(
            "The exact text of one of the cited lines, copied character for "
            "character. It is checked against the file."
        ),
    )


class IncidentReport(BaseModel):
    """What the agent concluded."""

    summary: str = Field(description="Two or three sentences a on-call engineer can act on.")
    root_cause: Finding = Field(description="The earliest event that explains the rest.")
    symptoms: list[Finding] = Field(
        default_factory=list,
        description="Effects of the root cause, not causes themselves.",
    )
    resolution: Finding | None = Field(
        default=None,
        description="The event that ended the incident, if the log contains one.",
    )
    ruled_out: list[Finding] = Field(
        default_factory=list,
        description=(
            "Errors that look serious but are not part of this incident. Naming "
            "them is useful: the next person will notice them too."
        ),
    )

    @property
    def all_findings(self) -> list[Finding]:
        found = [self.root_cause, *self.symptoms, *self.ruled_out]
        if self.resolution is not None:
            found.append(self.resolution)
        return found
