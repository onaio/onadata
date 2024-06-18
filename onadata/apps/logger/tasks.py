import logging

from django.db import DatabaseError

from onadata.apps.logger.models import EntityList
from onadata.celeryapp import app
from onadata.libs.utils.project_utils import set_project_perms_to_object


logger = logging.getLogger(__name__)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
def set_entity_list_perms_async(pk):
    """Set permissions for EntityList asynchronously

    Args:
        pk (int): Primary key for EntityList
    """
    try:
        entity_list = EntityList.objects.get(pk=pk)

    except EntityList.DoesNotExist as err:
        logger.exception(err)
        return

    set_project_perms_to_object(entity_list, entity_list.project)
