#!/usr/bin/env python3
"""
Simple test script for the RGB Matrix API Server
"""
import requests
import time
import json

# BASE_URL = "http://localhost:9191"
BASE_URL = "http://192.168.1.137:9191"

def test_status():
    """Test the status endpoint"""
    print("Testing status endpoint...")
    response = requests.get(f"{BASE_URL}/matrix/status")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_text_display():
    """Test text display"""
    print("Testing text display...")
    data = {
        "text": "Testing RGB Matrix API!",
        "duration": 3.0
    }
    response = requests.post(f"{BASE_URL}/matrix/show/text", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_image_display():
    """Test image display"""
    print("Testing image display...")
    data = {
        "url": "https://drive.google.com/uc?id=1muUjq2Q_Sxu5-lcsEgc90XycBVtG7Jls",
        "duration": 30.0
    }
    response = requests.post(f"{BASE_URL}/matrix/show/image", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_weather_display():
    """Test weather display"""
    print("Testing weather display...")
    data = {
        "template": "current",
        "duration": 3.0
    }
    response = requests.post(f"{BASE_URL}/matrix/show/weather", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_clear():
    """Test clear matrix"""
    print("Testing clear matrix...")
    response = requests.post(f"{BASE_URL}/matrix/clear")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_stop():
    """Test stop current job"""
    print("Testing stop current job...")
    response = requests.post(f"{BASE_URL}/matrix/stop")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

if __name__ == "__main__":
    print("🚀 Testing RGB Matrix API Server")
    print("=" * 40)
    
    try:
        # Test all endpoints
        test_status()
        test_text_display()
        time.sleep(1)  # Wait a bit between tests
        
        test_image_display()
        time.sleep(2)
        
        test_weather_display()
        time.sleep(1)
        
        test_clear()
        test_stop()
        test_status()
        
        print("✅ All tests completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server.")
        print("Make sure the server is running on http://localhost:9191")
    except Exception as e:
        print(f"❌ Error: {e}")
