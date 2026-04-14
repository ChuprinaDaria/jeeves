from unittest.mock import patch, MagicMock
import pytest

from Jeeves.tools.resolvers import resolve_url, ResolvedPackage, ResolutionError


class TestNpmResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_npm_url(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar MCP server',
            'homepage': 'https://github.com/ChuprinaDaria/mcp-ukrainian-calendar',
            'readme': 'Set API_KEY env var to configure',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/mcp-ukrainian-calendar')

        assert isinstance(result, ResolvedPackage)
        assert result.package_name == 'mcp-ukrainian-calendar'
        assert result.package_type == 'npm'
        assert result.version == '1.0.5'
        assert result.run_command == 'npx'
        assert result.run_args == ['-y', 'mcp-ukrainian-calendar']

    @patch('Jeeves.tools.resolvers.httpx')
    def test_npm_scoped_package(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': '@anthropic/mcp-server',
            'version': '2.0.0',
            'description': 'Anthropic MCP server',
            'homepage': '',
            'readme': '',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/@anthropic/mcp-server')
        assert result.package_name == '@anthropic/mcp-server'
        assert result.run_args == ['-y', '@anthropic/mcp-server']


class TestPypiResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_pypi_url(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'info': {
                'name': 'mcp-server-fetch',
                'version': '0.6.2',
                'summary': 'MCP server for web fetching',
                'home_page': '',
                'description': '',
            },
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://pypi.org/project/mcp-server-fetch/')
        assert result.package_name == 'mcp-server-fetch'
        assert result.package_type == 'pypi'
        assert result.run_command == 'python'
        assert result.run_args == ['-m', 'mcp_server_fetch']


class TestMcpServersOrgResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_mcpservers_org_with_npm_link(self, mock_httpx):
        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.text = '<html><a href="https://www.npmjs.com/package/mcp-ukrainian-calendar">npm</a></html>'

        npm_resp = MagicMock()
        npm_resp.status_code = 200
        npm_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar',
            'homepage': '',
            'readme': '',
        }

        mock_httpx.get.side_effect = [html_resp, npm_resp]

        result = resolve_url('https://mcpservers.org/servers/chuprinadaria/mcp-ukrainian-calendar')
        assert result.package_name == 'mcp-ukrainian-calendar'
        assert result.package_type == 'npm'


class TestDirectNameResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_plain_package_name_npm(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar',
            'homepage': '',
            'readme': '',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('mcp-ukrainian-calendar')
        assert result.package_type == 'npm'

    @patch('Jeeves.tools.resolvers.httpx')
    def test_plain_package_name_pypi_fallback(self, mock_httpx):
        npm_resp = MagicMock()
        npm_resp.status_code = 404

        pypi_resp = MagicMock()
        pypi_resp.status_code = 200
        pypi_resp.json.return_value = {
            'info': {
                'name': 'some-mcp-server',
                'version': '0.1.0',
                'summary': 'A server',
                'home_page': '',
                'description': '',
            },
        }

        mock_httpx.get.side_effect = [npm_resp, pypi_resp]

        result = resolve_url('some-mcp-server')
        assert result.package_type == 'pypi'


class TestGitHubResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_github_url_with_package_json(self, mock_httpx):
        pkg_resp = MagicMock()
        pkg_resp.status_code = 200
        pkg_resp.json.return_value = {
            'name': 'mcp-calendar',
            'version': '1.0.0',
            'description': 'Calendar MCP',
        }

        npm_resp = MagicMock()
        npm_resp.status_code = 200
        npm_resp.json.return_value = {
            'name': 'mcp-calendar',
            'version': '1.0.0',
            'description': 'Calendar MCP',
            'homepage': '',
            'readme': '',
        }

        mock_httpx.get.side_effect = [pkg_resp, npm_resp]

        result = resolve_url('https://github.com/user/mcp-calendar')
        assert result.package_type == 'npm'
        assert result.package_name == 'mcp-calendar'


class TestResolutionError:
    def test_invalid_url_raises(self):
        with pytest.raises(ResolutionError):
            resolve_url('')

    @patch('Jeeves.tools.resolvers.httpx')
    def test_unknown_url_raises(self, mock_httpx):
        with pytest.raises(ResolutionError):
            resolve_url('https://random-site.com/something')


class TestCredentialDetection:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_detects_env_vars_in_readme(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-firecrawl',
            'version': '1.0.0',
            'description': 'Firecrawl MCP',
            'homepage': '',
            'readme': '# Setup\nSet `FIRECRAWL_API_KEY` and `FIRECRAWL_SECRET` env vars.',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/mcp-firecrawl')
        assert result.requires_credentials is True
        assert 'FIRECRAWL_API_KEY' in result.env_vars
        assert 'FIRECRAWL_SECRET' in result.env_vars
