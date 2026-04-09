# Visual Node Editor — Adaptation to MCP Unified Context Architecture

## Context

We have a working node-based visual editor built on React + custom library.
It currently displays flat nodes (Email, Knowledge Base, Telegram Bot, Web Chat, WhatsApp, Live Manager, AI Assistant, Client Manager, Leads) with simple status indicators (Connected / Not connected) and edges between them.

Skills are already implemented as middleware on edges.

The goal is to evolve this editor into a rich, categorized MCP-oriented architecture visualization.

## Current State (What Exists)

- Flat list of nodes with basic cards: icon + name + status badge
- Green dashed edges (AI channels) and orange dashed edges (HITL/escalation flows)
- Top tabs: All (count), Servers, Skills, Tools — simple counters
- No content preview inside node cards
- No labels on edges
- No contextual panels
- Skills work as middleware on edges (already implemented)

## Target State (What We Want)

### 1. Categorized Tab System
Top navigation tabs that group nodes by function:
- **All** — everything
- **Data Sources** — Knowledge Base (Vector Store), Internal Wiki, Code Repository, CRM, Email
- **Business Logic** — Security/Permissions, Custom Action Blocks
- **Automation & Skills** — skills and automation tools
- **Communication & Security** — channels + auth
- **Analytics** — monitoring, dashboards, reports

Each tab shows a count of connected items.

### 2. Rich Node Cards (instead of flat name+status)
Each node becomes a detailed card showing a live preview of its content:

- **Knowledge Base (Vector Store)** — word cloud visualization showing term frequency from client documents. Uses d3-cloud for rendering. Data comes from a backend endpoint that computes word frequencies, cached in Redis with TTL.
- **Internal Wiki** — list of linked internal topics with clickable items
- **Code Repository** — code snippet preview with syntax highlighting
- **CRM** — contact card preview with recent activity
- **Security Permissions** — table view with access control matrix
- **Custom Action Blocks** — list of reusable logic patterns
- **Lead Capture** — visual verification pipeline preview
- **Report Generator** — report template thumbnail
- **Code Interpreter** — Python sandbox snippet
- **API Integration Hub** — connected service logos (Shopify, Stripe, etc.)
- **Decision Matrix** — path/trigger/condition flow preview

### 3. Labeled Edges
Edges between nodes should display action labels:
- "Fetch Semantic Profile"
- "Fetch semantic query"
- "Query order history"
- "Execute code"
- "Action trigger"
- "Apply business rules"
- "Format and send report"
- "Escalation"

Labels sit on the edge path, readable and non-overlapping.

### 4. Context View Panel
A side panel (top-right) that shows merged context for the current query/session:
- Which data sources contributed
- Recent query info
- Active permissions
- Relevant profiles
Format: "Merged Context from: Customer 123 | Recent Query | CRM Profile | Order Status | Internal Wiki | Active permissions"

### 5. Real-time Monitoring Strip
Bottom section with:
- Sales chart (mini sparkline)
- Customer Sentiment gauge
- Connected channel status indicators

## First Step — Audit

Before any code changes, audit the existing codebase:

### Step 1: Audit Knowledge Base Models
Find and analyze all Django models related to Knowledge Base / documents / RAG:
- Where is the original document text stored (which model, which field)?
- How are chunks/embeddings structured?
- How is data linked to Client → Specialization → Branch hierarchy?
- What fields exist for metadata (language, file type, word count, etc.)?
- Are there any existing statistics or aggregation fields?

Report findings as a structured summary with model names, fields, and relationships.

### Step 2: Audit the Node Editor Frontend
Find the React components responsible for:
- Node rendering (card component)
- Edge rendering (connection component)
- The tab/filter system
- Layout engine (how nodes are positioned)
- How skills-as-middleware are attached to edges
- Data fetching (which API endpoints feed the editor)

Report the component tree and data flow.

### Step 3: Propose Adaptation Plan
Based on audit results, propose a step-by-step plan starting with:
1. Knowledge Base rich card with word cloud (d3-cloud + Redis-cached backend endpoint)
2. Edge labels
3. Tab categorization
4. Context View panel
5. Remaining rich cards (one by one)

## Technical Constraints

- Backend: Django 5, PostgreSQL + pgvector, Redis, Celery
- Frontend: React + custom node editor library (NOT React Flow)
- Word cloud: d3-cloud library
- Caching: Redis with TTL for computed word frequencies
- Skills on edges: already implemented as middleware, preserve this
- Code style: clean, no comments in code, English only in code
- Architecture: Branch → Specialization → Client hierarchy
- Multi-language support: DE, PL, UK, EN, FR, IT (relevant for stop-words in word cloud)
- Do NOT rewrite working code — adapt and extend
- Do NOT overcomplicate — minimal changes for maximum result
- Ask before making structural changes

## What NOT To Do

- Do not touch the skill middleware on edges — it works
- Do not migrate to React Flow or any other library
- Do not create new Django apps without discussing first
- Do not add dependencies without justification
- Do not write code comments
- Do not use any language other than English in code
