#!/usr/bin/env python3
"""
Test script to verify the /api/load endpoint works with Java installed
"""

import requests
import json
import tempfile
import os

# API base URL
BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test the health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_create_session():
    """Test creating an upload session"""
    try:
        response = requests.post(f"{BASE_URL}/api/upload/create-session")
        print(f"Create session: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Session ID: {data.get('session_id')}")
            return data.get('session_id')
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Create session failed: {e}")
        return None

def test_upload_files(session_id):
    """Test uploading files to the session"""
    if not session_id:
        return False
    
    # Create a simple test CSV file
    test_csv = """id,name,age
1,Alice,30
2,Bob,25
3,Charlie,35"""
    
    files = {
        'files': ('test_data.csv', test_csv, 'text/csv')
    }
    data = {
        'session_id': session_id
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/upload/files", files=files, data=data)
        print(f"Upload files: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Uploaded files: {data.get('uploaded_files')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Upload files failed: {e}")
        return False

def test_load_data(session_id):
    """Test the load data endpoint"""
    if not session_id:
        return False
    
    # Fixed configuration format for HugeGraph loader
    config = {
        "vertices": [
            {
                "label": "person",
                "input": {
                    "type": "file",
                    "path": "test_data.csv"
                },
                "field_mapping": {
                    "id": "id",
                    "name": "name", 
                    "age": "age"
                },
                "id": "id"
            }
        ],
        "edges": []
    }
    
    schema = {
        "property_keys": [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "text"},
            {"name": "age", "type": "int"}
        ],
        "vertex_labels": [
            {
                "name": "person", 
                "properties": ["id", "name", "age"],
                "id_strategy": "customize_string"
            }
        ],
        "edge_labels": []
    }
    
    data = {
        'session_id': session_id,
        'config': json.dumps(config),
        'schema_json': json.dumps(schema),
        'writer_type': 'metta'
    }
    
    try:
        print("Testing load data endpoint...")
        response = requests.post(f"{BASE_URL}/api/load", data=data)
        print(f"Load data: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Job ID: {result.get('job_id')}")
            print(f"Status: {result.get('status')}")
            print(f"Message: {result.get('message')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Load data failed: {e}")
        return False

def main():
    """Run the test sequence"""
    print("=== Testing Custom AtomSpace Builder API ===")
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    if not test_health():
        print("❌ Health check failed")
        return
    
    # Test 2: Create session
    print("\n2. Testing session creation...")
    session_id = test_create_session()
    if not session_id:
        print("❌ Session creation failed")
        return
    
    # Test 3: Upload files
    print("\n3. Testing file upload...")
    if not test_upload_files(session_id):
        print("❌ File upload failed")
        return
    
    # Test 4: Load data
    print("\n4. Testing data loading...")
    if not test_load_data(session_id):
        print("❌ Data loading failed")
        return
    
    print("\n✅ All tests passed! The Java installation fixed the issue.")

if __name__ == "__main__":
    main() 