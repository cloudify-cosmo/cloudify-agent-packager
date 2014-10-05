import logger
import logging
import yaml
import json
import platform
import subprocess
import shutil
import requests
import os
import tarfile
import sys

DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_OUTPUT_TAR_PATH = '{0}/{1}-agent.tar.gz'
DEFAULT_VENV_PATH = '{0}/{1}-agent/env'

MODULES = {
    'plugins_common': 'https://github.com/cloudify-cosmo/cloudify-rest-client/archive/{0}.tar.gz',  # NOQA
    'rest_client': 'https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/{0}.tar.gz',  # NOQA
    'script_plugin': 'https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/{0}.tar.gz',  # NOQA
    'rest_service': 'https://github.com/cloudify-cosmo/cloudify-manager/archive/{0}.tar.gz'  # NOQA
}

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


def _run(cmd):
    return subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _make_virtualenv(virtualenv_dir):
    lgr.debug('virtualenv_dir: {0}'.format(virtualenv_dir))
    create_virtualenv_cmd = 'virtualenv {0}'.format(virtualenv_dir)
    lgr.debug('virtualenv_cmd: {0}'.format(create_virtualenv_cmd))
    p = _run(create_virtualenv_cmd)
    (stdout, stderr) = p.communicate()
    lgr.debug('stdout: {0}'.format(stdout))
    lgr.debug('stderr: {0}'.format(stderr))


def _install_module(module, venv):
    install_cmd = '{0}/bin/pip install {1}'.format(venv, module)
    lgr.debug('install_cmd: {0}'.format(install_cmd))
    p = _run(install_cmd)
    (stdout, stderr) = p.communicate()
    lgr.debug('stdout: {0}'.format(stdout))
    lgr.debug('stderr: {0}'.format(stderr))


def _merge_modules(modules, config):
    additional_modules = config.get('additional_modules', [])
    modules['base'].update(config.get('base_modules', {}))
    modules['management'].update(config.get('management_modules', {}))
    for additional_module in additional_modules:
        modules['additional'].append(additional_module)
    return modules


def _download_file(url, destination):
    lgr.debug('downloading {0} to {1}...'.format(url, destination))
    destination = destination if destination else url.split('/')[-1]
    r = requests.get(url, stream=True)
    with open(destination, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    return destination


def _get_manager(source, venv):
    manager_tmp_dir = os.path.join(venv, 'manager')
    os.makedirs(manager_tmp_dir)
    tmp_tar = '{0}/tmp.tar.gz'.format(manager_tmp_dir)
    lgr.debug('downloading manager code from: {0}'.format(source))
    _download_file(source, tmp_tar)
    # TODO: find a workaround for strip-components using tarfile
    lgr.debug('extracting {0} to {1}'.format(tmp_tar, manager_tmp_dir))
    _run('tar -xzvf {0} -C {1} --strip-components=1'.format(
        tmp_tar, manager_tmp_dir))
    return manager_tmp_dir


def _tar(source, destination):
    with tarfile.open(destination, "w:gz") as tar:
        tar.add(source, arcname=os.path.basename(source))


def _untar(source, destination):
    with tarfile.open(source, 'r:gz') as tar:
        tar.extractall(destination)


def create(config_file, verbose=True, cleanstart=True):
    """Creates an agent package (tar.gz)

    This will try to identify the distribution of the host you're running on.
    If it can't identify it for some reason, you'll have to supply a
    `distribution` config object in the config.yaml.

    If not all `base` AND `management` modules are explicitly specified,
    A `version` config object must be specified in the config.yaml as well.

    A virtualenv will be created
    The order of the modules' installation is as follows:

    cloudify-rest-service
    cloudify-plugins-common
    cloudify-script-plugin
    agent and plugin installers from cloudify-manager
    any additional modules specified under `additional_modules` in the yaml.

    When all modules are installed, a tar.gz file will be created. The
    `output_tar` config object can be specified to determine the path to the
    output file. If omitted, a default path will be given with the
    format `BASE_DIR/DISTRIBUTION-agent.tar.gz`.
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

    base_dir = config.get('base_dir', '')
    venv = config.get('venv', DEFAULT_VENV_PATH.format(base_dir, distro))

    try:
        version = config['version']
    except ValueError:
        lgr.warning('version is mandatory if not all base and management '
                    'modules are specified in the yaml.')

    destination_tar = config.get('output_tar',
                                 DEFAULT_OUTPUT_TAR_PATH.format(
                                     base_dir, distro))
    lgr.debug('distibution is: {0}'.format(distro))
    lgr.debug('venv is: {0}'.format(venv))

    # create modules dictionary
    lgr.debug('retrieving modules to install...')
    modules = {}
    modules['base'] = MODULES
    modules['management'] = MANAGEMENT_MODULES
    modules['additional'] = []
    for base_module, url in modules['base'].items():
        modules['base'][base_module] = url.format(version)
    for mgmt_module, url in modules['management'].items():
        modules['management'][mgmt_module] = url.format(version)
    modules = _merge_modules(modules, config)

    lgr.debug(json.dumps(
        modules, sort_keys=True, indent=4, separators=(',', ': ')))

    # virtualenv
    if os.path.isdir(venv) and cleanstart:
        lgr.debug('removing previous venv...')
        shutil.rmtree(venv)
    lgr.info('creating virtual environment: {0}'.format(venv))
    _make_virtualenv(venv)

    # install base
    lgr.info('installing base modules...')
    _install_module(modules['base']['rest_client'], venv)
    _install_module(modules['base']['plugins_common'], venv)
    _install_module(modules['base']['script_plugin'], venv)

    # install management
    lgr.debug('retrieiving management plugins code...')
    manager_tmp_dir = _get_manager(modules['base']['rest_service'], venv)

    lgr.info('installing management modules...')
    for mgmt_module in modules['management']:
        _install_module(os.path.join(manager_tmp_dir, mgmt_module), venv)

    # install additional
    lgr.info('installing additional plugins...')
    for module in modules['additional']:
        _install_module(module, venv)

    # create agent tar
    lgr.info('creating tar file: {0}'.format(destination_tar))
    _tar(venv, destination_tar)


class PackagerError(Exception):
    pass
