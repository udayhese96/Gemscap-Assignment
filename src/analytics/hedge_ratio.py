"""
Hedge ratio calculation using OLS regression
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HedgeRatioResult:
    """Container for hedge ratio calculation results."""
    beta: float          # Hedge ratio (slope)
    alpha: float         # Intercept
    r_squared: float     # R-squared of regression
    std_error: float     # Standard error of beta
    
    def to_dict(self):
        return {
            "beta": self.beta,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "std_error": self.std_error,
        }


def calculate_hedge_ratio(
    y: pd.Series,
    x: pd.Series,
    use_statsmodels: bool = True
) -> Optional[HedgeRatioResult]:
    """
    Calculate hedge ratio using OLS regression: y = alpha + beta * x + epsilon
    
    The hedge ratio (beta) represents how many units of x to short for each
    unit of y to create a hedged position.
    
    Args:
        y: Dependent variable (e.g., ETH prices)
        x: Independent variable (e.g., BTC prices)
        use_statsmodels: Whether to use statsmodels (more detailed) or numpy
        
    Returns:
        HedgeRatioResult or None if insufficient data
    """
    # Align indices and drop NaN
    df = pd.DataFrame({"y": y, "x": x}).dropna()
    
    if len(df) < 10:  # Need minimum data for regression
        return None
        
    y_clean = df["y"].values
    x_clean = df["x"].values
    
    if use_statsmodels:
        try:
            import statsmodels.api as sm
            
            # Add constant for intercept
            X = sm.add_constant(x_clean)
            model = sm.OLS(y_clean, X)
            results = model.fit()
            
            return HedgeRatioResult(
                beta=float(results.params[1]),
                alpha=float(results.params[0]),
                r_squared=float(results.rsquared),
                std_error=float(results.bse[1]) if len(results.bse) > 1 else 0.0,
            )
        except ImportError:
            use_statsmodels = False
            
    # Fallback to numpy implementation
    # y = alpha + beta * x
    n = len(x_clean)
    x_mean = np.mean(x_clean)
    y_mean = np.mean(y_clean)
    
    # Calculate beta (slope)
    numerator = np.sum((x_clean - x_mean) * (y_clean - y_mean))
    denominator = np.sum((x_clean - x_mean) ** 2)
    
    if denominator == 0:
        return None
        
    beta = numerator / denominator
    alpha = y_mean - beta * x_mean
    
    # Calculate R-squared
    y_pred = alpha + beta * x_clean
    ss_res = np.sum((y_clean - y_pred) ** 2)
    ss_tot = np.sum((y_clean - y_mean) ** 2)
    
    if ss_tot == 0:
        r_squared = 0.0
    else:
        r_squared = 1 - (ss_res / ss_tot)
    
    # Calculate standard error of beta
    if n > 2:
        mse = ss_res / (n - 2)
        std_error = np.sqrt(mse / denominator)
    else:
        std_error = 0.0
    
    return HedgeRatioResult(
        beta=float(beta),
        alpha=float(alpha),
        r_squared=float(r_squared),
        std_error=float(std_error),
    )


def calculate_rolling_hedge_ratio(
    y: pd.Series,
    x: pd.Series,
    window: int = 60
) -> pd.DataFrame:
    """
    Calculate rolling hedge ratio.
    
    Args:
        y: Dependent variable series
        x: Independent variable series
        window: Rolling window size
        
    Returns:
        DataFrame with rolling beta and r_squared
    """
    betas = []
    r_squareds = []
    
    for i in range(len(y)):
        if i < window - 1:
            betas.append(np.nan)
            r_squareds.append(np.nan)
        else:
            result = calculate_hedge_ratio(
                y.iloc[i-window+1:i+1],
                x.iloc[i-window+1:i+1]
            )
            if result:
                betas.append(result.beta)
                r_squareds.append(result.r_squared)
            else:
                betas.append(np.nan)
                r_squareds.append(np.nan)
                
    return pd.DataFrame({
        "beta": betas,
        "r_squared": r_squareds,
    }, index=y.index)
