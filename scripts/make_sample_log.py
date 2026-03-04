"""Generate the sample log used by the README and the tests.

The log describes one real incident with a root cause and a set of downstream
symptoms. That structure is the point. A log of unrelated random errors would
let a summariser look correct without doing anything useful.

The incident: the checkout service exhausts its database connection pool at
09:14. Requests then queue, time out, and return 500s. Retries make the queue
worse. A pool resize at 09:31 clears it.

Deterministic, so the tests can assert on specific line numbers.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "sample_logs" / "checkout-service.log"
SEED = 20260304
# A naive datetime on purpose. Log timestamps here are wall-clock strings, not
# instants, and attaching a timezone would imply a precision the format lacks.
START = datetime(2026, 3, 4, 9, 0, 0)  # noqa: DTZ001

ROUTES = ["/api/cart", "/api/checkout", "/api/orders", "/api/payment"]
USERS = [f"u-{n:05d}" for n in range(1000, 1040)]


def line(when: datetime, level: str, logger: str, message: str) -> str:
    return f"{when:%Y-%m-%d %H:%M:%S,%f}"[:-3] + f" {level:<5} [{logger}] {message}"


def build() -> list[str]:
    rng = random.Random(SEED)
    out: list[str] = []
    now = START

    def advance(low: float = 0.4, high: float = 2.5) -> None:
        nonlocal now
        now += timedelta(seconds=rng.uniform(low, high))

    def normal_traffic(count: int) -> None:
        for _ in range(count):
            route = rng.choice(ROUTES)
            out.append(
                line(
                    now,
                    "INFO",
                    "http.access",
                    f"{route} 200 user={rng.choice(USERS)} dur={rng.randint(18, 140)}ms",
                )
            )
            advance()

    # Quiet morning.
    normal_traffic(40)

    # The root cause. One line, easy to miss, 25 minutes before the pager fires.
    out.append(line(now, "WARN", "db.pool", "pool utilisation 92% (46/50 connections in use)"))
    advance()
    normal_traffic(12)

    out.append(
        line(
            now,
            "ERROR",
            "db.pool",
            "connection pool exhausted: 50/50 in use, 0 available, queue depth 18, waited 30000ms",
        )
    )
    pool_exhausted_at = now
    advance()

    # Symptoms. These are what someone reading the log notices first.
    for wave in range(6):
        for _ in range(rng.randint(3, 6)):
            route = rng.choice(ROUTES)
            out.append(
                line(
                    now,
                    "ERROR",
                    "http.access",
                    f"{route} 500 user={rng.choice(USERS)} dur={rng.randint(30000, 31000)}ms "
                    f"err=DataSourceTimeout",
                )
            )
            advance(0.2, 1.1)
        out.append(
            line(
                now,
                "WARN",
                "retry.policy",
                f"retrying {rng.randint(8, 22)} failed requests, attempt {wave + 1}/3",
            )
        )
        advance(0.3, 1.4)
        out.append(
            line(
                now,
                "ERROR",
                "db.pool",
                f"connection pool exhausted: 50/50 in use, 0 available, "
                f"queue depth {rng.randint(30, 90)}, waited 30000ms",
            )
        )
        advance(0.3, 1.4)

    # A distractor. Real but unrelated, and it looks alarming.
    out.append(line(now, "ERROR", "cache.redis", "connection reset by peer, reconnecting in 500ms"))
    advance()
    out.append(line(now, "INFO", "cache.redis", "reconnected to redis-01:6379"))
    advance()

    # Recovery.
    now = pool_exhausted_at + timedelta(minutes=17)
    out.append(
        line(now, "INFO", "db.pool", "pool resized: max connections 50 -> 200 (operator: on-call)")
    )
    advance()
    out.append(line(now, "INFO", "db.pool", "pool utilisation 31% (62/200 connections in use)"))
    advance()
    normal_traffic(25)

    return out


def main() -> None:
    lines = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} lines to {OUT}")


if __name__ == "__main__":
    main()
