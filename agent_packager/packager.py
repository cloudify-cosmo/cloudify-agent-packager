import logger
import logging
import yaml
import json
import platform
import shutil
import os
import sys

import utils


DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_OUTPUT_TAR_PATH = '{0}-{1}-agent.tar.gz'
DEFAULT_VENV_PATH = 'cloudify/{0}-{1}-agent/env'

EXTERNAL_MODULES = [
    'celery==3.1.17'
]

BASE_MODULES = {
    'plugins_common': 'https://github.com/cloudify-cosmo/cloudify-rest-client/archive/master.tar.gz',  # NOQA
    'rest_client': 'https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/master.tar.gz',  # NOQA
    'script_plugin': 'https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/master.tar.gz',  # NOQA
    'diamond_plugin': 'https://github.com/cloudify-cosmo/cloudify-diamond-plugin/archive/master.tar.gz'  # NOQA
}

MANAGER_REPO_URL = 'https://github.com/cloudify-cosmo/cloudify-manager/archive/{0}.tar.gz'  # NOQA

MANAGEMENT_MODULES = {
    'agent_installer': 'plugins/agent-installer',
    'plugin_installer': 'plugins/plugin-installer',
    'windows_agent_installer': 'plugins/windows-agent-installer',
    'windows_plugin_installer': 'plugins/windows-plugin-installer',
}


lgr = logger.init()
verbose_output = False


def _set_global_verbosity_level(is_verbose_output=False):
    """sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    """
    global verbose_output
    # TODO: (IMPRV) only raise exceptions in verbose mode
    verbose_output = is_verbose_output
    if verbose_output:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)


def _import_config(config_file=DEFAULT_CONFIG_FILE):
    """returns a configuration object

    :param string config_file: path to config file
    """
    # get config file path
    lgr.debug('config file is: {0}'.format(config_file))
    # append to path for importing
    try:
        lgr.debug('importing config...')
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        lgr.error(str(ex))
        raise RuntimeError('cannot access config file')
    except yaml.parser.ParserError as ex:
        lgr.error('invalid yaml file: {0}'.format(ex))
        raise RuntimeError('invalid yaml file')


def _merge_modules(modules, config):
    """merges the default modules with the modules from the config yaml

    :param dict modules: dict containing base, management and additional
    modules.
    :param dict config: dict containing the config.
    """
    additional_modules = config.get('additional_modules', [])
    modules['base'].update(config.get('base_modules', {}))
    modules['management'].update(config.get('management_modules', {}))
    for additional_module in additional_modules:
        modules['additional'].append(additional_module)
    return modules


def _get_manager(source, venv):
    """retrieves the manager repo

    This is used by default to install the installer plugins.

    :param string source: url of manager tar.gz file.
    :param string venv: virtualenv path.
    """
    manager_tmp_dir = os.path.join(venv, 'manager')
    os.makedirs(manager_tmp_dir)
    tmp_tar = '{0}/tmp.tar.gz'.format(manager_tmp_dir)
    lgr.debug('downloading manager code from: {0}'.format(source))
    utils.download_file(source, tmp_tar)
    # TODO: find a workaround for strip-components using tarfile
    # TODO: check if tar before untaring
    lgr.debug('extracting {0} to {1}'.format(tmp_tar, manager_tmp_dir))
    utils.run('tar -xzvf {0} -C {1} --strip-components=1'.format(
        tmp_tar, manager_tmp_dir))
    return manager_tmp_dir


