#%%
from dotenv import load_dotenv
import pandas as pd
import requests
import re
import numpy as np

def selling_progress_schedule_custom(
    total_revenue: float,
    project_start_year: int,
    current_year: int,
    sale_start_year: int,
    sale_num_years: int,
    end_booking_year: int,
    distribution: dict = None
) -> list:
    """
    Distribute total revenue based on custom distribution or evenly over years.
    
    Args:
        total_revenue (float): Total revenue
        project_start_year (int): Project start year
        current_year (int): Current year
        sale_start_year (int): Year selling begins
        sale_num_years (int): Number of years selling takes
        end_booking_year (int): Project completion year
        distribution (dict): Custom distribution {year_str: percentage} or None for even split
    
    Returns:
        List[float]: Annual revenue array from project_start_year to end_booking_year
    """
    if end_booking_year < sale_start_year:
        raise ValueError("Revenue booking end year must be >= sale start year")
    if (sale_start_year + sale_num_years - 1) > end_booking_year:
        raise ValueError("Selling period exceeds revenue booking end year")

    # Build full year list from project_start_year to end_booking_year
    full_years = list(range(project_start_year, end_booking_year + 1))
    revenue_by_year = [0.0] * len(full_years)
    
    if distribution and isinstance(distribution, dict):
        # Use custom distribution
        for i, year in enumerate(full_years):
            if sale_start_year <= year < sale_start_year + sale_num_years:
                # Get percentage for this year from distribution
                year_pct = distribution.get(str(year), 0.0) / 100.0
                revenue_by_year[i] = total_revenue * year_pct
    else:
        # Use even distribution (original logic)
        annual_revenue = total_revenue / sale_num_years
        for i, year in enumerate(full_years):
            if sale_start_year <= year < sale_start_year + sale_num_years:
                revenue_by_year[i] = annual_revenue
    
    return revenue_by_year

def selling_progress_schedule(
    total_revenue: float,
    project_start_year: int,
    current_year: int,
    sale_start_year: int,
    sale_num_years: int,
    end_booking_year: int
) -> list:
    """
    Distribute total revenue evenly over a given number of years (num_years),
    starting from start_year. Output is aligned from project_start_year to end_booking_year.
    Now allows start_year to be before current_year for historical tracking.

    Args:
        total_revenue (float): Total revenue
        current_year (int): Start year of the output array
        project_start_year (int): Year selling begins (can be < current_year)
        sale_num_years (int): Number of years selling takes
        end_booking_year (int): Project completion year

    Returns:
        List[float]: Annual revenue array from current_year to complete_year
    """
    if end_booking_year < sale_start_year:
        raise ValueError("Revenue booking end year must be >= sale start year")
    if (sale_start_year + sale_num_years - 1) > end_booking_year:
        raise ValueError("Selling period exceeds revenue booking end year")

    annual_revenue = total_revenue / sale_num_years

    # Build full year list from project_start_year to end_booking_year
    full_years = list(range(project_start_year, end_booking_year + 1))

    # Create array with revenue in the selling years only
    revenue_by_year = [
        annual_revenue if sale_start_year <= year < sale_start_year + sale_num_years else 0.0
        for year in full_years
    ]

    return revenue_by_year

def land_use_right_payment_schedule_single_year(
    total_payment: float,
    project_start_year: int,
    current_year: int,
    payment_year: int,
    end_booking_year: int
) -> list:
    """
    Generate land use right payment schedule from current_year to complete_year,
    with the entire payment made in payment_year.
    """
    if payment_year > end_booking_year:
        raise ValueError("payment_year must be earlier than end_booking_year")
    
    if payment_year < project_start_year:
        raise ValueError("payment_year must be later than project_start_year")

    num_years = end_booking_year - project_start_year + 1
    payment_array = [0.0] * num_years

    payment_index = payment_year - project_start_year
    payment_array[payment_index] = total_payment

    return payment_array

