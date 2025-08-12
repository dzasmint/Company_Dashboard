#%%
import streamlit as st
import pandas as pd


class AIDiscoveryTab:
    """AI Discovery tab for project extraction"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def render(self):
        """Render AI discovery interface"""
        st.header("AI Project Discovery")
        
        # Check if company is selected
        if not st.session_state.get('selected_company'):
            st.info("👈 Please select a company from the sidebar")
            return
        
        # Render sub-tabs for different AI discovery methods
        ai_tabs = st.tabs(["🤖 Claude Discovery", "🌐 Perplexity Discovery", "🔄 Merge Results", "📚 Discovery History"])
        
        with ai_tabs[0]:
            self.render_claude_discovery()
        
        with ai_tabs[1]:
            self.render_perplexity_discovery()
        
        with ai_tabs[2]:
            self.render_merge_results()
        
        with ai_tabs[3]:
            self.render_discovery_history()
    
    def render_claude_discovery(self):
        """Render Claude AI discovery section"""
        st.subheader("🤖 Claude AI Project Extraction")
        st.info("Upload financial statements or enter text for Claude to extract real estate project information")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Upload Financial Statements",
            type=['pdf', 'xlsx', 'xls', 'docx', 'txt'],
            help="Upload annual reports, financial statements, or investor presentations"
        )
        
        # Text input
        financial_text = st.text_area(
            "Or paste financial statement text:",
            height=200,
            placeholder="Paste text from financial statements, annual reports, or investor presentations..."
        )
        
        if st.button("🔍 Extract Projects with Claude"):
            if uploaded_file or financial_text:
                with st.spinner("Extracting project information..."):
                    # Delegate to parent's Claude extraction method
                    result = self.parent.extract_projects_with_claude(uploaded_file, financial_text)
                    
                    if result.get('success'):
                        st.success(f"✅ Extracted {len(result.get('projects', []))} projects")
                        
                        # Display extracted projects
                        projects = result.get('projects', [])
                        if projects:
                            st.dataframe(pd.DataFrame(projects), use_container_width=True)
                    else:
                        st.error(f"❌ {result.get('message', 'Extraction failed')}")
            else:
                st.warning("⚠️ Please upload a file or enter text to extract projects")
    
    def render_perplexity_discovery(self):
        """Render Perplexity AI discovery section"""
        st.subheader("🌐 Perplexity Web Research")
        st.info("Research additional projects using Perplexity's web search capabilities")
        
        selected_company = st.session_state.get('selected_company')
        
        if st.button("🌐 Research Additional Projects"):
            if selected_company:
                with st.spinner(f"Researching projects for {selected_company}..."):
                    # Delegate to parent's Perplexity research method
                    result = self.parent.research_additional_projects_with_perplexity(selected_company)
                    
                    if result.get('success'):
                        projects = result.get('projects', [])
                        st.success(f"✅ Found {len(projects)} additional projects")
                        
                        if projects:
                            st.dataframe(pd.DataFrame(projects), use_container_width=True)
                    else:
                        st.error(f"❌ {result.get('message', 'Research failed')}")
            else:
                st.warning("⚠️ Please select a company first")
    
    def render_merge_results(self):
        """Render merge results section"""
        st.subheader("🔄 Merge Discovery Results")
        st.info("Combine and deduplicate projects from different discovery methods")
        
        # Check for discovered projects in session state
        claude_projects = st.session_state.get('claude_projects', [])
        perplexity_projects = st.session_state.get('perplexity_projects', [])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Claude Projects", len(claude_projects))
        
        with col2:
            st.metric("Perplexity Projects", len(perplexity_projects))
        
        if claude_projects or perplexity_projects:
            if st.button("🔄 Merge All Projects"):
                with st.spinner("Merging and deduplicating projects..."):
                    # Delegate to parent's merge method
                    result = self.parent.merge_discovered_projects()
                    
                    if result.get('success'):
                        merged_projects = result.get('projects', [])
                        st.success(f"✅ Merged into {len(merged_projects)} unique projects")
                        
                        if merged_projects:
                            st.dataframe(pd.DataFrame(merged_projects), use_container_width=True)
                    else:
                        st.error(f"❌ {result.get('message', 'Merge failed')}")
        else:
            st.info("No discovered projects to merge. Use Claude or Perplexity discovery first.")
    
    def render_discovery_history(self):
        """Render discovery history section"""
        st.subheader("📚 Discovery Session History")
        st.info("View previous AI discovery sessions and their results")
        
        selected_company = st.session_state.get('selected_company')
        
        if selected_company:
            # Delegate to parent to load discovery history
            history = self.parent.load_discovery_history(selected_company)
            
            if history:
                for i, session in enumerate(history):
                    with st.expander(f"Session {i+1} - {session.get('timestamp', 'Unknown time')}", expanded=False):
                        st.json(session)
            else:
                st.info("No previous discovery sessions found")
        else:
            st.info("👈 Select a company to view discovery history")