def create(config=None, config_file=None, force=False, verbose=True):
    """Creates an agent package (tar.gz)

    This will try to identify the distribution of the host you're running on.
    If it can't identify it for some reason, you'll have to supply a
    `distribution` config object in the config.yaml.

    A virtualenv will be created under `/DISTRIBUTION-agent/env` unless
    configured in the yaml under the `venv` property.
    The order of the modules' installation is as follows:

    cloudify-rest-service
    cloudify-plugins-common
    cloudify-script-plugin
    cloudify-diamond-plugin
    agent and plugin installers from cloudify-manager
    any additional modules specified under `additional_modules` in the yaml.

    Once all modules are installed, a tar.gz file will be created. The
    `output_tar` config object can be specified to determine the path to the
    output file. If omitted, a default path will be given with the
    format `/DISTRIBUTION-agent.tar.gz`.
    """
    _set_global_verbosity_level(verbose)

    if not config:
        config = _import_config(config_file) if config_file else \
            _import_config()
        config = {} if not config else config
    try:
        distro = config.get('distribution', platform.dist()[0])
        release = config.get('release', platform.dist()[2])
    except Exception as ex:
        lgr.error('distribution not found in configuration '
                  'and could not be retrieved automatically. '
                  'please specify the distribution in the yaml. '
                  '({0})'.format(ex.message))
        sys.exit(1)

    python = config.get('python_path', '/usr/bin/python')
    venv = config.get('venv', DEFAULT_VENV_PATH.format(distro, release))
    keep_venv = config.get('keep_venv', False)
    destination_tar = config.get('output_tar',
                                 DEFAULT_OUTPUT_TAR_PATH.format(
                                     distro, release))

    lgr.debug('distibution is: {0}'.format(distro))
    lgr.debug('distribution release is: {0}'.format(release))
    lgr.debug('python path is: {0}'.format(python))
    lgr.debug('venv is: {0}'.format(venv))
    lgr.debug('destination tarfile is: {0}'.format(destination_tar))

    # virtualenv
    if os.path.isdir(venv):
        if force:
            lgr.info('removing previous venv...')
            shutil.rmtree(venv)
        else:
            lgr.error('virtualenv already exists at {0}. '
                      'You can use the -f flag or delete the '
                      'previous env.'.format(venv))
            sys.exit(2)

    lgr.info('creating virtual environment: {0}'.format(venv))
    utils.make_virtualenv(venv, python)

    # output file
    if os.path.isfile(destination_tar) and force:
        lgr.info('removing previous agent package...')
        os.remove(destination_tar)
    if os.path.exists(destination_tar):
            lgr.error('destination tar already exists: {0}'.format(
                destination_tar))
            sys.exit(9)

    # create modules dictionary
    lgr.debug('retrieving modules to install...')
    modules = {}
    modules['base'] = BASE_MODULES
    modules['management'] = MANAGEMENT_MODULES
    modules['additional'] = []
    modules = _merge_modules(modules, config)

    lgr.debug('modules to install: {0}'.format(json.dumps(
        modules, sort_keys=True, indent=4, separators=(',', ': '))))

    # install external
    lgr.info('installing external modules...')
    for ext_module in EXTERNAL_MODULES:
        utils.install_module(ext_module, venv)

    # install base
    lgr.info('installing base modules...')
    base = modules['base']

    if base.get('rest_client'):
        utils.install_module(base['rest_client'], venv)
    if base.get('plugins_common'):
        utils.install_module(base['plugins_common'], venv)
    if base.get('script_plugin'):
        utils.install_module(base['script_plugin'], venv)
    if base.get(bool('diamond_plugin')):
        utils.install_module(base['diamond_plugin'], venv)

    # install management
    lgr.debug('retrieiving management modules code...')
    version = config.get('management_modules_version', 'master')
    manager_tmp_dir = _get_manager(MANAGER_REPO_URL.format(version), venv)

    lgr.info('installing management modules...')
    for mgmt_module in modules['management'].values():
        if os.path.isdir(os.path.join(manager_tmp_dir, mgmt_module)):
            utils.install_module(os.path.join(
                manager_tmp_dir, mgmt_module), venv)
        else:
            if mgmt_module:
                utils.install_module(mgmt_module, venv)

    # install additional
    lgr.info('installing additional plugins...')
    for module in modules['additional']:
        utils.install_module(module, venv)

    # create agent tar
    lgr.info('creating tar file: {0}'.format(destination_tar))
    utils.tar(venv, destination_tar)
    if not keep_venv:
        lgr.info('removing origin venv')
        shutil.rmtree(venv)


class PackagerError(Exception):
    pass
