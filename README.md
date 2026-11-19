# Enterprise RAG Platform

> Session-based RAG system with multi-modal document understanding  
> Built for Deloitte Applied AI Engineer role - Demonstrating production-grade AI engineering

## 🎯 What Makes This Unique

**Session-Based Knowledge**: Users upload documents (PDF, images, Mermaid diagrams, code) in isolated sessions and query only their uploads - no global knowledge base.

**Zero Inference Cost**: Using Groq's free Llama 3.1 70B API + local Ollama fallback

**Production-Ready**: Proper exception handling, retry logic, type safety, comprehensive testing

## 🚀 Quick Start

```bash
# 1. Clone and setup
cd backend
cp .env.example .env  # Add your Groq API key

# 2. Install dependencies  
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Start server
uvicorn app.main:app --reload
```

## 📁 Project Structure

```
enterprise-rag-platform/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # REST API endpoints
│   │   ├── core/           # Config, exceptions, retry logic
│   │   ├── db/             # Database connection
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   └── utils/          # Helper functions
│   ├── tests/              # Unit & integration tests
│   └── requirements.txt    # Python dependencies
├── frontend/               # React dashboard (coming soon)
├── docs/                   # All documentation
│   ├── ARCHITECTURE.md     # Design decisions explained
│   ├── PROGRESS.md         # Development tracker
│   └── ROADMAP.md          # 4-week plan
└── docker/                 # Docker configs

```

## 🛠️ Tech Stack

**Backend**: FastAPI, SQLAlchemy, Pydantic  
**Database**: PostgreSQL (Neon serverless)  
**Vector DB**: Qdrant  
**Cache**: Redis  
**LLM**: Groq (free) + Ollama (local)  
**Agent Framework**: LangGraph  
**Testing**: pytest, pytest-asyncio  

## 📊 Development Status

**Phase 1**: Backend Foundation (In Progress - 30%)  
- ✅ Project structure with Clean Architecture
- ✅ Type-safe configuration system  
- ✅ Exception handling hierarchy
- ✅ Retry logic with exponential backoff
- 🟡 Database models (next)
- ⬜ Session management service
- ⬜ File upload & parsing

**Next**: See `docs/ROADMAP.md` for full plan

## 📚 Documentation

All docs in `docs/` folder:
- **ARCHITECTURE.md** - Design decisions, SOLID principles, data structures
- **PROGRESS.md** - What's completed, what's next
- **ROADMAP.md** - 4-week development plan

## 🎯 For Deloitte Interview

**Key Talking Points:**
- "Implemented Clean Architecture with SOLID principles"
- "Built retry logic with exponential backoff for transient errors"
- "Used tiered storage (Redis/PostgreSQL) with O(1) hot-path access"
- "Type-safe configuration with Pydantic validation"
- "Zero inference cost using free Groq API + local fallback"

---

Built with ❤️ for production-grade AI engineering
