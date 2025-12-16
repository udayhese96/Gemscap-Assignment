"""
Stationarity testing using Augmented Dickey-Fuller test
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import numpy as np


@dataclass
class ADFResult:
    """Container for ADF test results."""
    test_statistic: float
    p_value: float
    used_lag: int
    n_obs: int
    critical_values: dict  # 1%, 5%, 10% critical values
    is_stationary: bool    # p_value < significance_level
    
    def to_dict(self):
        return {
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "used_lag": self.used_lag,
            "n_obs": self.n_obs,
            "critical_values": self.critical_values,
            "is_stationary": self.is_stationary,
        }
    
    @property
    def interpretation(self) -> str:
        """Human-readable interpretation of results."""
        if self.is_stationary:
            return f"Stationary (p={self.p_value:.4f} < 0.05). Reject null hypothesis of unit root."
        else:
            return f"Non-stationary (p={self.p_value:.4f} >= 0.05). Cannot reject unit root hypothesis."


def adf_test(
    series: pd.Series,
    maxlag: Optional[int] = None,
    regression: str = "c",
    significance_level: float = 0.05
) -> Optional[ADFResult]:
    """
    Perform Augmented Dickey-Fuller test for stationarity.
    
    The ADF test tests the null hypothesis that a unit root is present
    in a time series sample. A stationary series is required for
    statistical arbitrage strategies.
    
    Args:
        series: Time series to test
        maxlag: Maximum lag to use for ADF test (None for auto selection)
        regression: Regression type - 'c' (constant), 'ct' (constant + trend),
                   'ctt' (constant + linear + quadratic trend), 'n' (no constant)
        significance_level: Significance level for stationarity decision
        
    Returns:
        ADFResult or None if insufficient data or error
    """
    if series is None or len(series) < 20:
        return None
        
    series = series.dropna()
    
    if len(series) < 20:
        return None
    
    try:
        from statsmodels.tsa.stattools import adfuller
        
        result = adfuller(
            series,
            maxlag=maxlag,
            regression=regression,
            autolag="AIC"
        )
        
        test_stat, p_value, used_lag, n_obs, critical_values, icbest = result
        
        return ADFResult(
            test_statistic=float(test_stat),
            p_value=float(p_value),
            used_lag=int(used_lag),
            n_obs=int(n_obs),
            critical_values={k: float(v) for k, v in critical_values.items()},
            is_stationary=p_value < significance_level,
        )
        
    except ImportError:
        # Fallback: simple difference stationarity check
        return _simple_stationarity_check(series, significance_level)
    except Exception:
        return None


def _simple_stationarity_check(
    series: pd.Series,
    significance_level: float = 0.05
) -> ADFResult:
    """
    Simple stationarity check without statsmodels.
    Uses variance ratio test as a rough approximation.
    """
    n = len(series)
    
    # Calculate variance of first and second half
    half = n // 2
    var1 = series.iloc[:half].var()
    var2 = series.iloc[half:].var()
    
    # Calculate mean of first and second half
    mean1 = series.iloc[:half].mean()
    mean2 = series.iloc[half:].mean()
    
    # Rough stationarity check: means and variances should be similar
    mean_diff = abs(mean1 - mean2) / (series.std() + 1e-10)
    var_ratio = max(var1, var2) / (min(var1, var2) + 1e-10)
    
    # Heuristic p-value based on variance ratio and mean difference
    p_value = min(1.0, (var_ratio - 1) * 0.1 + mean_diff * 0.2)
    
    return ADFResult(
        test_statistic=-1.0 / (var_ratio + 0.1),
        p_value=p_value,
        used_lag=1,
        n_obs=n,
        critical_values={"1%": -3.43, "5%": -2.86, "10%": -2.57},
        is_stationary=p_value < significance_level,
    )


def check_cointegration(
    y: pd.Series,
    x: pd.Series,
    significance_level: float = 0.05
) -> Optional[dict]:
    """
    Check if two series are cointegrated using Engle-Granger method.
    
    Two series are cointegrated if:
    1. Both are non-stationary (I(1))
    2. A linear combination of them is stationary (I(0))
    
    Args:
        y: First time series
        x: Second time series
        significance_level: Significance level for tests
        
    Returns:
        Dictionary with cointegration test results
    """
    try:
        from statsmodels.tsa.stattools import coint
        
        # Perform Engle-Granger cointegration test
        score, p_value, crit_values = coint(y.dropna(), x.dropna())
        
        return {
            "test_statistic": float(score),
            "p_value": float(p_value),
            "critical_values": {
                "1%": float(crit_values[0]),
                "5%": float(crit_values[1]),
                "10%": float(crit_values[2]),
            },
            "is_cointegrated": p_value < significance_level,
        }
        
    except ImportError:
        return None
    except Exception:
        return None
