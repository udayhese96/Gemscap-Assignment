"""
Price statistics calculations
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PriceStatistics:
    """Container for price statistics results."""
    symbol: str
    mean: float
    std: float
    min: float
    max: float
    last: float
    returns_mean: float  # Mean of log returns
    returns_std: float   # Std of log returns (volatility)
    cumulative_return: float
    count: int
    
    def to_dict(self):
        return {
            "symbol": self.symbol,
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "last": self.last,
            "returns_mean": self.returns_mean,
            "returns_std": self.returns_std,
            "cumulative_return": self.cumulative_return,
            "count": self.count,
        }


def calculate_statistics(
    prices: pd.Series,
    symbol: str = "",
    annualize_factor: float = 252 * 24 * 60  # For minute data
) -> Optional[PriceStatistics]:
    """
    Calculate comprehensive price statistics.
    
    Args:
        prices: Series of prices (typically close prices)
        symbol: Symbol name for labeling
        annualize_factor: Factor for annualizing volatility
        
    Returns:
        PriceStatistics object or None if insufficient data
    """
    if prices is None or len(prices) < 2:
        return None
        
    prices = prices.dropna()
    if len(prices) < 2:
        return None
    
    # Calculate log returns
    log_returns = np.log(prices / prices.shift(1)).dropna()
    
    if len(log_returns) == 0:
        returns_mean = 0.0
        returns_std = 0.0
        cumulative_return = 0.0
    else:
        returns_mean = float(log_returns.mean())
        returns_std = float(log_returns.std())
        cumulative_return = float(np.exp(log_returns.sum()) - 1)
    
    return PriceStatistics(
        symbol=symbol,
        mean=float(prices.mean()),
        std=float(prices.std()),
        min=float(prices.min()),
        max=float(prices.max()),
        last=float(prices.iloc[-1]),
        returns_mean=returns_mean,
        returns_std=returns_std,
        cumulative_return=cumulative_return,
        count=len(prices),
    )


def calculate_rolling_statistics(
    prices: pd.Series,
    window: int = 60
) -> pd.DataFrame:
    """
    Calculate rolling statistics.
    
    Args:
        prices: Series of prices
        window: Rolling window size
        
    Returns:
        DataFrame with rolling mean and std
    """
    if prices is None or len(prices) < window:
        return pd.DataFrame(columns=["rolling_mean", "rolling_std"])
        
    df = pd.DataFrame({
        "price": prices,
        "rolling_mean": prices.rolling(window=window).mean(),
        "rolling_std": prices.rolling(window=window).std(),
    })
    
    return df


def calculate_volatility(
    prices: pd.Series,
    window: int = 60,
    annualize_factor: float = 252 * 24 * 60
) -> pd.Series:
    """
    Calculate rolling annualized volatility.
    
    Args:
        prices: Series of prices
        window: Rolling window size
        annualize_factor: Annualization factor
        
    Returns:
        Series of annualized volatility
    """
    log_returns = np.log(prices / prices.shift(1))
    rolling_std = log_returns.rolling(window=window).std()
    return rolling_std * np.sqrt(annualize_factor)
