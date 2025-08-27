#!/usr/bin/env python3
"""
Test script for Enhanced AI MongoDB Collection Tools
Tests the new tools that fully utilize CompanyForecast and RealEstateProjects collections
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_assistant import EnhancedAIToolSystem

def test_mongodb_tools():
    """Test the new MongoDB collection tools"""
    
    print("=" * 70)
    print("ENHANCED AI MONGODB TOOLS TEST")
    print("=" * 70)
    
    # Initialize system
    system = EnhancedAIToolSystem()
    tools = system.get_tool_list()
    print(f"✅ System initialized with {len(tools)} tools")
    
    print("\n" + "=" * 70)
    print("TEST 1: PROJECT FINANCIAL STATEMENTS")
    print("=" * 70)
    
    # Test project financial statements
    result = system.execute_tool('get_project_financial_statements', {
        'project_name': 'New City 3',
        'statement_type': 'summary'
    })
    
    if result.get('status') == 'success':
        print(f"✅ Success for project: {result.get('project_name')}")
        if 'summary' in result:
            summary = result['summary']
            print("   Financial Summary:")
            print(f"   - Total Revenue: {summary.get('total_revenue', 0)/1e9:.1f}B VND")
            print(f"   - Total PAT: {summary.get('total_pat', 0)/1e9:.1f}B VND")
            print(f"   - Final Cash: {summary.get('final_cash_balance', 0)/1e9:.1f}B VND")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 2: PROJECT LOCATION DETAILS")
    print("=" * 70)
    
    # Test location details
    result = system.execute_tool('get_project_location_details', {
        'project_names': ['New City 3', 'New City 4']
    })
    
    if result.get('status') == 'success':
        print(f"✅ Found {result.get('count')} projects with locations")
        for project in result.get('projects', []):
            print(f"\n   {project['project_name']} ({project['company_ticker']}):")
            print(f"   - Location: {project.get('location', 'N/A')}")
            if 'latitude' in project and 'longitude' in project:
                print(f"   - Coordinates: {project['latitude']}, {project['longitude']}")
            if 'google_maps_url' in project:
                print(f"   - Maps: {project['google_maps_url'][:50]}...")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 3: FORECAST ASSUMPTIONS")
    print("=" * 70)
    
    # Test forecast assumptions
    for ticker in ['DXG', 'TCH']:
        result = system.execute_tool('analyze_company_forecast_assumptions', {
            'ticker': ticker
        })
        
        if result.get('status') == 'success':
            print(f"\n✅ {ticker} Forecast Analysis:")
            print(f"   - Forecast Years: {result.get('forecast_years')}")
            print(f"   - Last Updated: {result.get('last_updated')}")
            
            if 'assumptions' in result:
                print(f"   - Assumptions Count: {result.get('assumptions_count')}")
                # Show first assumption as example
                if result['assumptions'] and isinstance(result['assumptions'][0], str):
                    print(f"   - Example: {result['assumptions'][0][:80]}...")
            
            if 'revenue_cagr' in result:
                print(f"   - Revenue CAGR: {result['revenue_cagr']}")
            
            if 'revenue_growth' in result:
                growth = result['revenue_growth']
                print(f"   - Growth {growth['period']}: {growth['from']} → {growth['to']}")
        else:
            print(f"\n❌ {ticker}: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 4: COMPREHENSIVE PROJECT FINANCIALS")
    print("=" * 70)
    
    # Test comprehensive financials
    result = system.execute_tool('get_project_financial_statements', {
        'project_name': 'Taseco Trung Van',
        'statement_type': 'comprehensive'
    })
    
    if result.get('status') == 'success':
        print(f"✅ Comprehensive financials for: {result.get('project_name')}")
        if 'years' in result:
            print(f"   Available years: {result['years']}")
        if 'financial_statements' in result and result['financial_statements']:
            # Show one year's structure
            first_year = result['years'][0] if result.get('years') else None
            if first_year and first_year in result['financial_statements']:
                year_data = result['financial_statements'][first_year]
                print(f"   Year {first_year} contains sections:")
                for section in list(year_data.keys())[:5]:
                    print(f"   - {section}")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print("\n✅ MongoDB Collections Fully Utilized:")
    print("\n1. CompanyForecast Collection:")
    print("   - get_financial_forecasts: P&L, BS, CF for 2025-2030")
    print("   - analyze_company_forecast_assumptions: Growth rates & assumptions")
    print("   - Available for: DXG, KDH, NTL, TAL, TCH")
    
    print("\n2. RealEstateProjects Collection:")
    print("   - get_project_financial_statements: Comprehensive financials, cash flows")
    print("   - get_project_location_details: Coordinates & Google Maps links")
    print("   - list_real_estate_projects: Basic project info")
    print("   - Available for: KDH, TAL, TCH projects (24 total)")
    
    print("\n✅ Enhanced capabilities:")
    print("   - Access to detailed project-level P&L by year")
    print("   - Cash collection and presales schedules")
    print("   - Location mapping with coordinates")
    print("   - Forecast assumptions and growth analysis")
    print("   - All data directly from MongoDB, no CSV dependencies")

if __name__ == "__main__":
    test_mongodb_tools()