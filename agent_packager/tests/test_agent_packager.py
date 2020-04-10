########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import agent_packager.packager as ap
import agent_packager.cli as cli
import agent_packager.utils as utils
from agent_packager import exceptions
from requests import ConnectionError

import pytest
import logging
import tarfile
import os
import shutil


TEST_RESOURCES_DIR = 'agent_packager/tests/resources/'
CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'config_file.yaml')
TARGET_PACKAGE = 'Ubuntu-trusty-agent.tar.gz'  # same as in the config file
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_config_file.yaml')
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_config_file.yaml')
BASE_DIR = 'cloudify'
TEST_VENV = os.path.join(BASE_DIR, 'env')
TEST_MODULE = 'xmltodict'
TEST_FILE = 'https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz'  # NOQA
MANAGER = 'https://github.com/cloudify-cosmo/cloudify-manager/archive/master.tar.gz'  # NOQA
MOCK_MODULE = os.path.join(TEST_RESOURCES_DIR, 'mock-module')


@pytest.fixture
def venv():
    shutil.rmtree(TEST_VENV, ignore_errors=True)
    utils.make_virtualenv(TEST_VENV)
    try:
        yield
    finally:
        shutil.rmtree(TEST_VENV)


def test_set_global_verbosity_level(caplog):
    lgr = logging.getLogger()

    ap.set_global_verbosity_level(is_verbose_output=False)
    lgr.debug('TEST_LOG')
    assert not caplog.records
    lgr.info('TEST_LOG')
    assert caplog.record_tuples == [('root', logging.INFO, 'TEST_LOG')]

    caplog.clear()

    ap.set_global_verbosity_level(is_verbose_output=True)
    lgr.debug('TEST_LOG')
    assert caplog.record_tuples == [('root', logging.DEBUG, 'TEST_LOG')]


def test_import_config_file():
    outcome = ap._import_config(CONFIG_FILE)
    assert isinstance(outcome, dict)
    assert 'distribution' in outcome


def test_fail_import_config_file():
    with pytest.raises(exceptions.ConfigFileError, match='No such file'):
        ap._import_config('')


def test_import_bad_config_file_mapping():
    with pytest.raises(exceptions.ConfigFileError):
        ap._import_config(BAD_CONFIG_FILE)


def test_run():
    p = utils.run('uname')
    assert p.returncode == 0


def test_run_bad_command():
    p = utils.run('suname')
    assert p.returncode == 127


def test_create_virtualenv(venv):
    assert os.path.exists('{0}/bin/python'.format(TEST_VENV))


def test_fail_create_virtualenv_bad_dir():
    target = '/' + TEST_VENV
    with pytest.raises(exceptions.VirtualenvCreationError, match=target):
        utils.make_virtualenv(target)


def test_fail_create_virtualenv_missing_python():
    with pytest.raises(exceptions.VirtualenvCreationError):
        utils.make_virtualenv(TEST_VENV, '/usr/bin/missing_python')


def test_install_module(venv):
    utils.install_module(TEST_MODULE, TEST_VENV)
    pip_freeze_output = utils.get_installed(TEST_VENV).lower()
    assert TEST_MODULE in pip_freeze_output


def test_install_nonexisting_module(venv):
    with pytest.raises(exceptions.PipInstallError):
        utils.install_module('BLAH!!', TEST_VENV)


def test_install_module_nonexisting_venv():
    with pytest.raises(exceptions.PipInstallError):
        utils.install_module(TEST_MODULE, 'BLAH!!')


def test_download_file():
    utils.download_file(TEST_FILE, 'file')
    assert os.path.isfile('file')
    os.remove('file')


def test_download_bad_url():
    with pytest.raises(Exception, match='Invalid URL'):
        utils.download_file('something', 'file')


def test_download_connection_failed():
    with pytest.raises(ConnectionError):
        utils.download_file('http://nonexistent.test', 'file')


def test_download_missing_path():
    with pytest.raises(IOError):
        utils.download_file(TEST_FILE, 'x/file')


def test_download_no_permissions():
    with pytest.raises(IOError):
        utils.download_file(TEST_FILE, '/file')


def test_tar():
    os.makedirs('dir')
    with open('dir/content.file', 'w') as f:
        f.write('CONTENT')
    utils.tar('dir', 'tar.file')
    shutil.rmtree('dir')
    assert tarfile.is_tarfile('tar.file')
    with tarfile.open('tar.file', 'r:gz') as tar:
        members = tar.getnames()
        assert 'dir/content.file' in members
    os.remove('tar.file')


