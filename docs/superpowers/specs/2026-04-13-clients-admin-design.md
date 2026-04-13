# Clients Admin (Owner Panel) — Design Spec

**Date:** 2026-04-13
**Status:** Approved

## Goal

Full CRUD for Clients in the owner admin frontend. Replace the stub page with a working list + edit/create page.

## Scope

### List Page (`/owner/clients`)
Table columns: company_name, tag, client_type, is_active, channels (icons), created_at.

### Edit/Create Page (`/owner/clients/new`, `/owner/clients/:id`)

**Section 1 — Basic Info:**
- company_name, tag (auto-generated if empty), description, client_type (select), is_active (toggle)
- branch (select from existing), specialization (select from existing)
- greeting_message (textarea)

**Section 2 — AI Config:**
- llm_provider_model (select from LLMProvider)
- embedding_model (select from EmbeddingModel)

**Section 3 — Channels (toggles + status):**
- telegram_enabled
- whatsapp_meta_enabled
- whatsapp_bridge_enabled + status badge (read-only)
- email_smtp_enabled
- widget_enabled (web widget)

**Section 4 — SMTP Config (visible when email_smtp_enabled):**
- email_smtp_host, email_smtp_port, email_smtp_use_tls
- email_smtp_username, email_smtp_password (masked ****xxxx)
- email_from_address, email_from_name

**Section 5 — Email Reports:**
- email_report_enabled, email_report_recipients (comma-separated input)
- notification_language (select)

**Section 6 — Features:**
- leads_enabled, extension_enabled, pixel_dashboard_enabled

**Section 7 — Metadata (read-only):**
- api_key (masked), created_at, tag (copyable link to portal)

### NOT in scope:
- telephony_enabled (removed)
- Channel credentials (Meta tokens, Telegram bot token) — Django admin / client portal
- Dashboard customization JSON
- Manager telegram IDs
- AgentConfig detailed editing (separate future page)
- HITL config
