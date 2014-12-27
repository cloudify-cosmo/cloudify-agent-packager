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
    'celery==3.0.24'
]

MODULES_LIST = [
    'cloudify_rest_client',
    'cloudify_plugins_common',
    'cloudify_script_plugin',
    'cloudify_diamond_plugin',
    'cloudify_agent_installer_plugin',
    'cloudify_plugin_installer_plugin',
    'cloudify_windows_agent_installer_plugin',
    'cloudify_windows_plugin_installer_plugin',
]

BASE_MODULES = {
    'cloudify_plugins_common': 'https://github.com/cloudify-cosmo/cloudify-rest-client/archive/master.tar.gz',  # NOQA
    'cloudify_rest_client': 'https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/master.tar.gz',  # NOQA
    'cloudify_script_plugin': 'https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/master.tar.gz',  # NOQA
    'cloudify_diamond_plugin': 'https://github.com/cloudify-cosmo/cloudify-diamond-plugin/archive/master.tar.gz',  # NOQA
    'cloudify_agent_installer_plugin': 'https://github.com/cloudify-cosmo/cloudify-agent-installer-plugin/archive/master.tar.gz',  # NOQA
    'cloudify_plugin_installer_plugin': 'https://github.com/cloudify-cosmo/cloudify-plugin-installer-plugin/archive/master.tar.gz',  # NOQA
    'cloudify_windows_agent_installer_plugin': 'https://github.com/cloudify-cosmo/cloudify-windows-agent-installer-plugin/archive/master.tar.gz',  # NOQA
    'cloudify_windows_plugin_installer_plugin': 'https://github.com/cloudify-cosmo/cloudify-windows-plugin-installer-plugin/archive/master.tar.gz',  # NOQA
}

MANDATORY_MODULES = [
    'cloudify_plugins_common',
    'cloudify_rest_client'
]

DEFAULT_CLOUDIFY_AGENT_BRANCH = 'master'
DEFAULT_CLOUDIFY_AGENT_URL = 'https://github.com/nir0s/cloudify-agent/archive/{0}.tar.gz'  # NOQA

lgr = logger.init()
verbose_output = False


def set_global_verbosity_level(is_verbose_output=False):
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
    if 'cloudify_agent_module' in config:
        modules['agent'] = config['cloudify_agent_module']
    elif 'cloudify_agent_version' in config:
        modules['agent'] = DEFAULT_CLOUDIFY_AGENT_URL.format(
            config['cloudify_agent_version'])
    for additional_module in additional_modules:
        modules['additional'].append(additional_module)
    return modules


def _validate(modules, venv):
    """validates that all requested modules are actually installed
    within the virtualenv

    :param dict modules: dict containing base, management and additional
    modules.
    :param string venv: path of virtualenv to install in.
    """

    failed = []

    def check(module, venv, failed):
        if not utils.check_installed(module.replace('_', '-'), venv):
            lgr.error('failed to validate that {0} exists in {1}'.format(
                module.replace('_', '-'), venv))
            failed.append(module.replace('_', '-'))
            return failed
    for base_module, source in modules['base'].items():
        if source:
            check(base_module, venv, failed)
    for additional_module in modules['additional']:
        check(additional_module, venv, failed)
    if 'agent' in modules:
        check('cloudify-agent', venv, failed)

    if failed:
        lgr.error('validation failed. some of the requested modules were not '
                  'installed.')
        sys.exit(10)


def create(config=None, config_file=None, force=False, dry=False,
           verbose=True):
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
    cloudify-agent-installer-plugin
    cloudify-plugin-installer-plugin
    cloudify-windows-agent-installer-plugin
    cloudify-windows-plugin-installer-plugin
    any additional modules specified under `additional_modules` in the yaml.

    Once all modules are installed, a tar.gz file will be created. The
    `output_tar` config object can be specified to determine the path to the
    output file. If omitted, a default path will be given with the
    format `/DISTRIBUTION-agent.tar.gz`.
    """
    set_global_verbosity_level(verbose)

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
            lgr.info('removing previous virtualenv...')
            shutil.rmtree(venv)
        else:
            lgr.error('virtualenv already exists at {0}. '
                      'You can use the -f flag or delete the '
                      'previous env.'.format(venv))
            sys.exit(2)

    lgr.info('creating virtualenv: {0}'.format(venv))
    utils.make_virtualenv(venv, python)

    # output file
    if os.path.isfile(destination_tar) and force:
        lgr.info('removing previous agent package...')
        os.remove(destination_tar)
    if os.path.exists(destination_tar):
            lgr.error('destination tar already exists: {0}'.format(
                destination_tar))
            sys.exit(9)

    # create modules dictionary with defaults
    lgr.debug('retrieving modules to install...')
    modules = {}
    modules['base'] = BASE_MODULES
    modules['additional'] = []
    modules['agent'] = DEFAULT_CLOUDIFY_AGENT_URL.format(
        DEFAULT_CLOUDIFY_AGENT_BRANCH)
    modules = _merge_modules(modules, config)

    if dry:
        set_global_verbosity_level(True)
    lgr.debug('modules to install: {0}'.format(json.dumps(
        modules, sort_keys=True, indent=4, separators=(',', ': '))))

    if dry:
        lgr.info('dryrun complete')
        sys.exit(0)

    # install external
    for ext_module in EXTERNAL_MODULES:
        lgr.info('installing external module {0}'.format(ext_module))
        utils.install_module(ext_module, venv)

    # install base
    base = modules['base']
    for module in MODULES_LIST:
        if base.get(module):
            lgr.info('installing base module {0} from {1}'.format(
                module.replace('_', '-'), base[module]))
            utils.install_module(base[module], venv)
        elif not base.get(module) and module in MANDATORY_MODULES:
            lgr.error('module {0} is mandatory! '
                      'Cannot be "none"'.format(module.replace('_', '-')))
            sys.exit(4)
        else:
            lgr.info('module {0} is excluded. '
                     'it will not be a part of the agent'.format(
                         module.replace('_', '-')))

    # install additional
    for module in modules['additional']:
        lgr.info('installing additional module {0}'.format(module))
        utils.install_module(module, venv)

    # install cloudify-agent
    if modules.get('agent'):
        lgr.info('installing cloudify-agent module from {0}'.format(
            modules['agent']))
        utils.install_module(modules['agent'], venv)

    # uninstall excluded modules
    lgr.info('uninstalling excluded modules (if any)...')
    for module in MODULES_LIST:
        module_name = module.replace('_', '-')
        if not base.get(module) and utils.check_installed(module_name, venv):
            lgr.info('uninstalling {0}'.format(module_name))
            utils.uninstall_module(module_name, venv)

    lgr.info('validating installation...')
    _validate(modules, venv)

    # create agent tar
    lgr.info('creating tar file: {0}'.format(destination_tar))
    utils.tar(venv, destination_tar)

    if not keep_venv:
        lgr.info('removing origin virtualenv')
        shutil.rmtree(venv)

    lgr.info('process complete!')
    lgr.info('the following modules were installed in the agent:\n{0}'.format(
        utils.get_installed(venv)))


class PackagerError(Exception):
    pass
