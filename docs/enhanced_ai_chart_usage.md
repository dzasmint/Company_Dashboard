# Enhanced AI Chart Rendering - Usage Guide

## ✅ Implementation Complete

The chart rendering functionality has been successfully integrated into the Enhanced AI tab of the Real Estate Financial Model page.

## How It Works

### 1. Architecture
- **Tool Layer**: `render_chart` and `create_financial_chart` tools in `enhanced_ai_assistant.py`
- **Rendering Layer**: `create_plotly_chart()` function in `utils/chart_utils.py`
- **Integration**: Charts are automatically rendered after AI responses

### 2. Data Flow
1. User asks for a chart/visualization
2. AI calls `render_chart` tool with structured data
3. Tool returns a chart specification
4. System stores spec in `st.session_state.pending_charts`
5. After AI response, charts are rendered using Plotly

### 3. Chart Types Supported
- **Line Charts**: Trends over time
- **Bar Charts**: Comparisons
- **Area Charts**: Cumulative values
- **Scatter Plots**: Correlations

### 4. Y-Axis Formats
- **number**: Default numeric format
- **percent**: Shows as percentages (0.35 → 35%)
- **currency**: Shows with currency formatting ($1,234.56)

## Example Queries

### Financial Forecasts
```
"Show me TCH's revenue forecast from 2025 to 2028 in a chart"
"Visualize the forecasted net revenues for TCH from 2025 to 2028"
"Create a bar chart showing TCH revenue growth 2025-2028"
```

### Historical Data
```
"Chart VHM's revenue trend for the last 5 years"
"Show me quarterly revenue growth for DXG in 2023"
"Visualize EBITDA margins for real estate companies"
```

### Comparisons
```
"Compare revenue between VHM, DXG, and NVL in a chart"
"Show P/E ratios for top real estate companies"
"Chart debt levels across real estate sector"
```

## Testing

### Run Test Script
```bash
streamlit run test_enhanced_ai_chart_integration.py
```

### Direct Test
```python
from utils.enhanced_ai_assistant import EnhancedAIToolSystem
system = EnhancedAIToolSystem()

# Execute render_chart
result = system.execute_tool('render_chart', {
    'chart_type': 'bar',
    'data': {
        'x': ['2025', '2026', '2027', '2028'],
        'series': [{'name': 'Revenue', 'y': [1842, 12493, 12573, 18157]}]
    },
    'title': 'TCH Revenue Forecast'
})

# Chart spec is in result['chart_spec']
```

## Troubleshooting

### Chart Not Appearing
1. Check OpenAI API key is configured
2. Verify `utils/chart_utils.py` exists
3. Ensure Plotly is installed: `pip install plotly`
4. Check browser console for JavaScript errors

### Data Issues
- Ensure x-axis has string labels
- Y-values must be numeric
- Series must have matching lengths

### Tool Not Found
- Restart Streamlit app to reload modules
- Check `render_chart` in tool list

## Files Modified

1. **utils/enhanced_ai_assistant.py**
   - Added `render_chart` tool
   - Updated `create_financial_chart` to use render_chart
   - Added chart handling in `chat_with_ai()`

2. **utils/chart_utils.py** (new)
   - `create_plotly_chart()` function
   - Chart rendering utilities

3. **Test Files**
   - `test_enhanced_chart.py` - Tool testing
   - `test_enhanced_ai_chart_integration.py` - Integration test
   - `examples/enhanced_ai_with_charts.py` - Usage example

## Color Scheme

Charts use a custom color palette:
- Primary: #398278 (teal)
- Secondary: #cc7c5e (terracotta)
- Additional: #5A8A7F, #e6a085, #2D5E52, #b5694f

## Next Steps

The chart functionality is fully operational. Users can now:
1. Ask for visualizations in natural language
2. See charts rendered automatically below AI responses
3. Export charts using Plotly's built-in tools

The TCH revenue forecast chart showing growth from 1.8 trillion VND (2025) to 18.2 trillion VND (2028) will now render correctly in the Enhanced AI tab.