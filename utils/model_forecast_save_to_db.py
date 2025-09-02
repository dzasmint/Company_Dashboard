"""
Utility functions for saving consolidated financial statements to MongoDB
Extracted from tabs/model_forecast.py for better organization
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, List, Any, Optional
from utils.mongodb_utils import save_company_forecast


def convert_to_native(obj):
    """Convert numpy types to native Python types for MongoDB"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        # Recursively convert dictionary values
        return {k: convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Recursively convert list items
        return [convert_to_native(item) for item in obj]
    elif pd.isna(obj):
        return 0
    else:
        return obj


def prepare_pnl_data(
    year_str: str,
    re_revenue_row: Dict,
    revenue_row: Dict,
    re_cogs_row: Dict,
    total_cogs_pnl_row: Dict,
    gp_row: Dict,
    sga_row: Dict,
    ebitda_row: Dict,
    interest_income_row: Dict,
    project_interest_pnl_row: Dict,
    existing_interest_pnl_row: Dict,
    interest_row: Dict,
    pbt_row: Dict,
    tax_row: Dict,
    pat_row: Dict,
    minority_interest_row: Dict,
    npatmi_row: Dict
) -> Dict:
    """Prepare P&L statement data for a specific year"""
    # Convert from billions to raw VND values for database storage
    return {
        'real_estate_revenue': convert_to_native(re_revenue_row.get(year_str, 0) * 1e9),
        'other_revenue': convert_to_native((revenue_row.get(year_str, 0) - re_revenue_row.get(year_str, 0)) * 1e9),
        'net_revenue': convert_to_native(revenue_row.get(year_str, 0) * 1e9),
        'real_estate_cogs': convert_to_native(re_cogs_row.get(year_str, 0) * 1e9),
        'other_cogs': convert_to_native((total_cogs_pnl_row.get(year_str, 0) - re_cogs_row.get(year_str, 0)) * 1e9),
        'total_cogs': convert_to_native(total_cogs_pnl_row.get(year_str, 0) * 1e9),
        'gross_profit': convert_to_native(gp_row.get(year_str, 0) * 1e9),
        'sga': convert_to_native(sga_row.get(year_str, 0) * 1e9),
        'ebitda': convert_to_native(ebitda_row.get(year_str, 0) * 1e9),
        'interest_income': convert_to_native(interest_income_row.get(year_str, 0) * 1e9),
        'project_interest_expense': convert_to_native(project_interest_pnl_row.get(year_str, 0) * 1e9),
        'existing_debt_interest_expense': convert_to_native(existing_interest_pnl_row.get(year_str, 0) * 1e9),
        'interest_expense': convert_to_native(interest_row.get(year_str, 0) * 1e9),
        'pbt': convert_to_native(pbt_row.get(year_str, 0) * 1e9),
        'tax': convert_to_native(tax_row.get(year_str, 0) * 1e9),
        'pat': convert_to_native(pat_row.get(year_str, 0) * 1e9),
        'minority_interest': convert_to_native(minority_interest_row.get(year_str, 0) * 1e9),
        'npatmi': convert_to_native(npatmi_row.get(year_str, 0) * 1e9)
    }


def prepare_balance_sheet_data(
    year_str: str,
    cash_row: Dict,
    ar_row: Dict,
    inventory_row: Dict,
    other_assets_row: Dict,
    total_assets_row: Dict,
    ap_row: Dict,
    customer_prepayment_row: Dict,
    st_debt_row: Dict,
    lt_debt_row: Dict,
    total_debt_by_year: Dict,
    other_liab_row: Dict,
    total_liab_row: Dict,
    retained_earnings_row: Dict,
    minority_interest_bs_row: Dict,
    other_equity_row: Dict,
    total_equity_row: Dict
) -> Dict:
    """Prepare balance sheet data for a specific year"""
    # Convert from billions to raw VND values for database storage
    return {
        'assets': {
            'cash_and_equivalents': convert_to_native(cash_row.get(year_str, 0) * 1e9),
            'account_receivable': convert_to_native(ar_row.get(year_str, 0) * 1e9),
            'inventory': convert_to_native(inventory_row.get(year_str, 0) * 1e9),
            'other_assets': convert_to_native(other_assets_row.get(year_str, 0) * 1e9),
            'total_assets': convert_to_native(total_assets_row.get(year_str, 0) * 1e9)
        },
        'liabilities': {
            'account_payable': convert_to_native(ap_row.get(year_str, 0) * 1e9),
            'customer_prepayment': convert_to_native(customer_prepayment_row.get(year_str, 0) * 1e9),
            'short_term_debt': convert_to_native(st_debt_row.get(year_str, 0) * 1e9),
            'long_term_debt': convert_to_native(lt_debt_row.get(year_str, 0) * 1e9),
            'total_debt': convert_to_native(total_debt_by_year.get(year_str, 0) * 1e9),
            'other_liabilities': convert_to_native(other_liab_row.get(year_str, 0) * 1e9),
            'total_liabilities': convert_to_native(total_liab_row.get(year_str, 0) * 1e9)
        },
        'equity': {
            'retained_earnings': convert_to_native(retained_earnings_row.get(year_str, 0) * 1e9),
            'minority_interest': convert_to_native(minority_interest_bs_row.get(year_str, 0) * 1e9),
            'other_equity': convert_to_native(other_equity_row.get(year_str, 0) * 1e9),
            'total_equity': convert_to_native(total_equity_row.get(year_str, 0) * 1e9)
        },
        # Derived metrics
        'net_debt': convert_to_native((total_debt_by_year.get(year_str, 0) - cash_row.get(year_str, 0)) * 1e9),
        'working_capital': convert_to_native((inventory_row.get(year_str, 0) + cash_row.get(year_str, 0) - customer_prepayment_row.get(year_str, 0)) * 1e9)
    }


def prepare_cash_flow_data(
    year_str: str,
    presales_cf_breakdown: Dict,
    other_segment_revenue_cf: Dict,
    other_segment_cogs_cf: Dict,
    interest_outflow_breakdown: Dict,
    existing_debt_interest_row: Dict,
    sga_outflow_breakdown: Dict,
    other_sga_cf_row: Dict,
    tax_outflow_breakdown: Dict,
    operating_cf_by_year: Dict,
    land_outflow_breakdown: Dict,
    construction_outflow_breakdown: Dict,
    interest_income_row: Dict,
    investing_cf_by_year: Dict,
    financing_cf_breakdown: Dict,
    financing_cf_by_year: Dict,
    net_cf_by_year: Dict
) -> Dict:
    """Prepare cash flow statement data for a specific year"""
    # Convert from billions to raw VND values for database storage
    return {
        'operating': {
            'presales_inflow': convert_to_native(sum(presales_cf_breakdown.get(p, {}).get(year_str, 0) for p in presales_cf_breakdown) * 1e9),
            'other_segment_revenue': convert_to_native(other_segment_revenue_cf.get(year_str, 0) * 1e9),
            'other_segment_cogs': convert_to_native(other_segment_cogs_cf.get(year_str, 0) * 1e9),
            'project_interest_expense': convert_to_native(sum(interest_outflow_breakdown.get(p, {}).get(year_str, 0) for p in interest_outflow_breakdown) * 1e9),
            'existing_debt_interest': convert_to_native(existing_debt_interest_row.get(year_str, 0) * 1e9),
            'project_sga': convert_to_native(sum(sga_outflow_breakdown.get(p, {}).get(year_str, 0) for p in sga_outflow_breakdown) * 1e9),
            'other_segment_sga': convert_to_native(other_sga_cf_row.get(year_str, 0) * 1e9),
            'tax': convert_to_native(sum(tax_outflow_breakdown.get(p, {}).get(year_str, 0) for p in tax_outflow_breakdown) * 1e9),
            'total_operating': convert_to_native(operating_cf_by_year.get(year_str, 0) * 1e9)
        },
        'investing': {
            'land_outflow': convert_to_native(sum(land_outflow_breakdown.get(p, {}).get(year_str, 0) for p in land_outflow_breakdown) * 1e9),
            'construction_outflow': convert_to_native(sum(construction_outflow_breakdown.get(p, {}).get(year_str, 0) for p in construction_outflow_breakdown) * 1e9),
            'interest_income': convert_to_native(interest_income_row.get(year_str, 0) * 1e9),
            'total_investing': convert_to_native(investing_cf_by_year.get(year_str, 0) * 1e9)
        },
        'financing': {
            'debt_changes': convert_to_native(sum(financing_cf_breakdown.get(p, {}).get(year_str, 0) for p in financing_cf_breakdown) * 1e9),
            'total_financing': convert_to_native(financing_cf_by_year.get(year_str, 0) * 1e9)
        },
        'net_cash_flow': convert_to_native(net_cf_by_year.get(year_str, 0) * 1e9)
    }


def prepare_business_segments_data(
    year_str: str,
    segment_revenue_data: Dict,
    segment_cogs_data: Dict,
    base_year_revenues_keys: List
) -> Dict:
    """Prepare business segments data for a specific year"""
    business_segments_data = {}
    for segment_name in base_year_revenues_keys:
        if segment_name in segment_revenue_data:
            business_segments_data[segment_name] = {
                'revenue': convert_to_native(segment_revenue_data[segment_name].get(year_str, 0) * 1e9),
                'cogs': convert_to_native(segment_cogs_data[segment_name].get(year_str, 0) * 1e9),
                'gross_profit': convert_to_native((segment_revenue_data[segment_name].get(year_str, 0) + segment_cogs_data[segment_name].get(year_str, 0)) * 1e9)
            }
    return business_segments_data


def prepare_project_breakdown_data(
    year: int,
    year_str: str,
    project_revenue_breakdown: Dict,
    project_cogs_breakdown: Dict,
    project_sga_breakdown: Dict,
    project_interest_breakdown: Dict,
    project_pbt_breakdown: Dict,
    project_pat_breakdown: Dict,
    project_patmi_breakdown: Dict,
    project_minority_interest_breakdown: Dict,
    project_revenue_by_year: Dict = None,
    project_cogs_by_year: Dict = None
) -> Dict:
    """Prepare project breakdown data for a specific year"""
    return {
        'revenue': {p: convert_to_native(project_revenue_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_revenue_breakdown},
        'cogs': {p: convert_to_native(project_cogs_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_cogs_breakdown},
        'gross_profit': {p: convert_to_native((project_revenue_breakdown.get(p, {}).get(year, 0) + project_cogs_breakdown.get(p, {}).get(year, 0)) * 1e9) for p in project_revenue_breakdown},
        'sga': {p: convert_to_native(project_sga_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_sga_breakdown},
        'interest': {p: convert_to_native(project_interest_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_interest_breakdown},
        'pbt': {p: convert_to_native(project_pbt_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_pbt_breakdown if p in project_pbt_breakdown},
        'pat': {p: convert_to_native(project_pat_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_pat_breakdown},
        'patmi': {p: convert_to_native(project_patmi_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_patmi_breakdown},
        'minority_interest': {p: convert_to_native(project_minority_interest_breakdown.get(p, {}).get(year, {}).get('minority_interest', 0) * 1e9) for p in project_minority_interest_breakdown if year in project_minority_interest_breakdown.get(p, {})}
    }


def prepare_profitability_metrics(
    year: int,
    pnl_data: Dict,
    project_revenue_breakdown: Dict,
    project_cogs_breakdown: Dict,
    project_sga_breakdown: Dict,
    project_pbt_breakdown: Dict,
    project_pat_breakdown: Dict,
    project_patmi_breakdown: Dict,
    project_revenue_by_year: Dict,
    project_cogs_by_year: Dict
) -> Dict:
    """Prepare profitability metrics for a specific year"""
    return {
        'project_margins': {
            p: {
                'gross_margin': convert_to_native((project_revenue_breakdown.get(p, {}).get(year, 0) + project_cogs_breakdown.get(p, {}).get(year, 0)) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                'sga_margin': convert_to_native(-project_sga_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                'pbt_margin': convert_to_native(project_pbt_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 and p in project_pbt_breakdown else 0,
                'pat_margin': convert_to_native(project_pat_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                'patmi_margin': convert_to_native(project_patmi_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0
            } for p in project_revenue_breakdown if project_revenue_breakdown.get(p, {}).get(year, 0) > 0
        },
        'aggregated_project_margins': {
            'total_projects_revenue': convert_to_native(project_revenue_by_year.get(year, 0) * 1e9),
            'total_projects_gross_profit': convert_to_native((project_revenue_by_year.get(year, 0) + project_cogs_by_year.get(year, 0)) * 1e9),
            'total_projects_gross_margin': convert_to_native((project_revenue_by_year.get(year, 0) + project_cogs_by_year.get(year, 0)) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
            'total_projects_sga_margin': convert_to_native(-sum(project_sga_breakdown.get(p, {}).get(year, 0) for p in project_sga_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
            'total_projects_pbt_margin': convert_to_native(sum(project_pbt_breakdown.get(p, {}).get(year, 0) for p in project_pbt_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
            'total_projects_pat_margin': convert_to_native(sum(project_pat_breakdown.get(p, {}).get(year, 0) for p in project_pat_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
            'total_projects_patmi_margin': convert_to_native(sum(project_patmi_breakdown.get(p, {}).get(year, 0) for p in project_patmi_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0
        },
        'consolidated_margins': {
            'gross_margin': convert_to_native((pnl_data['gross_profit'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
            'ebitda_margin': convert_to_native((pnl_data['ebitda'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
            'pbt_margin': convert_to_native((pnl_data['pbt'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
            'pat_margin': convert_to_native((pnl_data['pat'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
            'patmi_margin': convert_to_native((pnl_data['npatmi'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0
        }
    }


def prepare_balance_sheet_detail_data(
    year_str: str,
    debt_change_breakdown: Dict,
    inventory_change_breakdown: Dict,
    prepayment_change_breakdown: Dict,
    cash_change_breakdown: Dict
) -> Dict:
    """Prepare detail balance sheet data for a specific year"""
    return {
        'debt_changes': {p: convert_to_native(debt_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in debt_change_breakdown},
        'inventory_changes': {p: convert_to_native(inventory_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in inventory_change_breakdown},
        'prepayment_changes': {p: convert_to_native(prepayment_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in prepayment_change_breakdown},
        'cash_changes': {p: convert_to_native(cash_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in cash_change_breakdown}
    }


def prepare_cash_flow_detail_data(
    year_str: str,
    presales_cf_breakdown: Dict,
    land_outflow_breakdown: Dict,
    construction_outflow_breakdown: Dict,
    interest_outflow_breakdown: Dict,
    sga_outflow_breakdown: Dict,
    tax_outflow_breakdown: Dict,
    financing_cf_breakdown: Dict
) -> Dict:
    """Prepare detail cash flow data for a specific year"""
    cash_flow_detail_data = {'by_project': {}}
    
    for project_name in presales_cf_breakdown.keys():
        cash_flow_detail_data['by_project'][project_name] = {
            'presales_inflow': convert_to_native(presales_cf_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'land_outflow': convert_to_native(land_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'construction_outflow': convert_to_native(construction_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'interest_outflow': convert_to_native(interest_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'sga_outflow': convert_to_native(sga_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'tax_outflow': convert_to_native(tax_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'debt_changes': convert_to_native(financing_cf_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
            'net_cash_flow': convert_to_native(
                (presales_cf_breakdown.get(project_name, {}).get(year_str, 0) +
                land_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                construction_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                interest_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                sga_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                tax_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                financing_cf_breakdown.get(project_name, {}).get(year_str, 0)) * 1e9
            )
        }
    
    return cash_flow_detail_data


def save_consolidated_financial_statements(
    selected_ticker: str,
    base_year: int,
    years: List[int],
    pnl_rows: Dict[str, Dict],
    balance_sheet_rows: Dict[str, Dict],
    cash_flow_aggregates: Dict[str, Dict],
    cash_flow_breakdowns: Dict[str, Dict],
    project_breakdowns: Dict[str, Dict],
    segment_data: Dict[str, Dict],
    balance_sheet_details: Dict[str, Dict],
    session_state_data: Dict
) -> Dict:
    """
    Save all consolidated financial statements to MongoDB
    
    Returns:
        Dictionary with success status and message
    """
    # Prepare consolidated financial data for MongoDB
    consolidated_data = {
        'ticker': selected_ticker,
        'base_year': int(base_year),
        'forecast_years': [str(y) for y in years],
        'timestamp': pd.Timestamp.now().isoformat(),
        'financial_statements': {}
    }
    
    for year in years:
        year_str = str(year)
        
        # Prepare P&L data
        pnl_data = prepare_pnl_data(
            year_str,
            **pnl_rows
        )
        
        # Prepare balance sheet data
        balance_sheet_data = prepare_balance_sheet_data(
            year_str,
            **balance_sheet_rows
        )
        
        # Prepare cash flow data
        cash_flow_data = prepare_cash_flow_data(
            year_str,
            **cash_flow_aggregates,
            **cash_flow_breakdowns
        )
        
        # Prepare business segments data
        business_segments_data = prepare_business_segments_data(
            year_str,
            segment_data['segment_revenue_data'],
            segment_data['segment_cogs_data'],
            session_state_data['base_year_revenues'].keys()
        )
        
        # Prepare project breakdown data
        project_breakdown = prepare_project_breakdown_data(
            year,
            year_str,
            **project_breakdowns
        )
        
        # Prepare profitability metrics
        profitability_metrics = prepare_profitability_metrics(
            year,
            pnl_data,
            project_breakdowns['project_revenue_breakdown'],
            project_breakdowns['project_cogs_breakdown'],
            project_breakdowns['project_sga_breakdown'],
            project_breakdowns['project_pbt_breakdown'],
            project_breakdowns['project_pat_breakdown'],
            project_breakdowns['project_patmi_breakdown'],
            project_breakdowns['project_revenue_by_year'],
            project_breakdowns['project_cogs_by_year']
        )
        
        # Prepare balance sheet detail data
        balance_sheet_detail_data = prepare_balance_sheet_detail_data(
            year_str,
            **balance_sheet_details
        )
        
        # Prepare cash flow detail data
        cash_flow_detail_data = prepare_cash_flow_detail_data(
            year_str,
            cash_flow_breakdowns['presales_cf_breakdown'],
            cash_flow_breakdowns['land_outflow_breakdown'],
            cash_flow_breakdowns['construction_outflow_breakdown'],
            cash_flow_breakdowns['interest_outflow_breakdown'],
            cash_flow_breakdowns['sga_outflow_breakdown'],
            cash_flow_breakdowns['tax_outflow_breakdown'],
            cash_flow_breakdowns['financing_cf_breakdown']
        )
        
        # Combine all statements for this year
        consolidated_data['financial_statements'][year_str] = {
            'pnl': pnl_data,
            'balance_sheet': balance_sheet_data,
            'balance_sheet_detail': balance_sheet_detail_data,
            'cash_flow': cash_flow_data,
            'cash_flow_detail': cash_flow_detail_data,
            'business_segments': business_segments_data,
            'project_breakdown': project_breakdown,
            'profitability_metrics': profitability_metrics
        }
    
    # Apply deep conversion to entire consolidated_data to ensure all numpy types are converted
    consolidated_data = convert_to_native(consolidated_data)
    
    # Extract all financial statements data for CompanyForecast collection
    forecast_data = {}
    for year_str, year_data in consolidated_data['financial_statements'].items():
        forecast_data[year_str] = {
            'pnl': year_data.get('pnl', {}),
            'balance_sheet': year_data.get('balance_sheet', {}),
            'balance_sheet_detail': year_data.get('balance_sheet_detail', {}),
            'cash_flow': year_data.get('cash_flow', {}),
            'cash_flow_detail': year_data.get('cash_flow_detail', {}),
            'business_segments': year_data.get('business_segments', {}),
            'project_breakdown': year_data.get('project_breakdown', {}),
            'profitability_metrics': year_data.get('profitability_metrics', {})
        }
    
    # Save to CompanyForecast collection
    result = save_company_forecast(selected_ticker, forecast_data)
    
    # Store in session state for reference if successful
    if result['success']:
        st.session_state[f'saved_consolidated_{selected_ticker}'] = consolidated_data
    
    return result, forecast_data


def render_save_section(
    selected_ticker: str,
    base_year: int,
    years: List[int],
    pnl_rows: Dict[str, Dict],
    balance_sheet_rows: Dict[str, Dict],
    cash_flow_aggregates: Dict[str, Dict],
    cash_flow_breakdowns: Dict[str, Dict],
    project_breakdowns: Dict[str, Dict],
    segment_data: Dict[str, Dict],
    balance_sheet_details: Dict[str, Dict],
    session_state_data: Dict
) -> None:
    """Render the save to MongoDB section with button and feedback"""
    
    st.markdown("---")
    st.subheader("Save Consolidated Financial Statements")
    
    col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
    with col_save2:
        if st.button("Save All Consolidated Statements to Database", type="primary", use_container_width=True):
            result, forecast_data = save_consolidated_financial_statements(
                selected_ticker,
                base_year,
                years,
                pnl_rows,
                balance_sheet_rows,
                cash_flow_aggregates,
                cash_flow_breakdowns,
                project_breakdowns,
                segment_data,
                balance_sheet_details,
                session_state_data
            )
            
            # Debug: Check if interest_income is present in the data
            has_interest_income = False
            for year_str in forecast_data.keys():
                if 'pnl' in forecast_data[year_str] and 'interest_income' in forecast_data[year_str]['pnl']:
                    interest_val = forecast_data[year_str]['pnl']['interest_income']
                    if interest_val != 0:
                        # Values are now in raw VND, convert to billions for display
                        st.info(f"💡 Interest Income for {year_str}: {interest_val/1e9:,.2f}B VND")
                        has_interest_income = True
                else:
                    st.warning(f"⚠️ Interest Income missing or zero for {year_str}")
            
            if not has_interest_income:
                st.warning("⚠️ No interest income values found in any year. Check if cash balances are positive.")
            
            if result['success']:
                st.success(f"✅ {result['message']}")
            else:
                st.error(f"❌ {result['message']}")
    
    st.info("💡 This saves all three consolidated financial statements (P&L, Balance Sheet, Cash Flow) to the CompanyForecast collection in MongoDB for reporting and analysis.")