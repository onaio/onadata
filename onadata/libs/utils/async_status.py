# -*- coding: utf-8 -*-
"""
async_status - helper functions to return the status string for celery processes.
"""
from celery import states

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
    """Takes a numeric celery task status and returns equivalent string
    representation of the state."""
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
    """Takes a numeric celery task status and returns equivalent status
    dictionary with the string representation of the state. If `error`
    is passed in the error message is added to the status dictionary."""
    status = {"job_status": status_msg[status]}
    if error:
        status["error"] = error
    return status
