# logtriage

A small LangChain agent that reads a log file, explains what went wrong, and
cites the lines it used.

Every claim in the report carries line numbers and one exact quote. The code
then checks that the quote is really on one of those lines. A line number on its
own is easy for a model to get wrong and impossible for a reader to trust.

## What it does

```bash
$ logtriage sample_logs/checkout-service.log

SUMMARY
  The DB connection pool (capped at 50) became exhausted at 09:01:12, causing
  every subsequent request to time out with DataSourceTimeout 500 errors for
  ~17 minutes. A retry storm worsened the queue depth. An on-call operator
  resolved it at 09:18:12 by resizing the pool from 50 to 200 connections.

ROOT CAUSE
  The database connection pool was exhausted (50/50 in use, queue depth 18) at
  09:01:12, 14 seconds after a 92%-utilisation warning.
    line 41, 54: "2026-03-04 09:01:12,155 ERROR [db.pool] connection pool exhausted..."

RULED OUT (1)
  A Redis 'connection reset by peer' error occurred at 09:01:38 but the client
  reconnected 1 second later; it did not contribute to the HTTP 500 errors,
  which were already in full swing before this event.
    line 85, 86: "2026-03-04 09:01:38,326 ERROR [cache.redis] connection reset by peer..."

CITATIONS  all 6 findings check out (38 lines)
  5 model calls, 20,891 in + 1,135 out tokens
```

The exit code is `0` when every citation checks out and `2` when one does not.

## Running it

```bash
make install
make test          # 23 tests, no network calls
make run           # needs AWS credentials, about one cent
```

The agent uses Claude Sonnet 4.6 on Amazon Bedrock through `langchain-aws`. It
needs credentials in the environment and Bedrock model access in `us-east-1`.

## How it is put together

```
src/logtriage/
  tools.py    four tools for navigating a log file
  models.py   the shape of an incident report
  agent.py    the agent, and the citation check
  cli.py      logtriage <file>
scripts/
  make_sample_log.py   generates the sample log, deterministically
```

**The tools.** Four, deliberately. Each answers one question an engineer asks
when reading a log: what kinds of errors are in here (`level_summary`), where
does this string appear (`search_log`), what does that section say
(`read_lines`), and what else happened at that moment (`around_line`).

A single "read the whole file" tool would be simpler and would defeat the
exercise. The agent has to navigate, and the line numbers it collects while
navigating are what it later cites.

**The loop.** LangChain's `create_agent` supplies it. The tool-calling cycle,
the message history and the structured final answer are all framework work.
This project only supplies the tools, the prompt, and the check.

**The check.** `verify()` reads the report, looks up each cited line, and
confirms the quoted text is on it. Only whitespace is normalised, because tool
output prefixes each line with its number and spacing may differ. Nothing else
is normalised: lowercasing would start accepting quotes that are close but not
exact, and those are what the check exists to catch.

## The sample log

`scripts/make_sample_log.py` generates one incident with a root cause and a set
of downstream symptoms. A log of unrelated random errors would let a summariser
look correct without doing anything useful.

It also contains one distractor: a Redis connection reset that is real, looks
alarming, and has nothing to do with the incident. The `ruled_out` section of
the report exists for exactly that. The next person reading the log will notice
it too, and saying why it does not matter saves them the work.

The generator is deterministic, so the tests can assert on specific line
numbers.

## Notes

The log is synthetic. No real system or customer data is involved.
