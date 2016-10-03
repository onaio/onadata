from celery import states

PENDING = 0
SUCCESSFUL = 1
FAILED = 2

status_msg = {PENDING: 'PENDING', SUCCESSFUL: 'SUCCESS', FAILED: 'FAILURE'}


def celery_state_to_status(state):
    status_map = {states.PENDING: PENDING, states.STARTED: PENDING,
                  states.RETRY: PENDING, states.SUCCESS: SUCCESSFUL,
                  states.FAILURE: FAILED}
    return status_map[state] if state in status_map else FAILED


def async_status(status, error=None):
    status = {
        'job_status': status_msg[status]
    }
    if error:
        status['error'] = error
    return status
