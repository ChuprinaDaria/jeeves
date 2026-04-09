# AI Nexelin Admin Panel

A Django-based admin panel with pgvector support for AI-powered document management and vector search capabilities.

## 🚀 CI/CD Pipeline

This project includes a comprehensive CI/CD pipeline using GitHub Actions:

- **Frontend CI/CD**: Automated linting, security scanning, building, and FTP deployment
- **Backend CI/CD**: Code quality checks, security scanning, testing, Docker building, and VPS deployment
- **Pre-Deployment Checks**: System health checks, dependency validation, configuration validation
- **Error Logging**: Automatic error logging and artifact archiving

**Workflows trigger on push to `main` branch only.**

For detailed CI/CD setup instructions, see [CI/CD Setup Documentation](docs/CI_CD_SETUP.md).

## RAG Overview (High Level)

This project includes a comprehensive Retrieval-Augmented Generation (RAG) pipeline located in `MASTER/rag/`:

### Core Components

- **`vector_search.py`**: Multi-level semantic search across Branch, Specialization, and Client levels with configurable weights and thresholds
- **`context_builder.py`**: Intelligent context assembly with neighbor chunk inclusion and token counting
- **`llm_client.py`**: OpenAI integration with streaming support, retry policies, and custom system prompts
- **`response_generator.py`**: End-to-end pipeline orchestration with source citations and streaming support
- **`diagnostics.py`**: Query performance monitoring and debugging tools

### Multi-Level Search Architecture

The RAG system implements a hierarchical search strategy:

1. **Branch Level**: Global knowledge across all specializations
2. **Specialization Level**: Domain-specific knowledge within a branch
3. **Client Level**: Client-specific documents and configurations
4. **Menu Level**: Restaurant-specific menu items and descriptions

### Configuration

All settings are centralized in `MASTER/settings.py`:

- **`VECTOR_SEARCH_CONFIG`**: Index parameters, similarity thresholds, result limits, and diagnostics
- **`RAG_CONFIG`**: Context size, streaming options, caching, and safety rules
- **`LLM_CONFIG`**: Model selection, temperature, token limits, and retry policies
- **`SYSTEM_PROMPTS`**: Domain-specific prompts for different business verticals

### Performance Optimization

- **pgvector Integration**: Optimized vector operations with IVFFlat and HNSW indexes
- **Caching**: Redis-based response caching for identical queries
- **Streaming**: Real-time response streaming for better user experience
- **Rate Limiting**: Built-in protection against API quota exhaustion

## Project Structure

```
backend/
├── MASTER/                          # Main Django project
│   ├── accounts/                    # User management app
│   │   ├── admin.py                 # User admin configuration
│   │   ├── models.py                # Custom User model with roles
│   │   ├── views.py                 # User authentication views
│   │   └── migrations/              # Database migrations
│   ├── api/                         # Core API endpoints
│   │   ├── views.py                 # RAG, bootstrap, provision endpoints
│   │   ├── serializers.py           # API serializers
│   │   └── urls.py                  # API URL routing
│   ├── branches/                    # Branch management app
│   │   ├── admin.py                 # Branch admin configuration
│   │   ├── models.py                # Branch and document models
│   │   ├── views.py                 # Branch API views
│   │   └── migrations/              # Database migrations
│   ├── clients/                     # Client management app
│   │   ├── admin.py                 # Client admin configuration
│   │   ├── models.py                # Client, API keys, Zero config models
│   │   ├── views.py                 # Client API views
│   │   ├── views_whatsapp.py        # WhatsApp integration
│   │   ├── docker_manager.py        # Zero Docker container management
│   │   ├── middleware.py            # API key authentication
│   │   ├── permissions.py           # Role-based permissions
│   │   ├── qr_utils.py              # QR code generation utilities
│   │   ├── signals.py               # Django signals
│   │   ├── tasks.py                 # Celery tasks
│   │   └── migrations/              # Database migrations
│   ├── specializations/             # Specialization management app
│   │   ├── admin.py                 # Specialization admin configuration
│   │   ├── models.py                # Specialization models
│   │   ├── views.py                 # Specialization API views
│   │   └── migrations/              # Database migrations
│   ├── EmbeddingModel/              # Embedding model management
│   │   ├── admin.py                 # Embedding model admin
│   │   ├── models.py                # Embedding model definitions
│   │   └── apps.py                  # App configuration
│   ├── processing/                  # Document processing pipeline
│   │   ├── tasks.py                 # Celery processing tasks
│   │   ├── parsers.py               # Document parsers (PDF, DOCX, etc.)
│   │   ├── chunker.py               # Text chunking algorithms
│   │   ├── embedding_service.py     # Embedding generation service
│   │   ├── metadata_extractor.py    # Document metadata extraction
│   │   └── RCTS+tiktoken/           # Token counting utilities
│   ├── rag/                         # RAG pipeline
│   │   ├── vector_search.py         # Multi-level vector search
│   │   ├── context_builder.py       # Context assembly
│   │   ├── llm_client.py            # OpenAI integration
│   │   ├── response_generator.py    # End-to-end pipeline
│   │   ├── diagnostics.py           # Performance monitoring
│   │   └── README.md                # RAG documentation
│   ├── restaurant/                  # Restaurant-specific features
│   │   ├── models.py                # Menu, tables, orders models
│   │   ├── views.py                 # Restaurant API views
│   │   ├── serializers.py           # Restaurant serializers
│   │   ├── tasks.py                 # Restaurant-specific tasks
│   │   └── migrations/              # Database migrations
│   ├── client_portal/               # React frontend
│   │   ├── src/                     # React source code
│   │   │   ├── components/          # React components
│   │   │   ├── pages/               # Page components
│   │   │   ├── stores/              # State management
│   │   │   └── i18n/                # Internationalization
│   │   ├── package.json             # Node.js dependencies
│   │   ├── vite.config.ts           # Vite configuration
│   │   └── Dockerfile               # Frontend Docker setup
│   ├── templates/                   # Django templates
│   │   └── admin/                   # Custom admin templates
│   ├── core/                        # Core Django settings
│   │   ├── settings.py              # Main settings
│   │   ├── urls.py                  # URL configuration
│   │   └── wsgi.py                  # WSGI configuration
│   ├── environ/                     # Environment variable handling
│   ├── celery.py                    # Celery configuration
│   └── manage.py                    # Django management script
├── docker/                          # Docker configurations
│   └── zero-test/                   # Zero email service testing
├── docs/                            # Documentation
│   ├── ZERO_INTEGRATION_RU.md       # Zero email integration guide
│   └── ZERO_REAL_SETUP.md           # Zero setup instructions
├── media/                           # User uploaded files
│   ├── branches/                    # Branch documents
│   ├── clients/                     # Client documents and logos
│   ├── restaurant/                  # Menu images and QR codes
│   └── specializations/             # Specialization documents
├── scripts/                         # Utility scripts
│   ├── check_indexes.py             # Database index checker
│   ├── debug_rag_data.py            # RAG debugging tools
│   ├── explain_vector_queries.py    # Vector query analyzer
│   └── setup_zero_for_client.py     # Zero setup automation
├── templates/                       # API documentation templates
│   └── api_docs/                    # Generated API documentation
├── typings/                         # TypeScript type definitions
│   ├── django/                      # Django type stubs
│   ├── MASTER/                      # Project-specific types
│   └── pgvector/                    # pgvector type stubs
├── zero-docker/                     # Zero email service Docker setup
├── zero-mock/                       # Zero mock service
├── zero-package/                    # Zero package files
├── docker-compose.yml               # Main Docker Compose
├── docker-compose.zero.yml          # Zero service Docker Compose
├── requirements.txt                 # Python dependencies
├── test_api.sh                      # API testing script
├── test_full_chain.sh               # Full chain testing script
└── README.md                        # This file
```

