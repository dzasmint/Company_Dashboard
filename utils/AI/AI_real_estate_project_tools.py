"""
AI Real Estate Project Tools
Simplified and optimized version
"""

from typing import Dict, List


def register_real_estate_tools(tool_system):
    """Register real estate project tools with the tool system"""
    
    @tool_system.tool(
        name="search_projects",
        description="Search real estate projects by company tickers. Returns project list for discovery and screening.",
        parameters={
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of company tickers (e.g., ['VHM', 'DXG', 'KDH'])",
                "required": True
            }
        }
    )
    def search_projects(tickers: List[str]) -> Dict:
        """
        Search projects by company tickers - lean discovery tool
        
        Returns:
            Project Name, Company Ticker, Location, Total Units, RNAV Value, Project Completion Year
        """
        # Normalize tickers
        tickers = [ticker.upper() for ticker in tickers]
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB connection not available", "status": "failed"}
            
        collection = tool_system.vietnam_stocks_db['RealEstateProjects']
        
        # Query projects with only essential fields for discovery
        projects = list(collection.find(
            {"company_ticker": {"$in": tickers}},
            {
                "project_name": 1,
                "company_ticker": 1,
                "location": 1,
                "total_units": 1,
                "rnav_value": 1,
                "project_completion_year": 1,
                "_id": 0
            }
        ))
        
        if not projects:
            return {
                "error": f"No projects found for tickers: {tickers}",
                "status": "failed"
            }
        
        # Format projects with lean fields
        formatted_projects = []
        for project in projects:
            formatted_projects.append({
                "project_name": project.get("project_name"),
                "company_ticker": project.get("company_ticker"),
                "location": project.get("location"),
                "total_units": project.get("total_units"),
                "rnav_value": project.get("rnav_value"),
                "project_completion_year": project.get("project_completion_year")
            })
        
        # Group by ticker for better organization
        results_by_ticker = {}
        for ticker in tickers:
            ticker_projects = [p for p in formatted_projects if p["company_ticker"] == ticker]
            if ticker_projects:
                results_by_ticker[ticker] = {
                    "count": len(ticker_projects),
                    "total_rnav": sum(p["rnav_value"] for p in ticker_projects if p["rnav_value"]),
                    "total_units": sum(p["total_units"] for p in ticker_projects if p["total_units"]),
                    "projects": ticker_projects
                }
        
        return {
            "summary": {
                "total_projects": len(formatted_projects),
                "companies_found": len(results_by_ticker),
                "total_rnav": sum(p["rnav_value"] for p in formatted_projects if p["rnav_value"]),
                "total_units": sum(p["total_units"] for p in formatted_projects if p["total_units"])
            },
            "by_company": results_by_ticker,
            "all_projects": formatted_projects,
            "status": "success"
        }
    
    @tool_system.tool(
        name="get_project_overview",
        description="Get comprehensive overview of a specific real estate project including land, construction, product mix, timelines and financial parameters.",
        parameters={
            "project_name": {
                "type": "string",
                "description": "Name of the project (e.g., 'Prive', 'Gem Skyworld Long Thanh')",
                "required": True
            }
        }
    )
    def get_project_overview(project_name: str) -> Dict:
        """
        Get detailed overview of a specific project
        
        Returns comprehensive project information including:
        - Project info (name, ticker, location, RNAV value, ownership percentage)
        - Land details (area, cost per sqm, total cost)
        - Construction details (GFA, cost per sqm, total cost)
        - Product mix (low-rise/high-rise breakdown with pricing)
        - Complete project timeline
        - Financial parameters (WACC, debt, SG&A)
        """
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB connection not available", "status": "failed"}
            
        collection = tool_system.vietnam_stocks_db['RealEstateProjects']
        
        # Query for the specific project
        project = collection.find_one(
            {"project_name": project_name},
            {"_id": 0}
        )
        
        if not project:
            return {
                "error": f"Project '{project_name}' not found",
                "status": "failed"
            }
        
        # Build the comprehensive overview
        overview = {
            "project_info": {
                "project_name": project.get("project_name"),
                "company_ticker": project.get("company_ticker"),
                "location": project.get("location"),
                "rnav_value": project.get("rnav_value"),
                "project_ownership": project.get("project_ownership") 
            },
            
            "land": {
                "land_area": project.get("land_area"),
                "land_cost_per_sqm": project.get("land_cost_per_sqm"),
                "total_land_cost": project.get("total_land_cost")
            },
            
            "construction": {
                "gross_floor_area": project.get("gross_floor_area"),
                "construction_cost_per_sqm": project.get("construction_cost_per_sqm"),
                "total_construction_cost": project.get("total_construction_cost")
            },
            
            "product_mix": {
                "low_rise": {
                    "total_units": project.get("low_rise_units", 0),
                    "unit_size": project.get("low_rise_avg_unit_size", 0),
                    "net_sellable_area": project.get("low_rise_nsa", 0),
                    "average_selling_price": project.get("low_rise_asp", 0)
                },
                "high_rise": {
                    "total_units": project.get("high_rise_units", 0),
                    "unit_size": project.get("high_rise_avg_unit_size", 0),
                    "net_sellable_area": project.get("high_rise_nsa", 0),
                    "average_selling_price": project.get("high_rise_asp", 0)
                },
                "annual_price_increment": project.get("price_increment_factor", 0)
            },
            
            "timelines": {
                "land_payment_start_year": project.get("land_payment_start_year") or project.get("land_payment_year"),
                "land_payment_end_year": (
                    project.get("land_payment_start_year", project.get("land_payment_year", 0)) + 
                    project.get("land_payment_years", 1) - 1
                ) if project.get("land_payment_start_year") or project.get("land_payment_year") else None,
                "construction_start_year": project.get("construction_start_year"),
                "construction_end_year": (
                    project.get("construction_start_year", 0) + 
                    project.get("construction_years", 1) - 1
                ) if project.get("construction_start_year") else None,
                "sale_start_year": project.get("sale_start_year"),
                "sale_end_year": (
                    project.get("sale_start_year", 0) + 
                    project.get("sales_years", 1) - 1
                ) if project.get("sale_start_year") else None,
                "revenue_booking_start_year": project.get("revenue_booking_start_year"),
                "revenue_booking_end_year": project.get("revenue_booking_end_year") or project.get("project_completion_year")
            },
            
            "financial_parameters": {
                "wacc": project.get("wacc_rate"),
                "cost_of_debt": project.get("cost_of_debt"),
                "sga_as_pct_of_revenue": project.get("sga_percentage"),
                "debt_financing_pct": project.get("debt_financing_pct")
            },
            
            "status": "success"
        }
        
        return overview
    
    @tool_system.tool(
        name="get_project_metrics",
        description="Get time series data for specific metrics of a real estate project over a year range.",
        parameters={
            "project_name": {
                "type": "string",
                "description": "Name of the project (e.g., 'Prive', 'Gem Skyworld Long Thanh')",
                "required": True
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of metrics to retrieve (e.g., ['revenue', 'cash_flow', 'debt', 'npv'])",
                "required": True
            },
            "year_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Year range as [start_year, end_year] (e.g., [2024, 2030])",
                "required": True,
                "minItems": 2,
                "maxItems": 2
            },
            "total": {
                "type": "boolean",
                "description": "If True, return only the total sum of each metric across all years instead of time series",
                "required": False,
                "default": False
            }
        }
    )
    def get_project_metrics(project_name: str, metrics: List[str], year_range: List[int], total: bool = False) -> Dict:
        """
        Get time series metrics for a specific project
        
        Returns structured time series data:
        - project_name: Name of the project
        - series: Array of metric time series with points
        - as_of: Current date timestamp
        """
        from datetime import datetime
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB connection not available", "status": "failed"}
        
        if len(year_range) != 2:
            return {"error": "year_range must contain exactly 2 elements: [start_year, end_year]", "status": "failed"}
        
        start_year, end_year = year_range
        if start_year > end_year:
            return {"error": f"Invalid year range: start_year ({start_year}) > end_year ({end_year})", "status": "failed"}
            
        collection = tool_system.vietnam_stocks_db['RealEstateProjects']
        
        # Query for the specific project
        project = collection.find_one(
            {"project_name": project_name},
            {"_id": 0}
        )
        
        if not project:
            return {
                "error": f"Project '{project_name}' not found",
                "status": "failed"
            }
        
        # Define available metrics - all from comprehensive_financial_statements
        metric_definitions = {
            # Revenue & Sales metrics (in VND)
            "presales": {"unit": "VND"},
            "presales_low_rise": {"unit": "VND"},
            "presales_high_rise": {"unit": "VND"},
            "revenue_recognition": {"unit": "VND"},
            "revenue_recognition_low_rise": {"unit": "VND"},
            "revenue_recognition_high_rise": {"unit": "VND"},
            
            # Cash metrics (in VND)
            "cash_balance": {"unit": "VND"},
            "cash_balance_change": {"unit": "VND"},
            "cash_inflow_presales": {"unit": "VND"},  # This was already here, metric name is correct
            "cash_outflow_land": {"unit": "VND"},
            "cash_outflow_construction": {"unit": "VND"},
            "cash_outflow_interest": {"unit": "VND"},
            "cash_outflow_sga": {"unit": "VND"},
            "cash_outflow_tax": {"unit": "VND"},
            
            # Debt metrics (in VND)
            "debt_balance": {"unit": "VND"},
            "debt_disbursement": {"unit": "VND"},
            "debt_repayment": {"unit": "VND"},
            
            # Cost metrics (in VND)
            "land_cost": {"unit": "VND"},
            "construction_cost": {"unit": "VND"},
            "cogs": {"unit": "VND"},
            "sga_expense": {"unit": "VND"},
            "interest_expense_cash": {"unit": "VND"},
            "interest_capitalized": {"unit": "VND"},
            
            # Inventory metrics (in VND)
            "inventory_addition": {"unit": "VND"},
            "inventory_balance": {"unit": "VND"},
            
            # Customer prepayment (in VND)
            "customer_prepayment_balance": {"unit": "VND"},
            
            # Profit metrics (in VND)
            "pbt": {"unit": "VND"},
            "pat": {"unit": "VND"},
            "tax": {"unit": "VND"}
        }
        
        # Validate requested metrics
        invalid_metrics = [m for m in metrics if m not in metric_definitions]
        if invalid_metrics:
            return {
                "error": f"Invalid metrics requested: {invalid_metrics}",
                "available_metrics": list(metric_definitions.keys()),
                "status": "failed"
            }
        
        # Get comprehensive financial statements
        cfs = project.get("comprehensive_financial_statements", {})
        
        if not cfs:
            return {
                "error": f"No financial statements data available for project '{project_name}'",
                "status": "failed"
            }
        
        # Get distribution fields for calculated metrics
        low_rise_presales_dist = project.get("low_rise_presales_distribution", {})
        high_rise_presales_dist = project.get("high_rise_presales_distribution", {})
        low_rise_revenue_dist = project.get("low_rise_revenue_distribution", {})
        high_rise_revenue_dist = project.get("high_rise_revenue_distribution", {})
        
        # Build series array
        series = []
        
        for metric in metrics:
            metric_def = metric_definitions[metric]
            unit = metric_def["unit"]
            points = []
            
            # Handle each metric type
            for year in range(start_year, end_year + 1):
                year_str = str(year)
                
                if metric == "presales_low_rise":
                    # Calculate low-rise presales from total presales * low-rise distribution
                    if year_str in cfs and isinstance(cfs[year_str], dict):
                        total_presales = cfs[year_str].get("presales", 0)
                        if total_presales and year_str in low_rise_presales_dist:
                            distribution_pct = low_rise_presales_dist[year_str] / 100.0
                            value = total_presales * distribution_pct
                            if value != 0:
                                points.append({"year": year, "value": value})
                            
                elif metric == "presales_high_rise":
                    # Calculate high-rise presales from total presales * high-rise distribution
                    if year_str in cfs and isinstance(cfs[year_str], dict):
                        total_presales = cfs[year_str].get("presales", 0)
                        if total_presales and year_str in high_rise_presales_dist:
                            distribution_pct = high_rise_presales_dist[year_str] / 100.0
                            value = total_presales * distribution_pct
                            if value != 0:
                                points.append({"year": year, "value": value})
                            
                elif metric == "revenue_recognition_low_rise":
                    # Calculate low-rise revenue from total revenue * low-rise distribution
                    if year_str in cfs and isinstance(cfs[year_str], dict):
                        total_revenue = cfs[year_str].get("revenue_recognition", 0)
                        if total_revenue and year_str in low_rise_revenue_dist:
                            distribution_pct = low_rise_revenue_dist[year_str] / 100.0
                            value = total_revenue * distribution_pct
                            if value != 0:
                                points.append({"year": year, "value": value})
                            
                elif metric == "revenue_recognition_high_rise":
                    # Calculate high-rise revenue from total revenue * high-rise distribution
                    if year_str in cfs and isinstance(cfs[year_str], dict):
                        total_revenue = cfs[year_str].get("revenue_recognition", 0)
                        if total_revenue and year_str in high_rise_revenue_dist:
                            distribution_pct = high_rise_revenue_dist[year_str] / 100.0
                            value = total_revenue * distribution_pct
                            if value != 0:
                                points.append({"year": year, "value": value})
                            
                else:
                    # Extract directly from comprehensive_financial_statements
                    if year_str in cfs and isinstance(cfs[year_str], dict):
                        year_data = cfs[year_str]
                        if metric in year_data:
                            value = year_data[metric]
                            if value is not None and value != 0:  # Only include non-zero values
                                points.append({"year": year, "value": value})
            
            # Add series even if empty to show what was requested
            series.append({
                "metric": metric,
                "unit": unit,
                "points": points
            })
        
        # Build response based on total flag
        if total:
            # Return totals instead of time series
            totals = {}
            for series_item in series:
                metric = series_item["metric"]
                points = series_item["points"]
                # Sum all values for this metric
                total_value = sum(point["value"] for point in points)
                totals[metric] = total_value
            
            result = {
                "project_name": project_name,
                "totals": totals,
                "year_range": [start_year, end_year],
                "as_of": datetime.now().strftime("%Y-%m-%d")
            }
        else:
            # Return time series format
            result = {
                "project_name": project_name,
                "series": series,
                "as_of": datetime.now().strftime("%Y-%m-%d")
            }
        
        # Add optional metadata
        result["metadata"] = {
            "company_ticker": project.get("company_ticker"),
            "location": project.get("location"),
            "project_completion_year": project.get("project_completion_year")
        }
        
        # Add success status
        result["status"] = "success"
        
        return result
    
    @tool_system.tool(
        name="rank_projects_by_metric",
        description="Rank specified real estate projects by a metric value (supports both static fields like 'rnav_value' and time-series metrics like 'presales').",
        parameters={
            "projects": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of project names to rank (e.g., ['Prive', 'Gem Skyworld', 'Duy Tien'])",
                "required": True
            },
            "metric": {
                "type": "string",
                "description": "The metric to rank by. Static fields: 'rnav_value', 'total_units', 'land_area', 'project_irr', etc. Time-series: 'presales', 'revenue_recognition', 'cash_balance', etc.",
                "required": True
            },
            "order": {
                "type": "string",
                "description": "Ranking order: 'descending' (highest first) or 'ascending' (lowest first)",
                "enum": ["descending", "ascending"],
                "required": True
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top projects to return",
                "required": False,
                "default": 5
            },
            "included_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional fields to include in output (e.g., ['project_name', 'company_ticker', 'location', 'rnav_value'])",
                "required": False,
                "default": ["project_name", "company_ticker", "location"]
            },
            "year_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Year range for metric calculation [start_year, end_year]. If not specified, uses [2024, 2035]",
                "required": False,
                "default": [2024, 2035]
            }
        }
    )
    def rank_projects_by_metric(
        projects: List[str],
        metric: str,
        order: str,
        top_k: int = 5,
        included_fields: List[str] = None,
        year_range: List[int] = None
    ) -> Dict:
        """
        Rank projects by a specific metric (static field or time-series)
        
        Returns ranked list of projects with metric values and requested fields
        """
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB connection not available", "status": "failed"}
        
        if not projects:
            return {"error": "No projects provided", "status": "failed"}
        
        if included_fields is None:
            included_fields = ["project_name", "company_ticker", "location"]
        
        if year_range is None:
            year_range = [2024, 2035]
            
        collection = tool_system.vietnam_stocks_db['RealEstateProjects']
        
        # Define static fields (actual fields from MongoDB, not in comprehensive_financial_statements)
        static_fields = {
            "average_selling_price",
            "average_unit_size",
            "company_name",
            "company_ticker",
            "construction_cost_per_sqm",
            "construction_start_year",
            "construction_years",
            "cost_of_debt",
            "created_date",
            "debt_financing_pct",
            "equity_investment",
            "google_maps_location",
            "gross_floor_area",
            "high_rise_asp",
            "high_rise_avg_unit_size",
            "high_rise_nsa",
            "high_rise_units",
            "land_area",
            "land_cost_per_sqm",
            "land_payment_start_year",
            "land_payment_year",
            "land_payment_years",
            "last_updated",
            "latitude",
            "location",
            "longitude",
            "low_rise_asp",
            "low_rise_avg_unit_size",
            "low_rise_nsa",
            "low_rise_units",
            "net_sellable_area",
            "price_increment_factor",
            "project_completion_year",
            "project_irr",
            "project_name",
            "project_ownership",
            "revenue_booking_end_year",
            "revenue_booking_start_year",
            "rnav_calculation_details",
            "rnav_value",
            "sale_start_year",
            "sales_years",
            "sector",
            "sga_percentage",
            "total_construction_cost",
            "total_debt",
            "total_land_cost",
            "total_pat",
            "total_pbt",
            "total_revenue",
            "total_sga_cost",
            "total_units",
            "wacc_rate",
        }
        
        # Check if metric is static or time-series
        is_static = metric in static_fields
        
        # Calculate metric value for each specified project
        project_metrics = []
        projects_not_found = []
        projects_without_data = []
        
        for project_name in projects:
            # Get project details from MongoDB
            project_doc = collection.find_one({"project_name": project_name}, {"_id": 0})
            
            if not project_doc:
                projects_not_found.append(project_name)
                continue
            
            try:
                metric_value = None
                
                if is_static:
                    # For static fields, get value directly from project document
                    if metric in project_doc:
                        metric_value = project_doc[metric]
                        # Skip if value is None, NaN, or 0 (for numeric fields)
                        if metric_value is None:
                            projects_without_data.append(project_name)
                            continue
                        if isinstance(metric_value, (int, float)):
                            import math
                            if math.isnan(metric_value) or metric_value == 0:
                                projects_without_data.append(project_name)
                                continue
                    else:
                        projects_without_data.append(project_name)
                        continue
                else:
                    # For time-series metrics, use get_project_metrics
                    result = get_project_metrics(
                        project_name=project_name,
                        metrics=[metric],
                        year_range=year_range,
                        total=True
                    )
                    
                    # Check if successful and has the metric
                    if result.get("status") != "failed" and "totals" in result:
                        metric_value = result["totals"].get(metric, 0)
                        if metric_value == 0:
                            projects_without_data.append(project_name)
                            continue
                    else:
                        projects_without_data.append(project_name)
                        continue
                
                # Build project info with requested fields
                if metric_value is not None:
                    project_info = {}
                    for field in included_fields:
                        if field in project_doc:
                            project_info[field] = project_doc[field]
                    
                    project_metrics.append({
                        "metric_value": metric_value,
                        **project_info
                    })
                    
            except Exception:
                projects_without_data.append(project_name)
                continue
        
        if not project_metrics:
            return {
                "error": f"No projects have data for metric '{metric}'",
                "projects_provided": len(projects),
                "projects_not_found": projects_not_found,
                "projects_without_data": projects_without_data,
                "status": "failed"
            }
        
        # Sort by metric value
        reverse = (order == "descending")
        sorted_projects = sorted(
            project_metrics,
            key=lambda x: x["metric_value"],
            reverse=reverse
        )
        
        # Get top k (limited to available projects)
        top_projects = sorted_projects[:min(top_k, len(sorted_projects))]
        
        # Format output
        result = {
            "metric": metric,
            "order": order,
            "year_range": year_range,
            "top_k": top_k,
            "projects_provided": len(projects),
            "projects_analyzed": len(project_metrics),
            "rankings": []
        }
        
        for i, project in enumerate(top_projects, 1):
            ranking_entry = {
                "rank": i,
                "metric_value": project["metric_value"]
            }
            # Add all requested fields
            for field in included_fields:
                if field in project:
                    ranking_entry[field] = project[field]
            
            result["rankings"].append(ranking_entry)
        
        # Add summary statistics if we have data
        if project_metrics:
            all_values = [p["metric_value"] for p in project_metrics]
            result["summary"] = {
                "min": min(all_values),
                "max": max(all_values),
                "average": sum(all_values) / len(all_values),
                "projects_with_data": len(project_metrics)
            }
        
        # Add information about missing projects
        if projects_not_found:
            result["projects_not_found"] = projects_not_found
        if projects_without_data:
            result["projects_without_metric_data"] = projects_without_data
        
        result["status"] = "success"
        
        return result