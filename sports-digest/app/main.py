"""FastAPI app + APScheduler wiring."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from .config import Settings, YamlConfig, get_settings, load_yaml_config, redact
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

state: dict = {}


def _run_pipeline_job() -> None:
    logger.info("Running scheduled digest pipeline")
    try:
        result = run_pipeline(state["settings"], state["config"])
        logger.info("Pipeline run result: %s", result)
    except Exception:
        logger.exception("Pipeline run raised unexpectedly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    config = load_yaml_config(settings.config_path)
    state["settings"] = settings
    state["config"] = config

    cron_expr = settings.digest_cron or config.digest_cron
    scheduler = BackgroundScheduler(timezone=config.timezone)
    scheduler.add_job(
        _run_pipeline_job,
        CronTrigger.from_crontab(cron_expr, timezone=config.timezone),
        id="digest_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    state["scheduler"] = scheduler
    logger.info("Scheduler started with cron '%s' (tz=%s)", cron_expr, config.timezone)

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="sports-digest", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/run-now")
def run_now() -> dict:
    result = run_pipeline(state["settings"], state["config"])
    return result


@app.get("/config")
def get_config() -> dict:
    settings: Settings = state["settings"]
    config: YamlConfig = state["config"]
    return {
        "settings": redact(settings),
        "config": config.model_dump(),
    }