## Features

### User Management
- **Custom User Model**: Extended Django user with role-based access (admin, owner, manager, client)
- **Role-Based Permissions**: Granular access control for different user types
- **JWT Authentication**: Secure API access with token-based authentication
- **Session Management**: Traditional Django session support for admin interface

### Document Management
- **Multi-Format Support**: PDF, DOCX, TXT, CSV, XML, JSON document parsing
- **Vector Embeddings**: Automatic embedding generation using OpenAI models
- **Intelligent Chunking**: Context-aware text chunking with overlap
- **Metadata Extraction**: Automatic extraction of document metadata
- **Version Control**: Document versioning and update tracking

### AI Integration
- **Multiple Embedding Providers**: OpenAI, HuggingFace, Cohere support
- **Configurable Models**: Easy switching between different embedding models
- **Cost Tracking**: Usage statistics and cost monitoring per model
- **Fallback Support**: Local TF-IDF fallback when API limits are reached
- **Streaming Responses**: Real-time streaming for better user experience

### RAG Pipeline
- **Multi-Level Search**: Hierarchical search across Branch → Specialization → Client levels
- **Context Assembly**: Intelligent context building with neighbor chunk inclusion
- **Source Citations**: Automatic source attribution with similarity scores
- **Performance Monitoring**: Query diagnostics and performance tracking
- **Caching**: Redis-based response caching for improved performance

### Branch System
- **Hierarchical Organization**: Branch → Specialization → Client structure
- **Document Categorization**: Automatic document organization by hierarchy
- **Custom System Prompts**: Specialized prompts for different business verticals
- **Embedding Model Assignment**: Per-level embedding model configuration

### Restaurant Features
- **Menu Management**: Complete menu system with categories, items, and translations
- **QR Code Generation**: Automatic QR code generation for restaurant tables
- **Order Management**: Order tracking and management system
- **Multi-language Support**: Menu translations in multiple languages
- **Image Management**: Menu item image upload and management
- **Table Management**: Restaurant table configuration and QR code assignment

### Client Portal
- **React Frontend**: Modern React/TypeScript client interface
- **Multi-language UI**: Support for Russian, English, German, French
- **Dark Theme**: CSS variable-based theming system
- **Real-time Updates**: Live data updates and notifications
- **Responsive Design**: Mobile-first responsive design

### Zero Email Integration
- **Docker Container Management**: Automatic Zero email service deployment
- **Gmail OAuth Integration**: Secure Gmail API integration
- **Per-Client Isolation**: Separate Zero instances for each client
- **Email AI Features**: AI-powered email management and automation
- **Container Health Monitoring**: Automatic health checks and restart

### WhatsApp Integration
- **Twilio Integration**: WhatsApp messaging via Twilio API
- **Webhook Support**: Incoming message webhook handling
- **Message Status Tracking**: Delivery and read status tracking
- **Multi-language Messages**: Support for multiple languages

### API Management
- **RESTful API**: Comprehensive REST API for all features
- **API Key Management**: Secure API key generation and management
- **Rate Limiting**: Configurable rate limits per API key
- **Usage Tracking**: Detailed API usage statistics
- **Bootstrap Endpoints**: One-click setup for complete client environments

### Processing Pipeline
- **Asynchronous Processing**: Celery-based background task processing
- **Document Parsing**: Automatic document content extraction
- **Embedding Generation**: Background embedding creation
- **Error Handling**: Robust error handling and retry mechanisms
- **Progress Tracking**: Real-time processing status updates

## Architecture

### System Overview

