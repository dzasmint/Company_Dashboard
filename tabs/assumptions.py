#%%
import streamlit as st
import pandas as pd
import numpy as np


class AssumptionsTab:
    """Assumptions interface tab with optimized data handling"""
    
    def __init__(self, parent):
        self.parent = parent
        # Initialize model_assumptions in session state if not exists
        if 'model_assumptions' not in st.session_state:
            st.session_state.model_assumptions = {}
    
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
        
        # Check if ticker has changed
        if 'last_assumptions_ticker' not in st.session_state:
            st.session_state.last_assumptions_ticker = None
        
        if st.session_state.last_assumptions_ticker != selected_ticker:
            # Ticker changed, force reload from MongoDB
            if 'model_assumptions' in st.session_state and selected_ticker in st.session_state.model_assumptions:
                del st.session_state.model_assumptions[selected_ticker]
            st.session_state.refresh_assumptions = True
            st.session_state.last_assumptions_ticker = selected_ticker
        
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
            - Each business segment should have 4 key assumptions:
              1. **Base Year Revenue** - Starting revenue (billion VND)
              2. **Revenue Growth** - Annual growth rate (%)
              3. **Gross Margin** - Gross profit margin (%)
              4. **SG&A % of Revenue** - Selling, General & Admin as % of revenue
            
            **Example (if you have a Brokerage segment):**
            - Category: `Business Segment`, Type: `Base Year Revenue`, Item: `Brokerage`, Value: `100`, Unit: `bn VND`
            - Category: `Business Segment`, Type: `Revenue Growth`, Item: `Brokerage`, Value: `15`, Unit: `%`
            - Category: `Business Segment`, Type: `Gross Margin`, Item: `Brokerage`, Value: `60`, Unit: `%`
            - Category: `Business Segment`, Type: `SG&A % of Revenue`, Item: `Brokerage`, Value: `25`, Unit: `%`
            
            **Note:** Business segments are optional. Use the AI Discovery tab to extract segments from documents or add them manually.
            
            **How to use:**
            - **Category**: Select "Business Segment" for revenue stream assumptions
            - **Type**: Choose the metric type (Base Year Revenue, Revenue Growth, Gross Margin, or SG&A % of Revenue)
            - **Item**: Enter the business segment name (e.g., "Brokerage", "Property Management")
            - **Value**: Enter the numeric value
            - **Unit**: Select the appropriate unit (usually "%")
            
            **Note:** Use consistent segment names across all metrics for proper grouping
            """)
    
    def _load_assumptions(self, selected_ticker):
        """Load assumptions with vectorized operations"""
        from utils.mongodb_utils import load_assumptions_from_mongodb
        
        # Initialize model_assumptions if not exists
        if 'model_assumptions' not in st.session_state:
            st.session_state.model_assumptions = {}
        
        # Check if we have assumptions for this ticker
        if selected_ticker not in st.session_state.model_assumptions or st.session_state.get('refresh_assumptions', False):
            with st.spinner(f"Loading assumptions for {selected_ticker}..."):
                # Try to load from MongoDB first
                mongodb_assumptions = load_assumptions_from_mongodb(selected_ticker)
                
                if mongodb_assumptions:
                    # Use MongoDB data
                    st.session_state.model_assumptions[selected_ticker] = mongodb_assumptions
                    st.toast(f"✅ Loaded saved assumptions for {selected_ticker}", icon="✅")
                else:
                    # Use default assumptions
                    st.session_state.model_assumptions[selected_ticker] = self._get_default_assumptions()
                    st.toast(f"📦 Using default assumptions for {selected_ticker}", icon="📦")
                
                st.session_state.refresh_assumptions = False
        
        # Get current assumptions as DataFrame
        assumptions_data = st.session_state.model_assumptions.get(selected_ticker, [])
        if not isinstance(assumptions_data, list):
            assumptions_data = []
        
        assumptions_df = pd.DataFrame(assumptions_data)
        
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
        """Get default assumptions - only financial items, no business segments"""
        return [
            {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": 12.0, "Unit": "%"},
            {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": 30.0, "Unit": "%"},
            {"Category": "Financial", "Type": "N/A", "Item": "Cost of Debts", "Value": 8.0, "Unit": "%"},
            {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": 20.0, "Unit": "%"}
        ]
    
    def _render_assumptions_editor(self, selected_ticker, assumptions_df):
        """Render the assumptions editor without form wrapper for direct editing"""
        st.subheader("📊 Assumptions Table")
        st.info("💡 **How to use:** Click any cell to edit | Use '+' button to add rows | Select row(s) and press Delete/Backspace to remove | Changes auto-save")
        
        editor_key = f"assumptions_editor_{selected_ticker}_direct"
        
        # Prepare data with Type column
        if assumptions_df.empty:
            # Create default empty dataframe with only financial items
            assumptions_df = pd.DataFrame([
                {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": 12.0, "Unit": "%"},
                {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": 30.0, "Unit": "%"},
                {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": 20.0, "Unit": "%"}
            ])
        elif 'Type' not in assumptions_df.columns:
            assumptions_df['Type'] = 'N/A'
        
        # Direct data editor without form
        edited_df = st.data_editor(
            assumptions_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    "Category",
                    options=["Business Segment", "Financial", "Operating", "Other"],
                    required=True,
                    width="medium"
                ),
                "Type": st.column_config.SelectboxColumn(
                    "Type",
                    options=["Base Year Revenue", "Revenue Growth", "Gross Margin", "SG&A % of Revenue", "N/A"],
                    required=True,
                    default="N/A",
                    help="For Business Segments: Select one of the 4 metrics. For others: Use N/A",
                    width="medium"  
                ),
                "Item": st.column_config.TextColumn(
                    "Item",
                    required=True,
                    help="Business segment or assumption name",
                    width="large"
                ),
                "Value": st.column_config.NumberColumn(
                    "Value",
                    min_value=0,
                    max_value=100000,
                    step=0.1,
                    format="%.2f",
                    width="small"
                ),
                "Unit": st.column_config.SelectboxColumn(
                    "Unit",
                    options=["%", "bn VND", "million VND", "x", "days", "years"],
                    required=True,
                    width="small"
                )
            },
            column_order=["Category", "Type", "Item", "Value", "Unit"],
            key=editor_key
        )
        
        # Auto-save to session state
        if edited_df is not None:
            if 'model_assumptions' not in st.session_state:
                st.session_state.model_assumptions = {}
            st.session_state.model_assumptions[selected_ticker] = edited_df.to_dict('records')
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Load Defaults", use_container_width=True):
                if 'model_assumptions' not in st.session_state:
                    st.session_state.model_assumptions = {}
                st.session_state.model_assumptions[selected_ticker] = self._get_default_assumptions()
                st.rerun()
        
        with col2:
            if st.button("💾 Save to Database", use_container_width=True):
                try:
                    from utils.mongodb_utils import save_assumptions_to_mongodb
                    result = save_assumptions_to_mongodb(selected_ticker, edited_df.to_dict('records'))
                    if result.get('success'):
                        st.success("✅ Saved to database!")
                    else:
                        st.error(f"Error: {result.get('message')}")
                except Exception as e:
                    st.error(f"Error saving: {str(e)}")
        
        with col3:
            if st.button("🔁 Reload from Database", use_container_width=True):
                from utils.mongodb_utils import load_assumptions_from_mongodb
                
                # Force reload from MongoDB
                with st.spinner(f"Reloading assumptions for {selected_ticker}..."):
                    mongodb_assumptions = load_assumptions_from_mongodb(selected_ticker)
                    
                    if 'model_assumptions' not in st.session_state:
                        st.session_state.model_assumptions = {}
                    
                    if mongodb_assumptions:
                        st.session_state.model_assumptions[selected_ticker] = mongodb_assumptions
                        st.success(f"✅ Reloaded assumptions from database for {selected_ticker}")
                    else:
                        # If no data in database, load defaults
                        st.session_state.model_assumptions[selected_ticker] = self._get_default_assumptions()
                        st.info(f"📦 No saved assumptions found, loaded defaults for {selected_ticker}")
                    
                    st.rerun()
        
        # Display business segments summary
        self._display_segments_summary(edited_df)
        
        # Add new business segment section
        st.markdown("---")
        st.subheader("➕ Add New Business Segment")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_segment_name = st.text_input(
                "Business Segment Name",
                placeholder="Enter segment name (e.g., Brokerage, Property Management)",
                key=f"new_segment_{selected_ticker}"
            )
        
        with col2:
            if st.button("Add New Business Segment", type="primary", use_container_width=True):
                if new_segment_name and new_segment_name.strip():
                    # Add 4 rows for the new segment
                    new_segment_assumptions = [
                        {"Category": "Business Segment", "Type": "Base Year Revenue", "Item": new_segment_name.strip(), "Value": 0.0, "Unit": "bn VND"},
                        {"Category": "Business Segment", "Type": "Revenue Growth", "Item": new_segment_name.strip(), "Value": 0.0, "Unit": "%"},
                        {"Category": "Business Segment", "Type": "Gross Margin", "Item": new_segment_name.strip(), "Value": 0.0, "Unit": "%"},
                        {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": new_segment_name.strip(), "Value": 0.0, "Unit": "%"}
                    ]
                    
                    # Get current assumptions
                    current_assumptions = st.session_state.model_assumptions.get(selected_ticker, [])
                    if not isinstance(current_assumptions, list):
                        current_assumptions = edited_df.to_dict('records') if edited_df is not None else []
                    
                    # Add new segment assumptions
                    current_assumptions.extend(new_segment_assumptions)
                    
                    # Update session state
                    if 'model_assumptions' not in st.session_state:
                        st.session_state.model_assumptions = {}
                    st.session_state.model_assumptions[selected_ticker] = current_assumptions
                    
                    st.success(f"✅ Added business segment: {new_segment_name.strip()}")
                    st.rerun()
                else:
                    st.warning("⚠️ Please enter a business segment name")
    
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
                options=["Base Year Revenue", "Revenue Growth", "Gross Margin", "SG&A % of Revenue", "N/A"],
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
                options=["%", "bn VND", "x", "days", "years", "B VND"],
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