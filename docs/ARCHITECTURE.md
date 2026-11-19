# Backend Architecture Explanation

## 📚 What We Built So Far

### 1. **Configuration System (`app/core/config.py`)**

#### Why This Approach?
```python
# ❌ Bad: Hardcoded values scattered everywhere
database_url = "postgresql://localhost/db"
secret = "mysecret"

# ✅ Good: Centralized, type-safe configuration
from app.core.config import settings
database_url = settings.DATABASE_URL  # Type-checked, validated
```

#### Key Design Decisions:

**A. Pydantic Settings (Not Python Dictionaries)**
```python
# Why? Type safety + validation at startup
class Settings(BaseSettings):
    SECRET_KEY: str = Field(..., min_length=32)  # MUST be 32+ chars
    DATABASE_URL: str  # Type-checked
```
- **Benefit**: If config is wrong, app won't start (fail fast)
- **Alternative**: Dict would allow wrong types, fail at runtime

**B. LRU Cache for Settings**
```python
@lru_cache()
def get_settings() -> Settings:
    return Settings()
```
- **Why**: Settings are read once, cached in memory
- **Data Structure**: LRU (Least Recently Used) cache - O(1) access
- **Benefit**: Don't re-read .env file on every request

**C. Validation with Pydantic Validators**
```python
@validator("SECRET_KEY")
def validate_secret_key(cls, v):
    if len(v) < 32:
        raise ValueError("Too short!")
```
- **Why**: Enforce security rules at startup
- **Benefit**: Can't run app with weak secrets

---

### 2. **Project Structure (Clean Architecture)**

```
app/
├── api/            # 🌐 HTTP layer (FastAPI routes)
├── core/           # ⚙️ Config, security, settings
├── db/             # 💾 Database session management
├── models/         # 📊 SQLAlchemy ORM (database tables)
├── schemas/        # 📝 Pydantic (API request/response)
├── services/       # 🧠 Business logic (session, upload, query)
└── utils/          # 🛠️ Helper functions
```

#### Why This Structure?

**SOLID Principles in Action:**

**S - Single Responsibility**
- `models/`: Only database structure
- `schemas/`: Only API validation
- `services/`: Only business logic
- Each module has ONE job

**O - Open/Closed**
- Want to add new file type? Extend `services/upload.py`
- Don't modify existing code, add new class

**L - Liskov Substitution**
- All parsers (PDF, DOCX, Image) implement same interface
- Can swap implementations without breaking code

**I - Interface Segregation**
- Small, focused interfaces
- Don't force classes to implement unused methods

**D - Dependency Inversion**
- Services depend on abstractions, not concrete implementations
- Example: Service depends on "DatabaseInterface", not PostgreSQL specifically

---

### 3. **State Management Strategy**

#### Session State Machine

```
User Login → CREATE Session → ACTIVE
                                ↓
                         User uploads docs
                                ↓
                         User asks questions
                                ↓
                     (After 24h inactive)
                                ↓
                             EXPIRED
                                ↓
                        Cleanup job deletes
```

**State Transitions:**
```python
# State enum (better than strings!)
class SessionState(str, Enum):
    ACTIVE = "active"      # User is interacting
    INACTIVE = "inactive"  # No activity for 1 hour
    EXPIRED = "expired"    # 24 hours passed, scheduled for deletion
    DELETED = "deleted"    # Cleaned up
```

**Why Enum?**
- Type-safe (can't typo "activ")
- Autocomplete in IDE
- Easy to refactor

---

### 4. **Data Structures & Algorithms Decisions**

#### A. Session Storage Strategy

**Challenge**: Where to store session data?

**Solution - Tiered Storage (LRU-like)**:
```
Hot (Active):    Redis    - O(1) access, fast
Warm (Recent):   Postgres - O(log n) with index
Cold (Old):      Archive  - Batch cleanup
```

**Algorithm**: Modified LRU Cache
```python
# Pseudocode
class SessionManager:
    def get_session(self, session_id):
        # Try hot tier first (O(1))
        if session_id in redis:
            return redis.get(session_id)
        
        # Fall back to warm tier (O(log n))
        session = db.query(Session).get(session_id)
        
        # Promote to hot tier
        redis.set(session_id, session, ttl=3600)
        return session
```

#### B. Document Chunking Strategy

**Challenge**: How to split documents?

**Data Structure**: Sliding Window with Overlap
```python
# Algorithm: O(n) where n = document length
chunks = []
window_size = 512  # tokens
overlap = 50       # tokens

for i in range(0, len(text), window_size - overlap):
    chunk = text[i:i + window_size]
    chunks.append(chunk)
```

**Why Overlap?**
- Prevents information loss at boundaries
- Example: "...end of sentence. Start of next..." won't be split

#### C. Vector Search Optimization

**Challenge**: Find similar documents fast

**Data Structure**: HNSW (Hierarchical Navigable Small World)
- Used by Qdrant under the hood
- Time Complexity: O(log n) search
- Space Complexity: O(n log n)

**Why HNSW over Brute Force?**
```
Brute Force: O(n) - compare with every vector
HNSW: O(log n) - navigate graph efficiently

For 1M vectors:
- Brute force: 1,000,000 comparisons
- HNSW: ~20 comparisons
```

---

### 5. **Software Principles Applied**

#### A. DRY (Don't Repeat Yourself)
```python
# ❌ Bad: Repeated code
def create_user(...):
    db.add(user)
    db.commit()
    db.refresh(user)

def create_session(...):
    db.add(session)
    db.commit()
    db.refresh(session)

# ✅ Good: Reusable function
async def create_entity(db, entity):
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity
```

#### B. KISS (Keep It Simple, Stupid)
```python
# ❌ Over-engineered
class AbstractFactoryStrategyBuilder:
    def create_instance_with_dependency_injection():
        ...

# ✅ Simple & clear
def create_session(user_id: str) -> Session:
    return Session(user_id=user_id, created_at=datetime.utcnow())
```

#### C. YAGNI (You Aren't Gonna Need It)
- Don't add features "just in case"
- Build what's needed NOW for the demo
- Can extend later if needed

#### D. Separation of Concerns
```
API Layer      → Handle HTTP, validation
Service Layer  → Business logic
Data Layer     → Database operations
```

---

### 6. **Type Safety & Error Handling**

#### A. Type Hints Everywhere
```python
# Helps catch bugs before running
def process_upload(
    file: UploadFile,
    session_id: UUID,
    user_id: UUID
) -> Document:
    ...
```

**Benefits**:
- IDE autocomplete
- mypy catches type errors
- Self-documenting code

#### B. Exception Hierarchy
```python
class AppException(Exception):
    """Base exception"""
    pass

class SessionExpiredException(AppException):
    """Session no longer valid"""
    pass

class UploadTooLargeException(AppException):
    """File exceeds size limit"""
    pass
```

**Why Custom Exceptions?**
- Catch specific errors
- Return appropriate HTTP status codes
- Better debugging

---

## 🎯 Next Steps

Now that we have solid foundation, we'll build:
1. **Database Models** (SQLAlchemy) - Session, User, Document tables
2. **Session Service** - Create, manage, expire sessions
3. **Upload Service** - Handle file uploads with type detection
4. **Multi-format Parsers** - PDF, DOCX, Image, Mermaid, Code

Each will follow the same principles we established here!