The AI Nexelin platform is built on a microservices architecture with the following core components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                           │
├─────────────────────────────────────────────────────────────┤
│  React Client Portal  │  Django Admin  │  Zero Email UI    │
│  (Port 5173)         │  (Port 8001)   │  (Port 3000+)     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                        │
├─────────────────────────────────────────────────────────────┤
│  Django REST API  │  Authentication  │  Rate Limiting     │
│  (Port 8000)      │  (JWT/Session)   │  (Redis-based)     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                     │
├─────────────────────────────────────────────────────────────┤
│  RAG Pipeline     │  Document Processing │  Client Management│
│  (Vector Search)  │  (Celery Tasks)     │  (Zero Docker)   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL + pgvector │  Redis Cache  │  Media Storage    │
│  (Port 5432)           │  (Port 6379)  │  (File System)    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    External Services                        │
├─────────────────────────────────────────────────────────────┤
│  OpenAI API      │  Twilio API     │  Gmail API           │
│  (Embeddings)    │  (WhatsApp)     │  (Zero Integration)  │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Django Web Application
- **REST API**: Comprehensive RESTful API for all platform features
- **Admin Interface**: Django admin for system management
- **Authentication**: JWT and session-based authentication
- **File Storage**: Media file management and serving

#### 2. Celery Task Queue
- **Document Processing**: Asynchronous document parsing and embedding
- **Background Tasks**: Long-running operations (email processing, AI tasks)
- **Scheduled Tasks**: Periodic maintenance and health checks
- **Error Handling**: Robust retry mechanisms and error reporting

#### 3. PostgreSQL Database
- **Primary Storage**: All application data and metadata
- **pgvector Extension**: Vector similarity search capabilities
- **ACID Compliance**: Reliable data consistency and transactions
- **Indexing**: Optimized indexes for vector operations

#### 4. Redis Cache
- **Session Storage**: User session management
- **Celery Broker**: Task queue message broker
- **Response Caching**: API response caching for performance
- **Rate Limiting**: API rate limiting storage

#### 5. Vector Search Engine
- **Multi-Level Search**: Hierarchical vector search across branches
- **Similarity Matching**: Semantic similarity using cosine distance
- **Index Optimization**: IVFFlat and HNSW index support
- **Performance Monitoring**: Query performance tracking and optimization

### Data Flow

#### Document Processing Pipeline
1. **Upload**: User uploads document via API or admin interface
2. **Parsing**: Celery task extracts text content using appropriate parser
3. **Chunking**: Text is split into semantic chunks with overlap
4. **Embedding**: Chunks are converted to vector embeddings using OpenAI
5. **Storage**: Embeddings stored in PostgreSQL with pgvector
6. **Indexing**: Vector indexes updated for optimal search performance

#### RAG Query Pipeline
1. **Query Input**: User submits natural language query
2. **Query Embedding**: Query converted to vector embedding
3. **Vector Search**: Multi-level similarity search across hierarchy
4. **Context Assembly**: Top results assembled into context string
5. **LLM Processing**: OpenAI generates response using context
6. **Response Delivery**: Streaming or complete response returned

#### Client Management Flow
1. **Client Creation**: Admin creates client with specialization assignment
2. **API Key Generation**: Secure API key generated for client access
3. **Zero Setup**: Docker container deployed for email service
4. **Portal Access**: Client gains access to React portal interface
5. **Document Upload**: Client uploads documents for AI processing

### Key Modules

#### Processing Pipeline (`MASTER/processing/`)
- **`tasks.py`**: Celery tasks for document processing
- **`parsers.py`**: Document format parsers (PDF, DOCX, etc.)
- **`chunker.py`**: Text chunking algorithms
- **`embedding_service.py`**: Embedding generation service
- **`metadata_extractor.py`**: Document metadata extraction

#### RAG System (`MASTER/rag/`)
- **`vector_search.py`**: Multi-level vector search implementation
- **`context_builder.py`**: Context assembly and token counting
- **`llm_client.py`**: OpenAI API integration
- **`response_generator.py`**: End-to-end RAG pipeline
- **`diagnostics.py`**: Performance monitoring and debugging

#### Client Management (`MASTER/clients/`)
- **`models.py`**: Client, API key, and Zero configuration models
- **`docker_manager.py`**: Zero Docker container management
- **`middleware.py`**: API key authentication middleware
- **`permissions.py`**: Role-based access control
- **`qr_utils.py`**: QR code generation utilities

### Scalability Considerations

#### Horizontal Scaling
- **Load Balancing**: Multiple Django instances behind load balancer
- **Database Replication**: Read replicas for improved query performance
- **Redis Clustering**: Distributed caching for high availability
- **Celery Workers**: Multiple worker processes for task processing

#### Vertical Scaling
- **Database Optimization**: Query optimization and index tuning
- **Memory Management**: Efficient memory usage for vector operations
- **CPU Optimization**: Parallel processing for embedding generation
- **Storage Optimization**: Efficient file storage and retrieval

#### Performance Monitoring
- **Query Analytics**: Database query performance tracking
- **API Metrics**: Request/response time monitoring
- **Resource Usage**: CPU, memory, and disk usage tracking
- **Error Tracking**: Comprehensive error logging and alerting

## Prerequisites

### System Requirements
- **Python**: 3.12+ (recommended 3.12.7)
- **PostgreSQL**: 16+ with pgvector extension
- **Redis**: 7+ for caching and task queue
- **Node.js**: 18+ for frontend development
- **Docker**: 20+ for containerized deployment
- **Memory**: Minimum 4GB RAM (8GB+ recommended)
- **Storage**: 10GB+ free space

### External Services
- **OpenAI API Key**: For embeddings and LLM functionality
- **Google OAuth Credentials**: For Zero email integration (optional)
- **Twilio Account**: For WhatsApp integration (optional)

## Installation

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

6. **Access the application**
   - Django Admin: http://localhost:8001/admin/
   - API: http://localhost:8000/api/
   - Client Portal: http://localhost:5173/

