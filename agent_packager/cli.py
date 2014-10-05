# flake8: NOQA

"""Script to run Cloudify's Agent Packager via command line

Usage:
    cfy-ap [--config=<path> --force -v]
    cfy-ap --version

Options:
    -h --help                   Show this screen
    -c --config=<path>          Path to config yaml (defaults to config.yaml)
    -f --force                  Forces deletion and creation of venv
    -v --verbose                verbose level logging
    --version                   Display current version
"""

from __future__ import absolute_import
from docopt import docopt
from agent_packager.logger import init
from agent_packager.packager import _set_global_verbosity_level
from agent_packager.packager import create

lgr = init()


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
    create(
        o.get('--config'),
        o.get('--force'),
        o.get('--verbose')
        )


def agent_packager(test_options=None):
    """Main entry point for script."""
    version = ver_check()
    options = test_options or docopt(__doc__, version=version)
    _set_global_verbosity_level(options.get('--verbose'))
    lgr.debug(options)
    agent_packager_run(options)


def main():
    agent_packager()


if __name__ == '__main__':
    main()
