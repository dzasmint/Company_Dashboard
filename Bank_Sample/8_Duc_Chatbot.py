"""
MCP Model - AI Banking Analysis Assistant
Streamlit interface for OpenAI-powered banking analysis with tool execution
"""

import streamlit as st

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Duc Chatbot",
    layout="wide"
)

import pandas as pd
import json
import os
import sys
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import threading
import plotly.graph_objects as go
import plotly.express as px

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import and apply Google Fonts
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
apply_google_font()
apply_sidebar_style()

# Load environment variables
load_dotenv()

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'facts_memory' not in st.session_state:
    st.session_state.facts_memory = []
if 'tool_cache' not in st.session_state:
    st.session_state.tool_cache = {}
if 'tool_executions' not in st.session_state:
    st.session_state.tool_executions = []
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-5"
if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []

# Initialize tool system FIRST (before OpenAI client which might use it)
# Force reload to get latest schema changes
if 'tool_system' in st.session_state:
    del st.session_state.tool_system

# Clear module cache to ensure fresh import
import importlib
if 'utilities.Banking_MCP' in sys.modules:
    importlib.reload(sys.modules['utilities.Banking_MCP'])

try:
    from utilities.Banking_MCP import get_tool_system
    # Create fresh instance (don't use cached singleton)
    from utilities.Banking_MCP import BankingToolSystem
    st.session_state.tool_system = BankingToolSystem()
    st.session_state.tool_system_error = None
except Exception as e:
    st.session_state.tool_system = None
    st.session_state.tool_system_error = str(e)

# Initialize OpenAI client
if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None


def execute_tool_call_sync(tool_name: str, arguments: Dict, tool_system) -> Dict:
    """Execute a tool synchronously without accessing session state"""
    # Create cache key
    cache_key = f"{tool_name}_{json.dumps(arguments, sort_keys=True)}"
    
    # Execute the tool
    result = tool_system.execute_tool(tool_name, arguments)
    
    return result, cache_key


async def execute_tool_async(tool_name: str, arguments: Dict, tool_system) -> Dict:
    """Async wrapper for tool execution"""
    loop = asyncio.get_event_loop()
    # Run in executor without accessing session state
    result, cache_key = await loop.run_in_executor(
        None, 
        execute_tool_call_sync, 
        tool_name, 
        arguments,
        tool_system
    )
    return result


async def execute_parallel_tools(tool_calls: List[Dict], tool_system) -> List[Dict]:
    """Execute multiple tools in parallel"""
    tasks = []
    for tool_call in tool_calls:
        function_name = tool_call['function']['name']
        function_args = json.loads(tool_call['function']['arguments'])
        tasks.append(execute_tool_async(function_name, function_args, tool_system))
    
    results = await asyncio.gather(*tasks)
    return results


def create_plotly_chart(chart_spec: Dict) -> go.Figure:
    """Create a Plotly chart from the specification"""
    chart_type = chart_spec.get("chart_type", "line")
    data = chart_spec.get("data", {})
    title = chart_spec.get("title", "")
    x_label = chart_spec.get("x_label", "")
    y_label = chart_spec.get("y_label", "")
    y_format = chart_spec.get("y_format", "number")
    
    # Define custom color palette - #398278 (teal) and #cc7c5e (terracotta)
    custom_colors = ['#398278', '#cc7c5e', '#5A8A7F', '#e6a085', '#2D5E52', '#b5694f']
    
    # Create figure
    fig = go.Figure()
    
    # Add data series
    x_values = data.get("x", [])
    for idx, series in enumerate(data.get("series", [])):
        name = series.get("name", "Series")
        y_values = series.get("y", [])
        color = custom_colors[idx % len(custom_colors)]
        
        if chart_type == "line":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines+markers',
                name=name,
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color)
            ))
        elif chart_type == "bar":
            fig.add_trace(go.Bar(
                x=x_values,
                y=y_values,
                name=name,
                marker=dict(color=color)
            ))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='markers',
                name=name,
                marker=dict(size=8, color=color)
            ))
        elif chart_type == "area":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines',
                name=name,
                fill='tozeroy',
                line=dict(width=2, color=color),
                fillcolor=color
            ))
    
    # Format y-axis based on type
    yaxis_config = {"title": y_label}
    if y_format == "percent":
        yaxis_config["tickformat"] = ".1%"
    elif y_format == "currency":
        yaxis_config["tickformat"] = "$,.0f"
    
    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis=yaxis_config,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50),
        height=400
    )
    
    return fig


