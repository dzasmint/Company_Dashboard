"""
AI Market Data Tools
Extracted from enhanced_ai_assistant.py
Contains market data analysis tools for MoC (Ministry of Construction) data
"""

from typing import Dict, List


def register_market_tools(tool_system):
    """Register market analysis tools (MoC data) with the tool system
    
    Args:
        tool_system: The EnhancedAIToolSystem instance to register tools with
    """
    
    @tool_system.tool(
        name="get_transaction_volumes",
        description="Get real estate transaction volumes from MoC data (quarterly)",
        parameters={
            "metric_type": {
                "type": "string",
                "enum": ["apartment", "land", "total"],
                "description": "Type of transaction",
                "required": False
            },
            "quarters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Quarters to retrieve (formats: '1Q24', '2Q23' or '2024-Q1', '2023-Q2')",
                "required": False
            },
            "years": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Years to filter (e.g., [2023, 2024])",
                "required": False
            },
            "last_n_quarters": {
                "type": "integer",
                "description": "Get last N quarters of data",
                "required": False
            }
        }
    )
    def get_transaction_volumes(metric_type: str = None, quarters: List[str] = None,
                               years: List[int] = None, last_n_quarters: int = None) -> Dict:
        """Get transaction volume data with enhanced quarterly extraction"""
        
        if tool_system.moc_db is None:
            # Fallback to CSV
            df = tool_system._load_moc_data_csv()
            if not df.empty:
                # Process CSV data
                return {
                    "data": df.head(20).to_dict('records'),
                    "source": "csv",
                    "status": "success"
                }
            return {"error": "MoC data not available", "status": "failed"}
        
        collection = tool_system.moc_db['transaction_volume']
        
        # Build query
        query = {}
        if metric_type:
            query['metric_type'] = metric_type
        
        # Handle different quarter formats
        if quarters:
            # Convert formats like '2024-Q1' to '1Q24'
            converted_quarters = []
            for q in quarters:
                if '-Q' in q:
                    # Format: 2024-Q1 -> 1Q24
                    year, quarter = q.split('-Q')
                    converted_q = f"{quarter}Q{year[-2:]}"
                    converted_quarters.append(converted_q)
                else:
                    # Already in format like 1Q24
                    converted_quarters.append(q)
            query['quarter'] = {"$in": converted_quarters}
        
        # Filter by years if specified
        if years:
            query['year'] = {"$in": years}
        
        # Get all data first for last_n_quarters processing
        if last_n_quarters:
            # Get all quarters sorted by date
            all_quarters = collection.distinct('quarter')
            all_quarters_sorted = sorted(all_quarters, 
                                        key=lambda x: (int('20' + x[2:]), int(x[0])))
            last_quarters = all_quarters_sorted[-last_n_quarters:]
            if 'quarter' in query:
                # Combine with existing quarter filter
                existing = query['quarter'].get('$in', [])
                query['quarter'] = {"$in": list(set(existing + last_quarters))}
            else:
                query['quarter'] = {"$in": last_quarters}
        
        # Execute query
        cursor = collection.find(query, {"_id": 0}).sort("date", 1)
        data = list(cursor)
        
        # Enhance data with formatted quarter and QoQ growth
        if data:
            for i, record in enumerate(data):
                # Add formatted quarter (e.g., 1Q24 -> 2024-Q1)
                if 'quarter' in record:
                    q = record['quarter']
                    quarter_num = q[0]
                    year = '20' + q[2:]
                    record['formatted_quarter'] = f"{year}-Q{quarter_num}"
                
                # Calculate QoQ growth
                if i > 0 and data[i-1].get('value') and record.get('value'):
                    prev_val = data[i-1]['value']
                    curr_val = record['value']
                    if prev_val > 0:
                        record['qoq_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
                    else:
                        record['qoq_growth'] = None
                else:
                    record['qoq_growth'] = None
                
                # Add YoY growth if same quarter last year exists
                if 'quarter' in record and 'year' in record:
                    quarter_num = record['quarter'][0]
                    curr_year = record['year']
                    prev_year_quarter = f"{quarter_num}Q{str(curr_year-1)[-2:]}"
                    
                    # Find previous year same quarter
                    for prev_record in data:
                        if prev_record.get('quarter') == prev_year_quarter:
                            if prev_record.get('value') and record.get('value'):
                                prev_val = prev_record['value']
                                curr_val = record['value']
                                if prev_val > 0:
                                    record['yoy_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
                            break
        
        # Calculate summary statistics
        summary = {}
        if data:
            values = [d['value'] for d in data if d.get('value')]
            if values:
                summary = {
                    'total_records': len(data),
                    'min_value': min(values),
                    'max_value': max(values),
                    'avg_value': round(sum(values) / len(values), 2),
                    'latest_quarter': data[-1].get('formatted_quarter', data[-1].get('quarter')),
                    'latest_value': data[-1].get('value'),
                    'latest_qoq': data[-1].get('qoq_growth'),
                    'latest_yoy': data[-1].get('yoy_growth')
                }
        
        return {
            "data": data,
            "metric_type": metric_type,
            "summary": summary,
            "source": "MoCDB",
            "status": "success"
        }
    
    @tool_system.tool(
        name="get_credit_outstanding",
        description="Get real estate credit outstanding data",
        parameters={
            "credit_type": {
                "type": "string",
                "description": "Type of credit (construction, hotel, industrial, etc.)",
                "required": False
            },
            "year": {
                "type": "integer",
                "description": "Year to filter",
                "required": False
            }
        }
    )
    def get_credit_outstanding(credit_type: str = None, year: int = None) -> Dict:
        """Get credit outstanding data"""
        
        if tool_system.moc_db is None:
            return {"error": "MoC database not available", "status": "failed"}
        
        collection = tool_system.moc_db['credit_outstanding']
        
        # Build query
        query = {}
        if credit_type:
            query['credit_type'] = credit_type
        if year:
            query['year'] = year
        
        # Get available credit types
        credit_types = collection.distinct('credit_type')
        
        # Execute query
        cursor = collection.find(query, {"_id": 0}).sort("date", 1)
        data = list(cursor)
        
        # Calculate totals by quarter
        quarter_totals = {}
        for record in data:
            q = record.get('quarter')
            val = record.get('value', 0)
            if q:
                if q not in quarter_totals:
                    quarter_totals[q] = 0
                quarter_totals[q] += val
        
        return {
            "data": data,
            "credit_types": credit_types,
            "quarter_totals": quarter_totals,
            "records": len(data),
            "status": "success"
        }
    
    @tool_system.tool(
        name="get_inventory_levels",
        description="Get real estate inventory levels (quarterly data)",
        parameters={
            "inventory_type": {
                "type": "string",
                "enum": ["apartment", "individual_house", "land", "total"],
                "description": "Type of inventory",
                "required": False
            },
            "quarters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Quarters to retrieve (formats: '1Q24' or '2024-Q1')",
                "required": False
            },
            "last_n_quarters": {
                "type": "integer",
                "description": "Get last N quarters of data",
                "required": False
            }
        }
    )
    def get_inventory_levels(inventory_type: str = None, quarters: List[str] = None,
                           last_n_quarters: int = None) -> Dict:
        """Get inventory level data with enhanced quarterly extraction"""
        
        if tool_system.moc_db is None:
            return {"error": "MoC database not available", "status": "failed"}
        
        collection = tool_system.moc_db['inventory']
        
        # Build query
        query = {}
        if inventory_type:
            query['inventory_type'] = inventory_type
        
        # Handle different quarter formats
        if quarters:
            # Convert formats like '2024-Q1' to '1Q24'
            converted_quarters = []
            for q in quarters:
                if '-Q' in q:
                    # Format: 2024-Q1 -> 1Q24
                    year, quarter = q.split('-Q')
                    converted_q = f"{quarter}Q{year[-2:]}"
                    converted_quarters.append(converted_q)
                else:
                    # Already in format like 1Q24
                    converted_quarters.append(q)
            query['quarter'] = {"$in": converted_quarters}
        
        # Get last N quarters if specified
        if last_n_quarters:
            # Get all quarters sorted by date
            all_quarters = collection.distinct('quarter')
            all_quarters_sorted = sorted(all_quarters, 
                                        key=lambda x: (int('20' + x[2:]), int(x[0])))
            last_quarters = all_quarters_sorted[-last_n_quarters:]
            if 'quarter' in query:
                # Combine with existing quarter filter
                existing = query['quarter'].get('$in', [])
                query['quarter'] = {"$in": list(set(existing + last_quarters))}
            else:
                query['quarter'] = {"$in": last_quarters}
        
        # Execute query
        cursor = collection.find(query, {"_id": 0}).sort("date", 1)
        data = list(cursor)
        
        # Enhance data with formatted quarter and growth metrics
        if data:
            for i, record in enumerate(data):
                # Add formatted quarter
                if 'quarter' in record:
                    q = record['quarter']
                    quarter_num = q[0]
                    year = '20' + q[2:]
                    record['formatted_quarter'] = f"{year}-Q{quarter_num}"
                
                # Calculate QoQ change
                if i > 0 and data[i-1].get('value') and record.get('value'):
                    if data[i-1].get('inventory_type') == record.get('inventory_type'):
                        prev_val = data[i-1]['value']
                        curr_val = record['value']
                        record['qoq_change'] = curr_val - prev_val
                        if prev_val > 0:
                            record['qoq_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
        
        # Get latest values by type
        latest_by_type = {}
        for record in data:
            inv_type = record.get('inventory_type')
            if inv_type:
                latest_by_type[inv_type] = record
        
        # Calculate summary
        summary = {}
        if data:
            # Group by inventory type for summary
            by_type = {}
            for record in data:
                inv_type = record.get('inventory_type', 'unknown')
                if inv_type not in by_type:
                    by_type[inv_type] = []
                by_type[inv_type].append(record)
            
            for inv_type, records in by_type.items():
                values = [r['value'] for r in records if r.get('value')]
                if values and records:
                    summary[inv_type] = {
                        'latest_quarter': records[-1].get('formatted_quarter', records[-1].get('quarter')),
                        'latest_value': records[-1].get('value'),
                        'latest_qoq_change': records[-1].get('qoq_change'),
                        'latest_qoq_growth': records[-1].get('qoq_growth'),
                        'min_value': min(values),
                        'max_value': max(values),
                        'avg_value': round(sum(values) / len(values), 2)
                    }
        
        return {
            "data": data,
            "latest_by_type": latest_by_type,
            "summary": summary,
            "records": len(data),
            "source": "MoCDB",
            "status": "success"
        }
    
    @tool_system.tool(
        name="analyze_market_trends",
        description="Analyze market trends from MoC data",
        parameters={
            "analysis_type": {
                "type": "string",
                "enum": ["transaction", "credit", "inventory", "all"],
                "description": "Type of analysis",
                "required": False
            },
            "period": {
                "type": "string",
                "description": "Period for analysis (e.g., '2024')",
                "required": False
            }
        }
    )
    def analyze_market_trends(analysis_type: str = "all", period: str = None) -> Dict:
        """Comprehensive market trend analysis"""
        
        results = {}
        
        # Transaction volume trends
        if analysis_type in ["transaction", "all"]:
            trans_result = get_transaction_volumes()
            if trans_result.get("status") == "success":
                trans_data = trans_result.get("data", [])
                if trans_data:
                    # Calculate trend
                    apartment_trend = [d for d in trans_data if d.get('metric_type') == 'apartment']
                    land_trend = [d for d in trans_data if d.get('metric_type') == 'land']
                    
                    results["transaction_trends"] = {
                        "apartment_latest": apartment_trend[-1] if apartment_trend else None,
                        "land_latest": land_trend[-1] if land_trend else None,
                        "total_quarters": len(set(d.get('quarter') for d in trans_data))
                    }
        
        # Credit trends
        if analysis_type in ["credit", "all"]:
            credit_result = get_credit_outstanding()
            if credit_result.get("status") == "success":
                results["credit_trends"] = {
                    "total_by_quarter": credit_result.get("quarter_totals", {}),
                    "credit_types": credit_result.get("credit_types", [])
                }
        
        # Inventory trends
        if analysis_type in ["inventory", "all"]:
            inv_result = get_inventory_levels()
            if inv_result.get("status") == "success":
                results["inventory_trends"] = inv_result.get("latest_by_type", {})
        
        return {
            "analysis": results,
            "analysis_type": analysis_type,
            "period": period,
            "status": "success"
        }