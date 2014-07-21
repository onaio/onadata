import os

from django.conf import settings


def viewer_fixture_path(*args):
    return os.path.join(settings.PROJECT_ROOT, 'apps', 'viewer',
                        'tests', 'fixtures', *args)