### Option 2: Local Development

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup PostgreSQL with pgvector**
   ```bash
   # Install PostgreSQL 16+
   sudo apt-get install postgresql-16 postgresql-16-pgvector

   # Create database
   sudo -u postgres createdb ai_nexelin_db
   sudo -u postgres psql -d ai_nexelin_db -c "CREATE EXTENSION vector;"
   ```

4. **Setup Redis**
   ```bash
   sudo apt-get install redis-server
   sudo systemctl start redis
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

6. **Run migrations and create superuser**
   ```bash
   cd MASTER
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. **Start development server**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   
   Backend буде доступний на: `http://localhost:8000`
   Django Admin: `http://localhost:8000/admin/`
   API: `http://localhost:8000/api/`

### Option 3: Zero Email Integration

1. **Setup Zero services**
   ```bash
   # Copy Zero environment
   cp zero.env.example .env.zero
   # Edit .env.zero with Google OAuth credentials
   ```

2. **Start Zero services**
   ```bash
   docker-compose -f docker-compose.zero.yml up -d
   ```

3. **Configure Zero for clients**
   - Access Django Admin: http://localhost:8001/admin/
   - Navigate to Clients → Select client
   - Configure Zero Email Service settings
   - Start Zero container for the client

### Environment Configuration

Create a `.env` file with the following variables:

```env
# Django Settings
SECRET_KEY=your-super-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database Configuration
DB_NAME=ai_nexelin_db
DB_USER=ai_nexelin_user
DB_PASS=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# Twilio Configuration (Optional)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Google OAuth (Optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Client Portal
CLIENT_PORTAL_BASE_URL=http://localhost:5173

# Performance Settings
CELERY_WORKER_CONCURRENCY=2
VECTOR_SEARCH_CONFIG_EXPLAIN_QUERIES=True
```

### Frontend Setup

#### Client Portal (React + Vite) - `MASTER/client_portal/`

1. **Install Node.js dependencies**
   ```bash
   cd MASTER/client_portal
   npm install
   ```

2. **Configure environment**
   ```bash
   # Create .env file
   echo "VITE_API_BASE_URL=http://localhost:8000" > .env
   ```
   
   Або створіть файл `.env.development`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```
   
   Фронтенд буде доступний на: `http://localhost:5173`

#### Frontend Frontend (React) - `frontend/`

Якщо ви працюєте з Frontend фронтендом:

1. **Navigate to frontend directory**
   ```bash
   cd ../frontend  # або абсолютний шлях до frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment**
   Створіть `.env.local` файл:
   ```env
   REACT_APP_API_BASE_URL=http://localhost:8000
   ```

4. **Start development server**
   ```bash
   npm start
   ```
   
   Фронтенд буде доступний на: `http://localhost:3000`

### Database Setup

1. **Enable pgvector extension**
   ```sql
   CREATE EXTENSION vector;
   ```

2. **Create indexes for performance**
   ```bash
   python scripts/check_indexes.py
   ```

3. **Load sample data (optional)**
   ```bash
   python manage.py loaddata sample_data.json
   ```

### Celery Setup

1. **Start Celery worker**
   ```bash
   celery -A MASTER worker --loglevel=info
   ```

2. **Start Celery beat (scheduler)**
   ```bash
   celery -A MASTER beat --loglevel=info
   ```

3. **Monitor Celery tasks**
   ```bash
   celery -A MASTER flower
   # Access at http://localhost:5555
   ```

## Локальний запуск та тестування

### Швидкий старт для локальної розробки

#### 1. Запуск Backend (Django)

**Варіант A: Без Docker (рекомендовано для розробки)**

1. **Підготовка середовища**
   ```bash
   # Активуйте віртуальне середовище
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # або
   venv\Scripts\activate  # Windows
   
   # Встановіть залежності
   pip install -r requirements.txt
   ```

2. **Налаштування бази даних**
   ```bash
   # Запустіть PostgreSQL (має бути встановлений з pgvector)
   sudo systemctl start postgresql  # Linux
   
   # Створіть базу даних
   sudo -u postgres createdb ai_nexelin_db
   sudo -u postgres psql -d ai_nexelin_db -c "CREATE EXTENSION vector;"
   ```

3. **Налаштування Redis**
   ```bash
   # Запустіть Redis
   sudo systemctl start redis  # Linux
   # або
   redis-server  # Якщо встановлено локально
   ```

4. **Налаштування змінних середовища**
   
   Створіть файл `.env` в корені проекту:
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
   
   DB_NAME=ai_nexelin_db
   DB_USER=postgres
   DB_PASS=your-postgres-password
   DB_HOST=localhost
   DB_PORT=5432
   
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   
   OPENAI_API_KEY=sk-your-openai-api-key
   
   CLIENT_PORTAL_BASE_URL=http://localhost:5173
   ```

5. **Запуск міграцій**
   ```bash
   cd MASTER
   python manage.py migrate
   python manage.py createsuperuser  # Створіть адміністратора
   ```

6. **Запуск Django сервера**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   
   Backend буде доступний на:
   - API: `http://localhost:8000/api/`
   - Admin: `http://localhost:8000/admin/`
   - Health check: `http://localhost:8000/`

7. **Запуск Celery (опціонально, для фонових задач)**
   
   В окремому терміналі:
   ```bash
   # Celery Worker
   celery -A MASTER worker --loglevel=info
   
   # Celery Beat (планувальник задач)
   celery -A MASTER beat --loglevel=info
   ```

**Варіант B: З Docker Compose**

```bash
# Запуск всіх сервісів
docker-compose up -d

# Перевірка статусу
docker-compose ps

# Перегляд логів
docker-compose logs -f web

# Запуск міграцій
docker-compose exec web python manage.py migrate

# Створення суперкористувача
docker-compose exec web python manage.py createsuperuser
```

#### 2. Запуск Frontend

**Client Portal (MASTER/client_portal/)**

1. **Встановіть залежності**
   ```bash
   cd MASTER/client_portal
   npm install
   ```

