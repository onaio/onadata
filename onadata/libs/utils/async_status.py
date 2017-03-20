from celery import states

PENDING = 0
SUCCESSFUL = 1
FAILED = 2
PROGRESS = 3
RETRY = 4
STARTED = 5

status_msg = {PENDING: 'PENDING', SUCCESSFUL: 'SUCCESS', FAILED: 'FAILURE',
              PROGRESS: 'PROGRESS', RETRY: 'RETRY', STARTED: 'STARTED'}


def celery_state_to_status(state):
    status_map = {states.PENDING: PENDING, states.STARTED: STARTED,
                  states.RETRY: RETRY, states.SUCCESS: SUCCESSFUL,
                  states.FAILURE: FAILED, 'PROGRESS': PROGRESS}
    return status_map[state] if state in status_map else FAILED


def async_status(status, error=None):
    status = {
        'job_status': status_msg[status]
    }
    if error:
        status['error'] = error
    return status