def compress_assistant_response(response: str, tool_calls_made: List[str], user_message: str) -> Dict:
    """Compress assistant response to structured data to save tokens"""
    import re
    
    compressed = {
        "tickers": [],
        "periods": [],
        "metrics": {},
        "tools": tool_calls_made[:5],
        "summary": ""
    }
    
    # Extract tickers
    tickers = re.findall(r'\b[A-Z]{3,4}\b', response + " " + user_message)
    compressed["tickers"] = list(set(tickers))[:10]
    
    # Extract periods
    quarters = re.findall(r'\b\d{4}-Q\d\b|\bQ\d\s*\d{4}\b|\b20\d{2}\b', response)
    compressed["periods"] = list(set(quarters))[:5]
    
    # Extract key metrics
    roe_match = re.search(r'ROE[\s]+([0-9.]+)%', response)
    if roe_match:
        compressed["metrics"]["ROE"] = roe_match.group(1) + "%"
    
    # Create summary
    if compressed["tickers"] and compressed["periods"]:
        compressed["summary"] = f"{compressed['tickers'][0]} {compressed['periods'][0]}"
    elif compressed["tickers"]:
        compressed["summary"] = f"Analyzed {', '.join(compressed['tickers'][:2])}"
    else:
        compressed["summary"] = "Banking analysis"
    
    return compressed


def reconstruct_context(compressed_history: List[Dict]) -> str:
    """Reconstruct concise context from compressed history"""
    if not compressed_history:
        return ""
    
    context_parts = []
    
    for item in compressed_history[-3:]:  # Last 3 items
        if item.get("role") == "user":
            content = item.get("content", "")
            if len(content) > 100:
                context_parts.append(f"User asked: {content[:100]}...")
            else:
                context_parts.append(f"User asked: {content}")
        elif item.get("role") == "assistant_compressed":
            data = item.get("data", {})
            parts = []
            if data.get("tickers"):
                parts.append(f"Discussed {', '.join(data['tickers'][:3])}")
            if data.get("periods"):
                parts.append(f"for {', '.join(data['periods'][:2])}")
            if parts:
                context_parts.append(" ".join(parts))
    
    return " | ".join(context_parts) if context_parts else ""


def chat_with_ai_streaming(user_message: str):
    """
    Enhanced chat function with streaming responses and parallel tool execution
    """
    if not st.session_state.openai_client:
        st.error("❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.")
        return
    
    if 'tool_system' not in st.session_state or not st.session_state.tool_system:
        st.error("❌ Tool system not initialized. Please refresh the page.")
        return
    
    # Clear any pending charts from previous messages
    st.session_state.pending_charts = []
    
    # Get tool system reference before async operations
    tool_system = st.session_state.tool_system
    
    # Prepare messages
    messages = []
    context_str = reconstruct_context(st.session_state.conversation_history)
    
    system_content = """You are a banking analyst assistant. Use tools to get data, then provide CONCISE analysis.
IMPORTANT: ALWAYS call get_data_availability() first when user asks for 'latest', 'recent', 'current' data.
Tickers must be arrays: ["VCB"] for single, ["VCB", "ACB"] for multiple."""
    
    if context_str:
        system_content += f"\n\nPrevious context: {context_str}"
    
    messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas
    tools = tool_system.get_openai_tools()
    
    # Create containers for streaming
    typing_container = st.empty()  # Separate container for "Duc is typing"
    response_container = st.empty()
    tool_status_container = st.container()
    
    accumulated_response = ""
    tool_call_count = 0
    tool_calls_made = []
    max_rounds = 20
    rounds = 0
    
    # Show initial typing indicator with custom styling
    typing_container.markdown(
        '<div style="background-color: #DDDDD6; padding: 8px 16px; border-radius: 8px; display: inline-block; font-size: 14px; color: #333;">Duc is typing...</div>',
        unsafe_allow_html=True
    )
    
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
                    # Clear typing indicator when actual content starts streaming
                    if not assistant_content:  # First content chunk
                        typing_container.empty()
                    assistant_content += delta.content
                    accumulated_response += delta.content
                    # Stream the response to user
                    response_container.markdown(accumulated_response + "▌")
            
            # Remove cursor after streaming
            if assistant_content:
                response_container.markdown(accumulated_response)
            
            # Handle tool calls if any
            if current_tool_calls:
                # Keep the typing indicator visible during tool execution
                # (it's already shown at the start of the loop)
                
                # Collect tool names for minimal display
                tool_names = []
                for i, tool_call in enumerate(current_tool_calls):
                    tool_name = tool_call['function']['name']
                    tool_calls_made.append(tool_name)
                    tool_names.append(tool_name)
                    tool_call_count += 1
                
                # Execute tools in parallel (background)
                start_time = time.time()
                
                # Run async execution in background
                try:
                    # Create new event loop for async execution
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    # Pass tool_system to avoid accessing session state from async
                    results = loop.run_until_complete(
                        execute_parallel_tools(current_tool_calls, tool_system)
                    )
                finally:
                    loop.close()
                
                execution_time = time.time() - start_time
                
                # Update cache and execution log in main thread
                for tool_call, result in zip(current_tool_calls, results):
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'])
                    cache_key = f"{function_name}_{json.dumps(function_args, sort_keys=True)}"
                    
                    # Check if this is a chart rendering tool
                    if function_name == "render_chart" and result.get("status") == "success":
                        if "chart_spec" in result:
                            st.session_state.pending_charts.append(result["chart_spec"])
                    
                    # Update cache in session state (main thread)
                    st.session_state.tool_cache[cache_key] = {
                        'result': result,
                        'timestamp': datetime.now()
                    }
                    
                    # Log execution
                    st.session_state.tool_executions.append({
                        "tool": function_name,
                        "arguments": function_args,
                        "timestamp": datetime.now().isoformat(),
                        "result": result
                    })
                
                # Don't clear typing here - let it stay until response starts
                # The typing indicator will be cleared when actual content starts streaming
                
                # Show minimal tool summary (small captions below)
                with tool_status_container:
                    # Show one line per tool with status icon
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
                    compressed_response = compress_assistant_response(accumulated_response, tool_calls_made, user_message)
                    st.session_state.conversation_history.append({
                        "role": "assistant_compressed",
                        "data": compressed_response
                    })
                    
                    # Keep only last 6 messages
                    if len(st.session_state.conversation_history) > 6:
                        st.session_state.conversation_history = st.session_state.conversation_history[-6:]
                    
                    # Add minimal tool summary if tools were used
                    if tool_call_count > 0:
                        st.caption(f"_Used {tool_call_count} tool{'s' if tool_call_count > 1 else ''}_")
                    
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
        st.warning(f"Analysis completed with {tool_call_count} tool calls. The query may be too complex.")


