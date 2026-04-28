from unittest.mock import patch, MagicMock
import pytest

from Jeeves.tools.resolvers import ResolvedPackage
from Jeeves.tools.installer import install_package, uninstall_package, InstallError


class TestInstallPackage:
    @patch('Jeeves.tools.installer.subprocess')
    def test_install_npm(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        pkg = ResolvedPackage(
            package_name='mcp-calendar',
            package_type='npm',
            run_command='npx',
            run_args=['-y', 'mcp-calendar'],
        )

        install_package(pkg)

        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args[0][0]
        assert args[0] == 'npm'
        assert 'install' in args
        assert 'mcp-calendar' in args

    @patch('Jeeves.tools.installer.subprocess')
    def test_install_pypi(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        pkg = ResolvedPackage(
            package_name='mcp-server-fetch',
            package_type='pypi',
            run_command='python',
            run_args=['-m', 'mcp_server_fetch'],
        )

        install_package(pkg)

        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args[0][0]
        assert args[0] == 'pip'
        assert 'install' in args

    @patch('Jeeves.tools.installer.subprocess')
    def test_install_failure_raises(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=1, stdout='', stderr='Package not found',
        )

        pkg = ResolvedPackage(
            package_name='nonexistent',
            package_type='npm',
            run_command='npx',
            run_args=['-y', 'nonexistent'],
        )

        with pytest.raises(InstallError, match='Package not found'):
            install_package(pkg)


class TestUninstallPackage:
    @patch('Jeeves.tools.installer.subprocess')
    def test_uninstall_npm(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        uninstall_package('mcp-calendar', 'npm')
        args = mock_subprocess.run.call_args[0][0]
        assert 'uninstall' in args

    @patch('Jeeves.tools.installer.subprocess')
    def test_uninstall_pypi(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        uninstall_package('mcp-server-fetch', 'pypi')
        args = mock_subprocess.run.call_args[0][0]
        assert 'uninstall' in args
