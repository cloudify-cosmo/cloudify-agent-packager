import argparse
import logging
import sys

import pkg_resources

from . import packager


lgr = logging.getLogger()


def ver_check():
    version = None
    version = pkg_resources.get_distribution('cloudify-agent-packager').version
    return version


def _run(args):
    packager.set_global_verbosity_level(args.verbose)

    packager.create(
        config_file=args.config,
        force=args.force,
        dryrun=args.dryrun,
        no_validate=args.no_validation,
        verbose=args.verbose,
    )


def main():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Script to run Cloudify's Agent Packager via command line"
    )

    parser.add_argument(
        '--version',
        help="Display version information.",
        action='version',
        version=ver_check(),
    )

    parser.add_argument(
        '-c', '--config',
        help="Path to config yaml",
        default="config.yaml",
    )
    parser.add_argument(
        '-f', '--force',
        help="Forces deletion and creation of venv and tar file.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        '-d', '--dryrun',
        help="Prints out modules to be installed without installing them.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Verbose level logging.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        '-n', '--no-validation',
        help="Does not validate that all modules were installed correctly.",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    _run(args)


if __name__ == '__main__':
    main()
