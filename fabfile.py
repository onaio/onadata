import os
import sys

from fabric.api import cd, env, prefix, run
from fabric.contrib import files

DEPLOYMENTS = {
    'stage': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@stage.ona.io',
        'project': 'ona',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
        'celeryd': '/etc/init.d/celeryd-ona',
        'django_config_module': 'onadata.preset.local_settings',
        'pid': '/var/run/ona.pid',
        'template': 'git@github.com:onaio/onadata-template.git',
    },
    'prod': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@ona.io',
        'project': 'ona',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
        'celeryd': '/etc/init.d/celeryd-ona',
        'django_config_module': 'onadata.preset.local_settings',
        'pid': '/var/run/ona.pid',
        'template': 'git@github.com:onaio/onadata-template.git',
    },
    'formhub': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@formhub.org',
        'project': 'formhub',
        'key_filename': os.path.expanduser('~/.ssh/modilabs.pem'),
        'celeryd': '/etc/init.d/celeryd',
        'django_config_module': 'onadata.preset.local_settings',
        'pid': '/run/formhub.pid',
        'template': 'git@github.com:SEL-Columbia/formhub-template.git',
    },
    'kobocat': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@kobocat.dev.kobotoolbox.org',
        'project': 'kobocat',
        'key_filename': os.path.expanduser('~/.ssh/kobo01.pem'),
        'celeryd': '/etc/init.d/celeryd',
        'django_config_module': 'onadata.preset.local_settings',
        'pid': '/run/kobocat.pid',
        'template': 'git@github.com:kobotoolbox/kobocat-template.git',
    },
}

CONFIG_PATH_DEPRECATED = 'formhub/local_settings.py'


def local_settings_check(config_module):
    config_path = config_module.replace('.', '/') + '.py'
    if not files.exists(config_path):
        if files.exists(CONFIG_PATH_DEPRECATED):
            run('mv %s %s' % (CONFIG_PATH_DEPRECATED, config_path))
            files.sed(config_path, 'formhub\.preset',
                      'onadata\.preset\.common')
        else:
            raise RuntimeError('Django config module not found in %s or %s' % (
                config_path, CONFIG_PATH_DEPRECATED))


def source(path):
    return prefix('source %s' % path)


def exit_with_error(message):
    print message
    sys.exit(1)


def check_key_filename(deployment_name):
    if 'key_filename' in DEPLOYMENTS[deployment_name] and \
       not os.path.exists(DEPLOYMENTS[deployment_name]['key_filename']):
        exit_with_error("Cannot find required permissions file: %s" %
                        DEPLOYMENTS[deployment_name]['key_filename'])


def setup_env(deployment_name):
    deployment = DEPLOYMENTS.get(deployment_name)

    if deployment is None:
        exit_with_error('Deployment "%s" not found.' % deployment_name)

    env.update(deployment)

    check_key_filename(deployment_name)

    env.virtualenv = os.path.join('/home', 'ubuntu', '.virtualenvs',
                                  env.project, 'bin', 'activate')

    env.code_src = os.path.join(env.home, env.project)
    env.pip_requirements_file = os.path.join(env.code_src,
                                             'requirements/common.pip')
    env.template_dir = 'onadata/libs/custom_template'


def deploy_template(env):
    if env.get('template'):
        run("git remote add template %s || true" % env.template)
        run("git fetch template")
        run("git reset HEAD %s && rm -rf %s" % (env.template_dir,
                                                env.template_dir))
        run("git read-tree --prefix=%s -u template/master"
            % env.template_dir)


def deploy(deployment_name, branch='master'):
    setup_env(deployment_name)
    with cd(env.code_src):
        run("git fetch origin")
        run("git checkout origin/%s" % branch)

        deploy_template(env)

        run('find . -name "*.pyc" -exec rm -rf {} \;')
        run('find . -type d -empty -delete')

    # numpy pip install from requirements file fails
    with source(env.virtualenv):
        run("pip install numpy")
        run("pip install -r %s" % env.pip_requirements_file)

    with cd(env.code_src):
        config_module = env.django_config_module
        local_settings_check(config_module)

        with source(env.virtualenv):
            run("python manage.py syncdb --preset=%s" % config_module)
            run("python manage.py migrate --preset=%s" % config_module)
            run("python manage.py collectstatic --preset=%s --noinput"
                % config_module)

    run("sudo %s restart" % env.celeryd)
    #run("sudo /etc/init.d/celerybeat-ona restart")
    run("sudo /usr/local/bin/uwsgi --reload %s" % env.pid)
