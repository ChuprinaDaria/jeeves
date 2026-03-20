# AI Nexelin — Implementation Plan

> Master tracking document for Claude CLI. All tasks, architecture, pricing, progress.
> Rate: 205 EUR/day (4.500 EUR/month, 22 working days x 8h)

---

## Project Overview

AI Nexelin is a multi-tenant B2B platform for creating personalized AI assistants.
Each client gets their own RAG-powered agent, knowledge base, API key, and admin panel.

**Hierarchy:** Branch (industry) → Specialization → Client

**Stack:** Django 5, PostgreSQL + pgvector, Redis, Celery, Docker, OpenAI API, Ollama, Nginx

**Domains:** api.nexelin.com (backend) | app.nexelin.com (client portal, React) | mg.nexelin.com (management)

**Servers (target):**

| Role | Provider | Specs | Monthly Cost |
|------|----------|-------|-------------|
| App Server | Hetzner CPX31 | 4 vCPU, 8 GB RAM | ~20 EUR/mo |
| Data Server | Hetzner CPX51 | 8 vCPU, 32 GB RAM | ~50 EUR/mo |
| AI Server | RunPod RTX 4090 | 24 GB VRAM | ~0.44 EUR/hr |
| Single (start, 0-20 clients) | Hetzner CPX41 | 8 vCPU, 16 GB RAM | ~40 EUR/mo |

**Scaling path:** Single Server (0-20 clients) → App + Data (20-100) → + GPU (local AI) → Cluster (100+)

---

## Architecture

### Hierarchy Model

```
Branch (e.g. Medicine, Hospitality, Construction)
  └── Specialization (e.g. Dentistry, Gynecology, Concierge)
       └── Client (own knowledge base, settings, API key, admin panel)
```

Dynamic creation of branches, specializations, clients. Each client gets auto-generated API documentation.

### Agent System

Orchestrator pattern: main agent receives request, determines needed sub-agents, calls them in parallel, collects results.

```
Request → Orchestrator → [SubAgent1, SubAgent2, ...] → Aggregated Response
```

### Unified Message Format (MCP/A2A ready)

```json
{
  "task_id": "uuid",
  "agent": "SearchAgent",
  "input": { "query": "...", "top_k": 5 },
  "context": { "client_id": "...", "language": "de" },
  "output": null
}
```

### Sub-Agents

| Agent | Function | Input | Output |
|-------|----------|-------|--------|
| SearchAgent | RAG knowledge base search | query, top_k | chunks[], scores[] |
| RerankAgent | Reorder results by relevance | chunks[], query | ranked_chunks[] |
| DocumentAgent | Document indexing and processing | file, client_id | index_status |
| TranslationAgent | Text translation | text, target_lang | translated_text |
| SummaryAgent | Conversation summary | messages[] | summary_text |
| EscalationAgent | HITL handoff to manager | conversation_id, reason | matrix_room_id |
| ChannelAgent | Unified message routing | raw_message, channel | normalized_message |
| AuditAgent | Change tracking and logging | event, actor | log_entry |
| CalendarAgent | Booking and scheduling | date_range, title | event_id, link |
| EmailAgent | Email delivery | to, subject, body | status |

---

## Phase Tracker

### PHASE URGENT: HOTFIX & MIGRATION (NOW)

> Critical tasks that block everything else. Do before any phase work.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| U.1 | Migrate mautrix-whatsapp bridge from old server | CRITICAL | 2 days | 409 EUR | TODO | Transfer existing mautrix-whatsapp bridge config, database, and registration to Hetzner. Verify bridge reconnects to WhatsApp and Matrix homeserver. Test message flow end-to-end. |
| U.2 | Server migration to Hetzner | CRITICAL | 3 days | 614 EUR | TODO | Full migration from current server to Hetzner. PostgreSQL dump + restore, media files, Docker configs, environment variables, nginx configs, DNS cutover. Verify all services: web, celery, redis, Matrix HITL. |
| U.3 | Database and media backups before migration | CRITICAL | 0.5 day | 102 EUR | TODO | Full pg_dump of PostgreSQL, tar of media volume, export vector data. Store backup on separate storage. Verify restore procedure works before migration. |
| U.4 | Clean code merge to main branch | CRITICAL | 1.5 days | 307 EUR | TODO | Audit dev branch, remove dead code, debug prints, hardcoded values. Resolve migration conflicts. Merge clean state into main. Tag release version. |
| U.5 | Connect new client to HITL Matrix | CRITICAL | 1 day | 205 EUR | TODO | Create Matrix room for new client on existing homeserver. Configure Django routing: client_id → matrix_room_id. Test escalation flow: AI trigger → Matrix room → manager notification → response callback. |
| U.6 | Fix web widget Send button on iPhone | CRITICAL | 0.5 day | 102 EUR | TODO | CSS viewport/overflow issue. Send button not visible or not tappable on iPhone Safari. Check position: fixed behavior, safe-area-inset-bottom, viewport meta tag. |
| U.7 | Web widget voice mode: TTS + STT | HIGH | 3 days | 614 EUR | TODO | Full voice mode for web widget. STT: browser MediaRecorder → audio to backend → Whisper transcription. TTS: response text → OpenAI TTS or local model → audio playback in widget. Toggle button for voice mode. |

