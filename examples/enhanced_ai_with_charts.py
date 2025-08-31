"""
Example: How to integrate Enhanced AI with chart rendering
This shows how to use the Enhanced AI Assistant with proper chart handling
"""

import streamlit as st
import json
from tabs.enhanced_ai_assistant import EnhancedAIToolSystem
from utils.chart_utils import create_plotly_chart, handle_tool_charts
from openai import OpenAI
import os

# Initialize session state
if 'tool_system' not in st.session_state:
    st.session_state.tool_system = EnhancedAIToolSystem()

if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []

if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None


def execute_tool_and_handle_charts(tool_name: str, arguments: dict):
    """
    Execute a tool and handle any chart specifications in the result
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments for the tool
    
    Returns:
        Tool execution result
    """
    # Execute the tool
    result = st.session_state.tool_system.execute_tool(tool_name, arguments)
    
    # Check if this is a chart rendering tool
    if tool_name in ["render_chart", "create_financial_chart"] and result.get("status") == "success":
        if "chart_spec" in result:
            st.session_state.pending_charts.append(result["chart_spec"])
    
    return result


def chat_with_enhanced_ai(user_message: str):
    """
    Process user message with Enhanced AI and handle chart rendering
    
    Args:
        user_message: User's input message
    """
    if not st.session_state.openai_client:
        st.error("OpenAI API key not configured")
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
            When users ask for visualizations, use the render_chart tool to create them.
            Structure your data properly with x-axis labels and series data."""
        },
        {"role": "user", "content": user_message}
    ]
    
    # Container for response
    response_container = st.empty()
    accumulated_response = ""
    
    # Call OpenAI with tools
    max_rounds = 10
    rounds = 0
    
    while rounds < max_rounds:
        rounds += 1
        
        try:
            # Call OpenAI
            response = st.session_state.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            
            # Handle tool calls
            if assistant_message.tool_calls:
                # Add assistant message to history
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]
                })
                
                # Execute tools
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute tool and handle charts
                    result = execute_tool_and_handle_charts(function_name, function_args)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str)
                    })
                
                # Continue to next round
                continue
            
            # Display final response
            if assistant_message.content:
                accumulated_response = assistant_message.content
                response_container.markdown(accumulated_response)
            
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
            st.error(f"Error: {str(e)}")
            break
    
    if rounds >= max_rounds:
        st.warning("Analysis completed (max iterations reached)")


def main():
    st.title("Enhanced AI with Chart Support")
    st.markdown("Ask questions about financial data and request visualizations")
    
    # Example queries
    with st.expander("Example Queries"):
        st.markdown("""
        - Show me VHM's revenue trend for the last 5 years in a chart
        - Compare EBITDA margins between VHM, DXG, and NVL
        - Create a chart showing quarterly revenue growth for VHM
        - Visualize the valuation metrics (P/E and P/B) for real estate companies
        """)
    
    # Chat input
    user_input = st.chat_input("Ask about financial data or request charts...")
    
    if user_input:
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response with charts
        with st.chat_message("assistant"):
            chat_with_enhanced_ai(user_input)


if __name__ == "__main__":
    main()