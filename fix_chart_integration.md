# How to Fix Chart Display in Your Application

## Problem
The AI is generating chart specifications correctly, but the charts aren't being rendered in the UI.

## Solution

### Step 1: Import Required Utilities
Add these imports to your Streamlit page:

```python
from utils.chart_utils import create_plotly_chart
import streamlit as st
```

### Step 2: Initialize Session State
Make sure you have pending_charts in session state:

```python
if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []
```

### Step 3: Handle Tool Execution
When executing AI tools, capture chart specifications:

```python
def handle_tool_response(tool_name, result):
    """Process tool results and capture charts"""
    if tool_name in ["render_chart", "create_financial_chart"]:
        if result.get("status") == "success" and "chart_spec" in result:
            st.session_state.pending_charts.append(result["chart_spec"])
    return result
```

### Step 4: Render Charts After AI Response
After the AI completes its response, render any pending charts:

```python
# After AI response is complete
if st.session_state.pending_charts:
    for chart_spec in st.session_state.pending_charts:
        try:
            # Create the Plotly figure from the spec
            fig = create_plotly_chart(chart_spec)
            
            # Display it in Streamlit
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering chart: {str(e)}")
    
    # Clear pending charts after rendering
    st.session_state.pending_charts = []
```

## Complete Example Integration

Here's a minimal example showing the complete integration:

```python
import streamlit as st
from utils.enhanced_ai_assistant import EnhancedAIToolSystem
from utils.chart_utils import create_plotly_chart
import json

# Initialize
if 'tool_system' not in st.session_state:
    st.session_state.tool_system = EnhancedAIToolSystem()

if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []

def process_ai_response(user_message):
    """Process user message and handle charts"""
    
    # ... Your AI processing logic here ...
    
    # When you get a tool response:
    if tool_name == "render_chart":
        result = st.session_state.tool_system.execute_tool(tool_name, arguments)
        
        # Capture chart specs
        if result.get("status") == "success" and "chart_spec" in result:
            st.session_state.pending_charts.append(result["chart_spec"])
    
    # After AI completes (no more tool calls):
    # Display the text response
    st.markdown(ai_response_text)
    
    # Then render any charts
    if st.session_state.pending_charts:
        for chart_spec in st.session_state.pending_charts:
            fig = create_plotly_chart(chart_spec)
            st.plotly_chart(fig, use_container_width=True)
        
        # Clear for next message
        st.session_state.pending_charts = []

# Your UI
user_input = st.chat_input("Ask a question...")
if user_input:
    process_ai_response(user_input)
```

## Testing the Fix

To verify it's working, you can test with this direct rendering:

```python
# Test chart with TCH data
test_spec = {
    "chart_type": "bar",
    "data": {
        "x": ["2025", "2026", "2027", "2028"],
        "series": [{
            "name": "Net Revenue",
            "y": [1842, 12493, 12573, 18157]
        }]
    },
    "title": "TCH Revenue Forecast 2025-2028",
    "x_label": "Year",
    "y_label": "Revenue (Billion VND)",
    "y_format": "number"
}

# Render it directly
from utils.chart_utils import create_plotly_chart
fig = create_plotly_chart(test_spec)
st.plotly_chart(fig, use_container_width=True)
```

## Common Issues and Solutions

1. **Chart not showing**: Make sure you're calling `st.plotly_chart()` after the AI response
2. **Import errors**: Ensure the path to `utils/chart_utils.py` is correct
3. **Empty charts**: Verify the chart_spec has valid data structure
4. **Chart appears then disappears**: Don't clear `pending_charts` too early

## Files to Check

1. Your main application file - needs the chart rendering logic
2. `/utils/chart_utils.py` - should exist with `create_plotly_chart()` function
3. `/utils/enhanced_ai_assistant.py` - should have the `render_chart` tool

The key is that the chart specification is being generated correctly (as shown in your screenshot), but the rendering step is missing. Add the rendering logic shown above to your application where the AI responses are displayed.