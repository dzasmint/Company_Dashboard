#!/usr/bin/env python3
"""
Test script for Enhanced AI Assistant with OpenAI integration
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.enhanced_ai_assistant import EnhancedAIToolSystem

def test_enhanced_ai():
    """Test the Enhanced AI Assistant"""
    
    print("=" * 60)
    print("ENHANCED AI ASSISTANT TEST")
    print("=" * 60)
    
    # Initialize system
    system = EnhancedAIToolSystem()
    print(f"✅ System initialized with {len(system.tools)} tools")
    
    # Check configurations
    print("\n📋 Configuration Status:")
    
    # Check OpenAI
    if os.getenv('OPENAI_API_KEY'):
        print("✅ OpenAI API key configured")
        print(f"   Model: {os.getenv('OPENAI_MODEL', 'gpt-4-turbo-preview')}")
    else:
        print("⚠️ OpenAI API key not found - chat_with_ai will not work")
    
    # Check MongoDB
    if system.mongo_client:
        print("✅ MongoDB connected")
        if system.vietnam_stocks_db is not None:
            collections = system.vietnam_stocks_db.list_collection_names()
            print(f"   VietnamStocks collections: {len(collections)}")
        if system.moc_db is not None:
            collections = system.moc_db.list_collection_names()
            print(f"   MoCDB collections: {len(collections)}")
    else:
        print("⚠️ MongoDB not connected")
    
    # Check Claude
    if system.anthropic_client:
        print("✅ Claude API configured")
    else:
        print("⚠️ Claude API not configured")
    
    # List all tools
    print("\n🔧 Available Tools:")
    tools = system.get_tool_list()
    
    # Group by category
    categories = {
        'Financial': [],
        'Real Estate': [],
        'Market': [],
        'Portfolio': [],
        'AI': []
    }
    
    for tool in tools:
        if 'financial' in tool or 'valuation' in tool or 'company' in tool.lower():
            categories['Financial'].append(tool)
        elif 'project' in tool or 'real_estate' in tool:
            categories['Real Estate'].append(tool)
        elif 'transaction' in tool or 'credit' in tool or 'inventory' in tool or 'market' in tool:
            categories['Market'].append(tool)
        elif 'portfolio' in tool or 'calculate' in tool:
            categories['Portfolio'].append(tool)
        else:
            categories['AI'].append(tool)
    
    for category, category_tools in categories.items():
        if category_tools:
            print(f"\n{category} Tools ({len(category_tools)}):")
            for tool in category_tools:
                print(f"  - {tool}")
    
    # Test a few tools
    print("\n" + "=" * 60)
    print("TESTING TOOL EXECUTION")
    print("=" * 60)
    
    # Test 1: List projects
    print("\n1. Testing list_real_estate_projects:")
    result = system.execute_tool('list_real_estate_projects', {'tickers': ['VHM'], 'limit': 2})
    if result.get('status') == 'success':
        print(f"   ✅ Success - Found {result.get('total_projects', 0)} projects")
    else:
        print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Test 2: Get financial data
    print("\n2. Testing get_historical_financials:")
    result = system.execute_tool('get_historical_financials', {
        'tickers': ['VHM'],
        'metrics': ['Net_Revenue', 'EBITDA'],
        'years': [2022, 2023]
    })
    if result.get('status') == 'success':
        print(f"   ✅ Success - Found {result.get('records', 0)} records")
    else:
        print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Test 3: Market data
    print("\n3. Testing get_transaction_volumes:")
    result = system.execute_tool('get_transaction_volumes', {'metric_type': 'apartment'})
    if result.get('status') == 'success':
        print(f"   ✅ Success - Found {result.get('quarters', 0)} quarters of data")
    else:
        print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    # Summary
    print("\n📊 Summary:")
    print(f"- Total tools available: {len(tools)}")
    print(f"- OpenAI ready: {'✅' if os.getenv('OPENAI_API_KEY') else '❌'}")
    print(f"- MongoDB ready: {'✅' if system.mongo_client else '❌'}")
    print(f"- Claude ready: {'✅' if system.anthropic_client else '❌'}")
    
    if os.getenv('OPENAI_API_KEY'):
        print("\n✅ System ready for chat_with_ai functionality!")
        print("   Users can ask natural language questions and GPT will")
        print("   automatically select and execute the appropriate tools.")
    else:
        print("\n⚠️ Add OPENAI_API_KEY to .env to enable chat functionality")

if __name__ == "__main__":
    test_enhanced_ai()