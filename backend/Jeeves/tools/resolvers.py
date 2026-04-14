import re
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_CREDENTIAL_PATTERNS = re.compile(
    r'[A-Z][A-Z0-9_]*(?:_API_KEY|_SECRET|_TOKEN|_PASSWORD|_CREDENTIALS)',
)


@dataclass
class ResolvedPackage:
    package_name: str
    package_type: str
    version: str = ''
    description: str = ''
    homepage: str = ''
    run_command: str = ''
    run_args: list = field(default_factory=list)
    env_vars: list = field(default_factory=list)
    requires_credentials: bool = False


class ResolutionError(Exception):
    pass


def resolve_url(url_or_name: str) -> ResolvedPackage:
    text = url_or_name.strip()
    if not text:
        raise ResolutionError('URL or package name is required.')

    if not text.startswith('http://') and not text.startswith('https://'):
        return _resolve_direct_name(text)

    parsed = urlparse(text)
    host = parsed.hostname or ''

    if 'mcpservers.org' in host:
        return _resolve_mcpservers_org(text)
    if 'npmjs.com' in host:
        return _resolve_npm_url(text)
    if 'pypi.org' in host:
        return _resolve_pypi_url(text)
    if 'github.com' in host:
        return _resolve_github(text)

    raise ResolutionError(
        f'Unsupported URL: {text}. '
        'Supported: mcpservers.org, npmjs.com, pypi.org, github.com, '
        'or a plain package name.'
    )


def _detect_credentials(readme: str) -> tuple[bool, list[str]]:
    if not readme:
        return False, []
    found = list(set(_CREDENTIAL_PATTERNS.findall(readme)))
    return bool(found), sorted(found)


def _extract_npm_package_name(url: str) -> str:
    path = urlparse(url).path
    match = re.match(r'^/package/(.+?)/?$', path)
    if not match:
        raise ResolutionError(f'Cannot parse npm package name from: {url}')
    return match.group(1)


def _fetch_npm_metadata(package_name: str) -> ResolvedPackage:
    registry_url = f'https://registry.npmjs.org/{package_name}/latest'
    resp = httpx.get(registry_url)
    if resp.status_code != 200:
        raise ResolutionError(f'npm package not found: {package_name}')

    data = resp.json()
    readme = data.get('readme', '')
    requires_creds, env_vars = _detect_credentials(readme)

    return ResolvedPackage(
        package_name=data.get('name', package_name),
        package_type='npm',
        version=data.get('version', ''),
        description=data.get('description', ''),
        homepage=data.get('homepage', ''),
        run_command='npx',
        run_args=['-y', data.get('name', package_name)],
        env_vars=env_vars,
        requires_credentials=requires_creds,
    )


def _resolve_npm_url(url: str) -> ResolvedPackage:
    name = _extract_npm_package_name(url)
    return _fetch_npm_metadata(name)


def _extract_pypi_package_name(url: str) -> str:
    path = urlparse(url).path
    match = re.match(r'^/project/([^/]+)', path)
    if not match:
        raise ResolutionError(f'Cannot parse PyPI package name from: {url}')
    return match.group(1)


def _fetch_pypi_metadata(package_name: str) -> ResolvedPackage:
    api_url = f'https://pypi.org/pypi/{package_name}/json'
    resp = httpx.get(api_url)
    if resp.status_code != 200:
        raise ResolutionError(f'PyPI package not found: {package_name}')

    info = resp.json().get('info', {})
    readme = info.get('description', '')
    requires_creds, env_vars = _detect_credentials(readme)

    module_name = info.get('name', package_name).replace('-', '_')

    return ResolvedPackage(
        package_name=info.get('name', package_name),
        package_type='pypi',
        version=info.get('version', ''),
        description=info.get('summary', ''),
        homepage=info.get('home_page', ''),
        run_command='python',
        run_args=['-m', module_name],
        env_vars=env_vars,
        requires_credentials=requires_creds,
    )


def _resolve_pypi_url(url: str) -> ResolvedPackage:
    name = _extract_pypi_package_name(url)
    return _fetch_pypi_metadata(name)


def _resolve_mcpservers_org(url: str) -> ResolvedPackage:
    resp = httpx.get(url)
    if resp.status_code != 200:
        raise ResolutionError(f'Cannot fetch catalog page: {url}')

    html = resp.text

    npm_match = re.search(r'href=["\']?(https://(?:www\.)?npmjs\.com/package/[^"\'>\s]+)', html)
    if npm_match:
        return _resolve_npm_url(npm_match.group(1))

    pypi_match = re.search(r'href=["\']?(https://pypi\.org/project/[^"\'>\s]+)', html)
    if pypi_match:
        return _resolve_pypi_url(pypi_match.group(1))

    raise ResolutionError(
        'Could not find npm or PyPI package link on the catalog page. '
        'Try pasting the npmjs.com or pypi.org URL directly.'
    )


def _resolve_github(url: str) -> ResolvedPackage:
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ResolutionError(f'Invalid GitHub URL: {url}')

    owner, repo = path_parts[0], path_parts[1]

    raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/main/package.json'
    resp = httpx.get(raw_url)
    if resp.status_code == 200:
        data = resp.json()
        pkg_name = data.get('name', repo)
        return _fetch_npm_metadata(pkg_name)

    raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/main/pyproject.toml'
    resp = httpx.get(raw_url)
    if resp.status_code == 200:
        return _fetch_pypi_metadata(repo)

    raise ResolutionError(
        f'Cannot detect package type for GitHub repo {owner}/{repo}. '
        'No package.json or pyproject.toml found on main branch.'
    )


def _resolve_direct_name(name: str) -> ResolvedPackage:
    try:
        return _fetch_npm_metadata(name)
    except ResolutionError:
        pass

    try:
        return _fetch_pypi_metadata(name)
    except ResolutionError:
        pass

    raise ResolutionError(
        f'Package "{name}" not found on npm or PyPI.'
    )
