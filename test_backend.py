#!/usr/bin/env python3
"""Test script to check backend connectivity and configuration."""

import os
import requests
import json

# Check environment variables
print("=== Checking Environment Variables ===")
openai_key = os.getenv("OPENAI_API_KEY")
serpapi_key = os.getenv("SERPAPI_KEY")
database_url = os.getenv("DATABASE_URL")

print(f"OPENAI_API_KEY: {'Set' if openai_key else 'NOT SET'}")
print(f"SERPAPI_KEY: {'Set' if serpapi_key else 'NOT SET'}")
print(f"DATABASE_URL: {database_url if database_url else 'Using default'}")

# Test backend connectivity
print("\n=== Testing Backend Connectivity ===")
backend_url = "http://localhost:8000"

try:
    # Test health endpoint
    response = requests.get(f"{backend_url}/health")
    print(f"Health check: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"Health check failed: {e}")

try:
    # Test root endpoint
    response = requests.get(f"{backend_url}/")
    print(f"Root endpoint: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"Root endpoint failed: {e}")

# Test RFQ endpoint
print("\n=== Testing RFQ Endpoint ===")
test_rfq = {
    "specification": "I need 1000 liters of paint for a warehouse floor"
}

try:
    response = requests.post(
        f"{backend_url}/intelligent-rfq/process",
        json=test_rfq,
        headers={"Content-Type": "application/json"}
    )
    print(f"RFQ endpoint status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error response: {response.text}")
except Exception as e:
    print(f"RFQ endpoint failed: {e}")

print("\n=== Summary ===")
if not openai_key:
    print("❌ OPENAI_API_KEY is not set. Set it with: export OPENAI_API_KEY='your-key-here'")
if not serpapi_key:
    print("❌ SERPAPI_KEY is not set. Set it with: export SERPAPI_KEY='your-key-here'")
if openai_key and serpapi_key:
    print("✅ API keys are configured")