def construction_payment_schedule(
    total_cost: float,
    project_start_year: int,
    current_year: int,
    construction_start_year: int,
    num_years: int,
    end_booking_year: int
) -> list:
    """
    Distribute total construction cost evenly over num_years starting from construction_start_year.
    Output is aligned from current_year to end_booking_year.
    Now allows construction_start_year to be before current_year for historical tracking.
    """
    if end_booking_year < construction_start_year:
        raise ValueError("end_booking_year must be >= construction_start_year")
    if (construction_start_year + num_years - 1) > end_booking_year:
        raise ValueError("Construction period exceeds project completion year")

    annual_cost = total_cost / num_years

    # Create timeline from current_year to end_booking_year
    full_years = list(range(project_start_year, end_booking_year + 1))

    # Allocate cost to construction years
    cost_by_year = [
        annual_cost if construction_start_year <= year < construction_start_year + num_years else 0.0
        for year in full_years
    ]

    return cost_by_year

def sga_payment_schedule_custom(
    total_sga: float,
    project_start_year: int,
    current_year: int,
    sale_start_year: int,
    num_years: int,
    end_booking_year: int,
    distribution: dict = None
) -> list:
    """
    Distribute total SG&A based on custom distribution or evenly over years.
    
    Args:
        total_sga (float): Total SG&A
        project_start_year (int): Project start year
        current_year (int): Current year
        sale_start_year (int): Year selling begins
        num_years (int): Number of years selling takes
        end_booking_year (int): Project completion year
        distribution (dict): Custom distribution {year_str: percentage} or None for even split
    
    Returns:
        List[float]: Annual SG&A array from project_start_year to end_booking_year
    """
    if end_booking_year < sale_start_year:
        raise ValueError("end_booking_year must be >= sale_start_year")
    if (sale_start_year + num_years - 1) > end_booking_year:
        raise ValueError("SG&A period exceeds project completion year")

    # Build full year list from project_start_year to end_booking_year
    full_years = list(range(project_start_year, end_booking_year + 1))
    sga_by_year = [0.0] * len(full_years)
    
    if distribution and isinstance(distribution, dict):
        # Use custom distribution (same as revenue)
        for i, year in enumerate(full_years):
            if sale_start_year <= year < sale_start_year + num_years:
                # Get percentage for this year from distribution
                year_pct = distribution.get(str(year), 0.0) / 100.0
                sga_by_year[i] = total_sga * year_pct
    else:
        # Use even distribution (original logic)
        annual_sga = total_sga / num_years
        for i, year in enumerate(full_years):
            if sale_start_year <= year < sale_start_year + num_years:
                sga_by_year[i] = annual_sga
    
    return sga_by_year

def sga_payment_schedule(
    total_sga: float,
    project_start_year: int,
    current_year: int,
    sale_start_year: int,
    num_years: int,
    end_booking_year: int
) -> list:
    """
    Distribute total SG&A evenly over a given number of years (num_years),
    starting from sale_start_year. Output is aligned from current_year to end_booking_year.
    Now allows sale_start_year to be before current_year for historical tracking.
    """
    if end_booking_year < sale_start_year:
        raise ValueError("end_booking_year must be >= sale_start_year")
    if (sale_start_year + num_years - 1) > end_booking_year:
        raise ValueError("SG&A period exceeds project completion year")

    annual_sga = total_sga / num_years

    # Build full year list from current_year to complete_year
    full_years = list(range(project_start_year, end_booking_year + 1))

    # Create array with SG&A in the active years only
    sga_by_year = [
        annual_sga if sale_start_year <= year < sale_start_year + num_years else 0.0
        for year in full_years
    ]

    return sga_by_year

