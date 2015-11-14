from setuptools import setup
import os
import codecs

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


setup(
    name='cloudify-agent-packager',
    version='3.6.0',
    url='https://github.com/cloudify-cosmo/cloudify-agent-packager',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    license='LICENSE',
    platforms='All',
    description='Creates Cloudify Agent Packages',
    long_description=read('README.rst'),
    packages=['agent_packager'],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'cfy-ap = agent_packager.packager:main',
        ]
    },
    install_requires=[
        "pyyaml==3.10",
        "virtualenv==12.0.7",
        "jingen==0.1.0",
        "click==4.0"
    ],
)