**Phase Urgent subtotal: 11.5 days (~2.3 weeks) | 2.353 EUR**

---

### PHASE 0: SECURITY HARDENING

> Protect all data and access points before public launch.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 0.1 | Enable encrypted traffic (SSL/TLS) | CRITICAL | 1 day | 205 EUR | TODO | All connections through HTTPS. Required for EU compliance. |
| 0.2 | Restrict internal services from public access | CRITICAL | 1 day | 205 EUR | TODO | Network isolation: DB and Redis not reachable from internet. |
| 0.3 | Remove dev backdoors from production config | CRITICAL | 0.5 day | 102 EUR | TODO | Conditional config: dev tools only in dev mode. |
| 0.4 | Secure API authentication (headers, not URL params) | CRITICAL | 1.5 days | 307 EUR | TODO | Move credentials to HTTP headers. Not visible in logs. |
| 0.5 | Protect client provisioning endpoint | CRITICAL | 1.5 days | 307 EUR | TODO | Cryptographic signature verification for client creation. |
| 0.6 | Centralize all secrets in environment config | CRITICAL | 0.5 day | 102 EUR | TODO | Move 100% of secrets out of code. Add .env template. |
| 0.7 | Rate limit AI chat endpoint | CRITICAL | 0.5 day | 102 EUR | TODO | 30 req/min per user with burst allowance. |
| 0.8 | Rate limit provisioning endpoint | CRITICAL | 0.5 day | 102 EUR | TODO | 5 req/min per source. |

**Phase 0 subtotal: 7 days (~1.4 weeks) | 1.432 EUR**

---

### PHASE 1: ARCHITECTURE REFACTORING

> Modular structure for faster development and easier scaling.
> Agent architecture foundations integrated here.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 1.1 | Separate channel settings from core client data | HIGH | 2 days | 409 EUR | TODO | Move channel config into independent records. |
| 1.2 | Separate AI model settings into dedicated config | HIGH | 1.5 days | 307 EUR | TODO | Dedicated AI configuration per client. |
| 1.3 | Separate human escalation settings | HIGH | 1.5 days | 307 EUR | TODO | Dedicated escalation config per client. |
| 1.4 | Separate notification and email settings | HIGH | 1 day | 205 EUR | TODO | Dedicated notification config record. |
| 1.5 | Separate branding and white-label settings | HIGH | 1 day | 205 EUR | TODO | Custom domain, styling, widget as dedicated record. |
| 1.6 | Update all interfaces for new structure | HIGH | 2 days | 409 EUR | TODO | Admin panel, API, queries updated for modular structure. |
| 1.7 | Extract AI conversation logic into dedicated module | HIGH | 1 day | 205 EUR | TODO | AI logic testable in isolation. |
| 1.8 | Extract document and channel handling into modules | HIGH | 1 day | 205 EUR | TODO | Dedicated modules for documents, channels, escalation. |
| 1.9 | Split settings into logical groups | HIGH | 1 day | 205 EUR | TODO | Separate files: core, AI, security, tasks, integrations. |
| 1.10 | Increase AI response relevance threshold | HIGH | 0.5 day | 102 EUR | TODO | Raise threshold. Below = honest "not found" response. |
| 1.11 | Increase background task processing (4 workers) | HIGH | 0.5 day | 102 EUR | TODO | 4x throughput for document processing. |
| 1.12 | Implement change tracking and audit log | HIGH | 2 days | 409 EUR | TODO | AuditAgent foundation. Log every change: who, what, when. |
| 1.13 | Agent Card table in PostgreSQL | HIGH | 1.5 days | 307 EUR | TODO | Each sub-agent has a DB record: name, version, input/output schema, endpoint, status. Foundation for MCP Agent Cards. |
| 1.14 | Unified JSON message format for all agent calls | HIGH | 1 day | 205 EUR | TODO | Standardize task_id, agent, input, context, output format. All internal communication uses this schema. |
| 1.15 | Agent call logging: request, response, score, timing | HIGH | 1.5 days | 307 EUR | TODO | Every sub-agent call logged with full context. Foundation for self-tuning analytics. |