2. **Налаштуйте змінні середовища**
   
   Створіть `.env.development`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Запустіть dev сервер**
   ```bash
   npm run dev
   ```
   
   Фронтенд буде доступний на: `http://localhost:5173`

**Frontend Frontend (frontend/)**

Якщо ви працюєте з Frontend фронтендом:

```bash
cd ../frontend  # або абсолютний шлях
npm install
npm start
```

Фронтенд буде доступний на: `http://localhost:3000`

### Тестування

#### 1. Тестування Backend API

**Базове тестування з curl:**

```bash
# Health check
curl http://localhost:8000/

# Створення суперкористувача (якщо ще не створено)
python MASTER/manage.py createsuperuser

# Логін через admin
curl -X POST http://localhost:8000/admin/login/ \
  -d "username=admin&password=yourpassword" \
  -c cookies.txt

# Тест API endpoints
curl http://localhost:8000/api/branches/list/ -b cookies.txt
```

**Використання тестових скриптів:**

```bash
# Базове тестування API
chmod +x test_api.sh
./test_api.sh

# Повне тестування ланцюжка
chmod +x test_full_chain.sh
./test_full_chain.sh
```

**Тестування через Django shell:**

```bash
cd MASTER
python manage.py shell

# Приклад тестування
from branches.models import Branch
from clients.models import Client

# Перевірка моделей
Branch.objects.all()
Client.objects.all()
```

#### 2. Тестування Frontend

**Client Portal:**

1. Відкрийте браузер: `http://localhost:5173`
2. Перевірте консоль браузера на помилки
3. Перевірте Network tab для API запитів

**Тестування інтеграції Frontend-Backend:**

1. Запустіть обидва сервери (Backend на 8000, Frontend на 5173)
2. Перевірте CORS налаштування в `MASTER/settings.py`
3. Перевірте що `VITE_API_BASE_URL` вказує на правильний backend URL

#### 3. Тестування RAG функціональності

```bash
# Через Django shell
cd MASTER
python manage.py shell

from rag.response_generator import RAGResponseGenerator
from clients.models import Client

client = Client.objects.first()
generator = RAGResponseGenerator(client)
response = generator.generate("Тестове питання")
print(response)
```

Або через API:

```bash
# Отримайте API ключ з адмін панелі або через API
API_KEY="your-api-key-here"

curl -X POST http://localhost:8000/api/rag/chat/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Що таке ваші послуги?", "stream": false}'
```

#### 4. Тестування через Django Admin

1. Відкрийте: `http://localhost:8000/admin/`
2. Увійдіть з обліковими даними суперкористувача
3. Перевірте всі моделі:
   - Branches
   - Specializations
   - Clients
   - Embedding Models
   - Documents

#### 5. Перевірка логів

**Django логи:**
```bash
# Якщо використовуєте Docker
docker-compose logs -f web

# Якщо локально
# Логи відображаються в терміналі де запущено runserver
```

**Celery логи:**
```bash
# Якщо використовуєте Docker
docker-compose logs -f celery_worker

# Якщо локально
# Логи відображаються в терміналі де запущено celery worker
```

### Типові проблеми та рішення

**Проблема: CORS помилки**
- Перевірте `CORS_ALLOWED_ORIGINS` в `MASTER/settings.py`
- Додайте `http://localhost:5173` до дозволених джерел

**Проблема: Підключення до бази даних**
- Перевірте що PostgreSQL запущений: `sudo systemctl status postgresql`
- Перевірте налаштування в `.env` файлі
- Перевірте що pgvector встановлений: `psql -d ai_nexelin_db -c "SELECT * FROM pg_extension WHERE extname = 'vector';"`

**Проблема: Redis не підключається**
- Перевірте що Redis запущений: `redis-cli ping`
- Перевірте URL в `.env`: `CELERY_BROKER_URL=redis://localhost:6379/0`

**Проблема: Frontend не підключається до Backend**
- Перевірте що Backend запущений на порту 8000
- Перевірте `VITE_API_BASE_URL` в `.env.development`
- Перезапустіть dev сервер після зміни змінних середовища

**Проблема: Міграції не застосовуються**
```bash
# Перевірте статус міграцій
python MASTER/manage.py showmigrations

# Застосуйте міграції
python MASTER/manage.py migrate

# Якщо є проблеми, створіть міграції заново
python MASTER/manage.py makemigrations
python MASTER/manage.py migrate
```

## Usage

### Admin Panel Access
- URL: `http://localhost:8000/admin/`
- Login with superuser credentials

### Available Models in Admin

#### Users
- **User Management**: Create and manage users with different roles
- **Role-based Access**: Admin, Owner, Manager roles
- **User Profiles**: Email, first name, last name, role management

#### Embedding Models
- **Model Configuration**: Set up different embedding providers
- **Provider Support**: OpenAI, HuggingFace, Cohere
- **Cost Management**: Track costs per 1k tokens
- **Model Selection**: Choose default embedding models

#### Branches
- **Branch Organization**: Create and manage organizational branches
- **Document Management**: Upload and manage documents per branch
- **Vector Search**: Search documents using vector similarity

#### Specializations
- **Specialization Setup**: Create specialized knowledge areas
- **Document Categorization**: Organize documents by specialization
- **Embedding Integration**: Link specializations to embedding models

#### Clients
- **Client Profiles**: Manage client information and preferences
- **API Key Management**: Generate and manage client API keys
- **Document Access**: Control client access to documents

## Database Configuration

