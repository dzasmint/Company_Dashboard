#%%
import streamlit as st


class GodAIAssistantTab:
    """God AI Assistant tab for intelligent queries"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def render(self):
        """Render God AI Assistant interface"""
        st.header("🤖 God AI Assistant")
        st.markdown("Ask intelligent questions about your real estate financial model, projects, and forecasts")
        
        # Check if company is selected
        selected_company = st.session_state.get('selected_company')
        if not selected_company:
            st.info("👈 Please select a company from the sidebar to use the AI assistant")
            return
        
        # Initialize chat history
        if 'god_ai_chat_history' not in st.session_state:
            st.session_state.god_ai_chat_history = []
        
        # Display chat history
        self._display_chat_history()
        
        # Chat input
        self._render_chat_interface(selected_company)
        
        # Example queries
        self._render_example_queries()
    
    def _display_chat_history(self):
        """Display chat history"""
        if st.session_state.god_ai_chat_history:
            st.subheader("💬 Conversation History")
            
            for i, message in enumerate(st.session_state.god_ai_chat_history):
                with st.container():
                    if message['role'] == 'user':
                        st.markdown(f"**You:** {message['content']}")
                    else:
                        st.markdown(f"**AI:** {message['content']}")
                    st.markdown("---")
        
        # Clear history button
        if st.session_state.god_ai_chat_history:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.god_ai_chat_history = []
                st.rerun()
    
    def _render_chat_interface(self, selected_company):
        """Render chat input interface"""
        st.subheader("💭 Ask the AI Assistant")
        
        # Chat input
        user_question = st.text_area(
            "Your question:",
            height=100,
            placeholder="Ask about projects, forecasts, margins, growth rates, or any financial analysis...",
            key="god_ai_input"
        )
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button("🚀 Send", type="primary"):
                if user_question.strip():
                    self._process_user_question(user_question, selected_company)
                else:
                    st.warning("Please enter a question")
        
        with col2:
            # Voice input placeholder (if implemented)
            st.button("🎤 Voice Input", disabled=True, help="Voice input coming soon")
    
    def _process_user_question(self, question, selected_company):
        """Process user question with AI assistant"""
        # Add user message to history
        st.session_state.god_ai_chat_history.append({
            'role': 'user',
            'content': question
        })
        
        with st.spinner("🤖 AI is thinking..."):
            try:
                # Use parent's God AI assistant
                if hasattr(self.parent, 'god_ai'):
                    response = self.parent.god_ai.process_query(
                        question, 
                        selected_company,
                        session_state=st.session_state
                    )
                    
                    # Add AI response to history
                    st.session_state.god_ai_chat_history.append({
                        'role': 'assistant',
                        'content': response
                    })
                    
                    # Clear input
                    st.session_state.god_ai_input = ""
                    
                    # Rerun to update display
                    st.rerun()
                    
                else:
                    st.error("AI Assistant not available")
                    
            except Exception as e:
                st.error(f"Error processing question: {str(e)}")
                
                # Add error message to history
                st.session_state.god_ai_chat_history.append({
                    'role': 'assistant',
                    'content': f"Sorry, I encountered an error: {str(e)}"
                })
    
    def _render_example_queries(self):
        """Render example queries section"""
        st.subheader("💡 Example Questions")
        
        examples = [
            "What is the total revenue forecast for 2025?",
            "Which project has the highest gross margin?",
            "What's the CAGR of our real estate revenue?",
            "Compare gross margins across all projects",
            "What are the key risks in our project pipeline?",
            "When will Project ABC start generating revenue?",
            "What's our debt capacity for new land acquisitions?",
            "How does our RNAV compare to market cap?",
            "What's the IRR of our top 3 projects?",
            "Show me the sales velocity by project"
        ]
        
        # Create columns for examples
        cols = st.columns(2)
        
        for i, example in enumerate(examples):
            col = cols[i % 2]
            with col:
                if st.button(f"📝 {example}", key=f"example_{i}"):
                    # Auto-fill the text area
                    st.session_state.god_ai_input = example
                    st.rerun()
        
        # Advanced features section
        with st.expander("🔧 Advanced Features", expanded=False):
            st.markdown("""
            **The AI Assistant can help with:**
            
            📊 **Financial Analysis:**
            - Revenue growth calculations
            - Margin analysis by project/segment
            - CAGR and trend analysis
            - Profitability comparisons
            
            🏗️ **Project Intelligence:**
            - Project ranking by metrics
            - Timeline and milestone tracking
            - Risk assessment
            - Performance benchmarking
            
            💰 **Valuation & Investment:**
            - RNAV calculations
            - IRR and NPV analysis
            - Capital allocation suggestions
            - Market comparison insights
            
            📈 **Forecasting:**
            - Revenue projections
            - Scenario modeling
            - Sensitivity analysis
            - What-if scenarios
            
            **Tips for better results:**
            - Be specific about metrics and time periods
            - Ask for comparisons between projects
            - Request explanations of calculations
            - Use follow-up questions for deeper insights
            """)
    
    def render_forecast_analysis_display(self, analysis_result):
        """Display forecast analysis results from God AI"""
        if not analysis_result:
            return
        
        st.subheader("📊 Forecast Analysis Results")
        
        # Display in expandable sections
        for section_title, content in analysis_result.items():
            if content and section_title != 'ticker':
                with st.expander(f"📈 {section_title.replace('_', ' ').title()}", expanded=True):
                    if isinstance(content, dict):
                        for key, value in content.items():
                            st.write(f"**{key}:** {value}")
                    elif isinstance(content, list):
                        for item in content:
                            st.write(f"• {item}")
                    else:
                        st.write(content)