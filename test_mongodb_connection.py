#!/usr/bin/env python3
"""Test MongoDB connection independently"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

# Load environment variables
load_dotenv()

def test_mongodb_connection():
    """Test MongoDB connection with various timeout settings"""
    
    # Get connection string
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    
    if not connection_string:
        print("❌ MONGODB_CONNECTION_STRING not found in .env file")
        return False
    
    print(f"✓ MongoDB connection string found (length: {len(connection_string)} chars)")
    
    # Show masked connection string for debugging
    if connection_string.startswith("mongodb+srv://"):
        parts = connection_string.split('@')
        if len(parts) > 1:
            masked = f"mongodb+srv://****@{parts[1]}"
            print(f"  Connection: {masked}")
    
    print("\nTesting connection with different timeout settings...")
    
    # Test 1: Default settings
    print("\n1. Testing with default settings...")
    try:
        client = MongoClient(connection_string, tlsCAFile=certifi.where())
        client.admin.command('ping')
        print("   ✓ Connected successfully with default settings")
        client.close()
    except Exception as e:
        print(f"   ✗ Failed with default settings: {e}")
    
    # Test 2: With increased timeouts
    print("\n2. Testing with increased timeouts (30s/30s)...")
    try:
        client = MongoClient(
            connection_string,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        client.admin.command('ping')
        print("   ✓ Connected successfully with explicit timeouts")
        
        # List databases
        dbs = client.list_database_names()
        print(f"   ✓ Found {len(dbs)} databases")
        
        # Check for VietnamStocks database
        if 'VietnamStocks' in dbs:
            print("   ✓ VietnamStocks database exists")
            db = client['VietnamStocks']
            collections = db.list_collection_names()
            print(f"   ✓ Found {len(collections)} collections:")
            for col in collections[:5]:  # Show first 5 collections
                print(f"      - {col}")
        else:
            print("   ⚠ VietnamStocks database not found")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"   ✗ Failed with explicit timeouts: {e}")
    
    # Test 3: With longer timeouts
    print("\n3. Testing with longer timeouts (30s/30s)...")
    try:
        client = MongoClient(
            connection_string,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        client.admin.command('ping')
        print("   ✓ Connected successfully with longer timeouts")
        client.close()
        return True
    except Exception as e:
        print(f"   ✗ Failed with longer timeouts: {e}")
    
    # Test 4: Without SSL certificate file
    print("\n4. Testing without explicit SSL certificate...")
    try:
        client = MongoClient(connection_string)
        client.admin.command('ping')
        print("   ✓ Connected successfully without explicit SSL certificate")
        client.close()
        return True
    except Exception as e:
        print(f"   ✗ Failed without SSL certificate: {e}")
    
    return False

if __name__ == "__main__":
    print("MongoDB Connection Test")
    print("=" * 50)
    
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check certifi
    try:
        import certifi
        print(f"Certifi CA bundle: {certifi.where()}")
    except ImportError:
        print("⚠ Certifi not installed")
    
    print("\n" + "=" * 50)
    
    success = test_mongodb_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ MongoDB connection test PASSED")
    else:
        print("❌ MongoDB connection test FAILED")
        print("\nPossible issues:")
        print("1. Check if MongoDB Atlas is accessible from your network")
        print("2. Verify the connection string in .env file")
        print("3. Check if your IP is whitelisted in MongoDB Atlas")
        print("4. Ensure you have a stable internet connection")