### PostgreSQL with pgvector
The project uses PostgreSQL with the pgvector extension for vector operations:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "admin_db",
        "USER": "admin_user",
        "PASSWORD": "admin_pass",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "OPTIONS": {
            "options": "-c default_table_access_method=heap"
        }
    }
}
```

### Vector Configuration
```python
VECTOR_DIMENSION = 1536  # OpenAI embedding dimension
VECTOR_INDEX_TYPE = "ivfflat"  # or "hnsw"
VECTOR_INDEX_LISTS = 100  # for ivfflat
```

## API (high-level)

- Authentication (JWT) — `MASTER/api/`
- Clients and API keys — `MASTER/clients/`
- Vector search/documents — `MASTER/branches/`, `MASTER/specializations/`

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Static Files
```bash
python manage.py collectstatic
```

## Dependencies (core)

- Django, DRF, Celery, Redis
- PostgreSQL + pgvector
- OpenAI SDK, tiktoken
- scikit-learn (TF‑IDF fallback)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support
## Changelog (Recent)

- 2025-10-10: RAG module improvements
  - Stronger typing fixes in `MASTER/rag/response_generator.py` and `MASTER/rag/llm_client.py`.
  - Guaranteed non-null `EmbeddingModel` selection with explicit fallback chain.
  - Simplified type signatures for LLM client to avoid overload conflicts.
  - Documentation updates: added RAG overview and changelog.

## New Features (Restaurant AI, Oct 2025)

This release brings an end-to-end Restaurant assistant workflow: menu embeddings, vector-backed chat, and built‑in text‑to‑speech for answers.

- Restaurant Chat with Vector Context
  - Auto‑embeddings for menu items: on create/update of `MenuItem`, a `MenuItemEmbedding` is generated (signal‑based) using your specialization’s embedding model (fallback to default).
  - Chat first tries vector search over menu embeddings, then falls back to a robust text filter if vectors are unavailable.
  - Toggle restaurant chat per client via `Client.features["menu_chat"] = true` and ensure `client_type = 'restaurant'`.

- TTS in Chat Responses
  - The chat endpoint accepts optional fields: `speak: true` and `voice` (one of `alloy|echo|fable|onyx|nova|shimmer`).
  - The response includes `tts.audio_base64` (MPEG) when `speak` is requested; clients can play it directly.

- Admin Test Console enhancements
  - Page: `admin → Clients → Actions → Test RAG`.
  - Added Speak toggle and Voice selector; when enabled, the page auto‑plays returned TTS from the chat response.

- Public API Quickstart (Restaurant)
  - Chat
    - `POST /api/restaurant/chat/` with header `X-API-Key: <client_api_key>`.
    - Body: `{ message, session_id, language?, table_id?, speak?, voice? }`.
    - Response: `{ response, session_id, suggested_items, context, tts? }`.
  - TTS
    - `POST /restaurant/tts/` with `X-API-Key` and JSON `{ text, voice? }` returns `audio/mpeg`.
  - STT
    - `POST /restaurant/stt/` with `X-API-Key` and multipart `file=@audio` returns `{ text }`.

- Configuration Notes
  - Set `OPENAI_API_KEY` for both LLM and embeddings/TTS.
  - Default dev stack runs on http://localhost:8001 (admin at `/admin/`).
  - Restaurant public endpoints require `X-API-Key` (see `ClientAPIKey`).

- Troubleshooting
  - 401 Invalid API key: ensure you’re sending header `X-API-Key` and using port 8001; verify underscores `_` weren’t lost when copying the key.
  - 403 Restaurant chat not enabled: set `client.features.menu_chat = true` and `client.client_type = 'restaurant'`.
  - TTS 500: verify `OPENAI_API_KEY` is set in the `web` container and rebuild.
  - Order number too long: generation now fits `CharField(20)`.



## API Documentation

### Base URL
```
http://localhost:8000
```

### Authentication

#### Admin Authentication (Session-based)
```bash
# Login to get session cookies
curl -X POST http://localhost:8000/admin/login/ \
  -d "username=admin&password=yourpassword" \
  -c cookies.txt
```

#### API Key Authentication
```bash
# Use API key in headers
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/endpoint/
```

### API Endpoints

#### Branches

**List All Branches**
```bash
GET /api/branches/list/
```

**Create Branch (Admin/Owner only)**
```bash
POST /api/branches/create/
```
Body:
```json
{
  "name": "Restaurants",
  "slug": "restaurants",
  "description": "Restaurant services",
  "is_active": true
}
```

**Update Branch (Admin/Owner only)**
```bash
PUT /api/branches/{id}/update/
```

**Delete Branch (Owner only)**
```bash
DELETE /api/branches/{id}/delete/
```

#### Specializations

**List Specializations**
```bash
GET /api/specializations/list/?branch_id=1
```

**Create Specialization (Admin/Owner/Manager)**
```bash
POST /api/specializations/create/
```
Body:
```json
{
  "name": "Italian Cuisine",
  "slug": "italian",
  "branch_id": 1,
  "description": "Italian restaurants",
  "is_active": true
}
```

**Update Specialization (Admin/Owner/Manager)**
```bash
PUT /api/specializations/{id}/update/
```

**Delete Specialization (Admin/Owner only)**
```bash
DELETE /api/specializations/{id}/delete/
```

#### Clients

**List Clients (Extended)**
```bash
GET /api/clients/list-extended/?branch_id=1&specialization_id=1&client_type=restaurant
```

**Create Client (Admin/Owner/Manager)**
```bash
POST /api/clients/clients/
```
Body:
```json
{
  "specialization": 1,
  "company_name": "Mario Pizza",
  "client_type": "restaurant"
}
```

**Get Client Stats**
```bash
GET /api/clients/{id}/stats/
```

**Create API Key for Client**
```bash
POST /api/clients/{id}/create-api-key/
```
Body:
```json
{
  "name": "Portal Access Key",
  "rate_limit_per_minute": 60,
  "rate_limit_per_day": 10000
}
```

#### Bootstrap & Provision

**Bootstrap Endpoint**
Creates/finds entire hierarchy structure:
```bash
POST /api/bootstrap/{branch_slug}/{specialization_slug}/{client_token}/
```
Example:
```bash
POST /api/bootstrap/restaurants/italian/rag_abc123xyz/
```

**Provision Link**
Creates structure and returns URL:
```bash
POST /api/provision-link/
```
Body:
```json
{
  "branch": "restaurants",
  "specialization": "italian",
  "token": "rag_abc123xyz"
}
```

#### RAG/AI Endpoints

**Chat with RAG (Public, requires API key)**
```bash
POST /api/rag/chat/
Headers: X-API-Key: your_api_key
```
Body:
```json
{
  "query": "What are your services?",
  "stream": false
}
```

**Test RAG Query (Admin only)**
```bash
POST /api/clients/rag-test/
```
Body:
```json
{
  "query": "Test query",
  "client_id": 1,
  "branch_id": 1,
  "specialization_id": 1
}
```

### Complete Testing Chain

**1. Login**
```bash
curl -X POST http://localhost:8000/admin/login/ \
  -d "username=admin&password=yourpass" \
  -c cookies.txt
