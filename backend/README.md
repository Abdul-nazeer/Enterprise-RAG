# Enterprise RAG Platform - Backend API

FastAPI-based REST API for session-based RAG system.

## Features

- ✅ **Authentication**: JWT tokens (access + refresh)
- ✅ **Session Management**: Isolated RAG sessions per user
- ✅ **Redis Caching**: Hot data in Redis, warm data in PostgreSQL
- ✅ **Database Migrations**: Alembic for schema management
- ✅ **Type Safety**: Pydantic schemas, SQLAlchemy ORM
- ✅ **Error Handling**: Custom exceptions with retry logic
- ✅ **API Documentation**: Auto-generated Swagger UI

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
```

Required variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT signing key (min 32 chars)

### 3. Run Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Or use helper script
python scripts/db_migrate.py upgrade
```

### 4. Start Development Server

```bash
# Method 1: Direct uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Method 2: Python module
python -m app.main

# Method 3: From app directory
cd app && python main.py
```

Server will start at: **http://localhost:8000**

## API Documentation

Once server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | ❌ |
| POST | `/auth/login` | Login with credentials | ❌ |
| POST | `/auth/refresh` | Refresh access token | ❌ |
| POST | `/auth/logout` | Logout (invalidate token) | ✅ |
| GET | `/auth/me` | Get current user info | ✅ |
| PUT | `/auth/password` | Change password | ✅ |

### Sessions (`/api/v1/sessions`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/sessions` | Create new session | ✅ |
| GET | `/sessions` | List user sessions | ✅ |
| GET | `/sessions/{id}` | Get session details | ✅ |
| PUT | `/sessions/{id}` | Update session state | ✅ |
| DELETE | `/sessions/{id}` | Delete session | ✅ |
| POST | `/sessions/{id}/extend` | Extend session TTL | ✅ |
| GET | `/sessions/stats/overview` | Get statistics | ✅ |

## Authentication Flow

### 1. Register

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z"
  },
  "tokens": {
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

### 3. Use Access Token

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <your_access_token>"
```

### 4. Refresh Token

When access token expires (30 min), use refresh token:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<your_refresh_token>"
  }'
```

## Session Management Flow

### 1. Create Session

```bash
curl -X POST "http://localhost:8000/api/v1/sessions" \
  -H "Authorization: Bearer <token>"
```

Response:
```json
{
  "id": "session-uuid",
  "user_id": "user-uuid",
  "state": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-16T10:30:00Z",
  "last_activity_at": "2024-01-15T10:30:00Z",
  "document_count": 0,
  "query_count": 0,
  "is_expired": false,
  "is_active": true
}
```

### 2. List Sessions

```bash
curl -X GET "http://localhost:8000/api/v1/sessions?state=active&page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

### 3. Get Session Stats

```bash
curl -X GET "http://localhost:8000/api/v1/sessions/stats/overview" \
  -H "Authorization: Bearer <token>"
```

## Testing

### Run Integration Tests

```bash
# Test authentication
python scripts/test_auth_service.py

# Test session service
python scripts/test_session_service.py
```

### Test with HTTP Client

Use any HTTP client (Postman, Insomnia, HTTPie):

```bash
# Install httpie
pip install httpie

# Register
http POST localhost:8000/api/v1/auth/register \
  email=test@example.com \
  password=SecurePassword123! \
  full_name="Test User"

# Login
http POST localhost:8000/api/v1/auth/login \
  email=test@example.com \
  password=SecurePassword123!

# Create session (use token from login)
http POST localhost:8000/api/v1/sessions \
  Authorization:"Bearer <token>"
```

## Development

### Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoints
│   │   │   ├── auth.py
│   │   │   └── sessions.py
│   │   └── dependencies.py  # Auth middleware
│   ├── core/
│   │   ├── config.py        # Settings
│   │   ├── security.py      # JWT, password hashing
│   │   ├── exceptions.py    # Custom exceptions
│   │   └── retry.py         # Retry logic
│   ├── db/
│   │   ├── base.py          # Database setup
│   │   └── redis.py         # Redis connection
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── session.py
│   │   └── document.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── user.py
│   │   └── session.py
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   └── session_service.py
│   └── main.py              # FastAPI app
├── alembic/                 # Database migrations
├── scripts/                 # Helper scripts
├── tests/                   # Tests (future)
└── requirements.txt
```

### Code Style

- **Type hints** everywhere for IDE support
- **Docstrings** for all functions
- **Clean Architecture** with clear separation
- **SOLID principles** throughout

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Check current version
alembic current
```

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Database Connection Issues

Check `.env` file has correct `DATABASE_URL`:
```
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname?ssl=require
```

### Redis Connection Issues

Check Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

Start Redis if needed:
```bash
# macOS (Homebrew)
brew services start redis

# Linux
sudo systemctl start redis
```

### Import Errors

Make sure you're in the backend directory:
```bash
cd backend
python -m app.main
```

## Production Deployment

### Environment Variables

Set production values:
```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<strong-random-key>
DATABASE_URL=<production-db-url>
REDIS_URL=<production-redis-url>
```

### Run with Gunicorn

```bash
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Docker (Future)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Next Steps

- [ ] Document upload endpoints
- [ ] Multi-format parsers (PDF, DOCX, Image, Mermaid, Code)
- [ ] Qdrant integration for vector storage
- [ ] LLM integration (Groq + Ollama)
- [ ] Query endpoints with RAG
- [ ] Celery for background jobs
- [ ] Rate limiting
- [ ] API key authentication (for programmatic access)

## License

MIT
