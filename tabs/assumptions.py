#%%
import streamlit as st
import pandas as pd
import numpy as np


class AssumptionsTab:
    """Assumptions interface tab with optimized data handling"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def render(self):
        """Render enhanced assumptions interface with business segment support"""
        st.header("Model Assumptions")
        
        # Import MongoDB utilities
        from utils.mongodb_utils import get_company_assumptions, save_company_assumptions
        
        # Get ticker from sidebar selection
        selected_ticker = st.session_state.get('selected_company', None)
        
        if not selected_ticker:
            st.info("Please select a company from the sidebar to manage assumptions")
            return
        
        st.markdown(f"Managing assumptions for **{selected_ticker}**")
        
        # Add helper text
        self._render_help_section()
        
        # Initialize and load assumptions
        assumptions_df = self._load_assumptions(selected_ticker)
        
        # Display editable table
        self._render_assumptions_editor(selected_ticker, assumptions_df)
    
    def _render_help_section(self):
        """Render help section for business segments"""
        with st.expander("📚 How to Define Business Segments", expanded=False):
            st.markdown("""
            **Business Segment Structure:**
            - Each business segment should have 3 key assumptions:
              1. **Revenue Growth** - Annual growth rate (%)
              2. **Gross Margin** - Gross profit margin (%)
              3. **SG&A % of Revenue** - Selling, General & Admin as % of revenue
            
            **Example for Brokerage segment:**
            - Category: `Business Segment`, Type: `Revenue Growth`, Item: `Brokerage`, Value: `15`, Unit: `%`
            - Category: `Business Segment`, Type: `Gross Margin`, Item: `Brokerage`, Value: `60`, Unit: `%`
            - Category: `Business Segment`, Type: `SG&A % of Revenue`, Item: `Brokerage`, Value: `25`, Unit: `%`
            
            **How to use:**
            - **Category**: Select "Business Segment" for revenue stream assumptions
            - **Type**: Choose the metric type (Revenue Growth, Gross Margin, or SG&A % of Revenue)
            - **Item**: Enter the business segment name (e.g., "Brokerage", "Property Management")
            - **Value**: Enter the numeric value
            - **Unit**: Select the appropriate unit (usually "%")
            
            **Note:** Use consistent segment names across all metrics for proper grouping
            """)
    
    def _load_assumptions(self, selected_ticker):
        """Load assumptions with vectorized operations"""
        from utils.mongodb_utils import get_company_assumptions
        
        assumptions_key = f"editable_assumptions_{selected_ticker}"
        
        # Initialize or load assumptions data
        if assumptions_key not in st.session_state or st.session_state.get('refresh_assumptions', False):
            # Load from MongoDB
            company_assumptions = get_company_assumptions(selected_ticker)
            
            # Build assumptions data using vectorized operations
            assumptions_data = self._build_assumptions_data(company_assumptions)
            
            # Store in session state
            st.session_state[assumptions_key] = pd.DataFrame(assumptions_data)
            st.session_state.refresh_assumptions = False
        
        # Get current assumptions DataFrame
        assumptions_df = st.session_state[assumptions_key]
        if not isinstance(assumptions_df, pd.DataFrame):
            assumptions_df = pd.DataFrame(assumptions_df)
        
        return assumptions_df
    
    def _build_assumptions_data(self, company_assumptions):
        """Build assumptions data structure with vectorized operations"""
        assumptions_data = []
        
        # Load standard financial assumptions
        financial_assumptions = [
            ("WACC", company_assumptions.get('wacc', 0.12) * 100),
            ("Debt Financing %", company_assumptions.get('debt_financing_pct', 0.30) * 100),
            ("Tax Rate", company_assumptions.get('tax_rate', 0.20) * 100)
        ]
        
        for item, value in financial_assumptions:
            assumptions_data.append({
                "Category": "Financial",
                "Type": "N/A",
                "Item": item,
                "Value": value,
                "Unit": "%"
            })
        
        # Process business segments
        revenue_streams = company_assumptions.get('revenue_streams', [])
        segment_data = self._process_revenue_streams(revenue_streams)
        assumptions_data.extend(segment_data)
        
        # Load custom assumptions
        custom_assumptions = company_assumptions.get('custom_assumptions', [])
        for custom in custom_assumptions:
            assumptions_data.append({
                "Category": custom.get('category', 'Other'),
                "Type": custom.get('type', 'N/A'),
                "Item": custom.get('item', 'Custom'),
                "Value": custom.get('value', 0),
                "Unit": custom.get('unit', '%')
            })
        
        # Use defaults if empty
        if not assumptions_data:
            assumptions_data = self._get_default_assumptions()
        
        return assumptions_data
    
    def _process_revenue_streams(self, revenue_streams):
        """Process revenue streams with vectorized operations"""
        segment_data = []
        
        # Define metric mappings
        metrics = [
            ('revenue_growth', 'Revenue Growth'),
            ('gross_margin', 'Gross Margin'),
            ('sga_percentage', 'SG&A % of Revenue')
        ]
        
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', '')
            if segment_name:
                for metric_key, metric_type in metrics:
                    if metric_key in stream:
                        segment_data.append({
                            "Category": "Business Segment",
                            "Type": metric_type,
                            "Item": segment_name,
                            "Value": stream[metric_key] * 100,  # Convert to percentage
                            "Unit": "%"
                        })
        
        return segment_data
    
    def _get_default_assumptions(self):
        """Get default assumptions if none exist"""
        return [
            {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": 12.0, "Unit": "%"},
            {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": 30.0, "Unit": "%"},
            {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": 20.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Brokerage", "Value": 15.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Brokerage", "Value": 60.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Brokerage", "Value": 25.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Property Management", "Value": 20.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Property Management", "Value": 45.0, "Unit": "%"},
            {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Property Management", "Value": 30.0, "Unit": "%"}
        ]
    
    def _render_assumptions_editor(self, selected_ticker, assumptions_df):
        """Render the assumptions editor with form wrapper"""
        st.subheader("📊 Assumptions Table")
        st.info("💡 **How to use:** Click any cell to edit | Use '+' button to add rows | Select row(s) and press Delete/Backspace to remove | Click 'Apply Changes' to save edits")
        
        editor_key = f"assumptions_editor_{selected_ticker}_v2"
        
        # Use a form to batch updates and prevent double-entry issues
        with st.form(key=f"assumptions_form_{selected_ticker}"):
            # Create DataFrame with proper handling
            if not assumptions_df.empty:
                # Ensure all required columns exist
                if 'Type' not in assumptions_df.columns:
                    assumptions_df['Type'] = 'N/A'
                
                # Use Streamlit's data editor
                edited_df = st.data_editor(
                    assumptions_df,
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config=self._get_column_config(),
                    column_order=["Category", "Type", "Item", "Value", "Unit"],
                    key=editor_key
                )
            else:
                # Show empty data editor
                st.info("No assumptions defined. Click 'Load Defaults' below or use the table to add new assumptions.")
                empty_df = pd.DataFrame(columns=["Category", "Type", "Item", "Value", "Unit"])
                edited_df = st.data_editor(
                    empty_df,
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config=self._get_column_config(),
                    key=editor_key
                )
            
            # Form buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                apply_changes = st.form_submit_button("💾 Apply Changes", type="primary")
            
            with col2:
                load_defaults = st.form_submit_button("🔄 Load Defaults")
            
            with col3:
                clear_all = st.form_submit_button("🗑️ Clear All")
        
        # Handle form submissions
        self._handle_form_submissions(
            selected_ticker, edited_df, apply_changes, load_defaults, clear_all
        )
        
        # Display business segments summary
        self._display_segments_summary(assumptions_df)
    
    def _get_column_config(self):
        """Get column configuration for data editor"""
        return {
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Business Segment", "Financial", "Operating", "Other"],
                required=True,
                default="Business Segment",
                width="medium"
            ),
            "Type": st.column_config.SelectboxColumn(
                "Type",
                options=["Revenue Growth", "Gross Margin", "SG&A % of Revenue", "N/A"],
                required=True,
                default="Revenue Growth",
                help="Select metric type for business segments",
                width="medium"
            ),
            "Item": st.column_config.TextColumn(
                "Item",
                required=True,
                default="New Segment",
                help="Enter business segment name or assumption item",
                width="large"
            ),
            "Value": st.column_config.NumberColumn(
                "Value",
                min_value=0,
                max_value=1000,
                step=0.1,
                format="%.2f",
                default=10.0,
                width="small"
            ),
            "Unit": st.column_config.SelectboxColumn(
                "Unit",
                options=["%", "x", "days", "years", "B VND"],
                required=True,
                default="%",
                width="small"
            )
        }
    
    def _handle_form_submissions(self, selected_ticker, edited_df, apply_changes, load_defaults, clear_all):
        """Handle form button submissions"""
        assumptions_key = f"editable_assumptions_{selected_ticker}"
        
        if apply_changes:
            try:
                if not edited_df.empty:
                    # Update session state
                    st.session_state[assumptions_key] = edited_df
                    
                    # Save to MongoDB
                    result = self._save_assumptions_to_mongodb(selected_ticker, edited_df)
                    
                    if result['success']:
                        st.success("✅ Assumptions saved successfully!")
                        st.session_state.refresh_assumptions = True
                    else:
                        st.error(f"❌ {result['message']}")
                else:
                    st.warning("⚠️ No data to save")
            except Exception as e:
                st.error(f"❌ Error applying changes: {str(e)}")
        
        elif load_defaults:
            # Load default assumptions
            default_data = self._get_default_assumptions()
            st.session_state[assumptions_key] = pd.DataFrame(default_data)
            st.success("✅ Default assumptions loaded")
            st.rerun()
        
        elif clear_all:
            # Clear all assumptions
            st.session_state[assumptions_key] = pd.DataFrame(columns=["Category", "Type", "Item", "Value", "Unit"])
            st.success("✅ All assumptions cleared")
            st.rerun()
    
    def _save_assumptions_to_mongodb(self, selected_ticker, edited_df):
        """Save assumptions to MongoDB with vectorized processing"""
        from utils.mongodb_utils import save_company_assumptions
        
        try:
            # Process business segments with vectorized operations
            revenue_streams = self._extract_revenue_streams(edited_df)
            
            # Extract financial assumptions
            financial_data = self._extract_financial_assumptions(edited_df)
            
            # Extract custom assumptions
            custom_assumptions = self._extract_custom_assumptions(edited_df)
            
            # Prepare data for MongoDB
            assumptions_data = {
                'wacc': financial_data.get('wacc', 0.12),
                'debt_financing_pct': financial_data.get('debt_financing_pct', 0.30),
                'tax_rate': financial_data.get('tax_rate', 0.20),
                'revenue_streams': revenue_streams,
                'custom_assumptions': custom_assumptions
            }
            
            # Save to MongoDB
            return save_company_assumptions(selected_ticker, assumptions_data)
            
        except Exception as e:
            return {"success": False, "message": f"Error processing assumptions: {str(e)}"}
    
    def _extract_revenue_streams(self, edited_df):
        """Extract revenue streams with vectorized operations"""
        # Filter business segment rows
        business_segments = edited_df[edited_df['Category'] == 'Business Segment'].copy()
        
        if business_segments.empty:
            return []
        
        # Group by segment name (Item column)
        revenue_streams = []
        segments_grouped = business_segments.groupby('Item')
        
        for segment_name, group in segments_grouped:
            stream_data = {'segment_name': segment_name}
            
            # Vectorized metric extraction
            for _, row in group.iterrows():
                metric_type = row['Type']
                value = row['Value'] / 100  # Convert from percentage to decimal
                
                if metric_type == 'Revenue Growth':
                    stream_data['revenue_growth'] = value
                elif metric_type == 'Gross Margin':
                    stream_data['gross_margin'] = value
                elif metric_type == 'SG&A % of Revenue':
                    stream_data['sga_percentage'] = value
            
            revenue_streams.append(stream_data)
        
        return revenue_streams
    
    def _extract_financial_assumptions(self, edited_df):
        """Extract financial assumptions with vectorized operations"""
        financial_rows = edited_df[edited_df['Category'] == 'Financial'].copy()
        
        financial_data = {}
        
        if not financial_rows.empty:
            # Create mapping for quick lookup
            financial_map = dict(zip(financial_rows['Item'], financial_rows['Value']))
            
            # Extract values with defaults
            if 'WACC' in financial_map:
                financial_data['wacc'] = financial_map['WACC'] / 100
            if 'Debt Financing %' in financial_map:
                financial_data['debt_financing_pct'] = financial_map['Debt Financing %'] / 100
            if 'Tax Rate' in financial_map:
                financial_data['tax_rate'] = financial_map['Tax Rate'] / 100
        
        return financial_data
    
    def _extract_custom_assumptions(self, edited_df):
        """Extract custom assumptions"""
        custom_rows = edited_df[~edited_df['Category'].isin(['Business Segment', 'Financial'])].copy()
        
        custom_assumptions = []
        
        for _, row in custom_rows.iterrows():
            custom_assumptions.append({
                'category': row['Category'],
                'type': row['Type'],
                'item': row['Item'],
                'value': row['Value'],
                'unit': row['Unit']
            })
        
        return custom_assumptions
    
    def _display_segments_summary(self, assumptions_df):
        """Display business segments summary"""
        if assumptions_df.empty:
            return
        
        # Filter business segments
        business_segments = assumptions_df[assumptions_df['Category'] == 'Business Segment']
        
        if not business_segments.empty:
            st.markdown("---")
            st.subheader("📋 Business Segments Summary")
            
            # Group by segment and display summary
            segments_grouped = business_segments.groupby('Item')
            
            for segment_name, group in segments_grouped:
                with st.expander(f"📊 {segment_name}", expanded=False):
                    cols = st.columns(3)
                    
                    metrics = dict(zip(group['Type'], group['Value']))
                    
                    with cols[0]:
                        revenue_growth = metrics.get('Revenue Growth', 0)
                        st.metric("Revenue Growth", f"{revenue_growth:.1f}%")
                    
                    with cols[1]:
                        gross_margin = metrics.get('Gross Margin', 0)
                        st.metric("Gross Margin", f"{gross_margin:.1f}%")
                    
                    with cols[2]:
                        sga_pct = metrics.get('SG&A % of Revenue', 0)
                        st.metric("SG&A % of Revenue", f"{sga_pct:.1f}%")