def test_tar_no_permissions(venv):
    with pytest.raises(exceptions.TarCreateError):
        utils.tar(TEST_VENV, '/file')


def test_tar_missing_source():
    with pytest.raises(exceptions.TarCreateError):
        utils.tar('missing', 'file')
    os.remove('file')


def test_create_agent_package():
    cli_options = {
        '--config': CONFIG_FILE,
        '--force': True,
        '--dryrun': False,
        '--no-validation': False,
        '--verbose': True
    }
    required_modules = [
        'cloudify-plugins-common',
        'cloudify-rest-client',
        'cloudify-agent',
        'pyyaml',
    ]
    config = ap._import_config(CONFIG_FILE)
    cli._run(cli_options)
    if os.path.isdir(TEST_VENV):
        shutil.rmtree(TEST_VENV)
    os.makedirs(TEST_VENV)
    utils.run('tar -xzvf {0} -C {1} --strip-components=1'.format(
        config['output_tar'], BASE_DIR))
    os.remove(config['output_tar'])
    assert os.path.isdir(TEST_VENV)
    pip_freeze_output = utils.get_installed(TEST_VENV).lower()
    for required_module in required_modules:
        assert required_module in pip_freeze_output
    shutil.rmtree(TEST_VENV)


def test_create_agent_package_in_existing_venv_force():
    cli_options = {
        '--config': CONFIG_FILE,
        '--force': True,
        '--dryrun': False,
        '--no-validation': False,
        '--verbose': True
    }
    utils.make_virtualenv(TEST_VENV)
    try:
        cli._run(cli_options)
    finally:
        shutil.rmtree(TEST_VENV)
        os.remove(TARGET_PACKAGE)


def test_create_agent_package_in_existing_venv_no_force(venv):
    cli_options = {
        '--config': CONFIG_FILE,
        '--force': False,
        '--dryrun': False,
        '--no-validation': False,
        '--verbose': True
    }
    with pytest.raises(
            exceptions.VirtualenvCreationError, match='already exists'):
        cli._run(cli_options)


def test_dryrun(caplog):
    cli_options = {
        '--config': CONFIG_FILE,
        '--force': False,
        '--dryrun': True,
        '--no-validation': False,
        '--verbose': True
    }
    cli._run(cli_options)
    assert ('root', logging.INFO, 'Dryrun complete') in caplog.record_tuples


def test_create_agent_package_no_cloudify_agent_configured(venv):
    config = ap._import_config(CONFIG_FILE)
    del config['cloudify_agent_module']

    with pytest.raises(
            exceptions.ConfigFileError, match='cloudify_agent_module'):
        ap.create(config, None, force=True, verbose=True)


def test_create_agent_package_existing_venv_no_force(venv):
    with pytest.raises(
            exceptions.VirtualenvCreationError, match='already exists'):
        ap.create(None, CONFIG_FILE, verbose=True)


def test_create_agent_package_tar_already_exists(venv):
    config = ap._import_config(CONFIG_FILE)
    shutil.rmtree(TEST_VENV)
    with open(config['output_tar'], 'w') as a:
        a.write('CONTENT')
    try:
        with pytest.raises(
                exceptions.TarCreateError, match='already exists'):
            ap.create(None, CONFIG_FILE, verbose=True)
    finally:
        os.remove(config['output_tar'])


def test_create_agent_package_with_version_info(venv):
    distro = 'Ubuntu'
    release = 'trusty'
    os.environ['VERSION'] = '3.3.0'
    os.environ['PRERELEASE'] = 'm4'
    os.environ['BUILD'] = '666'
    config = ap._import_config(CONFIG_FILE)
    config.pop('output_tar')
    archive = ap._name_archive(
        distro, release,
        os.environ['VERSION'],
        os.environ['PRERELEASE'],
        os.environ['BUILD'])
    try:
        ap.create(config, force=True, verbose=True)
        assert os.path.isfile(archive)
    finally:
        os.remove(archive)
        os.environ.pop('VERSION')
        os.environ.pop('PRERELEASE')
        os.environ.pop('BUILD')


def test_naming():
    distro = 'Ubuntu'
    release = 'trusty'
    version = '3.3.0'
    milestone = 'm4'
    build = '666'
    archive = ap._name_archive(distro, release, version, milestone, build)
    assert archive == 'Ubuntu-trusty-agent_3.3.0-m4-b666.tar.gz'


def test_naming_no_version_info():
    distro = 'Ubuntu'
    release = 'trusty'
    version = None
    milestone = None
    build = None
    archive = ap._name_archive(distro, release, version, milestone, build)
    assert archive == 'Ubuntu-trusty-agent.tar.gz'
