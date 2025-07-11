#!/usr/bin/env python3
"""
Test script for the authentication service API endpoints
"""

import requests
import json
import time

AUTH_BASE_URL = "http://localhost:8082"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{AUTH_BASE_URL}/health")
        print(f"Health check status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Health check failed: {e}")
        return False

def test_user_registration():
    """Test user registration"""
    print("\nTesting user registration...")
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "name": "Test User"
    }
    
    try:
        response = requests.post(
            f"{AUTH_BASE_URL}/api/auth/register",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Registration status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Registration failed: {e}")
        return False

def test_user_login():
    """Test user login"""
    print("\nTesting user login...")
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "login_type": "local"
    }
    
    try:
        response = requests.post(
            f"{AUTH_BASE_URL}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Login status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            return response.json()["data"]["jwt_token"]
        return None
    except requests.RequestException as e:
        print(f"Login failed: {e}")
        return None

def test_thermoworks_login():
    """Test ThermoWorks login"""
    print("\nTesting ThermoWorks login...")
    login_data = {
        "email": "thermoworks@example.com",
        "password": "testpassword123",
        "login_type": "thermoworks"
    }
    
    try:
        response = requests.post(
            f"{AUTH_BASE_URL}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"ThermoWorks login status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            return response.json()["data"]["jwt_token"]
        return None
    except requests.RequestException as e:
        print(f"ThermoWorks login failed: {e}")
        return None

def test_auth_status(token):
    """Test authentication status check"""
    print("\nTesting authentication status...")
    try:
        response = requests.get(
            f"{AUTH_BASE_URL}/api/auth/status",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        print(f"Auth status check: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Auth status check failed: {e}")
        return False

def test_user_info(token):
    """Test getting current user info"""
    print("\nTesting user info...")
    try:
        response = requests.get(
            f"{AUTH_BASE_URL}/api/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        print(f"User info status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"User info failed: {e}")
        return False

def test_logout(token):
    """Test user logout"""
    print("\nTesting logout...")
    try:
        response = requests.post(
            f"{AUTH_BASE_URL}/api/auth/logout",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        print(f"Logout status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Logout failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting authentication service tests...")
    print("=" * 50)
    
    # Test health check
    if not test_health_check():
        print("Health check failed. Is the auth service running?")
        return
    
    # Test user registration
    test_user_registration()
    
    # Test local login
    token = test_user_login()
    if token:
        test_auth_status(token)
        test_user_info(token)
        test_logout(token)
    
    # Test ThermoWorks login
    tw_token = test_thermoworks_login()
    if tw_token:
        test_auth_status(tw_token)
        test_user_info(tw_token)
        test_logout(tw_token)
    
    print("\n" + "=" * 50)
    print("Authentication service tests completed!")

if __name__ == "__main__":
    main()