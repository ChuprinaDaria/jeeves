# Contributing to Jeeves

Thank you for your interest in contributing! Jeeves is free and open-source, and we welcome pull requests, bug reports, and feature ideas.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<you>/jeeves.git`
3. Set up locally: see [SETUP.md](SETUP.md) or run `make setup && make up`
4. Create a feature branch: `git checkout -b feat/my-feature`
5. Make your changes
6. Run tests: `make test && make lint`
7. Push and open a Pull Request

## Code Style

### Backend (Python)
- **Black** — 120 character line length
- **isort** — black profile
- **flake8** — 120 chars, complexity 10
- Config in `pyproject.toml` and `.flake8`

### Frontend (JavaScript)
- **JSX** — no TypeScript
- **ESLint** with react-hooks and react-refresh plugins
- Run: `cd frontend && npm run lint`

## Tests

- Backend: `pytest` with `pytest-django`. Run from `backend/Jeeves/`
- Frontend: ESLint + production build check
- All PRs must pass CI before merge

## Branding

Jeeves is licensed under Elastic License 2.0. The attribution footer ("Jeeves — by Daria Chuprina & open-source community") must remain in the UI. You may customize colors, logos, and other visual elements, but please keep the footer and project name intact.

## Communication

- Language: **English** for all code, comments, issues, and PRs
- Be direct and constructive
- If something is unclear, ask — we'd rather answer a question than review a confused PR

## Reporting Bugs

[Open an issue](https://github.com/ChuprinaDaria/jeeves/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Docker version, browser)

## Security

Found a vulnerability? **Do not open a public issue.** See [SECURITY.md](SECURITY.md).
