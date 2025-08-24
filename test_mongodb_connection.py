import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_moc_database():
    """Test MongoDB connection and verify data"""
    
    # Connect to MongoDB
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    if not connection_string:
        print("❌ MONGODB_CONNECTION_STRING not found in environment variables")
        return
    
    try:
        client = MongoClient(connection_string)
        db = client['MoCDB']
        
        print("✅ Connected to MongoDB successfully!")
        print(f"\n📊 Database: MoCDB")
        print("=" * 50)
        
        # Test each collection
        collections = ['transaction_volume', 'credit_outstanding', 'inventory', 'infrastructure_projects']
        
        for coll_name in collections:
            collection = db[coll_name]
            count = collection.count_documents({})
            
            print(f"\n📁 Collection: {coll_name}")
            print(f"   Total documents: {count}")
            
            # Get sample document
            sample = collection.find_one()
            if sample:
                print(f"   Sample document fields: {list(sample.keys())}")
                
                # Get unique values for key fields
                if coll_name == 'transaction_volume':
                    unique_types = collection.distinct('metric_type')
                    print(f"   Metric types: {unique_types}")
                    
                elif coll_name == 'credit_outstanding':
                    unique_types = collection.distinct('credit_type')
                    print(f"   Credit types: {unique_types}")
                    
                elif coll_name == 'inventory':
                    unique_types = collection.distinct('inventory_type')
                    print(f"   Inventory types: {unique_types}")
                    
                elif coll_name == 'infrastructure_projects':
                    unique_types = collection.distinct('metric_type')
                    unique_status = collection.distinct('status')
                    print(f"   Metric types: {unique_types}")
                    print(f"   Status types: {unique_status}")
                
                # Get date range
                pipeline = [
                    {"$group": {
                        "_id": None,
                        "min_date": {"$min": "$date"},
                        "max_date": {"$max": "$date"},
                        "quarters": {"$addToSet": "$quarter"}
                    }}
                ]
                
                result = list(collection.aggregate(pipeline))
                if result:
                    date_info = result[0]
                    print(f"   Date range: {date_info['min_date']} to {date_info['max_date']}")
                    print(f"   Total quarters: {len(date_info['quarters'])}")
        
        print("\n" + "=" * 50)
        print("✅ All collections verified successfully!")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {str(e)}")

if __name__ == "__main__":
    test_moc_database()