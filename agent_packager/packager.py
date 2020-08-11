
import logging
import json
import platform
import shutil
import os
from . import exceptions, utils

try:
    from configparser import (
        RawConfigParser,
        Error as ConfigParserError,
        NoOptionError,
        NoSectionError)
except ImportError:
    # py2
    from ConfigParser import (
        RawConfigParser,
        Error as ConfigParserError,
        NoOptionError,
        NoSectionError)

try:
    import distro
except ImportError:
    HAS_DISTRO = False
else:
    HAS_DISTRO = True


DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_OUTPUT_TAR_PATH = '{0}-{1}-agent.tar.gz'
DEFAULT_VENV_PATH = 'cloudify/env'

DEFAULT_CLOUDIFY_AGENT_URL = 'https://github.com/cloudify-cosmo/cloudify-agent/archive/{0}.tar.gz'  # NOQA

lgr = logging.getLogger()
verbose_output = False


def set_global_verbosity_level(is_verbose_output=False):
    """Sets the global verbosity level for console and the lgr logger.

    :param bool is_verbose_output: should be output be verbose
    """
    global verbose_output
    verbose_output = is_verbose_output
    if verbose_output:
        lgr.setLevel(logging.DEBUG)
    else:
        lgr.setLevel(logging.INFO)


def get_option(config_get, *args, **kwargs):
    """Get an option from a configparser, or None if it doesn't exist.

    :param config_get: a method on a configparser, eg .get or .getboolean etc,
        or the configparser itself, in which case .get is used
    """
    if not callable(config_get):
        config_get = config_get.get
    try:
        return config_get(*args, **kwargs)
    except (NoOptionError, NoSectionError):
        return None


def _import_config(config_file=None):
    """Returns a configuration object

    :param string config_file: path to config file
    """
    if not config_file:
        config_file = DEFAULT_CONFIG_FILE
    lgr.debug('Importing config: {0}...'.format(config_file))
    config = RawConfigParser(allow_no_value=True)
    if not os.path.isfile(config_file):
        raise exceptions.ConfigFileError(
            'No such file: {0}'.format(config_file))
    try:
        config.read(config_file)
    except ConfigParserError as e:
        raise exceptions.ConfigFileError(e)
    return config


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
            raise exceptions.VirtualenvCreationError(
                'Virtualenv already exists at {0}. '
                'You can use the -f flag to install within the '
                'existing virtualenv.'.format(venv))
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
        raise exceptions.TarCreateError(
            '{0} already exists'.format(destination_tar))


def _set_defaults():
    """sets the default modules dictionary
    """
    modules = {}
    modules['additional_modules'] = []
    modules['additional_plugins'] = {}
    modules['agent'] = ''
    return modules


def _merge_modules(modules, config):
    """merges the default modules with the modules from the config yaml
    :param dict modules: dict containing core and additional
    modules and the cloudify-agent module.
    :param dict config: dict containing the config.
    """
    lgr.debug('Merging default modules with config...')

    modules['requirements_file'] = get_option(
        config, 'install', 'requirements_file')

    try:
        for name, _empty in config.items('additional_modules'):
            modules['additional_modules'].append(name)
    except NoSectionError:
        pass
    try:
        for name, target in config.items('additional_plugins'):
            modules['additional_plugins'][name] = target
    except NoSectionError:
        pass

    cloudify_agent_module = get_option(
        config, 'install', 'cloudify_agent_module')
    cloudify_agent_version = get_option(
        config, 'install', 'cloudify_agent_version')

    if cloudify_agent_module:
        modules['agent'] = cloudify_agent_module
    elif cloudify_agent_version:
        modules['agent'] = DEFAULT_CLOUDIFY_AGENT_URL.format(
            cloudify_agent_version)
    else:
        raise exceptions.ConfigFileError(
            'Either `cloudify_agent_module` or `cloudify_agent_version` '
            'must be specified in the configuration file.'
        )
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
        raise exceptions.PipInstallError(
            'some of the requested modules were not installed: {0}'
            .format(failed))


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
    lgr.info('Installing modules required by setup...')
    installer.install_modules(['setuptools==36.8.0'])
    lgr.info('Installing module from requirements file...')
    installer.install_requirements_file()
    lgr.info('Installing external modules...')
    lgr.info('Installing additional modules...')
    installer.install_modules(modules['additional_modules'])
    installer.install_additional_plugins()
    installer.install_agent()
    return installer.final_set


def get_module_name(module):
    """returns a module's name
    """
    return module.replace('_', '-')


def get_os_props():
    """returns a tuple of the distro and release
    """
    if HAS_DISTRO:
        return distro.name(), distro.codename()
    data = platform.dist()
    return data[0], data[2]


def _name_archive(distro, release, version, milestone, build):
    destination_tar = ''
    destination_tar += '{0}-'.format(distro)
    destination_tar += '{0}-'.format(release)
    destination_tar += 'agent'
    if version:
        destination_tar += '_{0}'.format(version)
    if milestone:
        destination_tar += '-{0}'.format(milestone)
    if build:
        destination_tar += '-b{0}'.format(build)
    destination_tar += '.tar.gz'
    return destination_tar


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
    installation validation will occur; a tar.gz file will be created.
    The `output_tar` config object can be specified to determine the path to
    the output file. If omitted, a default path will be given with the
    format `DISTRIBUTION-RELEASE-agent.tar.gz`.
    """
    set_global_verbosity_level(verbose)

    # this will be updated with installed plugins and modules and used
    # to validate the installation
    final_set = {'modules': [], 'plugins': []}
    if not config:
        config = _import_config(config_file)

    name_params = {
        'distro': get_option(config, 'system', 'distribution'),
        'release': get_option(config, 'system', 'release'),
        'version': (get_option(config, 'output', 'version') or
                    os.environ.get('VERSION', None)),
        'milestone': (get_option(config, 'output', 'milestone') or
                      os.environ.get('PRERELEASE', None)),
        'build': (get_option(config, 'output', 'build') or
                  os.environ.get('BUILD', None)),
    }
    if not name_params['distro'] or not name_params['release']:
        try:
            distro, release = get_os_props()
        except Exception as ex:
            raise exceptions.AgentPackagerError(
                'Distribution not found in configuration '
                'and could not be retrieved automatically. '
                'please specify the distribution in the config.file. '
                '({0})'.format(ex))
        name_params.update({
            'distro': distro,
            'release': release
        })

    python = get_option(config, 'system', 'python_path')
    venv = DEFAULT_VENV_PATH
    venv_already_exists = utils.is_virtualenv(venv)
    destination_tar = get_option(config, 'output', 'tar',) or \
        _name_archive(**name_params)

    lgr.debug('Distibution is: {0}'.format(name_params['distro']))
    lgr.debug('Distribution release is: {0}'.format(name_params['release']))
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
        return

    final_set = _install(modules, venv, final_set)
    utils.virtualenv_relocatable(venv, python)
    if not no_validate:
        _validate(final_set, venv)
    utils.tar(venv, destination_tar)

    lgr.info('The following modules and plugins were installed '
             'in the agent:\n{0}'.format(utils.get_installed(venv)))

    keep_virtualenv = get_option(
        config.getboolean, 'output', 'keep_virtualenv') or False
    if not keep_virtualenv and not venv_already_exists:
        lgr.info('Removing origin virtualenv...')
        shutil.rmtree(venv)

    lgr.info('Process complete!')
