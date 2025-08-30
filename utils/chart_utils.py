"""
Chart utilities for rendering AI-generated charts
Provides functions to create Plotly charts from AI tool specifications
"""

import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any

def create_plotly_chart(chart_spec: Dict) -> go.Figure:
    """
    Create a Plotly chart from the AI tool specification
    
    Args:
        chart_spec: Dictionary containing chart configuration with:
            - chart_type: Type of chart (line, bar, stacked_bar, scatter, area)
            - data: Dictionary with 'x' (labels) and 'series' (data series)
            - title: Chart title
            - x_label: X-axis label
            - y_label: Y-axis label
            - y_format: Format for y-axis (percent, currency, number)
    
    Returns:
        Plotly Figure object ready for display
    """
    chart_type = chart_spec.get("chart_type", "line")
    data = chart_spec.get("data", {})
    title = chart_spec.get("title", "")
    x_label = chart_spec.get("x_label", "")
    y_label = chart_spec.get("y_label", "")
    y_format = chart_spec.get("y_format", "number")
    
    # Define custom color palette - #398278 (teal) and #cc7c5e (terracotta)
    custom_colors = ['#398278', '#cc7c5e', '#5A8A7F', '#e6a085', '#2D5E52', '#b5694f']
    
    # Create figure
    fig = go.Figure()
    
    # Add data series
    x_values = data.get("x", [])
    for idx, series in enumerate(data.get("series", [])):
        name = series.get("name", "Series")
        y_values = series.get("y", [])
        color = custom_colors[idx % len(custom_colors)]
        
        if chart_type == "line":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines+markers',
                name=name,
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color)
            ))
        elif chart_type == "bar":
            fig.add_trace(go.Bar(
                x=x_values,
                y=y_values,
                name=name,
                marker=dict(color=color)
            ))
        elif chart_type == "stacked_bar":
            fig.add_trace(go.Bar(
                x=x_values,
                y=y_values,
                name=name,
                marker=dict(color=color)
            ))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='markers',
                name=name,
                marker=dict(size=8, color=color)
            ))
        elif chart_type == "area":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines',
                name=name,
                fill='tozeroy',
                line=dict(width=2, color=color),
                fillcolor=color
            ))
    
    # Format y-axis based on type
    yaxis_config = {"title": y_label}
    if y_format == "percent":
        yaxis_config["tickformat"] = ".1%"
    elif y_format == "currency":
        # For Vietnamese Dong, use number format without currency symbol
        # The currency is indicated in the axis label instead
        yaxis_config["tickformat"] = ",.0f"
    
    # Update layout
    layout_config = {
        "title": title,
        "xaxis_title": x_label,
        "yaxis": yaxis_config,
        "hovermode": 'x unified',
        "showlegend": True,
        "legend": dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        "margin": dict(l=50, r=50, t=80, b=50),
        "height": 400,
        "template": 'plotly_white'
    }
    
    # Add barmode for stacked bars
    if chart_type == "stacked_bar":
        layout_config["barmode"] = "stack"
    
    fig.update_layout(**layout_config)
    
    return fig


def handle_tool_charts(tool_result: Dict) -> list:
    """
    Extract chart specifications from tool execution results
    
    Args:
        tool_result: Result from AI tool execution
    
    Returns:
        List of chart specifications to render
    """
    charts = []
    
    # Check if the result is a chart render
    if tool_result.get("type") == "chart" and "chart_spec" in tool_result:
        charts.append(tool_result["chart_spec"])
    
    # Check for nested chart specifications (in case of batch operations)
    if isinstance(tool_result, dict):
        for key, value in tool_result.items():
            if isinstance(value, dict) and value.get("type") == "chart":
                if "chart_spec" in value:
                    charts.append(value["chart_spec"])
    
    return charts


def create_comparison_chart(tickers: list, metrics: Dict[str, list], title: str = "Company Comparison") -> go.Figure:
    """
    Create a comparison chart for multiple companies
    
    Args:
        tickers: List of company tickers
        metrics: Dictionary with metric names as keys and values as lists
        title: Chart title
    
    Returns:
        Plotly Figure object
    """
    # Define custom colors
    custom_colors = ['#398278', '#cc7c5e', '#5A8A7F', '#e6a085', '#2D5E52', '#b5694f']
    
    fig = go.Figure()
    
    # Create bar chart with grouped bars
    for idx, (metric, values) in enumerate(metrics.items()):
        fig.add_trace(go.Bar(
            name=metric,
            x=tickers,
            y=values,
            marker_color=custom_colors[idx % len(custom_colors)]
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Company",
        yaxis_title="Value",
        barmode='group',
        hovermode='x unified',
        template='plotly_white',
        height=400
    )
    
    return fig


def create_trend_chart(dates: list, values: Dict[str, list], title: str = "Trend Analysis", 
                       y_format: str = "number") -> go.Figure:
    """
    Create a trend chart over time
    
    Args:
        dates: List of date strings
        values: Dictionary with series names as keys and values as lists
        title: Chart title
        y_format: Format for y-axis (percent, currency, number)
    
    Returns:
        Plotly Figure object
    """
    # Define custom colors
    custom_colors = ['#398278', '#cc7c5e', '#5A8A7F', '#e6a085', '#2D5E52', '#b5694f']
    
    fig = go.Figure()
    
    # Add line traces for each series
    for idx, (series_name, series_values) in enumerate(values.items()):
        fig.add_trace(go.Scatter(
            x=dates,
            y=series_values,
            mode='lines+markers',
            name=series_name,
            line=dict(width=2, color=custom_colors[idx % len(custom_colors)]),
            marker=dict(size=6, color=custom_colors[idx % len(custom_colors)])
        ))
    
    # Format y-axis
    yaxis_config = {}
    if y_format == "percent":
        yaxis_config["tickformat"] = ".1%"
    elif y_format == "currency":
        # For Vietnamese Dong, use number format without currency symbol
        yaxis_config["tickformat"] = ",.0f"
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis=yaxis_config,
        hovermode='x unified',
        template='plotly_white',
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig