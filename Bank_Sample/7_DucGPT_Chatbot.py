"""
MCP Model - AI Banking Analysis Assistant
Streamlit interface for OpenAI-powered banking analysis with tool execution
"""

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="DucGPT Chatbot",
    layout="wide"
)

import pandas as pd
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import and apply Google Fonts
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
apply_google_font()

# Apply consistent sidebar styling
apply_sidebar_style()

# Import the banking tool system
from utilities.Banking_MCP import get_tool_system

# Load environment variables
load_dotenv()

# Initialize session state (removed conversation history)
if 'tool_executions' not in st.session_state:
    st.session_state.tool_executions = []
if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None
if 'tool_system' not in st.session_state:
    st.session_state.tool_system = get_tool_system()


def execute_tool_call(tool_name: str, arguments: Dict) -> Dict:
    """Execute a tool and return results"""
    tool_system = st.session_state.tool_system
    
    # Log the tool execution
    execution_log = {
        "tool": tool_name,
        "arguments": arguments,
        "timestamp": datetime.now().isoformat()
    }
    
    # Execute the tool
    result = tool_system.execute_tool(tool_name, arguments)
    
    execution_log["result"] = result
    st.session_state.tool_executions.append(execution_log)
    
    return result


def format_tool_result(result: Dict) -> str:
    """Format tool result for display"""
    if result.get("status") == "failed":
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    # Remove status field for cleaner display
    display_result = {k: v for k, v in result.items() if k != "status"}
    
    # Format based on content type
    if "data" in display_result and isinstance(display_result["data"], list):
        # If data is a list of records, show as table
        if display_result["data"]:
            df = pd.DataFrame(display_result["data"])
            return f"Found {len(display_result['data'])} records:\n{df.to_string()}"
    
    # Default JSON formatting
    return json.dumps(display_result, indent=2, default=str)


def chat_with_ai(user_message: str) -> str:
    """
    Send message to OpenAI and handle tool calls
    Allows unlimited tool execution rounds for complete analysis
    """
    if not st.session_state.openai_client:
        return "❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
    
    # Prepare messages (NO conversation history - single Q&A mode)
    messages = []
    
    # Add system message
    messages.append({
        "role": "system",
        "content": """You are a banking analyst assistant. Use tools to get data, then provide analysis.
IMPORTANT: ALWAYS call get_data_availability() first when user asks for 'latest', 'recent', 'current' data or 'developments'.
Tickers must be arrays: ["VCB"] for single, ["VCB", "ACB"] for multiple."""
    })
    
    # Add current user message only (no history)
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas
    tools = st.session_state.tool_system.get_openai_tools()
    
    # Initialize progress tracking
    max_rounds = 20  # Reasonable limit to prevent infinite loops
    with st.spinner("Duc is typing..."):
        rounds = 0
        final_response = None
        tool_call_count = 0
        
        while rounds < max_rounds:
            rounds += 1
            
            # Call OpenAI
            try:
                response = st.session_state.openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-5"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.5
                )
            except Exception as e:
                return f"❌ Error calling OpenAI: {str(e)}"
            
            # Get assistant message
            assistant_message = response.choices[0].message
            messages.append(assistant_message.model_dump())
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                # Show tool execution status
                tool_status = st.empty()
                tool_results_container = st.container()
                
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Update status with counter
                    tool_call_count += 1
                    tool_status.info(f"🔧 Executing tool #{tool_call_count}: **{function_name}**")
                    
                    # Execute the tool
                    tool_result = execute_tool_call(function_name, function_args)
                    
                    # Show tool result in expander
                    with tool_results_container.expander(f"Tool: {function_name}", expanded=False):
                        st.code(json.dumps(function_args, indent=2))
                        if tool_result.get("status") == "success":
                            st.success("✅ Success")
                            # Show summary of result
                            if "records" in tool_result:
                                st.write(f"Found {tool_result['records']} records")
                            if "data" in tool_result and isinstance(tool_result["data"], list) and tool_result["data"]:
                                df = pd.DataFrame(tool_result["data"][:5])  # Show first 5 rows
                                st.dataframe(df)
                        else:
                            st.error(f"❌ {tool_result.get('error', 'Failed')}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str)
                    })
                
                # Clear the status
                tool_status.empty()
                
                # Continue to next round
                continue
            else:
                # No more tool calls, we have the final response
                final_response = assistant_message.content
                # Add tool count summary if tools were used
                if tool_call_count > 0:
                    final_response = f"{final_response}\n\n---\n*Analysis completed using {tool_call_count} tool{'s' if tool_call_count > 1 else ''}.*"
                break
        
        if not final_response:
            if rounds >= max_rounds:
                final_response = f"Analysis completed with {tool_call_count} tool calls. The query may be too complex for a single response."
            else:
                final_response = "Please provide a more specific banking-related question."
        
        return final_response


def main():
    st.title("DucGPT MCP version")
    st.markdown("Only banking related questions are supported.")
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please create a `.env` file with your OpenAI API key:")
        st.code("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model selection
        model = st.selectbox(
            "Model",
            ["gpt-4-turbo-preview", "gpt-3.5-turbo"],
            index=0
        )
        os.environ["OPENAI_MODEL"] = model
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            tools = st.session_state.tool_system.get_tool_list()
            for tool in tools:
                st.write(f"• {tool}")
        
        # Clear tool executions
        if st.button("🗑️ Clear Tool History"):
            st.session_state.tool_executions = []
            st.rerun()
        
        # Export tool executions
        if st.button("📥 Export Tool History"):
            export_data = {
                "tool_executions": st.session_state.tool_executions,
                "timestamp": datetime.now().isoformat()
            }
            st.download_button(
                "Download JSON",
                json.dumps(export_data, indent=2, default=str),
                "tool_history.json",
                "application/json"
            )
    
    # Main chat interface
    st.header("💬 Chat (Single Question Mode)")
    
    # Always show rules (no history to check)
    st.info("**Rules - Please Read:**")
    col1, col2 = st.columns(2)
    with col1:
        st.write("1. Be specific (e.g., ask for PB not just 'valuation')")
        st.write("2. Available: historical, forecast, analysis, stock data")
    with col2:
        st.write("3. Sectors: SOCB, Private_1, Private_2, Private_3")
        st.write("4. Each question is independent (no context saved)")
    
    # Chat input
    user_input = st.chat_input("Ask DucGPT")
    
    if user_input:
        # Add user message to display
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response
        with st.chat_message("assistant"):
            response_container = st.empty()
            
            # Get response with tool execution
            response = chat_with_ai(user_input)
            
            # Display response
            response_container.write(response)
        
        # NO conversation history saved - each query is independent
    
    # Tool execution history (in expander)
    if st.session_state.tool_executions:
        with st.expander(f"🔧 Tool Execution History ({len(st.session_state.tool_executions)} executions)"):
            for i, execution in enumerate(reversed(st.session_state.tool_executions[-10:])):
                st.write(f"**{execution['tool']}** - {execution['timestamp']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.code(json.dumps(execution['arguments'], indent=2), language="json")
                with col2:
                    if execution['result'].get('status') == 'success':
                        st.success("✅ Success")
                    else:
                        st.error(f"❌ {execution['result'].get('error', 'Failed')}")
                st.divider()


if __name__ == "__main__":
    main()