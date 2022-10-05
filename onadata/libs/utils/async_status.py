"""
Utilities for celery asyncronous tasks
"""
import json
from datetime import datetime

from typing import List
from celery import states
from django.utils.translation import gettext

from onadata.celeryapp import app
from onadata.apps.logger.models.xform import XForm

PENDING = 0
SUCCESSFUL = 1
FAILED = 2
PROGRESS = 3
RETRY = 4
STARTED = 5

status_msg = {
    PENDING: "PENDING",
    SUCCESSFUL: "SUCCESS",
    FAILED: "FAILURE",
    PROGRESS: "PROGRESS",
    RETRY: "RETRY",
    STARTED: "STARTED",
}


def celery_state_to_status(state):
    status_map = {
        states.PENDING: PENDING,
        states.STARTED: STARTED,
        states.RETRY: RETRY,
        states.SUCCESS: SUCCESSFUL,
        states.FAILURE: FAILED,
        "PROGRESS": PROGRESS,
    }
    return status_map[state] if state in status_map else FAILED


def async_status(status, error=None):
    status = {"job_status": status_msg[status]}
    if error:
        status["error"] = error
    return status


def get_active_tasks(task_names: List[str], xform: XForm):
    """Get active celery tasks"""
    inspect = app.control.inspect()
    inspect_active = inspect.active()
    data = []
    if inspect_active:
        task_list = list(inspect_active.values())
        data = list(
            filter(
                lambda task: xform.pk == task["args"][1] and task["name"] in task_names,
                task_list[0],
            )
        )

    return json.dumps(
        list(
            map(
                lambda i: {
                    "job_uuid": gettext(i["id"]),
                    "time_start": datetime.fromtimestamp(i["time_start"]).strftime(
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                    "file": gettext(i["args"][2]),
                    "overwrite": i["args"][3],
                },
                data,
            )
        )
    )
