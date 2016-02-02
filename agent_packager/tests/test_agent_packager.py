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

__author__ = 'nir0s'

import agent_packager.packager as ap
import agent_packager.utils as utils
import agent_packager.codes as codes

import click.testing as clicktest
import imp
from contextlib import closing
# from testfixtures import LogCapture
# import logging
import tarfile
import testtools
import os
import shutil
from functools import wraps


TEST_RESOURCES_DIR = 'agent_packager/tests/resources/'
CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'config_file.yaml')
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_config_file.yaml')
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_config_file.yaml')
BASE_DIR = 'cloudify'
TEST_VENV = os.path.join(BASE_DIR, 'env')
TEST_PACKAGE = 'xmltodict'
TEST_FILE = 'https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz'  # NOQA
MANAGER = 'https://github.com/cloudify-cosmo/cloudify-manager/archive/master.tar.gz'  # NOQA
MOCK_PACKAGE = os.path.join(TEST_RESOURCES_DIR, 'mock-package')
MOCK_PACKAGE_NO_INCLUDES_FILE = os.path.join(
    TEST_RESOURCES_DIR, 'mock-package-no-includes')


def venv(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        try:
            shutil.rmtree(TEST_VENV)
        except:
            pass
        utils.make_virtualenv(TEST_VENV)
        try:
            func(*args, **kwargs)
        finally:
            shutil.rmtree(BASE_DIR)
    return execution_handler


def _invoke_click(func, args_dict):

    args_dict = args_dict or {}
    args_list = []
    for arg, value in args_dict.items():
        if value:
            args_list.append(arg + value)
        else:
            args_list.append(arg)

    return clicktest.CliRunner().invoke(getattr(ap, func), args_list)


class TestUtils(testtools.TestCase):

    def test_import_config_file(self):
        outcome = ap.import_config(CONFIG_FILE)
        self.assertEquals(type(outcome), dict)
        self.assertIn('distribution', outcome.keys())

    def test_fail_import_config_file(self):
        e = self.assertRaises(SystemExit, ap.import_config, '')
        self.assertEqual(
            codes.errors['could_not_access_config_file'], str(e))

    def test_import_bad_config_file_mapping(self):
        e = self.assertRaises(SystemExit, ap.import_config, BAD_CONFIG_FILE)
        self.assertEqual(codes.errors['invalid_yaml_file'], str(e))

    def test_run(self):
        p = utils.run('uname')
        self.assertEqual(0, p.returncode)

    def test_run_bad_command(self):
        p = utils.run('suname')
        self.assertEqual(127, p.returncode)

    @venv
    def test_create_virtualenv(self):
        if not os.path.exists(os.path.join(TEST_VENV, 'bin', 'python')):
            raise Exception('Failed to create virtualenv.')

    def test_fail_create_virtualenv_bad_dir(self):
        e = self.assertRaises(
            SystemExit, utils.make_virtualenv, '/' + TEST_VENV)
        self.assertEqual(
            codes.errors['could_not_create_virtualenv'], str(e))

    def test_fail_create_virtualenv_missing_python(self):
        e = self.assertRaises(
            SystemExit, utils.make_virtualenv, TEST_VENV,
            '/usr/bin/missing_python')
        self.assertEqual(
            codes.errors['could_not_create_virtualenv'], str(e))

    @venv
    def test_install_package(self):
        utils.install_package(TEST_PACKAGE, TEST_VENV)
        pip_freeze_output = utils.get_installed(TEST_VENV).lower()
        self.assertIn(TEST_PACKAGE, pip_freeze_output)

    @venv
    def test_install_nonexisting_package(self):
        e = self.assertRaises(
            SystemExit, utils.install_package, 'BLAH!!', TEST_VENV)
        self.assertEqual(codes.errors['could_not_install_package'], str(e))

    def test_install_package_nonexisting_venv(self):
        e = self.assertRaises(
            SystemExit, utils.install_package, TEST_PACKAGE, 'BLAH!!')
        self.assertEqual(codes.errors['could_not_install_package'], str(e))

    def test_download_file(self):
        utils.download_file(TEST_FILE, 'file')
        if not os.path.isfile('file'):
            raise Exception('file not downloaded')
        os.remove('file')

    def test_download_file_missing(self):
        e = self.assertRaises(
            SystemExit, utils.download_file,
            'http://www.google.com/x.tar.gz', 'file')
        self.assertEqual(
            codes.errors['could_not_download_file'], str(e))

    def test_download_bad_url(self):
        e = self.assertRaises(
            Exception, utils.download_file, 'something', 'file')
        self.assertIn('Invalid URL', str(e))

    def test_download_missing_path(self):
        e = self.assertRaises(
            IOError, utils.download_file, TEST_FILE, 'x/file')
        self.assertIn('No such file or directory', e)

    def test_download_no_permissions(self):
        e = self.assertRaises(IOError, utils.download_file, TEST_FILE, '/file')
        self.assertIn('Permission denied', e)

    def test_tar(self):
        content_file = os.path.join('dir', 'content.file')
        os.makedirs('dir')
        try:
            with open(content_file, 'w') as f:
                f.write('CONTENT')
            utils.tar('dir', 'tar.file')
        finally:
            shutil.rmtree('dir')
        self.assertTrue(tarfile.is_tarfile('tar.file'))
        try:
            with closing(tarfile.open('tar.file', 'r:gz')) as tar:
                members = tar.getnames()
                self.assertIn(content_file, members)
        finally:
            os.remove('tar.file')

    @venv
    def test_tar_no_permissions(self):
        e = self.assertRaises(SystemExit, utils.tar, TEST_VENV, '/file')
        self.assertEqual(codes.errors['failed_to_create_tar'], str(e))

    @venv
    def test_tar_missing_source(self):
        e = self.assertRaises(SystemExit, utils.tar, 'missing', 'file')
        self.assertEqual(codes.errors['failed_to_create_tar'], str(e))
        os.remove('file')


class TestCreate(testtools.TestCase):

    def setUp(self):
        super(TestCreate, self).setUp()
        self.packager = ap.AgentPackager(CONFIG_FILE, verbose=True)

    def test_create_agent_package(self):
        required_packages = [
            'cloudify-plugins-common',
            'cloudify-rest-client',
            'cloudify-fabric-plugin',
            'cloudify-agent',
            'pyyaml',
            'xmltodict'
        ]
        excluded_packages = [
            'cloudify-diamond-plugin',
            'cloudify-script-plugin'
        ]
        config = ap.import_config(CONFIG_FILE)
        params = {
            '-c': CONFIG_FILE,
            '-v': None,
            '-f': None
        }
        _invoke_click('create', params)
        if os.path.isdir(TEST_VENV):
            shutil.rmtree(TEST_VENV)
        os.makedirs(TEST_VENV)
        utils.run('tar -xzvf {0} -C {1} --strip-components=1'.format(
            config['output_tar'], BASE_DIR))
        os.remove(config['output_tar'])
        self.assertTrue(os.path.isdir(TEST_VENV))
        pip_freeze_output = utils.get_installed(
            TEST_VENV).lower()
        for required_package in required_packages:
            self.assertIn(required_package, pip_freeze_output)
        for excluded_package in excluded_packages:
            self.assertNotIn(excluded_package, pip_freeze_output)
        shutil.rmtree(BASE_DIR)

    def test_create_agent_package_in_existing_venv_force(self):
        utils.make_virtualenv(TEST_VENV)
        params = {
            '-f': None,
            '--no-validate': None
        }
        try:
            _invoke_click('create', params)
            # packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
            # packager.create(force=True, dryrun=False, no_validate=False)
        finally:
            shutil.rmtree(BASE_DIR)

    def test_create_agent_package_in_existing_venv_no_force(self):
        utils.make_virtualenv(TEST_VENV)
        try:
            e = self.assertRaises(SystemExit, self.packager.create,
                                  force=False, dryrun=False, no_validate=False)
            self.assertEqual(codes.errors['virtualenv_already_exists'], str(e))
        finally:
            shutil.rmtree(BASE_DIR)

    def test_dryrun(self):
        params = {
            '-c': CONFIG_FILE,
            '-v': None,
            '--dryrun': None
        }
        result = _invoke_click('create', params)
        self.assertIn('Dryrun complete!', str(result.output))
        self.assertEqual(
            codes.notifications['dryrun_complete'], result.exit_code)

    @venv
    def test_create_agent_package_no_cloudify_agent_configured(self):
        config = ap.import_config(CONFIG_FILE)
        del config['cloudify_agent_package']

        packager = ap.AgentPackager(config, verbose=True)
        e = self.assertRaises(SystemExit, packager.create, force=True)
        self.assertEqual(codes.errors['missing_cloudify_agent_config'], str(e))

    @venv
    def test_create_agent_package_existing_venv_no_force(self):
        packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
        e = self.assertRaises(SystemExit, packager.create)
        self.assertEqual(codes.errors['virtualenv_already_exists'], str(e))

    @venv
    def test_create_agent_package_tar_already_exists(self):
        config = ap.import_config(CONFIG_FILE)
        shutil.rmtree(TEST_VENV)
        try:
            with open(config['output_tar'], 'w') as a:
                a.write('CONTENT')
            packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
            e = self.assertRaises(SystemExit, packager.create)
            self.assertEqual(codes.errors['tar_already_exists'], str(e))
        finally:
            os.remove(config['output_tar'])

    @venv
    def test_generate_includes_file(self):
        utils.install_package(MOCK_PACKAGE, TEST_VENV)
        packages = {'plugins': ['cloudify-fabric-plugin']}
        packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
        includes_file = packager.generate_includes_file(packages, TEST_VENV)
        self.assertFalse(os.path.isfile('{0}c'.format(includes_file)))
        includes = imp.load_source('includes_file', includes_file)
        self.assertIn('cloudify-fabric-plugin', includes.included_plugins)
        self.assertIn('cloudify-puppet-plugin', includes.included_plugins)

    @venv
    def test_generate_includes_file_no_previous_includes_file_provided(self):
        utils.install_package(MOCK_PACKAGE_NO_INCLUDES_FILE, TEST_VENV)
        packages = {'plugins': ['cloudify-fabric-plugin']}
        packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
        includes_file = packager.generate_includes_file(packages, TEST_VENV)
        includes = imp.load_source('includes_file', includes_file)
        self.assertIn('cloudify-fabric-plugin', includes.included_plugins)

    @venv
    def test_create_agent_package_with_version_info(self):
        distro = 'ubuntu'
        release = 'trusty'
        os.environ['VERSION'] = '3.3.0'
        os.environ['PRERELEASE'] = 'm4'
        os.environ['BUILD'] = '666'
        config = ap.import_config(CONFIG_FILE)
        config.pop('output_tar')
        packager = ap.AgentPackager(config, verbose=True)
        archive = packager.set_archive_name(
            distro, release,
            os.environ['VERSION'],
            os.environ['PRERELEASE'],
            os.environ['BUILD'])
        try:
            packager = ap.AgentPackager(config, verbose=True)
            packager.create(force=True)
            self.assertTrue(os.path.isfile(archive))
        finally:
            os.remove(archive)
            os.environ.pop('VERSION')
            os.environ.pop('PRERELEASE')
            os.environ.pop('BUILD')


class TestArchiveNaming(testtools.TestCase):
    def test_naming(self):
        distro = 'ubuntu'
        release = 'trusty'
        version = '3.3.0'
        milestone = 'm4'
        build = '666'
        packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
        archive = packager.set_archive_name(
            distro, release, version, milestone, build)
        self.assertEquals(
            archive, 'cloudify-ubuntu-trusty-agent_3.3.0-m4-b666.tar.gz')

    def test_naming_no_version_info(self):
        distro = 'ubuntu'
        release = 'trusty'
        version = None
        milestone = None
        build = None
        packager = ap.AgentPackager(CONFIG_FILE, verbose=True)
        archive = packager.set_archive_name(
            distro, release, version, milestone, build)
        self.assertEquals(archive, 'cloudify-ubuntu-trusty-agent.tar.gz')
