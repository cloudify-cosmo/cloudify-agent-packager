class AgentPackagerError(Exception):
    _prefix = ''

    def __init__(self, message=''):
        super(AgentPackagerError, self).__init__(
            '{0}{1}'.format(self._prefix, message)
        )


class VirtualenvCreationError(AgentPackagerError):
    _prefix = 'Could not create venv: '


class PipInstallError(AgentPackagerError):
    _prefix = 'Could not install: '


class PipUninstallError(AgentPackagerError):
    _prefix = 'Could not uninstall: '


class DownloadError(AgentPackagerError):
    _prefix = 'Could not download '


class TarCreateError(AgentPackagerError):
    _prefix = 'Failed to create tar file: '


class ConfigFileError(AgentPackagerError):
    _prefix = 'Config file error: '
