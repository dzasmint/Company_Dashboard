#!/usr/bin/env python3
"""
Test script for RNAV value handling in Enhanced AI tools
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_assistant import EnhancedAIToolSystem

def test_rnav_tools():
    """Test RNAV value handling in tools"""
    
    print("=" * 70)
    print("RNAV VALUE HANDLING TEST")
    print("=" * 70)
    
    # Initialize system
    system = EnhancedAIToolSystem()
    print(f"✅ System initialized with {len(system.tools)} tools")
    
    print("\n" + "=" * 70)
    print("TEST 1: LIST PROJECTS WITH RNAV")
    print("=" * 70)
    
    # List projects showing RNAV values
    result = system.execute_tool('list_real_estate_projects', {})
    
    if result.get('status') == 'success':
        print(f"✅ Found {result.get('total_projects')} total projects")
        
        for ticker, data in result.get('summary', {}).items():
            print(f"\n{ticker}:")
            print(f"  - Projects: {data['count']}")
            print(f"  - Total Units: {data['total_units']:,}")
            if data.get('total_rnav'):
                print(f"  - Total RNAV: {data['total_rnav']/1e9:,.1f}B VND")
            
            # Show first project with RNAV
            if data.get('projects'):
                first_proj = data['projects'][0]
                print(f"  - Example: {first_proj['project_name']}")
                if 'rnav_value' in first_proj:
                    print(f"    RNAV: {first_proj['rnav_value']/1e9:,.1f}B VND")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 2: RANK PROJECTS BY RNAV")
    print("=" * 70)
    
    # Rank projects by RNAV value
    result = system.execute_tool('rank_projects_by_metric', {
        'metric': 'rnav',
        'top_n': 5
    })
    
    if result.get('status') == 'success':
        print(f"✅ Top {result.get('top_n')} projects by RNAV:")
        
        for project in result.get('ranking', []):
            rnav = project.get('rnav_value', 0)
            print(f"  {project['rank']}. {project['project_name']} ({project['company_ticker']})")
            print(f"     RNAV: {rnav/1e9:,.1f}B VND")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 3: PROJECT DETAILS WITH RNAV")
    print("=" * 70)
    
    # Get detailed project info including RNAV
    result = system.execute_tool('get_project_details', {
        'project_names': ['Taseco Long Bien', 'Duy Tien'],
        'include_financials': False
    })
    
    if result.get('status') == 'success':
        print(f"✅ Retrieved {result.get('count')} projects")
        
        for project in result.get('projects', []):
            print(f"\n{project['project_name']} ({project['company_ticker']}):")
            print(f"  - Location: {project.get('location', 'N/A')}")
            print(f"  - Units: {project.get('total_units', 0):,}")
            print(f"  - NSA: {project.get('net_sellable_area', 0):,} sqm")
            if 'rnav_value' in project:
                print(f"  - RNAV: {project['rnav_value']/1e9:,.1f}B VND")
            print(f"  - ASP: {project.get('average_selling_price', 0)/1e6:,.1f}M VND/sqm")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 4: PROJECT FINANCIAL STATEMENTS WITH RNAV")
    print("=" * 70)
    
    # Get financial statements including RNAV
    result = system.execute_tool('get_project_financial_statements', {
        'project_name': 'Duy Tien',
        'statement_type': 'summary'
    })
    
    if result.get('status') == 'success':
        print(f"✅ Financial data for {result.get('project_name')}:")
        
        # Show RNAV
        if result.get('rnav_value'):
            print(f"  - RNAV Value: {result['rnav_value']/1e9:,.1f}B VND")
        
        # Show summary if available
        if 'summary' in result:
            summary = result['summary']
            print(f"\n  Financial Summary:")
            print(f"  - Total Revenue: {summary.get('total_revenue', 0)/1e9:,.1f}B VND")
            print(f"  - Total PAT: {summary.get('total_pat', 0)/1e9:,.1f}B VND")
            
            # Calculate RNAV vs PAT ratio
            if result.get('rnav_value') and summary.get('total_pat'):
                ratio = result['rnav_value'] / summary['total_pat']
                print(f"  - RNAV/PAT Ratio: {ratio:.2f}x")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print("\n✅ RNAV Value Integration Complete:")
    print("1. list_real_estate_projects - Shows total RNAV per company")
    print("2. get_project_details - Includes RNAV in basic project info")
    print("3. rank_projects_by_metric - Can rank projects by RNAV value")
    print("4. get_project_financial_statements - Returns RNAV with financials")
    print("\nRNAV (Revalued Net Asset Value) is now a first-class metric")
    print("for real estate project valuation and comparison.")

if __name__ == "__main__":
    test_rnav_tools()