"""
AI Visualization Tools
Extracted from enhanced_ai_assistant.py
Contains data visualization tools for the Enhanced AI Tool System
"""

from typing import Dict, List
from datetime import datetime
import pandas as pd
import uuid


def register_visualization_tools(tool_system):
    """Register data visualization tools with the tool system
    
    Args:
        tool_system: The EnhancedAIToolSystem instance to register tools with
    """
    
    @tool_system.tool(
        name="render_chart",
        description="""Create a chart visualization from processed data. 
        INSTRUCTIONS FOR USE:
        1. ALWAYS gather data first using other tools (get_historical_financials, get_valuation_metrics, etc.)
        2. Structure data with clear x-axis labels and y-values
        3. Specify y_format: 'percent' for rates/ratios, 'number' for counts, 'currency' for monetary values
        4. Available chart types: line, bar, stacked_bar, scatter, area
        
        IMPORTANT:
        - Only pass processed, chart-ready data
        - Do NOT include raw data tables in your text response
        - For stacked_bar: provide multiple series that will be stacked
        """,
        parameters={
            "chart_type": {
                "type": "string",
                "enum": ["line", "bar", "stacked_bar", "scatter", "area"],
                "description": "Type of chart to render (use stacked_bar for stacked bar charts)"
            },
            "data": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "array",
                        "description": "X-axis labels (dates, categories, etc.)",
                        "items": {"type": "string"}
                    },
                    "series": {
                        "type": "array",
                        "description": "Data series to plot",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Series name for legend"},
                                "y": {
                                    "type": "array", 
                                    "description": "Y-axis values",
                                    "items": {"type": "number"}
                                }
                            }
                        }
                    }
                },
                "required": ["x", "series"]
            },
            "title": {
                "type": "string",
                "description": "Chart title"
            },
            "x_label": {
                "type": "string",
                "description": "X-axis label",
                "required": False
            },
            "y_label": {
                "type": "string",
                "description": "Y-axis label",
                "required": False
            },
            "y_format": {
                "type": "string",
                "enum": ["percent", "number", "currency"],
                "description": "Format for y-axis values",
                "required": False
            }
        }
    )
    def render_chart(chart_type: str, data: Dict, title: str, x_label: str = "", y_label: str = "", y_format: str = "number") -> Dict:
        """Prepare chart specification for rendering"""
        
        # Validate data structure
        if not data or "x" not in data or "series" not in data:
            return {"error": "Invalid data structure. Must have 'x' and 'series' fields", "status": "failed"}
        
        if not data["series"] or len(data["series"]) == 0:
            return {"error": "No data series provided", "status": "failed"}
        
        # Generate unique chart ID
        chart_id = str(uuid.uuid4())[:8]
        
        # Prepare chart specification
        chart_spec = {
            "chart_id": chart_id,
            "chart_type": chart_type,
            "data": data,
            "title": title,
            "x_label": x_label or "",
            "y_label": y_label or "",
            "y_format": y_format,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store chart spec in class attribute for retrieval
        if not hasattr(tool_system, '_pending_charts'):
            tool_system._pending_charts = {}
        tool_system._pending_charts[chart_id] = chart_spec
        
        # Return marker for the chat interface to detect
        return {
            "type": "chart",
            "chart_id": chart_id,
            "chart_spec": chart_spec,  # Include spec in response
            "message": f"Chart '{title}' prepared for rendering",
            "status": "success"
        }
    
    # Keep the original create_financial_chart for backward compatibility but updated
    @tool_system.tool(
        name="create_financial_chart",
        description="Create interactive financial charts using structured data format (alternative to render_chart)",
        parameters={
            "chart_type": {
                "type": "string",
                "enum": ["line", "bar", "waterfall", "scatter", "area", "combo"],
                "description": "Type of chart to create",
                "required": True
            },
            "data": {
                "type": "object",
                "description": "Data to visualize (as returned by other tools)",
                "required": True
            },
            "title": {
                "type": "string",
                "description": "Chart title",
                "required": False
            },
            "x_axis": {
                "type": "string",
                "description": "Column name for x-axis",
                "required": False
            },
            "y_axis": {
                "type": "string",
                "description": "Column name(s) for y-axis",
                "required": False
            },
            "options": {
                "type": "object",
                "description": "Additional chart options",
                "required": False
            }
        }
    )
    def create_financial_chart(chart_type: str, data: Dict = None, title: str = None,
                              x_axis: str = None, y_axis: str = None,
                              options: Dict = None) -> Dict:
        """Create interactive financial charts - converts to render_chart format"""
        
        try:
            # Validate data parameter
            if data is None:
                return {"error": "Data parameter is required", "status": "failed"}
            
            if not data:
                return {"error": "Data parameter cannot be empty", "status": "failed"}
            
            # Convert data to DataFrame if needed
            if isinstance(data, dict):
                if 'data' in data:
                    df = pd.DataFrame(data['data'])
                elif 'values' in data:
                    df = pd.DataFrame(data['values'])
                else:
                    df = pd.DataFrame([data])
            else:
                df = pd.DataFrame(data)
            
            # Determine axes if not specified
            if x_axis is None and 'DATE' in df.columns:
                x_axis = 'DATE'
            elif x_axis is None and len(df.columns) > 0:
                x_axis = df.columns[0]
            
            if y_axis is None and 'VALUE' in df.columns:
                y_axis = 'VALUE'
            elif y_axis is None and len(df.columns) > 1:
                y_axis = df.columns[1]
            
            # Convert to render_chart format
            x_values = df[x_axis].astype(str).tolist() if x_axis in df.columns else []
            
            series_data = []
            if isinstance(y_axis, list):
                for col in y_axis:
                    if col in df.columns:
                        series_data.append({
                            "name": col,
                            "y": df[col].tolist()
                        })
            elif y_axis in df.columns:
                series_data.append({
                    "name": y_axis,
                    "y": df[y_axis].tolist()
                })
            
            # Map chart types that aren't supported in render_chart
            mapped_chart_type = chart_type
            if chart_type == "waterfall":
                mapped_chart_type = "bar"
            elif chart_type == "combo":
                # For combo charts with multiple series, use stacked_bar
                mapped_chart_type = "stacked_bar" if len(series_data) > 1 else "bar"
            
            # Prepare data in render_chart format
            chart_data = {
                "x": x_values,
                "series": series_data
            }
            
            # Determine y_format
            y_format = "number"
            if options and "y_format" in options:
                y_format = options["y_format"]
            elif y_axis and isinstance(y_axis, str):
                if any(kw in y_axis.lower() for kw in ["margin", "ratio", "rate", "percent"]):
                    y_format = "percent"
                elif any(kw in y_axis.lower() for kw in ["revenue", "profit", "cost", "price"]):
                    y_format = "currency"
            
            # Call render_chart with converted data
            return render_chart(
                chart_type=mapped_chart_type,
                data=chart_data,
                title=title or f"{chart_type.capitalize()} Chart",
                x_label=x_axis,
                y_label=y_axis if isinstance(y_axis, str) else "Value",
                y_format=y_format
            )
            
        except Exception as e:
            return {"error": str(e), "status": "failed"}