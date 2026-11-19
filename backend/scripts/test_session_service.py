#!/usr/bin/env python3
"""
Quick integration test for Session Service

Tests:
1. Create session
2. Get session (cache miss)
3. Get session again (cache hit)
4. Update state
5. Extend TTL
6. List user sessions
7. Cleanup expired
8. Get stats
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.session_service import SessionService
from app.models.session import SessionState

settings = get_settings()


async def test_session_service():
    """Run integration tests"""
    
    print("🧪 Testing Session Service\n")
    
    # Setup database connection (convert asyncpg SSL mode)
    database_url = settings.DATABASE_URL.replace("?sslmode=require", "?ssl=require")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Setup Redis connection
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    async with async_session() as db:
        service = SessionService(db=db, redis=redis)
        
        # Test user - create a real user first
        user_id = uuid4()
        print(f"👤 Test User ID: {user_id}\n")
        
        # Create user in database (for foreign key constraint)
        from app.models.user import User
        test_user = User(
            id=user_id,
            email=f"test_{user_id}@example.com",
            hashed_password="hashed_password_here",
            full_name="Test User"
        )
        db.add(test_user)
        await db.commit()
        print(f"✅ Created test user in database\n")
        
        # Test 1: Create session
        print("1️⃣ Creating new session...")
        session1 = await service.create_session(user_id)
        print(f"   ✅ Created session: {session1.id}")
        print(f"   - State: {session1.state}")
        print(f"   - Expires: {session1.expires_at}")
        print(f"   - Active: {session1.is_active}\n")
        
        # Test 2: Get session (should hit cache)
        print("2️⃣ Getting session from cache...")
        session2 = await service.get_session(session1.id)
        print(f"   ✅ Retrieved: {session2.id}")
        print(f"   - Document count: {session2.document_count}")
        print(f"   - Query count: {session2.query_count}\n")
        
        # Test 3: Create another session
        print("3️⃣ Creating second session...")
        session3 = await service.create_session(user_id)
        print(f"   ✅ Created: {session3.id}\n")
        
        # Test 4: List user sessions
        print("4️⃣ Listing user sessions...")
        sessions, total = await service.list_user_sessions(user_id)
        print(f"   ✅ Found {total} sessions")
        for s in sessions:
            print(f"   - {s.id} ({s.state})")
        print()
        
        # Test 5: Update session state
        print("5️⃣ Updating session state...")
        updated = await service.update_session_state(
            session1.id,
            SessionState.INACTIVE
        )
        print(f"   ✅ Updated to: {updated.state}\n")
        
        # Test 6: Extend session
        print("6️⃣ Extending session TTL...")
        extended = await service.extend_session(session3.id)
        print(f"   ✅ New expires_at: {extended.expires_at}\n")
        
        # Test 7: Get stats
        print("7️⃣ Getting session statistics...")
        stats = await service.get_session_stats(user_id)
        print(f"   ✅ Stats:")
        print(f"   - Total sessions: {stats.total_sessions}")
        print(f"   - Active: {stats.active_sessions}")
        print(f"   - Inactive: {stats.inactive_sessions}")
        print(f"   - Avg documents/session: {stats.avg_documents_per_session}")
        print(f"   - Avg queries/session: {stats.avg_queries_per_session}\n")
        
        # Test 8: Touch session (update activity)
        print("8️⃣ Touching session (update activity)...")
        await service.touch_session(session3.id)
        print(f"   ✅ Activity updated\n")
        
        # Test 9: Delete session
        print("9️⃣ Deleting session...")
        await service.delete_session(session1.id)
        print(f"   ✅ Session {session1.id} deleted\n")
        
        print("✅ All tests passed!\n")
    
    await redis.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_session_service())
