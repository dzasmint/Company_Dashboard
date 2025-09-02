"""
Utility functions for creating cash flow statement rows in model forecast
Extracted from tabs/model_forecast.py for better organization
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Any, Optional, Tuple


def create_detail_cashflow_rows(
    years: List[int],
    hist_col: str,
    historical_data: Optional[pd.DataFrame],
    hist_date_idx: Optional[Any],
    operating_cf_by_year: Dict[str, float],
    investing_cf_by_year: Dict[str, float],
    financing_cf_by_year: Dict[str, float],
    net_cf_by_year: Dict[str, float],
    presales_cf_breakdown: Dict[str, Dict[str, float]],
    interest_outflow_breakdown: Dict[str, Dict[str, float]],
    sga_outflow_breakdown: Dict[str, Dict[str, float]],
    tax_outflow_breakdown: Dict[str, Dict[str, float]],
    land_outflow_breakdown: Dict[str, Dict[str, float]],
    construction_outflow_breakdown: Dict[str, Dict[str, float]],
    financing_cf_breakdown: Dict[str, Dict[str, float]],
    other_segment_revenue_cf: Dict[str, float],
    other_segment_cogs_cf: Dict[str, float],
    existing_debt_interest_row: Dict[str, float],
    sga_rows: List[Dict],
    interest_income_by_year: Dict[str, float]
) -> tuple:
    """
    Create detailed cash flow rows for the cash flow statement.
    
    Args:
        years: List of forecast years
        hist_col: Historical column name (e.g., '2024H')
        historical_data: Historical financial data DataFrame
        hist_date_idx: Index for historical data
        operating_cf_by_year: Operating cash flow by year
        investing_cf_by_year: Investing cash flow by year
        financing_cf_by_year: Financing cash flow by year
        net_cf_by_year: Net cash flow by year
        presales_cf_breakdown: Presales cash flow breakdown by project
        interest_outflow_breakdown: Interest outflow breakdown by project
        sga_outflow_breakdown: SG&A outflow breakdown by project
        tax_outflow_breakdown: Tax outflow breakdown by project
        land_outflow_breakdown: Land outflow breakdown by project
        construction_outflow_breakdown: Construction outflow breakdown by project
        financing_cf_breakdown: Financing cash flow breakdown by project
        other_segment_revenue_cf: Other segment revenue cash flow
        other_segment_cogs_cf: Other segment COGS cash flow
        existing_debt_interest_row: Existing debt interest row data
        sga_rows: SG&A rows from P&L
        interest_income_by_year: Interest income by year
        
    Returns:
        Tuple of (cf_rows, hist_operating_cf_detail, hist_investing_cf_detail, hist_financing_cf_detail)
    """
    cf_rows = []
    
    # Load historical cash flow data
    hist_operating_cf_detail, hist_investing_cf_detail, hist_financing_cf_detail = load_historical_cashflow_data(
        historical_data, hist_date_idx
    )
    
    # Build Operating Activities section
    cf_rows.extend(build_operating_activities_rows(
        years, hist_col, hist_operating_cf_detail,
        operating_cf_by_year, presales_cf_breakdown,
        interest_outflow_breakdown, sga_outflow_breakdown,
        tax_outflow_breakdown, other_segment_revenue_cf,
        other_segment_cogs_cf, existing_debt_interest_row,
        sga_rows
    ))
    
    # Add separator
    cf_rows.append({'Cash Flow Item': '', hist_col: None, **{str(y): None for y in years}})
    
    # Build Investing Activities section
    cf_rows.extend(build_investing_activities_rows(
        years, hist_col, hist_investing_cf_detail,
        investing_cf_by_year, land_outflow_breakdown,
        construction_outflow_breakdown, interest_income_by_year
    ))
    
    # Add separator
    cf_rows.append({'Cash Flow Item': '', hist_col: None, **{str(y): None for y in years}})
    
    # Build Financing Activities section
    cf_rows.extend(build_financing_activities_rows(
        years, hist_col, hist_financing_cf_detail,
        financing_cf_by_year, financing_cf_breakdown
    ))
    
    # Add separator with line
    cf_rows.append({'Cash Flow Item': '─' * 30, hist_col: None, **{str(y): None for y in years}})
    
    # Build Net Cash Flow summary
    cf_rows.extend(build_net_cashflow_rows(
        years, hist_col,
        hist_operating_cf_detail + hist_investing_cf_detail + hist_financing_cf_detail,
        net_cf_by_year
    ))
    
    return cf_rows, hist_operating_cf_detail, hist_investing_cf_detail, hist_financing_cf_detail


def load_historical_cashflow_data(
    historical_data: Optional[pd.DataFrame],
    hist_date_idx: Optional[Any]
) -> tuple:
    """
    Load historical cash flow data from FA_A_processed.parquet
    
    Returns:
        Tuple of (hist_operating_cf, hist_investing_cf, hist_financing_cf)
    """
    hist_operating_cf_detail = 0
    hist_investing_cf_detail = 0
    hist_financing_cf_detail = 0
    
    if historical_data is not None and not historical_data.empty and hist_date_idx is not None:
        # Get historical cash flow values
        if 'Operating_CF' in historical_data.columns:
            hist_operating_cf_val = historical_data.loc[hist_date_idx, 'Operating_CF']
            hist_operating_cf_detail = hist_operating_cf_val / 1e9 if not pd.isna(hist_operating_cf_val) else 0
        
        if 'Inv_CF' in historical_data.columns:
            hist_investing_cf_val = historical_data.loc[hist_date_idx, 'Inv_CF']
            hist_investing_cf_detail = hist_investing_cf_val / 1e9 if not pd.isna(hist_investing_cf_val) else 0
        
        if 'Fin_CF' in historical_data.columns:
            hist_financing_cf_val = historical_data.loc[hist_date_idx, 'Fin_CF']
            hist_financing_cf_detail = hist_financing_cf_val / 1e9 if not pd.isna(hist_financing_cf_val) else 0
    
    return hist_operating_cf_detail, hist_investing_cf_detail, hist_financing_cf_detail


def build_operating_activities_rows(
    years: List[int],
    hist_col: str,
    hist_operating_cf: float,
    operating_cf_by_year: Dict[str, float],
    presales_cf_breakdown: Dict[str, Dict[str, float]],
    interest_outflow_breakdown: Dict[str, Dict[str, float]],
    sga_outflow_breakdown: Dict[str, Dict[str, float]],
    tax_outflow_breakdown: Dict[str, Dict[str, float]],
    other_segment_revenue_cf: Dict[str, float],
    other_segment_cogs_cf: Dict[str, float],
    existing_debt_interest_row: Dict[str, float],
    sga_rows: List[Dict]
) -> List[Dict]:
    """Build Operating Activities section rows"""
    rows = []
    
    # Operating Cash Flow Section header
    rows.append({'Cash Flow Item': 'OPERATING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Operating Cash Inflows
    rows.append({'Cash Flow Item': '  Cash Inflows:', hist_col: None, **{str(y): None for y in years}})
    
    # Revenue from other business segments
    if any(other_segment_revenue_cf[str(y)] != 0 for y in years):
        other_revenue_row = {'Cash Flow Item': '    Revenue from Other Segments', hist_col: 0}
        for year in years:
            other_revenue_row[str(year)] = other_segment_revenue_cf[str(year)]
        rows.append(other_revenue_row)
    
    # Presales cash inflow by project
    for project_name in sorted(presales_cf_breakdown.keys()):
        if any(presales_cf_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    Presales - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = presales_cf_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # Operating Cash Outflows
    rows.append({'Cash Flow Item': '  Cash Outflows:', hist_col: None, **{str(y): None for y in years}})
    
    # COGS from other business segments
    if any(other_segment_cogs_cf[str(y)] != 0 for y in years):
        cogs_row = {'Cash Flow Item': '    COGS - Other Business Segments', hist_col: 0}
        for year in years:
            cogs_row[str(year)] = -other_segment_cogs_cf[str(year)]  # Show as negative
        rows.append(cogs_row)
    
    # Interest expense outflow by project
    for project_name in sorted(interest_outflow_breakdown.keys()):
        if any(interest_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    Interest Expense - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = interest_outflow_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # Interest expense from existing debt
    existing_debt_interest_cf_row = {'Cash Flow Item': '    Interest Expense - Existing Debt', hist_col: 0}
    for year in years:
        year_str = str(year)
        existing_debt_interest_cf_row[year_str] = existing_debt_interest_row.get(str(year), 0)
    rows.append(existing_debt_interest_cf_row)
    
    # SG&A expense outflow by project
    for project_name in sorted(sga_outflow_breakdown.keys()):
        if any(sga_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    SG&A Expense - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = sga_outflow_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # SG&A expense from other segments
    other_sga_cf_row = {'Cash Flow Item': '    SG&A Expense - Other Segments', hist_col: 0}
    for year in years:
        year_str = str(year)
        # Calculate SG&A for other segments
        total_sga = 0
        for row in sga_rows:
            if row.get('SG&A Source') == 'TOTAL SG&A':
                total_sga = row.get(str(year), 0)
                break
        total_proj_sga = sum(sga_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in sga_outflow_breakdown.keys())
        other_sga = total_sga - total_proj_sga
        other_sga_cf_row[year_str] = other_sga
    rows.append(other_sga_cf_row)
    
    # Tax expense outflow by project
    for project_name in sorted(tax_outflow_breakdown.keys()):
        if any(tax_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    Tax Expense - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = tax_outflow_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # Total Operating CF
    operating_total_row = {'Cash Flow Item': 'TOTAL OPERATING CASH FLOW', hist_col: hist_operating_cf}
    for year in years:
        operating_total_row[str(year)] = operating_cf_by_year[str(year)]
    rows.append(operating_total_row)
    
    return rows


def build_investing_activities_rows(
    years: List[int],
    hist_col: str,
    hist_investing_cf: float,
    investing_cf_by_year: Dict[str, float],
    land_outflow_breakdown: Dict[str, Dict[str, float]],
    construction_outflow_breakdown: Dict[str, Dict[str, float]],
    interest_income_by_year: Dict[str, float]
) -> List[Dict]:
    """Build Investing Activities section rows"""
    rows = []
    
    # Investing Cash Flow Section header
    rows.append({'Cash Flow Item': 'INVESTING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Land Payment Outflows
    rows.append({'Cash Flow Item': '  Land Payments:', hist_col: None, **{str(y): None for y in years}})
    for project_name in sorted(land_outflow_breakdown.keys()):
        if any(land_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    Land Payment - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = land_outflow_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # Construction Cost Outflows
    rows.append({'Cash Flow Item': '  Construction Costs:', hist_col: None, **{str(y): None for y in years}})
    for project_name in sorted(construction_outflow_breakdown.keys()):
        if any(construction_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
            project_row = {'Cash Flow Item': f'    Construction - {project_name}', hist_col: 0}
            for year in years:
                year_str = str(year)
                project_row[year_str] = construction_outflow_breakdown[project_name].get(year_str, 0)
            rows.append(project_row)
    
    # Interest Income (cash inflow from investing activities)
    rows.append({'Cash Flow Item': '  Interest Income:', hist_col: None, **{str(y): None for y in years}})
    interest_income_cf_row = {'Cash Flow Item': '    Interest Income from Cash', hist_col: 0}
    
    # Use the interest income already calculated and added to investing CF
    for year in years:
        year_str = str(year)
        # Get interest income from the already calculated values
        interest_income_cf = interest_income_by_year.get(year_str, 0)
        interest_income_cf_row[year_str] = interest_income_cf
    
    rows.append(interest_income_cf_row)
    
    # Total Investing CF (now includes interest income)
    investing_total_row = {'Cash Flow Item': 'TOTAL INVESTING CASH FLOW', hist_col: hist_investing_cf}
    for year in years:
        investing_total_row[str(year)] = investing_cf_by_year[str(year)]
    rows.append(investing_total_row)
    
    return rows


def build_financing_activities_rows(
    years: List[int],
    hist_col: str,
    hist_financing_cf: float,
    financing_cf_by_year: Dict[str, float],
    financing_cf_breakdown: Dict[str, Dict[str, float]]
) -> List[Dict]:
    """Build Financing Activities section rows"""
    rows = []
    
    # Financing Cash Flow Section header
    rows.append({'Cash Flow Item': 'FINANCING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Add breakdown by project for financing CF
    for project_name in sorted(financing_cf_breakdown.keys()):
        project_row = {'Cash Flow Item': f'  └─ {project_name}', hist_col: 0}
        for year in years:
            year_str = str(year)
            project_row[year_str] = financing_cf_breakdown[project_name].get(year_str, 0)
        rows.append(project_row)
    
    # Total Financing CF
    financing_total_row = {'Cash Flow Item': 'TOTAL FINANCING CASH FLOW', hist_col: hist_financing_cf}
    for year in years:
        financing_total_row[str(year)] = financing_cf_by_year[str(year)]
    rows.append(financing_total_row)
    
    return rows


def build_net_cashflow_rows(
    years: List[int],
    hist_col: str,
    hist_net_cf: float,
    net_cf_by_year: Dict[str, float]
) -> List[Dict]:
    """Build Net Cash Flow summary row"""
    rows = []
    
    # Net Cash Flow
    net_cf_row = {'Cash Flow Item': 'NET CASH FLOW', hist_col: hist_net_cf}
    for year in years:
        net_cf_row[str(year)] = net_cf_by_year[str(year)]
    rows.append(net_cf_row)
    
    return rows


def create_consolidated_cashflow_rows(
    years: List[int],
    hist_col: str,
    hist_operating_cf: float,
    hist_investing_cf: float,
    hist_financing_cf: float,
    operating_cf_by_year: Dict[str, float],
    investing_cf_by_year: Dict[str, float],
    financing_cf_by_year: Dict[str, float],
    net_cf_by_year: Dict[str, float],
    presales_cf_breakdown: Dict[str, Dict[str, float]],
    interest_outflow_breakdown: Dict[str, Dict[str, float]],
    sga_outflow_breakdown: Dict[str, Dict[str, float]],
    land_outflow_breakdown: Dict[str, Dict[str, float]],
    construction_outflow_breakdown: Dict[str, Dict[str, float]],
    other_segment_revenue_cf: Dict[str, float],
    other_segment_cogs_cf: Dict[str, float],
    existing_debt_interest_row: Dict[str, float],
    sga_rows: List[Dict],
    tax_row: Dict[str, float],
    interest_income_by_year: Dict[str, float],
    df_projects: pd.DataFrame
) -> Tuple[List[Dict], Dict[str, float]]:
    """
    Create consolidated cash flow rows for the cash flow statement.
    
    Args:
        years: List of forecast years
        hist_col: Historical column name
        hist_operating_cf: Historical operating cash flow
        hist_investing_cf: Historical investing cash flow
        hist_financing_cf: Historical financing cash flow
        operating_cf_by_year: Operating cash flow by year
        investing_cf_by_year: Investing cash flow by year
        financing_cf_by_year: Financing cash flow by year
        net_cf_by_year: Net cash flow by year
        presales_cf_breakdown: Presales cash flow breakdown by project
        interest_outflow_breakdown: Interest outflow breakdown by project
        sga_outflow_breakdown: SG&A outflow breakdown by project
        land_outflow_breakdown: Land outflow breakdown by project
        construction_outflow_breakdown: Construction outflow breakdown by project
        other_segment_revenue_cf: Other segment revenue cash flow
        other_segment_cogs_cf: Other segment COGS cash flow
        existing_debt_interest_row: Existing debt interest row data
        sga_rows: SG&A rows from P&L
        tax_row: Tax row from P&L
        interest_income_by_year: Interest income by year
        df_projects: Projects DataFrame
        
    Returns:
        Tuple of (consol_cf_rows, other_sga_cf_row)
    """
    consol_cf_rows = []
    
    # OPERATING ACTIVITIES SECTION
    consol_cf_rows.append({'Item': 'OPERATING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Total Presales (sum of all project presales cash inflows)
    total_presales_row = {'Item': '  Total Presales Cash Inflow', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_presales = sum(presales_cf_breakdown.get(proj, {}).get(year_str, 0) for proj in presales_cf_breakdown.keys())
        total_presales_row[year_str] = total_presales
    consol_cf_rows.append(total_presales_row)
    
    # Total Revenue from Other Segments
    other_revenue_row = {'Item': '  Revenue from Other Segments', hist_col: 0}
    for year in years:
        year_str = str(year)
        other_revenue_row[year_str] = other_segment_revenue_cf.get(year_str, 0)
    consol_cf_rows.append(other_revenue_row)
    
    # Total COGS from Other Segments (show as negative)
    other_cogs_row = {'Item': '  COGS from Other Segments', hist_col: 0}
    for year in years:
        year_str = str(year)
        other_cogs_row[year_str] = -other_segment_cogs_cf.get(year_str, 0) if other_segment_cogs_cf.get(year_str, 0) != 0 else 0
    consol_cf_rows.append(other_cogs_row)
    
    # Total Interest Expense from All Projects
    project_interest_row_cf = {'Item': '  Interest Expense - Projects', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_proj_interest = sum(interest_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in interest_outflow_breakdown.keys())
        project_interest_row_cf[year_str] = total_proj_interest
    consol_cf_rows.append(project_interest_row_cf)
    
    # Interest Expense from Existing Debt
    existing_interest_row_cf = {'Item': '  Interest Expense - Existing Debt', hist_col: 0}
    for year in years:
        year_str = str(year)
        existing_interest_row_cf[year_str] = existing_debt_interest_row.get(str(year), 0)
    consol_cf_rows.append(existing_interest_row_cf)
    
    # Total SG&A Expense from All Projects
    project_sga_row_cf = {'Item': '  SG&A Expense - Projects', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_proj_sga = sum(sga_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in sga_outflow_breakdown.keys())
        project_sga_row_cf[year_str] = total_proj_sga
    consol_cf_rows.append(project_sga_row_cf)
    
    # SG&A Expense from Other Segments
    other_sga_cf_row = {'Item': '  SG&A Expense - Other Segments', hist_col: 0}
    for year in years:
        year_str = str(year)
        # Calculate SG&A for other segments
        total_sga = 0
        for row in sga_rows:
            if row.get('SG&A Source') == 'TOTAL SG&A':
                total_sga = row.get(str(year), 0)
                break
        total_proj_sga = sum(sga_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in sga_outflow_breakdown.keys())
        other_sga = total_sga - total_proj_sga
        other_sga_cf_row[year_str] = other_sga
    consol_cf_rows.append(other_sga_cf_row)
    
    # Tax Expenses (Total from P&L)
    tax_expense_row_cf = {'Item': '  Tax Expense', hist_col: 0}
    for year in years:
        year_str = str(year)
        tax_expense_row_cf[year_str] = tax_row.get(year_str, 0)
    consol_cf_rows.append(tax_expense_row_cf)
    
    # Total Operating Cash Flow
    total_operating_row = {'Item': 'TOTAL OPERATING CASH FLOW', hist_col: hist_operating_cf}
    for year in years:
        year_str = str(year)
        total_operating_row[year_str] = operating_cf_by_year.get(year_str, 0)
    consol_cf_rows.append(total_operating_row)
    
    # INVESTING ACTIVITIES SECTION
    consol_cf_rows.append({'Item': '', hist_col: None, **{str(y): None for y in years}})  # Blank row
    consol_cf_rows.append({'Item': 'INVESTING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Total Land Payments from All Projects
    land_payments_row = {'Item': '  Land Payments', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_land = sum(land_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in land_outflow_breakdown.keys())
        land_payments_row[year_str] = total_land
    consol_cf_rows.append(land_payments_row)
    
    # Total Construction from All Projects
    construction_row = {'Item': '  Construction Costs', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_construction = sum(construction_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in construction_outflow_breakdown.keys())
        construction_row[year_str] = total_construction
    consol_cf_rows.append(construction_row)
    
    # Interest Income from Cash
    interest_income_consol_row = {'Item': '  Interest Income', hist_col: 0}
    for year in years:
        year_str = str(year)
        interest_income_consol_row[year_str] = interest_income_by_year.get(year_str, 0)
    consol_cf_rows.append(interest_income_consol_row)
    
    # Total Investing Cash Flow
    total_investing_row = {'Item': 'TOTAL INVESTING CASH FLOW', hist_col: hist_investing_cf}
    for year in years:
        year_str = str(year)
        total_investing_row[year_str] = investing_cf_by_year.get(year_str, 0)
    consol_cf_rows.append(total_investing_row)
    
    # FINANCING ACTIVITIES SECTION
    consol_cf_rows.append({'Item': '', hist_col: None, **{str(y): None for y in years}})  # Blank row
    consol_cf_rows.append({'Item': 'FINANCING ACTIVITIES', hist_col: None, **{str(y): None for y in years}})
    
    # Total New Debts from All Projects
    new_debt_row = {'Item': '  New Debt Disbursements', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_new_debt = 0
        for _, project in df_projects.iterrows():
            financial_statements = project.get('comprehensive_financial_statements', {})
            if isinstance(financial_statements, dict) and year_str in financial_statements:
                year_data = financial_statements[year_str]
                debt_disbursement = year_data.get('debt_disbursement', 0) / 1e9
                total_new_debt += debt_disbursement
        new_debt_row[year_str] = total_new_debt
    consol_cf_rows.append(new_debt_row)
    
    # Total Debt Repayment from All Projects
    debt_repayment_row = {'Item': '  Debt Repayments', hist_col: 0}
    for year in years:
        year_str = str(year)
        total_repayment = 0
        for _, project in df_projects.iterrows():
            financial_statements = project.get('comprehensive_financial_statements', {})
            if isinstance(financial_statements, dict) and year_str in financial_statements:
                year_data = financial_statements[year_str]
                debt_repayment = year_data.get('debt_repayment', 0) / 1e9
                total_repayment += debt_repayment
        debt_repayment_row[year_str] = total_repayment
    consol_cf_rows.append(debt_repayment_row)
    
    # Total Financing Cash Flow
    total_financing_row = {'Item': 'TOTAL FINANCING CASH FLOW', hist_col: hist_financing_cf}
    for year in years:
        year_str = str(year)
        total_financing_row[year_str] = financing_cf_by_year.get(year_str, 0)
    consol_cf_rows.append(total_financing_row)
    
    # NET CASH FLOW
    consol_cf_rows.append({'Item': '', hist_col: None, **{str(y): None for y in years}})  # Blank row
    net_cf_row_consol = {'Item': 'NET CASH FLOW', hist_col: hist_operating_cf + hist_investing_cf + hist_financing_cf}
    for year in years:
        year_str = str(year)
        net_cf_row_consol[year_str] = net_cf_by_year.get(year_str, 0)
    consol_cf_rows.append(net_cf_row_consol)
    
    return consol_cf_rows, other_sga_cf_row


def render_detail_cf_tab(cf_rows: List[Dict], hist_col: str, years: List[int]) -> None:
    """
    Render the detail cash flow tab with styling and formatting.
    
    Args:
        cf_rows: List of cash flow row dictionaries
        hist_col: Historical column name
        years: List of forecast years
    """
    # Create DataFrame
    cf_df = pd.DataFrame(cf_rows)
    
    st.write("**Detail Project Breakdown Cash Flow Statement (Billion VND)**")
    
    # Define style function for formatting
    def style_cf_table(val):
        if pd.isna(val) or val is None:
            return ''
        if isinstance(val, str):
            return ''
        # Color code: positive cash flow green, negative red
        color = '#28a745' if val >= 0 else '#dc3545'
        return f'color: {color}'
    
    # Apply styling to numeric columns
    styled_cf_df = cf_df.style.applymap(
        style_cf_table,
        subset=[hist_col] + [str(y) for y in years]
    ).format(
        {**{hist_col: lambda x: f"{int(x):,}" if pd.notna(x) and x != 0 and not pd.isna(x) else "-"},
         **{str(y): lambda x: f"{int(x):,}" if pd.notna(x) and x != 0 and not pd.isna(x) else "-" 
         for y in years}},
        na_rep="-"
    )
    
    # Apply row highlighting for totals and net cash flow
    def highlight_important_rows(row):
        styles = [''] * len(row)
        if 'TOTAL' in str(row.iloc[0]) or 'NET CASH FLOW' in str(row.iloc[0]):
            styles = ['font-weight: bold; background-color: #f8f9fa'] * len(row)
        elif any(keyword in str(row.iloc[0]) for keyword in ['OPERATING ACTIVITIES', 'INVESTING ACTIVITIES', 'FINANCING ACTIVITIES']):
            styles = ['font-weight: bold; background-color: #e9ecef'] * len(row)
        return styles
    
    styled_cf_df = styled_cf_df.apply(highlight_important_rows, axis=1)
    
    # Display the table
    st.dataframe(
        styled_cf_df,
        use_container_width=True,
        hide_index=True
    )


def render_consolidated_cf_tab(consol_cf_rows: List[Dict], hist_col: str, years: List[int]) -> None:
    """
    Render the consolidated cash flow tab with styling and formatting.
    
    Args:
        consol_cf_rows: List of consolidated cash flow row dictionaries
        hist_col: Historical column name
        years: List of forecast years
    """
    # Create DataFrame for consolidated cash flow
    consol_cf_df = pd.DataFrame(consol_cf_rows)
    
    st.write("**Consolidated Cash Flow Summary (Billion VND)**")
    
    # Style function for consolidated cash flow
    def style_consol_cf(val):
        if pd.isna(val) or val is None:
            return ''
        if isinstance(val, str):
            return ''
        # Color code: positive cash flow green, negative red
        if val > 0:
            return 'color: #28a745'
        elif val < 0:
            return 'color: #dc3545'
        return ''
    
    # Format function for values
    def format_cf_value(val):
        if pd.isna(val) or val is None or val == 0:
            return "-"
        return f"{val:,.0f}"
    
    # Apply styling
    styled_consol_cf = consol_cf_df.style.applymap(
        style_consol_cf,
        subset=[hist_col] + [str(y) for y in years]
    ).format(
        {col: format_cf_value for col in [hist_col] + [str(y) for y in years]},
        na_rep="-"
    )
    
    # Highlight important rows
    def highlight_cf_rows(row):
        styles = [''] * len(row)
        item = str(row.iloc[0])
        if item in ['OPERATING ACTIVITIES', 'INVESTING ACTIVITIES', 'FINANCING ACTIVITIES']:
            styles = ['font-weight: bold; background-color: #e9ecef'] * len(row)
        elif item.startswith('Total') or item == 'NET CASH FLOW':
            styles = ['font-weight: bold; background-color: #f8f9fa'] * len(row)
        return styles
    
    styled_consol_cf = styled_consol_cf.apply(highlight_cf_rows, axis=1)
    
    # Display the consolidated cash flow
    st.dataframe(
        styled_consol_cf,
        use_container_width=True,
        hide_index=True
    )


def prepare_cashflow_data(
    df_projects: pd.DataFrame,
    years: List[int],
    other_revenue_breakdown: Dict[str, Dict[str, float]],
    segment_metrics: Dict[str, Dict[str, float]],
    existing_debt_interest_row: Dict[str, float],
    sga_rows: List[Dict],
    tax_row: Dict[str, float],
    interest_income_by_year: Dict[str, float]
) -> Dict[str, Any]:
    """
    Pre-calculate cash flow data needed for balance sheet and cash flow statements.
    
    Args:
        df_projects: DataFrame containing project data
        years: List of forecast years
        other_revenue_breakdown: Revenue breakdown by segment
        segment_metrics: Metrics for each segment including gross margins
        existing_debt_interest_row: Existing debt interest by year
        sga_rows: List of SG&A rows from P&L
        tax_row: Tax row from P&L
        interest_income_by_year: Interest income by year
    
    Returns:
        Dictionary containing:
        - operating_cf_by_year: Operating cash flow by year
        - investing_cf_by_year: Investing cash flow by year
        - financing_cf_by_year: Financing cash flow by year
        - net_cf_by_year: Net cash flow by year
        - other_segment_revenue_cf: Other segment revenue cash flow
        - other_segment_cogs_cf: Other segment COGS cash flow
        - presales_cf_breakdown: Presales cash flow breakdown by project
        - interest_outflow_breakdown: Interest outflow breakdown by project
        - sga_outflow_breakdown: SG&A outflow breakdown by project
        - tax_outflow_breakdown: Tax outflow breakdown by project
        - land_outflow_breakdown: Land outflow breakdown by project
        - construction_outflow_breakdown: Construction outflow breakdown by project
        - investing_cf_breakdown: Investing cash flow breakdown by project
        - financing_cf_breakdown: Financing cash flow breakdown by project
    """
    # Initialize cash flow aggregates
    operating_cf_by_year = {}
    investing_cf_by_year = {}
    financing_cf_by_year = {}
    net_cf_by_year = {}
    
    # Initialize breakdown components
    other_segment_revenue_cf = {}
    other_segment_cogs_cf = {}
    presales_cf_breakdown = {}
    interest_outflow_breakdown = {}
    sga_outflow_breakdown = {}
    tax_outflow_breakdown = {}
    land_outflow_breakdown = {}
    construction_outflow_breakdown = {}
    investing_cf_breakdown = {}
    financing_cf_breakdown = {}
    
    # Initialize for all years
    for year in years:
        year_str = str(year)
        operating_cf_by_year[year_str] = 0
        investing_cf_by_year[year_str] = 0
        financing_cf_by_year[year_str] = 0
        net_cf_by_year[year_str] = 0
        other_segment_revenue_cf[year_str] = 0
        other_segment_cogs_cf[year_str] = 0
    
    # 1. Calculate revenue and COGS from other business segments (non-real estate)
    if other_revenue_breakdown:
        for segment_name, segment_revenue in other_revenue_breakdown.items():
            for year in years:
                year_str = str(year)
                revenue = segment_revenue.get(year_str, 0)
                other_segment_revenue_cf[year_str] += revenue
                operating_cf_by_year[year_str] += revenue
                
                # Calculate COGS for this segment
                if segment_name in segment_metrics:
                    gross_margin = segment_metrics[segment_name]['gross_margin']
                else:
                    gross_margin = 0.0
                
                segment_cogs = revenue * (1 - gross_margin)
                other_segment_cogs_cf[year_str] += segment_cogs
                operating_cf_by_year[year_str] -= segment_cogs
    
    # 2. Aggregate cash flows from all projects
    for _, project in df_projects.iterrows():
        project_name = project.get('project_name', 'Unknown')
        financial_statements = project.get('comprehensive_financial_statements', {})
        
        if not isinstance(financial_statements, dict):
            financial_statements = {}
        
        # Initialize project breakdown
        if project_name not in presales_cf_breakdown:
            presales_cf_breakdown[project_name] = {}
            interest_outflow_breakdown[project_name] = {}
            sga_outflow_breakdown[project_name] = {}
            tax_outflow_breakdown[project_name] = {}
            land_outflow_breakdown[project_name] = {}
            construction_outflow_breakdown[project_name] = {}
            investing_cf_breakdown[project_name] = {}
            financing_cf_breakdown[project_name] = {}
        
        for year in years:
            year_str = str(year)
            
            if year_str in financial_statements:
                year_data = financial_statements[year_str]
                
                # Operating Cash Flow Components
                presales_inflow = year_data.get('cash_inflow_presales', 0) / 1e9
                presales_cf_breakdown[project_name][year_str] = presales_inflow
                operating_cf_by_year[year_str] += presales_inflow
                
                interest_outflow = year_data.get('cash_outflow_interest', 0) / 1e9
                interest_outflow_breakdown[project_name][year_str] = interest_outflow
                operating_cf_by_year[year_str] += interest_outflow
                
                sga_outflow = year_data.get('cash_outflow_sga', 0) / 1e9
                sga_outflow_breakdown[project_name][year_str] = sga_outflow
                operating_cf_by_year[year_str] += sga_outflow
                
                tax_outflow = year_data.get('cash_outflow_tax', 0) / 1e9
                tax_outflow_breakdown[project_name][year_str] = tax_outflow
                operating_cf_by_year[year_str] += tax_outflow
                
                # Investing Cash Flow
                land_outflow = year_data.get('cash_outflow_land', 0) / 1e9
                construction_outflow = year_data.get('cash_outflow_construction', 0) / 1e9
                
                land_outflow_breakdown[project_name][year_str] = land_outflow
                construction_outflow_breakdown[project_name][year_str] = construction_outflow
                
                investing_cf = land_outflow + construction_outflow
                investing_cf_by_year[year_str] += investing_cf
                investing_cf_breakdown[project_name][year_str] = investing_cf
                
                # Financing Cash Flow
                debt_disbursement = year_data.get('debt_disbursement', 0) / 1e9
                debt_repayment = year_data.get('debt_repayment', 0) / 1e9
                financing_cf = debt_disbursement + debt_repayment
                financing_cf_by_year[year_str] += financing_cf
                financing_cf_breakdown[project_name][year_str] = financing_cf
            else:
                presales_cf_breakdown[project_name][year_str] = 0
                interest_outflow_breakdown[project_name][year_str] = 0
                sga_outflow_breakdown[project_name][year_str] = 0
                tax_outflow_breakdown[project_name][year_str] = 0
                land_outflow_breakdown[project_name][year_str] = 0
                construction_outflow_breakdown[project_name][year_str] = 0
                investing_cf_breakdown[project_name][year_str] = 0
                financing_cf_breakdown[project_name][year_str] = 0
    
    # Add existing debt interest expense to operating cash flow
    for year in years:
        year_str = str(year)
        existing_debt_interest = existing_debt_interest_row.get(str(year), 0)
        operating_cf_by_year[year_str] += existing_debt_interest
    
    # Add SG&A expense from other segments to operating cash flow
    for year in years:
        year_str = str(year)
        total_sga = 0
        for row in sga_rows:
            if row['SG&A Source'] == 'TOTAL SG&A':
                total_sga = row.get(str(year), 0)
                break
        total_proj_sga = sum(sga_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in sga_outflow_breakdown.keys())
        other_sga = total_sga - total_proj_sga
        operating_cf_by_year[year_str] += other_sga
    
    # Add total tax expense to operating cash flow
    for year in years:
        year_str = str(year)
        project_taxes = sum(tax_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in tax_outflow_breakdown.keys())
        operating_cf_by_year[year_str] -= project_taxes
        total_tax_pnl = tax_row.get(year_str, 0)
        operating_cf_by_year[year_str] += total_tax_pnl
    
    # Add interest income to investing cash flow
    for year in years:
        year_str = str(year)
        interest_income_cf = interest_income_by_year.get(year_str, 0)
        investing_cf_by_year[year_str] += interest_income_cf
    
    # Calculate net cash flow for each year
    for year in years:
        year_str = str(year)
        net_cf_by_year[year_str] = (
            operating_cf_by_year[year_str] + 
            investing_cf_by_year[year_str] + 
            financing_cf_by_year[year_str]
        )
    
    return {
        'operating_cf_by_year': operating_cf_by_year,
        'investing_cf_by_year': investing_cf_by_year,
        'financing_cf_by_year': financing_cf_by_year,
        'net_cf_by_year': net_cf_by_year,
        'other_segment_revenue_cf': other_segment_revenue_cf,
        'other_segment_cogs_cf': other_segment_cogs_cf,
        'presales_cf_breakdown': presales_cf_breakdown,
        'interest_outflow_breakdown': interest_outflow_breakdown,
        'sga_outflow_breakdown': sga_outflow_breakdown,
        'tax_outflow_breakdown': tax_outflow_breakdown,
        'land_outflow_breakdown': land_outflow_breakdown,
        'construction_outflow_breakdown': construction_outflow_breakdown,
        'investing_cf_breakdown': investing_cf_breakdown,
        'financing_cf_breakdown': financing_cf_breakdown
    }