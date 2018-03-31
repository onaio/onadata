import os
import sys

from fabric.api import env, sudo, put


DEPLOYMENTS = {
    'stage': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@stage.ona.io',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem')
    },
    'prod': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@ona.io',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem')
    },
}


def check_key_filename(deployment_name):
    if 'key_filename' in DEPLOYMENTS[deployment_name] and \
       not os.path.exists(DEPLOYMENTS[deployment_name]['key_filename']):
        print("Cannot find required permissions file: %s" %
              DEPLOYMENTS[deployment_name]['key_filename'])
        return False
    return True


def setup_env(deployment_name):
    env.update(DEPLOYMENTS[deployment_name])
    if not check_key_filename(deployment_name):
        sys.exit(1)


def deploy(deployment_name, scripts=''):
    setup_env(deployment_name)
    sudo('which monit || apt-get install -y monit')
    for script in scripts.split(' '):
        put(script, '/etc/monit/conf.d/%s' % script, use_sudo=True)
    sudo('/etc/init.d/monit restart')
