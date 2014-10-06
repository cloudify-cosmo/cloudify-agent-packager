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
DEFAULT_OUTPUT_TAR_PATH = '/{0}-agent.tar.gz'
DEFAULT_VENV_PATH = '/{0}-agent/env'

EXTERNAL_MODULES = [
    'celery==3.0.24'
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
    lgr.debug('extracting {0} to {1}'.format(tmp_tar, manager_tmp_dir))
    utils.run('tar -xzvf {0} -C {1} --strip-components=1'.format(
        tmp_tar, manager_tmp_dir))
    return manager_tmp_dir


def create_agent_package(config_file, force=False, verbose=True):
    """Creates an agent package (tar.gz)

    This will try to identify the distribution of the host you're running on.
    If it can't identify it for some reason, you'll have to supply a
    `distribution` config object in the config.yaml.

    If not all `base` AND `management` modules are explicitly specified,
    A `version` config object must be specified in the config.yaml as well,
    which will be used to retrieve the corrent version of the module.

    A virtualenv will be created under `/DISTRIBUTION-agent/env` unless
    configured in the yaml under the `venv` property.
    The order of the modules' installation is as follows:

    cloudify-rest-service
    cloudify-plugins-common
    cloudify-script-plugin
    agent and plugin installers from cloudify-manager
    any additional modules specified under `additional_modules` in the yaml.

    When all modules are installed, a tar.gz file will be created. The
    `output_tar` config object can be specified to determine the path to the
    output file. If omitted, a default path will be given with the
    format `/DISTRIBUTION-agent.tar.gz`.
    """
    _set_global_verbosity_level(verbose)

    config = _import_config(config_file) if config_file else _import_config()
    try:
        distro = config.get('distribution', platform.dist()[0])
    except:
        lgr.error('distribution not found in configuration '
                  'and could not be retrieved automatically. '
                  'please specify the distribution in the yaml.')
        sys.exit(1)

    venv = config.get('venv', DEFAULT_VENV_PATH.format(distro))
    destination_tar = config.get('output_tar',
                                 DEFAULT_OUTPUT_TAR_PATH.format(distro))

    lgr.debug('distibution is: {0}'.format(distro))
    lgr.debug('venv is: {0}'.format(venv))
    lgr.debug('destination tarfile is: {0}'.format(destination_tar))

    # create modules dictionary
    lgr.debug('retrieving modules to install...')
    modules = {}
    modules['base'] = BASE_MODULES
    modules['management'] = MANAGEMENT_MODULES
    modules['additional'] = []
    modules = _merge_modules(modules, config)

    lgr.debug('modules to install: {0}'.format(json.dumps(
        modules, sort_keys=True, indent=4, separators=(',', ': '))))

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
    utils.make_virtualenv(venv)

    # install external
    lgr.info('installing external modules...')
    for ext_module in EXTERNAL_MODULES:
        utils.install_module(ext_module, venv)

    # install base
    lgr.info('installing base modules...')
    utils.install_module(modules['base']['rest_client'], venv)
    utils.install_module(modules['base']['plugins_common'], venv)
    utils.install_module(modules['base']['script_plugin'], venv)
    if modules['base']['diamond_plugin']:
        utils.install_module(modules['base']['diamond_plugin'], venv)

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
            utils.install_module(mgmt_module, venv)

    # install additional
    lgr.info('installing additional plugins...')
    for module in modules['additional']:
        utils.install_module(module, venv)

    # create agent tar
    lgr.info('creating tar file: {0}'.format(destination_tar))
    utils.tar(venv, destination_tar)


class PackagerError(Exception):
    pass