def generate_pnl_schedule_custom(
    total_revenue: float,
    total_land_payment: float,
    total_construction_payment: float,
    total_sga: float,
    project_start_year: int,
    current_year: int,
    start_booking_year: int,
    end_booking_year: int,
    debt_amount: float = 0.0,
    debt_length: int = 0,
    interest_rate: float = 0.0,
    revenue_distribution: dict = None
) -> pd.DataFrame:
    """
    Generate a P&L schedule with custom revenue distribution.
    
    Args:
        Same as generate_pnl_schedule plus:
        revenue_distribution (dict): Custom revenue distribution {year_str: percentage}
    
    Returns:
        pd.DataFrame: Year-by-year P&L table
    """
    if end_booking_year < start_booking_year:
        raise ValueError("end_booking_year must be >= start_booking_year")

    # Calculate annual interest expense
    total_booking_years = end_booking_year - start_booking_year + 1
    total_interest_expense = debt_amount * interest_rate * debt_length
    annual_interest_expense = (total_interest_expense / total_booking_years) if total_booking_years > 0 else 0.0

    pnl_data = []
    for year in range(project_start_year, end_booking_year + 1):
        # Determine if this is historical or future
        is_historical = year < current_year
        year_type = "Historical" if is_historical else "Future"
        
        if year < start_booking_year:
            # Before revenue booking starts, all values are zero
            revenue = 0.0
            land_cost = 0.0
            sga = 0.0
            construction = 0.0
            interest_expense = 0.0  
            ebitda = 0.0
            ebit = 0.0  
            pbt = 0.0
            tax = 0.0
            pat = 0.0
        else:
            # Use custom distribution if provided
            if revenue_distribution and isinstance(revenue_distribution, dict):
                year_pct = revenue_distribution.get(str(year), 0.0) / 100.0
                revenue = total_revenue * year_pct
                # All P&L items follow revenue distribution pattern
                sga = total_sga * year_pct
                land_cost = total_land_payment * year_pct  # Proportionate to revenue
                construction = total_construction_payment * year_pct  # Proportionate to revenue
            else:
                # Even distribution (original logic)
                revenue = total_revenue / total_booking_years
                land_cost = total_land_payment / total_booking_years
                sga = total_sga / total_booking_years
                construction = total_construction_payment / total_booking_years
            
            interest_expense = annual_interest_expense
            
            # Calculate P&L items
            ebitda = revenue + land_cost + sga  # land_cost and sga are negative
            ebit = ebitda + construction  # construction is negative
            pbt = ebit - interest_expense  # interest is positive expense
            tax = pbt * 0.2 if pbt > 0 else 0.0
            pat = pbt - tax
        
        pnl_data.append({
            "Year": year,
            "Type": year_type,
            "Revenue": revenue,
            "Land Payment": land_cost,
            "Construction Payment": construction,
            "SG&A": sga,
            "EBITDA": ebitda,
            "Interest Expense": interest_expense,
            "PBT": pbt,
            "Tax Expense (20%)": tax,
            "PAT": pat
        })
    
    # Add summary row
    summary_revenue = sum(row["Revenue"] for row in pnl_data)
    summary_land = sum(row["Land Payment"] for row in pnl_data)
    summary_construction = sum(row["Construction Payment"] for row in pnl_data)
    summary_sga = sum(row["SG&A"] for row in pnl_data)
    summary_ebitda = sum(row["EBITDA"] for row in pnl_data)
    summary_interest = sum(row["Interest Expense"] for row in pnl_data)
    summary_pbt = sum(row["PBT"] for row in pnl_data)
    summary_tax = sum(row["Tax Expense (20%)"] for row in pnl_data)
    summary_pat = sum(row["PAT"] for row in pnl_data)
    
    pnl_data.append({
        "Year": "Total",
        "Type": "Summary",
        "Revenue": summary_revenue,
        "Land Payment": summary_land,
        "Construction Payment": summary_construction,
        "SG&A": summary_sga,
        "EBITDA": summary_ebitda,
        "Interest Expense": summary_interest,
        "PBT": summary_pbt,
        "Tax Expense (20%)": summary_tax,
        "PAT": summary_pat
    })
    
    return pd.DataFrame(pnl_data)

