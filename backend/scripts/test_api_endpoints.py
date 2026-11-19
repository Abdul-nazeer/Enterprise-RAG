#!/usr/bin/env python3
"""
Comprehensive API Endpoint Tests

Tests all REST API endpoints with actual HTTP requests
"""
import requests
import json
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Test data
TEST_EMAIL = f"test_{uuid4()}@example.com"
TEST_PASSWORD = "SecurePassword123!"
TEST_NAME = "Test User"

# Will be populated during tests
access_token = None
refresh_token = None
session_id = None


def print_test(number, description):
    """Print test header"""
    print(f"\n{'='*60}")
    print(f"{number}. {description}")
    print(f"{'='*60}")


def print_response(response):
    """Print response details"""
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return data
    except:
        print(f"Response: {response.text}")
        return None


def test_health():
    """Test health check endpoint"""
    print_test("1", "Health Check - GET /health")
    response = requests.get(f"{BASE_URL}/health")
    return print_response(response)


def test_root():
    """Test root endpoint"""
    print_test("2", "Root - GET /")
    response = requests.get(BASE_URL)
    return print_response(response)


def test_register():
    """Test user registration"""
    print_test("3", "Register User - POST /api/v1/auth/register")
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": TEST_NAME
    }
    response = requests.post(f"{API_V1}/auth/register", json=data)
    result = print_response(response)
    
    if result and response.status_code == 201:
        global access_token, refresh_token
        access_token = result["tokens"]["access_token"]
        refresh_token = result["tokens"]["refresh_token"]
        print(f"\n✅ Tokens saved for subsequent requests")
    
    return result


def test_login():
    """Test user login"""
    print_test("4", "Login - POST /api/v1/auth/login")
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    response = requests.post(f"{API_V1}/auth/login", json=data)
    result = print_response(response)
    
    if result and response.status_code == 200:
        global access_token, refresh_token
        access_token = result["tokens"]["access_token"]
        refresh_token = result["tokens"]["refresh_token"]
        print(f"\n✅ Tokens updated from login")
    
    return result


def test_get_me():
    """Test get current user"""
    print_test("5", "Get Current User - GET /api/v1/auth/me")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{API_V1}/auth/me", headers=headers)
    return print_response(response)


def test_refresh_token():
    """Test token refresh"""
    print_test("6", "Refresh Token - POST /api/v1/auth/refresh")
    data = {"refresh_token": refresh_token}
    response = requests.post(f"{API_V1}/auth/refresh", json=data)
    result = print_response(response)
    
    if result and response.status_code == 200:
        global access_token
        access_token = result["access_token"]
        print(f"\n✅ Access token refreshed")
    
    return result


def test_create_session():
    """Test create session"""
    print_test("7", "Create Session - POST /api/v1/sessions")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(f"{API_V1}/sessions", headers=headers)
    result = print_response(response)
    
    if result and response.status_code == 201:
        global session_id
        session_id = result["id"]
        print(f"\n✅ Session created: {session_id}")
    
    return result


def test_list_sessions():
    """Test list sessions"""
    print_test("8", "List Sessions - GET /api/v1/sessions")
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"page": 1, "page_size": 10}
    response = requests.get(f"{API_V1}/sessions", headers=headers, params=params)
    return print_response(response)


def test_get_session():
    """Test get session by ID"""
    print_test("9", f"Get Session - GET /api/v1/sessions/{session_id}")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{API_V1}/sessions/{session_id}", headers=headers)
    return print_response(response)


def test_update_session():
    """Test update session state"""
    print_test("10", f"Update Session - PUT /api/v1/sessions/{session_id}")
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"state": "inactive"}
    response = requests.put(f"{API_V1}/sessions/{session_id}", headers=headers, json=data)
    return print_response(response)


def test_extend_session():
    """Test extend session TTL"""
    print_test("11", f"Extend Session - POST /api/v1/sessions/{session_id}/extend")
    headers = {"Authorization": f"Bearer {access_token}"}
    # First set back to active
    requests.put(f"{API_V1}/sessions/{session_id}", headers=headers, json={"state": "active"})
    # Then extend
    response = requests.post(f"{API_V1}/sessions/{session_id}/extend", headers=headers)
    return print_response(response)


def test_session_stats():
    """Test get session statistics"""
    print_test("12", "Session Stats - GET /api/v1/sessions/stats/overview")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{API_V1}/sessions/stats/overview", headers=headers)
    return print_response(response)


def test_change_password():
    """Test change password"""
    global access_token, refresh_token
    
    print_test("13", "Change Password - PUT /api/v1/auth/password")
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "old_password": TEST_PASSWORD,
        "new_password": "NewSecurePassword123!"
    }
    response = requests.put(f"{API_V1}/auth/password", headers=headers, json=data)
    result = print_response(response)
    
    if response.status_code == 200:
        # Login with new password to get new tokens
        login_data = {
            "email": TEST_EMAIL,
            "password": "NewSecurePassword123!"
        }
        login_response = requests.post(f"{API_V1}/auth/login", json=login_data)
        if login_response.status_code == 200:
            login_result = login_response.json()
            access_token = login_result["tokens"]["access_token"]
            refresh_token = login_result["tokens"]["refresh_token"]
            print(f"\n✅ Logged in with new password, tokens updated")
    
    return result


def test_delete_session():
    """Test delete session"""
    print_test("14", f"Delete Session - DELETE /api/v1/sessions/{session_id}")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(f"{API_V1}/sessions/{session_id}", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 204:
        print("Response: (No Content)")
        return True
    else:
        return print_response(response)


def test_logout():
    """Test logout"""
    print_test("15", "Logout - POST /api/v1/auth/logout")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(f"{API_V1}/auth/logout", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 204:
        print("Response: (No Content)")
        print("\n✅ Logged out successfully")
        return True
    else:
        return print_response(response)


def test_error_handling():
    """Test error handling"""
    print_test("16", "Error Handling - Test Invalid Endpoints")
    
    # Test 404
    print("\n16a. Invalid endpoint (404):")
    response = requests.get(f"{API_V1}/invalid")
    print_response(response)
    
    # Test 401 (no token)
    print("\n16b. Protected endpoint without token (401):")
    response = requests.get(f"{API_V1}/auth/me")
    print_response(response)
    
    # Test 422 (validation error)
    print("\n16c. Invalid request body (422):")
    response = requests.post(f"{API_V1}/auth/register", json={"email": "invalid"})
    print_response(response)


def run_all_tests():
    """Run all API tests"""
    print("\n" + "="*60)
    print("🧪 ENTERPRISE RAG PLATFORM - API ENDPOINT TESTS")
    print("="*60)
    
    try:
        # Public endpoints
        test_health()
        test_root()
        
        # Authentication flow
        test_register()
        test_login()
        test_get_me()
        test_refresh_token()
        
        # Session management
        test_create_session()
        test_list_sessions()
        test_get_session()
        test_update_session()
        test_extend_session()
        test_session_stats()
        
        # Password change
        test_change_password()
        
        # Cleanup
        test_delete_session()
        test_logout()
        
        # Error handling
        test_error_handling()
        
        print("\n" + "="*60)
        print("✅ ALL API ENDPOINT TESTS COMPLETED!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
