#%%

import streamlit as st
import os
import pandas as pd
import numpy as np
import certifi
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv
from pathlib import Path
import sys
import json

# Load environment variables at module import
load_dotenv()

# Add parent directory to path for config imports
sys.path.append(str(Path(__file__).parent.parent))
from config.constants import MONGODB_COLLECTIONS, REAL_ESTATE_CONFIG, FINANCIAL_CONFIG


@st.cache_resource
def init_mongodb_connection():
    """Initialize MongoDB connection with graceful error handling"""
    try:
        # Load environment variables again in case they weren't loaded
        load_dotenv()
        
        # Get MongoDB connection string from .env file
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        
        if not connection_string:
            st.error("❌ MONGODB_CONNECTION_STRING not found in .env file. Please add it to your .env file.")
            return None
        
        # Create MongoDB client with SSL certificate verification and reasonable timeout settings
        client = MongoClient(
            connection_string, 
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,   # 5 second timeout
            connectTimeoutMS=5000,           # 5 second connection timeout
            socketTimeoutMS=5000             # 5 second socket timeout
        )
        
        # Test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        error_msg = str(e)
        
        # Provide more specific error messages based on the error type
        if "timed out" in error_msg.lower():
            st.error("❌ **MongoDB Connection Timeout**")
            st.warning("""
            **Possible causes:**
            1. **IP not whitelisted**: Check MongoDB Atlas Network Access settings
            2. **Network/Firewall blocking**: Corporate firewall may be blocking MongoDB ports (27017)
            3. **Internet connectivity issues**: Check your internet connection
            
            **To fix:**
            - Go to MongoDB Atlas → Network Access → Add your current IP address
            - Or add 0.0.0.0/0 to allow all IPs (less secure, only for development)
            """)
        elif "authentication failed" in error_msg.lower():
            st.error("❌ **MongoDB Authentication Failed**")
            st.warning("Check your username and password in the connection string")
        else:
            st.error(f"❌ Error connecting to MongoDB: {error_msg}")
        
        return None

