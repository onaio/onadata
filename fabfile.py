import os
import sys

from fabric.api import cd, env, prefix, run

DEPLOYMENTS = {
    'dev': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@dev.ona.io',
        'project': 'ona',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
        'celeryd': '/etc/init.d/celeryd-ona'
    },
    'prod': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@ona.io',
        'project': 'ona',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
        'virtualenv': '/home/ubuntu/.virtualenvs/ona',
        'celeryd': '/etc/init.d/celeryd-ona',
        'django_config_module': 'formhub.local_settings',
        'pid': '/var/run/ona.pid'
    },
    'kobocat': {
        'home': '/home/ubuntu/src/',
        'host_string':
        'ubuntu@ec2-54-200-151-185.us-west-2.compute.amazonaws.com',
        'project': 'kobocat',
        'key_filename': os.path.expanduser('~/.ssh/kobo01.pem'),
        'virtualenv': '/home/ubuntu/.virtualenvs/kobocat',
        'celeryd': '/etc/init.d/celeryd',
        'django_config_module': 'formhub.settings',
        'pid': '/run/kobocat.pid',
        'template': 'https://github.com/kobotoolbox/kobocat-template.git',
        'template_dir': 'kobocat'
    },
}


def source(path):
    return prefix('source %s' % path)


def check_key_filename(deployment_name):
    if 'key_filename' in DEPLOYMENTS[deployment_name] and \
       not os.path.exists(DEPLOYMENTS[deployment_name]['key_filename']):
        print "Cannot find required permissions file: %s" % \
            DEPLOYMENTS[deployment_name]['key_filename']
        return False
    return True


def setup_env(deployment_name):
    env.update(DEPLOYMENTS[deployment_name])

    if not check_key_filename(deployment_name):
        sys.exit(1)

    env.virtualenv = os.path.join('/home', 'ubuntu', '.virtualenvs',
                                  env.project, 'bin', 'activate')

    env.code_src = os.path.join(env.home, env.project)
    env.pip_requirements_file = os.path.join(env.code_src,
                                             'requirements/common.pip')


def deploy(deployment_name, branch='master'):
    setup_env(deployment_name)
    with cd(env.code_src):
        run("git fetch origin")
        run("git checkout origin/%s" % branch)
        run("git submodule init")
        run("git submodule update")

        if env.get('template'):
            run("git remote add template %s || true" % env.template)
            run("git fetch template")
            run("git reset HEAD %s" % env.template_dir)
            run("git read-tree --prefix=%s -u template/master"
                % env.template_dir)

        run('find . -name "*.pyc" -exec rm -rf {} \;')

    # numpy pip install from requirements file fails
    with source(env.virtualenv):
        run("pip install numpy")
        run("pip install -r %s" % env.pip_requirements_file)

    with cd(env.code_src):
        with source(env.virtualenv):
            run("python manage.py syncdb --settings=%s"
                % env.django_config_module)
            run("python manage.py migrate --settings=%s"
                % env.django_config_module)
            run("python manage.py collectstatic --settings=%s --noinput"
                % env.django_config_module)

    run("sudo %s restart" % env.celeryd)
    #run("sudo /etc/init.d/celerybeat-ona restart")
    run("sudo /usr/local/bin/uwsgi --reload %s" % env.pid)
