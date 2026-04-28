---
name: code-reviewer
description: Reviews Django/React changes for Jeeves-specific patterns and common issues
model: sonnet
---

Review the recent changes in the Jeeves codebase. Check for:

**Backend (Python/Django):**
- Correct import paths — always `from Jeeves.app_name.module import ...`
- QuerySets use `select_related` / `prefetch_related` where needed
- New credential storage uses `EncryptedJSONField`
- New MCP tools have scope annotations in `MCP_TOOL_SCOPES` (settings.py)
- Celery tasks are idempotent
- Migrations don't mix with business logic changes

**Frontend (React):**
- New UI text has i18n keys added to all 8 locale files (en, de, fr, es, it, nl, da, uk)
- API calls go through the correct API client (authAPI, clientAPI, ownerAPI)
- Routes are added to the correct zone (owner, client portal, or legacy)

**General:**
- No hardcoded secrets or API keys
- No `.env` files modified
- Line length <= 120 chars (Python)
