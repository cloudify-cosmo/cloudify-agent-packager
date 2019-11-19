# flake8: NOQA

"""Script to run Cloudify's Agent Packager via command line

Usage:
    cfy-ap [--config=<path> --force --dryrun --no-validation -v]
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

import sys
import logging
from docopt import docopt

import agent_packager.packager as packager

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


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


def _run(test_options=None):
    version = ver_check()
    options = test_options or docopt(__doc__, version=version)
    is_verbose = options.get('--verbose')
    if is_verbose:
        logging.root.setLevel(logging.DEBUG)
    logger.debug("Command-line options: %s", str(options))

    packager.create(
        config_file=options.get('--config'),
        force=options.get('--force'),
        dryrun=options.get('--dryrun'),
        no_validate=options.get('--no-validation')
        )

def main():
    _run()

if __name__ == '__main__':
    main()