def load_companies_data():
    """Load companies from MongoDB Companies collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            # Return empty DataFrame when MongoDB is not available
            return pd.DataFrame()
        
        # Get database and collection names
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['companies']
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all companies
        companies_cursor = collection.find({})
        companies_list = list(companies_cursor)
        
        if not companies_list:
            #st.write(f"🔍 DEBUG: No companies found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(companies_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df.columns:
            df = df.drop('_id', axis=1)
        
        #st.write(f"🔍 DEBUG: Loaded {len(df)} companies from MongoDB")
        return df
        
    except Exception as e:
        # Don't show error for connection issues - already handled in init_mongodb_connection
        if "timed out" not in str(e).lower():
            st.error(f"❌ Error loading companies data from MongoDB: {str(e)}")
        return pd.DataFrame()

def load_projects_data():
    """Load real estate projects from MongoDB database"""
    try:
        client = init_mongodb_connection()
        if client is None:
            # Return empty DataFrame when MongoDB is not available
            return pd.DataFrame()
        
        # Get database and collection names - using VietnamStocks database
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['real_estate_projects']
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all projects
        projects_cursor = collection.find({})
        projects_list = list(projects_cursor)
        
        if not projects_list:
            #st.write(f"🔍 DEBUG: No projects found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert string keys back to integers for certain fields
        for project in projects_list:
            # Convert relative_collection_schedule keys from strings to integers
            if 'relative_collection_schedule' in project and isinstance(project['relative_collection_schedule'], dict):
                converted = {}
                for k, v in project['relative_collection_schedule'].items():
                    try:
                        converted[int(k)] = v
                    except (ValueError, TypeError):
                        converted[k] = v  # Keep as string if conversion fails
                project['relative_collection_schedule'] = converted
            
            # Convert cash_collection_schedules keys from strings to integers
            if 'cash_collection_schedules' in project and isinstance(project['cash_collection_schedules'], dict):
                converted = {}
                for k, v in project['cash_collection_schedules'].items():
                    try:
                        # Convert outer key to int
                        k_int = int(k)
                        # Convert inner dict keys to int
                        if isinstance(v, dict):
                            v_converted = {}
                            for k2, v2 in v.items():
                                try:
                                    v_converted[int(k2)] = v2
                                except (ValueError, TypeError):
                                    v_converted[k2] = v2
                            converted[k_int] = v_converted
                        else:
                            converted[k_int] = v
                    except (ValueError, TypeError):
                        converted[k] = v  # Keep as string if conversion fails
                project['cash_collection_schedules'] = converted
        
        # Convert to DataFrame
        df_projects = pd.DataFrame(projects_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df_projects.columns:
            df_projects = df_projects.drop('_id', axis=1)
        
        #st.write(f"🔍 DEBUG: Loaded {len(df_projects)} projects from MongoDB")
        #st.write(f"🔍 DEBUG: Project columns: {list(df_projects.columns)}")
        
        # Load companies data and merge
        df_companies = load_companies_data()
        if not df_companies.empty:
            # Check for columns that might conflict and rename them
            if 'company_name' in df_projects.columns:
                df_projects = df_projects.rename(columns={'company_name': 'project_company_name'})
            
            if 'sector' in df_projects.columns:
                df_projects = df_projects.rename(columns={'sector': 'project_sector'})
            
            # Merge projects with company information on company_ticker
            df_merged = df_projects.merge(
                df_companies[['ticker', 'company_name', 'sector']], 
                left_on='company_ticker', 
                right_on='ticker', 
                how='left'
            )
            
            # If project had a company_name, use it if the merged one is missing
            if 'project_company_name' in df_merged.columns:
                df_merged['company_name'] = df_merged['company_name'].fillna(df_merged['project_company_name'])
                df_merged = df_merged.drop('project_company_name', axis=1)
            
            # If project had a sector, use it if the merged one is missing
            if 'project_sector' in df_merged.columns:
                df_merged['sector'] = df_merged['sector'].fillna(df_merged['project_sector'])
                df_merged = df_merged.drop('project_sector', axis=1)
            
            # Drop the duplicate ticker column
            if 'ticker' in df_merged.columns:
                df_merged = df_merged.drop('ticker', axis=1)
            
            # Handle date conversion for last_updated if it exists
            if 'last_updated' in df_merged.columns:
                df_merged['last_updated'] = pd.to_datetime(df_merged['last_updated'], errors='coerce')
            
            #st.write(f"🔍 DEBUG: Merged dataframe shape: {df_merged.shape}")
            return df_merged
        else:
            # Handle date conversion for last_updated if it exists
            if 'last_updated' in df_projects.columns:
                df_projects['last_updated'] = pd.to_datetime(df_projects['last_updated'], errors='coerce')
            return df_projects
        
    except Exception as e:
        st.error(f"❌ Error loading projects data from MongoDB: {str(e)}")
        return pd.DataFrame()

def get_companies_list():
    """Get formatted list of companies for selectbox"""
    df_companies = load_companies_data()
    if df_companies.empty:
        return []
    
    # Format as "TICKER - Company Name"
    companies_list = []
    for _, row in df_companies.iterrows():
        ticker = row.get('ticker', '')
        name = row.get('company_name', '')
        if ticker and name:
            companies_list.append(f"{ticker} - {name}")
    
    return sorted(companies_list)

def load_real_estate_companies_from_mongo_db(include_names: bool = True, filter_sector: str | None = None) -> list[str]:
    """
    Load tickers (and optionally names) from MongoDB 'VietnamStocks' → 'Companies'.
    Returns a sorted list suitable for a selectbox: either "TICKER - Company Name" or just "TICKER".

    Args:
        include_names: If True, include company_name when available.
        filter_sector: Optional sector filter (e.g., 'Real Estate'). If None, no filtering.

    Notes:
        Expects documents with at least fields: 'ticker' and (optionally) 'company_name'.
    """
    try:
        client = init_mongodb_connection()
        if client is None:
            return []

        db = client.get_database('VietnamStocks')
        collection = db.get_collection(MONGODB_COLLECTIONS['companies'])

        query = {}
        if filter_sector:
            query['sector'] = filter_sector

        # Only fetch required fields
        cursor = collection.find(query, {"ticker": 1, "company_name": 1, "_id": 0})
        companies = []
        for doc in cursor:
            ticker = doc.get('ticker')
            name = doc.get('company_name')
            if not ticker:
                continue
            if include_names and name:
                companies.append(f"{ticker} - {name}")
            else:
                companies.append(ticker)

        return sorted(companies)
    except Exception as e:
        # Avoid raising; show error and return empty list
        st.error(f"❌ Error loading companies from MongoDB: {str(e)}")
        return []

def get_projects_for_company(company_ticker):
    """Get projects for a specific company"""
    df_projects = load_projects_data()
    if df_projects.empty:
        return []
    
    # Filter projects by company ticker
    company_projects = df_projects[df_projects['company_ticker'] == company_ticker]
    if company_projects.empty:
        return []
    
    return sorted(company_projects['project_name'].tolist())


def get_project_data(company_ticker, project_name):
    """Get specific project data"""
    df_projects = load_projects_data()
    if df_projects.empty:
        return None
    
    # Find the specific project
    project_data = df_projects[
        (df_projects['company_ticker'] == company_ticker) & 
        (df_projects['project_name'] == project_name)
    ]
    
    if project_data.empty:
        return None
    
    return project_data.iloc[0].to_dict()

def save_assumptions_to_mongodb(company_ticker, assumptions_data):
    """Save business segment assumptions to MongoDB CompanyForecast collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Use VietnamStocks database and CompanyForecast collection
        db = client['VietnamStocks']
        collection = db['CompanyForecast']
        
        # Check if document exists for this ticker
        existing = collection.find_one({"ticker": company_ticker})
        
        if existing:
            # Update existing document - add assumptions to it
            result = collection.update_one(
                {"ticker": company_ticker},
                {
                    "$set": {
                        "assumptions": assumptions_data,
                        "assumptions_updated": datetime.datetime.now()
                    }
                }
            )
            if result.modified_count > 0:
                return {"success": True, "message": "Assumptions updated successfully"}
        else:
            # Create new document with assumptions
            document = {
                "ticker": company_ticker,
                "assumptions": assumptions_data,
                "assumptions_updated": datetime.datetime.now(),
                "last_updated": datetime.datetime.now(),
                "forecast_years": [],
                "forecast_data": {}
            }
            result = collection.insert_one(document)
            if result.inserted_id:
                return {"success": True, "message": "Assumptions saved successfully"}
        
        return {"success": False, "message": "No changes made"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

def load_assumptions_from_mongodb(company_ticker):
    """Load business segment assumptions from MongoDB CompanyForecast collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return None
        
        # Use VietnamStocks database and CompanyForecast collection
        db = client['VietnamStocks']
        collection = db['CompanyForecast']
        
        # Find document for this ticker
        document = collection.find_one({"ticker": company_ticker})
        
        if document and "assumptions" in document:
            return document.get("assumptions", [])
        
        return None
        
    except Exception as e:
        st.error(f"Error loading assumptions: {str(e)}")
        return None



def save_project_to_mongodb(project_data, project_name, rnav_value=None):
    """Save project data to MongoDB"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Get database and collection
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['real_estate_projects']
        
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Start with all fields from project_data to ensure nothing is missed
        document = project_data.copy()
        
        # List of fields that should NOT be saved to database
        fields_to_remove = [
            'is_new_project',
            'revenue_schedule',
            'construction_schedule', 
            'land_schedule',
            'sga_schedule',
            'interest_schedule',
            'custom_presales_schedule',
            'custom_revenue_schedule',
            'company_name_x',
            'company_name_y',
            'sector_x',
            'sector_y',
            # Remove any pandas merge suffixes
            '_x', '_y',
            # Remove temporary UI state fields
            'show_ai_research',
            'pending_ai_research',
            'ai_suggestions',
            # Add any other temporary or calculated fields that might contain suffixes
        ]
        
        # Also remove any fields ending with _x or _y (merge artifacts)
        for key in list(document.keys()):
            if key.endswith('_x') or key.endswith('_y'):
                # Try to keep the base field without suffix if it doesn't exist
                base_key = key[:-2]
                if base_key not in document and key.endswith('_x'):
                    document[base_key] = document[key]
                del document[key]
        
        # Remove unwanted fields
        for field in fields_to_remove:
            if field in document:
                del document[field]
        
        # Convert integer keys to strings for MongoDB compatibility
        for field in ['relative_collection_schedule', 'cash_collection_schedules']:
            if field in document and isinstance(document[field], dict):
                # Convert integer keys to strings
                converted = {}
                for k, v in document[field].items():
                    # If value is also a dict with integer keys, convert those too
                    if isinstance(v, dict):
                        v_converted = {str(k2): v2 for k2, v2 in v.items()}
                        converted[str(k)] = v_converted
                    else:
                        converted[str(k)] = v
                document[field] = converted
        
        # Clean up NaN values - convert to None or appropriate defaults
        for key, value in list(document.items()):
            if isinstance(value, float):
                if pd.isna(value) or np.isinf(value):
                    # Remove NaN/inf fields entirely or set to None/0 based on field type
                    if key in ['debt_financing_pct']:
                        document[key] = 0.3  # Default 30% debt financing
                    elif key == 'total_debt':
                        # Calculate reasonable total_debt if it's NaN or unreasonably large
                        if pd.isna(value) or value > 1e15:  # More than 1 quadrillion is likely an error
                            total_construction = document.get('total_construction_cost', 0)
                            debt_pct = document.get('debt_financing_pct', 0.3)
                            document[key] = total_construction * debt_pct
                    else:
                        del document[key]  # Remove NaN fields
            elif isinstance(value, str) and value in ['NaN', 'nan', 'None']:
                del document[key]  # Remove string 'NaN' fields
        
        # Ensure required fields are present with defaults
        document.update({
            "project_name": project_name,
            "company_ticker": project_data.get('company_ticker', 'MANUAL'),
            "company_name": project_data.get('company_name', 'Manual Entry'),
            "location": project_data.get('location', ''),
            "google_maps_location": project_data.get('google_maps_location', ''),
            "latitude": project_data.get('latitude', None),
            "longitude": project_data.get('longitude', None),
            "project_ownership": project_data.get('project_ownership', 1.0),
            "total_units": project_data.get('total_units', 0),
            "net_sellable_area": project_data.get('net_sellable_area', project_data.get('total_units', 0) * project_data.get('average_unit_size', 0)),
            "average_unit_size": project_data.get('average_unit_size', 0),
            "average_selling_price": project_data.get('average_selling_price', 0),
            "price_increment_factor": project_data.get('price_increment_factor', 0.0),
            "gross_floor_area": project_data.get('gross_floor_area', 0),
            "land_area": project_data.get('land_area', 0),
            "construction_cost_per_sqm": project_data.get('construction_cost_per_sqm', 0),
            "land_cost_per_sqm": project_data.get('land_cost_per_sqm', 0),
            "construction_start_year": project_data.get('construction_start_year', 2025),
            "sale_start_year": project_data.get('sale_start_year', 2025),
            "land_payment_year": project_data.get('land_payment_year', 2025),
            "construction_years": project_data.get('construction_years', 3),
            "sales_years": project_data.get('sales_years', 3),
            "revenue_booking_start_year": project_data.get('revenue_booking_start_year', 2025),
            "project_completion_year": project_data.get('project_completion_year', 2028),
            "sga_percentage": project_data.get('sga_percentage', FINANCIAL_CONFIG['default_sga']),
            "wacc_rate": project_data.get('wacc_rate', FINANCIAL_CONFIG['default_wacc']),
            "cost_of_debt": project_data.get('cost_of_debt', 0.08),
            "rnav_value": float(rnav_value) if rnav_value is not None else None,
            # Financial fields
            "total_revenue": project_data.get('total_revenue', 0),
            "total_pat": project_data.get('total_pat', 0),
            "total_pbt": project_data.get('total_pbt', 0),
            "total_construction_cost": project_data.get('total_construction_cost', 0),
            "total_land_cost": project_data.get('total_land_cost', 0),
            "total_sga_cost": project_data.get('total_sga_cost', 0),
            "total_debt": project_data.get('total_debt', 0),
            "debt_financing_pct": project_data.get('debt_financing_pct', 0.3),
            "project_irr": project_data.get('project_irr', None),  # IRR calculated from cash flows
            # Distribution percentages
            "revenue_distribution": project_data.get('revenue_distribution', {}),
            "presales_distribution": project_data.get('presales_distribution', {}),
            # P&L schedule (legacy - replaced by comprehensive_financial_statements)
            "pnl_schedule": project_data.get('pnl_schedule', {}),
            # Comprehensive Financial Statements - includes Balance Sheet, P&L, and Cash Flow
            "comprehensive_financial_statements": project_data.get('comprehensive_financial_statements', {}),
            "financial_statements_summary": project_data.get('financial_statements_summary', {}),
            # Timestamps
            "last_updated": datetime.datetime.now(),
            "created_date": datetime.datetime.now()
        })
        
        # Check if project exists
        existing = collection.find_one({
            "project_name": project_name,
            "company_ticker": document["company_ticker"]
        })
        
        # Log if financial statements are being saved
        if document.get("comprehensive_financial_statements"):
            years_count = len(document["comprehensive_financial_statements"])
            # Debug: Print what we're actually saving
            print(f"DEBUG: Saving comprehensive_financial_statements with {years_count} years")
            print(f"DEBUG: Years in data: {list(document['comprehensive_financial_statements'].keys())}")
            # Check if summary exists too
            if document.get("financial_statements_summary"):
                print(f"DEBUG: financial_statements_summary also included with {len(document['financial_statements_summary'])} fields")
            message_suffix = f" (including {years_count} years of financial statements)"
        else:
            print("DEBUG: No comprehensive_financial_statements found in document")
            message_suffix = ""
        
        if existing:
            # Update existing document but preserve created_date and location if not provided
            document["created_date"] = existing.get("created_date", datetime.datetime.now())
            # Preserve existing location if new one is empty
            if not document["location"] and existing.get("location"):
                document["location"] = existing["location"]
            result = collection.replace_one(
                {"_id": existing["_id"]}, 
                document
            )
            action = "updated"
            message = f"✅ Project '{project_name}' updated successfully in MongoDB{message_suffix}"
        else:
            # Insert new document
            result = collection.insert_one(document)
            action = "saved"
            message = f"✅ Project '{project_name}' saved successfully to MongoDB{message_suffix}"
        
        return {"success": True, "message": message, "action": action}
        
    except Exception as e:
        return {"success": False, "message": f"Error saving to MongoDB: {str(e)}"}

def delete_project_from_mongodb(company_ticker, project_name):
    """Delete a project from MongoDB database"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Get database and collection
        db_name = 'VietnamStocks'
        collection_name = 'RealEstateProjects'
        
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Check if project exists before deletion
        existing_project = collection.find_one({
            "project_name": project_name,
            "company_ticker": company_ticker
        })
        
        if not existing_project:
            return {
                "success": False, 
                "message": f"Project '{project_name}' not found for company '{company_ticker}'"
            }
        
        # Delete the project
        result = collection.delete_one({
            "project_name": project_name,
            "company_ticker": company_ticker
        })
        
        if result.deleted_count == 1:
            return {
                "success": True, 
                "message": f"Project '{project_name}' successfully deleted from company '{company_ticker}'"
            }
        else:
            return {
                "success": False, 
                "message": f"Failed to delete project '{project_name}' - no documents were deleted"
            }
        
    except Exception as e:
        return {
            "success": False, 
            "message": f"Error deleting project from MongoDB: {str(e)}"
        }


# New MongoDB Helper Class for AI Agent functionality
class MongoDBHelper:
    """MongoDB helper class for AI Agent project discovery features"""
    
    def __init__(self):
        """Initialize MongoDB connection"""
        self.client = init_mongodb_connection()
        if self.client:
            self.db = self.client.get_database('VietnamStocks')
            self.projects_collection = self.db.get_collection('RealEstateProjects')
            self.discovery_collection = self.db.get_collection('ProjectDiscovery')
            # Quarterly earnings collections
            self.quarterly_documents_collection = self.db.get_collection('QuarterlyEarningsDocuments')
            self.quarterly_data_collection = self.db.get_collection('QuarterlyEarningsData')
            self.quarterly_summaries_collection = self.db.get_collection('QuarterlySummaries')
            
            # Initialize quarterly collections with schema validation and indexes
            self._setup_quarterly_collections()
        else:
            self.db = None
            self.projects_collection = None
            self.discovery_collection = None
            self.quarterly_documents_collection = None
            self.quarterly_data_collection = None
            self.quarterly_summaries_collection = None
    
    def _setup_quarterly_collections(self):
        """Setup quarterly earnings collections with proper indexes and schema validation"""
        try:
            # Load the JSON schema for validation
            schema_path = Path(__file__).parent / "quarterly_analysis.json"
            if schema_path.exists():
                import json
                with open(schema_path, 'r', encoding='utf-8') as f:
                    json_schema = json.load(f)
                
                # Create indexes for efficient querying
                self._ensure_quarterly_indexes()
                
                # Optional: You can add MongoDB schema validation here if needed
                # For now, we'll rely on application-level validation
                st.info("✅ Quarterly collections initialized with proper indexing")
            else:
                st.warning("⚠️ JSON schema file not found - collections initialized without validation")
        except Exception as e:
            st.warning(f"⚠️ Error setting up quarterly collections: {e}")
    
    def _ensure_quarterly_indexes(self):
        """Ensure proper indexes exist on quarterly collections"""
        try:
            # QuarterlyEarningsData collection indexes
            # REMOVED unique=True to allow multiple documents per ticker/quarter (one per source)
            self.quarterly_data_collection.create_index([("ticker", 1), ("quarter", 1)])
            self.quarterly_data_collection.create_index([("ticker", 1), ("quarter", 1), ("source.file_type", 1)])
            self.quarterly_data_collection.create_index([("ticker", 1), ("year", 1), ("quarter_num", 1)])
            self.quarterly_data_collection.create_index([("last_updated", -1)])
            self.quarterly_data_collection.create_index([("document_id", 1)])
            
            # QuarterlyEarningsDocuments collection indexes  
            self.quarterly_documents_collection.create_index([("ticker", 1), ("quarter", 1)])
            self.quarterly_documents_collection.create_index([("processing_status", 1)])
            self.quarterly_documents_collection.create_index([("upload_date", -1)])
            
            # QuarterlySummaries collection indexes
            self.quarterly_summaries_collection.create_index([("ticker", 1), ("quarter", 1)], unique=True)
            self.quarterly_summaries_collection.create_index([("generated_date", -1)])
            
        except Exception as e:
            # Indexes may already exist, that's okay
            pass
    
    def get_real_estate_projects(self, ticker: str) -> list:
        """Get all real estate projects for a company"""
        if self.projects_collection is None:
            return []
        
        try:
            projects = list(self.projects_collection.find({"company_ticker": ticker}))
            # Remove MongoDB _id field
            for project in projects:
                if '_id' in project:
                    del project['_id']
            return projects
        except Exception as e:
            st.error(f"Error loading projects: {str(e)}")
            return []
    
    def save_real_estate_project(self, project_data: dict) -> bool:
        """Save a single real estate project"""
        if self.projects_collection is None:
            return False
        
        try:
            # Add timestamps
            project_data['last_updated'] = datetime.datetime.now()
            if 'created_date' not in project_data:
                project_data['created_date'] = datetime.datetime.now()
            
            # Insert project
            self.projects_collection.insert_one(project_data)
            return True
        except Exception as e:
            st.error(f"Error saving project: {str(e)}")
            return False
    
    def upsert_real_estate_project(self, project_data: dict) -> bool:
        """Update project if exists, insert if not"""
        if self.projects_collection is None:
            return False
        
        try:
            # Prepare filter
            filter_query = {
                "project_name": project_data.get('project_name'),
                "company_ticker": project_data.get('ticker')
            }
            
            # Add timestamps
            project_data['last_updated'] = datetime.datetime.now()
            
            # Check if exists
            existing = self.projects_collection.find_one(filter_query)
            
            if existing:
                # Preserve created_date
                project_data['created_date'] = existing.get('created_date', datetime.datetime.now())
                # Update
                self.projects_collection.replace_one(filter_query, project_data)
            else:
                # Insert new
                project_data['created_date'] = datetime.datetime.now()
                self.projects_collection.insert_one(project_data)
            
            return True
        except Exception as e:
            st.error(f"Error upserting project: {str(e)}")
            return False
    
    def delete_real_estate_projects(self, ticker: str) -> bool:
        """Delete all projects for a company"""
        if self.projects_collection is None:
            return False
        
        try:
            result = self.projects_collection.delete_many({"company_ticker": ticker})
            st.info(f"Deleted {result.deleted_count} projects for {ticker}")
            return True
        except Exception as e:
            st.error(f"Error deleting projects: {str(e)}")
            return False
    
    def save_discovery_session(self, session_data: dict) -> bool:
        """Save AI discovery session data for audit trail"""
        if self.discovery_collection is None:
            return False
        
        try:
            session_data['timestamp'] = datetime.datetime.now()
            self.discovery_collection.insert_one(session_data)
            return True
        except Exception as e:
            st.error(f"Error saving discovery session: {str(e)}")
            return False
    
    def get_discovery_history(self, ticker: str, limit: int = 10) -> list:
        """Get discovery session history for a company"""
        if self.discovery_collection is None:
            return []
        
        try:
            sessions = list(self.discovery_collection.find(
                {"company_ticker": ticker}
            ).sort("timestamp", -1).limit(limit))
            
            # Remove MongoDB _id field
            for session in sessions:
                if '_id' in session:
                    del session['_id']
            
            return sessions
        except Exception as e:
            st.error(f"Error loading discovery history: {str(e)}")
            return []
    
    def save_project_version(self, project_data: dict, version_note: str = "") -> bool:
        """Save a versioned copy of project data for change tracking"""
        if self.db is None:
            return False
        
        try:
            # Get or create versions collection
            versions_collection = self.db.get_collection('ProjectVersions')
            
            # Create version document
            version_doc = {
                "project_name": project_data.get('project_name'),
                "company_ticker": project_data.get('ticker'),
                "version_date": datetime.datetime.now(),
                "version_note": version_note,
                "project_data": project_data
            }
            
            versions_collection.insert_one(version_doc)
            return True
        except Exception as e:
            st.error(f"Error saving project version: {str(e)}")
            return False
    
    def get_project_versions(self, project_name: str, ticker: str) -> list:
        """Get version history for a project"""
        if self.db is None:
            return []
        
        try:
            versions_collection = self.db.get_collection('ProjectVersions')
            versions = list(versions_collection.find({
                "project_name": project_name,
                "company_ticker": ticker
            }).sort("version_date", -1))
            
            # Remove MongoDB _id field
            for version in versions:
                if '_id' in version:
                    del version['_id']
            
            return versions
        except Exception as e:
            st.error(f"Error loading project versions: {str(e)}")
            return []
    
    # ========== Quarterly Earnings Methods ==========
    
    def save_quarterly_document(self, document_metadata: dict) -> str:
        """Save quarterly earnings document metadata"""
        if self.quarterly_documents_collection is None:
            return None
        
        try:
            result = self.quarterly_documents_collection.insert_one(document_metadata)
            return str(result.inserted_id)
        except Exception as e:
            st.error(f"Error saving document metadata: {str(e)}")
            return None
    
    def update_quarterly_document_status(self, document_id: str, status: str, 
                                        extraction_id: str = None, 
                                        error_message: str = None) -> bool:
        """Update document processing status"""
        if self.quarterly_documents_collection is None:
            return False
        
        try:
            from bson import ObjectId
            update_data = {
                "processing_status": status,
                "processing_date": datetime.datetime.now()
            }
            if extraction_id:
                update_data["extraction_id"] = extraction_id
            if error_message:
                update_data["error_message"] = error_message
            
            self.quarterly_documents_collection.update_one(
                {"_id": ObjectId(document_id)},
                {"$set": update_data}
            )
            return True
        except Exception as e:
            st.error(f"Error updating document status: {str(e)}")
            return False
    
    def get_quarterly_documents(self, ticker: str, quarter: str) -> list:
        """Get all documents for a specific quarter"""
        if self.quarterly_documents_collection is None:
            return []
        
        try:
            documents = list(self.quarterly_documents_collection.find({
                "ticker": ticker.upper(),
                "quarter": quarter.upper()
            }).sort("upload_date", -1))
            
            # Convert ObjectId to string
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            return documents
        except Exception as e:
            st.error(f"Error loading documents: {str(e)}")
            return []
    
    def get_quarterly_document_by_id(self, document_id: str) -> dict:
        """Get document by ID"""
        if self.quarterly_documents_collection is None:
            return None
        
        try:
            from bson import ObjectId
            doc = self.quarterly_documents_collection.find_one({"_id": ObjectId(document_id)})
            if doc and '_id' in doc:
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            st.error(f"Error loading document: {str(e)}")
            return None
    
    def delete_quarterly_document(self, document_id: str) -> bool:
        """Delete a document"""
        if self.quarterly_documents_collection is None:
            return False
        
        try:
            from bson import ObjectId
            self.quarterly_documents_collection.delete_one({"_id": ObjectId(document_id)})
            return True
        except Exception as e:
            st.error(f"Error deleting document: {str(e)}")
            return False
    
    def save_quarterly_earnings_data(self, earnings_data: dict) -> str:
        """Save quarterly earnings data (creates new document for each source)"""
        if self.quarterly_data_collection is None:
            return None
        
        try:
            # Insert new document (each uploaded file gets its own document)
            result = self.quarterly_data_collection.insert_one(earnings_data)
            return str(result.inserted_id)
        except Exception as e:
            st.error(f"Error saving earnings data: {str(e)}")
            return None
    
    def get_quarterly_earnings_data(self, ticker: str, quarter: str) -> list:
        """Get all earnings data for a specific quarter"""
        if self.quarterly_data_collection is None:
            return []
        
        try:
            # Return as list even though typically one document per quarter
            data = list(self.quarterly_data_collection.find({
                "ticker": ticker.upper(),
                "quarter": quarter.upper()
            }))
            
            # Remove _id field
            for doc in data:
                if '_id' in doc:
                    del doc['_id']
            
            return data
        except Exception as e:
            st.error(f"Error loading earnings data: {str(e)}")
            return []
    
    def save_quarterly_summary(self, summary_data: dict) -> str:
        """Save quarterly summary report"""
        if self.quarterly_summaries_collection is None:
            return None
        
        try:
            # Upsert based on ticker and quarter
            result = self.quarterly_summaries_collection.update_one(
                {
                    "ticker": summary_data.get("ticker"),
                    "quarter": summary_data.get("quarter")
                },
                {"$set": summary_data},
                upsert=True
            )
            
            if result.upserted_id:
                return str(result.upserted_id)
            else:
                doc = self.quarterly_summaries_collection.find_one({
                    "ticker": summary_data.get("ticker"),
                    "quarter": summary_data.get("quarter")
                })
                return str(doc['_id']) if doc else None
        except Exception as e:
            st.error(f"Error saving summary: {str(e)}")
            return None
    
    def get_quarterly_summary(self, ticker: str, quarter: str) -> dict:
        """Get quarterly summary report"""
        if self.quarterly_summaries_collection is None:
            return None
        
        try:
            summary = self.quarterly_summaries_collection.find_one({
                "ticker": ticker.upper(),
                "quarter": quarter.upper()
            })
            
            if summary and '_id' in summary:
                del summary['_id']
            
            return summary
        except Exception as e:
            st.error(f"Error loading summary: {str(e)}")
            return None
    
    def invalidate_quarterly_summary(self, ticker: str, quarter: str) -> bool:
        """Invalidate cached summary (mark for regeneration)"""
        if self.quarterly_summaries_collection is None:
            return False
        
        try:
            self.quarterly_summaries_collection.update_one(
                {
                    "ticker": ticker.upper(),
                    "quarter": quarter.upper()
                },
                {"$set": {"cache_valid": False}}
            )
            return True
        except Exception as e:
            return False
    
    def get_company_quarters(self, ticker: str) -> list:
        """Get list of quarters with data for a company"""
        if self.quarterly_data_collection is None:
            return []
        
        try:
            # Get distinct quarters
            quarters = self.quarterly_data_collection.distinct(
                "quarter",
                {"ticker": ticker.upper()}
            )
            return sorted(quarters, reverse=True)
        except Exception as e:
            st.error(f"Error loading quarters: {str(e)}")
            return []


def save_company_forecast(ticker, forecast_data, valuation_data=None):
    """
    Save company P&L forecast and valuation to MongoDB CompanyForecast collection
    
    Args:
        ticker (str): Company ticker symbol
        forecast_data (dict): Dictionary with year as key and P&L data as value
        valuation_data (dict): Optional valuation data including RNAV and multiples
                             Example: {
                                 '2025': {
                                     'real_estate_revenue': 100,
                                     'other_business_revenue': 200,
                                     'net_revenue': 300,
                                     'real_estate_cogs': -50,
                                     'other_business_cogs': -100,
                                     'total_cogs': -150,
                                     'gross_profit': 150,
                                     'sga': -30,
                                     'ebitda': 120,
                                     'interest_expense': -10,
                                     'pbt': 110,
                                     'tax': -22,
                                     'pat': 88
                                 },
                                 '2026': {...}
                             }
    
    Returns:
        dict: Success status and message
    """
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Get database and collection
        db = client['VietnamStocks']
        collection = db['CompanyForecast']
        
        # Prepare document
        document = {
            "ticker": ticker,
            "last_updated": datetime.datetime.now(),
            "forecast_years": list(forecast_data.keys()),
            "forecast_data": forecast_data
        }
        
        # Add valuation data if provided
        if valuation_data:
            document["valuation_data"] = valuation_data
        
        # Upsert - update if exists, insert if not
        result = collection.update_one(
            {"ticker": ticker},
            {"$set": document},
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            if valuation_data:
                return {"success": True, "message": f"Forecast and valuation saved successfully for {ticker}"}
            else:
                return {"success": True, "message": f"Forecast saved successfully for {ticker}"}
        else:
            return {"success": False, "message": "No changes made"}
            
    except Exception as e:
        return {"success": False, "message": f"Error saving forecast: {str(e)}"}

def load_company_forecast(ticker):
    """
    Load company P&L forecast from MongoDB CompanyForecast collection
    
    Args:
        ticker (str): Company ticker symbol
    
    Returns:
        dict: Full forecast document or empty dict if not found
    """
    try:
        client = init_mongodb_connection()
        if client is None:
            return {}
        
        # Get database and collection
        db = client['VietnamStocks']
        collection = db['CompanyForecast']
        
        # Query for specific ticker
        forecast_doc = collection.find_one({"ticker": ticker})
        
        if forecast_doc:
            # Return the full document to allow access to nested structure
            return forecast_doc
        else:
            return {}
            
    except Exception as e:
        st.error(f"Error loading forecast for {ticker}: {str(e)}")
        return {}

# %%
