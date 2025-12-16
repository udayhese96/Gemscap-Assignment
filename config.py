"""
Configuration constants for GemsCap Quantitative Analytics System
"""
from typing import List, Dict

# =============================================================================
# SYMBOLS & DATA
# =============================================================================
SYMBOLS: List[str] = ["btcusdt", "ethusdt"]
SYMBOL_DISPLAY: Dict[str, str] = {
    "btcusdt": "BTCUSDT",
    "ethusdt": "ETHUSDT",
    "solusdt": "SOLUSDT",
    "bnbusdt": "BNBUSDT",
}

# =============================================================================
# TIMEFRAMES
# =============================================================================
TIMEFRAMES: Dict[str, str] = {
    "1s": "1S",   # 1 second
    "1m": "1T",   # 1 minute (T = minute in pandas)
    "5m": "5T",   # 5 minutes
}

DEFAULT_TIMEFRAME: str = "1m"

# =============================================================================
# ANALYTICS
# =============================================================================
ROLLING_WINDOW: int = 60  # Default lookback period in bars
MIN_WINDOW: int = 20
MAX_WINDOW: int = 200

# Z-score alert thresholds
ZSCORE_UPPER_THRESHOLD: float = 2.0
ZSCORE_LOWER_THRESHOLD: float = -2.0

# ADF test significance level
ADF_SIGNIFICANCE: float = 0.05

# =============================================================================
# STORAGE
# =============================================================================
MAX_TICK_HISTORY: int = 100000  # Maximum ticks to retain per symbol
MAX_BAR_HISTORY: int = 10000    # Maximum bars to retain per symbol/timeframe

# SQLite (optional)
SQLITE_DB_PATH: str = "gemscap_data.db"
ENABLE_SQLITE: bool = False

# =============================================================================
# WEBSOCKET
# =============================================================================
BINANCE_WS_BASE: str = "wss://fstream.binance.com/ws"
RECONNECT_DELAY: float = 1.0  # Initial delay in seconds
MAX_RECONNECT_DELAY: float = 30.0  # Maximum delay
RECONNECT_MULTIPLIER: float = 2.0  # Exponential backoff multiplier

# =============================================================================
# UI
# =============================================================================
REFRESH_RATE_MS: int = 1000  # Dashboard refresh rate in milliseconds
CHART_HEIGHT: int = 300
SIDEBAR_WIDTH: int = 300

# Color scheme (dark theme)
COLORS: Dict[str, str] = {
    "background": "#0f172a",
    "surface": "#1e293b",
    "primary": "#0ea5e9",
    "secondary": "#8b5cf6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "text": "#e2e8f0",
    "text_muted": "#94a3b8",
    "btc": "#f7931a",
    "eth": "#627eea",
}

# =============================================================================
# ALERTS
# =============================================================================
ALERT_COOLDOWN_SECONDS: int = 60  # Minimum time between same alert type
MAX_ALERT_HISTORY: int = 100
