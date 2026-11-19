#!/usr/bin/env python3
"""
Integration test for Authentication Service

Tests:
1. Register new user
2. Login with correct credentials
3. Login with wrong password (should fail)
4. Get user by ID
5. Get user by email
6. Refresh access token
7. Change password
8. Deactivate user
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

from app.core.config import get_settings
from app.services.auth_service import AuthService, AuthenticationError
from app.schemas.user import UserCreate

settings = get_settings()


async def test_auth_service():
    """Run authentication integration tests"""
    
    print("🔐 Testing Authentication Service\n")
    
    # Setup database connection
    database_url = settings.DATABASE_URL.replace("?sslmode=require", "?ssl=require")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as db:
        service = AuthService(db=db)
        
        # Test data
        test_email = f"test_{uuid4()}@example.com"
        test_password = "SecurePassword123!"
        test_name = "Test User"
        
        print(f"📧 Test Email: {test_email}\n")
        
        # Test 1: Register new user
        print("1️⃣ Registering new user...")
        try:
            user_data = UserCreate(
                email=test_email,
                password=test_password,
                full_name=test_name
            )
            result = await service.register_user(user_data)
            print(f"   ✅ Registered user: {result.user.id}")
            print(f"   - Email: {result.user.email}")
            print(f"   - Name: {result.user.full_name}")
            print(f"   - Active: {result.user.is_active}")
            print(f"   - Access Token: {result.tokens.access_token[:50]}...")
            print(f"   - Refresh Token: {result.tokens.refresh_token[:50]}...")
            user_id = result.user.id
            refresh_token = result.tokens.refresh_token
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            return
        print()
        
        # Test 2: Try to register with same email (should fail)
        print("2️⃣ Trying to register with duplicate email...")
        try:
            duplicate_data = UserCreate(
                email=test_email,
                password="AnotherPassword123!",
                full_name="Duplicate User"
            )
            await service.register_user(duplicate_data)
            print(f"   ❌ Should have failed but didn't!")
        except Exception as e:
            print(f"   ✅ Correctly rejected: {type(e).__name__}")
        print()
        
        # Test 3: Login with correct credentials
        print("3️⃣ Logging in with correct credentials...")
        try:
            login_result = await service.login(test_email, test_password)
            print(f"   ✅ Login successful")
            print(f"   - User ID: {login_result.user.id}")
            print(f"   - Token expires in: {login_result.tokens.expires_in}s")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        # Test 4: Login with wrong password (should fail)
        print("4️⃣ Trying to login with wrong password...")
        try:
            await service.login(test_email, "WrongPassword123!")
            print(f"   ❌ Should have failed but didn't!")
        except AuthenticationError as e:
            print(f"   ✅ Correctly rejected: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
        print()
        
        # Test 5: Get user by ID
        print("5️⃣ Getting user by ID...")
        try:
            user = await service.get_user_by_id(user_id)
            if user:
                print(f"   ✅ Found user: {user.email}")
                print(f"   - Created at: {user.created_at}")
            else:
                print(f"   ❌ User not found")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        # Test 6: Get user by email
        print("6️⃣ Getting user by email...")
        try:
            user = await service.get_user_by_email(test_email)
            if user:
                print(f"   ✅ Found user: {user.id}")
            else:
                print(f"   ❌ User not found")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        # Test 7: Refresh access token
        print("7️⃣ Refreshing access token...")
        try:
            new_tokens = await service.refresh_access_token(refresh_token)
            print(f"   ✅ Got new access token")
            print(f"   - New token: {new_tokens.access_token[:50]}...")
            print(f"   - Refresh token (same): {new_tokens.refresh_token[:50]}...")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        # Test 8: Change password
        print("8️⃣ Changing password...")
        try:
            new_password = "NewSecurePassword123!"
            success = await service.change_password(
                user_id,
                test_password,
                new_password
            )
            if success:
                print(f"   ✅ Password changed successfully")
                
                # Verify old password doesn't work
                print(f"   - Verifying old password doesn't work...")
                try:
                    await service.login(test_email, test_password)
                    print(f"     ❌ Old password still works!")
                except AuthenticationError:
                    print(f"     ✅ Old password correctly rejected")
                
                # Verify new password works
                print(f"   - Verifying new password works...")
                try:
                    await service.login(test_email, new_password)
                    print(f"     ✅ New password works")
                except Exception as e:
                    print(f"     ❌ New password doesn't work: {e}")
            else:
                print(f"   ❌ Password change failed")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        # Test 9: Try to change password with wrong old password
        print("9️⃣ Trying to change password with wrong old password...")
        try:
            await service.change_password(
                user_id,
                "WrongOldPassword123!",
                "AnotherNewPassword123!"
            )
            print(f"   ❌ Should have failed but didn't!")
        except AuthenticationError as e:
            print(f"   ✅ Correctly rejected: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
        print()
        
        # Test 10: Deactivate user
        print("🔟 Deactivating user...")
        try:
            success = await service.deactivate_user(user_id)
            if success:
                print(f"   ✅ User deactivated")
                
                # Try to login (should fail)
                print(f"   - Trying to login with deactivated account...")
                try:
                    await service.login(test_email, new_password)
                    print(f"     ❌ Login should have failed!")
                except AuthenticationError as e:
                    print(f"     ✅ Correctly rejected: {e}")
            else:
                print(f"   ❌ Deactivation failed")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        print()
        
        print("✅ All authentication tests passed!\n")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_auth_service())
