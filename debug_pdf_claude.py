#!/usr/bin/env python3
"""
Debug script to test PDF reading and Claude AI extraction
"""

import os
import sys
import json
import PyPDF2
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    print(f"\n1. READING PDF: {pdf_path}")
    print("-" * 50)
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            print(f"Total pages: {total_pages}")
            
            text = ""
            # Read all pages
            pages_to_read = total_pages
            
            for page_num in range(pages_to_read):
                print(f"Reading page {page_num + 1}/{pages_to_read}...", end=" ")
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text += page_text + "\n"
                print(f"({len(page_text)} chars)")
            
            print(f"\nTotal text extracted: {len(text)} characters")
            print(f"First 500 characters of extracted text:")
            print("-" * 30)
            print(text[:500])
            print("-" * 30)
            
            return text
            
    except Exception as e:
        print(f"ERROR reading PDF: {str(e)}")
        return None

def test_business_segments_extraction(text, api_key):
    """Test business segments extraction with Claude"""
    print("\n2. TESTING BUSINESS SEGMENTS EXTRACTION")
    print("-" * 50)
    
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        return
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Limit text for API call - use more text for better extraction
    text_sample = text[:60000] if text else ""
    
    prompt = """Analyze this financial document and extract business segment information.

Look for business segments such as:
- Real Estate Development
- Property Investment
- Construction
- Hospitality
- Retail
- Or any other business divisions mentioned

Return ONLY a valid JSON object with this structure:
{
    "segments": ["Segment1", "Segment2"],
    "periods": ["2023", "2024", "Q1/2024"],
    "data": {
        "revenue": {"Segment1": {"2023": 1234.5}, "Total": {"2023": 5678.9}},
        "cogs": {},
        "gross_profit": {},
        "gross_margin": {}
    }
}

Start with { and end with }

Document text:
""" + text_sample
    
    print("Sending request to Claude AI...")
    print(f"Prompt length: {len(prompt)} characters")
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        print(f"\nClaude Response (first 1000 chars):")
        print("-" * 30)
        print(response_text[:1000])
        print("-" * 30)
        
        # Try to parse JSON
        print("\nAttempting to parse JSON...")
        try:
            result = json.loads(response_text)
            print("✅ Successfully parsed JSON!")
            print(json.dumps(result, indent=2)[:1000])
            return result
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                print("Trying to extract JSON with regex...")
                try:
                    result = json.loads(json_match.group())
                    print("✅ Successfully extracted and parsed JSON!")
                    print(json.dumps(result, indent=2)[:1000])
                    return result
                except json.JSONDecodeError as e2:
                    print(f"❌ Regex extraction also failed: {e2}")
            
    except Exception as e:
        print(f"ERROR calling Claude API: {str(e)}")
    
    return None

def test_real_estate_extraction(text, api_key):
    """Test real estate projects extraction with Claude"""
    print("\n3. TESTING REAL ESTATE PROJECTS EXTRACTION")
    print("-" * 50)
    
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        return
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Limit text for API call - use more text for better extraction
    text_sample = text[:60000] if text else ""
    
    prompt = """Extract ALL real estate projects from this document.

For each project, extract:
- project_name: Project name
- land_area_sqm: Land area in sqm
- total_units: Total units
- legal_status: Legal status
- selling_status: Selling status (% sold, etc.)

Return ONLY a valid JSON array. Start with [ and end with ]

Document text:
""" + text_sample
    
    print("Sending request to Claude AI...")
    print(f"Prompt length: {len(prompt)} characters")
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        print(f"\nClaude Response (first 1000 chars):")
        print("-" * 30)
        print(response_text[:1000])
        print("-" * 30)
        
        # Try to parse JSON
        print("\nAttempting to parse JSON array...")
        try:
            result = json.loads(response_text)
            if isinstance(result, list):
                print(f"✅ Successfully parsed JSON array with {len(result)} projects!")
                print(json.dumps(result[:2], indent=2) if result else "[]")
                return result
            else:
                print("❌ Response is not a JSON array")
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            
            # Try to extract JSON array from response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                print("Trying to extract JSON array with regex...")
                try:
                    result = json.loads(json_match.group())
                    print(f"✅ Successfully extracted and parsed JSON array with {len(result)} projects!")
                    print(json.dumps(result[:2], indent=2) if result else "[]")
                    return result
                except json.JSONDecodeError as e2:
                    print(f"❌ Regex extraction also failed: {e2}")
            
    except Exception as e:
        print(f"ERROR calling Claude API: {str(e)}")
    
    return None

def main():
    """Main function"""
    print("=" * 60)
    print("PDF & CLAUDE AI DEBUG SCRIPT")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set it in your .env file")
        return
    else:
        print(f"\n✅ ANTHROPIC_API_KEY found (length: {len(api_key)})")
    
    # PDF file path
    pdf_path = "/Users/hoangminhtrinh/Library/CloudStorage/Dropbox/Vietnam/Dragon Capital/AI_Mac/Company_Dashboard/data/Report/TCH/BCTN_TCH_V_final.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"\n❌ ERROR: PDF file not found at {pdf_path}")
        return
    
    print(f"\n✅ PDF file found: {pdf_path}")
    print(f"File size: {os.path.getsize(pdf_path) / (1024*1024):.2f} MB")
    
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        print("\n❌ Failed to extract text from PDF")
        return
    
    # Test both extractions
    print("\n" + "=" * 60)
    print("TESTING CLAUDE AI EXTRACTIONS")
    print("=" * 60)
    
    # Test business segments
    segments_result = test_business_segments_extraction(text, api_key)
    
    # Test real estate projects
    projects_result = test_real_estate_extraction(text, api_key)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"PDF Reading: {'✅ Success' if text else '❌ Failed'}")
    print(f"Business Segments: {'✅ Extracted' if segments_result else '❌ Failed'}")
    print(f"Real Estate Projects: {'✅ Extracted' if projects_result else '❌ Failed'}")
    
    if segments_result:
        print(f"\nSegments found: {segments_result.get('segments', [])}")
        print(f"Periods found: {segments_result.get('periods', [])}")
    
    if projects_result:
        print(f"\nProjects found: {len(projects_result)}")
        if projects_result:
            print(f"First project: {projects_result[0].get('project_name', 'Unknown')}")

if __name__ == "__main__":
    main()