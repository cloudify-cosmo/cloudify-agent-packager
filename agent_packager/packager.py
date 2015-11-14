import logging
import yaml
import json
import shutil
import os
import sys
import imp

import click
from jingen.jingen import Jingen

from . import utils, codes, logger


DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_VENV_PATH = 'cloudify/env'

INCLUDES_FILE = 'included_plugins.py'
TEMPLATE_FILE = 'included_plugins.py.j2'
TEMPLATE_DIR = 'resources'

EXTERNAL_PACKAGES = [
    'celery==3.1.17'
]

CORE_PACKAGES_LIST = [
    'cloudify_rest_client',
    'cloudify_plugins_common',
]

CORE_PLUGINS_LIST = [
    'cloudify_script_plugin',
    'cloudify_diamond_plugin',
]

MANDATORY_PACKAGES = [
    'cloudify_rest_client',
    'cloudify_plugins_common',
]

DEFAULT_CLOUDIFY_AGENT_URL = 'https://github.com/cloudify-cosmo/cloudify-agent/archive/{0}.tar.gz'  # NOQA
DEFAULT_CLOUDIFY_AGENT_REQ_FILE_URL = 'https://raw.githubusercontent.com/cloudify-cosmo/cloudify-agent/{0}/dev-requirements.txt'  # NOQA

lgr = logger.init()


def import_config(config_file):
    """Returns a configuration object

    :param string config_file: path to config file
    """
    lgr.debug('Importing config: {0}...'.format(config_file))
    config_file = config_file or DEFAULT_CONFIG_FILE
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


class PackageInstaller():
    def __init__(self, packages, venv, final_set, pip_args):
        self.venv = venv
        self.packages = packages
        self.final_set = final_set
        self.pip_args = pip_args

    def install_requirements_file(self):
        if 'requirements_file' in self.packages:
            utils.install_requirements_file(
                self.packages['requirements_file'], self.venv, self.pip_args)

    def install_packages(self, packages):
        for package in packages:
            lgr.info('Installing package {0}'.format(package))
            utils.install_package(package, self.venv, self.pip_args)

    def install_core_packages(self):
        lgr.info('Installing core packages...')
        core = self.packages['core_packages']
        # we must run through the CORE_PACKAGES_LIST so that dependencies are
        # installed in order
        for package in CORE_PACKAGES_LIST:
            package_name = utils.get_package_name(package)
            if package in core:
                lgr.info('Installing package {0} from {1}.'.format(
                    package_name, core[package]))
                utils.install_package(core[package], self.venv, self.pip_args)
                self.final_set['packages'].append(package_name)
            elif package not in core and package in MANDATORY_PACKAGES:
                lgr.info('package {0} will be installed as a part of '
                         'cloudify-agent (It is a mandatory package).'.format(
                             package_name))
            elif package not in core:
                lgr.info('package {0} will be installed as a part of '
                         'cloudify-agent (if applicable).'.format(
                             package_name))

    def install_core_plugins(self):
        lgr.info('Installing core plugins...')
        core = self.packages['core_plugins']

        for package in CORE_PLUGINS_LIST:
            package_name = utils.get_package_name(package)
            if package in core and core[package] == 'exclude':
                lgr.info('package {0} is excluded. '
                         'it will not be a part of the agent.'.format(
                             package_name))
            elif core.get(package):
                lgr.info('Installing package {0} from {1}.'.format(
                    package_name, core[package]))
                utils.install_package(core[package], self.venv, self.pip_args)
                self.final_set['plugins'].append(package_name)
            elif package not in core:
                lgr.info('package {0} will be installed as a part of '
                         'cloudify-agent (if applicable).'.format(
                             package_name))

    def install_additional_plugins(self):
        lgr.info('Installing additional plugins...')
        additional = self.packages['additional_plugins']

        for package, source in additional.items():
            package_name = utils.get_package_name(package)
            lgr.info('Installing package {0} from {1}.'.format(
                package_name, source))
            utils.install_package(source, self.venv, self.pip_args)
            self.final_set['plugins'].append(package_name)

    def install_agent(self):
        lgr.info('Installing cloudify-agent package from {0}'.format(
            self.packages['agent']))
        utils.install_package(self.packages['agent'], self.venv, self.pip_args)
        self.final_set['packages'].append('cloudify-agent')


