"""
Enhanced AI Chat with Chart Support
Interactive chat interface with financial data analysis and visualization capabilities
"""

import streamlit as st
import json
import os
import sys
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from tabs.enhanced_ai_assistant import EnhancedAIToolSystem
from utils.chart_utils import create_plotly_chart

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Enhanced AI Chat",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'tool_system' not in st.session_state:
    st.session_state.tool_system = EnhancedAIToolSystem()

if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []

if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None

if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-4-turbo-preview"

def execute_tool_and_handle_charts(tool_name: str, arguments: dict):
    """Execute a tool and handle any chart specifications in the result"""
    # Execute the tool
    result = st.session_state.tool_system.execute_tool(tool_name, arguments)
    
    # Check if this is a chart rendering tool
    if tool_name in ["render_chart", "create_financial_chart"] and result.get("status") == "success":
        if "chart_spec" in result:
            st.session_state.pending_charts.append(result["chart_spec"])
    
    return result

def chat_with_enhanced_ai_streaming(user_message: str):
    """Process user message with Enhanced AI and handle chart rendering with streaming"""
    if not st.session_state.openai_client:
        st.error("❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.")
        return
    
    # Clear pending charts from previous messages
    st.session_state.pending_charts = []
    
    # Get tool schemas
    tools = st.session_state.tool_system.get_openai_tools()
    
    # Prepare messages
    messages = [
        {
            "role": "system",
            "content": """You are a financial analysis assistant with access to comprehensive data tools.
            When users ask for visualizations or charts, use the render_chart tool to create them.
            Structure your data properly with x-axis labels and series data.
            Be concise in your responses and focus on providing insights with supporting visualizations."""
        },
        {"role": "user", "content": user_message}
    ]
    
    # Create containers for streaming
    response_container = st.empty()
    tool_status_container = st.container()
    
    accumulated_response = ""
    tool_calls_made = []
    max_rounds = 15
    rounds = 0
    
    # Main chat loop
    while rounds < max_rounds:
        rounds += 1
        
        try:
            # Call OpenAI with streaming
            stream = st.session_state.openai_client.chat.completions.create(
                model=st.session_state.selected_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True
            )
            
            # Process streaming response
            current_tool_calls = []
            assistant_content = ""
            is_tool_call = False
            
            for chunk in stream:
                delta = chunk.choices[0].delta
                
                # Check for tool calls
                if delta.tool_calls:
                    is_tool_call = True
                    for tool_call in delta.tool_calls:
                        # Accumulate tool call data
                        if len(current_tool_calls) <= tool_call.index:
                            current_tool_calls.append({
                                "id": "",
                                "function": {"name": "", "arguments": ""}
                            })
                        
                        if tool_call.id:
                            current_tool_calls[tool_call.index]["id"] = tool_call.id
                        if tool_call.function.name:
                            current_tool_calls[tool_call.index]["function"]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            current_tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
                
                # Check for content (non-tool response)
                if delta.content and not is_tool_call:
                    assistant_content += delta.content
                    accumulated_response += delta.content
                    # Stream the response to user
                    response_container.markdown(accumulated_response + "▌")
            
            # Remove cursor after streaming
            if assistant_content:
                response_container.markdown(accumulated_response)
            
            # Handle tool calls if any
            if current_tool_calls:
                # Execute tools
                tool_names = []
                for tool_call in current_tool_calls:
                    tool_name = tool_call['function']['name']
                    tool_calls_made.append(tool_name)
                    tool_names.append(tool_name)
                
                # Execute tools and collect results
                results = []
                for tool_call in current_tool_calls:
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'])
                    
                    # Execute tool and handle charts
                    result = execute_tool_and_handle_charts(function_name, function_args)
                    results.append(result)
                
                # Show minimal tool summary
                with tool_status_container:
                    for tool_name, result in zip(tool_names, results):
                        if result.get("status") == "success":
                            st.caption(f"✓ {tool_name}")
                        else:
                            st.caption(f"✗ {tool_name}: {result.get('error', 'Failed')[:50]}")
                
                # Add tool results to messages
                messages.append({
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"]
                        } for tc in current_tool_calls
                    ]
                })
                
                for tool_call, result in zip(current_tool_calls, results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, default=str)
                    })
                
                # Continue to next round for tool response
                continue
            else:
                # No tool calls, we have the final response
                if assistant_content:
                    # Update conversation history
                    st.session_state.conversation_history.append({"role": "user", "content": user_message})
                    st.session_state.conversation_history.append({"role": "assistant", "content": accumulated_response})
                    
                    # Render any pending charts
                    if st.session_state.pending_charts:
                        for chart_spec in st.session_state.pending_charts:
                            try:
                                fig = create_plotly_chart(chart_spec)
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error rendering chart: {str(e)}")
                        # Clear pending charts after rendering
                        st.session_state.pending_charts = []
                
                break
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            break
    
    if rounds >= max_rounds:
        st.warning(f"Analysis completed with {len(tool_calls_made)} tool calls.")

def main():
    st.title("🤖 Enhanced AI Chat")
    st.markdown("Ask questions about financial data and request visualizations")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model selection
        st.session_state.selected_model = st.selectbox(
            "AI Model:",
            options=["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
            index=0,
            help="Select the AI model for analysis"
        )
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            if st.session_state.tool_system:
                tools = st.session_state.tool_system.get_tool_list()
                
                # Group tools by category
                financial_tools = [t for t in tools if any(kw in t.lower() for kw in ['financial', 'valuation', 'company'])]
                chart_tools = [t for t in tools if 'chart' in t.lower()]
                other_tools = [t for t in tools if t not in financial_tools and t not in chart_tools]
                
                if financial_tools:
                    st.write("**Financial Analysis:**")
                    for tool in financial_tools:
                        st.write(f"• {tool}")
                
                if chart_tools:
                    st.write("**Visualization:**")
                    for tool in chart_tools:
                        st.write(f"• {tool}")
                
                if other_tools:
                    st.write("**Other Tools:**")
                    for tool in other_tools[:5]:  # Show first 5
                        st.write(f"• {tool}")
                    if len(other_tools) > 5:
                        st.write(f"  ...and {len(other_tools)-5} more")
        
        # Clear conversation
        if st.button("🗑️ Clear Conversation"):
            st.session_state.conversation_history = []
            st.session_state.pending_charts = []
            st.rerun()
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please create a `.env` file with your OpenAI API key:")
        st.code("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Example queries
    with st.expander("💡 Example Queries"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Financial Analysis:**
            - Show me VHM's revenue trend for the last 5 years
            - Compare EBITDA margins between VHM, DXG, and NVL
            - What are the financial forecasts for TCH from 2025 to 2028?
            - Analyze the profitability trends of real estate companies
            """)
        with col2:
            st.markdown("""
            **Visualizations:**
            - Create a chart showing quarterly revenue growth for VHM
            - Visualize P/E and P/B ratios for top real estate companies
            - Show me a bar chart comparing debt levels across companies
            - Plot the historical stock performance of banking sector
            """)
    
    # Display conversation history
    for message in st.session_state.conversation_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    user_input = st.chat_input("Ask about financial data or request charts...")
    
    if user_input:
        # Add user message to display
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response with streaming
        with st.chat_message("assistant"):
            chat_with_enhanced_ai_streaming(user_input)

if __name__ == "__main__":
    main()