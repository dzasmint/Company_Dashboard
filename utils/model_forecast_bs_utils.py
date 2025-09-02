"""
Utility functions for Model Forecast Balance Sheet tabs
"""
import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional


def render_detail_bs_tab(
    df_projects: pd.DataFrame,
    hist_col: str,
    years: List[int],
    base_year_str: str,
    hist_debt: float,
    hist_inventory: float,
    hist_customer_prepayment: float,
    debt_breakdown: Dict,
    inventory_breakdown: Dict,
    prepayment_breakdown: Dict,
    cash_breakdown: Dict,
    debt_change_breakdown: Dict,
    inventory_change_breakdown: Dict,
    prepayment_change_breakdown: Dict,
    cash_change_breakdown: Dict,
    total_debt_by_year: Dict,
    total_inventory_by_year: Dict,
    total_customer_prepayment_by_year: Dict,
    format_bs_value: callable
) -> None:
    """
    Render the detail balance sheet tab showing project-level breakdown
    
    Args:
        df_projects: DataFrame containing project data
        hist_col: Historical column name
        years: List of forecast years
        base_year_str: Base year as string
        hist_debt: Historical debt value
        hist_inventory: Historical inventory value
        hist_customer_prepayment: Historical customer prepayment value
        debt_breakdown: Dictionary of debt breakdown by project
        inventory_breakdown: Dictionary of inventory breakdown by project
        prepayment_breakdown: Dictionary of prepayment breakdown by project
        cash_breakdown: Dictionary of cash breakdown by project
        debt_change_breakdown: Dictionary to populate with debt changes
        inventory_change_breakdown: Dictionary to populate with inventory changes
        prepayment_change_breakdown: Dictionary to populate with prepayment changes
        cash_change_breakdown: Dictionary to populate with cash changes
        total_debt_by_year: Total debt by year
        total_inventory_by_year: Total inventory by year
        total_customer_prepayment_by_year: Total customer prepayment by year
        format_bs_value: Function to format balance sheet values
    """
    # Detail Project Breakdown Balance Sheet content
    bs_rows = []
    
    # Build Detail Project Breakdown Balance Sheet
    for _, project in df_projects.iterrows():
        project_name = project.get('project_name', 'Unknown')
        financial_statements = project.get('comprehensive_financial_statements', {})
        
        # Ensure financial_statements is a dictionary
        if not isinstance(financial_statements, dict):
            financial_statements = {}
    
        # Initialize project breakdown
        debt_breakdown[project_name] = {hist_col: 0}
        inventory_breakdown[project_name] = {hist_col: 0}
        prepayment_breakdown[project_name] = {hist_col: 0}
        cash_breakdown[project_name] = {hist_col: 0}
    
        # Track cumulative cash for this project
        project_cumulative_cash = 0
    
        for year in years:
            year_str = str(year)
            debt_breakdown[project_name][year_str] = 0
            inventory_breakdown[project_name][year_str] = 0
            prepayment_breakdown[project_name][year_str] = 0
            cash_breakdown[project_name][year_str] = 0
        
            if year_str in financial_statements:
                year_data = financial_statements[year_str]
            
                # Get debt for this project
                if 'debt_balance' in year_data:
                    debt_breakdown[project_name][year_str] = year_data.get('debt_balance', 0) / 1e9
                elif 'Debt_Balance' in year_data:
                    debt_breakdown[project_name][year_str] = year_data.get('Debt_Balance', 0) / 1e9
            
                # Get inventory for this project
                if 'inventory_balance' in year_data:
                    inventory_breakdown[project_name][year_str] = year_data.get('inventory_balance', 0) / 1e9
                elif 'Inventory_Balance' in year_data:
                    inventory_breakdown[project_name][year_str] = year_data.get('Inventory_Balance', 0) / 1e9
            
                # Get customer prepayment for this project
                if 'customer_prepayment_balance' in year_data:
                    prepayment_breakdown[project_name][year_str] = year_data.get('customer_prepayment_balance', 0) / 1e9
                elif 'Customer_Prepayment_Balance' in year_data:
                    prepayment_breakdown[project_name][year_str] = year_data.get('Customer_Prepayment_Balance', 0) / 1e9
            
                # Get cash for this project
                if 'cumulative_cash_balance' in year_data:
                    cash_breakdown[project_name][year_str] = year_data.get('cumulative_cash_balance', 0) / 1e9
                elif 'Cumulative_Cash_Balance' in year_data:
                    cash_breakdown[project_name][year_str] = year_data.get('Cumulative_Cash_Balance', 0) / 1e9
                elif 'cash_balance_change' in year_data or 'Cash_Balance_Change' in year_data:
                    cash_change = year_data.get('cash_balance_change', year_data.get('Cash_Balance_Change', 0)) / 1e9
                    project_cumulative_cash += cash_change
                    cash_breakdown[project_name][year_str] = project_cumulative_cash

    # Create balance sheet rows with breakdown
    # Note: Individual project rows show the project's balance at each year
    # Total rows show cumulative company-wide balance (historical + all project changes)

    # DEBT SECTION - Show changes for each project
    # Calculate debt changes for each project
    for project_name in debt_breakdown.keys():
        debt_change_breakdown[project_name] = {}
        prev_value = 0  # Projects start with 0 debt in historical year
        
        # Check if project has historical debt
        financial_statements = None
        for _, project in df_projects.iterrows():
            if project.get('project_name', 'Unknown') == project_name:
                financial_statements = project.get('comprehensive_financial_statements', {})
                break
        
        if financial_statements and base_year_str in financial_statements:
            hist_data = financial_statements[base_year_str]
            if 'debt_balance' in hist_data:
                prev_value = hist_data.get('debt_balance', 0) / 1e9
            elif 'Debt_Balance' in hist_data:
                prev_value = hist_data.get('Debt_Balance', 0) / 1e9
        
        for year in years:
            year_str = str(year)
            current_value = debt_breakdown[project_name].get(year_str, 0)
            change = current_value - prev_value
            debt_change_breakdown[project_name][year_str] = change
            prev_value = current_value
    
    # Add individual project debt change rows
    for project_name in debt_change_breakdown.keys():
        project_debt_row = {'Balance Sheet Item': f'  {project_name} Debt Change'}
        project_debt_row[hist_col] = 0  # No historical changes
        for year in years:
            project_debt_row[str(year)] = debt_change_breakdown[project_name][str(year)]
        bs_rows.append(project_debt_row)

    # Total Debt row (previous year + sum of changes)
    debt_row = {'Balance Sheet Item': 'TOTAL DEBT'}
    debt_row[hist_col] = hist_debt
    for year in years:
        debt_row[str(year)] = total_debt_by_year[str(year)]
    bs_rows.append(debt_row)

    # INVENTORY SECTION - Show changes for each project
    # Calculate inventory changes for each project
    for project_name in inventory_breakdown.keys():
        inventory_change_breakdown[project_name] = {}
        prev_value = 0  # Projects start with 0 inventory in historical year
        
        # Check if project has historical inventory
        financial_statements = None
        for _, project in df_projects.iterrows():
            if project.get('project_name', 'Unknown') == project_name:
                financial_statements = project.get('comprehensive_financial_statements', {})
                break
        
        if financial_statements and base_year_str in financial_statements:
            hist_data = financial_statements[base_year_str]
            if 'inventory_balance' in hist_data:
                prev_value = hist_data.get('inventory_balance', 0) / 1e9
            elif 'Inventory_Balance' in hist_data:
                prev_value = hist_data.get('Inventory_Balance', 0) / 1e9
        
        for year in years:
            year_str = str(year)
            current_value = inventory_breakdown[project_name].get(year_str, 0)
            change = current_value - prev_value
            inventory_change_breakdown[project_name][year_str] = change
            prev_value = current_value
    
    # Add individual project inventory change rows
    for project_name in inventory_change_breakdown.keys():
        project_inv_row = {'Balance Sheet Item': f'  {project_name} Inventory Change'}
        project_inv_row[hist_col] = 0  # No historical changes
        for year in years:
            project_inv_row[str(year)] = inventory_change_breakdown[project_name][str(year)]
        bs_rows.append(project_inv_row)

    # Total Inventory row (previous year + sum of changes)
    inventory_row = {'Balance Sheet Item': 'TOTAL INVENTORY'}
    inventory_row[hist_col] = hist_inventory
    for year in years:
        inventory_row[str(year)] = total_inventory_by_year[str(year)]
    bs_rows.append(inventory_row)

    # CUSTOMER PREPAYMENT SECTION - Show changes for each project
    # Calculate prepayment changes for each project
    for project_name in prepayment_breakdown.keys():
        prepayment_change_breakdown[project_name] = {}
        prev_value = 0  # Projects start with 0 prepayment in historical year
        
        # Check if project has historical prepayment
        financial_statements = None
        for _, project in df_projects.iterrows():
            if project.get('project_name', 'Unknown') == project_name:
                financial_statements = project.get('comprehensive_financial_statements', {})
                break
        
        if financial_statements and base_year_str in financial_statements:
            hist_data = financial_statements[base_year_str]
            if 'customer_prepayment_balance' in hist_data:
                prev_value = hist_data.get('customer_prepayment_balance', 0) / 1e9
            elif 'Customer_Prepayment_Balance' in hist_data:
                prev_value = hist_data.get('Customer_Prepayment_Balance', 0) / 1e9
        
        for year in years:
            year_str = str(year)
            current_value = prepayment_breakdown[project_name].get(year_str, 0)
            change = current_value - prev_value
            prepayment_change_breakdown[project_name][year_str] = change
            prev_value = current_value
    
    # Add individual project prepayment change rows
    for project_name in prepayment_change_breakdown.keys():
        project_prep_row = {'Balance Sheet Item': f'  {project_name} Prepayment Change'}
        project_prep_row[hist_col] = 0  # No historical changes
        for year in years:
            project_prep_row[str(year)] = prepayment_change_breakdown[project_name][str(year)]
        bs_rows.append(project_prep_row)

    # Total Customer Prepayment row (previous year + sum of changes)
    prepayment_row = {'Balance Sheet Item': 'TOTAL CUSTOMER PREPAYMENT'}
    prepayment_row[hist_col] = hist_customer_prepayment
    for year in years:
        prepayment_row[str(year)] = total_customer_prepayment_by_year[str(year)]
    bs_rows.append(prepayment_row)

    # CASH SECTION - Show changes for each project
    # Calculate cash changes for each project
    for project_name in cash_breakdown.keys():
        cash_change_breakdown[project_name] = {}
        prev_value = 0  # Projects start with 0 cash in historical year
        
        # Check if project has historical cash
        financial_statements = None
        for _, project in df_projects.iterrows():
            if project.get('project_name', 'Unknown') == project_name:
                financial_statements = project.get('comprehensive_financial_statements', {})
                break
        
        if financial_statements and base_year_str in financial_statements:
            hist_data = financial_statements[base_year_str]
            if 'cumulative_cash_balance' in hist_data:
                prev_value = hist_data.get('cumulative_cash_balance', 0) / 1e9
            elif 'Cumulative_Cash_Balance' in hist_data:
                prev_value = hist_data.get('Cumulative_Cash_Balance', 0) / 1e9
        
        for year in years:
            year_str = str(year)
            current_value = cash_breakdown[project_name].get(year_str, 0)
            change = current_value - prev_value
            cash_change_breakdown[project_name][year_str] = change
            prev_value = current_value
    
    # Add individual project cash change rows
    for project_name in cash_change_breakdown.keys():
        project_cash_row = {'Balance Sheet Item': f'  {project_name} Cash Change'}
        project_cash_row[hist_col] = 0  # No historical changes
        for year in years:
            project_cash_row[str(year)] = cash_change_breakdown[project_name][str(year)]
        bs_rows.append(project_cash_row)

    # Total Cash row (previous year + sum of changes)
    cash_row = {'Balance Sheet Item': 'TOTAL CASH'}
    cash_row[hist_col] = 0  # Start with 0 for project cash (no historical project breakdown)
    cumulative_cash = 0  # Start from 0 for projects
    for year in years:
        year_str = str(year)
        # Sum cash changes from all projects for this year
        total_cash_change = sum(
            cash_change_breakdown[project_name].get(year_str, 0) 
            for project_name in cash_change_breakdown.keys()
        )
        cumulative_cash += total_cash_change
        cash_row[year_str] = cumulative_cash
    bs_rows.append(cash_row)

    # Create DataFrame
    bs_df = pd.DataFrame(bs_rows)

    st.write("**Detailed Project Breakdown Balance Sheet Items (Billion VND)**")

    # Style function to highlight key rows and color code changes
    def style_bs_table(row):
        item = str(row['Balance Sheet Item'])
        # Total rows - bold with background
        if item in ['TOTAL DEBT', 'TOTAL INVENTORY', 'TOTAL CUSTOMER PREPAYMENT', 'TOTAL CASH']:
            return ['font-weight: bold; background-color: #e6f2ff'] * len(row)
        # Debt change rows - color code based on value
        elif 'Debt Change' in item:
            styles = ['padding-left: 20px']  # First column (item name)
            styles.append('')  # Historical column
            # Color code each year's value
            for year in years:
                val = row.get(str(year), 0)
                if pd.notna(val) and val != 0:
                    if val > 0:
                        styles.append('color: #28a745; font-weight: 600')  # Green for increase
                    elif val < 0:
                        styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                    else:
                        styles.append('color: #666')
                else:
                    styles.append('color: #666')
            return styles
        # Inventory change rows - color code based on value
        elif 'Inventory Change' in item:
            styles = ['padding-left: 20px']  # First column (item name)
            styles.append('')  # Historical column
            # Color code each year's value
            for year in years:
                val = row.get(str(year), 0)
                if pd.notna(val) and val != 0:
                    if val > 0:
                        styles.append('color: #28a745; font-weight: 600')  # Green for increase
                    elif val < 0:
                        styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                    else:
                        styles.append('color: #666')
                else:
                    styles.append('color: #666')
            return styles
        # Customer prepayment change rows - color code based on value
        elif 'Prepayment Change' in item:
            styles = ['padding-left: 20px']  # First column (item name)
            styles.append('')  # Historical column
            # Color code each year's value
            for year in years:
                val = row.get(str(year), 0)
                if pd.notna(val) and val != 0:
                    if val > 0:
                        styles.append('color: #28a745; font-weight: 600')  # Green for increase
                    elif val < 0:
                        styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                    else:
                        styles.append('color: #666')
                else:
                    styles.append('color: #666')
            return styles
        # Cash change rows - color code based on value
        elif 'Cash Change' in item:
            styles = ['padding-left: 20px']  # First column (item name)
            styles.append('')  # Historical column
            # Color code each year's value
            for year in years:
                val = row.get(str(year), 0)
                if pd.notna(val) and val != 0:
                    if val > 0:
                        styles.append('color: #28a745; font-weight: 600')  # Green for increase
                    elif val < 0:
                        styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                    else:
                        styles.append('color: #666')
                else:
                    styles.append('color: #666')
            return styles
        # Other project details - indented with lighter font
        elif item.startswith('  '):
            return ['padding-left: 20px; color: #666'] * len(row)
        return [''] * len(row)

    # Define column configuration
    bs_column_config = {
        'Balance Sheet Item': st.column_config.TextColumn('Balance Sheet Item', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        bs_column_config[col] = st.column_config.NumberColumn(col, width='small')
    
    # Display the detail balance sheet
    st.dataframe(
        bs_df.style
        .format(format_bs_value, subset=[hist_col] + [str(y) for y in years])
        .apply(style_bs_table, axis=1),
        use_container_width=True,
        column_config=bs_column_config,
        hide_index=True
    )


def render_consolidated_bs_tab(
    hist_col: str,
    years: List[int],
    hist_bs_data: Dict,
    net_cf_by_year: Dict,
    total_inventory_by_year: Dict,
    total_customer_prepayment_by_year: Dict,
    total_debt_by_year: Dict,
    hist_customer_prepayment: float,
    npatmi_row: Optional[Dict],
    minority_interest_row: Optional[Dict],
    cash_row: Dict = None,
    ar_row: Dict = None,
    inventory_row: Dict = None,
    other_assets_row: Dict = None,
    total_assets_row: Dict = None,
    ap_row: Dict = None,
    customer_prepayment_row: Dict = None,
    st_debt_row: Dict = None,
    lt_debt_row: Dict = None,
    other_liab_row: Dict = None,
    total_liab_row: Dict = None,
    retained_earnings_row: Dict = None,
    minority_interest_bs_row: Dict = None,
    other_equity_row: Dict = None,
    total_equity_row: Dict = None
) -> None:
    """
    Render the consolidated balance sheet tab
    
    Args:
        hist_col: Historical column name
        years: List of forecast years
        hist_bs_data: Historical balance sheet data
        net_cf_by_year: Net cash flow by year
        total_inventory_by_year: Total inventory by year
        total_customer_prepayment_by_year: Total customer prepayment by year
        total_debt_by_year: Total debt by year
        hist_customer_prepayment: Historical customer prepayment value
        npatmi_row: NPATMI row data (optional)
        minority_interest_row: Minority interest row data (optional)
        cash_row through total_equity_row: Row dictionaries to be populated (optional, will be created if None)
    """
    # Create consolidated balance sheet with typical items
    consolidated_bs_rows = []
    
    # Assets Section
    # Cash & Equivalents
    if cash_row is None:
        cash_row = {}
    cash_row['Item'] = 'Cash & Equivalents'
    cash_row[hist_col] = hist_bs_data.get('Cash & Equivalents', 0)
    
    # Calculate cash based on cumulative net cash flow from cash flow statement
    cumulative_cash_balance = hist_bs_data.get('Cash & Equivalents', 0)
    for year in years:
        year_str = str(year)
        # Add the net cash flow for this year to cumulative balance
        net_cf = net_cf_by_year.get(year_str, 0)
        cumulative_cash_balance += net_cf
        cash_row[year_str] = cumulative_cash_balance
    consolidated_bs_rows.append(cash_row)
    
    # Account Receivable
    hist_ar = hist_bs_data.get('Account Receivable', 0)
    if ar_row is None:
        ar_row = {}
    ar_row['Item'] = 'Account Receivable'
    ar_row[hist_col] = hist_ar
    for year in years:
        year_str = str(year)
        # Keep AR constant at historical level
        ar_row[year_str] = hist_ar
    consolidated_bs_rows.append(ar_row)
    
    # Inventory
    if inventory_row is None:
        inventory_row = {}
    inventory_row['Item'] = 'Inventory'
    inventory_row[hist_col] = hist_bs_data.get('Inventory', 0)
    for year in years:
        year_str = str(year)
        inventory_row[year_str] = total_inventory_by_year.get(year_str, 0)
    consolidated_bs_rows.append(inventory_row)
    
    # Other Assets
    # For historical year: Other Assets = Total Assets - Cash & Equivalent - Account Receivable - Inventory
    hist_total_assets = hist_bs_data.get('Total Assets', 0)
    hist_cash_equiv = hist_bs_data.get('Cash & Equivalents', 0)
    hist_acc_receivable = hist_bs_data.get('Account Receivable', 0)
    hist_inventory_bs = hist_bs_data.get('Inventory', 0)
    hist_other_assets = hist_total_assets - hist_cash_equiv - hist_acc_receivable - hist_inventory_bs
    
    if other_assets_row is None:
        other_assets_row = {}
    other_assets_row['Item'] = 'Other Assets'
    other_assets_row[hist_col] = hist_other_assets
    # For forecast years, keep Other Assets constant at historical level
    for year in years:
        year_str = str(year)
        other_assets_row[year_str] = hist_other_assets
    consolidated_bs_rows.append(other_assets_row)
    
    # Total Assets
    if total_assets_row is None:
        total_assets_row = {}
    total_assets_row['Item'] = 'Total Assets'
    total_assets_row[hist_col] = hist_bs_data.get('Total Assets', 0)
    for year in years:
        year_str = str(year)
        # Total Assets = Cash + AR + Inventory + Other Assets
        total_assets_row[year_str] = (
            cash_row[year_str] + 
            ar_row[year_str] + 
            inventory_row[year_str] +
            other_assets_row[year_str]
        )
    consolidated_bs_rows.append(total_assets_row)
    
    # Liabilities Section
    # Account Payable
    hist_ap = hist_bs_data.get('Account Payable', 0)
    if ap_row is None:
        ap_row = {}
    ap_row['Item'] = 'Account Payable'
    ap_row[hist_col] = hist_ap
    for year in years:
        year_str = str(year)
        # Keep AP constant at historical level
        ap_row[year_str] = hist_ap
    consolidated_bs_rows.append(ap_row)
    
    # Customer Prepayment
    if customer_prepayment_row is None:
        customer_prepayment_row = {}
    customer_prepayment_row['Item'] = 'Customer Prepayment'
    customer_prepayment_row[hist_col] = hist_bs_data.get('Customer Prepayment', hist_customer_prepayment)
    for year in years:
        year_str = str(year)
        customer_prepayment_row[year_str] = total_customer_prepayment_by_year.get(year_str, 0)
    consolidated_bs_rows.append(customer_prepayment_row)
    
    # Calculate historical ST/LT debt ratio
    hist_st_debt = hist_bs_data.get('Short-term Debt', 0)
    hist_lt_debt = hist_bs_data.get('Long-term Debt', 0)
    hist_total_debt = hist_st_debt + hist_lt_debt
    
    # Calculate ratios, with fallback to 30/70 if no historical debt
    if hist_total_debt > 0:
        st_debt_ratio = hist_st_debt / hist_total_debt
        lt_debt_ratio = hist_lt_debt / hist_total_debt
    else:
        # Default ratios if no historical debt
        st_debt_ratio = 0.3  # 30% short-term
        lt_debt_ratio = 0.7  # 70% long-term
    
    # Short-term Debt
    if st_debt_row is None:
        st_debt_row = {}
    st_debt_row['Item'] = 'Short-term Debt'
    st_debt_row[hist_col] = hist_st_debt
    for year in years:
        year_str = str(year)
        # Use historical ratio for forecast
        st_debt_row[year_str] = total_debt_by_year.get(year_str, 0) * st_debt_ratio
    consolidated_bs_rows.append(st_debt_row)
    
    # Long-term Debt
    if lt_debt_row is None:
        lt_debt_row = {}
    lt_debt_row['Item'] = 'Long-term Debt'
    lt_debt_row[hist_col] = hist_lt_debt
    for year in years:
        year_str = str(year)
        # Use historical ratio for forecast
        lt_debt_row[year_str] = total_debt_by_year.get(year_str, 0) * lt_debt_ratio
    consolidated_bs_rows.append(lt_debt_row)
    
    # Other Liabilities
    # For historical year: Other Liabilities = Total Liabilities - Account Payable - Customer Prepayment - Short-term debt - Long-term debt
    hist_total_liabilities = hist_bs_data.get('Total Liabilities', 0)
    hist_acc_payable = hist_bs_data.get('Account Payable', 0)
    hist_cust_prepayment = hist_bs_data.get('Customer Prepayment', hist_customer_prepayment)
    hist_other_liabilities = hist_total_liabilities - hist_acc_payable - hist_cust_prepayment - hist_st_debt - hist_lt_debt
    
    if other_liab_row is None:
        other_liab_row = {}
    other_liab_row['Item'] = 'Other Liabilities'
    other_liab_row[hist_col] = hist_other_liabilities
    # For forecast years, keep Other Liabilities constant at historical level
    for year in years:
        year_str = str(year)
        other_liab_row[year_str] = hist_other_liabilities
    consolidated_bs_rows.append(other_liab_row)
    
    # Total Liabilities
    if total_liab_row is None:
        total_liab_row = {}
    total_liab_row['Item'] = 'Total Liabilities'
    total_liab_row[hist_col] = hist_bs_data.get('Total Liabilities', 0)
    for year in years:
        year_str = str(year)
        # Total Liabilities = AP + Customer Prepayment + ST Debt + LT Debt + Other Liabilities
        total_liab_row[year_str] = (
            ap_row[year_str] + 
            customer_prepayment_row[year_str] +
            st_debt_row[year_str] +
            lt_debt_row[year_str] +
            other_liab_row[year_str]
        )
    consolidated_bs_rows.append(total_liab_row)
    
    # Equity Section
    # Retained Earnings
    if retained_earnings_row is None:
        retained_earnings_row = {}
    retained_earnings_row['Item'] = 'Retained Earnings'
    retained_earnings_row[hist_col] = hist_bs_data.get('Retained Earnings', 0)
    # Calculate cumulative retained earnings from NPATMI
    cumulative_earnings = retained_earnings_row[hist_col]
    for year in years:
        year_str = str(year)
        # Add current year NPATMI to retained earnings
        if npatmi_row and year_str in npatmi_row:
            cumulative_earnings += npatmi_row[year_str]
        retained_earnings_row[year_str] = cumulative_earnings
    consolidated_bs_rows.append(retained_earnings_row)
    
    # Minority Interest
    if minority_interest_bs_row is None:
        minority_interest_bs_row = {}
    minority_interest_bs_row['Item'] = 'Minority Interest'
    minority_interest_bs_row[hist_col] = hist_bs_data.get('Minority Interest', 0)
    # Calculate cumulative minority interest from P&L
    cumulative_minority = minority_interest_bs_row[hist_col]
    for year in years:
        year_str = str(year)
        # Add current year minority interest from P&L to cumulative
        if minority_interest_row and year_str in minority_interest_row:
            cumulative_minority += minority_interest_row[year_str]
        minority_interest_bs_row[year_str] = cumulative_minority
    consolidated_bs_rows.append(minority_interest_bs_row)
    
    # Other Equity (Charter Capital, Treasury shares etc.)
    # For historical: Other Equity = Total Equity - Retained Earnings - Minority Interest
    hist_total_equity = hist_bs_data.get('Total Equity', 0)
    hist_retained_earnings = hist_bs_data.get('Retained Earnings', 0)
    hist_minority_interest = hist_bs_data.get('Minority Interest', 0)
    hist_other_equity = hist_total_equity - hist_retained_earnings - hist_minority_interest
    
    if other_equity_row is None:
        other_equity_row = {}
    other_equity_row['Item'] = 'Other Equity (Charter Capital, Treasury shares etc.)'
    other_equity_row[hist_col] = hist_other_equity
    # For forecast years, keep Other Equity constant at historical level
    for year in years:
        year_str = str(year)
        other_equity_row[year_str] = hist_other_equity
    consolidated_bs_rows.append(other_equity_row)
    
    # Total Equity
    if total_equity_row is None:
        total_equity_row = {}
    total_equity_row['Item'] = 'Total Equity'
    total_equity_row[hist_col] = hist_bs_data.get('Total Equity', 0)
    for year in years:
        year_str = str(year)
        # Total Equity = Retained Earnings + Minority Interest + Other Equity
        total_equity_row[year_str] = (
            retained_earnings_row[year_str] + 
            minority_interest_bs_row[year_str] +
            other_equity_row[year_str]
        )
    consolidated_bs_rows.append(total_equity_row)
    
    # Check row (Total Assets - Total Liabilities - Total Equity)
    check_row = {
        'Item': 'Check (A - L - E)',
        hist_col: 0  # Historical should balance
    }
    # Calculate check for historical year
    hist_check = hist_bs_data.get('Total Assets', 0) - hist_bs_data.get('Total Liabilities', 0) - hist_bs_data.get('Total Equity', 0)
    check_row[hist_col] = hist_check
    
    for year in years:
        year_str = str(year)
        # Check = Total Assets - Total Liabilities - Total Equity (should be 0)
        check_value = (
            total_assets_row[year_str] - 
            total_liab_row[year_str] - 
            total_equity_row[year_str]
        )
        check_row[year_str] = check_value
    consolidated_bs_rows.append(check_row)
    
    # Create DataFrame
    consolidated_bs_df = pd.DataFrame(consolidated_bs_rows)
    
    # Format function for balance sheet values
    def format_consolidated_bs(val):
        if val is None or pd.isna(val):
            return ""
        elif val == 0:
            return "-"
        else:
            return f"{val:,.0f}"
    
    # Style function for the consolidated balance sheet
    def style_consolidated_bs(row):
        if row['Item'] == 'Total Assets':
            return ['background-color: #e8f4f8; font-weight: bold'] * len(row)
        elif row['Item'] == 'Total Liabilities':
            return ['background-color: #ffe8e8; font-weight: bold'] * len(row)
        elif row['Item'] == 'Total Equity':
            return ['background-color: #e8f8e8; font-weight: bold'] * len(row)
        elif row['Item'] in ['Other Assets', 'Other Liabilities']:
            return ['font-weight: 600'] * len(row)
        elif row['Item'] == 'Check (A - L - E)':
            # Check if any value is non-zero and highlight in red
            styles = []
            for col in row.index:
                if col == 'Item':
                    styles.append('font-weight: bold')
                else:
                    val = row[col]
                    if val is not None and not pd.isna(val) and abs(val) > 0.01:  # Allow small rounding errors
                        styles.append('color: red; font-weight: bold')
                    else:
                        styles.append('color: green')
            return styles
        return [''] * len(row)
    
    # Display the consolidated balance sheet
    st.dataframe(
        consolidated_bs_df.style
        .format(format_consolidated_bs, subset=[hist_col] + [str(y) for y in years])
        .apply(style_consolidated_bs, axis=1),
        use_container_width=True,
        column_config={
            'Item': st.column_config.TextColumn('Balance Sheet Item', width=200),
            hist_col: st.column_config.NumberColumn(hist_col, width=120),
            **{str(year): st.column_config.NumberColumn(str(year), width=120) for year in years}
        },
        hide_index=True
    )


def prepare_balance_sheet_data(
    df_projects: pd.DataFrame,
    hist_col: str,
    years: List[int],
    base_year: int,
    historical_data: Optional[pd.DataFrame],
    hist_date_idx: Optional[Any]
) -> Dict[str, Any]:
    """
    Prepare balance sheet data by aggregating project-level information and historical data
    
    Args:
        df_projects: DataFrame containing project data
        hist_col: Historical column name
        years: List of forecast years
        base_year: Base year for calculations
        historical_data: Historical financial data
        hist_date_idx: Historical date index
    
    Returns:
        Dictionary containing:
        - total_debt_by_year: Total debt by year
        - total_inventory_by_year: Total inventory by year
        - total_customer_prepayment_by_year: Total customer prepayment by year
        - total_cash_by_year: Total cash by year (before interest income)
        - hist_bs_data: Historical balance sheet data
        - hist_debt: Historical debt
        - hist_inventory: Historical inventory
        - hist_cash: Historical cash
        - hist_customer_prepayment: Historical customer prepayment
        - hist_retained_earnings: Historical retained earnings
        - hist_minority_interest: Historical minority interest
        - debt_changes_by_year: Debt changes by year
        - inventory_changes_by_year: Inventory changes by year
        - prepayment_changes_by_year: Prepayment changes by year
        - cash_changes_by_year: Cash changes by year
        - cumulative_debt: Cumulative debt
        - cumulative_inventory: Cumulative inventory
        - cumulative_prepayment: Cumulative prepayment
        - cumulative_cash: Cumulative cash
        - debt_breakdown: Empty dict for detail BS tab to populate
        - inventory_breakdown: Empty dict for detail BS tab to populate
        - prepayment_breakdown: Empty dict for detail BS tab to populate
        - cash_breakdown: Empty dict for detail BS tab to populate
        - debt_change_breakdown: Empty dict for detail BS tab to populate
        - inventory_change_breakdown: Empty dict for detail BS tab to populate
        - prepayment_change_breakdown: Empty dict for detail BS tab to populate
        - cash_change_breakdown: Empty dict for detail BS tab to populate
    """
    # Initialize aggregated balance sheet data (needed by both tabs)
    total_debt_by_year = {hist_col: 0}
    total_inventory_by_year = {hist_col: 0}
    total_customer_prepayment_by_year = {hist_col: 0}
    total_cash_by_year = {hist_col: 0}

    for year in years:
        year_str = str(year)
        total_debt_by_year[year_str] = 0
        total_inventory_by_year[year_str] = 0
        total_customer_prepayment_by_year[year_str] = 0
        total_cash_by_year[year_str] = 0

    # Load historical balance sheet data for consolidated balance sheet
    hist_bs_data = {}
    if historical_data is not None and not historical_data.empty and hist_date_idx is not None:
        # Map of display names to column names in FA_A_processed.parquet
        bs_mapping = {
            'Cash & Equivalents': ['Cash_Equivalent', 'Cash'],
            'Account Receivable': ['Account_Receivable'],
            'Inventory': ['Inventory'],
            'Total Current Assets': ['Current_Asset'],
            'Tangible Fixed Assets': ['Tangible_Fixed_Asset'],
            'Total Assets': ['Total_Asset'],
            'Account Payable': ['Account_Payable'],
            'Customer Prepayment': ['Advance_From_Custmers'],  # Note the typo in the KEYCODE
            'Short-term Debt': ['ST_Debt'],
            'Current Liabilities': ['Current_Liabilities'],
            'Long-term Debt': ['LT_Debt'],
            'Total Liabilities': ['Total_Liabilities'],
            'Retained Earnings': ['Retain_Earning'],
            'Minority Interest': ['Minority_Interest'],
            'Total Equity': ['TOTAL_Equity']
        }
        
        # Extract historical values
        for display_name, col_names in bs_mapping.items():
            value = 0
            for col_name in col_names:
                if col_name in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, col_name]
                        if not pd.isna(raw_value):
                            value += raw_value
                    except:
                        pass
            hist_bs_data[display_name] = value / 1e9  # Convert to billions

    # Use consolidated balance sheet historical values for consistency
    hist_debt = hist_bs_data.get('Short-term Debt', 0) + hist_bs_data.get('Long-term Debt', 0)
    hist_inventory = hist_bs_data.get('Inventory', 0)
    hist_cash = hist_bs_data.get('Cash & Equivalents', 0)
    hist_customer_prepayment = hist_bs_data.get('Customer Prepayment', 0)
    hist_retained_earnings = hist_bs_data.get('Retained Earnings', 0)
    hist_minority_interest = hist_bs_data.get('Minority Interest', 0)

    # First, initialize with historical values as starting point
    # These will be the base for cumulative calculations
    cumulative_debt = hist_debt
    cumulative_inventory = hist_inventory
    cumulative_prepayment = hist_customer_prepayment
    cumulative_cash = hist_cash

    # Store year-over-year changes for each project
    debt_changes_by_year = {str(y): 0 for y in years}
    inventory_changes_by_year = {str(y): 0 for y in years}
    prepayment_changes_by_year = {str(y): 0 for y in years}
    cash_changes_by_year = {str(y): 0 for y in years}

    # Aggregate changes from all projects
    for _, project in df_projects.iterrows():
        financial_statements = project.get('comprehensive_financial_statements', {})
        project_name = project.get('project_name', 'Unknown')
        
        # Ensure financial_statements is a dictionary
        if not isinstance(financial_statements, dict):
            financial_statements = {}
    
        # Track previous year values for this project to calculate changes
        # Check if project has historical data (base year) for proper initialization
        base_year_str = str(base_year)
        prev_debt = 0
        prev_inventory = 0
        prev_prepayment = 0
        prev_cash = 0
        
        # If project has historical year data, use it as starting point
        if base_year_str in financial_statements:
            hist_data = financial_statements[base_year_str]
            
            # Get historical inventory
            if 'inventory_balance' in hist_data:
                prev_inventory = hist_data.get('inventory_balance', 0) / 1e9
            elif 'Inventory_Balance' in hist_data:
                prev_inventory = hist_data.get('Inventory_Balance', 0) / 1e9
            
            # Get historical debt
            if 'debt_balance' in hist_data:
                prev_debt = hist_data.get('debt_balance', 0) / 1e9
            elif 'Debt_Balance' in hist_data:
                prev_debt = hist_data.get('Debt_Balance', 0) / 1e9
            
            # Get historical prepayment
            if 'customer_prepayment_balance' in hist_data:
                prev_prepayment = hist_data.get('customer_prepayment_balance', 0) / 1e9
            elif 'Customer_Prepayment_Balance' in hist_data:
                prev_prepayment = hist_data.get('Customer_Prepayment_Balance', 0) / 1e9
            
            # Note: prev_cash typically stays at 0 as cash is cumulative from project start
    
        for year in years:
            year_str = str(year)
        
            if year_str in financial_statements:
                year_data = financial_statements[year_str]
            
                # Get current year debt balance
                current_debt = 0
                if 'debt_balance' in year_data:
                    current_debt = year_data.get('debt_balance', 0) / 1e9
                elif 'Debt_Balance' in year_data:
                    current_debt = year_data.get('Debt_Balance', 0) / 1e9
                # Calculate net change and add to total changes
                debt_changes_by_year[year_str] += (current_debt - prev_debt)
                prev_debt = current_debt
            
                # Get current year inventory balance
                current_inventory = 0
                if 'inventory_balance' in year_data:
                    current_inventory = year_data.get('inventory_balance', 0) / 1e9
                elif 'Inventory_Balance' in year_data:
                    current_inventory = year_data.get('Inventory_Balance', 0) / 1e9
                
                # Calculate net change (current year - previous year)
                inventory_change = current_inventory - prev_inventory
                inventory_changes_by_year[year_str] += inventory_change
                
                # Update prev_inventory for next year's calculation
                prev_inventory = current_inventory
            
                # Get current year customer prepayment balance
                current_prepayment = 0
                if 'customer_prepayment_balance' in year_data:
                    current_prepayment = year_data.get('customer_prepayment_balance', 0) / 1e9
                elif 'Customer_Prepayment_Balance' in year_data:
                    current_prepayment = year_data.get('Customer_Prepayment_Balance', 0) / 1e9
                # Calculate net change and add to total changes
                prepayment_changes_by_year[year_str] += (current_prepayment - prev_prepayment)
                prev_prepayment = current_prepayment
            
                # For cash, we can use cash_balance_change directly if available
                if 'cash_balance_change' in year_data:
                    cash_changes_by_year[year_str] += year_data.get('cash_balance_change', 0) / 1e9
                elif 'Cash_Balance_Change' in year_data:
                    cash_changes_by_year[year_str] += year_data.get('Cash_Balance_Change', 0) / 1e9
                else:
                    # Calculate from cumulative balance if available
                    current_cash = 0
                    if 'cumulative_cash_balance' in year_data:
                        current_cash = year_data.get('cumulative_cash_balance', 0) / 1e9
                    elif 'Cumulative_Cash_Balance' in year_data:
                        current_cash = year_data.get('Cumulative_Cash_Balance', 0) / 1e9
                    # Calculate net change
                    cash_changes_by_year[year_str] += (current_cash - prev_cash)
                    prev_cash = current_cash

    # Calculate cumulative totals for each year (before interest income)
    for year_str in [str(y) for y in years]:
        # Add the year's changes to the cumulative totals
        cumulative_debt += debt_changes_by_year[year_str]
        cumulative_inventory += inventory_changes_by_year[year_str]
        cumulative_prepayment += prepayment_changes_by_year[year_str]
        cumulative_cash += cash_changes_by_year[year_str]
        
        # Store the base totals (before interest income)
        total_debt_by_year[year_str] = cumulative_debt
        total_inventory_by_year[year_str] = cumulative_inventory
        total_customer_prepayment_by_year[year_str] = cumulative_prepayment
        total_cash_by_year[year_str] = cumulative_cash

    # Initialize breakdown dictionaries for detail BS tab to populate
    debt_breakdown = {}
    inventory_breakdown = {}
    prepayment_breakdown = {}
    cash_breakdown = {}
    
    # Initialize change breakdown variables for save function
    debt_change_breakdown = {}
    inventory_change_breakdown = {}
    prepayment_change_breakdown = {}
    cash_change_breakdown = {}

    return {
        'total_debt_by_year': total_debt_by_year,
        'total_inventory_by_year': total_inventory_by_year,
        'total_customer_prepayment_by_year': total_customer_prepayment_by_year,
        'total_cash_by_year': total_cash_by_year,
        'hist_bs_data': hist_bs_data,
        'hist_debt': hist_debt,
        'hist_inventory': hist_inventory,
        'hist_cash': hist_cash,
        'hist_customer_prepayment': hist_customer_prepayment,
        'hist_retained_earnings': hist_retained_earnings,
        'hist_minority_interest': hist_minority_interest,
        'debt_changes_by_year': debt_changes_by_year,
        'inventory_changes_by_year': inventory_changes_by_year,
        'prepayment_changes_by_year': prepayment_changes_by_year,
        'cash_changes_by_year': cash_changes_by_year,
        'cumulative_debt': cumulative_debt,
        'cumulative_inventory': cumulative_inventory,
        'cumulative_prepayment': cumulative_prepayment,
        'cumulative_cash': cumulative_cash,
        'debt_breakdown': debt_breakdown,
        'inventory_breakdown': inventory_breakdown,
        'prepayment_breakdown': prepayment_breakdown,
        'cash_breakdown': cash_breakdown,
        'debt_change_breakdown': debt_change_breakdown,
        'inventory_change_breakdown': inventory_change_breakdown,
        'prepayment_change_breakdown': prepayment_change_breakdown,
        'cash_change_breakdown': cash_change_breakdown
    }