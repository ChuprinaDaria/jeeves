# Jeeves Open-Source Transition — Design Spec

**Date:** 2026-05-27
**Author:** Daria Chuprina / Claude
**Status:** Approved

## Goal

Prepare Jeeves for public open-source release. Remove commercial licensing, add community governance files, clean up secrets, rename "Concierge" references, and make it easy for external contributors to set up and contribute.

## Principles

- Forever free, no paywalls, no license keys
- License: Elastic License 2.0 (free use, no reselling as hosted service, branding preserved)
- Branding: "Jeeves — by Daria Chuprina & open-source community" in footer, not removable
- Execution: series of isolated PRs, not one big bang

---

## Step 1: Security Cleanup

**Goal:** Remove hardcoded secrets, make all sensitive values env-only.

**Changes:**
- `backend/docker-compose.yml`: replace `WHATSAPP_QR_SECRET: "super_secret_key_9283jd0923jd"` with `${WHATSAPP_QR_SECRET:-change-me}`
- `backend/Jeeves/settings.py`: remove default value from `FIELD_ENCRYPTION_KEY`, make it required
- `backend/.env.example`: add `WHATSAPP_QR_SECRET` and `FIELD_ENCRYPTION_KEY` entries
- Root `.env` file: not in git, but user must rotate OpenAI API key on dashboard

**Not doing:**
- Fake test keys like `sk-proj-abc123` in test files — these are fine

---

## Step 2: License (ELv2)

**Goal:** Add Elastic License 2.0, replace incorrect MIT references.

**Changes:**
- Create `LICENSE` file at repo root with full ELv2 text
  - Licensor: "Daria Chuprina / Lazysoft"
  - Licensed Work: "Jeeves"
- `README.md`: replace "MIT — See LICENSE" with ELv2 summary
  - What's allowed: use, deploy, modify for yourself
  - What's not: sell as hosted service, remove branding/license
- Footer requirement documented in CONTRIBUTING.md (Step 7)

**Not doing:**
- Per-file license headers — not required for ELv2

---

## Step 3: Remove Gumroad Licensing

**Goal:** Strip the entire commercial licensing system.

**Changes:**
- Delete `backend/Jeeves/concierge_platform/gumroad_client.py`
- `backend/Jeeves/concierge_platform/models.py`: remove `PlatformLicense` model
- `backend/Jeeves/concierge_platform/views_setup.py`: remove license verification logic
- `backend/Jeeves/concierge_platform/views_owner.py`: remove license-related endpoints
- `backend/Jeeves/concierge_platform/serializers.py`: remove license serializer if present
- `backend/Jeeves/settings.py`: remove `GUMROAD_PRODUCT_ID` and related `ImproperlyConfigured` check
- `backend/docker-compose.yml`: remove `GUMROAD_PRODUCT_ID` from all 3 services (web, celery_worker, celery_beat)
- Delete tests: `test_gumroad_client.py`, `test_reverify_api.py`, license-related parts of other tests
- Create Django migration to drop `PlatformLicense` table
- Frontend: remove license check from `BootstrapGate`, remove license step from `SetupWizard`

**Not doing:**
- `PlatformDefaults` stays — it's platform config, not licensing
- `FeatureFlag`, `SystemMessage` stay — useful features
- `concierge_platform` app not renamed (see Step 6 notes)

---

## Step 4: Remove Stripe

**Goal:** Remove unused Stripe dependencies.

**Changes:**
- `frontend/package.json`: remove `@stripe/react-stripe-js` and `@stripe/stripe-js`
- `frontend/.env.example`: remove `VITE_STRIPE_PUBLIC_KEY`
- Run `npm install` to update lockfile

---

## Step 5: Remove dev-deploy Workflow

**Goal:** Remove private infrastructure deployment pipeline.

**Changes:**
- Delete `.github/workflows/dev-deploy.yml`

**Not doing:**
- `.github/workflows/main-tests.yml` stays — CI for tests, useful for contributors

---

## Step 6: Rename concierge → jeeves

**Goal:** User-facing names consistently say "Jeeves".

**Changes:**

Docker (`backend/docker-compose.yml`):
- `concierge_db` → `jeeves_db`
- `concierge_redis` → `jeeves_redis`
- `concierge_web` → `jeeves_web`
- `concierge_celery_worker` → `jeeves_celery_worker`
- `concierge_celery_beat` → `jeeves_celery_beat`
- `concierge_nginx` → `jeeves_nginx`
- `concierge_network` → `jeeves_network`

Env (`backend/.env.example`):
- `DB_NAME=concierge` → `DB_NAME=jeeves`
- `QDRANT_COLLECTION=concierge_embeddings` → `QDRANT_COLLECTION=jeeves_embeddings`

Docs:
- `SETUP.md`: "Concierge AI Platform" → "Jeeves"

**Not doing:**
- Django app `concierge_platform` NOT renamed — would break imports, migrations, URLs, INSTALLED_APPS. Separate task later.
- Internal variable names with "concierge" — not user-facing

---

## Step 7: Community Files

**Goal:** Standard open-source governance and contributor onboarding.

**New files:**
- `CONTRIBUTING.md` — fork → branch → PR workflow, how to run tests, code style (Black 120ch, isort, flake8), branding requirement (footer not removable), communication language: English
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1
- `SECURITY.md` — report vulnerabilities to chuprina.dariia@gmail.com
- `.github/ISSUE_TEMPLATE/bug_report.md` — steps to reproduce, expected/actual behavior, environment info
- `.github/ISSUE_TEMPLATE/feature_request.md` — problem description, proposed solution
- `.github/PULL_REQUEST_TEMPLATE.md` — what changed, how tested, checklist

---

## Step 8: Developer Experience (DX)

**Goal:** Make it trivial to set up and contribute.

**Changes:**

New `Makefile` at repo root:
- `make setup` — copy .env.example → .env for backend and frontend
- `make up` — docker compose up -d
- `make down` — docker compose down
- `make test` — pytest in backend container
- `make lint` — black --check + isort --check + flake8
- `make migrate` — django migrate in container
- `make superuser` — createsuperuser in container
- `make logs` — docker compose logs -f web

Complete `backend/.env.example`:
- Add `FIELD_ENCRYPTION_KEY`, `WHATSAPP_QR_SECRET`, `TWILIO_*` variables

Update `SETUP.md`:
- Replace "Concierge" → "Jeeves"
- Add `make setup` / `make up` as primary path
- Add "For contributors" section with link to CONTRIBUTING.md

Update `README.md`:
- License section: ELv2 instead of MIT
- Remove remaining Gumroad mentions
- Add "Forever free" messaging
- Add links to CONTRIBUTING, SECURITY, CODE_OF_CONDUCT
- Add branding footer text to frontend

Frontend footer:
- Add footer component: "Jeeves — by Daria Chuprina & open-source community. Forever free."
- Link to GitHub repo

---

## Execution Order

Each step = one commit on a feature branch, then squash-merge to main. Steps are sequential — each depends on the previous being clean.

```
Step 1 (security) → Step 2 (license) → Step 3 (gumroad) → Step 4 (stripe) →
Step 5 (dev-deploy) → Step 6 (rename) → Step 7 (community) → Step 8 (DX)
```

## Out of Scope

- Renaming Django app `concierge_platform` — too risky, separate initiative
- Adding new features
- Refactoring existing code
- Deployment documentation for specific providers