**Phase 1 subtotal: 19.5 days (~3.9 weeks) | 3.989 EUR**

---

### PHASE 2: SEARCH ENGINE UPGRADE

> Enterprise-grade semantic search with AI reranking. Qdrant migration.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 2.1 | Deploy Qdrant vector search engine | HIGH | 2 days | 409 EUR | TODO | Purpose-built search engine on Data Server. |
| 2.2 | Design multi-tenant search structure in Qdrant | HIGH | 3 days | 614 EUR | TODO | Client isolation, multi-language support, payload filtering. |
| 2.3 | Build VectorStore abstraction layer | HIGH | 2 days | 409 EUR | TODO | Clean interface. SearchAgent uses abstraction, does not know backend. Technology swap = one file change. |
| 2.4 | Enable dual-write: pgvector + Qdrant | HIGH | 2 days | 409 EUR | TODO | New documents indexed in both simultaneously. |
| 2.5 | Migrate existing knowledge base to Qdrant | HIGH | 3 days | 614 EUR | TODO | Background job re-processes all documents with BGE-M3 multilingual embeddings. |
| 2.6 | Verify migration completeness | HIGH | 1 day | 205 EUR | TODO | Counts per client, result spot-checks, target >= 95% match. |
| 2.7 | Upgrade to multilingual embeddings (BGE-M3) | HIGH | 3 days | 614 EUR | TODO | Native 100+ language support. 20-40% better for DE, UK, PL. |
| 2.8 | Add Cohere Rerank (RerankAgent) | HIGH | 3 days | 614 EUR | TODO | Retrieve 20 candidates, rerank by meaning, return top 5. Wraps as RerankAgent with standard I/O. |
| 2.9 | Compare answer quality: old vs new pipeline | HIGH | 2 days | 409 EUR | TODO | A/B comparison framework. Data-driven proof. |
| 2.10 | Switch production to Qdrant | HIGH | 1 day | 205 EUR | TODO | Feature flag switch. Keep pgvector as rollback for 2 weeks. |
| 2.11 | Decommission pgvector | MEDIUM | 1 day | 205 EUR | TODO | After 2 weeks stable. Free resources. |

**Phase 2 subtotal: 23 days (~4.6 weeks) | 4.705 EUR**

---

### PHASE 3: SERVICE EXTRACTION

> Independent, scalable services. Sub-agent extraction.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 3.1 | Create independent AI processing service | MEDIUM | 3 days | 614 EUR | TODO | Standalone: embed, index, reindex, health check. |
| 3.2 | Multi-provider fallback chain | MEDIUM | 2 days | 409 EUR | TODO | Primary cloud → secondary → local models. Auto-failover. |
| 3.3 | Document indexing as independent operation | MEDIUM | 2 days | 409 EUR | TODO | DocumentAgent: async processing with progress tracking. |
| 3.4 | Unified channel management service | MEDIUM | 3 days | 614 EUR | TODO | ChannelAgent: all messages converted to unified format. |
| 3.5 | Channel adapters: Telegram, WhatsApp, Web Widget, Email | MEDIUM | 3 days | 614 EUR | TODO | One adapter per channel, standard output. Adding new channel = one file. |
| 3.6 | Real-time manager response delivery | MEDIUM | 2 days | 409 EUR | TODO | Instant callback when manager replies in Matrix. |
| 3.7 | Escalation timeout and topic-based routing | MEDIUM | 2 days | 409 EUR | TODO | EscalationAgent: 15min default timeout, route by topic. |
| 3.8 | Local AI health monitoring with auto-failover | MEDIUM | 1 day | 205 EUR | TODO | Health checks + auto-switch to cloud if local is down. |
| 3.9 | Orchestrator with async parallel sub-agent calls | MEDIUM | 3 days | 614 EUR | TODO | Main orchestrator dispatches to sub-agents in parallel, collects results as ready. asyncio-based. |
| 3.10 | Extract TranslationAgent and SummaryAgent | MEDIUM | 2 days | 409 EUR | TODO | Stateless sub-agents with standard JSON I/O. TranslationAgent wraps LLM translation. SummaryAgent wraps conversation summarization. |

**Phase 3 subtotal: 23 days (~4.6 weeks) | 4.705 EUR**

---

### PHASE 4: DATA PROTECTION & COMPLIANCE

