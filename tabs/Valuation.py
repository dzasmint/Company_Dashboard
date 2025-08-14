import streamlit as st
import pandas as pd


class ValuationTab:
    """Valuation Analysis Tab"""
    
    def __init__(self):
        pass
    
    def render(self):
        """Render simplified valuation analysis based on RNAV and revenue forecasts"""
        st.header("Valuation Analysis")
        
        # RNAV Valuation
        st.subheader("RNAV Valuation")
        
        total_rnav = 0  # Initialize total_rnav
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            if 'rnav_value' in st.session_state.project_data.columns:
                total_rnav = st.session_state.project_data['rnav_value'].sum()
                st.metric("Total RNAV", f"{total_rnav/1e9:,.0f}B VND")
                
                # Show project-level RNAV breakdown
                project_rnav = st.session_state.project_data[['project_name', 'rnav_value']].copy()
                project_rnav['rnav_value'] = project_rnav['rnav_value'] / 1e9  # Convert to billions
                project_rnav = project_rnav.sort_values('rnav_value', ascending=False)
                
                st.dataframe(
                    project_rnav.style.format({'rnav_value': '{:,.0f}B'}),
                    use_container_width=True
                )
            else:
                st.info("RNAV values not available in project data")
        else:
            st.info("Sync project data to calculate RNAV")