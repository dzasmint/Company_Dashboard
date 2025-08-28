re#!/usr/bin/env python3
"""
Utility script to upload CSV financial data to MongoDB
This will help avoid repeated CSV file reading which causes performance issues
"""

import pandas as pd
import os
import sys
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

def init_mongodb_connection():
    """Initialize MongoDB connection"""
    try:
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if not connection_string:
            print("❌ MONGODB_CONNECTION_STRING not found in .env file")
            return None
        
        client = MongoClient(
            connection_string,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000
        )
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")
        return client
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        return None

# DEPRECATED: FinancialStatements collection is no longer used
# The application now loads financial data directly from CSV files via data_loader.py
# Keeping this function commented for reference only
'''
def upload_fa_data_to_mongodb(ticker=None, collection_name='FinancialStatements'):
    """
    Upload FA_A_processed.csv data to MongoDB
    
    Args:
        ticker: Specific ticker to upload (None for all)
        collection_name: Name of MongoDB collection to create/update
    """
    try:
        # Load CSV file
        csv_path = os.path.join(parent_dir, 'data', 'FA_A_processed.csv')
        print(f"📂 Loading data from: {csv_path}")
        
        if not os.path.exists(csv_path):
            print(f"❌ File not found: {csv_path}")
            return False
        
        # Read CSV
        df = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(df)} rows from CSV")
        
        # Filter for specific ticker if provided
        if ticker:
            df = df[df['TICKER'] == ticker].copy()
            print(f"📊 Filtered to {len(df)} rows for ticker: {ticker}")
            
            if df.empty:
                print(f"❌ No data found for ticker: {ticker}")
                return False
        
        # Connect to MongoDB
        client = init_mongodb_connection()
        if not client:
            return False
        
        # Get database and collection
        db = client['VietnamStocks']
        collection = db[collection_name]
        
        # Clear existing data for the ticker(s) if updating
        if ticker:
            result = collection.delete_many({'TICKER': ticker})
            print(f"🗑️ Removed {result.deleted_count} existing records for {ticker}")
        else:
            # Clear entire collection if uploading all data
            result = collection.delete_many({})
            print(f"🗑️ Cleared collection: {result.deleted_count} documents removed")
        
        # Convert DataFrame to records
        records = df.to_dict('records')
        
        # Add upload metadata to each record
        for record in records:
            record['uploaded_at'] = datetime.now()
            record['source'] = 'FA_A_processed.csv'
            
            # Convert NaN values to None for MongoDB
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        
        # Insert records to MongoDB
        if records:
            result = collection.insert_many(records)
            print(f"✅ Inserted {len(result.inserted_ids)} documents to MongoDB collection '{collection_name}'")
            
            # Create indexes for better query performance
            collection.create_index('TICKER')
            collection.create_index('DATE')
            collection.create_index([('TICKER', 1), ('DATE', 1)])
            print("✅ Created indexes on TICKER and DATE fields")
            
            # Verify the upload
            count = collection.count_documents({'TICKER': ticker} if ticker else {})
            print(f"📊 Total documents in collection: {count}")
            
            # Show sample of uploaded data
            sample = collection.find_one({'TICKER': ticker} if ticker else {})
            if sample:
                print("\n📋 Sample document:")
                print(f"  TICKER: {sample.get('TICKER')}")
                print(f"  DATE: {sample.get('DATE')}")
                print(f"  KEYCODE: {sample.get('KEYCODE')}")
                print(f"  VALUE: {sample.get('VALUE')}")
                print(f"  Columns: {list(sample.keys())}")
            
            return True
        else:
            print("❌ No records to insert")
            return False
            
    except Exception as e:
        print(f"❌ Error uploading data: {e}")
        import traceback
        traceback.print_exc()
        return False
'''

# DEPRECATED: ValuationMetrics collection is no longer used
# The application now loads valuation data directly from CSV files via data_loader.py
# Keeping this function commented for reference only
'''
def upload_valuation_data_to_mongodb(ticker=None, collection_name='ValuationMetrics'):
    """
    Upload Val_processed.csv data to MongoDB
    """
    try:
        # Load CSV file
        csv_path = os.path.join(parent_dir, 'data', 'Val_processed.csv')
        print(f"\n📂 Loading valuation data from: {csv_path}")
        
        if not os.path.exists(csv_path):
            print(f"❌ File not found: {csv_path}")
            return False
        
        # Read CSV
        df = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(df)} rows from CSV")
        
        # Filter for specific ticker if provided
        if ticker:
            df = df[df['TICKER'] == ticker].copy()
            print(f"📊 Filtered to {len(df)} rows for ticker: {ticker}")
            
            if df.empty:
                print(f"❌ No data found for ticker: {ticker}")
                return False
        
        # Connect to MongoDB
        client = init_mongodb_connection()
        if not client:
            return False
        
        # Get database and collection
        db = client['VietnamStocks']
        collection = db[collection_name]
        
        # Clear existing data for the ticker(s)
        if ticker:
            result = collection.delete_many({'TICKER': ticker})
            print(f"🗑️ Removed {result.deleted_count} existing records for {ticker}")
        
        # Convert DataFrame to records and upload
        records = df.to_dict('records')
        
        for record in records:
            record['uploaded_at'] = datetime.now()
            record['source'] = 'Val_processed.csv'
            
            # Convert NaN values to None
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        
        if records:
            result = collection.insert_many(records)
            print(f"✅ Inserted {len(result.inserted_ids)} valuation documents")
            
            # Create indexes
            collection.create_index('TICKER')
            collection.create_index('DATE')
            print("✅ Created indexes for valuation collection")
            
            return True
            
    except Exception as e:
        print(f"❌ Error uploading valuation data: {e}")
        return False
'''

def verify_upload(ticker='DXG'):
    """Verify that data was uploaded correctly"""
    # DEPRECATED: Both FinancialStatements and ValuationMetrics collections are no longer used
    print(f"\n📊 Verification Results:")
    print("  ⚠️ MongoDB collections FinancialStatements and ValuationMetrics are deprecated")
    print("  ✅ Data is now loaded directly from CSV files:")
    print("     - Financial data: FA_A_processed.csv")
    print("     - Valuation data: Val_processed.csv")
    print("     - Use core/data_loader.py for data access")

def main():
    """Main function - DEPRECATED"""
    print("=" * 60)
    print("⚠️  DEPRECATED UPLOAD UTILITY")
    print("=" * 60)
    
    print("\n📌 Important Notice:")
    print("  Both FinancialStatements and ValuationMetrics collections are deprecated!")
    print("")
    print("  The application now loads data directly from CSV files:")
    print("  - Financial data: data/FA_A_processed.csv")
    print("  - Valuation data: data/Val_processed.csv")
    print("")
    print("  Active MongoDB collections still in use:")
    print("  - RealEstateProjects")
    print("  - CompanyForecast") 
    print("  - ProjectDiscovery")
    print("  - ProjectVersions")
    print("  - Assumptions")
    print("")
    print("  To access financial/valuation data, use:")
    print("  - core/data_loader.py")
    print("")
    print("  Both deprecated collections can be safely deleted from MongoDB.")
    print("=" * 60)

if __name__ == "__main__":
    main()