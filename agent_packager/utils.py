import codes

import subprocess
import sys
import re
import os
import platform
from threading import Thread
import time
import logging
from contextlib import closing
import tarfile
import urllib

import logger


IS_VIRTUALENV = hasattr(sys, 'real_prefix')
PROCESS_POLLING_INTERVAL = 0.1

lgr = logger.init()


class PipeReader(Thread):
    def __init__(self, fd, proc, logger, log_level):
        Thread.__init__(self)
        self.fd = fd
        self.proc = proc
        self.logger = logger
        self.log_level = log_level
        self.aggr = ''

    def run(self):
        while self.proc.poll() is None:
            output = self.fd.readline()
            if len(output) > 0:
                self.aggr += output
                self.logger.log(self.log_level, output)
            else:
                time.sleep(PROCESS_POLLING_INTERVAL)


# TODO: implement using sh
def run(cmd, suppress_errors=False, suppress_output=False):
    """Executes a command
    """
    lgr.debug('Executing: {0}...'.format(cmd))
    pipe = subprocess.PIPE
    proc = subprocess.Popen(cmd, shell=True, stdout=pipe, stderr=pipe)

    stderr_log_level = logging.NOTSET if suppress_errors else logging.ERROR
    stdout_log_level = logging.NOTSET if suppress_output else logging.DEBUG

    stdout_thread = PipeReader(proc.stdout, proc, lgr, stdout_log_level)
    stderr_thread = PipeReader(proc.stderr, proc, lgr, stderr_log_level)

    stdout_thread.start()
    stderr_thread.start()

    while proc.poll() is None:
        time.sleep(PROCESS_POLLING_INTERVAL)

    stdout_thread.join()
    stderr_thread.join()

    proc.aggr_stdout = stdout_thread.aggr
    proc.aggr_stderr = stderr_thread.aggr

    return proc


def make_virtualenv(virtualenv_dir, python='/usr/bin/python'):
    """Creates a virtualenv

    :param string virtualenv_dir: path of virtualenv to create
    """
    lgr.debug('virtualenv_dir: {0}'.format(virtualenv_dir))
    p = run('virtualenv -p {0} {1}'.format(python, virtualenv_dir))
    if not p.returncode == 0:
        lgr.error('Could not create venv: {0}'.format(virtualenv_dir))
        sys.exit(codes.errors['could_not_create_virtualenv'])


def install_package(package, venv, pip_args):
    """Installs a package in a virtualenv

    :param string package: package to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('Installing {0} in venv {1}'.format(package, venv))

    pip_cmd = [os.path.join(get_env_bin_path(venv), 'pip'), 'install', package]
    if pip_args:
        pip_cmd.append(pip_args)
    p = run(' '.join(pip_cmd))
    if not p.returncode == 0:
        lgr.error('Could not install package: {0}'.format(package))
        sys.exit(codes.errors['could_not_install_package'])


def install_requirements_file(path, venv, pip_args=''):
    """Installs packages from a requirements file in a virtualenv

    :param string path: path to requirements file1
    :param string venv: path of virtualenv to install in
    """
    lgr.debug('Installing {0} in venv {1}'.format(path, venv))
    pip_cmd = [os.path.join(
        get_env_bin_path(venv), 'pip'), 'install', '-r{0}'.format(path)]
    if pip_args:
        pip_cmd.append(pip_args)
    p = run(' '.join(pip_cmd))
    if not p.returncode == 0:
        lgr.error('Could not install from requirements file: {0}'.format(path))
        sys.exit(codes.errors['could_not_install_from_requirements_file'])


def uninstall_package(package, venv):
    """Uninstalls a package from a virtualenv

    :param string package: package to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('Uninstalling {0} in venv {1}'.format(package, venv))
    pip_cmd = [os.path.join(get_env_bin_path(venv), 'pip'), '-y', package]
    p = run(' '.join(pip_cmd))
    if not p.returncode == 0:
        lgr.error('Could not uninstall package: {0}'.format(package))
        sys.exit(codes.errors['could_not_uninstall_package'])


def get_installed(venv):
    p = run('{0} freeze'.format(
        os.path.join(get_env_bin_path(venv), 'pip')), suppress_output=True)
    return p.aggr_stdout


def check_installed(package, venv):
    """Checks to see if a package is installed

    :param string package: package to install. can be a url or a path.
    :param string venv: path of virtualenv to install in.
    """
    installed_packages = get_installed(venv)
    if re.search(r'{0}'.format(package), installed_packages.lower()):
        lgr.debug('Package {0} is installed in {1}'.format(package, venv))
        return True
    lgr.debug('Package {0} is not installed in {1}'.format(package, venv))
    return False


def download_file(url, destination):
    lgr.info('Downloading {0} to {1}...'.format(url, destination))
    final_url = urllib.urlopen(url).geturl()
    if final_url != url:
        lgr.debug('Redirected to {0}'.format(final_url))
    f = urllib.URLopener()
    f.retrieve(final_url, destination)


def tar(source, destination):
    lgr.info('Creating tar.gz archive: {0}...'.format(destination))
    with closing(tarfile.open(destination, "w:gz")) as tar:
        tar.add(source, arcname=os.path.basename(source))
    # # TODO: solve or depracate..
    # # TODO: apparently, it will tar the first child dir of
    # # TODO: source, and not the given parent.
    # # with closing(tarfile.open(destination, "w:gz")) as tar:
    # #     tar.add(source, arcname=os.path.basename(source))
    # # WORKAROUND IMPLEMENTATION
    # lgr.info('Creating tar file: {0}'.format(destination))
    # r = run('tar czvf {0} {1}'.format(
    #     destination, source), suppress_output=True)
    # if not r.returncode == 0:
    #     lgr.error('Failed to create tar file.')
    #     sys.exit(codes.errors['failed_to_create_tar'])


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


def get_package_name(package):
    """Returns a package's name
    """
    return package.replace('_', '-')


def get_os_props():
    """returns a tuple of the distro and release
    """
    data = platform.dist()
    distro = data[0]
    release = data[2]
    return distro, release
