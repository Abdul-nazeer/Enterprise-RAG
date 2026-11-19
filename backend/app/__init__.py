"""
Enterprise RAG Platform Backend

Architecture:
- api/: API layer (FastAPI routes, dependencies)
- core/: Core configuration, security, settings
- db/: Database setup, session management
- models/: SQLAlchemy ORM models
- schemas/: Pydantic schemas for request/response
- services/: Business logic (session, upload, query, etc.)
- utils/: Helper functions, utilities

Following SOLID principles:
- S: Single Responsibility (each module has one job)
- O: Open/Closed (extensible without modification)
- L: Liskov Substitution (proper abstractions)
- I: Interface Segregation (focused interfaces)
- D: Dependency Inversion (depend on abstractions)
"""
__version__ = "0.1.0"