```

**2. Create Branch**
```bash
curl -X POST http://localhost:8000/api/branches/create/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Restaurants",
    "slug": "restaurants",
    "description": "Restaurant services"
  }'
```

**3. Create Specialization**
```bash
curl -X POST http://localhost:8000/api/specializations/create/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Italian",
    "slug": "italian",
    "branch_id": 1,
    "description": "Italian cuisine"
  }'
```

**4. Create Client**
```bash
curl -X POST http://localhost:8000/api/clients/clients/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "specialization": 1,
    "company_name": "Mario Pizza",
    "client_type": "restaurant"
  }'
```

**5. Create API Key**
```bash
curl -X POST http://localhost:8000/api/clients/1/create-api-key/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main API Key"
  }'
```

**6. Get Statistics**
```bash
curl http://localhost:8000/api/clients/1/stats/ \
  -b cookies.txt
```

**7. Test Bootstrap**
```bash
curl -X POST http://localhost:8000/api/bootstrap/restaurants/italian/rag_abc123xyz/
```

**8. Test Chat**
```bash
curl -X POST http://localhost:8000/api/restaurant/chat/ \
  -H "X-API-Key: rag_abc123xyz" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me the menu",
    "table_id": 1
  }'
```

### One-Liner Demo

Create everything at once:
```bash
# Set cookies
curl -X POST http://localhost:8000/admin/login/ -d "username=admin&password=pass" -c c.txt