> EU/GDPR compliance for German and Polish B2B markets.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 4.1 | Encrypt personal data in stored conversations | HIGH | 3 days | 614 EUR | TODO | GDPR Article 32. Encrypt before storage. |
| 4.2 | Transparent encryption layer | HIGH | 2 days | 409 EUR | TODO | Auto encrypt/decrypt, transparent to existing code. |
| 4.3 | Right-to-deletion API | HIGH | 1.5 days | 307 EUR | TODO | GDPR Article 17. Delete messages, vectors, audit records. |
| 4.4 | Automated data retention cleanup | MEDIUM | 1 day | 205 EUR | TODO | Auto-delete older than configurable period (default 90 days). |
| 4.5 | User consent tracking for web widget | MEDIUM | 1.5 days | 307 EUR | TODO | GDPR Article 7. Consent dialog, timestamp, scope. |

**Phase 4 subtotal: 9 days (~1.8 weeks) | 1.841 EUR**

---

### PHASE 5: PRODUCTION INFRASTRUCTURE

> Reliable, monitored, auto-recoverable deployment. MCP endpoints.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 5.1 | Provision production servers (Hetzner EU) | HIGH | 1.5 days | 307 EUR | TODO | EU datacenter. 99.9% uptime. |
| 5.2 | Production deployment configuration | HIGH | 2 days | 409 EUR | TODO | Separate prod config with security and resource limits. |
| 5.3 | Production nginx configuration | HIGH | 1.5 days | 307 EUR | TODO | SSL, compression, security headers, caching, client domains. |
| 5.4 | Automated database backups | HIGH | 1 day | 205 EUR | TODO | Daily full + hourly incremental. Max 1hr data loss. |
| 5.5 | Automated Qdrant backups | MEDIUM | 0.5 day | 102 EUR | TODO | Daily snapshots to separate storage. |
| 5.6 | Recovery procedure documentation | MEDIUM | 0.5 day | 102 EUR | TODO | Step-by-step guide. Target: 30 min full recovery. |
| 5.7 | Error tracking (Sentry or similar) | HIGH | 1 day | 205 EUR | TODO | Real-time error tracking with alerts. |
| 5.8 | Health monitoring for all services | MEDIUM | 1.5 days | 307 EUR | TODO | DB, cache, search, AI providers, Celery. Auto-restart. |
| 5.9 | Automated deployment pipeline (CI/CD) | HIGH | 2 days | 409 EUR | TODO | test → build → staging → approve → production. One-click rollback. |
| 5.10 | Performance monitoring dashboard | LOW | 1 day | 205 EUR | TODO | Key metrics. Proactive monitoring. |
| 5.11 | MCP-compatible Agent Card endpoints | HIGH | 2 days | 409 EUR | TODO | Each sub-agent publishes Agent Card JSON at public endpoint. Standard for MCP (Anthropic) and A2A (Google). |
| 5.12 | Auto-generated API docs per client | HIGH | 3 days | 614 EUR | TODO | On client creation: generate API documentation, Python/JS code examples, Postman collection. Zero developer involvement. |

**Phase 5 subtotal: 18 days (~3.6 weeks) | 3.580 EUR**

---

### PHASE 6: LOCAL AI MODELS

> Cost optimization through hybrid cloud/local AI routing.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 6.1 | Provision GPU server (RunPod) | LOW | 1.5 days | 307 EUR | TODO | RTX 4090, optimized local models (Qwen2.5). |
| 6.2 | Containerize local AI with auto-recovery | LOW | 1 day | 205 EUR | TODO | Ollama in Docker with health checks, model preloading. |
| 6.3 | Cost-based query routing | LOW | 2.5 days | 511 EUR | TODO | Simple queries → local ($0), complex → cloud. 60-70% local. |
| 6.4 | Automatic AI provider failover | LOW | 2 days | 409 EUR | TODO | Fallback chain with health-aware routing. |
| 6.5 | Local vs cloud quality benchmarks | LOW | 1 day | 205 EUR | TODO | 100 queries benchmark: speed, quality, cost per query. |

**Phase 6 subtotal: 8 days (~1.6 weeks) | 1.636 EUR**

---

### PHASE 7: TECHNICAL IMPROVEMENTS

> Eliminate fragile patterns and reduce maintenance risk.

