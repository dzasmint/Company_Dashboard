#%%
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def generate_balance_sheet_schedules(
    total_debt: float,
    total_construction_cost: float,
    total_land_cost: float,  # New parameter
    land_payment_year: int = None,  # Deprecated - kept for backwards compatibility
    presales_schedule: Dict[int, float] = None,  # {year: presale_amount}
    interest_rate: float = 0.0,
    sga_percentage: float = 0.0,  # SG&A as percentage of revenue (e.g., 0.05 for 5%)
    debt_disbursement_start_year: int = None,
    debt_disbursement_end_year: int = None,
    debt_repayment_start_year: int = None,
    debt_repayment_end_year: int = None,
    revenue_booking_start_year: int = None,
    revenue_booking_end_year: int = None,
    revenue_distribution: Optional[Dict[int, float]] = None,  # {year: percentage} for revenue recognition
    project_start_year: int = None,
    project_end_year: int = None,
    tax_rate: float = 0.2,  # Default 20% tax rate
    cash_collection_schedules: Optional[Dict[int, Dict[int, float]]] = None,  # {presale_year: {collection_year: percentage}}
    land_payment_start_year: int = None,  # New parameter for multi-year payment
    land_payment_years: int = 1  # New parameter for payment duration
) -> pd.DataFrame:
    """
    Generate comprehensive balance sheet schedules including debt, interest, inventory, and cash.
    
    Args:
        total_debt: Total debt amount to be disbursed
        total_construction_cost: Total construction cost
        total_land_cost: Total land cost to be paid
        land_payment_year: (Deprecated) Year when land cost is paid in single payment
        land_payment_start_year: Start year for land payment (for multi-year payment)
        land_payment_years: Number of years over which land payment is distributed
        presales_schedule: Dictionary of presales by year {year: amount}
        interest_rate: Annual interest rate (as decimal, e.g., 0.08 for 8%)
        sga_percentage: SG&A as percentage of revenue (as decimal, e.g., 0.05 for 5%)
        debt_disbursement_start_year: Year debt disbursement begins
        debt_disbursement_end_year: Year debt disbursement ends
        debt_repayment_start_year: Year debt repayment begins
        debt_repayment_end_year: Year debt repayment ends
        revenue_booking_start_year: Year revenue recognition begins
        revenue_booking_end_year: Year revenue recognition ends
        revenue_distribution: Optional dict of {year: percentage} for custom revenue recognition
        project_start_year: Optional, defaults to earliest year in inputs
        project_end_year: Optional, defaults to latest year in inputs
    
    Returns:
        DataFrame with columns:
        - Year
        - Debt_Disbursement: Annual debt disbursement amount
        - Debt_Repayment: Annual debt repayment amount
        - Debt_Balance: Outstanding debt balance at year end
        - Interest_Expense_Cash: Interest recognized as expense in P&L (during revenue period)
        - Interest_Capitalized: Interest added to inventory (during construction)
        - Construction_Cost: Annual construction cost
        - Inventory_Addition: Construction cost + capitalized interest
        - Inventory_Balance: Cumulative inventory balance
        - Revenue_Recognition: Revenue recognized in the year
        - COGS: Cost of goods sold (inventory released upon revenue recognition)
        - Cash_Inflow_Presales: Cash received from presales
        - Cash_Inflow_Revenue: Cash received from revenue (if different from presales)
        - Cash_Outflow_Construction: Cash paid for construction
        - Cash_Outflow_Interest: Cash paid for interest
        - Cash_Balance_Change: Net cash flow for the year
    """
    
    # Handle backwards compatibility for land payment
    if land_payment_start_year is None and land_payment_year is not None:
        # Use old single-year parameter
        land_payment_start_year = land_payment_year
        land_payment_years = 1
    elif land_payment_start_year is None:
        # Default to project start if not specified
        land_payment_start_year = project_start_year or debt_disbursement_start_year
        land_payment_years = 1
    
    # Determine project timeline
    if project_start_year is None:
        # Include all relevant start years in the timeline calculation
        start_years = []
        
        # Add all years that have activities
        start_years.append(debt_disbursement_start_year)
        start_years.append(land_payment_start_year)
        start_years.append(revenue_booking_start_year)
        start_years.append(debt_repayment_start_year)
        
        if presales_schedule:
            start_years.append(min(presales_schedule.keys()))
        
        # Filter out None values and get minimum
        start_years = [y for y in start_years if y is not None]
        project_start_year = min(start_years) if start_years else debt_disbursement_start_year
    
    if project_end_year is None:
        # Include all relevant end years
        end_years = []
        
        end_years.append(debt_disbursement_end_year)
        end_years.append(debt_repayment_end_year)
        end_years.append(revenue_booking_end_year)
        
        if presales_schedule:
            end_years.append(max(presales_schedule.keys()))
        
        # Filter out None values and get maximum
        end_years = [y for y in end_years if y is not None]
        project_end_year = max(end_years) if end_years else revenue_booking_end_year
    
    # Initialize arrays for each schedule
    years = list(range(project_start_year, project_end_year + 1))
    n_years = len(years)
    
    # Initialize all schedules
    debt_disbursement = np.zeros(n_years)
    debt_repayment = np.zeros(n_years)
    debt_balance = np.zeros(n_years)
    interest_expense_cash = np.zeros(n_years)
    interest_capitalized = np.zeros(n_years)
    construction_cost = np.zeros(n_years)
    land_cost = np.zeros(n_years)  # New array for land cost
    inventory_addition = np.zeros(n_years)
    inventory_balance = np.zeros(n_years)
    presales = np.zeros(n_years)  # Presales in each year
    customer_prepayment_balance = np.zeros(n_years)  # Customer prepayment balance
    revenue_recognition = np.zeros(n_years)
    cogs = np.zeros(n_years)
    cash_inflow_presales = np.zeros(n_years)
    cash_outflow_construction = np.zeros(n_years)
    cash_outflow_land = np.zeros(n_years)  # New array for land cash outflow
    cash_outflow_interest = np.zeros(n_years)
    sga_expense = np.zeros(n_years)  # SG&A expense for P&L
    cash_outflow_sga = np.zeros(n_years)  # SG&A cash outflow
    
    # 1. Calculate debt disbursement schedule (linear during disbursement period)
    disbursement_years = debt_disbursement_end_year - debt_disbursement_start_year + 1
    if disbursement_years > 0:
        annual_disbursement = total_debt / disbursement_years
        for year in range(debt_disbursement_start_year, debt_disbursement_end_year + 1):
            if year in years:
                idx = years.index(year)
                debt_disbursement[idx] = annual_disbursement
    
    # 2. Calculate construction cost schedule (linear during construction period)
    # Assuming construction period aligns with debt disbursement period
    construction_years = debt_disbursement_end_year - debt_disbursement_start_year + 1
    if construction_years > 0:
        annual_construction = total_construction_cost / construction_years
        for year in range(debt_disbursement_start_year, debt_disbursement_end_year + 1):
            if year in years:
                idx = years.index(year)
                construction_cost[idx] = annual_construction
                cash_outflow_construction[idx] = -annual_construction  # Negative for outflow
    
    # 3. Calculate debt repayment schedule (linear during repayment period)
    repayment_years = debt_repayment_end_year - debt_repayment_start_year + 1
    if repayment_years > 0:
        annual_repayment = total_debt / repayment_years
        for year in range(debt_repayment_start_year, debt_repayment_end_year + 1):
            if year in years:
                idx = years.index(year)
                debt_repayment[idx] = -annual_repayment  # Negative for outflow
    
    # 4. Calculate presales and convert to cash inflow schedule with tranche logic
    # First record the presales bookings (contractual commitments)
    # Note: presales[i] = booking amount (when sale is made)
    #       cash_inflow_presales[i] = actual cash collection (follows tranche payment schedule)
    for year, amount in presales_schedule.items():
        if year in years:
            idx = years.index(year)
            presales[idx] = amount  # Record presales booking (contractual amount)
    
    # Calculate actual cash collection from presales using flexible schedules
    if cash_collection_schedules:
        # Use user-defined collection schedules
        for presale_year, presale_amount in presales_schedule.items():
            if presale_year in years and presale_amount > 0:
                # Get the collection schedule for this presale year
                collection_schedule = cash_collection_schedules.get(presale_year, {})
                
                if collection_schedule:
                    # Apply the user-defined percentages
                    for collection_year, percentage in collection_schedule.items():
                        if collection_year in years:
                            col_idx = years.index(collection_year)
                            collection_amount = presale_amount * (percentage / 100.0)
                            cash_inflow_presales[col_idx] += collection_amount
                else:
                    # Fallback: collect 100% in presale year if no schedule defined
                    presale_year_idx = years.index(presale_year)
                    cash_inflow_presales[presale_year_idx] += presale_amount
    else:
        # Fallback to default 30/70 logic if no schedules provided
        construction_end_year = debt_disbursement_end_year
        
        for year, presale_amount in presales_schedule.items():
            if year in years and presale_amount > 0:
                presale_year_idx = years.index(year)
                
                # Default: 30% in first year, 70% spread to construction end
                if year >= construction_end_year:
                    # Collect all 100% immediately
                    cash_inflow_presales[presale_year_idx] += presale_amount
                else:
                    # 30% in first year
                    first_tranche = presale_amount * 0.3
                    cash_inflow_presales[presale_year_idx] += first_tranche
                    
                    # Remaining 70% distributed evenly
                    remaining_amount = presale_amount * 0.7
                    collection_years = list(range(year + 1, construction_end_year + 1))
                    
                    if collection_years:
                        annual_collection = remaining_amount / len(collection_years)
                        for col_year in collection_years:
                            if col_year in years:
                                col_idx = years.index(col_year)
                                cash_inflow_presales[col_idx] += annual_collection
                    else:
                        # Add remaining to presale year
                        cash_inflow_presales[presale_year_idx] += remaining_amount
    
    # 5. Calculate SG&A expense based on actual cash collection
    # SG&A is now calculated as a percentage of actual cash collected, not presales booking
    for i, year in enumerate(years):
        if cash_inflow_presales[i] > 0:
            # SG&A expense is based on cash collected in this year
            sga_amount = cash_inflow_presales[i] * sga_percentage
            sga_expense[i] = sga_amount  # Hit P&L when cash is collected
            cash_outflow_sga[i] = -sga_amount  # Negative for cash outflow
    
    # 6. Calculate land cost payment (multi-year payment)
    if total_land_cost > 0 and land_payment_start_year is not None:
        land_payment_end_year = land_payment_start_year + land_payment_years - 1
        annual_land_payment = total_land_cost / land_payment_years
        
        for payment_year in range(land_payment_start_year, land_payment_end_year + 1):
            if payment_year in years:
                idx = years.index(payment_year)
                land_cost[idx] = annual_land_payment
                cash_outflow_land[idx] = -annual_land_payment  # Negative for cash outflow
    
    # 7. Calculate revenue recognition (custom distribution or linear)
    total_revenue = sum(presales_schedule.values()) if presales_schedule else 0
    
    if revenue_distribution and isinstance(revenue_distribution, dict):
        # Use custom revenue distribution
        for year in range(revenue_booking_start_year, revenue_booking_end_year + 1):
            if year in years:
                idx = years.index(year)
                # Get percentage for this year (as decimal)
                year_pct = revenue_distribution.get(year, 0.0)
                revenue_recognition[idx] = total_revenue * year_pct
    else:
        # Default: linear distribution during booking period
        booking_years = revenue_booking_end_year - revenue_booking_start_year + 1
        if booking_years > 0 and total_revenue > 0:
            annual_revenue = total_revenue / booking_years
            for year in range(revenue_booking_start_year, revenue_booking_end_year + 1):
                if year in years:
                    idx = years.index(year)
                    revenue_recognition[idx] = annual_revenue
    
    # 8. Calculate debt balance, interest, and inventory year by year
    for i, year in enumerate(years):
        # Starting debt balance
        if i == 0:
            starting_balance = 0
        else:
            starting_balance = debt_balance[i-1]
        
        # Update debt balance (debt_repayment is already negative)
        debt_balance[i] = starting_balance + debt_disbursement[i] + debt_repayment[i]
        
        # Calculate interest on average balance during the year
        average_balance = (starting_balance + debt_balance[i]) / 2
        total_interest = average_balance * interest_rate
        
        # Determine if we're in construction or revenue period
        is_construction_period = year < revenue_booking_start_year
        is_revenue_period = revenue_booking_start_year <= year <= revenue_booking_end_year
        
        if is_construction_period and total_interest > 0:
            # During construction: capitalize interest to inventory
            # BUT still pay interest in cash
            interest_capitalized[i] = total_interest
            interest_expense_cash[i] = 0  # Not expensed in P&L
            cash_outflow_interest[i] = -total_interest  # Negative for cash outflow
        elif is_revenue_period and average_balance > 0:
            # During revenue period with debt: expense interest
            # Use average_balance instead of ending balance to catch final year
            interest_expense_cash[i] = total_interest
            interest_capitalized[i] = 0
            cash_outflow_interest[i] = -total_interest  # Negative for cash outflow
        elif average_balance > 0:
            # If there's debt outside construction/revenue periods, still need to pay interest
            interest_expense_cash[i] = total_interest  # Expense it
            interest_capitalized[i] = 0
            cash_outflow_interest[i] = -total_interest  # Negative for cash outflow
        else:
            # No interest if no debt
            interest_expense_cash[i] = 0
            interest_capitalized[i] = 0
            cash_outflow_interest[i] = 0
        
        # Update inventory (include land, construction, and capitalized interest)
        inventory_addition[i] = construction_cost[i] + land_cost[i] + interest_capitalized[i]
        
        # Calculate inventory balance
        if i == 0:
            previous_inventory = 0
        else:
            previous_inventory = inventory_balance[i-1]
        
        # During revenue recognition, release inventory to COGS
        if is_revenue_period and total_revenue > 0:
            # Calculate COGS proportional to revenue recognition
            revenue_percentage = revenue_recognition[i] / total_revenue if total_revenue > 0 else 0
            
            # Total inventory to be released = total construction cost + total capitalized interest
            total_inventory_accumulated = sum(inventory_addition[:i+1]) + previous_inventory
            
            # COGS released proportionally
            if i == years.index(revenue_booking_end_year):
                # Last year: release all remaining inventory
                cogs[i] = previous_inventory + inventory_addition[i]
                inventory_balance[i] = 0
            else:
                # Release inventory proportional to revenue
                total_expected_inventory = total_construction_cost + total_land_cost + sum(interest_capitalized)
                cogs[i] = total_expected_inventory * revenue_percentage
                inventory_balance[i] = previous_inventory + inventory_addition[i] - cogs[i]
        else:
            # Not in revenue period: accumulate inventory
            inventory_balance[i] = previous_inventory + inventory_addition[i]
            cogs[i] = 0
    
    # 9. Calculate customer prepayment balance
    # Customer prepayment increases with actual cash collection (not presales booking) and decreases with revenue recognition
    for i in range(n_years):
        if i == 0:
            previous_prepayment = 0
        else:
            previous_prepayment = customer_prepayment_balance[i-1]
        
        # Add actual cash collected (from tranche logic), subtract revenue recognized
        # This reflects the actual cash received from customers
        customer_prepayment_balance[i] = previous_prepayment + cash_inflow_presales[i] - revenue_recognition[i]
    
    # 10. Calculate P&L items (PBT, Tax, PAT)
    pbt = np.zeros(n_years)  # Profit before tax
    tax_expense = np.zeros(n_years)  # Tax expense
    pat = np.zeros(n_years)  # Profit after tax
    cash_outflow_tax = np.zeros(n_years)  # Tax cash outflow
    
    for i in range(n_years):
        # PBT = Revenue - COGS - SG&A - Interest Expense
        pbt[i] = revenue_recognition[i] - cogs[i] - sga_expense[i] - interest_expense_cash[i]
        
        # Tax = PBT * Tax Rate (only if PBT is positive)
        if pbt[i] > 0:
            tax_expense[i] = pbt[i] * tax_rate
            # Tax is paid in cash in the same year (simplified assumption)
            cash_outflow_tax[i] = -tax_expense[i]
        else:
            tax_expense[i] = 0
            cash_outflow_tax[i] = 0
        
        # PAT = PBT - Tax
        pat[i] = pbt[i] - tax_expense[i]
    
    # 11. Calculate net cash flow (outflows are already negative)
    cash_balance_change = (
        cash_inflow_presales 
        + debt_disbursement  # Cash inflow from debt
        + cash_outflow_construction  # Already negative
        + cash_outflow_land  # Already negative
        + cash_outflow_interest  # Already negative
        + cash_outflow_sga  # Already negative
        + cash_outflow_tax  # Already negative
        + debt_repayment  # Already negative
    )
    
    # Calculate cumulative cash balance
    cumulative_cash_balance = np.cumsum(cash_balance_change)
    
    # Create DataFrame with results in the requested order
    df = pd.DataFrame({
        'Year': years,
        # Debt section
        'Debt_Balance': debt_balance,
        # Cost section
        'Land_Cost': land_cost,
        'Construction_Cost': construction_cost,
        'Interest_Capitalized': interest_capitalized,
        # Inventory section
        'Inventory_Addition': inventory_addition,
        'Inventory_Balance': inventory_balance,
        # Presales and Revenue section
        'Presales': presales,
        'Customer_Prepayment_Balance': customer_prepayment_balance,
        'Revenue_Recognition': revenue_recognition,
        # P&L section
        'COGS': cogs,
        'SGA_Expense': sga_expense,
        'Interest_Expense_Cash': interest_expense_cash,
        'PBT': pbt,
        'Tax': tax_expense,
        'PAT': pat,
        # Cash flow section
        'Cash_Inflow_Presales': cash_inflow_presales,
        'Debt_Disbursement': debt_disbursement,
        'Debt_Repayment': debt_repayment,
        'Cash_Outflow_Land': cash_outflow_land,
        'Cash_Outflow_Construction': cash_outflow_construction,
        'Cash_Outflow_Interest': cash_outflow_interest,
        'Cash_Outflow_SGA': cash_outflow_sga,
        'Cash_Outflow_Tax': cash_outflow_tax,
        'Cash_Balance_Change': cash_balance_change,
        'Cumulative_Cash_Balance': cumulative_cash_balance
    })
    
    # Add summary row
    summary = pd.DataFrame({
        'Year': ['Total'],
        # Debt section
        'Debt_Balance': [debt_balance[-1]],  # Final balance
        # Cost section
        'Land_Cost': [land_cost.sum()],
        'Construction_Cost': [construction_cost.sum()],
        'Interest_Capitalized': [interest_capitalized.sum()],
        # Inventory section
        'Inventory_Addition': [inventory_addition.sum()],
        'Inventory_Balance': [inventory_balance[-1]],  # Final balance
        # Presales and Revenue section
        'Presales': [presales.sum()],
        'Customer_Prepayment_Balance': [customer_prepayment_balance[-1]],  # Final balance
        'Revenue_Recognition': [revenue_recognition.sum()],
        # P&L section
        'COGS': [cogs.sum()],
        'SGA_Expense': [sga_expense.sum()],
        'Interest_Expense_Cash': [interest_expense_cash.sum()],
        'PBT': [pbt.sum()],
        'Tax': [tax_expense.sum()],
        'PAT': [pat.sum()],
        # Cash flow section
        'Cash_Inflow_Presales': [cash_inflow_presales.sum()],
        'Debt_Disbursement': [debt_disbursement.sum()],
        'Debt_Repayment': [debt_repayment.sum()],  # Already negative
        'Cash_Outflow_Land': [cash_outflow_land.sum()],
        'Cash_Outflow_Construction': [cash_outflow_construction.sum()],
        'Cash_Outflow_Interest': [cash_outflow_interest.sum()],
        'Cash_Outflow_SGA': [cash_outflow_sga.sum()],
        'Cash_Outflow_Tax': [cash_outflow_tax.sum()],
        'Cash_Balance_Change': [cash_balance_change.sum()],
        'Cumulative_Cash_Balance': [cumulative_cash_balance[-1]]  # Final cash balance
    })
    
    df = pd.concat([df, summary], ignore_index=True)
    
    return df


