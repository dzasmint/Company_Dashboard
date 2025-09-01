"""
Utility functions for generating project breakdown tables in model forecast
Extracted from tabs/model_forecast.py for better organization
"""

import pandas as pd
import streamlit as st


def create_revenue_breakdown_table(
    project_revenue_breakdown,
    project_revenue_by_year,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Create revenue breakdown table with projects and other revenue streams
    
    Args:
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_revenue_by_year: Dictionary of total project revenue by year
        hist_col: Historical column name (e.g., '2024H')
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics (growth rates, margins, etc.)
        hist_values: Dictionary of historical values
        
    Returns:
        pd.DataFrame: Revenue breakdown dataframe
    """
    revenue_rows = []
    
    # Add individual project revenues
    for project_name in project_revenue_breakdown.keys():
        row_data = {'Revenue Source': f"{project_name}"}
        row_data[hist_col] = 0  # No historical breakdown by project
        for year in years:
            row_data[str(year)] = project_revenue_breakdown[project_name].get(year, 0)
        revenue_rows.append(row_data)
    
    # Add separator row for projects total
    if revenue_rows:
        total_projects_row = {'Revenue Source': 'Subtotal: Projects'}
        total_projects_row[hist_col] = 0  # No historical breakdown
        for year in years:
            total_projects_row[str(year)] = project_revenue_by_year[year]
        revenue_rows.append(total_projects_row)
    
    # Add other revenue streams
    for segment_name in st.session_state.base_year_revenues.keys():
        row_data = {'Revenue Source': f"{segment_name}"}
        # Base year revenue goes in the historical column
        row_data[hist_col] = st.session_state.base_year_revenues[segment_name]
        base_revenue = st.session_state.base_year_revenues[segment_name]
        
        # Get growth rate from segment_metrics
        if segment_name in segment_metrics:
            growth_rate = segment_metrics[segment_name]['revenue_growth']
        else:
            growth_rate = 0.0  # Default 0%
        
        # Apply growth for forecast years
        for year in years:
            # Base year is the latest historical year, apply growth from there
            years_from_base = year - base_year
            row_data[str(year)] = base_revenue * ((1 + growth_rate) ** years_from_base)
        revenue_rows.append(row_data)
    
    # Add total row
    total_row = {'Revenue Source': 'TOTAL REVENUE'}
    total_row[hist_col] = hist_values.get('Net Revenue', 0)  # Historical Net Revenue
    for year in years:
        total_revenue = project_revenue_by_year[year]
        for segment_name in st.session_state.base_year_revenues.keys():
            base_revenue = st.session_state.base_year_revenues[segment_name]
            if segment_name in segment_metrics:
                growth_rate = segment_metrics[segment_name]['revenue_growth']
            else:
                growth_rate = 0.0
            
            # Base year is the latest historical year, apply growth from there
            years_from_base = year - base_year
            total_revenue += base_revenue * ((1 + growth_rate) ** years_from_base)
        total_row[str(year)] = total_revenue
    revenue_rows.append(total_row)
    
    # Create DataFrame
    return pd.DataFrame(revenue_rows)


def display_revenue_breakdown_table(revenue_df, hist_col, years):
    """
    Display the revenue breakdown table with proper formatting and styling
    
    Args:
        revenue_df: Revenue breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    # Style the dataframe - highlight subtotal and total rows
    def highlight_special_rows(row):
        if 'TOTAL' in str(row['Revenue Source']) or 'Subtotal' in str(row['Revenue Source']):
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.write("**Revenue by Source (Billion VND)**")
    
    # Define column configuration for consistent width
    column_config = {
        'Revenue Source': st.column_config.TextColumn('Revenue Source', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        column_config[col] = st.column_config.NumberColumn(col, width='small')
    
    st.dataframe(
        revenue_df.style
        .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
        .apply(highlight_special_rows, axis=1),
        use_container_width=True,
        column_config=column_config,
        hide_index=True
    )


def render_revenue_forecast_tab(
    project_revenue_breakdown,
    project_revenue_by_year,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Render the complete revenue forecast tab
    
    Args:
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_revenue_by_year: Dictionary of total project revenue by year
        hist_col: Historical column name
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics
        hist_values: Dictionary of historical values
        
    Returns:
        pd.DataFrame: Revenue breakdown dataframe
    """
    st.subheader("Revenue Forecast")
    
    # Create revenue breakdown table
    revenue_df = create_revenue_breakdown_table(
        project_revenue_breakdown,
        project_revenue_by_year,
        hist_col,
        years,
        base_year,
        segment_metrics,
        hist_values
    )
    
    # Display the table
    display_revenue_breakdown_table(revenue_df, hist_col, years)
    
    return revenue_df


def create_cogs_breakdown_table(
    project_cogs_breakdown,
    project_cogs_by_year,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Create COGS breakdown table with projects and other cost streams
    
    Args:
        project_cogs_breakdown: Dictionary of project COGS by project and year
        project_cogs_by_year: Dictionary of total project COGS by year
        hist_col: Historical column name (e.g., '2024H')
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics (growth rates, margins, etc.)
        hist_values: Dictionary of historical values
        
    Returns:
        pd.DataFrame: COGS breakdown dataframe
    """
    cogs_rows = []
    
    # Add individual project COGS
    for project_name in project_cogs_breakdown.keys():
        row_data = {'COGS Source': f"{project_name}"}
        row_data[hist_col] = 0  # No historical breakdown by project
        for year in years:
            row_data[str(year)] = project_cogs_breakdown[project_name].get(year, 0)
        cogs_rows.append(row_data)
    
    # Add separator row for projects total
    if cogs_rows:
        total_projects_row = {'COGS Source': 'Subtotal: Project COGS'}
        total_projects_row[hist_col] = 0  # No historical breakdown
        for year in years:
            total_projects_row[str(year)] = project_cogs_by_year[year]
        cogs_rows.append(total_projects_row)
    
    # Add COGS for other revenue streams
    for segment_name in st.session_state.base_year_revenues.keys():
        row_data = {'COGS Source': f"{segment_name} COGS"}
        base_revenue = st.session_state.base_year_revenues[segment_name]
        
        # Get metrics from segment_metrics
        if segment_name in segment_metrics:
            growth_rate = segment_metrics[segment_name]['revenue_growth']
            gross_margin = segment_metrics[segment_name]['gross_margin']
        else:
            growth_rate = 0.0  # Default 0%
            gross_margin = 0.0  # Default 0%
        
        # Base year COGS in historical column (negative)
        row_data[hist_col] = -base_revenue * (1 - gross_margin)
        
        # Calculate COGS for forecast years (negative)
        for year in years:
            # Base year is the latest historical year, apply growth from there
            years_from_base = year - base_year
            year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
            
            row_data[str(year)] = -year_revenue * (1 - gross_margin)
        cogs_rows.append(row_data)
    
    # Add total row
    total_row = {'COGS Source': 'TOTAL COGS'}
    total_row[hist_col] = -abs(hist_values.get('COGS', 0))  # Historical COGS as negative
    for year in years:
        total_cogs = project_cogs_by_year[year]  # Already negative from projects
        for segment_name in st.session_state.base_year_revenues.keys():
            base_revenue = st.session_state.base_year_revenues[segment_name]
            
            if segment_name in segment_metrics:
                growth_rate = segment_metrics[segment_name]['revenue_growth']
                gross_margin = segment_metrics[segment_name]['gross_margin']
            else:
                growth_rate = 0.0
                gross_margin = 0.0
            
            # Base year is the latest historical year, apply growth from there
            years_from_base = year - base_year
            year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
            
            # Add negative COGS for other segments
            total_cogs -= year_revenue * (1 - gross_margin)
        total_row[str(year)] = total_cogs
    cogs_rows.append(total_row)
    
    # Create DataFrame
    return pd.DataFrame(cogs_rows)


def display_cogs_breakdown_table(cogs_df, hist_col, years):
    """
    Display the COGS breakdown table with proper formatting and styling
    
    Args:
        cogs_df: COGS breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    # Style the dataframe - highlight subtotal and total rows
    def highlight_special_rows_cogs(row):
        if 'TOTAL' in str(row['COGS Source']) or 'Subtotal' in str(row['COGS Source']):
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.write("**COGS by Source (Billion VND)**")
    
    # Define column configuration for consistent width
    cogs_column_config = {
        'COGS Source': st.column_config.TextColumn('COGS Source', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        cogs_column_config[col] = st.column_config.NumberColumn(col, width='small')
    
    st.dataframe(
        cogs_df.style
        .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
        .apply(highlight_special_rows_cogs, axis=1),
        use_container_width=True,
        column_config=cogs_column_config,
        hide_index=True
    )


def render_cogs_forecast_tab(
    project_cogs_breakdown,
    project_cogs_by_year,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Render the complete COGS forecast tab
    
    Args:
        project_cogs_breakdown: Dictionary of project COGS by project and year
        project_cogs_by_year: Dictionary of total project COGS by year
        hist_col: Historical column name
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics
        hist_values: Dictionary of historical values
        
    Returns:
        pd.DataFrame: COGS breakdown dataframe
    """
    st.subheader("Cost of Goods Sold (COGS)")
    
    # Create COGS breakdown table
    cogs_df = create_cogs_breakdown_table(
        project_cogs_breakdown,
        project_cogs_by_year,
        hist_col,
        years,
        base_year,
        segment_metrics,
        hist_values
    )
    
    # Display the table
    display_cogs_breakdown_table(cogs_df, hist_col, years)
    
    return cogs_df


def create_gross_profit_breakdown_table(
    project_revenue_breakdown,
    project_cogs_breakdown,
    revenue_df,
    cogs_df,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Create gross profit breakdown table by segment
    
    Args:
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_cogs_breakdown: Dictionary of project COGS by project and year
        revenue_df: Revenue breakdown dataframe
        cogs_df: COGS breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics
        hist_values: Dictionary of historical values
        
    Returns:
        tuple: (gross_profit_df, projects_gp_total_by_year, total_revenue_row, total_cogs_row, total_gp_row)
    """
    # Get total revenue and COGS from the last row of each DataFrame
    total_revenue_row = revenue_df[revenue_df['Revenue Source'] == 'TOTAL REVENUE'].iloc[0]
    total_cogs_row = cogs_df[cogs_df['COGS Source'] == 'TOTAL COGS'].iloc[0]
    
    # Create gross profit breakdown by segment (rows = segments, columns = years)
    gross_profit_rows = []
    
    # Add individual project gross profit
    projects_gp_total_by_year = {year: 0 for year in years}
    for project_name in project_revenue_breakdown.keys():
        gp_row = {'Gross Profit Source': f"{project_name}"}
        gp_row[hist_col] = 0  # No historical breakdown by project
        for year in years:
            year_str = str(year)
            project_revenue = project_revenue_breakdown[project_name].get(year, 0)
            project_cogs = project_cogs_breakdown[project_name].get(year, 0)  # Already negative
            project_gp = project_revenue + project_cogs  # Add negative COGS to revenue
            gp_row[year_str] = project_gp
            projects_gp_total_by_year[year] += project_gp
        gross_profit_rows.append(gp_row)
    
    # Add subtotal for projects
    if gross_profit_rows:
        projects_subtotal_row = {'Gross Profit Source': 'Subtotal: Projects'}
        projects_subtotal_row[hist_col] = 0  # No historical breakdown
        for year in years:
            year_str = str(year)
            projects_subtotal_row[year_str] = projects_gp_total_by_year[year]
        gross_profit_rows.append(projects_subtotal_row)
    
    # Calculate gross profit for each other segment
    for segment_name in st.session_state.base_year_revenues.keys():
        gp_row = {'Gross Profit Source': f"{segment_name}"}
        gp_row[hist_col] = 0  # No historical breakdown
        base_revenue = st.session_state.base_year_revenues[segment_name]
        
        # Get metrics from segment_metrics
        if segment_name in segment_metrics:
            growth_rate = segment_metrics[segment_name]['revenue_growth']
            gross_margin = segment_metrics[segment_name]['gross_margin']
        else:
            growth_rate = 0.0  # Default 0%
            gross_margin = 0.0  # Default 0%
        
        for year in years:
            year_str = str(year)
            # Base year is the latest historical year, apply growth from there
            years_from_base = year - base_year
            year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
            
            year_cogs = year_revenue * (1 - gross_margin)
            gp_row[year_str] = year_revenue - year_cogs
        gross_profit_rows.append(gp_row)
    
    # Add total gross profit row
    total_gp_row = {'Gross Profit Source': 'TOTAL GROSS PROFIT'}
    total_gp_row[hist_col] = hist_values.get('Gross profit', 0)  # Historical Gross Profit
    for year in years:
        year_str = str(year)
        revenue = total_revenue_row[year_str]
        cogs = total_cogs_row[year_str]  # Already negative
        total_gp_row[year_str] = revenue + cogs  # Add negative COGS to revenue
    gross_profit_rows.append(total_gp_row)
    
    # Create DataFrame for gross profit
    gross_profit_df = pd.DataFrame(gross_profit_rows)
    
    return gross_profit_df, projects_gp_total_by_year, total_revenue_row, total_cogs_row, total_gp_row


def display_gross_profit_table(gross_profit_df, hist_col, years):
    """
    Display the gross profit breakdown table with proper formatting
    
    Args:
        gross_profit_df: Gross profit breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    # Style function to highlight subtotal and total rows
    def highlight_special_gp_rows(row):
        if 'TOTAL' in str(row['Gross Profit Source']) or 'Subtotal' in str(row['Gross Profit Source']):
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.write("**Gross Profit Summary by Segment (Billion VND)**")
    
    # Define column configuration for consistent width
    gp_column_config = {
        'Gross Profit Source': st.column_config.TextColumn('Gross Profit Source', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        gp_column_config[col] = st.column_config.NumberColumn(col, width='small')
    
    st.dataframe(
        gross_profit_df.style
        .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
        .apply(highlight_special_gp_rows, axis=1),
        use_container_width=True,
        column_config=gp_column_config,
        hide_index=True
    )


def create_gross_margin_table(
    project_revenue_by_year,
    gross_profit_df,
    projects_gp_total_by_year,
    total_revenue_row,
    total_gp_row,
    hist_col,
    years,
    segment_metrics,
    hist_values
):
    """
    Create gross profit margin table by segment
    
    Args:
        project_revenue_by_year: Dictionary of total project revenue by year
        gross_profit_df: Gross profit breakdown dataframe
        projects_gp_total_by_year: Dictionary of total project GP by year
        total_revenue_row: Total revenue row from revenue_df
        total_gp_row: Total GP row dictionary
        hist_col: Historical column name
        years: List of forecast years
        segment_metrics: Dictionary of segment metrics
        hist_values: Dictionary of historical values
        
    Returns:
        pd.DataFrame: Gross margin dataframe
    """
    margin_rows = []
    
    # Calculate margin for Projects (using subtotal)
    projects_margin_row = {'Segment': 'Projects'}
    projects_margin_row['2024H'] = 0  # Will calculate if historical data exists
    for year in years:
        year_str = str(year)
        projects_revenue = project_revenue_by_year[year]
        if projects_revenue > 0:
            # Use Subtotal: Projects row for gross profit
            subtotal_row = gross_profit_df[gross_profit_df['Gross Profit Source'] == 'Subtotal: Projects']
            if not subtotal_row.empty:
                projects_gp = subtotal_row.iloc[0][year_str]
            else:
                # Fallback: sum individual projects
                projects_gp = projects_gp_total_by_year[year]
            projects_margin_row[year_str] = (projects_gp / projects_revenue) * 100
        else:
            projects_margin_row[year_str] = 0
    margin_rows.append(projects_margin_row)
    
    # Calculate margin for each other segment
    for segment_name in st.session_state.base_year_revenues.keys():
        margin_row = {'Segment': segment_name}
        margin_row['2024H'] = 0  # Will calculate if historical data exists
        
        # Get gross margin from segment_metrics
        if segment_name in segment_metrics:
            gross_margin = segment_metrics[segment_name]['gross_margin'] * 100
        else:
            gross_margin = 0.0  # Default 0%
        
        for year in years:
            year_str = str(year)
            margin_row[year_str] = gross_margin
        margin_rows.append(margin_row)
    
    # Add overall margin row
    overall_margin_row = {'Segment': 'OVERALL MARGIN'}
    # Calculate historical margin if data exists
    if hist_values.get('Net Revenue', 0) > 0 and hist_values.get('Gross profit', 0) > 0:
        overall_margin_row['2024H'] = (hist_values['Gross profit'] / hist_values['Net Revenue']) * 100
    else:
        overall_margin_row['2024H'] = 0
    for year in years:
        year_str = str(year)
        revenue = total_revenue_row[year_str]
        if revenue > 0:
            gross_profit = total_gp_row[year_str]
            overall_margin_row[year_str] = (gross_profit / revenue) * 100
        else:
            overall_margin_row[year_str] = 0
    margin_rows.append(overall_margin_row)
    
    # Create DataFrame for margins
    return pd.DataFrame(margin_rows)


def display_gross_margin_table(margin_df, hist_col, years):
    """
    Display the gross margin table with proper formatting
    
    Args:
        margin_df: Gross margin dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    st.write("**Gross Profit Margin by Segment (%)**")
    
    # Define column configuration for consistent width
    margin_column_config = {
        'Segment': st.column_config.TextColumn('Segment', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        margin_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f%%')
    
    st.dataframe(
        margin_df.style
        .format("{:.1f}%", subset=[hist_col] + [str(y) for y in years])
        .apply(lambda row: ['font-weight: bold'] * len(row) if 'OVERALL' in str(row['Segment']) else [''] * len(row), axis=1),
        use_container_width=True,
        column_config=margin_column_config,
        hide_index=True
    )


def render_gross_profit_tab(
    project_revenue_breakdown,
    project_cogs_breakdown,
    project_revenue_by_year,
    revenue_df,
    cogs_df,
    hist_col,
    years,
    base_year,
    segment_metrics,
    hist_values
):
    """
    Render the complete gross profit analysis tab
    
    Args:
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_cogs_breakdown: Dictionary of project COGS by project and year
        project_revenue_by_year: Dictionary of total project revenue by year
        revenue_df: Revenue breakdown dataframe
        cogs_df: COGS breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
        base_year: Base historical year
        segment_metrics: Dictionary of segment metrics
        hist_values: Dictionary of historical values
        
    Returns:
        tuple: (gross_profit_df, margin_df, projects_gp_total_by_year)
    """
    st.subheader("Gross Profit Analysis")
    
    # Create gross profit breakdown table
    gross_profit_df, projects_gp_total_by_year, total_revenue_row, total_cogs_row, total_gp_row = create_gross_profit_breakdown_table(
        project_revenue_breakdown,
        project_cogs_breakdown,
        revenue_df,
        cogs_df,
        hist_col,
        years,
        base_year,
        segment_metrics,
        hist_values
    )
    
    # Display gross profit table
    display_gross_profit_table(gross_profit_df, hist_col, years)
    
    # Create gross margin table
    margin_df = create_gross_margin_table(
        project_revenue_by_year,
        gross_profit_df,
        projects_gp_total_by_year,
        total_revenue_row,
        total_gp_row,
        hist_col,
        years,
        segment_metrics,
        hist_values
    )
    
    # Display gross margin table
    display_gross_margin_table(margin_df, hist_col, years)
    
    return gross_profit_df, margin_df, projects_gp_total_by_year


def create_pbt_breakdown_table(
    df_projects,
    hist_col,
    years
):
    """
    Create PBT breakdown table loading from project details
    
    Args:
        df_projects: DataFrame containing project data
        hist_col: Historical column name
        years: List of forecast years
        
    Returns:
        tuple: (pbt_breakdown_df, project_pbt_breakdown, project_pbt_total_by_year)
    """
    pbt_breakdown_rows = []
    
    # Create project PBT breakdown - load from project details
    project_pbt_breakdown = {}
    project_pbt_total_by_year = {year: 0 for year in years}
    
    # First, try to load PBT from MongoDB if available
    for _, project in df_projects.iterrows():
        project_name = project.get('project_name', 'Unknown')
        if project_name not in project_pbt_breakdown:
            project_pbt_breakdown[project_name] = {}
        
        financial_statements = project.get('comprehensive_financial_statements', {})
        if not isinstance(financial_statements, dict):
            financial_statements = {}
        
        for year in years:
            year_str = str(year)
            
            if year_str in financial_statements:
                year_data = financial_statements[year_str]
                # Check if PBT is available in the data
                if 'pbt' in year_data:
                    project_pbt = year_data.get('pbt', 0) / 1e9
                else:
                    # No PBT data available
                    project_pbt = 0
            else:
                # No data for this year
                project_pbt = 0
            
            project_pbt_breakdown[project_name][year] = project_pbt
            project_pbt_total_by_year[year] += project_pbt
    
    # Now create the display rows
    for project_name in project_pbt_breakdown.keys():
        pbt_project_row = {'PBT Source': f"{project_name}"}
        pbt_project_row[hist_col] = 0  # No historical breakdown by project
        
        for year in years:
            year_str = str(year)
            pbt_project_row[year_str] = project_pbt_breakdown[project_name].get(year, 0)
        
        pbt_breakdown_rows.append(pbt_project_row)
    
    # Add subtotal for projects
    if pbt_breakdown_rows:
        projects_pbt_subtotal = {'PBT Source': 'Projects PBT'}
        projects_pbt_subtotal[hist_col] = 0
        for year in years:
            year_str = str(year)
            projects_pbt_subtotal[year_str] = project_pbt_total_by_year[year]
        pbt_breakdown_rows.append(projects_pbt_subtotal)
    
    # Create DataFrame for PBT breakdown
    pbt_breakdown_df = pd.DataFrame(pbt_breakdown_rows)
    
    return pbt_breakdown_df, project_pbt_breakdown, project_pbt_total_by_year


def display_pbt_breakdown_table(pbt_breakdown_df, hist_col, years):
    """
    Display the PBT breakdown table with proper formatting
    
    Args:
        pbt_breakdown_df: PBT breakdown dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    # Style function to highlight special rows
    def highlight_pbt_rows(row):
        if 'TOTAL' in str(row['PBT Source']) or 'Projects PBT' in str(row['PBT Source']):
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.write("**Profit Before Tax Breakdown (Billion VND)**")
    
    # Define column configuration for consistent width
    pbt_column_config = {
        'PBT Source': st.column_config.TextColumn('PBT Source', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        pbt_column_config[col] = st.column_config.NumberColumn(col, width='small')
    
    st.dataframe(
        pbt_breakdown_df.style
        .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
        .apply(highlight_pbt_rows, axis=1),
        use_container_width=True,
        column_config=pbt_column_config,
        hide_index=True
    )


def create_pbt_margin_table(
    project_pbt_breakdown,
    project_pbt_total_by_year,
    project_revenue_breakdown,
    project_revenue_by_year,
    hist_col,
    years
):
    """
    Create PBT margin table for projects
    
    Args:
        project_pbt_breakdown: Dictionary of project PBT by project and year
        project_pbt_total_by_year: Dictionary of total project PBT by year
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_revenue_by_year: Dictionary of total project revenue by year
        hist_col: Historical column name
        years: List of forecast years
        
    Returns:
        pd.DataFrame: PBT margin dataframe
    """
    pbt_margin_rows = []
    
    # Calculate margin for each individual project
    for project_name in project_pbt_breakdown.keys():
        project_margin_row = {'Segment': project_name}
        project_margin_row[hist_col] = 0  # No historical breakdown by project
        
        for year in years:
            year_str = str(year)
            project_revenue = project_revenue_breakdown.get(project_name, {}).get(year, 0)
            if project_revenue > 0:
                project_pbt = project_pbt_breakdown[project_name].get(year, 0)
                project_margin_row[year_str] = (project_pbt / project_revenue) * 100
            else:
                project_margin_row[year_str] = 0
        pbt_margin_rows.append(project_margin_row)
    
    # Calculate overall projects margin
    overall_projects_margin_row = {'Segment': 'Projects PBT Margin'}
    overall_projects_margin_row[hist_col] = 0
    for year in years:
        year_str = str(year)
        projects_revenue = project_revenue_by_year[year]
        if projects_revenue > 0:
            projects_pbt = project_pbt_total_by_year[year]
            overall_projects_margin_row[year_str] = (projects_pbt / projects_revenue) * 100
        else:
            overall_projects_margin_row[year_str] = 0
    pbt_margin_rows.append(overall_projects_margin_row)
    
    # Create DataFrame for PBT margins
    return pd.DataFrame(pbt_margin_rows)


def display_pbt_margin_table(pbt_margin_df, hist_col, years):
    """
    Display the PBT margin table with proper formatting
    
    Args:
        pbt_margin_df: PBT margin dataframe
        hist_col: Historical column name
        years: List of forecast years
    """
    st.write("**PBT Margin Analysis (%)**")
    
    # Define column configuration for margins
    margin_column_config = {
        'Segment': st.column_config.TextColumn('Segment', width='medium'),
    }
    for col in [hist_col] + [str(y) for y in years]:
        margin_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f%%')
    
    st.dataframe(
        pbt_margin_df.style
        .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
        .apply(lambda row: ['font-weight: bold'] * len(row) if row['Segment'] == 'Projects PBT Margin' else [''] * len(row), axis=1),
        use_container_width=True,
        column_config=margin_column_config,
        hide_index=True
    )


def render_pbt_tab(
    df_projects,
    project_revenue_breakdown,
    project_revenue_by_year,
    hist_col,
    years
):
    """
    Render the complete PBT analysis tab
    
    Args:
        df_projects: DataFrame containing project data
        project_revenue_breakdown: Dictionary of project revenues by project and year
        project_revenue_by_year: Dictionary of total project revenue by year
        hist_col: Historical column name
        years: List of forecast years
        
    Returns:
        tuple: (project_pbt_breakdown, project_pbt_total_by_year)
    """
    st.subheader("Profit Before Tax Analysis")
    
    # Create PBT breakdown table
    pbt_breakdown_df, project_pbt_breakdown, project_pbt_total_by_year = create_pbt_breakdown_table(
        df_projects,
        hist_col,
        years
    )
    
    # Display PBT breakdown table
    display_pbt_breakdown_table(pbt_breakdown_df, hist_col, years)
    
    # Create PBT margin table
    pbt_margin_df = create_pbt_margin_table(
        project_pbt_breakdown,
        project_pbt_total_by_year,
        project_revenue_breakdown,
        project_revenue_by_year,
        hist_col,
        years
    )
    
    # Display PBT margin table
    display_pbt_margin_table(pbt_margin_df, hist_col, years)
    
    return project_pbt_breakdown, project_pbt_total_by_year