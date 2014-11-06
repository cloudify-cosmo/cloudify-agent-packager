# from contextlib import closing
# import os
import subprocess
import logger
import sys
import requests
import tarfile

lgr = logger.init()


def run(cmd):
    """executes a command

    :param string cmd: command to execute
    """
    p = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    lgr.debug('stdout: {0}'.format(stdout))
    lgr.debug('stderr: {0}'.format(stderr))
    p.stdout = stdout
    p.strerr = stderr
    return p


def make_virtualenv(virtualenv_dir, python='/usr/bin/python'):
    """creates a virtualenv

    :param string virtualenv_dir: path of virtualenv to create
    """
    lgr.debug('virtualenv_dir: {0}'.format(virtualenv_dir))
    p = run('virtualenv -p {0} {1}'.format(python, virtualenv_dir))
    if not p.returncode == 0:
        lgr.error('could not create venv: {0}'.format(virtualenv_dir))
        sys.exit(1)


def install_module(module, venv):
    """installs a module in a virtualenv

    :param string module: module to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('installing {0} in venv {1}'.format(module, venv))
    if module == 'pre':
        pip_cmd = '{1}/bin/pip install {0} --pre'.format(module, venv)
    else:
        pip_cmd = '{1}/bin/pip install {0}'.format(module, venv)
    p = run(pip_cmd)
    if not p.returncode == 0:
        lgr.error('could not install module: {0}'.format(module))
        sys.exit(2)


def download_file(url, destination):
    """downloads a file to a destination
    """
    lgr.debug('downloading {0} to {1}...'.format(url, destination))
    destination = destination if destination else url.split('/')[-1]
    r = requests.get(url, stream=True)
    if not r.status_code == 200:
        lgr.error('could not download file: {0}'.format(url))
        sys.exit(3)
    with open(destination, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()


def tar(source, destination):
    # TODO: solve or depracate..
    # TODO: apparently, it will tar the first child dir of
    # TODO: source, and not the given parent.
    # with closing(tarfile.open(destination, "w:gz")) as tar:
    #     tar.add(source, arcname=os.path.basename(source))
    # WORKAROUND IMPLEMENTATION
    r = run('tar czvf {0} {1}'.format(destination, source))
    if not r.returncode == 0:
        lgr.error('failed to create tar file.')
        sys.exit(10)


def untar(source, destination):
    with tarfile.open(source, 'r:gz') as tar:
        tar.extractall(destination)
