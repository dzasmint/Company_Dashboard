# ChatGPT Financial Analysis Feature

## Overview
The Model Forecast page now includes an AI-powered financial analysis feature that uses ChatGPT to provide comprehensive investment analysis based on consolidated financial statements.

## Features

### 1. Comprehensive Analysis
The ChatGPT analysis covers:
- **Profitability & Revenue Growth**: Revenue trends, margin analysis, ROE/ROA calculations
- **Financial Health**: Debt ratios, leverage metrics, working capital analysis
- **Cash Flow Quality**: Operating cash flow trends, free cash flow generation
- **Key Strengths**: Major competitive advantages and positive factors
- **Red Flags & Risks**: Concerns and risk factors specific to the company
- **Investment Recommendation**: Overall assessment with target valuation metrics
- **Key Metrics Summary**: Table of important financial ratios

### 2. Data Integration
The analysis uses:
- Consolidated P&L Statement (including historical comparison)
- Consolidated Balance Sheet 
- Consolidated Cash Flow Statement
- Project-level breakdowns for real estate companies
- Business segment details

## Setup

### Prerequisites
1. OpenAI API key must be configured in `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

2. Install required packages (already in requirements.txt):
```bash
pip install openai
```

## Usage

### Running Analysis
1. Navigate to the **Model Forecast** tab
2. Select a company from the sidebar
3. Configure forecast assumptions if needed
4. Scroll down to the **AI Financial Analysis** section
5. Click **"Analyze with ChatGPT"** button
6. Wait for analysis to complete (typically 10-30 seconds)
7. Review the comprehensive analysis in the expandable section

### Testing Connection
Use the **Test OpenAI Connection** expander to verify API connectivity before running analysis.

## Technical Details

### Files Modified
- `/tabs/model_forecast.py`: Added ChatGPT analysis button and display logic
- `/utils/chatgpt_utils.py`: New utility file with OpenAI integration functions

### Key Functions
- `analyze_financial_statements()`: Main analysis function that sends financial data to ChatGPT
- `test_openai_connection()`: Verifies API key and connection
- `format_dataframe_for_chatgpt()`: Formats DataFrames for API consumption

### Model Configuration
- Default model: `gpt-5` (latest and most advanced model)
- Temperature: 1.0 (GPT-5 only supports default temperature)
- Max completion tokens: 2500 (comprehensive analysis)
- Note: GPT-5 has specific parameter requirements:
  - Uses `max_completion_tokens` instead of `max_tokens`
  - Only supports default temperature value (1.0)

## Error Handling

### Common Issues
1. **No API Key**: Set OPENAI_API_KEY in .env file
2. **Connection Failed**: Check internet connection and API key validity
3. **Rate Limit**: Wait a few moments and retry
4. **Timeout**: Analysis may take longer for complex statements

## Future Enhancements
- Export analysis to PDF/Word
- Save analysis history to MongoDB
- Compare multiple companies
- Customizable analysis templates
- Integration with other AI models (Claude, Gemini)