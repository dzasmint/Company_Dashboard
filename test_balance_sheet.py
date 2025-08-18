#!/usr/bin/env python3
"""Test balance sheet with actual cash collection"""

import pandas as pd
from balance_sheet_manager import generate_simplified_balance_sheet_schedules

# Test scenario matching Taseco Long Bien
print("\n" + "="*80)
print("TEST: Balance Sheet with Actual Cash Collection")
print("="*80)

# Simple test case
total_revenue = 1000  # billion VND
presales_distribution = {
    '2025': 40,  # 400 Bn presales in 2025
    '2026': 60,  # 600 Bn presales in 2026
}

# Revenue recognition in 2027
revenue_distribution = {
    '2027': 100,  # All revenue in 2027
}

result_df = generate_simplified_balance_sheet_schedules(
    total_revenue=total_revenue,
    total_construction_cost=500,
    total_land_cost=100,
    total_debt=400,
    interest_rate=0.08,
    sga_percentage=0.05,
    construction_start_year=2025,
    construction_end_year=2026,
    land_payment_year=2025,
    sales_start_year=2025,
    sales_end_year=2026,
    debt_repayment_start_year=2027,
    debt_repayment_end_year=2027,
    revenue_booking_start_year=2027,
    revenue_booking_end_year=2027,  # Revenue ends in 2027
    presales_distribution=presales_distribution,
    revenue_distribution=revenue_distribution
)

print("\nKey Columns:")
key_columns = ['Year', 'Presales', 'Cash_Inflow_Presales', 'Revenue_Recognition', 'Customer_Prepayment_Balance']
display_df = result_df[key_columns].copy()

for idx, row in display_df.iterrows():
    if row['Year'] != 'Total':
        print(f"\nYear {int(row['Year'])}:")
        print(f"  Presales (Booking):        {row['Presales']:8.0f} Bn")
        print(f"  Cash Collected:            {row['Cash_Inflow_Presales']:8.0f} Bn")
        print(f"  Revenue Recognized:        {row['Revenue_Recognition']:8.0f} Bn")
        print(f"  Customer Prepayment Bal:   {row['Customer_Prepayment_Balance']:8.0f} Bn")

print("\n" + "="*80)
print("VERIFICATION:")
print("="*80)

# Check that cash collection doesn't extend beyond 2027
cash_2028 = display_df[display_df['Year'] == 2028]['Cash_Inflow_Presales'].iloc[0] if 2028 in display_df['Year'].values else 0
if cash_2028 == 0:
    print("✅ No cash collection in 2028 (correct - revenue ends in 2027)")
else:
    print(f"❌ Cash collection found in 2028: {cash_2028:.0f} Bn (should be 0)")

# Check customer prepayment balance
prepayment_2027 = display_df[display_df['Year'] == 2027]['Customer_Prepayment_Balance'].iloc[0]
if prepayment_2027 >= 0:
    print(f"✅ Customer prepayment balance in 2027 is non-negative: {prepayment_2027:.0f} Bn")
else:
    print(f"❌ Customer prepayment balance in 2027 is negative: {prepayment_2027:.0f} Bn")