class AgentPackager():
    def __init__(self, config='config.yaml', python_path=sys.executable,
                 verbose=False):
        if verbose:
            lgr.setLevel(logging.DEBUG)
        else:
            lgr.setLevel(logging.INFO)

        if isinstance(config, dict):
            self.config = config
        elif os.path.isfile(config):
            self.config = import_config(config)
        else:
            self.config = {}

        self.python = python_path

    def create(self, force=False, dryrun=False, no_validate=False,
               agent_source=DEFAULT_CLOUDIFY_AGENT_URL.format('master'),
               reqs_file=DEFAULT_CLOUDIFY_AGENT_REQ_FILE_URL.format('master'),
               exclude=None, output_path='', keep_virtualenv=False,
               pip_args=''):
        """Creates an agent package (tar.gz)

        This will try to identify the distribution of the host you're running.
        If it can't identify it for some reason, you'll have to supply a
        `distribution` (e.g. Ubuntu) config object in the config.yaml.
        The same goes for the `release` (e.g. Trusty).

        A virtualenv will be created under cloudify/env.

        The order of the packages' installation is as follows:
        cloudify-rest-service
        cloudify-plugins-common
        cloudify-script-plugin
        cloudify-diamond-plugin
        cloudify-agent
        additional packages specified under `additional_packages` in the yaml.
        additional plugins specified under `additional_plugins` in the yaml.
        Once all packages are installed, excluded packages will be uninstalled;
        installation validation will occur; an included_plugins file will be
        generated and a tar.gz file will be created.
        The `output_tar` config obj can be specified to determine the path to
        the output file. If omitted, a default path will be given with the
        format `DISTRIBUTION-RELEASE-agent.tar.gz`.
        """

        self.agent_source = agent_source
        self.reqs_file = reqs_file
        self.pip_args = pip_args

        # this will be updated with installed plugins and packages and used
        # to validate the installation and create the includes file
        final_set = {'packages': [], 'plugins': []}

        venv = DEFAULT_VENV_PATH
        venv_already_exists = utils.is_virtualenv(venv)
        destination_tar = output_path or self.set_archive_name()

        lgr.debug('Distibution: {0}'.format(self.distro))
        lgr.debug('Distribution release: {0}'.format(self.release))
        lgr.debug('Version: {0}'.format(self.version))
        lgr.debug('Milestone: {0}'.format(self.milestone))
        lgr.debug('Build: {0}'.format(self.build))
        lgr.debug('Python path: {0}'.format(self.python))
        lgr.debug('Destination tarfile: {0}'.format(destination_tar))

        if not dryrun:
            self._make_venv(venv, self.python, force)

        self._handle_output_file(destination_tar, force)

        packages = self._set_defaults()
        packages = self._merge_packages(packages, self.config)

        if dryrun:
            lgr.setLevel(logging.DEBUG)
        lgr.debug('Packages and plugins to install: {0}'.format(json.dumps(
            packages, sort_keys=True, indent=4, separators=(',', ': '))))
        if dryrun:
            lgr.info('Dryrun complete')
            sys.exit(codes.notifications['dryrun_complete'])

        final_set = self._install(packages, venv, final_set)
        self._uninstall_excluded(packages, venv)
        if not no_validate:
            self.validate(final_set, venv)
        self.generate_includes_file(final_set, venv)
        utils.tar(venv, destination_tar)

        lgr.info('The following packages and plugins were installed '
                 'in the agent:\n{0}'.format(utils.get_installed(venv)))

        # If the virtualenv already existed, it will not be deleted.
        if not keep_virtualenv and not venv_already_exists:
            lgr.info('Removing origin virtualenv...')
            shutil.rmtree(os.path.dirname(venv))

        # duh!
        lgr.info('Process complete!')

    def set_archive_name(self, distro='', release='', version='',
                         milestone='', build=''):
        try:
            self.distro = distro or self.config.get('distribution') \
                or utils.get_os_props()[0].lower()
            self.release = release or self.config.get('release') \
                or utils.get_os_props()[1].lower()
        except Exception as ex:
            lgr.error(
                'Distribution or Release not found in configuration '
                'and could not be retrieved automatically. '
                'please specify them in the yaml. '
                '({0})'.format(str(ex)))
            sys.exit(codes.errors['could_not_identify_distribution'])

        self.version = version or os.environ.get('VERSION', None)
        self.milestone = milestone or os.environ.get('PRERELEASE', None)
        self.build = build or os.environ.get('BUILD', None)

        archive = ['cloudify-']
        archive.append('{0}-'.format(self.distro))
        archive.append('{0}-'.format(self.release))
        archive.append('agent')
        if self.version:
            archive.append('_{0}'.format(self.version))
        if self.milestone:
            archive.append('-{0}'.format(self.milestone))
        if self.build:
            archive.append('-b{0}'.format(self.build))
        archive.append('.tar.gz')
        return ''.join(archive)

    def generate_includes_file(self, packages, venv):
        """Generates the included_plugins file for `cloudify-agent` to use.

        :param dict packages: dict containing a list of packages and a list
         of plugins. The plugins list will be used to populate the file.
        :param string venv: path of virtualenv to install in.
        """
        lgr.info('Generating includes file')

        process = utils.run('{0} -c "import cloudify_agent;'
                            ' print cloudify_agent.__file__"'.format(
                                os.path.join(utils.get_env_bin_path(venv),
                                             'python')))
        cloudify_agent_package_path = os.path.dirname(process.aggr_stdout)
        included_plugins_py = os.path.join(
            cloudify_agent_package_path, INCLUDES_FILE)
        included_plugins_pyc = '{0}c'.format(included_plugins_py)

        try:
            previous_included = imp.load_source('included_plugins',
                                                included_plugins_py)
            plugins_list = previous_included.included_plugins
            for plugin in plugins_list:
                if plugin not in packages['plugins']:
                    packages['plugins'].append(plugin)
        except IOError:
            lgr.info('Included Plugins file could not be found in agent '
                     'package. A new file will be generated.')

        lgr.debug('Writing includes file to: {0}'.format(included_plugins_py))
        i = Jingen(
            template_file=TEMPLATE_FILE,
            vars_source=packages,
            output_file=included_plugins_py,
            template_dir=os.path.join(os.path.dirname(__file__), TEMPLATE_DIR),
            make_file=True
        )
        i.generate()
        if os.path.isfile(included_plugins_pyc):
            os.remove(included_plugins_pyc)
        return included_plugins_py

    def _install(self, packages, venv, final_set):
        """Installs all requested packages

        :param dict packages: dict containing core and additional
        packages and the cloudify-agent package.
        :param string venv: path of virtualenv to install in.
        :param dict final_set: dict to populate with packages.
        """
        installer = PackageInstaller(packages, venv, final_set, self.pip_args)
        lgr.info('Installing package from requirements file...')
        installer.install_requirements_file()
        lgr.info('Installing external packages...')
        installer.install_packages(EXTERNAL_PACKAGES)
        installer.install_core_packages()
        installer.install_core_plugins()
        lgr.info('Installing additional packages...')
        installer.install_packages(packages['additional_packages'])
        installer.install_additional_plugins()
        installer.install_agent()
        return installer.final_set

    def _uninstall_excluded(self, packages, venv):
        """Uninstalls excluded packages.

        Since there is no way to exclude requirements from a package;
        and packages are installed from cloudify-agent's requirements;
        if any packages are chosen to be excluded, they will be uninstalled.
        :param dict packages: dict containing core and additional
        packages and the cloudify-agent package.
        :param string venv: path of virtualenv to install in.
        """
        lgr.info('Uninstalling excluded plugins (if any)...')
        for package in CORE_PLUGINS_LIST:
            package_name = utils.get_package_name(package)
            if packages['core_plugins'].get(package) == 'exclude' and \
                    utils.check_installed(package_name, venv):
                lgr.info('Uninstalling {0}'.format(package_name))
                utils.uninstall_package(package_name, venv)

    def validate(self, packages, venv):
        """validates that all requested packages are actually installed
        within the virtualenv.

        :param dict packages: dict containing core and additional
        packages and the cloudify-agent package.
        :param string venv: path of virtualenv to install in.
        """

        failed = []

        lgr.info('Validating installation...')
        packages = packages['plugins'] + packages['packages']
        for package_name in packages:
            lgr.info('Validating that {0} is installed.'.format(package_name))
            if not utils.check_installed(package_name, venv):
                lgr.error('It appears that {0} does not exist in {1}'.format(
                    package_name, venv))
                failed.append(package_name)

        if failed:
            lgr.error('Validation failed. some of the requested packages were '
                      'not installed.')
            sys.exit(codes.errors['installation_validation_failed'])

    def _make_venv(self, venv, python, force):
        """Handles the virtualenv.

        Removes the virtualenv if required, else, notifies
        that it already exists. If it doesn't exist, it will be
        created.

        :param string venv: path of virtualenv to install in.
        :param string python: python binary path to use.
        :param bool force: whether to force creation or not if it
         already exists.
        """
        if utils.is_virtualenv(venv):
            if force:
                lgr.info('Installing within existing virtualenv: {0}'.format(
                    venv))
            else:
                lgr.error('Virtualenv already exists at {0}. '
                          'You can use the -f flag to install within the '
                          'existing virtualenv.'.format(venv))
                sys.exit(codes.errors['virtualenv_already_exists'])
        else:
            lgr.debug('Creating virtualenv: {0}'.format(venv))
            utils.make_virtualenv(venv, python)

    def _handle_output_file(self, destination_tar, force):
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

    def _set_defaults(self):
        """sets the default packages dictionary
        """
        return {
            'core_packages': {},
            'core_plugins': {},
            'additional_packages': [],
            'additional_plugins': {},
            'agent': ''
        }

    def _merge_packages(self, packages, config):
        """merges the default packages with the packages from the config yaml
        :param dict packages: dict containing core and additional
        packages and the cloudify-agent package.
        :param dict config: dict containing the config.
        """
        lgr.debug('Merging default packages with config...')

        if self.reqs_file:
            packages['requirements_file'] = self.reqs_file
        elif 'requirements_file' in config:
            packages['requirements_file'] = config['requirements_file']

        packages['core_packages'].update(config.get('core_packages', {}))
        packages['core_plugins'].update(config.get('core_plugins', {}))

        additional_packages = config.get('additional_packages', [])
        for additional_package in additional_packages:
            packages['additional_packages'].append(additional_package)
        packages['additional_plugins'].update(
            config.get('additional_plugins', {}))

        if self.agent_source:
            packages['agent'] = self.agent_source
        elif 'cloudify_agent_package_source' in config:
            packages['agent'] = config['cloudify_agent_package_source']
        return packages


