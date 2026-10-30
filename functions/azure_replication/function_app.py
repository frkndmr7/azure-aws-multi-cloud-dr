"""Disabled Azure Functions v2 entry points; live feed and federation are not wired."""

import logging
import os

import azure.functions as func

app = func.FunctionApp()
logger = logging.getLogger(__name__)


@app.timer_trigger(schedule="0 */1 * * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def producer(timer: func.TimerRequest) -> None:
    if os.getenv("PRODUCER_ENABLED", "false").lower() != "false":
        raise RuntimeError("Producer disabled: feed-range, checkpoint ownership and deployment are not verified")
    logger.info("Producer disabled")


@app.timer_trigger(schedule="0 */1 * * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def dispatcher(timer: func.TimerRequest) -> None:
    if os.getenv("DISPATCHER_ENABLED", "false").lower() != "false":
        raise RuntimeError("Dispatcher disabled: AWS federation is not verified")
    logger.info("Dispatcher disabled")