def generate_pnl_schedule(
    total_revenue: float,
    total_land_payment: float,
    total_construction_payment: float,
    total_sga: float,
    project_start_year: int,
    current_year: int,
    start_booking_year: int,
    end_booking_year: int,
    debt_amount: float = 0.0,
    debt_length: int = 0,
    interest_rate: float = 0.0
) -> pd.DataFrame:
    """
    Generate a simplified P&L schedule from start_booking_year to end_booking_year.
    Shows both historical and future data with proper labeling.
    Now includes debt and interest expense calculations.
    
    Args:
        total_revenue (float): Total revenue (VND)
        total_land_payment (float): Total land use cost (VND) - negative value
        total_construction_payment (float): Total construction payment (VND) - negative value
        total_sga (float): Total SG&A (VND) - negative value
        current_year (int): Current year (for historical vs future classification)
        start_booking_year (int): Year revenue booking starts
        end_booking_year (int): Year revenue booking ends
        debt_amount (float): Total debt amount (VND) - positive value
        interest_rate (float): Annual interest rate (e.g., 0.08 for 8%)
        
    Returns:
        pd.DataFrame: Year-by-year P&L table with debt and interest calculations
    """
    if end_booking_year < start_booking_year:
        raise ValueError("end_booking_year must be >= start_booking_year")

    # Calculate annual amounts based on total booking period
    total_booking_years = end_booking_year - start_booking_year + 1
    revenue_annual = total_revenue / total_booking_years if total_booking_years > 0 else 0
    land_payment_annual = total_land_payment / total_booking_years if total_booking_years > 0 else 0
    sga_annual = total_sga / total_booking_years if total_booking_years > 0 else 0
    construction_annual = total_construction_payment / total_booking_years if total_booking_years > 0 else 0
    
    # Calculate annual interest expense
    total_interest_expense = debt_amount * interest_rate * debt_length
    annual_interest_expense = (total_interest_expense / total_booking_years) if total_booking_years > 0 else 0.0

    pnl_data = []
    for year in range(project_start_year, end_booking_year + 1):
        # Determine if this is historical or future
        is_historical = year < current_year
        year_type = "Historical" if is_historical else "Future"
        if year < start_booking_year:
            # Before revenue booking starts, all values are zero
            revenue = 0.0
            land_cost = 0.0
            sga = 0.0
            construction = 0.0
            interest_expense = 0.0  
            ebitda = 0.0
            ebit = 0.0  
            pbt = 0.0
            tax = 0.0
            pat = 0.0
        else:
            # All years in the booking period have values
            revenue = revenue_annual
            land_cost = land_payment_annual
            sga = sga_annual
            construction = construction_annual
            interest_expense = annual_interest_expense
            ebitda = revenue + land_cost + sga + construction
            ebit = ebitda    
            pbt = ebit + interest_expense
            tax = -pbt * 0.2 if pbt > 0 else 0.0
            pat = pbt + tax  # tax is negative when there's profit

        pnl_data.append({
            "Year": year,
            "Type": year_type,
            "Revenue": revenue,
            "Land Payment": land_cost,
            "Construction": construction,
            "SG&A": sga,
            "EBITDA": ebitda,
            "Interest Expense": interest_expense,
            "Profit Before Tax": pbt,
            "Tax Expense (20%)": tax,
            "Profit After Tax": pat
        })

    df = pd.DataFrame(pnl_data)
    
    # Add total rows for historical, future, and overall
    historical_df = df[df["Type"] == "Historical"]
    future_df = df[df["Type"] == "Future"]
    
    # Add subtotals
    if not historical_df.empty:
        historical_total = {
            "Year": "Total (Historical)",
            "Type": "Summary",
            "Revenue": historical_df["Revenue"].sum(),
            "Land Payment": historical_df["Land Payment"].sum(),
            "Construction": historical_df["Construction"].sum(),
            "SG&A": historical_df["SG&A"].sum(),
            "EBITDA": historical_df["EBITDA"].sum(),
            "Interest Expense": historical_df["Interest Expense"].sum(),
            "Profit Before Tax": historical_df["Profit Before Tax"].sum(),
            "Tax Expense (20%)": historical_df["Tax Expense (20%)"].sum(),
            "Profit After Tax": historical_df["Profit After Tax"].sum()
        }
        df = pd.concat([df, pd.DataFrame([historical_total])], ignore_index=True)
    
    if not future_df.empty:
        future_total = {
            "Year": "Total (Future)",
            "Type": "Summary",
            "Revenue": future_df["Revenue"].sum(),
            "Land Payment": future_df["Land Payment"].sum(),
            "Construction": future_df["Construction"].sum(),
            "SG&A": future_df["SG&A"].sum(),
            "EBITDA": future_df["EBITDA"].sum(),
            "Interest Expense": future_df["Interest Expense"].sum(),
            "Profit Before Tax": future_df["Profit Before Tax"].sum(),
            "Tax Expense (20%)": future_df["Tax Expense (20%)"].sum(),
            "Profit After Tax": future_df["Profit After Tax"].sum()
        }
        df = pd.concat([df, pd.DataFrame([future_total])], ignore_index=True)
    
    # Add overall total
    overall_total = {
        "Year": "Total (Overall)",
        "Type": "Summary",
        "Revenue": df[df["Type"] != "Summary"]["Revenue"].sum(),
        "Land Payment": df[df["Type"] != "Summary"]["Land Payment"].sum(),
        "Construction": df[df["Type"] != "Summary"]["Construction"].sum(),
        "SG&A": df[df["Type"] != "Summary"]["SG&A"].sum(),
        "EBITDA": df[df["Type"] != "Summary"]["EBITDA"].sum(),
        "Interest Expense": df[df["Type"] != "Summary"]["Interest Expense"].sum(),
        "Profit Before Tax": df[df["Type"] != "Summary"]["Profit Before Tax"].sum(),
        "Tax Expense (20%)": df[df["Type"] != "Summary"]["Tax Expense (20%)"].sum(),
        "Profit After Tax": df[df["Type"] != "Summary"]["Profit After Tax"].sum()
    }
    df = pd.concat([df, pd.DataFrame([overall_total])], ignore_index=True)

    return df