@click.group()
def main():
    pass


@click.command()
@click.option('-c', '--config', required=False, default='config.yaml',
              help='Source URL, Path or package name.')
@click.option('-s', '--cloudify-agent-source', required=False,
              default=DEFAULT_CLOUDIFY_AGENT_URL.format('master'),
              help='pip installable source of cloudify-agent package.')
@click.option('-r', '--requirements-file', required=False,
              default=DEFAULT_CLOUDIFY_AGENT_REQ_FILE_URL.format('master'),
              help='Include packages from requirements file.')
@click.option('--python-path', required=False, default='python',
              help='Python executable to use when packaging.')
@click.option('-f', '--force', default=False, is_flag=True,
              help='Force overwriting existing output file.')
@click.option('--keep-virtualenv', default=False, is_flag=True,
              help='Keep the virtualenv after package creation.')
@click.option('-x', '--exclude', default=None, multiple=True,
              help='Specific packages to exclude from the archive. '
                   'This argument can be provided multiple times.')
@click.option('--dryrun', default=False, is_flag=True,
              help='Do not create package. Rather, show potential outcome.')
@click.option('-nv', '--no-validate', default=False, is_flag=True,
              help='Output directory for the tar file.')
@click.option('-o', '--output-path', default=None,
              help='Output path for the archive.')
@click.option('--pip-args', default=None,
              help='Additional args to pass to the pip install command.')
@click.option('-v', '--verbose', default=False, is_flag=True)
def create(config, cloudify_agent_source, requirements_file, python_path,
           force, keep_virtualenv, exclude, dryrun, no_validate, output_path,
           pip_args, verbose):
    """Creates an agent package (tar.gz)
    """
    logger.configure()
    packager = AgentPackager(config, python_path, verbose)
    packager.create(force, dryrun, no_validate, cloudify_agent_source,
                    requirements_file, exclude, output_path, keep_virtualenv,
                    pip_args)


main.add_command(create)
