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

import logging
import sys

from docopt import docopt
import pkg_resources

from . import packager


lgr = logging.getLogger()

def ver_check():
    version = None
    version = pkg_resources.get_distribution('cloudify-agent-packager').version
    return version


def _run(test_options=None):
    version = ver_check()
    options = test_options or docopt(__doc__, version=version)
    packager.set_global_verbosity_level(options.get('--verbose'))
    lgr.debug(options)

    packager.create(
        config_file=options.get('--config'),
        force=options.get('--force'),
        dryrun=options.get('--dryrun'),
        no_validate=options.get('--no-validation'),
        verbose=options.get('--verbose')
        )

def main():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s - %(message)s"
    )
    _run()

if __name__ == '__main__':
    main()
