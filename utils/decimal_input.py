"""
Custom decimal input component for Streamlit that handles float/decimal values smoothly
without cursor jumping issues that occur with st.number_input
"""

import streamlit as st
import re
from typing import Optional, Union


def decimal_input(
    label: str,
    value: Union[float, int] = 0.0,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    step: Optional[float] = None,
    key: Optional[str] = None,
    help: Optional[str] = None,
    label_visibility: str = "visible",
    disabled: bool = False,
    placeholder: Optional[str] = None
) -> float:
    """
    Custom decimal input using text_input with validation.
    
    This component provides a better user experience for entering decimal numbers
    compared to st.number_input, avoiding cursor jumping issues.
    
    Args:
        label: Label for the input field
        value: Default value
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        step: Step increment for up/down buttons (not implemented in text version)
        key: Unique key for the widget
        help: Help tooltip text
        label_visibility: "visible", "hidden", or "collapsed"
        disabled: Whether the input is disabled
        placeholder: Placeholder text when empty
    
    Returns:
        float: The validated decimal value
    """
    
    # Generate unique keys for session state
    if key:
        text_key = f"{key}_text"
        value_key = f"{key}_value"
        error_key = f"{key}_error"
    else:
        import hashlib
        unique_id = hashlib.md5(label.encode()).hexdigest()[:8]
        text_key = f"decimal_{unique_id}_text"
        value_key = f"decimal_{unique_id}_value"
        error_key = f"decimal_{unique_id}_error"
    
    # Initialize session state
    if value_key not in st.session_state:
        st.session_state[value_key] = float(value)
        st.session_state[text_key] = str(value) if value != 0 else ""
        st.session_state[error_key] = ""
    
    # Create columns for input and validation feedback
    if label_visibility == "visible":
        input_col, feedback_col = st.columns([3, 1])
    else:
        input_col = st.container()
        feedback_col = None
    
    with input_col:
        # Text input for decimal number
        user_input = st.text_input(
            label=label,
            value=st.session_state[text_key],
            key=text_key + "_widget",
            help=help,
            label_visibility=label_visibility,
            disabled=disabled,
            placeholder=placeholder or "Enter a number"
        )
    
    # Validation logic
    if user_input != st.session_state[text_key]:
        st.session_state[text_key] = user_input
        
        # Allow empty input (treat as 0)
        if user_input.strip() == "":
            st.session_state[value_key] = 0.0
            st.session_state[error_key] = ""
        else:
            # Validate decimal number format
            # Allow: optional sign, digits, optional decimal point, optional digits after decimal
            # Also allow numbers like .5 (without leading zero)
            decimal_pattern = r'^[-+]?(\d+\.?\d*|\.\d+)$'
            
            if re.match(decimal_pattern, user_input.strip()):
                try:
                    float_value = float(user_input.strip())
                    
                    # Check min/max constraints
                    if min_value is not None and float_value < min_value:
                        st.session_state[error_key] = f"Value must be ≥ {min_value}"
                        # Optionally clamp to min value
                        st.session_state[value_key] = min_value
                    elif max_value is not None and float_value > max_value:
                        st.session_state[error_key] = f"Value must be ≤ {max_value}"
                        # Optionally clamp to max value
                        st.session_state[value_key] = max_value
                    else:
                        st.session_state[value_key] = float_value
                        st.session_state[error_key] = ""
                        
                except ValueError:
                    st.session_state[error_key] = "Invalid number"
            else:
                st.session_state[error_key] = "Please enter a valid number"
    
    # Display validation feedback
    if feedback_col and st.session_state[error_key]:
        with feedback_col:
            st.error(st.session_state[error_key])
    elif st.session_state[error_key] and label_visibility != "collapsed":
        st.error(st.session_state[error_key])
    
    return st.session_state[value_key]


def percentage_input(
    label: str,
    value: float = 0.0,
    key: Optional[str] = None,
    help: Optional[str] = None,
    label_visibility: str = "visible",
    disabled: bool = False,
    max_value: float = 100.0
) -> float:
    """
    Specialized decimal input for percentage values (0-100).
    
    Args:
        label: Label for the input field
        value: Default value (0-100)
        key: Unique key for the widget
        help: Help tooltip text  
        label_visibility: "visible", "hidden", or "collapsed"
        disabled: Whether the input is disabled
        max_value: Maximum percentage (default 100.0)
    
    Returns:
        float: The validated percentage value (0-100)
    """
    return decimal_input(
        label=label,
        value=value,
        min_value=0.0,
        max_value=max_value,
        key=key,
        help=help or "Enter a percentage between 0 and 100",
        label_visibility=label_visibility,
        disabled=disabled,
        placeholder="0-100"
    )


def currency_input(
    label: str,
    value: float = 0.0,
    key: Optional[str] = None,
    help: Optional[str] = None,
    label_visibility: str = "visible",
    disabled: bool = False,
    min_value: float = 0.0
) -> float:
    """
    Specialized decimal input for currency/monetary values.
    
    Args:
        label: Label for the input field
        value: Default value
        key: Unique key for the widget
        help: Help tooltip text
        label_visibility: "visible", "hidden", or "collapsed"
        disabled: Whether the input is disabled
        min_value: Minimum value (default 0.0 for no negative amounts)
    
    Returns:
        float: The validated currency value
    """
    return decimal_input(
        label=label,
        value=value,
        min_value=min_value,
        key=key,
        help=help,
        label_visibility=label_visibility,
        disabled=disabled,
        placeholder="0.00"
    )