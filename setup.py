from setuptools import setup
import os
import codecs

here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open
    return codecs.open(os.path.join(here, *parts), 'r').read()


setup(
    name='cloudify-agent-packager',
    version='5.0.7',
    url='https://github.com/cloudify-cosmo/cloudify-agent-packager',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    license='LICENSE',
    platforms='All',
    description='Creates Cloudify Agent Packages',
    long_description=read('README.md'),
    packages=['agent_packager'],
    entry_points={
        'console_scripts': [
            'cfy-ap = agent_packager.cli:main',
        ]
    },
    install_requires=[
        "virtualenv==15.1.0",
        "requests==2.7.0",
    ],
    include_package_data=True
)