| # | Task | Priority | Duration | Cost | Status | Details |
|---|------|----------|----------|------|--------|---------|
| 7.1 | Production-grade language detection | MEDIUM | 1.5 days | 307 EUR | TODO | Statistical detection with confidence scoring. |
| 7.2 | Remove dev bypass from authentication | MEDIUM | 0.5 day | 102 EUR | TODO | Environment-based flags only. |
| 7.3 | Secure credentials management | MEDIUM | 1.5 days | 307 EUR | TODO | Container-level secrets. Rotation-ready. |
| 7.4 | Remove hardcoded network addresses | MEDIUM | 0.5 day | 102 EUR | TODO | All addresses via environment with defaults. |
| 7.5 | Type safety on critical API endpoints | LOW | 1.5 days | 307 EUR | TODO | Type annotations for public API and data processing. |

**Phase 7 subtotal: 5.5 days (~1.1 weeks) | 1.125 EUR**

---

## Budget Summary

| Phase | Days | Cost | Focus |
|-------|------|------|-------|
| URGENT | 11.5 | 2.353 EUR | Migration, hotfixes, new client |
| Phase 0 | 7 | 1.432 EUR | Security hardening |
| Phase 1 | 19.5 | 3.989 EUR | Architecture + agent foundations |
| Phase 2 | 23 | 4.705 EUR | Search upgrade + Qdrant + Rerank |
| Phase 3 | 23 | 4.705 EUR | Service extraction + sub-agents |
| Phase 4 | 9 | 1.841 EUR | GDPR compliance |
| Phase 5 | 18 | 3.580 EUR | Infrastructure + MCP + API docs |
| Phase 6 | 8 | 1.636 EUR | Local AI models |
| Phase 7 | 5.5 | 1.125 EUR | Tech debt cleanup |
| **TOTAL** | **124.5 days (~5.7 months)** | **25.366 EUR** | |

---

## Dynamic Prompt Priority Chain

```
Client-level override → Specialization default → Branch default → Platform default
```

Each level can define: system prompt, temperature, top_k, language, escalation rules, active tools.

---

## Future Roadmap

### Self-Evolution (4 levels)

| Level | Name | What Changes | Risk | Status in Nexelin |
|-------|------|-------------|------|-------------------|
| 1 | Self-tuning | Agent configuration only | Low | PLANNED (Phase 1.15 lays foundation) |
| 2 | Self-improving | Own prompt strategies | Medium | FUTURE |
| 3 | Self-analyse | Reasoning chains, A/B tests | Medium | FUTURE |
| 4 | Self-decide | Goals and strategy | High | NOT PLANNED |

**Self-tuning implementation plan:**
- Each sub-agent logs: request, response, user score, timing (Phase 1.15)
- Celery task runs daily: analyze error patterns
- Auto-correct: system prompt, temperature, top_k
- Save new config version in DB, apply without restart

**Self-analyse (next stage):**
- A/B testing of agent configurations
- Reasoning chain analysis
- Systematic weak spots in client knowledge base

### ScenarioAgent (Make.com / n8n)

Status: PLANNED — after Phase 3 service extraction is stable.

ScenarioAgent creates and launches automation scenarios from plain-language requests.

**Input:** natural language task description + platform (make/n8n) + client integrations
**Output:** scenario_id, status, preview_url

Example scenarios: lead processing, daily reports, client onboarding, escalation automation, knowledge base updates, reputation monitoring.

Depends on: Orchestrator (3.9), Channel adapters (3.5), Agent Card system (1.13).

### AvatarAgent (Video Responses)

Status: FUTURE

**Input:** text, avatar_id
**Output:** video_url

### Additional Planned Integrations

- Google Calendar (CalendarAgent)
- Google Reviews monitoring
- Instagram DMs channel adapter
- Voice AI (foundation in U.7)
- Mobile apps (iOS / Android)

---

## Key Technical Decisions

- **Avoid overengineering:** sequential DB scans are fine at small scale. Minimal solutions beat elaborate ones.
- **MCP/A2A readiness from day one:** stateless agents, strict schemas, Agent Cards in PostgreSQL.
- **Docker/git dual-path:** on Nexelin server, git pulls update one path, Docker builds use another. Copy between both before rebuilding.
- **Django migration discipline:** conflicts around llm_provider_fk and vector dimensions. Use --fake when schema and migration state diverge.
- **Matrix/MAS complexity:** MAS and Synapse must be fully synchronized or MAS disabled.
- **nginx as silent failure point:** always verify requests reach Django via access logs.

---

## Progress Log

> Format: [DATE] PHASE.TASK — status — notes

```
[2025-XX-XX] U.1 — DONE — mautrix-whatsapp bridge migrated, tested on ...
[2025-XX-XX] U.2 — DONE — server migration complete, DNS switched
```

<!-- Add entries as work progresses. Keep newest at top. -->
