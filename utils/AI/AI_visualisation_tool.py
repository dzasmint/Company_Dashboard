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
    
    
