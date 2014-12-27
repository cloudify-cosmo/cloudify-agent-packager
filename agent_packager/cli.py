# flake8: NOQA

"""Script to run Cloudify's Agent Packager via command line

Usage:
    cfy-ap [--config=<path> --force --dryrun -v]
    cfy-ap --version

Options:
    -h --help                   Show this screen
    -c --config=<path>          Path to config yaml (defaults to config.yaml)
    -f --force                  Forces deletion and creation of venv and tar file.
    -d --dryrun                 Prints out the modules to be installed without actually installing them.
    -n --no-validation          Does not validate that all modules were installed correctly.
    -v --verbose                verbose level logging
    --version                   Display current version
"""

from __future__ import absolute_import
from docopt import docopt
import agent_packager.logger as logger
import agent_packager.packager as packager

lgr = logger.init()


def ver_check():
    import pkg_resources
    version = None
    try:
        version = pkg_resources.get_distribution('agent_packager').version
    except Exception as e:
        print(e)
    finally:
        del pkg_resources
    return version


def agent_packager_run(o):
    packager.create(
        config_file=o.get('--config'),
        force=o.get('--force'),
        dry=o.get('--dryrun'),
        validate=o.get('--no-validation'),
        verbose=o.get('--verbose')
        )


def agent_packager(test_options=None):
    """Main entry point for script."""
    version = ver_check()
    options = test_options or docopt(__doc__, version=version)
    packager.set_global_verbosity_level(options.get('--verbose'))
    lgr.debug(options)
    agent_packager_run(options)


def main():
    agent_packager()


if __name__ == '__main__':
    main()
