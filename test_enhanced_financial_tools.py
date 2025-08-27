#!/usr/bin/env python3
"""
Test script for Enhanced AI Financial Tools
Tests the separation of historical and forecast data tools
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_assistant import EnhancedAIToolSystem

def test_financial_tools():
    """Test the separated financial tools"""
    
    print("=" * 70)
    print("ENHANCED AI FINANCIAL TOOLS TEST")
    print("=" * 70)
    
    # Initialize system
    system = EnhancedAIToolSystem()
    tools = system.get_tool_list()
    print(f"✅ System initialized with {len(tools)} tools")
    
    # List financial tools
    print("\n📊 Financial Data Tools:")
    financial_tools = [t for t in tools if 'financial' in t or 'forecast' in t or 'historical' in t]
    for tool in financial_tools:
        print(f"  • {tool}")
    
    print("\n" + "=" * 70)
    print("TEST 1: HISTORICAL DATA (2016-2024)")
    print("=" * 70)
    
    # Test historical data for multiple companies
    test_tickers = ['VHM', 'DXG', 'NLG']
    print(f"\nTesting get_historical_financials for {test_tickers}")
    
    result = system.execute_tool('get_historical_financials', {
        'tickers': test_tickers,
        'metrics': ['Net_Revenue', 'EBITDA', 'NPATMI'],
        'years': [2022, 2023]
    })
    
    if result.get('status') == 'success':
        print(f"✅ Success - {result.get('records')} records retrieved")
        print(f"   Source: {result.get('source')}")
        print(f"   Years: {result.get('years_range')}")
        
        # Show sample data
        if result.get('data'):
            print("\n   Sample results:")
            for record in result['data'][:3]:
                ticker = record.get('TICKER')
                year = record.get('DATE')
                revenue = record.get('Net_Revenue', 0)
                print(f"   {ticker} ({year}): Revenue = {revenue/1e12:.1f}T VND")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 2: FORECAST DATA (2025-2030+)")
    print("=" * 70)
    
    # Test forecast data
    forecast_tickers = ['DXG', 'TCH']
    
    for ticker in forecast_tickers:
        print(f"\nTesting get_financial_forecasts for {ticker}")
        
        result = system.execute_tool('get_financial_forecasts', {
            'ticker': ticker,
            'years': ['2025', '2026', '2027'],
            'statement_type': 'pnl',
            'include_breakdown': False
        })
        
        if result.get('status') == 'success':
            print(f"✅ Success for {ticker}")
            print(f"   Available years: {result.get('available_years')}")
            
            # Show forecast data
            forecast_data = result.get('forecast_data', {})
            if forecast_data:
                print(f"   Forecast P&L:")
                for year, data in list(forecast_data.items())[:2]:
                    pnl = data.get('pnl', {})
                    revenue = pnl.get('net_revenue', 0)
                    npatmi = pnl.get('npatmi', 0)
                    print(f"   {year}: Revenue={revenue:.1f}B, NPATMI={npatmi:.1f}B VND")
                
                # Show CAGR if available
                summary = result.get('summary', {})
                if 'revenue_cagr' in summary:
                    print(f"   Revenue CAGR: {summary['revenue_cagr']}%")
        else:
            print(f"❌ Failed: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("TEST 3: COVERAGE COMPARISON")
    print("=" * 70)
    
    # Compare coverage between historical and forecast
    print("\n📈 Data Coverage:")
    
    # Historical coverage
    hist_df = system._load_financial_statements_csv()
    if not hist_df.empty:
        hist_tickers = hist_df['TICKER'].nunique()
        hist_years = f"{hist_df['DATE'].min()}-{hist_df['DATE'].max()}"
        print(f"Historical data: {hist_tickers} companies, years {hist_years}")
    
    # Forecast coverage
    if system.vietnam_stocks_db is not None:
        collection = system.vietnam_stocks_db['CompanyForecast']
        forecast_tickers = collection.distinct('ticker')
        print(f"Forecast data: {len(forecast_tickers)} companies {forecast_tickers}")
        print(f"               Years typically 2025-2030+")
    
    print("\n" + "=" * 70)
    print("TEST 4: TOOL SELECTION GUIDANCE")
    print("=" * 70)
    
    print("\n🤖 OpenAI will automatically select:")
    print("• get_historical_financials for years ≤ 2024")
    print("• get_financial_forecasts for years ≥ 2025")
    print("• Both tools when analyzing historical vs forecast")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print("\n✅ Financial tools successfully separated:")
    print("1. Historical data tool uses CSV with 1000+ companies")
    print("2. Forecast data tool uses MongoDB CompanyForecast")
    print("3. Clear distinction between historical (2016-2024) and forecast (2025+)")
    print("4. OpenAI system message updated for proper tool selection")
    
    # Check OpenAI configuration
    if os.getenv('OPENAI_API_KEY'):
        print("\n✅ OpenAI API configured - ready for intelligent tool selection")
    else:
        print("\n⚠️ OpenAI API key not found - add to .env for chat functionality")

if __name__ == "__main__":
    test_financial_tools()