def main():
    st.title("Duc - AI Chatbot")
    st.markdown("This chatbot can draw charts, provide analysis and fetch banking data")
    
    # Add custom CSS for iPhone-style message bubbles
    st.markdown("""
    <style>
    /* User message styling - iPhone blue */
    div[data-testid="stChatMessageContent-user"] {
        background-color: #619BF7;
        color: white;
        border-radius: 18px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 70%;
        margin-left: auto;
        margin-right: 0;
    }
    
    /* Assistant message styling - iPhone gray */
    div[data-testid="stChatMessageContent-assistant"] {
        background-color: #F1F1F2;
        color: black;
        border-radius: 18px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 70%;
        margin-left: 0;
        margin-right: auto;
    }
    
    /* Adjust message container alignment */
    div[data-testid="stChatMessage-user"] {
        justify-content: flex-end;
    }
    
    div[data-testid="stChatMessage-assistant"] {
        justify-content: flex-start;
    }
    
    /* Hide default avatars for cleaner look */
    div[data-testid="stChatMessage-user"] img,
    div[data-testid="stChatMessage-assistant"] img {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please create a `.env` file with your OpenAI API key:")
        st.code("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Check tool system
    if 'tool_system' not in st.session_state or not st.session_state.tool_system:
        st.error("⚠️ Tool system not initialized!")
        if 'tool_system_error' in st.session_state and st.session_state.tool_system_error:
            st.error(f"Error details: {st.session_state.tool_system_error}")
        st.info("Please refresh the page or check that the Banking_MCP module is properly installed.")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            if 'tool_system' in st.session_state and st.session_state.tool_system:
                tools = st.session_state.tool_system.get_tool_list()
                for tool in tools:
                    st.write(f"• {tool}")
            else:
                st.write("Tool system not initialized")
        
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
    
    # Model selection
    col1, col2, col3 = st.columns([2, 3, 2])
    with col1:
        st.session_state.selected_model = st.selectbox(
            "Select AI Model:",
            options=["gpt-5", "gpt-5-mini"],
            index=0 if st.session_state.selected_model == "gpt-5" else 1,
            help="GPT-5: More capable, better reasoning | GPT-5-mini: Faster, more cost-effective"
        )
    
    # Show conversation info
    st.info("**Rules for your questions**")
    col1, col2 = st.columns(2)
    with col1:
        st.write("1. Be specific (e.g., ask for PB not just 'valuation', or PBT, not just 'earnings')")
        st.write("2. Available: historical, forecast, analysis, stock data, charting")
    with col2:
        st.write("3. Sectors: SOCB, Private_1, Private_2, Private_3")
        st.write("4. Short conversation is supported")
    
    # Chat input
    user_input = st.chat_input("Ask Duc something ...")
    
    if user_input:
        # Add user message to display
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response with streaming
        with st.chat_message("assistant"):
            chat_with_ai_streaming(user_input)
    
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