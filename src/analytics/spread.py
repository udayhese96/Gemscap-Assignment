"""
Spread calculation for pairs trading
"""
import pandas as pd
import numpy as np
from typing import Optional


def calculate_spread(
    y: pd.Series,
    x: pd.Series,
    hedge_ratio: float,
    normalize: bool = False
) -> pd.Series:
    """
    Calculate spread between two assets.
    
    Spread = y - hedge_ratio * x
    
    For a cointegrated pair, this spread should be mean-reverting.
    
    Args:
        y: Price series of first asset (e.g., ETH)
        x: Price series of second asset (e.g., BTC)
        hedge_ratio: Beta from OLS regression
        normalize: Whether to normalize the spread
        
    Returns:
        Series of spread values
    """
    spread = y - hedge_ratio * x
    
    if normalize and len(spread) > 1:
        spread = (spread - spread.mean()) / spread.std()
        
    return spread


def calculate_log_spread(
    y: pd.Series,
    x: pd.Series,
    hedge_ratio: float
) -> pd.Series:
    """
    Calculate spread using log prices.
    
    Log Spread = log(y) - hedge_ratio * log(x)
    
    This is sometimes preferred for assets with different price scales.
    
    Args:
        y: Price series of first asset
        x: Price series of second asset
        hedge_ratio: Beta from OLS regression (on log prices)
        
    Returns:
        Series of log spread values
    """
    return np.log(y) - hedge_ratio * np.log(x)


def calculate_ratio_spread(
    y: pd.Series,
    x: pd.Series,
    window: Optional[int] = None
) -> pd.Series:
    """
    Calculate simple ratio spread.
    
    Ratio = y / x
    
    Optionally normalized by rolling mean.
    
    Args:
        y: Price series of first asset
        x: Price series of second asset
        window: Rolling window for normalization
        
    Returns:
        Series of ratio values
    """
    ratio = y / x
    
    if window and len(ratio) >= window:
        rolling_mean = ratio.rolling(window=window).mean()
        return ratio / rolling_mean
        
    return ratio


def calculate_spread_statistics(spread: pd.Series) -> dict:
    """
    Calculate statistics for a spread series.
    
    Args:
        spread: Series of spread values
        
    Returns:
        Dictionary of spread statistics
    """
    if spread is None or len(spread) < 2:
        return {}
        
    spread = spread.dropna()
    
    return {
        "mean": float(spread.mean()),
        "std": float(spread.std()),
        "min": float(spread.min()),
        "max": float(spread.max()),
        "last": float(spread.iloc[-1]),
        "range": float(spread.max() - spread.min()),
        "half_life": _estimate_half_life(spread),
    }


def _estimate_half_life(spread: pd.Series) -> Optional[float]:
    """
    Estimate mean-reversion half-life using Ornstein-Uhlenbeck model.
    
    Half-life = -log(2) / log(theta)
    
    where theta is the mean-reversion speed from AR(1) regression.
    
    Args:
        spread: Series of spread values
        
    Returns:
        Half-life in periods, or None if cannot be calculated
    """
    if len(spread) < 10:
        return None
        
    spread = spread.dropna()
    
    # AR(1) regression: spread_t = theta * spread_{t-1} + epsilon
    y = spread.iloc[1:].values
    x = spread.iloc[:-1].values
    
    # Simple OLS
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    
    if denominator == 0:
        return None
        
    theta = numerator / denominator
    
    # Calculate half-life
    if theta <= 0 or theta >= 1:
        return None
        
    half_life = -np.log(2) / np.log(theta)
    
    return float(half_life) if half_life > 0 else None