def RNAV_Calculation(
    selling_progress_schedule: list,
    construction_payment_schedule: list,
    sga_payment_schedule: list,
    tax_expense_schedule: list,
    land_use_right_payment_schedule: list,
    wacc: float,
    project_start_year: int,
    current_year: int
) -> pd.DataFrame:
    """
    Calculate RNAV using discounted cash flow method.
    Only includes future cash flows (current year and beyond) for RNAV calculation.
    """
    n = len(selling_progress_schedule)
    # Validate all input lists are of equal length
    all_schedules = [
        construction_payment_schedule,
        sga_payment_schedule,
        tax_expense_schedule,
        land_use_right_payment_schedule
    ]
    if not all(len(lst) == n for lst in all_schedules):
        raise ValueError("All input lists must be of equal length.")

    data = []
    total_rnav = 0.0
    wacc_adjust = current_year - project_start_year  # Adjusted to use project_start_year
    for i in range(n):
        year = project_start_year + i
        wacc_index = i - wacc_adjust  # Adjusted to use project_start_year
        inflow = selling_progress_schedule[i]
        
        # Break down outflow components
        construction_cost = construction_payment_schedule[i]
        sga_cost = sga_payment_schedule[i]
        tax_cost = tax_expense_schedule[i]
        land_cost = land_use_right_payment_schedule[i]
        
        total_outflow = construction_cost + sga_cost + tax_cost + land_cost
        net_cashflow = inflow + total_outflow
        
        # calculate discounted cash flow, if year < current_year, it will not be included in RNAV
        discount_factor = 1 / ((1 + wacc) ** wacc_index) if year >= current_year else 0
        discounted_cashflow = net_cashflow * discount_factor
        
        total_rnav += discounted_cashflow

        data.append({
            "Year": year,
            "Inflow (Revenue)": inflow,
            "Construction Cost": construction_cost,
            "Land Cost": land_cost,
            "SG&A": sga_cost,
            "Tax": tax_cost,
            "Total Outflow": total_outflow,
            "Net Cash Flow": net_cashflow,
            "Discount Factor": discount_factor,
            "Discounted Cash Flow": discounted_cashflow,
        })

    df = pd.DataFrame(data)
    
    # Add total row
    total_row = {
        "Year": "Total RNAV",
        "Inflow (Revenue)": df["Inflow (Revenue)"].sum(),
        "Construction Cost": df["Construction Cost"].sum(),
        "Land Cost": df["Land Cost"].sum(),
        "SG&A": df["SG&A"].sum(),
        "Tax": df["Tax"].sum(),
        "Total Outflow": df["Total Outflow"].sum(),
        "Net Cash Flow": df["Net Cash Flow"].sum(),
        "Discount Factor": np.nan,
        "Discounted Cash Flow": total_rnav,
    }
    
    df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    
    return df