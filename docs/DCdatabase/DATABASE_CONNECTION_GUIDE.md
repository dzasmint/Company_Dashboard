# MSSQL Database Connection Guide

**Connecting to Microsoft SQL Server using SQLAlchemy + pymssql**

This guide explains how to connect to an MSSQL database using the connection architecture implemented in this project. Our implementation provides flexible connection string parsing, automatic driver selection, connection pooling, and robust error handling.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Connection String Formats](#connection-string-formats)
4. [Configuration Methods](#configuration-methods)
5. [Implementation Details](#implementation-details)
6. [Connection Pooling](#connection-pooling)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Configuration](#advanced-configuration)

---

## Overview

Our database connection system uses:
- **SQLAlchemy**: Python SQL toolkit and ORM for database abstraction
- **pymssql**: Primary driver for MSSQL connections (FreeTDS-based, works on all platforms)
- **pyodbc**: Fallback driver for local development with Windows ODBC drivers

### Key Features

✅ **Flexible connection string parsing** - Accepts ODBC format, key=value format, or direct URLs
✅ **Automatic driver selection** - Tries pymssql first, falls back to pyodbc
✅ **Connection pooling** - Maintains 5-15 persistent connections for performance
✅ **URL encoding** - Handles special characters in passwords automatically
✅ **Connection validation** - Pre-pings connections before use
✅ **Singleton pattern** - Reuses a single database connection throughout app lifecycle
✅ **Dual configuration** - Supports both Streamlit secrets and environment variables

---

## Prerequisites

### 1. Install Required Packages

```bash
pip install sqlalchemy pymssql pandas
```

**Package versions used in this project:**
```txt
sqlalchemy>=2.0.0
pymssql>=2.2.0
pandas>=1.5.0
```

### 2. Optional: Install pyodbc for Windows

```bash
pip install pyodbc
```

**Note:** pyodbc requires Microsoft ODBC Driver for SQL Server on your system.

### 3. Database Requirements

- MSSQL Server (2016 or later recommended)
- Valid database credentials (username + password)
- Network access to database server (port 1433 typically)
- Database user must have `SELECT` permissions on required tables

---

## Connection String Formats

Our implementation accepts **three connection string formats**:

### Format 1: ODBC Connection String (Recommended)

```
Server=your-server.database.windows.net,1433;Database=your_database;User Id=your_username;Password=your_password
```

**Supported keys:**
- `Server` or `Data Source` - Server hostname and optional port
- `Database` or `Initial Catalog` - Database name
- `User Id` or `UID` or `User` - Username
- `Password` or `PWD` - Password
- `DRIVER` (optional) - Ignored but won't cause errors

**Examples:**
```
Server=localhost;Database=testdb;User Id=sa;Password=Pass123
Server=192.168.1.100,1433;Database=mydb;User Id=admin;Password=Secret!
Data Source=server.domain.com;Initial Catalog=analytics;UID=user;PWD=p@ssw0rd
```

### Format 2: Azure SQL Server Format

```
Server=tcp:your-server.database.windows.net,1433;Database=your_database;User Id=your_username;Password=your_password
```

**Note:** The `tcp:` prefix is automatically stripped during parsing.

### Format 3: Direct SQLAlchemy URL

```
mssql+pymssql://username:password@server:1433/database
```

**Use this format if:**
- You want explicit control over the driver
- You're migrating from another SQLAlchemy project
- You need to URL-encode special characters manually

**Example with special characters:**
```python
import urllib.parse

username = "admin"
password = "p@ssw0rd!#"
host = "server.com"
database = "mydb"

# URL encode the password
password_encoded = urllib.parse.quote_plus(password)

conn_string = f"mssql+pymssql://{username}:{password_encoded}@{host}:1433/{database}"
# Result: mssql+pymssql://admin:p%40ssw0rd%21%23@server.com:1433/mydb
```

---

## Configuration Methods

### Method 1: Streamlit Secrets (Production)

For Streamlit Cloud or production deployments, use Streamlit secrets:

**Create `.streamlit/secrets.toml`:**
```toml
DC_DB_STRING = "Server=your-server.database.windows.net,1433;Database=your_database;User Id=your_username;Password=your_password"
```

**Security notes:**
- `.streamlit/secrets.toml` should be in `.gitignore`
- Never commit secrets to version control
- On Streamlit Cloud, add secrets via the web interface

### Method 2: Environment Variable (Local Development)

For local development or non-Streamlit applications:

**Linux/Mac:**
```bash
export DC_DB_STRING="Server=localhost;Database=testdb;User Id=sa;Password=Pass123"
```

**Windows (PowerShell):**
```powershell
$env:DC_DB_STRING="Server=localhost;Database=testdb;User Id=sa;Password=Pass123"
```

**Windows (Command Prompt):**
```cmd
set DC_DB_STRING=Server=localhost;Database=testdb;User Id=sa;Password=Pass123
```

**Persistent environment variable (Linux/Mac):**

Add to `~/.bashrc` or `~/.zshrc`:
```bash
export DC_DB_STRING="Server=localhost;Database=testdb;User Id=sa;Password=Pass123"
```

Then reload:
```bash
source ~/.bashrc
```

### Method 3: Python Code (Testing Only)

**⚠️ WARNING:** Only use this for testing. Never hardcode credentials in production code.

```python
import os

# Set before importing db_connection
os.environ['DC_DB_STRING'] = "Server=localhost;Database=testdb;User Id=sa;Password=Pass123"

from utils.db_connection import get_db_connection
```

---

## Implementation Details

### File Structure

```
utils/
├── db_connection.py    # Connection management class
├── functions.py        # Query functions
└── variables.py        # Global variables
```

### Core Components

#### 1. DatabaseConnection Class

The main class that handles all database operations.

```python
from utils.db_connection import DatabaseConnection

# Initialize connection (reads from secrets or env)
db = DatabaseConnection()

# Execute query
df = db.execute_query("SELECT * FROM Market_Data WHERE TICKER = 'VNM'")

# Close connection
db.close()
```

#### 2. Singleton Pattern

Use `get_db_connection()` to reuse the same connection throughout your app:

```python
from utils.db_connection import get_db_connection

# First call creates the connection
db = get_db_connection()

# Subsequent calls return the same instance
db2 = get_db_connection()  # db2 is db -> True
```

#### 3. Connection String Parsing

The `_parse_connection_string()` method handles all formats:

```python
# Input: ODBC format
"Server=localhost,1433;Database=mydb;User Id=admin;Password=secret"

# Parsed output:
{
    'host': 'localhost',
    'port': '1433',
    'database': 'mydb',
    'username': 'admin',
    'password': 'secret'
}

# Converted to SQLAlchemy URL:
"mssql+pymssql://admin:secret@localhost:1433/mydb?charset=utf8"
```

#### 4. Automatic URL Encoding

Passwords with special characters are automatically URL-encoded:

```python
# Password: p@ssw0rd!#$
# Automatically becomes: p%40ssw0rd%21%23%24
```

**Special characters that require encoding:**
```
@ → %40
! → %21
# → %23
$ → %24
% → %25
& → %26
* → %2A
( → %28
) → %29
+ → %2B
= → %3D
```

---

## Connection Pooling

Our implementation uses SQLAlchemy's connection pooling for optimal performance.

### Pool Configuration

```python
engine = create_engine(
    connection_url,
    pool_size=5,           # Keep 5 connections alive
    max_overflow=10,       # Allow up to 10 additional connections
    pool_pre_ping=True,    # Test connections before use
    pool_recycle=3600,     # Recycle connections after 1 hour
    echo=False,            # Set to True for SQL debugging
    connect_args={
        "timeout": 30,     # Connection timeout: 30 seconds
    }
)
```

### Pool Behavior

| Scenario | Behavior |
|----------|----------|
| **App starts** | No connections created yet |
| **First query** | 1 connection opened, kept in pool |
| **Concurrent queries (≤5)** | Each gets a pooled connection |
| **Concurrent queries (6-15)** | Creates additional temporary connections |
| **Concurrent queries (>15)** | Waits for a connection to become available |
| **Connection idle > 1 hour** | Automatically recycled (reconnected) |
| **Connection lost** | Detected by pre-ping, reconnected automatically |

### Pool Advantages

✅ **Performance** - Eliminates connection overhead for repeated queries
✅ **Reliability** - Automatic reconnection on connection loss
✅ **Resource management** - Limits total connections to database
✅ **Concurrency** - Handles multiple simultaneous queries

---

## Usage Examples

### Example 1: Basic Query

```python
from utils.db_connection import get_db_connection

# Get connection
db = get_db_connection()

# Execute query
query = """
    SELECT TICKER, TRADE_DATE, PX_LAST
    FROM Market_Data
    WHERE TRADE_DATE >= '2025-01-01'
    ORDER BY TRADE_DATE DESC
"""

df = db.execute_query(query)

print(f"Retrieved {len(df)} rows")
print(df.head())
```

### Example 2: Parameterized Query

```python
from utils.db_connection import get_db_connection

db = get_db_connection()

query = """
    SELECT TICKER, TRADE_DATE, PX_LAST, PE, PB
    FROM Market_Data
    WHERE TICKER = :ticker
      AND TRADE_DATE BETWEEN :start_date AND :end_date
    ORDER BY TRADE_DATE
"""

params = {
    'ticker': 'VNM',
    'start_date': '2025-01-01',
    'end_date': '2025-12-31'
}

df = db.execute_query(query, params=params)
```

### Example 3: Using in Streamlit with Caching

```python
import streamlit as st
from utils.db_connection import get_db_connection

@st.cache_data
def load_market_data(ticker: str, start_date: str):
    """Load market data with caching."""
    db = get_db_connection()

    query = """
        SELECT TICKER, TRADE_DATE, PX_LAST, PE, PB, PS
        FROM Market_Data
        WHERE TICKER = :ticker
          AND TRADE_DATE >= :start_date
        ORDER BY TRADE_DATE
    """

    return db.execute_query(query, params={
        'ticker': ticker,
        'start_date': start_date
    })

# Usage in Streamlit app
df = load_market_data('VNM', '2025-01-01')
st.dataframe(df)
```

### Example 4: Transaction Example (Advanced)

```python
from utils.db_connection import get_db_connection
from sqlalchemy import text

db = get_db_connection()

# Using a transaction
with db.engine.begin() as conn:
    # Insert data
    conn.execute(
        text("INSERT INTO MyTable (col1, col2) VALUES (:val1, :val2)"),
        {"val1": "value1", "val2": "value2"}
    )

    # Update data
    conn.execute(
        text("UPDATE MyTable SET col2 = :new_val WHERE col1 = :id"),
        {"new_val": "updated", "id": "value1"}
    )

    # If any error occurs, transaction is automatically rolled back
```

### Example 5: Custom Query Function

```python
import pandas as pd
from utils.db_connection import get_db_connection

def get_top_stocks_by_market_cap(top_n: int = 10) -> pd.DataFrame:
    """
    Get top N stocks by market capitalization.

    Args:
        top_n: Number of top stocks to return

    Returns:
        DataFrame with ticker and market cap
    """
    db = get_db_connection()

    query = f"""
        SELECT TOP {top_n}
            TICKER,
            MKT_CAP,
            PX_LAST,
            TRADE_DATE
        FROM Market_Data
        WHERE TRADE_DATE = (SELECT MAX(TRADE_DATE) FROM Market_Data)
        ORDER BY MKT_CAP DESC
    """

    return db.execute_query(query)

# Usage
top_stocks = get_top_stocks_by_market_cap(20)
print(top_stocks)
```

---

## Troubleshooting

### Error: "Database connection string not found"

**Cause:** DC_DB_STRING not set in secrets or environment.

**Solution:**
```bash
# Check if variable is set
echo $DC_DB_STRING

# Set it
export DC_DB_STRING="Server=localhost;Database=testdb;User Id=sa;Password=Pass123"
```

### Error: "Missing required connection parameters"

**Cause:** Connection string is missing required fields (host, database, username, or password).

**Solution:** Verify your connection string has all required fields:
```
Server=HOST;Database=DATABASE;User Id=USERNAME;Password=PASSWORD
```

### Error: "Failed to connect to database"

**Cause:** Network issues, wrong credentials, or database not running.

**Solution:**
1. Test network connectivity:
```bash
telnet your-server.com 1433
# or
nc -zv your-server.com 1433
```

2. Verify credentials by connecting with a SQL client
3. Check firewall rules allow port 1433
4. Ensure database server is running

### Error: "pymssql not installed" or "No module named 'pymssql'"

**Cause:** pymssql package not installed.

**Solution:**
```bash
pip install pymssql
```

If installation fails on Linux, you may need FreeTDS development files:
```bash
# Ubuntu/Debian
sudo apt-get install freetds-dev

# CentOS/RHEL
sudo yum install freetds-devel

# Then install pymssql
pip install pymssql
```

### Error: "OperationalError: Login failed for user"

**Cause:** Invalid credentials or user doesn't have database access.

**Solution:**
1. Verify username and password
2. Check user has access to the database:
```sql
-- Run as admin user
SELECT name FROM sys.databases  -- List all databases
SELECT name FROM sys.sql_logins -- List all logins
```

3. Grant access if needed:
```sql
USE your_database;
CREATE USER [your_username] FOR LOGIN [your_username];
GRANT SELECT ON SCHEMA::dbo TO [your_username];
```

### Error: "Connection timeout"

**Cause:** Network latency or server overload.

**Solution:** Increase timeout in connection args:
```python
# In db_connection.py, modify connect_args
connect_args={
    "timeout": 60,  # Increase from 30 to 60 seconds
}
```

### Error: Special characters in password cause issues

**Cause:** Password contains characters that need URL encoding.

**Solution:** Our implementation automatically handles this, but if you're using direct SQLAlchemy URL format, manually encode:
```python
import urllib.parse

password = "p@ssw0rd!#"
encoded = urllib.parse.quote_plus(password)
# Result: p%40ssw0rd%21%23
```

### Performance Issue: Slow queries

**Solutions:**

1. **Enable query echo for debugging:**
```python
# In db_connection.py, set echo=True
engine = create_engine(connection_url, echo=True)
```

2. **Check for missing indexes:**
```sql
-- Find tables without indexes
SELECT OBJECT_NAME(object_id) AS TableName
FROM sys.tables
WHERE object_id NOT IN (SELECT object_id FROM sys.indexes WHERE index_id > 0)
```

3. **Monitor connection pool:**
```python
db = get_db_connection()
print(f"Pool size: {db.engine.pool.size()}")
print(f"Checked out connections: {db.engine.pool.checkedout()}")
```

---

## Advanced Configuration

### Custom Connection Pooling

Modify pool settings for your specific needs:

```python
# In db_connection.py, _create_engine() method

# High-concurrency configuration
engine = create_engine(
    connection_url,
    pool_size=20,          # More persistent connections
    max_overflow=30,       # More temporary connections
    pool_pre_ping=True,
    pool_recycle=1800,     # Recycle every 30 minutes
    pool_timeout=60,       # Wait up to 60s for available connection
)

# Low-resource configuration
engine = create_engine(
    connection_url,
    pool_size=2,           # Fewer persistent connections
    max_overflow=3,        # Fewer temporary connections
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Debugging configuration
engine = create_engine(
    connection_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=True,             # Log all SQL statements
    echo_pool=True,        # Log all pool checkouts/checkins
)
```

### Multiple Database Connections

If you need to connect to multiple databases:

```python
# utils/db_connection_multi.py

class MultiDatabaseManager:
    def __init__(self):
        self.connections = {}

    def add_connection(self, name: str, conn_string: str):
        """Add a named database connection."""
        from sqlalchemy import create_engine

        engine = create_engine(
            conn_string,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self.connections[name] = engine

    def get_connection(self, name: str):
        """Get a named connection."""
        return self.connections.get(name)

# Usage
manager = MultiDatabaseManager()
manager.add_connection('prod', 'mssql+pymssql://...')
manager.add_connection('dev', 'mssql+pymssql://...')

prod_engine = manager.get_connection('prod')
dev_engine = manager.get_connection('dev')
```

### Connection String from Azure Key Vault

For enterprise deployments using Azure Key Vault:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_connection_string_from_keyvault():
    """Retrieve connection string from Azure Key Vault."""
    credential = DefaultAzureCredential()
    vault_url = "https://your-keyvault.vault.azure.net/"
    client = SecretClient(vault_url=vault_url, credential=credential)

    secret = client.get_secret("db-connection-string")
    return secret.value

# Usage
import os
os.environ['DC_DB_STRING'] = get_connection_string_from_keyvault()

from utils.db_connection import get_db_connection
db = get_db_connection()
```

### Read-Only Connection

Create a separate read-only connection for reporting:

```python
# Create read-only user in SQL Server first
"""
CREATE LOGIN readonly_user WITH PASSWORD = 'SecurePassword123';
USE your_database;
CREATE USER readonly_user FOR LOGIN readonly_user;
GRANT SELECT ON SCHEMA::dbo TO readonly_user;
"""

# Python code
os.environ['DC_DB_STRING_READONLY'] = "Server=...;User Id=readonly_user;Password=..."
```

### SSL/TLS Encryption

For encrypted connections (Azure SQL, AWS RDS):

```python
# Azure SQL (automatic encryption)
connection_url = (
    "mssql+pymssql://user:pass@server.database.windows.net:1433/db"
    "?charset=utf8&encrypt=true&TrustServerCertificate=false"
)

# Custom SSL configuration
engine = create_engine(
    connection_url,
    connect_args={
        "tds_version": "7.0",
        "encrypt": "true",
        "trust_server_certificate": "false",
    }
)
```

---

## Testing Your Connection

Use the provided test script:

```bash
# Set connection string
export DC_DB_STRING="Server=localhost;Database=testdb;User Id=sa;Password=Pass123"

# Run test
python test_db_connection.py
```

**Expected output:**
```
============================================================
MSSQL Database Connection Test
============================================================

1. Testing connection string parsing...
   ✓ Parsed: Server=localhost;Database=testdb...
     Server: localhost, DB: testdb

2. Testing database connection...
   ✓ Database connection successful

3. Testing data retrieval...
   ✓ Found 5 sample records from Market_Data
     VNM: 2025-09-23 - Price: 67800
     CTG: 2025-09-23 - Price: 32450
     ...

4. Testing retrieve_vn_data_db function...
   ✓ Retrieved 15432 rows
     Columns: ['Ticker', 'Date', 'Close']
     Date range: 2025-07-01 to 2025-09-23
     Unique tickers: 1523

============================================================
Test completed
============================================================
```

---

## Summary

**Quick Start Checklist:**

1. ✅ Install dependencies: `pip install sqlalchemy pymssql pandas`
2. ✅ Set connection string:
   - **Production**: Add to `.streamlit/secrets.toml`
   - **Development**: Set `DC_DB_STRING` environment variable
3. ✅ Use singleton pattern: `db = get_db_connection()`
4. ✅ Execute queries: `df = db.execute_query(query)`
5. ✅ Test connection: `python test_db_connection.py`

**Connection String Template:**
```
Server=YOUR_SERVER;Database=YOUR_DATABASE;User Id=YOUR_USERNAME;Password=YOUR_PASSWORD
```

**Key Points:**
- Connection pooling is automatic (5-15 connections)
- Special characters in passwords are handled automatically
- Connections are validated before use (pool_pre_ping)
- Singleton pattern prevents multiple connection instances
- Works with Streamlit secrets or environment variables

---

## Additional Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [pymssql Documentation](https://pymssql.readthedocs.io/)
- [Microsoft SQL Server Documentation](https://docs.microsoft.com/en-us/sql/)
- [Streamlit Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)

---

**Last Updated:** 2025-10-07
**Version:** 1.0
**Project:** Broker Performance Tracker (Dragon Capital)
