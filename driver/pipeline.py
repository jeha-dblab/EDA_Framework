""" Module containing pipelines (reoccuring function calls) for use with apscheduler. """

from datetime import datetime
import logging
from requests import Session
import json
from apscheduler.schedulers.background import BlockingScheduler

from driver.driver_config_builder import DriverConfig
from driver.compute_server_client import ComputeServerClient
from driver.database import (
    collect_db_level_observation_for_on_prem,
    collect_table_level_observation_for_on_prem,
)
from datetime import datetime


TUNE_JOB_ID = "tune_job"
DB_LEVEL_MONITOR_JOB_ID = "db_level_monitor_job"
APPLY_EVENT_JOB_ID = "apply_event_job"
TABLE_LEVEL_MONITOR_JOB_ID = "table_level_monitor_job"


def driver_pipeline(
    config: DriverConfig,
    job_id: str,  # pylint: disable=unused-argument
) -> None:
    """
    Run the core pipeline for the driver deployment
    """
    logging.info("Running driver pipeline deployment!")


    #compute_server_client = ComputeServerClient(
    #    config.server_url, Session(), config.api_key
    #)

    if job_id == DB_LEVEL_MONITOR_JOB_ID:
        _db_level_monitor_driver_pipeline_for_on_prem(config)
    elif job_id == TABLE_LEVEL_MONITOR_JOB_ID:
        _table_level_monitor_driver_pipeline_for_on_prem(config)
    # elif job_id == LINUX


def _db_level_monitor_driver_pipeline_for_on_prem(
    config: DriverConfig,
    #compute_server_client: ComputeServerClient,
) -> None:
    """
    Regular monitoring pipeline that collects database level metrics and configs every minute

    Args:
        config: Driver configuration.
        compute_server_client: Client interacting with server in Ottertune.
    Raises:
        DriverException: Driver error.
        Exception: Other unknown exceptions that are not caught as DriverException.
    """
    logging.debug("Collecting db level observation data.")
    db_level_observation = collect_db_level_observation_for_on_prem(config)
    now = datetime.now()
    file_name = now.strftime('%Y%m%d_%H%M%S')
    f_path = open('path.txt' , 'r' )
    path = f_path.readline()
    path.rstrip('\n')
    with open(path+'/'+file_name, 'w') as outfile:
        json.dump(db_level_observation, outfile)
    logging.debug("Saving db level observation data to the server.")

    #compute_server_client.post_db_level_observation(db_level_observation)

def _table_level_monitor_driver_pipeline_for_on_prem(
    config: DriverConfig,
    #compute_server_client: ComputeServerClient,
) -> None:
    """
    Regular monitoring pipeline that collects table level metrics every hour

    Args:
        config: Driver configuration.
        comppute_server_client: Client interacting with server in Ottertune.
    Raises:
        DriverException: Driver error.
        Exception: Other unknown exceptions that are not caught as DriverException.
    """
    logging.debug("Collecting table level observation data")
    table_level_observation = collect_table_level_observation_for_on_prem(config)

    logging.debug("Posting table level observation data to the server.")
    #compute_server_client.post_table_level_observation(table_level_observation)

def _get_interval(config: DriverConfig, job_id: str) -> int:
    """Get the scheduled time interval (sec) based on job id."""

    if job_id == DB_LEVEL_MONITOR_JOB_ID:
        interval_s = int(config['monitor_interval'])
    elif job_id == TABLE_LEVEL_MONITOR_JOB_ID:
        interval_s = int(config['table_level_monitor_interval'])
    else:
        raise ValueError(f"Job {job_id} is not supported")
    return interval_s


def _start_job(
    scheduler: BlockingScheduler, config: DriverConfig, job_id: str, interval: int
) -> None:
    "Helper to start new job"
    logging.info("Initializing driver pipeline (job %s)...", job_id)

    kwargs = {}
    if job_id in (DB_LEVEL_MONITOR_JOB_ID, TABLE_LEVEL_MONITOR_JOB_ID):
        kwargs["next_run_time"] = datetime.now()

    scheduler.add_job(
        driver_pipeline,
        "interval",
        seconds=interval,
        args=[config, job_id],
        id=job_id,
        **kwargs,
    )
    logging.info("Running driver pipeline every %d seconds (job %s).", interval, job_id)


def _update_job(
    scheduler: BlockingScheduler,
    old_config: DriverConfig,
    new_config: DriverConfig,
    job_id: str,
    interval: int,
) -> None:
    "Helper to update pre-existing job"
    logging.info("Found new config (job %s)...", job_id)
    # grab old interval before modification
    old_interval = _get_interval(old_config, job_id)
    scheduler.modify_job(job_id, args=[new_config, job_id])
    if old_interval != interval:
        scheduler.reschedule_job(job_id, trigger="interval", seconds=interval)
        logging.info(
            "Running driver pipeline every %d seconds (job %s).", interval, job_id
        )


def schedule_or_update_job(
    scheduler: BlockingScheduler, config: DriverConfig, job_id: str
) -> None:
    """
    Apply configuration change to the job. If the configuration does not change, it will do nothing.
    If the job is not scheduled, it will start a job.

    Args:
        config: Driver configuration.
        job_id: Job ID.
    Raises:
        DriverException: Driver error.
        Exception: Other unknown exceptions that are not caught as DriverException.
    """
    interval = _get_interval(config, job_id)
    job = scheduler.get_job(job_id)

    if not job:
        # NB: first invocation is at current_time + interval
        _start_job(scheduler=scheduler, config=config, job_id=job_id, interval=interval)
    else:
        old_config = job.args[0]
        if old_config != config:
            _update_job(
                scheduler=scheduler,
                old_config=old_config,
                new_config=config,
                job_id=job_id,
                interval=interval,
            )
