"""
Test script to load real VHM forecast data from MongoDB
Run this in Streamlit environment or with proper dependencies
"""

import sys
import os
import json

# Ensure we can import from utils
sys.path.insert(0, os.path.dirname(__file__))

from utils.mongodb_utils import load_company_forecast

print("=" * 80)
print("Loading VHM Forecast Data from MongoDB CompanyForecast Collection")
print("=" * 80)

# Load VHM forecast
ticker = "VHM"
forecast_doc = load_company_forecast(ticker)

if not forecast_doc:
    print(f"\n❌ No forecast data found for {ticker}")
    print("Make sure you have run the Model Forecast tab and saved forecasts to MongoDB")
else:
    print(f"\n✅ Forecast data loaded for {ticker}")
    
    # Remove MongoDB _id field for cleaner display
    if '_id' in forecast_doc:
        del forecast_doc['_id']
    
    print("\n" + "=" * 80)
    print("FULL FORECAST DOCUMENT:")
    print("=" * 80)
    print(json.dumps(forecast_doc, indent=2, default=str))
    
    print("\n" + "=" * 80)
    print("KEY SECTIONS:")
    print("=" * 80)
    
    # Show forecast years
    print("\n1. FORECAST YEARS AVAILABLE:")
    forecast_years = forecast_doc.get('forecast_years', [])
    print(f"   {forecast_years}")
    
    # Show 2025 forecast (if available)
    if '2025' in forecast_doc.get('forecast_data', {}):
        print("\n2. FY 2025 FORECAST:")
        fy2025 = forecast_doc['forecast_data']['2025']
        
        if 'pnl' in fy2025:
            print("\n   P&L:")
            pnl = fy2025['pnl']
            print(f"   - Revenue: {pnl.get('net_revenue', 'N/A')} bn VND")
            print(f"   - Gross Profit: {pnl.get('gross_profit', 'N/A')} bn VND")
            print(f"   - EBITDA: {pnl.get('ebitda', 'N/A')} bn VND")
            print(f"   - NPATMI: {pnl.get('npatmi', 'N/A')} bn VND")
    
    # Show valuation data
    if 'valuation_data' in forecast_doc:
        print("\n3. VALUATION METRICS:")
        val_data = forecast_doc['valuation_data']
        
        print(f"\n   Current Price: {val_data.get('current_price', 'N/A')} VND")
        print(f"   RNAV per Share: {val_data.get('rnav_per_share', 'N/A')} VND")
        
        current_price = val_data.get('current_price', 0)
        rnav = val_data.get('rnav_per_share', 0)
        if current_price and rnav:
            upside = ((rnav / current_price - 1) * 100)
            print(f"   Upside to RNAV: {upside:.1f}%")
        
        multiples = val_data.get('multiples', {})
        if multiples:
            print("\n   Trading Multiples:")
            print(f"   - Trailing P/E: {multiples.get('trailing_PE', 'N/A')}x")
            print(f"   - 2025F P/E: {multiples.get('2025F_PE', 'N/A')}x")
            print(f"   - 2026F P/E: {multiples.get('2026F_PE', 'N/A')}x")
            print(f"   - Mean P/E: {multiples.get('mean_PE', 'N/A')}x")
            print(f"   - Trailing P/B: {multiples.get('trailing_PB', 'N/A')}x")
            print(f"   - 2025F P/B: {multiples.get('2025F_PB', 'N/A')}x")
            print(f"   - Mean P/B: {multiples.get('mean_PB', 'N/A')}x")

print("\n" + "=" * 80)
print("Test Complete!")
print("=" * 80)

