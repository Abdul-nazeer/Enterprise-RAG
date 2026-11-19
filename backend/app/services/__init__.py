"""
Business Logic Services

Design Decision: Service Layer Pattern because:
1. Separates business logic from HTTP handlers
2. Reusable across different interfaces (API, CLI, tests)
3. Easier to test (mock dependencies)
4. Single Responsibility Principle
"""
from app.services.session_service import SessionService

__all__ = [
    "SessionService",
]
