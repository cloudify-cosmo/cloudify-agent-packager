import logging
import subprocess
import requests
import re
import os
import sys
import tarfile

from . import exceptions


lgr = logging.getLogger()


def run(cmd, no_print=False):
    """executes a command

    :param string cmd: command to execute
    """
    p = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    if not no_print:
        if len(stdout) > 0:
            lgr.debug('stdout: {0}'.format(stdout))
        if len(stderr) > 0:
            lgr.debug('stderr: {0}'.format(stderr))
    p.stdout = stdout.decode('utf-8', 'replace')
    p.strerr = stderr.decode('utf-8', 'replace')
    return p


def make_virtualenv(virtualenv_dir, python=None):
    """creates a virtualenv

    :param string virtualenv_dir: path of virtualenv to create
    """
    lgr.debug('virtualenv_dir: {0}'.format(virtualenv_dir))
    python = python or sys.executable
    command = '{0} -m virtualenv {1}'.format(python, virtualenv_dir)

    p = run(command)
    if not p.returncode == 0:
        raise exceptions.VirtualenvCreationError(virtualenv_dir)


def virtualenv_relocatable(virtualenv_dir, python=None):
    """Make virtualenv_dir relocatable"""
    lgr.debug('making relocatable: {0}'.format(virtualenv_dir))
    python = python or sys.executable
    command = '{0} -m virtualenv {1} --relocatable'.format(
        python, virtualenv_dir)

    p = run(command)
    if not p.returncode == 0:
        raise exceptions.VirtualenvCreationError(virtualenv_dir)


def install_module(module, venv):
    """installs a module in a virtualenv

    :param string module: module to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('Installing {0} in venv {1}'.format(module, venv))
    if module == 'pre':
        pip_cmd = '{1}/bin/pip install {0} --pre'.format(module, venv)
    else:
        pip_cmd = '{1}/bin/pip install {0}'.format(module, venv)
    p = run(pip_cmd)
    if not p.returncode == 0:
        raise exceptions.PipInstallError(module)


def install_requirements_file(path, venv):
    """installs modules from a requirements file in a virtualenv

    :param string path: path to requirements file1
    :param string venv: path of virtualenv to install in
    """
    lgr.debug('Installing {0} in venv {1}'.format(path, venv))
    pip_cmd = '{1}/bin/pip install -r{0}'.format(path, venv)
    p = run(pip_cmd)
    if not p.returncode == 0:
        raise exceptions.PipInstallError(path)


def uninstall_module(module, venv):
    """uninstalls a module from a virtualenv

    :param string module: module to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('Uninstalling {0} in venv {1}'.format(module, venv))
    pip_cmd = '{1}/bin/pip uninstall {0} -y'.format(module, venv)
    p = run(pip_cmd)
    if not p.returncode == 0:
        raise exceptions.PipUninstallError(module)


def get_installed(venv):
    p = run('{0}/bin/pip freeze'.format(venv), no_print=True)
    return p.stdout


def check_installed(module, venv):
    """checks to see if a module is installed

    :param string module: module to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    p = run('{0}/bin/pip freeze'.format(venv), no_print=True)
    if re.search(r'{0}'.format(module), p.stdout.lower()):
        lgr.debug('Module {0} is installed in {1}'.format(module, venv))
        return True
    lgr.debug('Module {0} is not installed in {1}'.format(module, venv))
    return False


def download_file(url, destination):
    """downloads a file to a destination
    """
    lgr.debug('Downloading {0} to {1}...'.format(url, destination))
    destination = destination if destination else url.split('/')[-1]
    r = requests.get(url, stream=True)
    if not r.status_code == 200:
        raise exceptions.DownloadError('{0}: {1}'.format(url, r.status_code))
    with open(destination, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()


def tar(source, destination):
    lgr.info('Creating tar file: {0}'.format(destination))
    tar = tarfile.open(destination, "w:gz")
    tar.add(source)
    tar.close()


def get_env_bin_path(env_path):
    """returns the bin path for a virtualenv
    """
    try:
        import virtualenv
        return virtualenv.path_locations(env_path)[3]
    except ImportError:
        # this is a fallback for an edge case in which you're trying
        # to use the script and create a virtualenv from within
        # a virtualenv in which virtualenv isn't installed and so
        # is not importable.
        return os.path.join(env_path, 'bin')


def is_virtualenv(env_path):
    return os.path.isfile(os.path.join(get_env_bin_path(env_path), 'activate'))
