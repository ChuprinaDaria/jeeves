# Service Technology Stack Recommendations

## Overview

This document provides technology stack recommendations for each microservice in the refactored architecture, with special focus on performance, scalability, and maintainability.

## General Principles

1. **Right Tool for the Job**: Choose technology based on service requirements
2. **Performance First**: High-throughput services use Go or Rust
3. **Rapid Development**: Business logic services use Python/FastAPI
4. **Real-time Requirements**: WebSocket-heavy services use Node.js or Go
5. **Interoperability**: All services expose REST APIs with OpenAPI specs

---

## Service-by-Service Recommendations

### 1. Integration Service (WhatsApp, Telegram, Email, Matrix HITL)

**Current State**: Django views with webhook handlers

**Recommended Stack**: **Go (GoLang)**

**Rationale**:
- **High Concurrency**: Webhook handlers need to process thousands of requests/second
- **Low Latency**: Real-time messaging requires <100ms response time
- **Memory Efficiency**: Go's goroutines handle concurrent connections efficiently
- **WebSocket Support**: Native WebSocket support for Matrix.org integration
- **Binary Size**: Small Docker images (~20MB vs ~200MB for Python)

**Key Libraries**:
- `matrix-org/gomatrix` - Matrix client SDK
- `gorilla/websocket` - WebSocket handling
- `gin-gonic/gin` - HTTP framework
- `golang.org/x/sync` - Concurrency utilities

**Why Not FastAPI?**
- Go handles concurrent webhooks better (goroutines vs async/await overhead)
- Lower memory footprint for long-running connections
- Better for Matrix.org persistent connections

**Migration Strategy**:
1. Start with Matrix.org integration in Go (new feature)
2. Gradually migrate webhook handlers
3. Keep Django for complex business logic initially

**Structure**:
```
services/integration-service/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── matrix/          # Matrix.org client
│   ├── telegram/        # Telegram bot
│   ├── whatsapp/        # WhatsApp webhooks
│   ├── email/           # Email service
│   └── hitl/            # Human-in-the-loop orchestration
├── pkg/
│   ├── webhook/         # Webhook handlers
│   └── messaging/       # Message routing
├── go.mod
├── go.sum
└── Dockerfile
```

---

### 2. RAG Service

**Current State**: Django app with vector search

**Recommended Stack**: **Python + FastAPI**

**Rationale**:
- **ML/AI Libraries**: Best support for pgvector, embeddings, LLM clients
- **Rapid Development**: Easy integration with OpenAI, Anthropic, Ollama
- **Async Support**: FastAPI handles async LLM calls efficiently
- **Existing Codebase**: Most RAG logic already in Python

**Key Libraries**:
- `fastapi` - Web framework
- `sqlalchemy` - Database ORM
- `pgvector` - Vector operations
- `httpx` - Async HTTP client for LLM APIs
- `pydantic` - Data validation

**Why Not Go?**
- Limited ML/AI ecosystem
- pgvector support is better in Python
- Easier to integrate with existing Python RAG code

**Structure**:
```
services/rag-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   ├── vector_search.py
│   │   ├── context_builder.py
│   │   └── llm_client.py
│   └── models/
│       └── schemas.py
├── requirements.txt
└── Dockerfile
```

---

### 3. Document Processing Service

**Current State**: Django + Celery tasks

**Recommended Stack**: **Python + FastAPI + Celery**

**Rationale**:
- **Document Parsing**: Best libraries in Python (PyPDF2, python-docx, etc.)
- **Async Processing**: Celery handles long-running tasks
- **CouchDB Integration**: Python CouchDB client is mature
- **File Handling**: Python excels at file processing

**Key Libraries**:
- `fastapi` - API framework
- `celery` - Task queue
- `couchdb` - CouchDB client
- `PyPDF2`, `python-docx` - Document parsers
- `Pillow` - Image processing

**Structure**:
```
services/document-service/
├── app/
│   ├── main.py
│   ├── api/
│   ├── workers/
│   │   └── celery_app.py
│   ├── processors/
│   │   ├── pdf.py
│   │   ├── docx.py
│   │   └── image.py
│   └── storage/
│       └── couchdb.py
├── requirements.txt
└── Dockerfile
```

---

### 4. Embedding Service

**Current State**: Part of processing app

**Recommended Stack**: **Python + FastAPI**

**Rationale**:
- **ML Models**: HuggingFace, OpenAI, Cohere SDKs are Python-native
- **Batch Processing**: Python handles batch operations well
- **Model Management**: Easy integration with model registry

**Key Libraries**:
- `fastapi` - API framework
- `openai` - OpenAI embeddings
- `cohere` - Cohere embeddings
- `sentence-transformers` - Local embeddings
- `numpy` - Vector operations

**Why Not Go?**
- Limited ML model support
- Embedding libraries are Python-first

---

### 5. Tenant Service

**Current State**: Django models and views

**Recommended Stack**: **Django REST Framework (Keep Django)**

**Rationale**:
- **Complex Business Logic**: Tenant management has complex relationships
- **Admin Interface**: Django admin is valuable for tenant management
- **Migrations**: Django migrations handle schema-per-tenant well
- **Existing Code**: Minimal refactoring needed

**Key Libraries**:
- `djangorestframework` - REST API
- `django-tenant-schemas` or custom schema routing
- `django-guardian` - Object-level permissions

**Structure**:
```
services/tenant-service/
├── tenant_app/
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   └── admin.py
├── manage.py
├── requirements.txt
└── Dockerfile
```

---

### 6. Analytics Service

