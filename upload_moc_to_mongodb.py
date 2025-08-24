import pandas as pd
import numpy as np
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def parse_quarter_to_date(quarter_str):
    """Convert quarter string (e.g., '3Q19') to a date object"""
    if not quarter_str or not isinstance(quarter_str, str):
        return None
    
    try:
        # Extract quarter and year
        quarter = int(quarter_str[0])
        year = int('20' + quarter_str[2:])
        
        # Convert quarter to month (use first month of quarter)
        month = (quarter - 1) * 3 + 1
        
        return datetime(year, month, 1)
    except:
        return None

def upload_moc_data_to_mongodb():
    """Upload MoC data from CSV to MongoDB with efficient schema"""
    
    # Connect to MongoDB
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    if not connection_string:
        print("Error: MONGODB_CONNECTION_STRING not found in environment variables")
        return
    
    client = MongoClient(connection_string)
    
    # Create or get the MoCDB database
    db = client['MoCDB']
    
    # Read the CSV file
    df = pd.read_csv('data/MoC_Data.csv', index_col=0)
    df.index.name = 'Metric'
    
    print("Processing MoC data for MongoDB upload...")
    
    # 1. REAL ESTATE TRANSACTION VOLUME COLLECTION
    print("\n1. Processing Real Estate Transaction Volume...")
    trans_collection = db['transaction_volume']
    trans_collection.drop()  # Clear existing data
    
    # Filter transaction data
    trans_metrics = [
        'Lượng giao dịch căn hộ chung cư nhà ở riêng lẻ',
        'Lượng giao dịch đất nền',
        'Tổng lượng giao dịch'
    ]
    
    trans_docs = []
    for metric in trans_metrics:
        if metric in df.index:
            row = df.loc[metric]
            # Process each quarter
            for col in df.columns:
                if col != 'unit':
                    quarter_date = parse_quarter_to_date(col)
                    if quarter_date and pd.notna(row[col]):
                        try:
                            value = float(row[col])
                        except (ValueError, TypeError):
                            continue  # Skip non-numeric values
                        
                        trans_docs.append({
                            'metric': metric,
                            'metric_type': 'apartment' if 'căn hộ' in metric else 'land' if 'đất nền' in metric else 'total',
                            'quarter': col,
                            'date': quarter_date,
                            'year': quarter_date.year,
                            'quarter_num': (quarter_date.month - 1) // 3 + 1,
                            'value': value,
                            'unit': 'unit'
                        })
    
    if trans_docs:
        trans_collection.insert_many(trans_docs)
        print(f"  Inserted {len(trans_docs)} transaction volume records")
    
    # Create indexes for efficient querying
    trans_collection.create_index([('date', 1)])
    trans_collection.create_index([('metric_type', 1)])
    trans_collection.create_index([('year', 1), ('quarter_num', 1)])
    
    # 2. REAL ESTATE CREDIT OUTSTANDING COLLECTION
    print("\n2. Processing Real Estate Credit Outstanding...")
    credit_collection = db['credit_outstanding']
    credit_collection.drop()  # Clear existing data
    
    # Filter credit data
    credit_rows = df[df.index.str.contains('Dư nợ', na=False)]
    
    credit_docs = []
    for idx, row in credit_rows.iterrows():
        # Categorize credit type
        if 'khu đô thị' in idx:
            credit_type = 'urban_development'
        elif 'văn phòng' in idx:
            credit_type = 'office'
        elif 'công nghiệp' in idx:
            credit_type = 'industrial'
        elif 'du lịch' in idx:
            credit_type = 'tourism'
        elif 'khách sạn' in idx:
            credit_type = 'hotel'
        elif 'sửa chữa nhà' in idx:
            credit_type = 'construction_repair'
        elif 'quyền sử dụng đất' in idx:
            credit_type = 'land_rights'
        elif 'Tổng' in idx:
            credit_type = 'total'
        else:
            credit_type = 'other'
        
        # Process each quarter
        for col in df.columns:
            if col != 'unit':
                quarter_date = parse_quarter_to_date(col)
                if quarter_date and pd.notna(row[col]):
                    try:
                        value = float(row[col])
                    except (ValueError, TypeError):
                        continue  # Skip non-numeric values
                    
                    credit_docs.append({
                        'metric': idx,
                        'credit_type': credit_type,
                        'quarter': col,
                        'date': quarter_date,
                        'year': quarter_date.year,
                        'quarter_num': (quarter_date.month - 1) // 3 + 1,
                        'value': value,
                        'unit': 'VND_billion'
                    })
    
    if credit_docs:
        credit_collection.insert_many(credit_docs)
        print(f"  Inserted {len(credit_docs)} credit outstanding records")
    
    # Create indexes
    credit_collection.create_index([('date', 1)])
    credit_collection.create_index([('credit_type', 1)])
    credit_collection.create_index([('year', 1), ('quarter_num', 1)])
    
    # 3. REAL ESTATE INVENTORY COLLECTION
    print("\n3. Processing Real Estate Inventory...")
    inventory_collection = db['inventory']
    inventory_collection.drop()  # Clear existing data
    
    # Filter inventory data
    inventory_metrics = [
        'Chung cư',
        'Nhà ở riêng lẻ',
        'Đất nền',
        'Tổng tồn kho bất động sản'
    ]
    
    inventory_docs = []
    for metric in inventory_metrics:
        if metric in df.index:
            row = df.loc[metric]
            # Categorize inventory type
            if 'Chung cư' in metric:
                inv_type = 'apartment'
            elif 'Nhà ở riêng lẻ' in metric:
                inv_type = 'individual_house'
            elif 'Đất nền' in metric:
                inv_type = 'land'
            else:
                inv_type = 'total'
            
            # Process each quarter
            for col in df.columns:
                if col != 'unit':
                    quarter_date = parse_quarter_to_date(col)
                    if quarter_date and pd.notna(row[col]):
                        try:
                            value = float(row[col])
                        except (ValueError, TypeError):
                            continue  # Skip non-numeric values
                        
                        inventory_docs.append({
                            'metric': metric,
                            'inventory_type': inv_type,
                            'quarter': col,
                            'date': quarter_date,
                            'year': quarter_date.year,
                            'quarter_num': (quarter_date.month - 1) // 3 + 1,
                            'value': value,
                            'unit': 'unit'
                        })
    
    if inventory_docs:
        inventory_collection.insert_many(inventory_docs)
        print(f"  Inserted {len(inventory_docs)} inventory records")
    
    # Create indexes
    inventory_collection.create_index([('date', 1)])
    inventory_collection.create_index([('inventory_type', 1)])
    inventory_collection.create_index([('year', 1), ('quarter_num', 1)])
    
    # 4. INFRASTRUCTURE PROJECTS COLLECTION
    print("\n4. Processing Infrastructure Projects...")
    projects_collection = db['infrastructure_projects']
    projects_collection.drop()  # Clear existing data
    
    # Filter project data
    project_metrics = [
        'Số lượng dự án',
        'Hoàn thành',
        'Đang triển khai xây dựng',
        'Được cấp phép mới',
        'Quy mô ô nền'
    ]
    
    # Need to handle multiple "Hoàn thành" and other duplicate rows
    # Group by project status type
    project_docs = []
    
    # Process project count metrics
    for metric in project_metrics:
        matching_rows = df[df.index == metric]
        if len(matching_rows) > 0:
            # Handle first occurrence (project counts)
            row = matching_rows.iloc[0]
            
            # Determine project metric type
            if 'Số lượng' in metric:
                metric_type = 'project_count'
                status = 'total'
            elif 'Hoàn thành' in metric:
                metric_type = 'project_count'
                status = 'completed'
            elif 'Đang triển khai' in metric:
                metric_type = 'project_count'
                status = 'under_construction'
            elif 'Được cấp phép' in metric:
                metric_type = 'project_count'
                status = 'newly_licensed'
            elif 'Quy mô' in metric:
                metric_type = 'project_scale'
                status = 'total'
            else:
                continue
            
            # Process each quarter
            for col in df.columns:
                if col != 'unit':
                    quarter_date = parse_quarter_to_date(col)
                    if quarter_date and pd.notna(row[col]):
                        try:
                            value = float(row[col])
                        except (ValueError, TypeError):
                            continue  # Skip non-numeric values
                        
                        project_docs.append({
                            'metric': metric,
                            'metric_type': metric_type,
                            'status': status,
                            'category': 'project_statistics',
                            'quarter': col,
                            'date': quarter_date,
                            'year': quarter_date.year,
                            'quarter_num': (quarter_date.month - 1) // 3 + 1,
                            'value': value,
                            'unit': 'unit'
                        })
            
            # Handle second occurrence if exists (scale metrics)
            if len(matching_rows) > 1:
                row = matching_rows.iloc[1]
                
                if 'Hoàn thành' in metric:
                    status = 'completed'
                elif 'Đang triển khai' in metric:
                    status = 'under_construction'
                elif 'Được cấp phép' in metric:
                    status = 'newly_licensed'
                else:
                    status = 'unknown'
                
                # Process each quarter
                for col in df.columns:
                    if col != 'unit':
                        quarter_date = parse_quarter_to_date(col)
                        if quarter_date and pd.notna(row[col]):
                            try:
                                value = float(row[col])
                            except (ValueError, TypeError):
                                continue  # Skip non-numeric values
                            
                            project_docs.append({
                                'metric': f"{metric} (Quy mô)",
                                'metric_type': 'project_scale',
                                'status': status,
                                'category': 'scale_statistics',
                                'quarter': col,
                                'date': quarter_date,
                                'year': quarter_date.year,
                                'quarter_num': (quarter_date.month - 1) // 3 + 1,
                                'value': value,
                                'unit': 'unit'
                            })
    
    if project_docs:
        projects_collection.insert_many(project_docs)
        print(f"  Inserted {len(project_docs)} infrastructure project records")
    
    # Create indexes
    projects_collection.create_index([('date', 1)])
    projects_collection.create_index([('metric_type', 1), ('status', 1)])
    projects_collection.create_index([('year', 1), ('quarter_num', 1)])
    projects_collection.create_index([('category', 1)])
    
    print("\n✅ Data upload complete!")
    print(f"Database: MoCDB")
    print(f"Collections created:")
    print(f"  - transaction_volume: {trans_collection.count_documents({})}")
    print(f"  - credit_outstanding: {credit_collection.count_documents({})}")
    print(f"  - inventory: {inventory_collection.count_documents({})}")
    print(f"  - infrastructure_projects: {projects_collection.count_documents({})}")
    
    # Close connection
    client.close()

if __name__ == "__main__":
    upload_moc_data_to_mongodb()