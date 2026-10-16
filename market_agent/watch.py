"""Sequential, interruptible monitoring loop."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from .models import RunResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WatchPolicy:
    """Bounded recovery delays for failed cycles."""

    initial_backoff: float = 5.0
    maximum_backoff: float = 300.0


def run_watch(
    cycle: Callable[[], RunResult],
    *,
    interval: float,
    stop_event: threading.Event | None = None,
    wait: Callable[[float], bool] | None = None,
    policy: WatchPolicy = WatchPolicy(),
    on_result: Callable[[RunResult], None] | None = None,
    on_exception: Callable[[Exception], None] | None = None,
    max_cycles: int | None = None,
) -> int:
    """Run cycles sequentially, returning when stopped or ``max_cycles`` is met.

    ``wait`` must return true when shutdown was requested. Injecting it makes
    backoff and interval behavior testable without real sleeping.
    """

    if interval <= 0:
        raise ValueError("watch interval must be greater than zero")
    event = stop_event or threading.Event()
    interruptible_wait = wait or event.wait
    failures = 0
    cycles = 0
    while not event.is_set() and (max_cycles is None or cycles < max_cycles):
        try:
            result = cycle()
            cycles += 1
            failures = 0
            if on_result:
                on_result(result)
            if result.status == "failed":
                failures += 1
                delay = min(policy.maximum_backoff, policy.initial_backoff * (2 ** (failures - 1)))
                logger.warning("run_id=%s cycle failed; retrying in %.1fs", result.run_id, delay)
                if interruptible_wait(delay):
                    break
                continue
        except KeyboardInterrupt:
            break
        except Exception as exc:  # a transient cycle must not kill monitoring
            cycles += 1
            failures += 1
            if on_exception:
                on_exception(exc)
            delay = min(policy.maximum_backoff, policy.initial_backoff * (2 ** (failures - 1)))
            logger.exception("watch cycle failed; retrying in %.1fs", delay)
            if interruptible_wait(delay):
                break
            continue
        if event.is_set():
            break
        if interruptible_wait(interval):
            break
    return 0
