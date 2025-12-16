"""
Correlation calculations
"""
import pandas as pd
import numpy as np
from typing import Optional, List


def rolling_correlation(
    x: pd.Series,
    y: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling Pearson correlation between two series.
    
    Args:
        x: First series
        y: Second series
        window: Rolling window size
        min_periods: Minimum periods for calculation
        
    Returns:
        Series of correlation values
    """
    if x is None or y is None or len(x) < 2 or len(y) < 2:
        return pd.Series(dtype=float)
        
    if min_periods is None:
        min_periods = max(2, window // 2)
        
    # Align indices
    df = pd.DataFrame({"x": x, "y": y}).dropna()
    
    if len(df) < min_periods:
        return pd.Series(dtype=float)
        
    return df["x"].rolling(window=window, min_periods=min_periods).corr(df["y"])


def calculate_correlation_matrix(
    data: dict,  # {symbol: pd.Series of prices}
    method: str = "pearson"
) -> pd.DataFrame:
    """
    Calculate correlation matrix for multiple assets.
    
    Args:
        data: Dictionary mapping symbol to price series
        method: Correlation method ('pearson', 'spearman', 'kendall')
        
    Returns:
        DataFrame correlation matrix
    """
    if not data:
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    return df.corr(method=method)


def rolling_correlation_matrix(
    data: dict,
    window: int = 60
) -> List[pd.DataFrame]:
    """
    Calculate rolling correlation matrices.
    
    Args:
        data: Dictionary mapping symbol to price series
        window: Rolling window size
        
    Returns:
        List of correlation matrices, one per time period
    """
    if not data or len(data) < 2:
        return []
        
    df = pd.DataFrame(data)
    
    matrices = []
    for i in range(window, len(df) + 1):
        window_df = df.iloc[i-window:i]
        matrices.append(window_df.corr())
        
    return matrices


def calculate_returns_correlation(
    x: pd.Series,
    y: pd.Series,
    window: int = 60
) -> pd.Series:
    """
    Calculate rolling correlation of returns.
    
    Using returns instead of prices removes the impact of
    trending behavior on correlation estimates.
    
    Args:
        x: First price series
        y: Second price series
        window: Rolling window size
        
    Returns:
        Series of return correlations
    """
    # Calculate log returns
    x_returns = np.log(x / x.shift(1)).dropna()
    y_returns = np.log(y / y.shift(1)).dropna()
    
    return rolling_correlation(x_returns, y_returns, window)


def beta_correlation_decomposition(
    y: pd.Series,
    x: pd.Series,
    window: int = 60
) -> pd.DataFrame:
    """
    Decompose relationship between two assets into beta and correlation.
    
    beta = correlation * (std_y / std_x)
    
    Args:
        y: Dependent variable
        x: Independent variable
        window: Rolling window size
        
    Returns:
        DataFrame with rolling beta and correlation
    """
    y_returns = np.log(y / y.shift(1))
    x_returns = np.log(x / x.shift(1))
    
    corr = rolling_correlation(x_returns, y_returns, window)
    y_std = y_returns.rolling(window=window).std()
    x_std = x_returns.rolling(window=window).std()
    
    beta = corr * (y_std / x_std)
    
    return pd.DataFrame({
        "correlation": corr,
        "beta": beta,
        "y_volatility": y_std,
        "x_volatility": x_std,
    })
