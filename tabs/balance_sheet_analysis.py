#%%
import streamlit as st
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from balance_sheet_manager import generate_simplified_balance_sheet_schedules


class BalanceSheetAnalysisTab:
    """Balance Sheet Analysis tab for Real Estate Financial Model"""
    
    def __init__(self):
        self.init_session_state()
    
    def init_session_state(self):
        """Initialize session state variables for balance sheet analysis"""
        if 'bs_analysis_params' not in st.session_state:
            st.session_state.bs_analysis_params = {
                'total_debt': 1000000000000,  # 1,000B VND
                'total_construction_cost': 2000000000000,  # 2,000B VND
                'total_land_cost': 500000000000,  # 500B VND
                'land_payment_year': 2025,
                'total_revenue': 5000000000000,  # 5,000B VND
                'interest_rate': 0.1,  # 10%
                'sga_percentage': 0.05,  # 5% SG&A
                'construction_start_year': 2025,
                'construction_end_year': 2026,
                'sales_start_year': 2025,
                'sales_end_year': 2027,
                'debt_repayment_start_year': 2027,
                'debt_repayment_end_year': 2028,
                'revenue_booking_start_year': 2027,
                'revenue_booking_end_year': 2028,
                'use_custom_distribution': False,
                'custom_distribution': {},
                'use_revenue_distribution': False,
                'revenue_distribution': {}
            }
    
    def render(self):
        """Main render method for Balance Sheet Analysis tab"""
        st.header("📊 Balance Sheet Analysis")
        st.markdown("---")
        
        # Create two columns for input parameters
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Financial Parameters")
            
            # Financial inputs
            total_debt = st.number_input(
                "Total Debt (VND)",
                min_value=0.0,
                value=float(st.session_state.bs_analysis_params['total_debt']),
                step=1000000000.0,
                format="%f",
                help="Total debt amount to be disbursed"
            )
            
            total_construction_cost = st.number_input(
                "Total Construction Cost (VND)",
                min_value=0.0,
                value=float(st.session_state.bs_analysis_params['total_construction_cost']),
                step=1000000000.0,
                format="%f",
                help="Total construction cost for the project"
            )
            
            st.subheader("🏗️ Land Cost")
            
            land_cols = st.columns(2)
            with land_cols[0]:
                total_land_cost = st.number_input(
                    "Total Land Cost (VND)",
                    min_value=0.0,
                    value=float(st.session_state.bs_analysis_params['total_land_cost']),
                    step=1000000000.0,
                    format="%f",
                    help="Total land acquisition cost"
                )
            
            with land_cols[1]:
                land_payment_year = st.number_input(
                    "Land Payment Year",
                    min_value=2020,
                    max_value=2050,
                    value=st.session_state.bs_analysis_params['land_payment_year'],
                    step=1,
                    help="Year when land cost is paid"
                )
            
            total_revenue = st.number_input(
                "Total Revenue (VND)",
                min_value=0.0,
                value=float(st.session_state.bs_analysis_params['total_revenue']),
                step=1000000000.0,
                format="%f",
                help="Total revenue expected from the project"
            )
            
            interest_rate = st.number_input(
                "Interest Rate (%)",
                min_value=0.0,
                max_value=30.0,
                value=st.session_state.bs_analysis_params['interest_rate'] * 100,
                step=0.5,
                format="%.2f",
                help="Annual interest rate on debt"
            ) / 100
            
            sga_percentage = st.number_input(
                "SG&A (% of Revenue)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.bs_analysis_params['sga_percentage'] * 100,
                step=0.5,
                format="%.2f",
                help="Selling, General & Administrative expenses as % of revenue"
            ) / 100
            
            st.subheader("📅 Construction Timeline")
            
            construction_cols = st.columns(2)
            with construction_cols[0]:
                construction_start = st.number_input(
                    "Construction Start Year",
                    min_value=2020,
                    max_value=2050,
                    value=st.session_state.bs_analysis_params['construction_start_year'],
                    step=1
                )
            
            with construction_cols[1]:
                construction_end = st.number_input(
                    "Construction End Year",
                    min_value=construction_start,
                    max_value=2050,
                    value=max(construction_start, st.session_state.bs_analysis_params['construction_end_year']),
                    step=1
                )
        
        with col2:
            st.subheader("💰 Sales & Revenue Timeline")
            
            sales_cols = st.columns(2)
            with sales_cols[0]:
                sales_start = st.number_input(
                    "Sales Start Year",
                    min_value=2020,
                    max_value=2050,
                    value=st.session_state.bs_analysis_params['sales_start_year'],
                    step=1
                )
            
            with sales_cols[1]:
                sales_end = st.number_input(
                    "Sales End Year",
                    min_value=sales_start,
                    max_value=2050,
                    value=max(sales_start, st.session_state.bs_analysis_params['sales_end_year']),
                    step=1
                )
            
            st.subheader("💳 Debt Repayment Timeline")
            
            repayment_cols = st.columns(2)
            with repayment_cols[0]:
                debt_repayment_start = st.number_input(
                    "Debt Repayment Start Year",
                    min_value=2020,
                    max_value=2050,
                    value=st.session_state.bs_analysis_params['debt_repayment_start_year'],
                    step=1
                )
            
            with repayment_cols[1]:
                debt_repayment_end = st.number_input(
                    "Debt Repayment End Year",
                    min_value=debt_repayment_start,
                    max_value=2050,
                    value=max(debt_repayment_start, st.session_state.bs_analysis_params['debt_repayment_end_year']),
                    step=1
                )
            
            st.subheader("📝 Revenue Recognition Timeline")
            
            booking_cols = st.columns(2)
            with booking_cols[0]:
                revenue_booking_start = st.number_input(
                    "Revenue Booking Start Year",
                    min_value=2020,
                    max_value=2050,
                    value=st.session_state.bs_analysis_params['revenue_booking_start_year'],
                    step=1
                )
            
            with booking_cols[1]:
                revenue_booking_end = st.number_input(
                    "Revenue Booking End Year",
                    min_value=revenue_booking_start,
                    max_value=2050,
                    value=max(revenue_booking_start, st.session_state.bs_analysis_params['revenue_booking_end_year']),
                    step=1
                )
        
        # Custom Distribution Section
        st.markdown("---")
        st.subheader("📊 Sales Distribution")
        
        use_custom = st.checkbox(
            "Use Custom Sales Distribution",
            value=st.session_state.bs_analysis_params['use_custom_distribution'],
            help="Enable to specify custom percentage distribution for sales across years"
        )
        
        custom_distribution = {}
        if use_custom:
            st.info("Enter the percentage of total sales for each year (must sum to 100%)")
            
            sales_years = list(range(sales_start, sales_end + 1))
            cols = st.columns(min(len(sales_years), 4))
            
            total_pct = 0
            for i, year in enumerate(sales_years):
                with cols[i % len(cols)]:
                    pct = st.number_input(
                        f"Year {year} (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=st.session_state.bs_analysis_params.get('custom_distribution', {}).get(str(year), 100.0/len(sales_years)),
                        step=5.0,
                        key=f"dist_{year}"
                    )
                    custom_distribution[str(year)] = pct
                    total_pct += pct
            
            if abs(total_pct - 100.0) > 0.1:
                st.warning(f"⚠️ Distribution percentages sum to {total_pct:.1f}%. Should sum to 100%")
        
        # Revenue Recognition Distribution Section
        st.markdown("---")
        st.subheader("💰 Revenue Recognition Distribution")
        
        use_revenue_custom = st.checkbox(
            "Use Custom Revenue Recognition Distribution",
            value=st.session_state.bs_analysis_params['use_revenue_distribution'],
            help="Enable to specify custom percentage distribution for revenue recognition across years"
        )
        
        revenue_distribution = {}
        if use_revenue_custom:
            st.info("Enter the percentage of total revenue to recognize each year (must sum to 100%)")
            
            revenue_years = list(range(revenue_booking_start, revenue_booking_end + 1))
            rev_cols = st.columns(min(len(revenue_years), 4))
            
            total_rev_pct = 0
            for i, year in enumerate(revenue_years):
                with rev_cols[i % len(rev_cols)]:
                    rev_pct = st.number_input(
                        f"Year {year} (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=st.session_state.bs_analysis_params.get('revenue_distribution', {}).get(str(year), 100.0/len(revenue_years)),
                        step=5.0,
                        key=f"rev_dist_{year}"
                    )
                    revenue_distribution[str(year)] = rev_pct
                    total_rev_pct += rev_pct
            
            if abs(total_rev_pct - 100.0) > 0.1:
                st.warning(f"⚠️ Revenue distribution percentages sum to {total_rev_pct:.1f}%. Should sum to 100%")
        
        # Update session state
        st.session_state.bs_analysis_params.update({
            'total_debt': total_debt,
            'total_construction_cost': total_construction_cost,
            'total_land_cost': total_land_cost,
            'land_payment_year': land_payment_year,
            'total_revenue': total_revenue,
            'interest_rate': interest_rate,
            'sga_percentage': sga_percentage,
            'construction_start_year': construction_start,
            'construction_end_year': construction_end,
            'sales_start_year': sales_start,
            'sales_end_year': sales_end,
            'debt_repayment_start_year': debt_repayment_start,
            'debt_repayment_end_year': debt_repayment_end,
            'revenue_booking_start_year': revenue_booking_start,
            'revenue_booking_end_year': revenue_booking_end,
            'use_custom_distribution': use_custom,
            'custom_distribution': custom_distribution if use_custom else {},
            'use_revenue_distribution': use_revenue_custom,
            'revenue_distribution': revenue_distribution if use_revenue_custom else {}
        })
        
        # Run Analysis Button
        st.markdown("---")
        if st.button("🔍 Run Balance Sheet Analysis", type="primary", use_container_width=True):
            self.run_analysis()
    
    def run_analysis(self):
        """Run the balance sheet analysis and display results"""
        params = st.session_state.bs_analysis_params
        
        try:
            # Generate balance sheet schedules
            df = generate_simplified_balance_sheet_schedules(
                total_debt=params['total_debt'],
                total_construction_cost=params['total_construction_cost'],
                total_land_cost=params['total_land_cost'],
                land_payment_year=params['land_payment_year'],
                total_revenue=params['total_revenue'],
                interest_rate=params['interest_rate'],
                sga_percentage=params['sga_percentage'],
                construction_start_year=params['construction_start_year'],
                construction_end_year=params['construction_end_year'],
                sales_start_year=params['sales_start_year'],
                sales_end_year=params['sales_end_year'],
                debt_repayment_start_year=params['debt_repayment_start_year'],
                debt_repayment_end_year=params['debt_repayment_end_year'],
                revenue_booking_start_year=params['revenue_booking_start_year'],
                revenue_booking_end_year=params['revenue_booking_end_year'],
                presales_distribution=params['custom_distribution'] if params['use_custom_distribution'] else None,
                revenue_distribution=params['revenue_distribution'] if params['use_revenue_distribution'] else None
            )
            
            # Display Results
            st.success("✅ Analysis completed successfully!")
            
            # Display summary tables directly without tabs
            self.display_summary_tables(df)
            
            # Store results in session state for export
            st.session_state['bs_analysis_results'] = df
            
        except Exception as e:
            st.error(f"❌ Error running analysis: {str(e)}")
    
    def display_summary_tables(self, df):
        """Display summary tables of the analysis"""
        st.subheader("Balance Sheet Schedules")
        
        # Format the dataframe for display (exclude Total row for now)
        display_df = df[df['Year'] != 'Total'].copy()
        
        # Convert to billions VND for better readability
        value_columns = [col for col in df.columns if col != 'Year']
        for col in value_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col] / 1e9
        
        # Transpose the dataframe - years as columns, items as rows
        # Set Year as index first
        display_df = display_df.set_index('Year')
        # Transpose so years become columns
        display_df = display_df.T
        
        # Rename index with more readable labels
        index_labels = {
            'Debt_Disbursement': 'Debt Disbursement (Inflow)',
            'Debt_Repayment': 'Debt Repayment (Outflow)',
            'Debt_Balance': 'Debt Balance (Outstanding)',
            'Land_Cost': 'Land Cost',
            'Construction_Cost': 'Construction Cost',
            'Interest_Capitalized': 'Interest Capitalized',
            'Interest_Expense_Cash': 'Interest Expense (P&L)',
            'SGA_Expense': 'SG&A Expense (P&L)',
            'Inventory_Addition': 'Inventory Addition',
            'Inventory_Balance': 'Inventory Balance',
            'Revenue_Recognition': 'Revenue Recognition',
            'COGS': 'Cost of Goods Sold',
            'Cash_Inflow_Presales': 'Cash Inflow (Presales)',
            'Cash_Outflow_Land': 'Cash Outflow (Land)',
            'Cash_Outflow_Construction': 'Cash Outflow (Construction)',
            'Cash_Outflow_Interest': 'Cash Outflow (Interest)',
            'Cash_Outflow_SGA': 'Cash Outflow (SG&A)',
            'Cash_Balance_Change': 'Cash Balance Change',
            'Cumulative_Cash_Balance': 'Cumulative Cash Balance'
        }
        display_df.index = display_df.index.map(lambda x: index_labels.get(x, x))
        display_df.index.name = 'Balance Sheet Item'
        
        # Create format dictionary for all year columns
        format_dict = {col: "{:.1f}" for col in display_df.columns}
        
        # Format with 1 decimal place
        st.dataframe(
            display_df.style.format(format_dict),
            use_container_width=True,
            height=500
        )
