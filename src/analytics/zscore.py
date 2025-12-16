"""
Z-score calculation for mean reversion signals
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple


def calculate_zscore(
    series: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling z-score.
    
    Z-score = (value - rolling_mean) / rolling_std
    
    A z-score > 2 or < -2 indicates the value is significantly
    above/below the rolling mean, suggesting mean reversion opportunity.
    
    Args:
        series: Input series (typically spread)
        window: Rolling window size
        min_periods: Minimum periods for calculation (default: window)
        
    Returns:
        Series of z-score values
    """
    if series is None or len(series) < 2:
        return pd.Series(dtype=float)
        
    if min_periods is None:
        min_periods = max(2, window // 2)
        
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)
    
    zscore = (series - rolling_mean) / rolling_std
    
    return zscore


def calculate_zscore_expanded(
    series: pd.Series,
    min_periods: int = 20
) -> pd.Series:
    """
    Calculate expanding z-score (using all available history).
    
    This uses all data from start to current point instead of a fixed window.
    
    Args:
        series: Input series
        min_periods: Minimum periods before calculating
        
    Returns:
        Series of z-score values
    """
    if series is None or len(series) < min_periods:
        return pd.Series(dtype=float)
        
    expanding_mean = series.expanding(min_periods=min_periods).mean()
    expanding_std = series.expanding(min_periods=min_periods).std()
    
    expanding_std = expanding_std.replace(0, np.nan)
    
    return (series - expanding_mean) / expanding_std


def get_zscore_signal(
    zscore: float,
    upper_threshold: float = 2.0,
    lower_threshold: float = -2.0
) -> str:
    """
    Get trading signal based on z-score.
    
    Args:
        zscore: Current z-score value
        upper_threshold: Upper threshold for sell signal
        lower_threshold: Lower threshold for buy signal
        
    Returns:
        Signal string: "buy", "sell", or "neutral"
    """
    if pd.isna(zscore):
        return "neutral"
        
    if zscore > upper_threshold:
        return "sell"  # Spread is high, expect mean reversion down
    elif zscore < lower_threshold:
        return "buy"   # Spread is low, expect mean reversion up
    else:
        return "neutral"


def calculate_zscore_with_bands(
    series: pd.Series,
    window: int = 60
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculate z-score along with mean and bands.
    
    Args:
        series: Input series
        window: Rolling window size
        
    Returns:
        Tuple of (zscore, rolling_mean, upper_band, lower_band)
    """
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    
    rolling_std_safe = rolling_std.replace(0, np.nan)
    zscore = (series - rolling_mean) / rolling_std_safe
    
    upper_band = rolling_mean + 2 * rolling_std
    lower_band = rolling_mean - 2 * rolling_std
    
    return zscore, rolling_mean, upper_band, lower_band


def zscore_entry_exit_signals(
    zscore: pd.Series,
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5
) -> pd.DataFrame:
    """
    Generate entry and exit signals based on z-score.
    
    Entry when |z-score| > entry_threshold
    Exit when |z-score| < exit_threshold
    
    Args:
        zscore: Series of z-score values
        entry_threshold: Threshold for entry signals
        exit_threshold: Threshold for exit signals
        
    Returns:
        DataFrame with signal columns
    """
    df = pd.DataFrame(index=zscore.index)
    
    df["zscore"] = zscore
    df["long_entry"] = zscore < -entry_threshold
    df["short_entry"] = zscore > entry_threshold
    df["exit"] = abs(zscore) < exit_threshold
    
    return df
