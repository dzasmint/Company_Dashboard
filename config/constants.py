# Configuration constants for Company Dashboard

# Plotly configuration
PLOTLY_CONFIG = {
    'template': 'plotly_white',
    'chart_height': 600,
    'chart_width': 1200,
    'subplot_height_multiplier': 400,
    'colors': ['royalblue', 'darkorange', 'green', 'gray', 'red', 'purple', 'brown', 'pink']
}

# Financial constants
FINANCIAL_CONFIG = {
    'default_tax_rate': 0.2,
    'default_wacc': 0.12,
    'default_sga': 0.1,
    'moving_average_window': 4,
    'min_periods': 1
}

# Data file mappings
DATA_FILES = {
    'financial_statements': 'FA_A_processed.csv',
    'valuation': 'Val_processed.csv',
    'market_cap': 'MktCap_processed.csv',
    'bank_supplement': 'BankSupp_processed.csv',
    'bank_quarterly': 'df_q_full.csv',
    'classification': 'Classification.xlsx',
    'stock_list': 'STOCK LIST.xlsx',
    'bank_keycodes': 'IRIS KeyCodes - Bank.xlsx',
    'real_estate_projects': 'real_estate_projects.csv'
}

# Financial statement categories
FINANCIAL_CATEGORIES = {
    'IS': ['Net Revenue', 'COGS', 'Gross profit', 'SG&A expenses', 'EBIT', 'EBITDA', 'Interest expense', 'PBT', 'Tax', 'NPATMI'],
    'MARGIN': ['Gross profit margin', 'SG&A margin', 'EBIT margin', 'EBITDA margin', 'Tax rate', 'Net profit margin'],
    'BS': ['Cash and cash equivalents', 'Inventories', 'Current Assets', 'PPE', 'Total Assets', 'Current liabilities', 'Total Debt', 'Total Equity', 'Total Liabilities and Equity'],
    'CF': ['Operating CF', 'Capex', 'FCF']
}

# Bank specific metrics
BANK_METRICS = {
    'profitability': ['Net interest income', 'Non-interest income', 'Operating income', 'Operating expenses', 'Credit costs', 'PBT', 'NPAT'],
    'quality': ['NIM', 'CIR', 'CoF', 'Yield', 'ROE', 'ROA'],
    'asset_quality': ['NPL ratio', 'NPL coverage', 'Credit costs / Average loans']
}

# Real estate configuration
REAL_ESTATE_CONFIG = {
    'default_construction_cost': 15000000,  # VND per sqm
    'default_land_cost_ratio': 0.3,
    'default_margin': 0.25,
    'completion_stages': ['Planning', 'Construction', 'Marketing', 'Handover', 'Completed']
}

# MongoDB collections
MONGODB_COLLECTIONS = {
    'companies': 'Companies',
    'projects': 'projects',
    'real_estate_projects': 'RealEstateProjects'
}

# API endpoints
API_ENDPOINTS = {
    'ssi_base': 'https://iboard-api.ssi.com.vn',
    'ssi_market_data': '/statistics/foreigner',
    'ssi_company_data': '/securities'
}