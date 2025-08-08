# Real Estate Financial Model - User Guide

## Overview
The Real Estate Financial Model is a comprehensive analyst workstation designed specifically for Vietnamese real estate companies. It combines historical financial analysis, project-level RNAV calculations, AI-powered research insights, and sophisticated forecasting capabilities into a single integrated platform.

## Key Features

### 1. **Historical Financial Analysis**
- Automatic data fetching from multiple sources (SSI API, MongoDB)
- Interactive financial trends visualization
- Key metrics dashboard (Revenue, Net Income, Margins, ROE)
- Quarterly and annual data support

### 2. **Excel-Like Assumptions Interface**
- Editable grid for all model assumptions
- Categories: Revenue Growth, Margins, Costs, Working Capital, Valuation
- Real-time model updates when assumptions change
- Sensitivity analysis on key variables

### 3. **Project Pipeline Integration**
- Syncs with RNAV Calculator and Real Estate Dashboard
- Project timeline visualization (Gantt charts)
- Automatic revenue forecast from project schedules
- Project-level contribution analysis

### 4. **Advanced Revenue Forecasting**
- Three revenue streams: Presales, Handover, Recurring
- Project-based revenue recognition
- Customizable growth assumptions
- Visual breakdown by source and project

### 5. **Complete Financial Projections**
- Income Statement projections
- Balance Sheet forecasts
- Cash Flow statements
- Key metrics tracking (CAGR, margins, ROE)

### 6. **Multi-Method Valuation**
- DCF valuation with terminal value
- P/E and P/B multiples analysis
- RNAV summation from projects
- Valuation comparison dashboard

### 7. **AI-Powered Research Insights**
- **Earnings Commentary Analysis**: Automatically analyzes latest earnings calls and management discussions
- **Sell-Side Report Parsing**: Aggregates consensus estimates from major Vietnamese brokers
- **Investment Thesis Generation**: AI-generated bull/bear cases and recommendations
- Real-time sentiment analysis

### 8. **Export & Sharing Capabilities**
- Export to Excel with all projections and assumptions
- PDF report generation (coming soon)
- Save/load model states in JSON format
- Shareable model links

## How to Use

### Getting Started
1. **Select a Company**: Choose a real estate company from the sidebar dropdown
2. **Refresh Data**: Click "Refresh Financial Data" to load latest financials
3. **Sync Projects**: Click "Sync Project Data" to load RNAV projects
4. **Fetch Reports**: Click "Fetch Latest Reports" for AI analysis

### Building Your Model

#### Step 1: Review Historical Performance
- Navigate to "Historical Analysis" tab
- Examine revenue trends and profitability
- Identify key drivers and patterns

#### Step 2: Set Assumptions
- Go to "Assumptions" tab
- Edit values directly in the grid
- Common adjustments:
  - Revenue growth rates (15-25% for presales)
  - Gross margins (30-40% typical)
  - WACC (10-12% for Vietnam)
  - Terminal growth (2-3%)

#### Step 3: Analyze Project Pipeline
- Check "Project Pipeline" tab
- Review project timelines
- Verify revenue recognition schedules
- Assess project concentration risk

#### Step 4: Review Revenue Forecast
- Navigate to "Revenue Forecast" tab
- Check if project-based forecast aligns with assumptions
- Adjust growth rates if needed
- Analyze project contribution mix

#### Step 5: Examine Financial Projections
- Review projected Income Statement
- Check Balance Sheet reasonableness
- Verify Free Cash Flow generation
- Monitor key metrics trends

#### Step 6: Perform Valuation
- Compare DCF, multiples, and RNAV values
- Identify valuation gaps
- Run sensitivity analysis
- Determine target price

#### Step 7: Leverage AI Insights
- Read earnings commentary analysis
- Review sell-side consensus
- Consider AI-generated thesis
- Factor in identified risks/opportunities

### Best Practices

1. **Data Quality**
   - Always refresh data before starting analysis
   - Verify project data completeness
   - Cross-check with company reports

2. **Assumption Setting**
   - Start with historical averages
   - Adjust based on company guidance
   - Consider industry benchmarks
   - Be conservative on margins

3. **Project Analysis**
   - Focus on near-term projects (1-3 years)
   - Apply probability weightings for uncertain projects
   - Consider execution track record
   - Account for regulatory delays

4. **Valuation Approach**
   - Use multiple methods for cross-validation
   - Weight methods based on company stage
   - Apply appropriate discounts (liquidity, size)
   - Consider market conditions

## Integration with Other Tools

### RNAV Calculator
- Projects automatically sync
- NPV calculations feed into valuation
- Consistent assumptions across tools

### Real Estate Dashboard
- Shared MongoDB database
- Project updates reflect immediately
- Unified company view

### Financial Data Viewer
- Historical data foundation
- Consistent data processing
- Shared utilities and constants

## Technical Requirements

### Required Packages
```bash
pip install streamlit pandas numpy plotly
pip install streamlit-aggrid xlsxwriter
pip install pymongo python-dotenv requests
```

### Environment Variables
```
MONGODB_CONNECTION_STRING=your_mongodb_connection
PERPLEXITY_API_KEY=your_perplexity_key
OPENAI_API_KEY=your_openai_key (optional)
```

## Troubleshooting

### MongoDB Connection Issues
- Check IP whitelist in MongoDB Atlas
- Verify connection string in .env
- Ensure network connectivity

### Missing Data
- Refresh financial data
- Sync project data
- Check data source availability

### Calculation Errors
- Verify all assumptions are numeric
- Check for division by zero
- Ensure positive values where required

## Advanced Features

### Sensitivity Analysis
1. Select variable (Gross Margin, Revenue Growth, WACC)
2. Set sensitivity range (-20% to +20%)
3. Run analysis to see impact on valuation
4. Use for risk assessment

### Scenario Modeling
- Create multiple assumption sets
- Save as different model states
- Compare scenarios side-by-side
- Useful for bull/bear/base cases

### Custom Formulas
- Model is extensible via Python
- Add custom metrics in projections
- Modify valuation methods
- Integrate additional data sources

## Updates and Roadmap

### Current Version (v1.0)
- Full financial modeling capability
- AI-powered research integration
- Excel-like interface
- Multi-method valuation

### Planned Features (v2.0)
- PDF report generation
- Monte Carlo simulation
- Peer comparison module
- API for external access
- Real-time market data
- Automated report scheduling

## Support

For issues or questions:
1. Check this documentation
2. Review error messages carefully
3. Ensure all dependencies installed
4. Verify data sources accessible

## Tips for Analysts

1. **Start Simple**: Begin with basic assumptions, refine iteratively
2. **Document Changes**: Use comments in export to track assumption rationale
3. **Cross-Check**: Validate against sell-side estimates
4. **Stay Updated**: Refresh data regularly for latest information
5. **Collaborate**: Share models via export for team review

## Conclusion

The Real Estate Financial Model provides institutional-grade financial modeling capabilities with the ease of use of modern web applications. By combining traditional financial analysis with AI-powered insights and project-level detail, it enables more accurate and comprehensive valuation of Vietnamese real estate companies.