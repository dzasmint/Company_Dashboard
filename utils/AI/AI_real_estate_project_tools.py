"""
AI Real Estate Project Tools
Extracted from enhanced_ai_assistant.py
Contains real estate project analysis tools for the Enhanced AI Tool System
"""

from typing import Dict, List
from datetime import datetime


def register_real_estate_tools(tool_system):
    """Register real estate project tools with the tool system
    
    Args:
        tool_system: The EnhancedAIToolSystem instance to register tools with
    """
    
    @tool_system.tool(
        name="list_real_estate_projects",
        description="List real estate projects with filtering options",
        parameters={
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Company tickers",
                "required": False
            },
            "location": {
                "type": "string",
                "description": "Project location filter",
                "required": False
            },
            "min_units": {
                "type": "integer",
                "description": "Minimum number of units",
                "required": False
            }
        }
    )
    def list_real_estate_projects(tickers: List[str] = None, location: str = None,
                                 min_units: int = None) -> Dict:
        """List real estate projects"""
        
        df = tool_system._load_real_estate_projects()
        
        if df.empty:
            return {"error": "No projects data available", "status": "failed"}
        
        # Apply filters
        if tickers:
            tickers = [t.upper() for t in tickers]
            df = df[df['company_ticker'].isin(tickers)]
        
        if location:
            df = df[df['location'].str.contains(location, case=False, na=False)]
        
        if min_units:
            df = df[df['total_units'] >= min_units]
        
        # Group by company
        summary = {}
        for ticker in df['company_ticker'].unique():
            company_projects = df[df['company_ticker'] == ticker]
            # Include RNAV if available
            project_cols = ['project_name', 'location', 'total_units']
            if 'rnav_value' in company_projects.columns:
                project_cols.append('rnav_value')
            
            summary[ticker] = {
                "count": len(company_projects),
                "total_units": company_projects['total_units'].sum(),
                "total_nsa": company_projects['net_sellable_area'].sum(),
                "total_rnav": company_projects['rnav_value'].sum() if 'rnav_value' in company_projects.columns else None,
                "projects": company_projects[project_cols].to_dict('records')
            }
        
        return {
            "summary": summary,
            "total_projects": len(df),
            "filters_applied": {
                "tickers": tickers,
                "location": location,
                "min_units": min_units
            },
            "status": "success"
        }
    
    @tool_system.tool(
        name="get_project_details",
        description="Get detailed information about specific projects. IMPORTANT: presales_distribution and revenue_distribution contain PERCENTAGES (not actual units/amounts). cash_collection_schedule may be percentages or absolute amounts. The tool returns calculated actual values in presales_info, revenue_info, and cash_collection_info fields with both percentages and absolute amounts.",
        parameters={
            "project_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Project names to retrieve",
                "required": False
            },
            "ticker": {
                "type": "string",
                "description": "Company ticker to filter projects",
                "required": False
            },
            "include_financials": {
                "type": "boolean",
                "description": "Include detailed financial projections and schedules",
                "required": False
            },
            "include_assumptions": {
                "type": "boolean",
                "description": "Include AI-generated assumptions",
                "required": False
            }
        }
    )
    def get_project_details(project_names: List[str] = None, ticker: str = None,
                          include_financials: bool = True, 
                          include_assumptions: bool = False) -> Dict:
        """Get detailed project information from MongoDB RealEstateProjects collection"""
        
        # Try MongoDB first
        if tool_system.vietnam_stocks_db is not None:
            try:
                collection = tool_system.vietnam_stocks_db['RealEstateProjects']
                
                # Build query
                query = {}
                if project_names:
                    # Case-insensitive search
                    query['project_name'] = {
                        "$in": [{"$regex": f"^{name}$", "$options": "i"} for name in project_names]
                    }
                if ticker:
                    query['company_ticker'] = ticker.upper()
                
                # Retrieve projects
                projects = list(collection.find(query, {'_id': 0}))
                
                if not projects:
                    # Fallback to CSV
                    df = tool_system._load_real_estate_projects()
                    if not df.empty:
                        if project_names:
                            mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
                            df = df[mask]
                        if ticker:
                            df = df[df['company_ticker'] == ticker.upper()]
                        
                        if not df.empty:
                            return {
                                "projects": df.to_dict('records'),
                                "count": len(df),
                                "source": "csv_fallback",
                                "status": "success"
                            }
                    
                    return {"error": f"No projects found", "status": "failed"}
                
                # Process retrieved projects
                result_projects = []
                for project in projects:
                    project_data = {
                        "project_name": project.get('project_name'),
                        "company_ticker": project.get('company_ticker'),
                        "location": project.get('location'),
                        "total_units": project.get('total_units'),
                        "net_sellable_area": project.get('net_sellable_area'),
                        "average_selling_price": project.get('average_selling_price'),
                        "construction_start_year": project.get('construction_start_year'),
                        "project_completion_year": project.get('project_completion_year'),
                        "project_type": project.get('project_type'),
                        "ownership_percentage": project.get('ownership_percentage', 100),
                        "land_cost_per_sqm": project.get('land_cost_per_sqm'),
                        "construction_cost_per_sqm": project.get('construction_cost_per_sqm'),
                        "last_updated": project.get('last_updated')
                    }
                    
                    # Add financial details if requested
                    if include_financials:
                        # Get presales distribution (these are PERCENTAGES, not units)
                        presales_dist_pct = project.get('presales_distribution', {})
                        total_units = project.get('total_units', 0)
                        
                        # Calculate actual presold units from percentages
                        presales_units_by_year = {}
                        cumulative_presold = 0
                        current_year = datetime.now().year
                        
                        for year_str, percentage in presales_dist_pct.items():
                            year = int(year_str)
                            units_this_year = (total_units * percentage / 100) if total_units else 0
                            presales_units_by_year[year_str] = {
                                "percentage": percentage,
                                "units": int(units_this_year),
                                "description": f"{percentage}% of total units ({int(units_this_year)} units)"
                            }
                            if year <= current_year:
                                cumulative_presold += units_this_year
                        
                        # Get revenue distribution (also PERCENTAGES)
                        revenue_dist_pct = project.get('revenue_distribution', {})
                        total_revenue = project.get('total_revenue', 0)
                        
                        # Calculate actual revenue amounts from percentages
                        revenue_by_year = {}
                        cumulative_revenue = 0
                        
                        for year_str, percentage in revenue_dist_pct.items():
                            year = int(year_str)
                            revenue_this_year = (total_revenue * percentage / 100) if total_revenue else 0
                            revenue_by_year[year_str] = {
                                "percentage": percentage,
                                "revenue_vnd": revenue_this_year,
                                "revenue_billion_vnd": revenue_this_year / 1e9 if revenue_this_year else 0,
                                "description": f"{percentage}% of total revenue ({revenue_this_year/1e9:.1f}B VND)"
                            }
                            if year <= current_year:
                                cumulative_revenue += revenue_this_year
                        
                        # Get cash collection schedules (complex structure based on presale year)
                        cash_collection_schedules = project.get('cash_collection_schedules', {})
                        
                        # Calculate actual cash collection amounts
                        # Logic from project_pipeline_real_estate.py:
                        # Each presale year has its own collection schedule
                        # Actual cash = presale_amount * (collection_percentage / 100)
                        
                        cash_collection_by_year = {}
                        cumulative_cash_collected = 0
                        
                        # First, calculate presales amounts by year (in VND)
                        presales_amounts_by_year = {}
                        for year_str, percentage in presales_dist_pct.items():
                            presale_amount = (total_revenue * percentage / 100) if total_revenue else 0
                            presales_amounts_by_year[int(year_str)] = presale_amount
                        
                        # Now calculate cash collection based on collection schedules
                        for presale_year, presale_amount in presales_amounts_by_year.items():
                            # Get the collection schedule for this presale year
                            schedule = cash_collection_schedules.get(presale_year, {})
                            if not schedule:
                                # If no schedule, assume 100% collection in presale year
                                schedule = {presale_year: 100}
                            
                            for collection_year_str, collection_pct in schedule.items():
                                collection_year = int(collection_year_str)
                                cash_amount = presale_amount * (collection_pct / 100)
                                
                                if collection_year not in cash_collection_by_year:
                                    cash_collection_by_year[collection_year] = 0
                                cash_collection_by_year[collection_year] += cash_amount
                        
                        # Format cash collection data for output
                        cash_collection_formatted = {}
                        for year, amount in sorted(cash_collection_by_year.items()):
                            cash_collection_formatted[str(year)] = {
                                "cash_collected_vnd": amount,
                                "cash_collected_billion_vnd": amount / 1e9 if amount else 0,
                                "description": f"{amount/1e9:.1f}B VND collected"
                            }
                            if year <= current_year:
                                cumulative_cash_collected += amount
                        
                        project_data.update({
                            # Original percentage data with clear labeling
                            "presales_distribution_percentages": presales_dist_pct,
                            "presales_distribution_note": "IMPORTANT: presales_distribution contains PERCENTAGES, not unit counts",
                            
                            # Calculated actual units
                            "presales_info": {
                                "total_units_in_project": total_units,
                                "presales_by_year": presales_units_by_year,
                                "total_presold_units_to_date": int(cumulative_presold),
                                "percentage_presold_to_date": (cumulative_presold / total_units * 100) if total_units else 0,
                                "remaining_units_to_sell": int(total_units - cumulative_presold) if total_units else 0
                            },
                            
                            # Revenue distribution (also PERCENTAGES)
                            "revenue_distribution_percentages": revenue_dist_pct,
                            "revenue_distribution_note": "Revenue distribution also contains PERCENTAGES of total revenue recognized each year",
                            
                            # Calculated actual revenue amounts
                            "revenue_info": {
                                "total_revenue_vnd": total_revenue,
                                "total_revenue_billion_vnd": total_revenue / 1e9 if total_revenue else 0,
                                "revenue_by_year": revenue_by_year,
                                "cumulative_revenue_to_date_vnd": cumulative_revenue,
                                "cumulative_revenue_to_date_billion_vnd": cumulative_revenue / 1e9 if cumulative_revenue else 0,
                                "percentage_revenue_recognized_to_date": (cumulative_revenue / total_revenue * 100) if total_revenue else 0
                            },
                            
                            # Cash collection schedule with calculations
                            "cash_collection_schedules_raw": cash_collection_schedules,
                            "cash_collection_note": "Cash collection is calculated from presales amounts using collection schedules per presale year",
                            "cash_collection_info": {
                                "cash_collection_by_year": cash_collection_formatted,
                                "total_cash_to_collect": total_revenue,
                                "total_cash_to_collect_billion_vnd": total_revenue / 1e9 if total_revenue else 0,
                                "cumulative_cash_collected_vnd": cumulative_cash_collected,
                                "cumulative_cash_collected_billion_vnd": cumulative_cash_collected / 1e9 if cumulative_cash_collected else 0,
                                "percentage_cash_collected_to_date": (cumulative_cash_collected / total_revenue * 100) if total_revenue else 0,
                                "remaining_cash_to_collect_vnd": total_revenue - cumulative_cash_collected if total_revenue else 0,
                                "remaining_cash_to_collect_billion_vnd": (total_revenue - cumulative_cash_collected) / 1e9 if total_revenue else 0
                            },
                            "construction_schedule": project.get('construction_schedule', {})
                        })
                        
                        # Calculate and add advanced financial metrics
                        # Use saved IRR if available, otherwise calculate it
                        project_irr = project.get('project_irr')  # Try to get saved IRR first
                        if project_irr is None:
                            project_irr = tool_system._calculate_project_irr(project) if hasattr(tool_system, '_calculate_project_irr') else None
                        
                        cumulative_interest = tool_system._calculate_cumulative_interest(project) if hasattr(tool_system, '_calculate_cumulative_interest') else 0
                        total_debt = project.get('total_debt', 0) or 0
                        cash_burden = total_debt + cumulative_interest
                        
                        project_data.update({
                            "total_revenue": project.get('total_revenue'),
                            "total_cogs": project.get('total_cogs'),
                            "gross_margin": project.get('gross_margin'),
                            "rnav_value": project.get('rnav_value'),
                            "npv": project.get('npv'),
                            "irr": project_irr,
                            "irr_percentage": f"{project_irr:.2%}" if project_irr else "N/A",
                            "total_debt": total_debt,
                            "cumulative_interest": cumulative_interest,
                            "cash_burden": cash_burden,
                            "debt_to_revenue_ratio": (total_debt / project.get('total_revenue', 1)) if project.get('total_revenue') else None
                        })
                    
                    # Add AI assumptions if requested
                    if include_assumptions:
                        project_data["ai_assumptions"] = project.get('ai_assumptions', {})
                    
                    result_projects.append(project_data)
                
                return {
                    "projects": result_projects,
                    "count": len(result_projects),
                    "source": "RealEstateProjects",
                    "include_financials": include_financials,
                    "include_assumptions": include_assumptions,
                    "status": "success"
                }
                
            except Exception as e:
                # Fallback to CSV on error
                pass
        
        # Fallback to CSV
        df = tool_system._load_real_estate_projects()
        
        if df.empty:
            return {"error": "No projects data available", "status": "failed"}
        
        # Filter projects
        if project_names:
            mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
            df = df[mask]
        if ticker:
            df = df[df['company_ticker'] == ticker.upper()]
        
        if df.empty:
            return {"error": f"Projects not found", "status": "failed"}
        
        # Select columns based on request
        if include_financials:
            cols = df.columns.tolist()
        else:
            cols = ['project_name', 'company_ticker', 'location', 'total_units',
                   'net_sellable_area', 'average_selling_price', 'rnav_value',
                   'construction_start_year', 'project_completion_year']
            cols = [c for c in cols if c in df.columns]
        
        projects_data = df[cols].to_dict('records')
        
        return {
            "projects": projects_data,
            "count": len(projects_data),
            "source": "csv",
            "include_financials": include_financials,
            "status": "success"
        }
    
    @tool_system.tool(
        name="rank_projects_by_metric",
        description="Rank real estate projects by specified metric",
        parameters={
            "metric": {
                "type": "string",
                "description": "Metric to rank by (rnav, revenue, units, nsa, margin, asp)",
                "required": True
            },
            "top_n": {
                "type": "integer",
                "description": "Number of top projects to return",
                "required": False
            },
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by companies",
                "required": False
            }
        }
    )
    def rank_projects_by_metric(metric: str, top_n: int = 10, 
                               tickers: List[str] = None) -> Dict:
        """Rank projects by metric"""
        
        df = tool_system._load_real_estate_projects()
        
        if df.empty:
            return {"error": "No projects data available", "status": "failed"}
        
        # Filter by tickers if specified
        if tickers:
            tickers = [t.upper() for t in tickers]
            df = df[df['company_ticker'].isin(tickers)]
        
        # Map metric names to columns
        metric_mapping = {
            'rnav': 'rnav_value',
            'revenue': 'total_revenue_potential',
            'units': 'total_units',
            'nsa': 'net_sellable_area',
            'margin': 'gross_margin',
            'asp': 'average_selling_price',
            'construction_cost': 'construction_cost_per_sqm',
            'land_cost': 'land_cost_per_sqm'
        }
        
        column = metric_mapping.get(metric.lower())
        if not column or column not in df.columns:
            # Try to find revenue columns
            revenue_cols = [col for col in df.columns if 'revenue' in col.lower()]
            if revenue_cols:
                column = revenue_cols[0]
            else:
                return {
                    "error": f"Metric '{metric}' not found",
                    "available_metrics": list(metric_mapping.keys()),
                    "status": "failed"
                }
        
        # Remove rows with null values and sort
        df_clean = df.dropna(subset=[column])
        # For debt metrics, show lowest first (best); for others, highest first
        ascending = True if metric.lower() in ['total_debt', 'cumulative_interest', 'cash_burden'] else False
        df_sorted = df_clean.sort_values(column, ascending=ascending).head(top_n)
        
        # Prepare ranking data
        ranking = df_sorted[['project_name', 'company_ticker', column]].copy()
        ranking['rank'] = range(1, len(ranking) + 1)
        
        return {
            "ranking": ranking.to_dict('records'),
            "metric": metric,
            "column_used": column,
            "top_n": top_n,
            "status": "success"
        }
    
    @tool_system.tool(
        name="calculate_rnav_sensitivity",
        description="Calculate RNAV sensitivity to parameter changes (ASP, costs, WACC, etc.) by regenerating full financial statements",
        parameters={
            "project_name": {
                "type": "string",
                "description": "Project name for sensitivity analysis",
                "required": True
            },
            "adjustments": {
                "type": "object",
                "description": "Parameter adjustments",
                "properties": {
                    "asp_change_pct": {"type": "number", "description": "ASP change % for both segments"},
                    "low_rise_asp_change_pct": {"type": "number", "description": "Low-rise ASP change %"},
                    "high_rise_asp_change_pct": {"type": "number", "description": "High-rise ASP change %"},
                    "construction_cost_change_pct": {"type": "number", "description": "Construction cost change %"},
                    "land_cost_change_pct": {"type": "number", "description": "Land cost change %"},
                    "sga_pct_change": {"type": "number", "description": "SG&A percentage point change"},
                    "wacc_change_bps": {"type": "number", "description": "WACC change in basis points"},
                    "cost_of_debt_change_bps": {"type": "number", "description": "Cost of debt change in basis points"}
                },
                "required": True
            },
            "output_format": {
                "type": "string",
                "description": "Output format (detailed, summary, comparison)",
                "required": False
            }
        }
    )
    def calculate_rnav_sensitivity(project_name: str, adjustments: Dict, output_format: str = "summary") -> Dict:
        """Calculate RNAV sensitivity by regenerating full financial statements"""
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            collection = tool_system.vietnam_stocks_db['RealEstateProjects']
            
            # Find project
            project = collection.find_one({"project_name": {"$regex": f"^{project_name}$", "$options": "i"}})
            
            if not project:
                return {"error": f"Project {project_name} not found", "status": "failed"}
            
            # Store original RNAV
            base_rnav = project.get('rnav_value', 0)
            
            # Apply adjustments to project parameters
            adjusted_project = project.copy()
            
            # Apply ASP changes
            if 'asp_change_pct' in adjustments:
                # Apply to both segments
                adjusted_project['low_rise_asp'] = project.get('low_rise_asp', 0) * (1 + adjustments['asp_change_pct'] / 100)
                adjusted_project['high_rise_asp'] = project.get('high_rise_asp', 0) * (1 + adjustments['asp_change_pct'] / 100)
            
            if 'low_rise_asp_change_pct' in adjustments:
                adjusted_project['low_rise_asp'] = project.get('low_rise_asp', 0) * (1 + adjustments['low_rise_asp_change_pct'] / 100)
            
            if 'high_rise_asp_change_pct' in adjustments:
                adjusted_project['high_rise_asp'] = project.get('high_rise_asp', 0) * (1 + adjustments['high_rise_asp_change_pct'] / 100)
            
            # Apply cost changes
            if 'construction_cost_change_pct' in adjustments:
                adjusted_project['construction_cost_per_sqm'] = project.get('construction_cost_per_sqm', 0) * (1 + adjustments['construction_cost_change_pct'] / 100)
            
            if 'land_cost_change_pct' in adjustments:
                adjusted_project['land_cost_per_sqm'] = project.get('land_cost_per_sqm', 0) * (1 + adjustments['land_cost_change_pct'] / 100)
            
            # Apply financial parameter changes
            if 'sga_pct_change' in adjustments:
                adjusted_project['sga_percentage'] = project.get('sga_percentage', 8.0) + adjustments['sga_pct_change']
            
            if 'wacc_change_bps' in adjustments:
                adjusted_project['wacc_rate'] = project.get('wacc_rate', 0.12) + adjustments['wacc_change_bps'] / 10000
            
            if 'cost_of_debt_change_bps' in adjustments:
                adjusted_project['cost_of_debt'] = project.get('cost_of_debt', 0.08) + adjustments['cost_of_debt_change_bps'] / 10000
            
            # Recalculate presales schedule with adjusted ASP
            presales_start = int(adjusted_project.get('sale_start_year', 2024))
            sales_years = int(adjusted_project.get('sales_years', 3))
            presales_end = presales_start + sales_years - 1
            price_increment = float(adjusted_project.get('price_increment_factor', 0))
            
            presales_schedule = {}
            for i, year in enumerate(range(presales_start, presales_end + 1)):
                # Low-rise presales
                low_dist = adjusted_project.get('low_rise_presales_distribution', {})
                low_pct = low_dist.get(str(year), 0) / 100 if low_dist else 0
                low_nsa = float(adjusted_project.get('low_rise_nsa', 0)) * low_pct
                low_asp = float(adjusted_project.get('low_rise_asp', 0)) * (1 + price_increment) ** i
                low_presale = low_nsa * low_asp
                
                # High-rise presales
                high_dist = adjusted_project.get('high_rise_presales_distribution', {})
                high_pct = high_dist.get(str(year), 0) / 100 if high_dist else 0
                high_nsa = float(adjusted_project.get('high_rise_nsa', 0)) * high_pct
                high_asp = float(adjusted_project.get('high_rise_asp', 0)) * (1 + price_increment) ** i
                high_presale = high_nsa * high_asp
                
                presales_schedule[year] = low_presale + high_presale
            
            # Import balance sheet manager
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from balance_sheet_manager import generate_balance_sheet_schedules
            from utils.RNAV_utils import RNAV_Calculation
            
            # Calculate total costs with adjustments
            total_construction = float(adjusted_project.get('gross_floor_area', 0)) * float(adjusted_project.get('construction_cost_per_sqm', 0))
            total_land = float(adjusted_project.get('land_area', 0)) * float(adjusted_project.get('land_cost_per_sqm', 0))
            
            # Get timeline parameters
            const_start = int(adjusted_project.get('construction_start_year', 2025))
            const_years = int(adjusted_project.get('construction_years', 3))
            const_end = const_start + const_years - 1
            
            land_payment_start = int(adjusted_project.get('land_payment_start_year', const_start))
            land_payment_years = int(adjusted_project.get('land_payment_years', 1))
            
            revenue_booking_start = int(adjusted_project.get('revenue_booking_start_year', const_end))
            revenue_booking_end = int(adjusted_project.get('project_completion_year', const_end + 1))
            
            # Generate balance sheet with adjusted parameters
            bs_df = generate_balance_sheet_schedules(
                total_debt=float(adjusted_project.get('total_debt', 0)),
                total_construction_cost=total_construction,
                total_land_cost=total_land,
                land_payment_start_year=land_payment_start,
                land_payment_years=land_payment_years,
                presales_schedule=presales_schedule,
                interest_rate=float(adjusted_project.get('cost_of_debt', 0.08)),
                sga_percentage=float(adjusted_project.get('sga_percentage', 0.08)),
                debt_disbursement_start_year=const_start,
                debt_disbursement_end_year=const_end,
                debt_repayment_start_year=revenue_booking_end,
                debt_repayment_end_year=revenue_booking_end,
                revenue_booking_start_year=revenue_booking_start,
                revenue_booking_end_year=revenue_booking_end,
                cash_collection_schedules=adjusted_project.get('cash_collection_schedules')
            )
            
            # Extract cash flows from balance sheet (matching actual RNAV calculation)
            project_start = min([y for y in bs_df['Year'] if isinstance(y, int)])
            project_end = max([y for y in bs_df['Year'] if isinstance(y, int)])
            current_year = 2024  # Use current year
            
            selling_progress = []
            construction_payment = []
            land_payment = []
            sga_payment = []
            tax_expense = []
            
            for year in range(project_start, project_end + 1):
                year_data = bs_df[bs_df["Year"] == year]
                if not year_data.empty:
                    selling_progress.append(float(year_data["Cash_Inflow_Presales"].iloc[0]) / 1e9)
                    construction_payment.append(float(year_data["Cash_Outflow_Construction"].iloc[0]) / 1e9)
                    land_payment.append(float(year_data["Cash_Outflow_Land"].iloc[0]) / 1e9)
                    sga_payment.append(float(year_data["Cash_Outflow_SGA"].iloc[0]) / 1e9)
                    tax_expense.append(float(year_data["Cash_Outflow_Tax"].iloc[0]) / 1e9)
                else:
                    selling_progress.append(0.0)
                    construction_payment.append(0.0)
                    land_payment.append(0.0)
                    sga_payment.append(0.0)
                    tax_expense.append(0.0)
            
            # Calculate new RNAV
            df_rnav = RNAV_Calculation(
                selling_progress,
                construction_payment,
                sga_payment,
                tax_expense,
                land_payment,
                float(adjusted_project.get('wacc_rate', 0.12)),
                int(project_start),
                int(current_year)
            )
            
            # Extract RNAV value
            total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
            if not total_row.empty:
                new_rnav = float(total_row["Discounted Cash Flow"].iloc[0]) * 1e9
            else:
                # Fallback to sum of discounted cash flows
                numeric_rows = df_rnav[df_rnav["Year"] != "Total RNAV"]
                new_rnav = float(numeric_rows["Discounted Cash Flow"].sum()) * 1e9
            
            # Prepare result based on output format
            result = {
                "project_name": project_name,
                "base_rnav": base_rnav,
                "adjusted_rnav": new_rnav,
                "change_amount": new_rnav - base_rnav,
                "change_percentage": ((new_rnav - base_rnav) / base_rnav * 100) if base_rnav != 0 else 0,
                "adjustments_applied": adjustments,
                "status": "success"
            }
            
            if output_format == "detailed":
                # Add detailed cash flow comparison
                result["cash_flows"] = {
                    "total_inflow": sum(selling_progress) * 1e9,
                    "total_construction": sum(construction_payment) * 1e9,
                    "total_land": sum(land_payment) * 1e9,
                    "total_sga": sum(sga_payment) * 1e9,
                    "total_tax": sum(tax_expense) * 1e9
                }
                result["rnav_details"] = df_rnav.to_dict('records')
            
            elif output_format == "comparison":
                # Add year-by-year comparison
                result["yearly_comparison"] = []
                for i, year in enumerate(range(project_start, project_end + 1)):
                    result["yearly_comparison"].append({
                        "year": year,
                        "cash_inflow": selling_progress[i] * 1e9 if i < len(selling_progress) else 0,
                        "net_cash_flow": (selling_progress[i] + construction_payment[i] + land_payment[i] + 
                                         sga_payment[i] + tax_expense[i]) * 1e9 if i < len(selling_progress) else 0
                    })
            
            return result
            
        except Exception as e:
            return {
                "error": f"Error calculating sensitivity: {str(e)}",
                "status": "failed"
            }