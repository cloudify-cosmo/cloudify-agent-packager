from setuptools import setup
# from setuptools import find_packages
from setuptools.command.test import test as TestCommand
import sys
import re
import os
import codecs

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        print('VERSION: ', version_match.group(1))
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


class Tox(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import tox
        errcode = tox.cmdline(self.test_args)
        sys.exit(errcode)

setup(
    name='cloudify-agent-packager',
    version='3.2a4',
    url='https://github.com/cloudify-cosmo/cloudify-agent-packager',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    license='LICENSE',
    platforms='All',
    description='Creates Cloudify Agent Packages',
    long_description=read('README.rst'),
    packages=['agent_packager'],
    entry_points={
        'console_scripts': [
            'cfy-ap = agent_packager.cli:main',
        ]
    },
    install_requires=[
        "docopt==.0.6.1",
        "pyyaml==3.10",
        "virtualenv==1.11.4",
        "requests==2.4.1"
    ],
    tests_require=['nose', 'tox'],
    cmdclass={'test': Tox},
)
