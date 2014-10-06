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
# from agent_packager.logger import init
import agent_packager.utils as utils
# from requests import ConnectionError

# from contextlib import closing
import testtools
import os
# from testfixtures import log_capture
# import logging
import shutil
from functools import wraps
# import tarfile


TEST_RESOURCES_DIR = 'agent_packager/tests/resources/'
CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'config_file.yaml')
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_config_file.yaml')
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_config_file.yaml')
TEST_VENV = 'test_venv'
TEST_FILE = 'https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz'  # NOQA
MANAGER = 'https://github.com/cloudify-cosmo/cloudify-manager/archive/master.tar.gz'  # NOQA


def venv(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        utils.make_virtualenv(TEST_VENV)
        func(*args, **kwargs)
        shutil.rmtree(TEST_VENV)
    return execution_handler


class TestBase(testtools.TestCase):

    # @log_capture()
    # def test_set_global_verbosity_level(self, capture):
    #     lgr = init(base_level=logging.INFO)

    #     ap._set_global_verbosity_level(is_verbose_output=False)
    #     lgr.debug('TEST_LOGGER_OUTPUT')
    #     capture.check()
    #     lgr.info('TEST_LOGGER_OUTPUT')
    #     capture.check(('user', 'INFO', 'TEST_LOGGER_OUTPUT'))

    #     ap._set_global_verbosity_level(is_verbose_output=True)
    #     lgr.debug('TEST_LOGGER_OUTPUT')
    #     capture.check(
    #         ('user', 'INFO', 'TEST_LOGGER_OUTPUT'),
    #         ('user', 'DEBUG', 'TEST_LOGGER_OUTPUT'))

    # def test_import_config_file(self):
    #     outcome = ap._import_config(CONFIG_FILE)
    #     self.assertEquals(type(outcome), dict)
    #     self.assertIn('distribution', outcome.keys())

    # def test_fail_import_config_file(self):
    #     e = self.assertRaises(RuntimeError, ap._import_config, '')
    #     self.assertEquals('cannot access config file', str(e))

    # def test_import_bad_config_file_mapping(self):
    #     e = self.assertRaises(Exception, ap._import_config, BAD_CONFIG_FILE)
    #     self.assertIn('mapping values are not allowed here', str(e))

    # def test_import_bad_config_file(self):
    #     e = self.assertRaises(Exception, ap._import_config, BAD_CONFIG_FILE)
    #     self.assertIn('mapping values are not allowed here', str(e))

    # def test_run(self):
    #     p = utils.run('uname')
    #     self.assertEqual(0, p.returncode)

    # def test_run_bad_command(self):
    #     p = utils.run('suname')
    #     self.assertEqual(127, p.returncode)

    # @venv
    # def test_create_virtualenv(self):
    #     if not os.path.exists('test_venv/bin/python'):
    #         raise Exception('venv not created')

    # def test_fail_create_virtualenv(self):
    #     e = self.assertRaises(
    #          SystemExit, utils.make_virtualenv, '/test_venv')
    #     self.assertEqual('1', str(e))

    # @venv
    # def test_install_module(self):
    #     utils.install_module('xmltodict', TEST_VENV)
    #     p = utils.run('test_venv/bin/pip freeze')
    #     self.assertIn('xmltodict', p.stdout)

    # @venv
    # def test_fail_install_module(self):
    #     e = self.assertRaises(
    #         SystemExit, utils.install_module, 'BLAH!!', TEST_VENV)
    #     self.assertEqual('2', str(e))

    # def test_fail_install_module_nonexistent_venv(self):
    #     e = self.assertRaises(
    #         SystemExit, utils.install_module, 'BLAH!!', TEST_VENV)
    #     self.assertEqual('2', str(e))

    # def test_download_file(self):
    #     utils.download_file(TEST_FILE, 'file')
    #     if not os.path.isfile('file'):
    #         raise Exception('file not downloaded')
    #     os.remove('file')

    # def test_download_file_missing(self):
    #     e = self.assertRaises(
    #         SystemExit, utils.download_file,
    #         'http://www.google.com/x.tar.gz', 'file')
    #     self.assertEqual('3', str(e))

    # def test_download_bad_url(self):
    #     e = self.assertRaises(
    #         Exception, utils.download_file, 'something', 'file')
    #     self.assertIn('Invalid URL', str(e))

    # def test_download_connection_failed(self):
    #     e = self.assertRaises(
    #         ConnectionError, utils.download_file, 'http://something', 'file')
    #     self.assertIn('Connection aborted', str(e))

    # def test_download_missing_path(self):
    #     e = self.assertRaises(
    #         IOError, utils.download_file, TEST_FILE, 'x/file')
    #     self.assertIn('No such file or directory', e)

    # def test_download_no_permissions(self):
    #     e = self.assertRaises(
    #        IOError, utils.download_file, TEST_FILE, '/file')
    #     self.assertIn('Permission denied', e)

    # @venv
    # def test_download_manager_code(self):
    #     d = ap._get_manager(MANAGER, TEST_VENV)
    #     self.assertTrue(os.path.isdir(os.path.join(d, 'plugins/plugin-installer')))  # NOQA
    #     self.assertTrue(os.path.isdir(os.path.join(d, 'plugins/agent-installer')))  # NOQA
    #     self.assertTrue(os.path.isdir(os.path.join(d, 'plugins/windows-plugin-installer')))  # NOQA
    #     self.assertTrue(os.path.isdir(os.path.join(d, 'plugins/windows-agent-installer')))  # NOQA
    #     shutil.rmtree(d)

    # @venv
    # def test_tar(self):
    #     utils.tar(TEST_VENV, 'file')
    #     self.assertTrue(tarfile.is_tarfile('file'))
    #     with closing(tarfile.open('file', 'r:gz')) as tar:
    #         members = tar.getnames()
    #         self.assertIn('test_venv/bin/python', members)
    #     os.remove('file')

    # @venv
    # def test_tar_no_permissions(self):
    #     e = self.assertRaises(IOError, utils.tar, TEST_VENV, '/file')
    #     self.assertIn('Permission denied', e)

    # @venv
    # def test_tar_missing_source(self):
    #     e = self.assertRaises(OSError, utils.tar, 'missing', 'file')
    #     self.assertIn('No such file or directory', e)

    def test_create_agent_package(self):
        config = ap._import_config(CONFIG_FILE)
        ap.create_agent_package(CONFIG_FILE, force=True, verbose=True)
        shutil.rmtree(config['venv'])
        os.makedirs(config['venv'])
        utils.run('tar -xzvf {0} -C {1} --strip-components=1'.format(
            config['output_tar'], config['venv']))
        # os.remove(config['output_tar'])
        self.assertTrue(os.path.isdir(config['venv']))
        p = utils.run('{0}/bin/pip freeze'.format(config['venv']))
        self.assertIn('cloudify-plugins-common', p.stdout)
        self.assertIn('cloudify-rest-client', p.stdout)
        self.assertIn('cloudify-diamond-plugin', p.stdout)
        self.assertIn('cloudify-script-plugin', p.stdout)
        # shutil.rmtree(config['venv'])

    # @venv
    # def test_create_agent_package_existing_venv_no_force(self):
    #     e = self.assertRaises(
    #         SystemExit, ap.create_agent_package, CONFIG_FILE, verbose=True)
    #     self.assertEqual(str(e), '2')
