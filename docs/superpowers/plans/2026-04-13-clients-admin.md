# Clients Admin — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement.

**Goal:** Owner can manage Clients from frontend admin — full CRUD with AI config, channels, SMTP, features.

**Architecture:** New `ClientOwnerViewSet` (DRF ModelViewSet) + `ClientOwnerSerializer`. Two React pages following existing LLMProviders/MCPServers pattern.

**Tech Stack:** Django REST Framework, React 18, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-04-13-clients-admin-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `backend/Jeeves/clients/serializers_owner.py` | ClientOwnerSerializer with masked SMTP password |
| Create | `backend/Jeeves/clients/views_owner.py` | ClientOwnerViewSet with CRUD |
| Modify | `backend/Jeeves/concierge_platform/urls.py` | Register owner clients routes |
| Modify | `frontend/src/api/owner.js` | Add clientsAPI |
| Create | `frontend/src/pages/owner/ClientsPage.jsx` | List page |
| Create | `frontend/src/pages/owner/ClientEditPage.jsx` | Edit/create page |
| Modify | `frontend/src/App.jsx` | Replace stub route with real pages |

---

### Task 1: Owner Serializer for Client

**Files:**
- Create: `backend/Jeeves/clients/serializers_owner.py`

The serializer exposes fields grouped by section. SMTP password uses masked pattern (like LLMProvider api_key). Branch and Specialization are select fields (ID write, nested read). LLM/Embedding same pattern.

Key fields:
- Read-only: id, api_key (masked), created_at, updated_at, whatsapp_bridge_status
- Write-only: email_smtp_password (keep existing if empty on update)
- Nested read: branch {id, name}, specialization {id, name}, llm_provider_model {id, name}, embedding_model {id, name}
- Write: branch_id, specialization_id, llm_provider_model_id, embedding_model_id

---

### Task 2: Owner ViewSet for Client

**Files:**
- Create: `backend/Jeeves/clients/views_owner.py`

Standard ModelViewSet with _OwnerOnlyMixin (JWTAuthentication + IsOwner). Queryset with select_related for branch, specialization, llm_provider_model, embedding_model. Extra action `choices` that returns available branches, specializations, LLM providers, embedding models for dropdowns.

---

### Task 3: URL Registration

**Files:**
- Modify: `backend/Jeeves/concierge_platform/urls.py`

Register `owner/clients` ViewSet in router.

---

### Task 4: Frontend API Client

**Files:**
- Modify: `frontend/src/api/owner.js`

Add `clientsAPI` with list, detail, create, update, delete, choices.

---

### Task 5: ClientsPage (List)

**Files:**
- Create: `frontend/src/pages/owner/ClientsPage.jsx`

Table with columns: Company, Tag, Type, Active, Channels (icon badges), Created. Same pattern as MCPServersPage.

---

### Task 6: ClientEditPage (Create/Edit)

**Files:**
- Create: `frontend/src/pages/owner/ClientEditPage.jsx`

Sections: Basic, AI Config, Channels, SMTP (conditional), Email Reports, Features, Metadata. Uses MaskedPasswordInput for SMTP password. Dropdowns populated from `choices` endpoint.

---

### Task 7: Routes (replace stub)

**Files:**
- Modify: `frontend/src/App.jsx`

Replace `<StubPage title="Clients" />` with real routes. Add imports.

---

### Task 8: Smoke Test

Verify API returns clients, frontend builds, pages render.