# Create everything
B=$(curl -s -X POST http://localhost:8000/api/branches/create/ -b c.txt -H "Content-Type: application/json" -d '{"name":"Demo","slug":"demo"}' | jq -r .id)
S=$(curl -s -X POST http://localhost:8000/api/specializations/create/ -b c.txt -H "Content-Type: application/json" -d "{\"name\":\"Test\",\"slug\":\"test\",\"branch_id\":$B}" | jq -r .id)
C=$(curl -s -X POST http://localhost:8000/api/clients/clients/ -b c.txt -H "Content-Type: application/json" -d "{\"specialization\":$S,\"company_name\":\"Demo Co\",\"client_type\":\"generic\"}" | jq -r .id)
K=$(curl -s -X POST http://localhost:8000/api/clients/$C/create-api-key/ -b c.txt -H "Content-Type: application/json" -d '{"name":"Key"}' | jq -r .key)

echo "Branch ID: $B"
echo "Spec ID: $S"
echo "Client ID: $C"
echo "API Key: $K"
```

### Permission Matrix

| Endpoint | Owner | Admin | Manager | Client |
|----------|-------|-------|---------|--------|
| POST branches/create/ | ✅ | ✅ | ❌ | ❌ |
| PUT branches/update/ | ✅ | ✅ | ❌ | ❌ |
| DELETE branches/delete/ | ✅ | ❌ | ❌ | ❌ |
| POST specializations/create/ | ✅ | ✅ | ✅ | ❌ |
| PUT specializations/update/ | ✅ | ✅ | ✅ | ❌ |
| DELETE specializations/delete/ | ✅ | ✅ | ❌ | ❌ |
| POST clients/clients/ | ✅ | ✅ | ✅ | ❌ |
| PUT clients/clients/{id}/ | ✅ | ✅ | ✅ | ❌ |
| DELETE clients/clients/{id}/ | ✅ | ✅ | ❌ | ❌ |
| GET clients/{id}/stats/ | ✅ | ✅ | ✅ | ❌ |
| POST clients/{id}/create-api-key/ | ✅ | ✅ | ✅ | ❌ |
| GET /api/clients/me/ | ❌ | ❌ | ❌ | ✅ |
| POST /api/restaurant/chat/ | - | - | - | API Key |

### Filters & Query Parameters

**Specializations**
- `GET /api/specializations/list/?branch_id=1`

**Clients**
- `GET /api/clients/list-extended/`
  - `?branch_id=1` - Filter by branch
  - `&specialization_id=1` - Filter by specialization
  - `&client_type=restaurant` - Filter by type

### Status Codes

- `200` - OK
- `201` - Created
- `204` - No Content (deleted)
- `400` - Bad Request (validation error)
- `403` - Forbidden (permission denied)
- `404` - Not Found
- `500` - Internal Server Error

### Frontend Integration

#### Client Portal
The client portal is a React/TypeScript application that connects to this API. It provides:

1. **Admin Dashboard** - Full management interface for branches, specializations, and clients
2. **Client Portal** - Individual client interface for managing their AI chat system
3. **Restaurant Interface** - Specialized interface for restaurant clients with QR code generation

#### CORS Configuration
The API is configured to accept requests from:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)
- `http://localhost:8080` (Alternative dev server)

#### Authentication Flow
1. **Admin users** use session-based authentication via `/admin/login/`
2. **Client users** use API key authentication via `X-API-Key` header
3. **Bootstrap flow** creates client accounts automatically with provided tokens

### API Testing

Use the provided test scripts:
```bash
# Basic API testing
chmod +x test_api.sh
./test_api.sh

# Full chain testing
chmod +x test_full_chain.sh
./test_full_chain.sh
```

## Scripts and Utilities

The project includes several utility scripts for maintenance and debugging:

### Database Scripts

#### `scripts/check_indexes.py`
Checks and displays database indexes for vector operations:
```bash
python scripts/check_indexes.py
```

#### `scripts/check_usage_stats_and_indexes.py`
Comprehensive database health check including usage statistics and index analysis:
```bash
python scripts/check_usage_stats_and_indexes.py
```

### RAG Debugging Scripts

#### `scripts/debug_rag_data.py`
Debug RAG pipeline and vector search functionality:
```bash
python scripts/debug_rag_data.py --client-id 1 --query "test query"
```

#### `scripts/explain_vector_queries.py`
Analyze vector query performance and execution plans:
```bash
python scripts/explain_vector_queries.py --query "sample query"
```

### Zero Integration Scripts

#### `scripts/setup_zero_for_client.py`
Automated Zero email service setup for clients:
```bash
python scripts/setup_zero_for_client.py --client-id 1 --google-client-id "your-id"
```

#### `scripts/test_zero_integration.py`
Test Zero email service integration:
```bash
python scripts/test_zero_integration.py --client-id 1
```

### Development Scripts

#### `test_api.sh`
Comprehensive API testing script that tests all major endpoints:
- Authentication flow
- CRUD operations for all models
- RAG functionality
- Error handling

#### `test_full_chain.sh`
Complete system integration test:
- Creates full hierarchy (Branch → Specialization → Client)
- Tests API key generation
- Validates bootstrap functionality
- Tests RAG chat functionality

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check database connection
python manage.py dbshell

# Verify pgvector extension
python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('SELECT * FROM pg_extension WHERE extname = \"vector\";'); print(cursor.fetchall())"
```

#### Redis Connection Issues
```bash
# Check Redis status
redis-cli ping

# Check Redis configuration
redis-cli config get "*"
```

#### Celery Task Issues
```bash
# Check Celery worker status
celery -A MASTER inspect active

# Check task results
celery -A MASTER inspect stats

# Clear failed tasks
celery -A MASTER purge
```

#### Vector Search Performance
```bash
# Check vector indexes
python scripts/check_indexes.py

# Analyze query performance
python scripts/explain_vector_queries.py --query "your query"

# Debug RAG pipeline
python scripts/debug_rag_data.py --client-id 1
```

### Performance Optimization

#### Database Optimization
1. **Check index usage**:
   ```bash
   python scripts/check_indexes.py
   ```

2. **Analyze slow queries**:
   ```bash
   python scripts/explain_vector_queries.py
   ```

3. **Monitor database performance**:
   ```sql
   SELECT * FROM pg_stat_activity;
   SELECT * FROM pg_stat_user_tables;
   ```

#### Memory Optimization
1. **Monitor memory usage**:
   ```bash
   # Check Python process memory
   ps aux | grep python

   # Check Redis memory
   redis-cli info memory
   ```

2. **Optimize vector operations**:
   - Adjust `VECTOR_SEARCH_CONFIG` settings
   - Tune `ivfflat_probes` and `hnsw_ef_search` parameters
   - Monitor query execution times

#### API Performance
1. **Enable response caching**:
   ```python
   # In settings.py
   RAG_CONFIG['cache_enabled'] = True
   ```

2. **Monitor API metrics**:
   - Check response times in Django logs
   - Monitor Celery task queue length
   - Track API key usage statistics

### Logging and Monitoring

#### Django Logging
```python
# In settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

#### Celery Monitoring
```bash
# Start Flower monitoring
celery -A MASTER flower

# Access at http://localhost:5555
```

#### Vector Search Monitoring
```bash
# Enable query explanation
export VECTOR_SEARCH_CONFIG_EXPLAIN_QUERIES=True

# Run performance analysis
python scripts/explain_vector_queries.py
```

## Production Deployment

### Docker Production Setup

1. **Build production images**:
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

2. **Deploy with environment variables**:
   ```bash
   # Set production environment
   export DJANGO_SETTINGS_MODULE=MASTER.settings_prod
   export DEBUG=False
   export SECRET_KEY=your-production-secret

   # Start services
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Setup SSL certificates**:
   ```bash
   # Use Let's Encrypt or your SSL provider
   # Configure nginx reverse proxy
   ```

### Environment-Specific Configuration

#### Production Settings
```python
# settings_prod.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

#### Database Configuration
```python
# Production database settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ai_nexelin_prod',
        'USER': 'ai_nexelin_user',
        'PASSWORD': 'secure_password',
        'HOST': 'db.yourdomain.com',
        'PORT': '5432',
        'OPTIONS': {
            'sslmode': 'require',
        }
    }
}
```

### Backup and Recovery

#### Database Backup
```bash
# Create backup
pg_dump -h localhost -U ai_nexelin_user ai_nexelin_db > backup.sql

# Restore backup
psql -h localhost -U ai_nexelin_user ai_nexelin_db < backup.sql
```

#### Media Files Backup
```bash
# Backup media files
tar -czf media_backup.tar.gz media/

# Restore media files
tar -xzf media_backup.tar.gz
```

### Security Considerations

1. **API Key Security**:
   - Rotate API keys regularly
   - Monitor API key usage
   - Implement rate limiting

2. **Database Security**:
   - Use strong passwords
   - Enable SSL connections
   - Regular security updates

3. **File Upload Security**:
   - Validate file types
   - Scan for malware
   - Limit file sizes

4. **Network Security**:
   - Use HTTPS in production
   - Configure firewall rules
   - Monitor access logs

For support and questions, please contact the development team or create an issue in the repository.