def generate_simplified_balance_sheet_schedules(
    total_debt: float,
    total_construction_cost: float,
    total_land_cost: float,
    land_payment_year: int = None,  # Deprecated - kept for backwards compatibility
    total_revenue: float = 0.0,
    interest_rate: float = 0.0,
    sga_percentage: float = 0.0,  # SG&A as percentage of revenue
    construction_start_year: int = None,
    construction_end_year: int = None,
    sales_start_year: int = None,
    sales_end_year: int = None,
    debt_repayment_start_year: int = None,
    debt_repayment_end_year: int = None,
    revenue_booking_start_year: int = None,
    revenue_booking_end_year: int = None,
    presales_distribution: Optional[Dict[str, float]] = None,  # {year_str: percentage}
    revenue_distribution: Optional[Dict[str, float]] = None,  # {year_str: percentage} for revenue recognition
    tax_rate: float = 0.2,  # Default 20% tax rate
    price_increment_factor: float = 0.0,  # Annual price increment as decimal (e.g., 0.05 for 5%)
    base_asp: float = None,  # Base average selling price
    total_nsa: float = None,  # Total net sellable area
    land_payment_start_year: int = None,  # New parameter for multi-year payment
    land_payment_years: int = 1  # New parameter for payment duration
) -> pd.DataFrame:
    """
    Simplified version that integrates with project pipeline calculations.
    
    Args:
        total_debt: Total debt amount
        total_construction_cost: Total construction cost
        total_land_cost: Total land cost
        land_payment_year: (Deprecated) Year when land is paid in single payment
        land_payment_start_year: Start year for land payment (for multi-year payment)
        land_payment_years: Number of years over which land payment is distributed
        total_revenue: Total revenue from project
        interest_rate: Annual interest rate (as decimal)
        sga_percentage: SG&A as percentage of revenue (as decimal)
        construction_start_year: Year construction begins
        construction_end_year: Year construction ends
        sales_start_year: Year sales/presales begin
        sales_end_year: Year sales/presales end
        debt_repayment_start_year: Year debt repayment begins
        debt_repayment_end_year: Year debt repayment ends
        revenue_booking_start_year: Year revenue recognition begins
        revenue_booking_end_year: Year revenue recognition ends
        presales_distribution: Optional custom distribution {year_str: percentage} for presales
        revenue_distribution: Optional custom distribution {year_str: percentage} for revenue recognition
    
    Returns:
        DataFrame with balance sheet schedules
    """
    
    # Generate presales schedule based on distribution with price increment
    presales_schedule = {}
    
    # If price increment is provided and we have base ASP and NSA, calculate adjusted presales
    if price_increment_factor > 0 and base_asp is not None and total_nsa is not None:
        # Calculate presales with price increment for each year
        sales_years_list = list(range(sales_start_year, sales_end_year + 1))
        
        if presales_distribution:
            for i, year in enumerate(sales_years_list):
                year_pct = presales_distribution.get(str(year), 0.0) / 100.0
                year_nsa = total_nsa * year_pct
                # Apply price increment: first year = base, subsequent years apply increment
                year_asp = base_asp * (1 + price_increment_factor) ** i
                presales_schedule[year] = year_nsa * year_asp
        else:
            # No fallback - require presales distribution
            pass  # presales_schedule remains empty
    else:
        # Fallback to original logic if no price increment
        if presales_distribution:
            for year in range(sales_start_year, sales_end_year + 1):
                year_pct = presales_distribution.get(str(year), 0.0) / 100.0
                presales_schedule[year] = total_revenue * year_pct
        else:
            # No fallback - require presales distribution
            pass  # presales_schedule remains empty
    
    # Convert revenue distribution from percentage strings to year integers with decimal values
    revenue_dist_converted = None
    if revenue_distribution:
        revenue_dist_converted = {}
        for year_str, percentage in revenue_distribution.items():
            year = int(year_str)
            # Convert percentage to decimal (e.g., 50% -> 0.5)
            revenue_dist_converted[year] = percentage / 100.0
    
    # Use construction period for debt disbursement
    return generate_balance_sheet_schedules(
        total_debt=total_debt,
        total_construction_cost=total_construction_cost,
        total_land_cost=total_land_cost,
        land_payment_year=land_payment_year,  # Keep for backwards compatibility
        land_payment_start_year=land_payment_start_year,
        land_payment_years=land_payment_years,
        presales_schedule=presales_schedule,
        interest_rate=interest_rate,
        sga_percentage=sga_percentage,
        debt_disbursement_start_year=construction_start_year,
        debt_disbursement_end_year=construction_end_year,
        debt_repayment_start_year=debt_repayment_start_year,
        debt_repayment_end_year=debt_repayment_end_year,
        revenue_booking_start_year=revenue_booking_start_year,
        revenue_booking_end_year=revenue_booking_end_year,
        revenue_distribution=revenue_dist_converted,
        tax_rate=tax_rate
    )


# Example usage
if __name__ == "__main__":
    # Example parameters
    result = generate_simplified_balance_sheet_schedules(
        total_debt=1000000000,  # 1B VND
        total_construction_cost=800000000,  # 800M VND
        total_land_cost=300000000,  # 300M VND
        land_payment_year=2024,  # Pay land in first year
        total_revenue=1500000000,  # 1.5B VND
        interest_rate=0.08,  # 8% per year
        sga_percentage=0.05,  # 5% SG&A
        construction_start_year=2024,
        construction_end_year=2026,
        sales_start_year=2025,
        sales_end_year=2027,
        debt_repayment_start_year=2027,
        debt_repayment_end_year=2028,
        revenue_booking_start_year=2027,
        revenue_booking_end_year=2028,
        presales_distribution={'2025': 30, '2026': 50, '2027': 20}  # Custom distribution
    )
    
    print("\nBalance Sheet Schedules:")
    print(result.to_string(index=False))
    
    # Display with formatting for better readability
    pd.options.display.float_format = '{:,.0f}'.format
    print("\n\nFormatted Balance Sheet Schedules:")
    print(result.to_string(index=False))