**Current State**: UsageStats model in Django

**Recommended Stack**: **Go (GoLang)**

**Rationale**:
- **High Throughput**: Analytics events arrive at high frequency
- **Real-time Aggregation**: Go handles concurrent aggregations efficiently
- **Time-series Data**: Can integrate with InfluxDB or TimescaleDB
- **Low Latency**: Fast query responses for dashboards

**Key Libraries**:
- `gin-gonic/gin` - HTTP framework
- `influxdata/influxdb-client-go` - Time-series database
- `golang.org/x/sync` - Concurrent aggregations

**Why Not Python?**
- Go handles high-frequency events better
- Lower memory overhead for long-running aggregations

**Structure**:
```
services/analytics-service/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── aggregator/
│   ├── storage/
│   └── api/
├── go.mod
└── Dockerfile
```

---

### 7. Model Service (GPU Server Management)

**Current State**: Ollama configuration in settings

**Recommended Stack**: **Python + FastAPI**

**Rationale**:
- **Ollama Integration**: Ollama Python client is mature
- **GPU Management**: Python libraries for GPU monitoring (nvidia-ml-py)
- **Model Registry**: Easy to manage model metadata
- **Health Checks**: Simple to implement with FastAPI

**Key Libraries**:
- `fastapi` - API framework
- `ollama` - Ollama client
- `nvidia-ml-py` - GPU monitoring
- `pydantic` - Model configuration schemas

**Structure**:
```
services/model-service/
├── app/
│   ├── main.py
│   ├── registry/
│   │   ├── models.py
│   │   └── loader.py
│   ├── gpu/
│   │   └── monitor.py
│   └── ollama/
│       └── client.py
├── requirements.txt
└── Dockerfile
```

---

### 8. Django Orchestrator (API Gateway)

**Current State**: Main Django app

**Recommended Stack**: **Django + Django REST Framework**

**Rationale**:
- **Service Discovery**: Django can manage service registry
- **Request Routing**: Middleware handles routing well
- **Authentication**: Django auth integrates with all services
- **Admin Interface**: Useful for service management

**Key Libraries**:
- `djangorestframework` - REST API
- `httpx` - Service client (async)
- `django-cors-headers` - CORS handling
- `django-ratelimit` - Rate limiting

**Structure**:
```
MASTER/orchestrator/
├── gateway/
│   ├── routing.py
│   ├── middleware.py
│   └── views.py
├── service_client/
│   ├── clients.py
│   └── discovery.py
└── workflows/
    └── orchestration.py
```

---

## Technology Comparison Matrix

| Service | Recommended | Alternative | Why Recommended |
|--------|------------|-------------|----------------|
| Integration | **Go** | FastAPI | High concurrency, WebSocket support |
| RAG | **FastAPI** | Go | ML/AI libraries, pgvector |
| Document Processing | **FastAPI + Celery** | Go | Document parsing libraries |
| Embedding | **FastAPI** | Go | ML model support |
| Tenant | **Django** | FastAPI | Complex business logic, admin |
| Analytics | **Go** | FastAPI | High throughput events |
| Model Service | **FastAPI** | Go | Ollama integration, GPU monitoring |
| Orchestrator | **Django** | FastAPI | Service management, admin |

---

## Inter-Service Communication

### Protocol: REST API (Primary)
- All services expose REST APIs
- OpenAPI 3.0 specifications
- JSON request/response format
- Standard HTTP status codes

### Protocol: gRPC (Optional, for high-performance)
- Consider for RAG → Embedding service calls
- Consider for Analytics event streaming
- Not required initially

### Message Queue: Redis/RabbitMQ
- Celery for async tasks (Python services)
- Redis Streams for event streaming
- RabbitMQ for guaranteed delivery (optional)

---

## Database Recommendations

| Service | Database | Rationale |
|---------|----------|-----------|
| Tenant | PostgreSQL (schema-per-tenant) | Multi-tenancy, ACID compliance |
| RAG | PostgreSQL + pgvector | Vector search |
| Document | CouchDB | Document storage, versioning |
| Analytics | TimescaleDB or InfluxDB | Time-series data |
| Embedding | PostgreSQL | Metadata storage |
| Integration | PostgreSQL | Conversation state |

---

## Deployment Considerations

### Containerization
- All services containerized with Docker
- Multi-stage builds for optimization
- Health check endpoints required
- Graceful shutdown handling

### Resource Allocation

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| Integration (Go) | 2 cores | 512MB | Low resource usage |
| RAG (FastAPI) | 4 cores | 2GB | LLM API calls |
| Document (FastAPI) | 2 cores | 1GB | File processing |
| Embedding (FastAPI) | 2 cores | 1GB | Model inference |
| Tenant (Django) | 2 cores | 1GB | Database queries |
| Analytics (Go) | 2 cores | 512MB | Event processing |
| Model Service | 4 cores | 4GB | GPU server management |
| Orchestrator (Django) | 2 cores | 1GB | Request routing |

---

## Migration Priority

1. **High Priority** (Start Here):
   - Integration Service (Matrix.org HITL) - **Go**
   - RAG Service - **FastAPI**

2. **Medium Priority**:
   - Document Service - **FastAPI**
   - Embedding Service - **FastAPI**

3. **Low Priority** (Can stay in Django initially):
   - Tenant Service - **Django**
   - Analytics Service - **Go** (can wait)
   - Model Service - **FastAPI**

---

## Next Steps

1. **Start with Matrix.org Integration** in Go
2. Extract RAG service to FastAPI
3. Gradually migrate other services
4. Maintain backward compatibility during migration

