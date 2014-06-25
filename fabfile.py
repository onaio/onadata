import os
import sys

from fabric.api import cd, env, prefix, run
from fabric.contrib import files

DEPLOYMENTS = {
    'kobocat': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@kobocat.dev.kobotoolbox.org',
        'project': 'kobocat',
        'key_filename': os.path.expanduser('~/.ssh/kobo01.pem'),
        'celeryd': '/etc/init.d/celeryd',
        'django_config_module': 'onadata.settings.local_settings',
        'pid': '/run/kobocat.pid',
        'template': 'https://github.com/kobotoolbox/kobocat-template.git',
    },
    'staging': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@kc.staging.kobotoolbox.org',
        'project': 'kobocat',
        'key_filename': os.path.expanduser('~/.ssh/kobo01.pem'),
        'celeryd': '/etc/init.d/celeryd',
        'django_config_module': 'onadata.settings.local_settings',
        'pid': '/run/kobocat.pid',
        'template': 'https://github.com/kobotoolbox/kobocat-template.git',
        'template_branch': 'master',
    },
}

CONFIG_PATH_DEPRECATED = 'formhub/local_settings.py'


def local_settings_check(config_module):
    config_path = config_module.replace('.', '/') + '.py'
    if not files.exists(config_path):
        if files.exists(CONFIG_PATH_DEPRECATED):
            run('mv %s %s' % (CONFIG_PATH_DEPRECATED, config_path))
            files.sed(config_path, 'formhub\.settings',
                      'onadata\.settings\.common')
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
    env.template_repo = '../kobocat-template'


def deploy_template(env):
    if env.get('template'):
        run("mkdir -p %s" % env.template_repo)
        run("ls -al %s" % env.template_repo)
        run("rm -rf %s" % env.template_repo)
        if env.get('template_branch'):
            run("git clone -b %s %s %s" % (env.get('template_branch'), env.get('template'), env.template_repo))
        else:
            run("git clone %s %s" % (env.get('template'), env.template_repo))

def reload(deployment_name, branch='master'):
    setup_env(deployment_name)
    run("sudo %s restart" % env.celeryd)
    #run("sudo /etc/init.d/celerybeat-ona restart")
    run("sudo /usr/local/bin/uwsgi --reload %s" % env.pid)

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
            run("python manage.py syncdb --settings=%s" % config_module)
            run("python manage.py migrate --settings=%s" % config_module)
            run("python manage.py collectstatic --settings=%s --noinput"
                % config_module)

    run("sudo %s restart" % env.celeryd)
    run("sudo /usr/local/bin/uwsgi --reload %s" % env.pid)

