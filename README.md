# Real Estate Financial Model - God AI Edition

A comprehensive real estate financial modeling application for the Vietnamese stock market, built for Dragon Capital's investment analysis workflows.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables (create .env file)
MONGODB_CONNECTION_STRING="your_mongodb_connection"
OPENAI_API_KEY="your_openai_key"
PERPLEXITY_API_KEY="your_perplexity_key"

# Run the application
streamlit run pages/Real_Estate_Financial_Model_God_AI.py
```

## Main Features

- **Historical Analysis**: Analyze historical financial data and trends
- **AI Project Discovery**: Discover real estate projects using Claude AI and Perplexity
- **Assumptions Management**: Configure and save modeling assumptions
- **Project Pipeline**: Manage and track real estate project pipeline
- **Model Forecast**: Generate revenue and financial forecasts
- **Valuation**: Perform RNAV and other valuation calculations
- **Research Insights**: AI-powered research and analysis
- **BDS-GPT**: Enhanced AI assistant for real estate analysis
- **Report Generation**: Generate comprehensive reports

## Application Structure

- `pages/Real_Estate_Financial_Model_God_AI.py` - Main application file
- `tabs/` - Individual feature modules
- `utils/` - Utility functions and helpers
- `data/` - Financial datasets

## Documentation

See `CLAUDE.md` for detailed development documentation and guidelines.

## Tech Stack

- **Frontend**: Streamlit
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly
- **Database**: MongoDB
- **AI**: Claude AI, Perplexity, OpenAI
- **Market Focus**: Vietnamese stock exchange (VND)