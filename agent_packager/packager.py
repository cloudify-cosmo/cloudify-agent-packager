import logger
import logging
import yaml
import json
import platform
import shutil
import os
import sys
import imp

import utils
import codes

from jingen.jingen import Jingen


DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_OUTPUT_TAR_PATH = '{0}-{1}-agent.tar.gz'
DEFAULT_VENV_PATH = 'cloudify/env'

INCLUDES_FILE = 'included_plugins.py'
TEMPLATE_FILE = 'included_plugins.py.j2'
TEMPLATE_DIR = 'resources'

EXTERNAL_MODULES = [
    'celery==3.1.17'
]

CORE_MODULES_LIST = [
    'cloudify_rest_client',
    'cloudify_plugins_common',
]

CORE_PLUGINS_LIST = [
    'cloudify_script_plugin',
    'cloudify_diamond_plugin',
]

MANDATORY_MODULES = [
    'cloudify_rest_client',
    'cloudify_plugins_common',
]

DEFAULT_CLOUDIFY_AGENT_URL = 'https://github.com/cloudify-cosmo/cloudify-agent/archive/{0}.tar.gz'  # NOQA

lgr = logger.init()
verbose_output = False


def set_global_verbosity_level(is_verbose_output=False):
    """Sets the global verbosity level for console and the lgr logger.

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
    """Returns a configuration object

    :param string config_file: path to config file
    """
    lgr.debug('Importing config: {0}...'.format(config_file))
    try:
        with open(config_file, 'r') as c:
            return yaml.safe_load(c.read())
    except IOError as ex:
        lgr.error(str(ex))
        lgr.error('Cannot access config file')
        sys.exit(codes.errors['could_not_access_config_file'])
    except (yaml.parser.ParserError, yaml.scanner.ScannerError) as ex:
        lgr.error(str(ex))
        lgr.error('Invalid yaml file')
        sys.exit(codes.errors['invalid_yaml_file'])


def _make_venv(venv, python, force):
    """Handles the virtualenv.

    removes the virtualenv if required, else, notifies
    that it already exists. If it doesn't exist, it will be
    created.
    :param string venv: path of virtualenv to install in.
    :param string python: python binary path to use.
    :param bool force: whether to force creation or not if it
     already exists.
    """
    if utils.is_virtualenv(venv):
        if force:
            lgr.info('Installing within existing virtualenv: {0}'.format(venv))
        else:
            lgr.error('Virtualenv already exists at {0}. '
                      'You can use the -f flag to install within the '
                      'existing virtualenv.'.format(venv))
            sys.exit(codes.errors['virtualenv_already_exists'])
    else:
        lgr.debug('Creating virtualenv: {0}'.format(venv))
        utils.make_virtualenv(venv, python)


def _handle_output_file(destination_tar, force):
    """Handles the output tar.

    removes the output file if required, else, notifies
    that it already exists.

    :param string destination_tar: destination tar path
    :param bool force: whether to force creation or not if
     it already exists.
    """
    if os.path.isfile(destination_tar) and force:
        lgr.info('Removing previous agent package...')
        os.remove(destination_tar)
    if os.path.exists(destination_tar):
            lgr.error('Destination tar already exists: {0}'.format(
                destination_tar))
            sys.exit(codes.errors['tar_already_exists'])


def _set_defaults():
    """sets the default modules dictionary
    """
    modules = {}
    modules['core_modules'] = {}
    modules['core_plugins'] = {}
    modules['additional_modules'] = []
    modules['additional_plugins'] = {}
    modules['agent'] = ""
    return modules


def _merge_modules(modules, config):
    """merges the default modules with the modules from the config yaml
    :param dict modules: dict containing core and additional
    modules and the cloudify-agent module.
    :param dict config: dict containing the config.
    """
    lgr.debug('Merging default modules with config...')

    if 'requirements_file' in config:
        modules['requirements_file'] = config['requirements_file']

    modules['core_modules'].update(config.get('core_modules', {}))
    modules['core_plugins'].update(config.get('core_plugins', {}))

    additional_modules = config.get('additional_modules', [])
    for additional_module in additional_modules:
        modules['additional_modules'].append(additional_module)
    modules['additional_plugins'].update(config.get('additional_plugins', {}))

    if 'cloudify_agent_module' in config:
        modules['agent'] = config['cloudify_agent_module']
    elif 'cloudify_agent_version' in config:
        modules['agent'] = DEFAULT_CLOUDIFY_AGENT_URL.format(
            config['cloudify_agent_version'])
    else:
        lgr.error('Either `cloudify_agent_module` or `cloudify_agent_version` '
                  'must be specified in the yaml configuration file.')
        sys.exit(codes.errors['missing_cloudify_agent_config'])
    return modules


def _validate(modules, venv):
    """validates that all requested modules are actually installed
    within the virtualenv
    :param dict modules: dict containing core and additional
    modules and the cloudify-agent module.
    :param string venv: path of virtualenv to install in.
    """

    failed = []

    lgr.info('Validating installation...')
    modules = modules['plugins'] + modules['modules']
    for module_name in modules:
        lgr.info('Validating that {0} is installed.'.format(module_name))
        if not utils.check_installed(module_name, venv):
            lgr.error('It appears that {0} does not exist in {1}'.format(
                module_name, venv))
            failed.append(module_name)

    if failed:
        lgr.error('Validation failed. some of the requested modules were not '
                  'installed.')
        sys.exit(codes.errors['installation_validation_failed'])


class ModuleInstaller():
    def __init__(self, modules, venv, final_set):
        self.venv = venv
        self.modules = modules
        self.final_set = final_set

    def install_requirements_file(self):
        if 'requirements_file' in self.modules:
            utils.install_requirements_file(
                self.modules['requirements_file'], self.venv)

    def install_modules(self, modules):
        for module in modules:
            lgr.info('Installing module {0}'.format(module))
            utils.install_module(module, self.venv)

    def install_core_modules(self):
        lgr.info('Installing core modules...')
        core = self.modules['core_modules']
        # we must run through the CORE_MODULES_LIST so that dependencies are
        # installed in order
        for module in CORE_MODULES_LIST:
            module_name = get_module_name(module)
            if module in core:
                lgr.info('Installing module {0} from {1}.'.format(
                    module_name, core[module]))
                utils.install_module(core[module], self.venv)
                self.final_set['modules'].append(module_name)
            elif module not in core and module in MANDATORY_MODULES:
                lgr.info('Module {0} will be installed as a part of '
                         'cloudify-agent (This is a mandatory module).'.format(
                             module_name))
            elif module not in core:
                lgr.info('Module {0} will be installed as a part of '
                         'cloudify-agent (if applicable).'.format(module_name))

    def install_core_plugins(self):
        lgr.info('Installing core plugins...')
        core = self.modules['core_plugins']

        for module in CORE_PLUGINS_LIST:
            module_name = get_module_name(module)
            if module in core and core[module] == 'exclude':
                lgr.info('Module {0} is excluded. '
                         'it will not be a part of the agent.'.format(
                             module_name))
            elif core.get(module):
                lgr.info('Installing module {0} from {1}.'.format(
                    module_name, core[module]))
                utils.install_module(core[module], self.venv)
                self.final_set['plugins'].append(module_name)
            elif module not in core:
                lgr.info('Module {0} will be installed as a part of '
                         'cloudify-agent (if applicable).'.format(module_name))

    def install_additional_plugins(self):
        lgr.info('Installing additional plugins...')
        additional = self.modules['additional_plugins']

        for module, source in additional.items():
            module_name = get_module_name(module)
            lgr.info('Installing module {0} from {1}.'.format(
                module_name, source))
            utils.install_module(source, self.venv)
            self.final_set['plugins'].append(module_name)

    def install_agent(self):
        lgr.info('Installing cloudify-agent module from {0}'.format(
            self.modules['agent']))
        utils.install_module(self.modules['agent'], self.venv)
        self.final_set['modules'].append('cloudify-agent')


def _install(modules, venv, final_set):
    """installs all requested modules
    :param dict modules: dict containing core and additional
    modules and the cloudify-agent module.
    :param string venv: path of virtualenv to install in.
    :param dict final_set: dict to populate with modules.
    """
    installer = ModuleInstaller(modules, venv, final_set)
    lgr.info('Installing module from requirements file...')
    installer.install_requirements_file()
    lgr.info('Installing external modules...')
    installer.install_modules(EXTERNAL_MODULES)
    installer.install_core_modules()
    installer.install_core_plugins()
    lgr.info('Installing additional modules...')
    installer.install_modules(modules['additional_modules'])
    installer.install_additional_plugins()
    installer.install_agent()
    return installer.final_set


def _uninstall_excluded(modules, venv):
    """Uninstalls excluded modules.
    Since there is no way to exclude requirements from a module;
    and modules are installed from cloudify-agent's requirements;
    if any modules are chosen to be excluded, they will be uninstalled.
    :param dict modules: dict containing core and additional
    modules and the cloudify-agent module.
    :param string venv: path of virtualenv to install in.
    """
    lgr.info('Uninstalling excluded plugins (if any)...')
    for module in CORE_PLUGINS_LIST:
        module_name = get_module_name(module)
        if modules['core_plugins'].get(module) == 'exclude' and \
                utils.check_installed(module_name, venv):
            lgr.info('Uninstalling {0}'.format(module_name))
            utils.uninstall_module(module_name, venv)


def get_module_name(module):
    """returns a module's name
    """
    return module.replace('_', '-')


def get_os_props():
    """returns a tuple of the distro and release
    """
    data = platform.dist()
    distro = data[0]
    release = data[2]
    return distro, release


def _generate_includes_file(modules, venv):
    """generates the included_plugins file for `cloudify-agent` to use
    :param dict modules: dict containing a list of modules and a list
     of plugins. The plugins list will be used to populate the file.
    :param string venv: path of virtualenv to install in.
    """
    lgr.debug('Generating includes file')

    process = utils.run('{0}/bin/python -c "import cloudify_agent;'
                        ' print cloudify_agent.__file__"'.format(venv))
    cloudify_agent_module_path = os.path.dirname(process.stdout)
    output_file = os.path.join(
        cloudify_agent_module_path, INCLUDES_FILE)

    try:
        previous_included = imp.load_source('included_plugins', os.path.join(
            cloudify_agent_module_path, INCLUDES_FILE))
        plugins_list = previous_included.included_plugins
        for plugin in plugins_list:
            if plugin not in modules['plugins']:
                modules['plugins'].append(plugin)
    except IOError:
        lgr.debug('Included Plugins file could not be found in agent '
                  'module. A new file will be generated.')

    lgr.debug('Writing includes file to: {0}'.format(output_file))
    i = Jingen(
        template_file=TEMPLATE_FILE,
        vars_source=modules,
        output_file=output_file,
        template_dir=os.path.join(os.path.dirname(__file__), TEMPLATE_DIR),
        make_file=True
    )
    i.generate()
    return output_file


def create(config=None, config_file=None, force=False, dryrun=False,
           no_validate=False, verbose=True):
    """Creates an agent package (tar.gz)

    This will try to identify the distribution of the host you're running on.
    If it can't identify it for some reason, you'll have to supply a
    `distribution` (e.g. Ubuntu) config object in the config.yaml.
    The same goes for the `release` (e.g. Trusty).

    A virtualenv will be created under cloudify/env.

    The order of the modules' installation is as follows:
    cloudify-rest-service
    cloudify-plugins-common
    cloudify-script-plugin
    cloudify-diamond-plugin
    cloudify-agent
    any additional modules specified under `additional_modules` in the yaml.
    any additional plugins specified under `additional_plugins` in the yaml.
    Once all modules are installed, excluded modules will be uninstalled;
    installation validation will occur; an included_plugins file will be
    generated and a tar.gz file will be created.
    The `output_tar` config object can be specified to determine the path to
    the output file. If omitted, a default path will be given with the
    format `DISTRIBUTION-RELEASE-agent.tar.gz`.
    """
    set_global_verbosity_level(verbose)

    # this will be updated with installed plugins and modules and used
    # to validate the installation and create the includes file
    final_set = {'modules': [], 'plugins': []}
    if not config:
        config = _import_config(config_file) if config_file else \
            _import_config()
        config = {} if not config else config
    try:
        (distro, release) = get_os_props()
        distro = config.get('distribution', distro)
        release = config.get('release', release)
    except Exception as ex:
        lgr.error(
            'Distribution not found in configuration '
            'and could not be retrieved automatically. '
            'please specify the distribution in the yaml. '
            '({0})'.format(ex.message))
        sys.exit(codes.errors['could_not_identify_distribution'])
    python = config.get('python_path', '/usr/bin/python')
    venv = DEFAULT_VENV_PATH
    venv_already_exists = utils.is_virtualenv(venv)
    destination_tar = config.get(
        'output_tar', DEFAULT_OUTPUT_TAR_PATH.format(distro, release))

    lgr.debug('Distibution is: {0}'.format(distro))
    lgr.debug('Distribution release is: {0}'.format(release))
    lgr.debug('Python path is: {0}'.format(python))
    lgr.debug('Destination tarfile is: {0}'.format(destination_tar))

    if not dryrun:
        _make_venv(venv, python, force)

    _handle_output_file(destination_tar, force)

    modules = _set_defaults()
    modules = _merge_modules(modules, config)

    if dryrun:
        set_global_verbosity_level(True)
    lgr.debug('Modules and plugins to install: {0}'.format(json.dumps(
        modules, sort_keys=True, indent=4, separators=(',', ': '))))
    if dryrun:
        lgr.info('Dryrun complete')
        sys.exit(codes.notifications['dryrun_complete'])

    final_set = _install(modules, venv, final_set)
    _uninstall_excluded(modules, venv)
    if not no_validate:
        _validate(final_set, venv)
    _generate_includes_file(final_set, venv)
    utils.tar(venv, destination_tar)

    lgr.info('The following modules and plugins were installed '
             'in the agent:\n{0}'.format(utils.get_installed(venv)))

    # if keep_venv is explicitly specified to be false, the virtualenv
    # will not be deleted.
    # if keep_venv is not in the config but the virtualenv already
    # existed, it will not be deleted.
    if ('keep_venv' in config and not config['keep_venv']) \
            or ('keep_venv' not in config and not venv_already_exists):
        lgr.info('Removing origin virtualenv...')
        shutil.rmtree(venv)

    # duh!
    lgr.info('Process complete!')
