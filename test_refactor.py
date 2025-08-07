#!/usr/bin/env python3
"""
Test script to verify refactored components work properly
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_imports():
    """Test that all refactored modules can be imported"""
    
    print("🧪 Testing imports...")
    
    try:
        from config.constants import PLOTLY_CONFIG, FINANCIAL_CATEGORIES
        print("✅ Config constants imported successfully")
        print(f"   - Available financial categories: {list(FINANCIAL_CATEGORIES.keys())}")
    except Exception as e:
        print(f"❌ Error importing config constants: {e}")
        return False
    
    try:
        from core.common_imports import pd, go, st
        print("✅ Common imports imported successfully") 
        print(f"   - Pandas version available: {hasattr(pd, '__version__')}")
    except Exception as e:
        print(f"❌ Error importing common imports: {e}")
        return False
    
    try:
        from core.data_loader import DataLoader, data_loader
        print("✅ DataLoader imported successfully")
        print(f"   - DataLoader instance created: {type(data_loader).__name__}")
    except Exception as e:
        print(f"❌ Error importing DataLoader: {e}")
        return False
        
    try:
        from core.plot_factory import PlotFactory, plot_factory
        print("✅ PlotFactory imported successfully")
        print(f"   - PlotFactory instance created: {type(plot_factory).__name__}")
    except Exception as e:
        print(f"❌ Error importing PlotFactory: {e}")
        return False
    
    return True

def test_data_structures():
    """Test that configuration data structures are properly defined"""
    
    print("\n🧪 Testing data structures...")
    
    try:
        from config.constants import FINANCIAL_CATEGORIES, DATA_FILES, PLOTLY_CONFIG
        
        # Test financial categories
        required_categories = ['IS', 'MARGIN', 'BS', 'CF']
        missing_categories = [cat for cat in required_categories if cat not in FINANCIAL_CATEGORIES]
        if missing_categories:
            print(f"❌ Missing financial categories: {missing_categories}")
            return False
        print(f"✅ All required financial categories present: {required_categories}")
        
        # Test data files mapping
        essential_files = ['financial_statements', 'valuation', 'market_cap']
        missing_files = [f for f in essential_files if f not in DATA_FILES]
        if missing_files:
            print(f"❌ Missing data file mappings: {missing_files}")
            return False
        print(f"✅ Essential data file mappings present: {essential_files}")
        
        # Test plotly config
        required_plot_keys = ['template', 'chart_height', 'colors']
        missing_plot_keys = [key for key in required_plot_keys if key not in PLOTLY_CONFIG]
        if missing_plot_keys:
            print(f"❌ Missing plotly config keys: {missing_plot_keys}")
            return False
        print(f"✅ Plotly configuration complete: {required_plot_keys}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing data structures: {e}")
        return False

def test_utility_functions():
    """Test that utility functions work as expected"""
    
    print("\n🧪 Testing utility functions...")
    
    try:
        from core.common_imports import format_currency_vnd, format_percentage
        
        # Test currency formatting
        test_value = 1500000000  # 1.5 billion
        formatted = format_currency_vnd(test_value, "billion")
        expected = "1.5B VND"
        if expected not in formatted:
            print(f"❌ Currency formatting failed: got '{formatted}', expected '{expected}'")
            return False
        print(f"✅ Currency formatting works: {test_value} -> {formatted}")
        
        # Test percentage formatting
        test_pct = 15.678
        formatted_pct = format_percentage(test_pct, 1)
        expected_pct = "15.7%"
        if formatted_pct != expected_pct:
            print(f"❌ Percentage formatting failed: got '{formatted_pct}', expected '{expected_pct}'")
            return False
        print(f"✅ Percentage formatting works: {test_pct} -> {formatted_pct}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing utility functions: {e}")
        return False

def test_file_structure():
    """Test that the refactored file structure is correct"""
    
    print("\n🧪 Testing file structure...")
    
    required_files = [
        "config/constants.py",
        "config/__init__.py", 
        "core/data_loader.py",
        "core/plot_factory.py",
        "core/common_imports.py",
        "core/__init__.py",
        "Company_Dashboard_Refactored.py",
        "utils/mongodb_utils.py",
        "utils/SSI_API.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = current_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    print(f"✅ All required files present: {len(required_files)} files checked")
    
    # Check archive directory  
    archive_dir = current_dir / "archive"
    if archive_dir.exists():
        archived_files = list(archive_dir.glob("*.disabled"))
        print(f"✅ Archive directory contains {len(archived_files)} disabled files")
    else:
        print("⚠️  Archive directory not found")
    
    return True

def main():
    """Run all tests"""
    print("🚀 Starting refactoring tests for Company Dashboard\n")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports), 
        ("Data Structures", test_data_structures),
        ("Utility Functions", test_utility_functions)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running {test_name} Tests")
        print(f"{'='*50}")
        
        try:
            if test_func():
                print(f"✅ {test_name} tests PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} tests FAILED")
        except Exception as e:
            print(f"❌ {test_name} tests ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"REFACTORING TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Refactoring is successful.")
        return True
    else:
        print("💥 Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)