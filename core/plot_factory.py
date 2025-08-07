import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from config.constants import PLOTLY_CONFIG, FINANCIAL_CONFIG

class PlotFactory:
    """Factory class for creating standardized financial plots"""
    
    def __init__(self):
        self.config = PLOTLY_CONFIG
        self.fin_config = FINANCIAL_CONFIG
    
    def create_financial_plots(self, df: pd.DataFrame, ticker: str, plot_config: dict) -> go.Figure:
        """
        Generic function to create financial plots with consistent styling
        
        Args:
            df: DataFrame with financial data
            ticker: Company ticker symbol
            plot_config: Dictionary with plot-specific configuration
                - cols: Number of columns in subplot
                - rows: Number of rows in subplot  
                - plot_cols: List of columns to plot
                - subplot_titles: List of subplot titles
                - chart_type: 'bar' or 'scatter' or 'mixed'
        """
        # Filter and pivot data
        df_temp = df.copy()
        df_ticker = df_temp[df_temp['TICKER'] == ticker]
        df_ticker = df_ticker.pivot(index='KEYCODE', columns='DATE', values='VALUE')
        
        # Calculate moving averages
        ma = df_ticker[plot_config['plot_cols']].rolling(
            window=self.fin_config['moving_average_window'], 
            min_periods=self.fin_config['min_periods']
        ).mean()
        
        # Create subplots
        fig = make_subplots(
            rows=plot_config['rows'], 
            cols=plot_config['cols'],
            subplot_titles=plot_config['subplot_titles']
        )
        
        # Add traces
        for idx, col in enumerate(plot_config['plot_cols']):
            row = (idx // plot_config['cols']) + 1
            col_pos = (idx % plot_config['cols']) + 1
            
            if col in df_ticker.index:
                # Add bar chart
                if plot_config.get('chart_type', 'bar') in ['bar', 'mixed']:
                    fig.add_trace(
                        go.Bar(
                            x=df_ticker.columns,
                            y=df_ticker.loc[col],
                            name=col,
                            marker_color=self.config['colors'][idx % len(self.config['colors'])],
                            showlegend=False
                        ),
                        row=row, col=col_pos
                    )
                
                # Add moving average line
                if plot_config.get('show_ma', True):
                    fig.add_trace(
                        go.Scatter(
                            x=ma.columns,
                            y=ma.loc[col],
                            mode='lines+markers',
                            name=f'{col} MA',
                            line=dict(color='red', width=2),
                            showlegend=False
                        ),
                        row=row, col=col_pos
                    )
        
        # Update layout
        fig.update_layout(
            height=self.config['subplot_height_multiplier'] * plot_config['rows'],
            width=self.config['chart_width'],
            template=self.config['template'],
            title_text=f"{ticker} - {plot_config.get('title', 'Financial Analysis')}"
        )
        
        return fig
    
    def create_comparison_chart(self, df: pd.DataFrame, tickers: list, metric: str, 
                              chart_type: str = 'bar') -> go.Figure:
        """Create comparison chart for multiple tickers on single metric"""
        
        fig = go.Figure()
        
        for idx, ticker in enumerate(tickers):
            df_ticker = df[df['TICKER'] == ticker]
            if not df_ticker.empty:
                pivot_data = df_ticker.pivot(index='KEYCODE', columns='DATE', values='VALUE')
                
                if metric in pivot_data.index:
                    if chart_type == 'bar':
                        fig.add_trace(go.Bar(
                            x=pivot_data.columns,
                            y=pivot_data.loc[metric],
                            name=ticker,
                            marker_color=self.config['colors'][idx % len(self.config['colors'])]
                        ))
                    elif chart_type == 'line':
                        fig.add_trace(go.Scatter(
                            x=pivot_data.columns,
                            y=pivot_data.loc[metric],
                            mode='lines+markers',
                            name=ticker,
                            line=dict(color=self.config['colors'][idx % len(self.config['colors'])], width=2)
                        ))
        
        fig.update_layout(
            height=self.config['chart_height'],
            width=self.config['chart_width'],
            template=self.config['template'],
            title_text=f"{metric} Comparison",
            xaxis_title="Date",
            yaxis_title=metric
        )
        
        return fig
    
    def create_time_series_chart(self, df: pd.DataFrame, ticker: str, metrics: list) -> go.Figure:
        """Create time series chart for multiple metrics of single ticker"""
        
        df_ticker = df[df['TICKER'] == ticker]
        pivot_data = df_ticker.pivot(index='KEYCODE', columns='DATE', values='VALUE')
        
        fig = go.Figure()
        
        for idx, metric in enumerate(metrics):
            if metric in pivot_data.index:
                fig.add_trace(go.Scatter(
                    x=pivot_data.columns,
                    y=pivot_data.loc[metric],
                    mode='lines+markers',
                    name=metric,
                    line=dict(color=self.config['colors'][idx % len(self.config['colors'])], width=2)
                ))
        
        fig.update_layout(
            height=self.config['chart_height'],
            width=self.config['chart_width'],
            template=self.config['template'],
            title_text=f"{ticker} - Time Series Analysis",
            xaxis_title="Date",
            yaxis_title="Value"
        )
        
        return fig
    
    def create_table_chart(self, df: pd.DataFrame, ticker: str, metrics: list, 
                          format_as_billions: bool = True) -> pd.DataFrame:
        """Create formatted table for financial statements"""
        
        df_ticker = df[df['TICKER'] == ticker]
        pivot_data = df_ticker.pivot(index='KEYCODE', columns='DATE', values='VALUE')
        
        # Filter for requested metrics
        available_metrics = [m for m in metrics if m in pivot_data.index]
        table_data = pivot_data.loc[available_metrics].copy()
        
        if format_as_billions and not table_data.empty:
            # Format as billions for display
            numeric_columns = table_data.select_dtypes(include=['number']).columns
            table_data[numeric_columns] = table_data[numeric_columns] / 1e9
        
        return table_data

# Global instance
plot_factory = PlotFactory()