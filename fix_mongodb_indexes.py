"""
Script to fix MongoDB indexes for QuarterlyEarningsData collection
Run this once to remove the unique constraint and allow multiple documents per ticker/quarter
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def fix_quarterly_earnings_indexes():
    """Remove unique index and create proper indexes for separate documents design"""
    
    # Connect to MongoDB
    connection_string = os.getenv("MONGODB_CONNECTION_STRING")
    if not connection_string:
        print("❌ Error: MONGODB_CONNECTION_STRING not found in environment")
        return
    
    try:
        client = MongoClient(connection_string)
        db = client.get_database('VietnamStocks')
        collection = db.get_collection('QuarterlyEarningsData')
        
        print("📊 Current indexes:")
        for index in collection.list_indexes():
            print(f"  - {index['name']}: {index.get('key', {})}")
            if index.get('unique'):
                print(f"    ⚠️  UNIQUE constraint found!")
        
        print("\n🗑️  Dropping old unique index...")
        try:
            # Drop the old unique index on (ticker, quarter)
            collection.drop_index("ticker_1_quarter_1")
            print("✅ Dropped ticker_1_quarter_1 index")
        except Exception as e:
            print(f"ℹ️  Index may not exist or already dropped: {e}")
        
        print("\n🔧 Creating new indexes (without unique constraint)...")
        
        # Create new indexes (without unique constraint)
        collection.create_index([("ticker", 1), ("quarter", 1)])
        print("✅ Created: (ticker, quarter)")
        
        collection.create_index([("ticker", 1), ("quarter", 1), ("source.file_type", 1)])
        print("✅ Created: (ticker, quarter, source.file_type)")
        
        collection.create_index([("ticker", 1), ("year", 1), ("quarter_num", 1)])
        print("✅ Created: (ticker, year, quarter_num)")
        
        collection.create_index([("last_updated", -1)])
        print("✅ Created: (last_updated)")
        
        collection.create_index([("document_id", 1)])
        print("✅ Created: (document_id)")
        
        print("\n📊 New indexes:")
        for index in collection.list_indexes():
            print(f"  - {index['name']}: {index.get('key', {})}")
            if index.get('unique'):
                print(f"    ⚠️  WARNING: Still has UNIQUE constraint!")
        
        print("\n✅ MongoDB indexes fixed successfully!")
        print("👉 You can now upload multiple documents for the same ticker/quarter")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Index Fix for QuarterlyEarningsData Collection")
    print("=" * 60)
    print()
    fix_quarterly_earnings_indexes()


