"""
GemsCap Quantitative Analytics Dashboard

Real-time statistical arbitrage analytics using Binance Futures WebSocket data.
Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import threading
import json
from datetime import datetime, timedelta, timezone
from collections import deque
import time

# Import local modules
from config import (
    SYMBOLS, SYMBOL_DISPLAY, TIMEFRAMES, DEFAULT_TIMEFRAME,
    ROLLING_WINDOW, MIN_WINDOW, MAX_WINDOW,
    ZSCORE_UPPER_THRESHOLD, ZSCORE_LOWER_THRESHOLD,
    COLORS, REFRESH_RATE_MS, CHART_HEIGHT
)
from src.ingestion.data_normalizer import Tick, normalize_tick, normalize_from_ndjson
from src.processing.resampler import TimeSeriesResampler
from src.processing.ohlcv import OHLCVBar
from src.storage.memory_store import MemoryStore
from src.analytics.statistics import calculate_statistics, PriceStatistics
from src.analytics.hedge_ratio import calculate_hedge_ratio, HedgeRatioResult
from src.analytics.spread import calculate_spread, calculate_spread_statistics
from src.analytics.zscore import calculate_zscore, get_zscore_signal
from src.analytics.stationarity import adf_test, ADFResult
from src.analytics.correlation import rolling_correlation
from src.alerts.rule_engine import AlertEngine, Alert, AlertSeverity

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="GemsCap Quant Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CUSTOM CSS - Apple Magnus Glassmorphism Theme
# =============================================================================
st.markdown("""
<style>
    /* ========================================
       GLOBAL STYLES & DARK GRADIENT BACKGROUND
       ======================================== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-tertiary: #1a1a24;
        --glass-bg: rgba(255, 255, 255, 0.03);
        --glass-border: rgba(255, 255, 255, 0.08);
        --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-blue: #3b82f6;
        --accent-cyan: #06b6d4;
        --accent-green: #10b981;
        --accent-amber: #f59e0b;
        --accent-red: #ef4444;
        --accent-purple: #8b5cf6;
        --border-radius: 16px;
    }
    
    .main {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0d1117 50%, var(--bg-secondary) 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .stApp {
        background: linear-gradient(180deg, 
            #0a0a0f 0%, 
            #0d1220 25%, 
            #0f1628 50%, 
            #0d1220 75%, 
            #0a0a0f 100%);
    }
    
    /* Subtle animated gradient overlay */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: 
            radial-gradient(ellipse at 20% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(6, 182, 212, 0.04) 0%, transparent 60%);
        pointer-events: none;
        z-index: 0;
    }
    
    /* ========================================
       GLASSMORPHISM CARD STYLES
       ======================================== */
    .glass-card {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.05) 0%, 
            rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: var(--border-radius);
        box-shadow: 
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        padding: 20px;
        margin: 8px 0;
        position: relative;
        overflow: hidden;
    }
    
    .glass-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(255, 255, 255, 0.1) 50%, 
            transparent 100%);
    }
    
    /* ========================================
       KPI CARDS - Horizontal Top Section
       ======================================== */
    .kpi-card {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.06) 0%, 
            rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 14px;
        padding: 20px 24px;
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .kpi-card:hover {
        border-color: rgba(255, 255, 255, 0.15);
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
    }
    
    .kpi-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
        opacity: 0.6;
    }
    
    .kpi-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 32px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -1px;
        margin-bottom: 2px;
        line-height: 1.1;
    }
    
    .kpi-label {
        font-size: 10px;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
    }
    
    .kpi-change {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        font-weight: 500;
        padding: 4px 8px;
        border-radius: 6px;
        margin-top: 8px;
    }
    
    .kpi-change-positive {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
    }
    
    .kpi-change-negative {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
    }
    
    .kpi-change-neutral {
        background: rgba(100, 116, 139, 0.15);
        color: #94a3b8;
    }
    
    /* ========================================
       CHART CONTAINERS
       ======================================== */
    .chart-container {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.04) 0%, 
            rgba(255, 255, 255, 0.01) 100%);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: var(--border-radius);
        padding: 24px;
        margin: 16px 0;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
    }
    
    .chart-title {
        font-size: 15px;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 4px 0;
    }
    
    .chart-title::before {
        content: '';
        width: 3px;
        height: 18px;
        background: linear-gradient(180deg, #3b82f6, #06b6d4);
        border-radius: 2px;
        flex-shrink: 0;
    }
    
    /* ========================================
       SIDEBAR STYLING
       ======================================== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, 
            rgba(15, 23, 42, 0.95) 0%, 
            rgba(10, 10, 15, 0.98) 100%);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    section[data-testid="stSidebar"] > div {
        background: transparent !important;
    }
    
    .sidebar-section {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
    }
    
    .sidebar-title {
        font-size: 11px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 12px;
    }
    
    /* ========================================
       ALERT CARDS
       ======================================== */
    .alert-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
        display: flex;
        align-items: flex-start;
        gap: 12px;
        border-left: 3px solid;
        transition: all 0.2s ease;
    }
    
    .alert-card:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    
    .alert-warning {
        border-left-color: var(--accent-amber);
        background: linear-gradient(135deg, 
            rgba(245, 158, 11, 0.08) 0%, 
            rgba(245, 158, 11, 0.02) 100%);
    }
    
    .alert-critical {
        border-left-color: var(--accent-red);
        background: linear-gradient(135deg, 
            rgba(239, 68, 68, 0.1) 0%, 
            rgba(239, 68, 68, 0.03) 100%);
    }
    
    .alert-info {
        border-left-color: var(--accent-blue);
        background: linear-gradient(135deg, 
            rgba(59, 130, 246, 0.08) 0%, 
            rgba(59, 130, 246, 0.02) 100%);
    }
    
    .alert-icon {
        font-size: 18px;
        flex-shrink: 0;
    }
    
    .alert-content {
        flex: 1;
    }
    
    .alert-message {
        font-size: 13px;
        color: var(--text-primary);
        line-height: 1.4;
    }
    
    .alert-time {
        font-size: 11px;
        color: var(--text-muted);
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* ========================================
       STATUS INDICATORS
       ======================================== */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }
    
    .status-live {
        background: linear-gradient(135deg, 
            rgba(16, 185, 129, 0.15) 0%, 
            rgba(16, 185, 129, 0.05) 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: var(--accent-green);
    }
    
    .status-live::before {
        content: '';
        width: 8px;
        height: 8px;
        background: var(--accent-green);
        border-radius: 50%;
        animation: pulse-green 2s ease-in-out infinite;
        box-shadow: 0 0 8px var(--accent-green);
    }
    
    .status-disconnected {
        background: rgba(100, 116, 139, 0.1);
        border: 1px solid rgba(100, 116, 139, 0.2);
        color: var(--text-muted);
    }
    
    .status-demo {
        background: linear-gradient(135deg, 
            rgba(139, 92, 246, 0.15) 0%, 
            rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(139, 92, 246, 0.3);
        color: var(--accent-purple);
    }
    
    @keyframes pulse-green {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.9); }
    }
    
    /* ========================================
       BUTTON STYLING
       ======================================== */
    .stButton > button {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.08) 0%, 
            rgba(255, 255, 255, 0.03) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        color: var(--text-primary);
        font-weight: 500;
        padding: 10px 20px;
        transition: all 0.2s ease;
        backdrop-filter: blur(8px);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.12) 0%, 
            rgba(255, 255, 255, 0.06) 100%);
        border-color: rgba(255, 255, 255, 0.2);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .stButton > button:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }
    
    /* Primary action button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
        border: none;
    }
    
    /* ========================================
       METRICS STYLING
       ======================================== */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, 
            rgba(255, 255, 255, 0.05) 0%, 
            rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
    }
    
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
        font-size: 24px;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--text-muted);
    }
    
    /* ========================================
       INPUT ELEMENTS
       ======================================== */
    .stSelectbox, .stMultiSelect, .stSlider {
        background: transparent;
    }
    
    .stSlider [data-testid="stThumbValue"] {
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 10px;
        padding: 8px;
    }
    
    /* ========================================
       DIVIDERS
       ======================================== */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(255, 255, 255, 0.1) 50%, 
            transparent 100%);
        margin: 24px 0;
    }
    
    /* ========================================
       SCROLLBAR STYLING
       ======================================== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.15);
    }
    
    /* ========================================
       HEADER & TYPOGRAPHY
       ======================================== */
    h1, h2, h3 {
        color: var(--text-primary);
        font-weight: 600;
    }
    
    h1 {
        font-size: 28px;
        letter-spacing: -0.5px;
    }
    
    .header-gradient {
        background: linear-gradient(135deg, var(--text-primary), var(--accent-cyan));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* ========================================
       PLOTLY CHART OVERRIDES
       ======================================== */
    .js-plotly-plot {
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* ========================================
       Z-SCORE INDICATOR
       ======================================== */
    .zscore-positive {
        color: var(--accent-red);
    }
    
    .zscore-negative {
        color: var(--accent-green);
    }
    
    .zscore-neutral {
        color: var(--text-secondary);
    }
    
    /* ========================================
       HIDE STREAMLIT BRANDING
       ======================================== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* ========================================
       SUCCESS/INFO/WARNING BOXES
       ======================================== */
    .stSuccess, .stInfo, .stWarning, .stError {
        background: transparent !important;
        border-radius: 10px !important;
        backdrop-filter: blur(8px);
    }
    
    .stSuccess {
        background: linear-gradient(135deg, 
            rgba(16, 185, 129, 0.1) 0%, 
            rgba(16, 185, 129, 0.03) 100%) !important;
        border: 1px solid rgba(16, 185, 129, 0.2) !important;
    }
    
    .stInfo {
        background: linear-gradient(135deg, 
            rgba(59, 130, 246, 0.1) 0%, 
            rgba(59, 130, 246, 0.03) 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# GLOBAL SHARED STATE (Thread-safe, accessible from WebSocket callbacks)
# =============================================================================
# Using st.cache_resource to persist state across Streamlit reruns

import threading

class GlobalState:
    """Thread-safe global state for WebSocket data."""
    
    def __init__(self):
        self.store = MemoryStore()
        self.alert_engine = AlertEngine()
        self.resamplers = {}
        self.tick_count = 0
        self.last_update = None
        self.is_running = False
        self.ws_client = None
        self._data_lock = threading.Lock()
        
    def add_tick(self, tick: Tick, timeframe: str):
        """Thread-safe tick processing."""
        with self._data_lock:
            self.store.add_tick(tick)
            self.tick_count += 1
            self.last_update = datetime.now(timezone.utc)
            
            # Get or create resampler for this timeframe
            if timeframe not in self.resamplers:
                self.resamplers[timeframe] = TimeSeriesResampler(timeframe)
                
                # Set up callback to store bars
                def on_bar(bar: OHLCVBar, tf=timeframe):
                    self.store.add_bar(bar, tf)
                self.resamplers[timeframe].on_bar(on_bar)
                
            bar = self.resamplers[timeframe].add_tick(tick)
            if bar:
                self.store.add_bar(bar, timeframe)
    
    def reset_all(self):
        """Reset all data and state - clears cache and starts fresh."""
        with self._data_lock:
            # Clear the memory store
            self.store.clear()
            # Reset alert engine
            self.alert_engine.clear_all()
            # Reset resamplers
            self.resamplers = {}
            # Reset counters
            self.tick_count = 0
            self.last_update = None

@st.cache_resource
def get_global_state():
    """Get or create the global state singleton (persists across reruns)."""
    return GlobalState()

# Global state instance - use the cached function
_global_state = get_global_state()

# =============================================================================
# SESSION STATE INITIALIZATION (For UI state only)
# =============================================================================
def init_session_state():
    """Initialize session state variables for UI only."""
    if "demo_mode" not in st.session_state:
        st.session_state.demo_mode = False
    if "demo_data_loaded" not in st.session_state:
        st.session_state.demo_data_loaded = False

init_session_state()

# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================
def load_ndjson_data(filepath: str) -> list:
    """Load tick data from NDJSON file."""
    ticks = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    tick = normalize_from_ndjson(record)
                    if tick:
                        ticks.append(tick)
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return ticks


def load_demo_data(timeframe: str):
    """Load demo data from NDJSON file."""
    if st.session_state.demo_data_loaded:
        return
    
    import os
    filepath = "ticks_2025-12-15T09-34-58.362Z.ndjson"
    
    # Check if file exists
    if not os.path.exists(filepath):
        st.error(f"Demo data file not found: {filepath}")
        return
        
    ticks = load_ndjson_data(filepath)
    if not ticks:
        st.error("No ticks loaded from demo data file")
        return
    
    # Create resamplers for all timeframes
    resamplers = {
        "1S": TimeSeriesResampler("1S"),
        "1T": TimeSeriesResampler("1T"),
        "5T": TimeSeriesResampler("5T"),
    }
    
    store = _global_state.store
    
    # Process all ticks
    for tick in ticks:
        store.add_tick(tick)
        _global_state.tick_count += 1
        
        # Add to all resamplers
        for tf, resampler in resamplers.items():
            bar = resampler.add_tick(tick)
            if bar:
                store.add_bar(bar, tf)
    
    # Force completion of current bars by getting them
    for tf, resampler in resamplers.items():
        for symbol in resampler.symbols:
            current_bar = resampler.get_current_bar(symbol)
            if current_bar:
                store.add_bar(current_bar, tf)
    
    st.session_state.demo_data_loaded = True
    st.session_state.demo_mode = True
    _global_state.last_update = datetime.now(timezone.utc)


# =============================================================================
# WEBSOCKET CONNECTION
# =============================================================================
def start_websocket(symbols: list, timeframe: str):
    """Start WebSocket connection in background thread."""
    if _global_state.is_running:
        return
        
    try:
        from src.ingestion.websocket_client import SyncWebSocketClient
        
        client = SyncWebSocketClient()
        
        # Use global state in callback (thread-safe)
        def on_tick(tick: Tick):
            _global_state.add_tick(tick, timeframe)
            
        client.on_tick(on_tick)
        client.start(symbols)
        _global_state.ws_client = client
        _global_state.is_running = True
        
    except Exception as e:
        st.error(f"WebSocket connection failed: {e}")


def stop_websocket():
    """Stop WebSocket connection."""
    if _global_state.ws_client:
        _global_state.ws_client.stop()
        _global_state.ws_client = None
    _global_state.is_running = False

# =============================================================================
# ANALYTICS FUNCTIONS
# =============================================================================
def compute_analytics(symbols: list, timeframe: str, window: int, 
                       filter_start: datetime = None, filter_end: datetime = None) -> dict:
    """Compute all analytics for the dashboard with optional date filtering."""
    store = _global_state.store
    results = {
        "prices": {},
        "statistics": {},
        "hedge_ratio": None,
        "spread": None,
        "zscore": None,
        "adf": None,
        "correlation": None,
        "filtered": filter_start is not None,  # Flag to indicate if data is filtered
    }
    
    # Get price data for each symbol
    for symbol in symbols:
        prices = store.get_prices(symbol.upper(), timeframe)
        if not prices.empty:
            # Apply date filter if specified
            if filter_start is not None and filter_end is not None:
                # Ensure index is datetime-like for filtering
                if hasattr(prices.index, 'tz_localize'):
                    try:
                        mask = (prices.index >= pd.Timestamp(filter_start)) & (prices.index <= pd.Timestamp(filter_end))
                        prices = prices[mask]
                    except:
                        pass  # If filtering fails, use all data
            
            if not prices.empty:
                results["prices"][symbol.upper()] = prices
                results["statistics"][symbol.upper()] = calculate_statistics(prices, symbol.upper())
    
    # Need at least 2 symbols for pair analytics
    if len(results["prices"]) >= 2:
        symbol_list = list(results["prices"].keys())
        y_symbol, x_symbol = symbol_list[0], symbol_list[1]
        y_prices = results["prices"][y_symbol]
        x_prices = results["prices"][x_symbol]
        
        # Remove duplicate indices (can happen with fast data)
        y_prices = y_prices[~y_prices.index.duplicated(keep='last')]
        x_prices = x_prices[~x_prices.index.duplicated(keep='last')]
        
        # Align indices using merge instead of direct DataFrame creation
        try:
            df = pd.DataFrame({"y": y_prices, "x": x_prices}).dropna()
        except ValueError:
            # Fallback: use inner join on common indices
            common_idx = y_prices.index.intersection(x_prices.index)
            if len(common_idx) > 0:
                df = pd.DataFrame({
                    "y": y_prices.loc[common_idx].values,
                    "x": x_prices.loc[common_idx].values
                }, index=common_idx)
            else:
                df = pd.DataFrame()
        
        if len(df) >= window:
            y = df["y"]
            x = df["x"]
            
            # Hedge ratio
            results["hedge_ratio"] = calculate_hedge_ratio(y, x)
            
            # Spread
            if results["hedge_ratio"]:
                spread = calculate_spread(y, x, results["hedge_ratio"].beta)
                results["spread"] = spread
                results["spread_stats"] = calculate_spread_statistics(spread)
                
                # Z-score
                zscore = calculate_zscore(spread, window)
                results["zscore"] = zscore
                
                # Check for alerts
                if not zscore.empty and not pd.isna(zscore.iloc[-1]):
                    current_zscore = zscore.iloc[-1]
                    _global_state.alert_engine.check_zscore(
                        current_zscore,
                        symbol=f"{y_symbol}/{x_symbol}"
                    )
                
                # ADF test on spread
                results["adf"] = adf_test(spread)
            
            # Correlation
            results["correlation"] = rolling_correlation(x, y, window)
    
    return results

# =============================================================================
# CHART FUNCTIONS
# =============================================================================
def create_price_chart(prices: dict, height: int = 300) -> go.Figure:
    """Create dual-axis price chart."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    colors = [COLORS["btc"], COLORS["eth"], COLORS["primary"], COLORS["secondary"]]
    symbols = list(prices.keys())
    
    for i, (symbol, series) in enumerate(prices.items()):
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                name=symbol,
                line=dict(color=colors[i % len(colors)], width=2),
            ),
            secondary_y=(i == 1)
        )
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=60, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#e2e8f0")),
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    if len(symbols) >= 1:
        fig.update_yaxes(title_text=symbols[0], secondary_y=False, gridcolor="#1e293b", 
                        title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    if len(symbols) >= 2:
        fig.update_yaxes(title_text=symbols[1], secondary_y=True, gridcolor="#1e293b",
                        title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    
    return fig


def create_spread_chart(spread: pd.Series, height: int = 250) -> go.Figure:
    """Create spread chart with mean line."""
    if spread is None or spread.empty:
        return go.Figure()
    
    mean_val = spread.mean()
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=spread.index,
            y=spread.values,
            name="Spread",
            line=dict(color=COLORS["primary"], width=2),
            fill="tozeroy",
            fillcolor="rgba(14, 165, 233, 0.1)",
        )
    )
    
    fig.add_hline(
        y=mean_val,
        line_dash="dash",
        line_color=COLORS["warning"],
        annotation_text=f"Mean: {mean_val:.2f}",
    )
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Spread", gridcolor="#1e293b", 
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_zscore_chart(zscore: pd.Series, height: int = 250) -> go.Figure:
    """Create z-score chart with threshold bands."""
    if zscore is None or zscore.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    # Z-score line
    fig.add_trace(
        go.Scatter(
            x=zscore.index,
            y=zscore.values,
            name="Z-Score",
            line=dict(color=COLORS["secondary"], width=2),
        )
    )
    
    # Threshold bands
    fig.add_hline(y=ZSCORE_UPPER_THRESHOLD, line_dash="dash", line_color=COLORS["error"],
                  annotation_text=f"+{ZSCORE_UPPER_THRESHOLD}")
    fig.add_hline(y=ZSCORE_LOWER_THRESHOLD, line_dash="dash", line_color=COLORS["error"],
                  annotation_text=f"{ZSCORE_LOWER_THRESHOLD}")
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["text_muted"])
    
    # Add fill between thresholds
    fig.add_hrect(
        y0=ZSCORE_LOWER_THRESHOLD, y1=ZSCORE_UPPER_THRESHOLD,
        fillcolor="rgba(139, 92, 246, 0.1)", line_width=0,
    )
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Z-Score", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_correlation_chart(correlation: pd.Series, height: int = 200) -> go.Figure:
    """Create rolling correlation chart."""
    if correlation is None or correlation.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=correlation.index,
            y=correlation.values,
            name="Correlation",
            line=dict(color=COLORS["success"], width=2),
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.1)",
        )
    )
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Correlation (ρ)", range=[-0.2, 1.1], gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


# =============================================================================
# ADVANCED QUANT ANALYTICS CHARTS
# =============================================================================

def create_zscore_histogram(zscore: pd.Series, height: int = 250) -> go.Figure:
    """
    Create Z-Score Distribution Histogram.
    Shows how often Z-score exceeds ±2 thresholds.
    Insight: Validates threshold selection, shows tail behavior.
    """
    if zscore is None or zscore.empty:
        return go.Figure()
    
    zscore_clean = zscore.dropna()
    
    # Calculate statistics
    above_2 = (zscore_clean > 2).sum()
    below_minus2 = (zscore_clean < -2).sum()
    total = len(zscore_clean)
    pct_extreme = ((above_2 + below_minus2) / total * 100) if total > 0 else 0
    
    fig = go.Figure()
    
    # Add histogram
    fig.add_trace(
        go.Histogram(
            x=zscore_clean.values,
            nbinsx=50,
            name="Z-Score",
            marker=dict(
                color="rgba(59, 130, 246, 0.7)",
                line=dict(color="#3b82f6", width=1)
            ),
        )
    )
    
    # Add threshold lines
    fig.add_vline(x=2, line_dash="dash", line_color="#ef4444", 
                  annotation_text="SELL (+2)", annotation_position="top right")
    fig.add_vline(x=-2, line_dash="dash", line_color="#10b981",
                  annotation_text="BUY (-2)", annotation_position="top left")
    fig.add_vline(x=0, line_dash="dot", line_color="#64748b")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=40, b=40),
        showlegend=False,
        font=dict(color="#e2e8f0"),
        annotations=[
            dict(
                x=0.95, y=0.95, xref="paper", yref="paper",
                text=f"Extreme signals: {pct_extreme:.1f}%",
                showarrow=False,
                font=dict(size=11, color="#94a3b8"),
                bgcolor="rgba(15, 23, 42, 0.8)",
                borderpad=4
            )
        ]
    )
    
    fig.update_xaxes(title_text="Z-Score", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Frequency", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_rolling_volatility_chart(spread: pd.Series, window: int = 20, height: int = 220) -> go.Figure:
    """
    Create Rolling Volatility of Spread chart.
    Detects regime shifts and unstable periods.
    Insight: Low vol + high |Z| = ideal; High vol = ignore signals.
    """
    if spread is None or spread.empty or len(spread) < window:
        return go.Figure()
    
    # Calculate rolling volatility (standard deviation)
    rolling_vol = spread.rolling(window=window).std()
    
    # Define volatility regimes
    vol_mean = rolling_vol.mean()
    vol_std = rolling_vol.std()
    high_vol_threshold = vol_mean + vol_std
    
    fig = go.Figure()
    
    # Color code by regime
    colors = ['#10b981' if v < vol_mean else ('#f59e0b' if v < high_vol_threshold else '#ef4444') 
              for v in rolling_vol.values]
    
    fig.add_trace(
        go.Scatter(
            x=rolling_vol.index,
            y=rolling_vol.values,
            name="Rolling Vol",
            mode="lines",
            line=dict(color="#8b5cf6", width=2),
            fill="tozeroy",
            fillcolor="rgba(139, 92, 246, 0.15)",
        )
    )
    
    # Add regime threshold
    fig.add_hline(y=vol_mean, line_dash="dash", line_color="#64748b",
                  annotation_text=f"Mean: {vol_mean:.4f}")
    fig.add_hline(y=high_vol_threshold, line_dash="dash", line_color="#ef4444",
                  annotation_text="High Vol Zone")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Volatility (σ)", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_rolling_hedge_ratio_chart(y_prices: pd.Series, x_prices: pd.Series, 
                                      window: int = 30, height: int = 220) -> go.Figure:
    """
    Create Rolling Hedge Ratio (β) chart.
    Shows structural change detection and model validity.
    Insight: Stable β = model valid; Drifting β = recalibration needed.
    """
    if y_prices is None or x_prices is None:
        return go.Figure()
    
    # Align prices
    y_clean = y_prices[~y_prices.index.duplicated(keep='last')]
    x_clean = x_prices[~x_prices.index.duplicated(keep='last')]
    common_idx = y_clean.index.intersection(x_clean.index)
    
    if len(common_idx) < window:
        return go.Figure()
    
    y = y_clean.loc[common_idx]
    x = x_clean.loc[common_idx]
    
    # Calculate rolling beta using rolling regression
    rolling_beta = []
    rolling_r2 = []
    indices = []
    
    for i in range(window, len(common_idx)):
        y_window = y.iloc[i-window:i]
        x_window = x.iloc[i-window:i]
        
        try:
            # Simple OLS: β = Cov(X,Y) / Var(X)
            cov = np.cov(y_window, x_window)[0, 1]
            var = np.var(x_window)
            beta = cov / var if var > 0 else 0
            
            # R-squared approximation
            corr = np.corrcoef(y_window, x_window)[0, 1]
            r2 = corr ** 2 if not np.isnan(corr) else 0
            
            rolling_beta.append(beta)
            rolling_r2.append(r2)
            indices.append(common_idx[i])
        except:
            continue
    
    if not rolling_beta:
        return go.Figure()
    
    fig = go.Figure()
    
    # Add beta line
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=rolling_beta,
            name="Hedge Ratio (β)",
            line=dict(color="#06b6d4", width=2),
        )
    )
    
    # Add mean line
    mean_beta = np.mean(rolling_beta)
    std_beta = np.std(rolling_beta)
    
    fig.add_hline(y=mean_beta, line_dash="dash", line_color="#64748b",
                  annotation_text=f"Mean β: {mean_beta:.4f}")
    
    # Add stability bands (±1 std)
    fig.add_hrect(y0=mean_beta - std_beta, y1=mean_beta + std_beta,
                  fillcolor="rgba(6, 182, 212, 0.1)", line_width=0,
                  annotation_text="Stable Zone", annotation_position="top right")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Hedge Ratio (β)", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_signal_efficacy_chart(zscore: pd.Series, spread: pd.Series, 
                                  lookahead: int = 5, height: int = 250) -> go.Figure:
    """
    Create Z-Score vs Future Spread Change scatter plot.
    Shows if high |Z| actually leads to mean reversion.
    Insight: Negative slope = strong mean reversion = good signal.
    """
    if zscore is None or spread is None or zscore.empty or spread.empty:
        return go.Figure()
    
    zscore_clean = zscore.dropna()
    spread_clean = spread.dropna()
    
    # Align indices
    common_idx = zscore_clean.index.intersection(spread_clean.index)
    if len(common_idx) < lookahead + 10:
        return go.Figure()
    
    z_aligned = zscore_clean.loc[common_idx]
    s_aligned = spread_clean.loc[common_idx]
    
    # Calculate future spread change
    z_values = []
    spread_changes = []
    colors = []
    
    for i in range(len(common_idx) - lookahead):
        z = z_aligned.iloc[i]
        future_change = s_aligned.iloc[i + lookahead] - s_aligned.iloc[i]
        
        z_values.append(z)
        spread_changes.append(future_change)
        
        # Color by Z-score region
        if z > 2:
            colors.append("#ef4444")  # Sell zone
        elif z < -2:
            colors.append("#10b981")  # Buy zone
        else:
            colors.append("#64748b")  # Neutral
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=z_values,
            y=spread_changes,
            mode="markers",
            marker=dict(
                size=6,
                color=colors,
                opacity=0.6,
            ),
            name="Signal Efficacy"
        )
    )
    
    # Add trend line using linear regression
    if len(z_values) > 10:
        z_arr = np.array(z_values)
        sc_arr = np.array(spread_changes)
        mask = ~np.isnan(z_arr) & ~np.isnan(sc_arr)
        if mask.sum() > 10:
            slope, intercept = np.polyfit(z_arr[mask], sc_arr[mask], 1)
            x_line = np.linspace(min(z_arr[mask]), max(z_arr[mask]), 100)
            y_line = slope * x_line + intercept
            
            fig.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_line,
                    mode="lines",
                    line=dict(color="#f59e0b", width=2, dash="dash"),
                    name=f"Trend (slope={slope:.4f})"
                )
            )
    
    # Add zero lines
    fig.add_hline(y=0, line_dash="dot", line_color="#64748b")
    fig.add_vline(x=0, line_dash="dot", line_color="#64748b")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#e2e8f0")),
        hovermode="closest",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(title_text="Z-Score at t", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text=f"Spread Change (t+{lookahead})", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


def create_zscore_with_signals_chart(zscore: pd.Series, height: int = 280) -> go.Figure:
    """
    Create Z-Score chart with Entry/Exit markers.
    Visual trading logic with clear signal identification.
    """
    if zscore is None or zscore.empty:
        return go.Figure()
    
    zscore_clean = zscore.dropna()
    
    fig = go.Figure()
    
    # Main Z-score line
    fig.add_trace(
        go.Scatter(
            x=zscore_clean.index,
            y=zscore_clean.values,
            name="Z-Score",
            line=dict(color="#3b82f6", width=2),
        )
    )
    
    # Find entry and exit points
    sell_entries = zscore_clean[zscore_clean > 2]
    buy_entries = zscore_clean[zscore_clean < -2]
    
    # Find exits (Z crosses back toward 0)
    exits = []
    in_position = None
    prev_z = None
    
    for idx, z in zscore_clean.items():
        if prev_z is not None:
            if in_position == "long" and prev_z < 0 and z >= 0:
                exits.append((idx, z))
                in_position = None
            elif in_position == "short" and prev_z > 0 and z <= 0:
                exits.append((idx, z))
                in_position = None
            elif z < -2 and in_position is None:
                in_position = "long"
            elif z > 2 and in_position is None:
                in_position = "short"
        prev_z = z
    
    # Add sell entry markers
    if not sell_entries.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_entries.index,
                y=sell_entries.values,
                mode="markers",
                marker=dict(size=10, color="#ef4444", symbol="triangle-down"),
                name="SELL Entry (Z > 2)"
            )
        )
    
    # Add buy entry markers
    if not buy_entries.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_entries.index,
                y=buy_entries.values,
                mode="markers",
                marker=dict(size=10, color="#10b981", symbol="triangle-up"),
                name="BUY Entry (Z < -2)"
            )
        )
    
    # Add exit markers
    if exits:
        exit_times = [e[0] for e in exits]
        exit_values = [e[1] for e in exits]
        fig.add_trace(
            go.Scatter(
                x=exit_times,
                y=exit_values,
                mode="markers",
                marker=dict(size=8, color="#f8fafc", symbol="circle", 
                           line=dict(width=2, color="#64748b")),
                name="EXIT (Z → 0)"
            )
        )
    
    # Add threshold bands
    fig.add_hrect(y0=2, y1=4, fillcolor="rgba(239, 68, 68, 0.1)", line_width=0)
    fig.add_hrect(y0=-4, y1=-2, fillcolor="rgba(16, 185, 129, 0.1)", line_width=0)
    fig.add_hline(y=2, line_dash="dash", line_color="#ef4444", annotation_text="+2")
    fig.add_hline(y=-2, line_dash="dash", line_color="#10b981", annotation_text="-2")
    fig.add_hline(y=0, line_dash="dot", line_color="#64748b")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        height=height,
        margin=dict(l=60, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                   font=dict(size=10, color="#e2e8f0")),
        hovermode="x unified",
        font=dict(color="#e2e8f0"),
    )
    
    fig.update_xaxes(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"))
    fig.update_yaxes(title_text="Z-Score", gridcolor="#1e293b",
                    title_font=dict(color="#e2e8f0"), tickfont=dict(color="#94a3b8"))
    
    return fig


# =============================================================================
# SIDEBAR - Premium Controls
# =============================================================================
with st.sidebar:
    # Logo and title
    st.markdown("""
    <div style="text-align: center; padding: 16px 0 24px 0;">
        <div style="font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
            <span style="background: linear-gradient(135deg, #f8fafc, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                GemsCap
            </span>
        </div>
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 2px; margin-top: 4px;">
            Quant Analytics
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Trading Pairs Section
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">Trading Pairs</div>
    </div>
    """, unsafe_allow_html=True)
    
    selected_symbols = st.multiselect(
        "Select Symbols",
        options=list(SYMBOL_DISPLAY.values()),
        default=["BTCUSDT", "ETHUSDT"],
        label_visibility="collapsed"
    )
    selected_symbols_lower = [s.lower() for s in selected_symbols]
    
    # Timeframe Section
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">Timeframe</div>
    </div>
    """, unsafe_allow_html=True)
    
    timeframe_options = {"1 Second": "1S", "1 Minute": "1T", "5 Minutes": "5T"}
    selected_tf_label = st.radio(
        "Select Timeframe",
        list(timeframe_options.keys()),
        index=1,
        label_visibility="collapsed",
        horizontal=True
    )
    selected_timeframe = timeframe_options[selected_tf_label]
    
    # Rolling Window
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">Rolling Window</div>
    </div>
    """, unsafe_allow_html=True)
    
    rolling_window = st.slider(
        "Window Size",
        min_value=MIN_WINDOW,
        max_value=MAX_WINDOW,
        value=ROLLING_WINDOW,
        step=10,
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    
    # Date/Time Filter Section
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">📅 Date Filter</div>
    </div>
    """, unsafe_allow_html=True)
    
    date_filter_mode = st.radio(
        "Filter Mode",
        ["All Time", "Today", "Last Hour", "Custom Range"],
        index=0,
        label_visibility="collapsed",
        horizontal=True
    )
    
    # Calculate date range based on selection
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if date_filter_mode == "All Time":
        filter_start = None
        filter_end = None
    elif date_filter_mode == "Today":
        filter_start = today_start
        filter_end = now
    elif date_filter_mode == "Last Hour":
        filter_start = now - timedelta(hours=1)
        filter_end = now
    else:  # Custom Range
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        
        col_from, col_to = st.columns(2)
        with col_from:
            st.markdown("<div style='font-size: 11px; color: #64748b; margin-bottom: 4px;'>From</div>", unsafe_allow_html=True)
            from_date = st.date_input("From Date", value=today_start.date(), label_visibility="collapsed", key="from_date")
            from_time = st.time_input("From Time", value=today_start.time(), label_visibility="collapsed", key="from_time")
        with col_to:
            st.markdown("<div style='font-size: 11px; color: #64748b; margin-bottom: 4px;'>To</div>", unsafe_allow_html=True)
            to_date = st.date_input("To Date", value=now.date(), label_visibility="collapsed", key="to_date")
            to_time = st.time_input("To Time", value=now.time(), label_visibility="collapsed", key="to_time")
        
        filter_start = datetime.combine(from_date, from_time)
        filter_end = datetime.combine(to_date, to_time)
    
    # Store filter in session state for use in analytics
    st.session_state["date_filter_start"] = filter_start
    st.session_state["date_filter_end"] = filter_end
    
    # Display active filter info
    if filter_start and filter_end:
        st.markdown(f"""
        <div style="background: rgba(6, 182, 212, 0.1); border-radius: 6px; padding: 8px; margin-top: 8px; text-align: center;">
            <div style="font-size: 10px; color: #64748b;">ACTIVE FILTER</div>
            <div style="font-size: 11px; color: #06b6d4; font-family: 'JetBrains Mono', monospace;">
                {filter_start.strftime('%H:%M:%S')} → {filter_end.strftime('%H:%M:%S')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(34, 197, 94, 0.1); border-radius: 6px; padding: 8px; margin-top: 8px; text-align: center;">
            <div style="font-size: 11px; color: #22c55e;">📊 Showing All Data</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    
    # Connection Controls
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">Connection</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        start_disabled = _global_state.is_running
        if st.button("▶️ Start", use_container_width=True, disabled=start_disabled, key="start_btn"):
            start_websocket(selected_symbols_lower, selected_timeframe)
            st.rerun()
    with col2:
        stop_disabled = not _global_state.is_running
        if st.button("⏹️ Stop", use_container_width=True, disabled=stop_disabled, key="stop_btn"):
            stop_websocket()
            st.rerun()
    
    if st.button("📂 Load Demo Data", use_container_width=True, key="demo_btn"):
        load_demo_data(selected_timeframe)
        st.rerun()
    
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    
    # Clear Cache / Reset Dashboard button
    if st.button("🗑️ Clear Cache / Reset", use_container_width=True, key="reset_btn", type="secondary"):
        # Stop any active connection first
        if _global_state.is_running:
            stop_websocket()
        # Reset all data - use try/except for backwards compatibility
        try:
            if hasattr(_global_state, 'reset_all'):
                _global_state.reset_all()
            else:
                # Fallback: manually clear components
                _global_state.store.clear()
                _global_state.alert_engine.clear_history()
                _global_state.resamplers = {}
                _global_state.tick_count = 0
                _global_state.last_update = None
        except Exception:
            # If all else fails, clear the cached resource to force fresh state
            get_global_state.clear()
        # Reset session state
        st.session_state.demo_mode = False
        st.session_state.demo_data_loaded = False
        if "date_filter_start" in st.session_state:
            del st.session_state["date_filter_start"]
        if "date_filter_end" in st.session_state:
            del st.session_state["date_filter_end"]
        st.toast("✅ Dashboard reset successfully!", icon="🗑️")
        st.rerun()
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Statistics Section
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">Live Statistics</div>
    </div>
    """, unsafe_allow_html=True)
    
    analytics = compute_analytics(
        selected_symbols, selected_timeframe, rolling_window,
        filter_start=st.session_state.get("date_filter_start"),
        filter_end=st.session_state.get("date_filter_end")
    )
    
    for symbol, stats in analytics.get("statistics", {}).items():
        if stats:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; margin: 8px 0;">
                <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">{symbol}</div>
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-size: 11px; color: #64748b;">PRICE</div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: #f8fafc;">${stats.last:,.2f}</div>
                    </div>
                    <div>
                        <div style="font-size: 11px; color: #64748b;">STD</div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: #94a3b8;">${stats.std:,.2f}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Hedge Ratio & ADF
    if analytics.get("hedge_ratio"):
        hr = analytics["hedge_ratio"]
        adf = analytics.get("adf")
        adf_status = "✅" if adf and adf.is_stationary else "❌"
        adf_pval = f"{adf.p_value:.4f}" if adf else "N/A"
        
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; margin: 8px 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <div>
                    <div style="font-size: 11px; color: #64748b;">HEDGE RATIO (β)</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; color: #06b6d4;">{hr.beta:.4f}</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #64748b;">R²</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; color: #f8fafc;">{hr.r_squared:.3f}</div>
                </div>
            </div>
            <div style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; margin-top: 8px;">
                <div style="font-size: 11px; color: #64748b;">ADF TEST</div>
                <div style="font-size: 13px; color: #f8fafc;">p-value: {adf_pval} {adf_status}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Correlation
    if analytics.get("correlation") is not None and not analytics["correlation"].empty:
        current_corr = analytics["correlation"].dropna().iloc[-1] if len(analytics["correlation"].dropna()) > 0 else 0
        corr_color = "#10b981" if current_corr > 0.8 else ("#f59e0b" if current_corr > 0.5 else "#ef4444")
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; margin: 8px 0; text-align: center;">
            <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">CORRELATION (ρ)</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 24px; color: {corr_color};">{current_corr:.3f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Alerts Section
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-title">🚨 Alerts</div>
    </div>
    """, unsafe_allow_html=True)
    
    alerts = _global_state.alert_engine.get_history(n=5)
    if alerts:
        for alert in alerts:
            icon = "🔴" if alert.severity == AlertSeverity.CRITICAL else "🟡"
            severity_class = "alert-critical" if alert.severity == AlertSeverity.CRITICAL else "alert-warning"
            st.markdown(f"""
            <div class="alert-card {severity_class}">
                <span class="alert-icon">{icon}</span>
                <div class="alert-content">
                    <div class="alert-message">{alert.message}</div>
                    <div class="alert-time">{alert.timestamp.strftime("%H:%M:%S")}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 16px; color: #64748b;">
            <div style="font-size: 24px; margin-bottom: 8px;">✓</div>
            <div style="font-size: 12px;">No active alerts</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Export Button
    if st.button("📥 Export to CSV", use_container_width=True, key="export_btn"):
        for symbol in selected_symbols:
            df = _global_state.store.get_dataframe(symbol, selected_timeframe)
            if not df.empty:
                csv = df.to_csv()
                st.download_button(
                    f"Download {symbol}",
                    csv,
                    f"{symbol}_{selected_timeframe}.csv",
                    "text/csv",
                    key=f"download_{symbol}"
                )
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Quick Guide Section
    with st.expander("📖 Quick Guide", expanded=False):
        st.markdown("""
        <div style="font-size: 12px; line-height: 1.6; color: #94a3b8;">
        
        **🎯 What is this?**  
        A real-time statistical arbitrage dashboard analyzing BTC/ETH price relationships.
        
        ---
        
        **📊 KPI Cards (Top Row)**  
        • **Ticks Received** - Live trade count  
        • **Bars Processed** - OHLCV bars created  
        • **Z-Score** - Current mean-reversion signal  
        • **Alerts** - Threshold breach count  
        
        ---
        
        **📈 Main Charts**  
        • **Price Chart** - Dual-axis BTC/ETH prices  
        • **Spread** - Price difference (Y - β×X)  
        • **Z-Score with Signals** - Entry/Exit markers  
        
        ---
        
        **🔬 Advanced Analytics**  
        • **Z-Score Histogram** - Distribution & tail risk  
        • **Rolling Volatility** - Regime detection  
        • **Rolling β** - Hedge ratio stability  
        • **Signal Efficacy** - Mean-reversion validation  
        
        ---
        
        **📌 Trading Logic**  
        • **BUY** when Z < -2 (spread undervalued)  
        • **SELL** when Z > +2 (spread overvalued)  
        • **EXIT** when Z crosses back to 0  
        
        ---
        
        **⚡ Quick Start**  
        1. Click **Start** to connect live data  
        2. Or click **Load Demo** for sample data  
        3. Adjust **Rolling Window** to tune sensitivity  
        
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# MAIN CONTENT - Premium Glassmorphism Layout
# =============================================================================

# Header with gradient title and status badge
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding: 0 4px;">
    <div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -1px;">
            <span style="background: linear-gradient(135deg, #f8fafc 0%, #06b6d4 50%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                📈 GemsCap Analytics
            </span>
        </h1>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b;">Real-time Statistical Arbitrage Dashboard</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Status badge
if _global_state.is_running:
    st.markdown("""
    <div class="status-badge status-live" style="margin-bottom: 16px;">
        <span>● LIVE</span> Receiving data from Binance
    </div>
    """, unsafe_allow_html=True)
elif st.session_state.demo_mode:
    st.markdown("""
    <div class="status-badge status-demo" style="margin-bottom: 16px;">
        📂 DEMO MODE
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="status-badge status-disconnected" style="margin-bottom: 16px;">
        ○ Not Connected
    </div>
    """, unsafe_allow_html=True)

# KPI Cards Section
st.markdown("""
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px;">
""", unsafe_allow_html=True)

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

# Calculate some change metrics for display
tick_rate = _global_state.tick_count  # ticks per session

with kpi_col1:
    # Show tick count with a rate indicator
    rate_text = "Active" if _global_state.is_running else "Idle"
    rate_class = "kpi-change-positive" if _global_state.is_running else "kpi-change-neutral"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Ticks Received</div>
        <div class="kpi-value">{_global_state.tick_count:,}</div>
        <div class="kpi-change {rate_class}">
            <span>●</span> {rate_text}
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col2:
    bar_counts = _global_state.store.bar_count()
    total_bars = sum(sum(tf.values()) for tf in bar_counts.values()) if bar_counts else 0
    # Show bar count with timeframe info
    tf_display = selected_timeframe.replace("S", "s").replace("T", "m")
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Bars Processed</div>
        <div class="kpi-value">{total_bars:,}</div>
        <div class="kpi-change kpi-change-neutral">
            <span>⏱</span> {tf_display} interval
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col3:
    if analytics.get("zscore") is not None and not analytics["zscore"].empty:
        current_z = analytics["zscore"].dropna().iloc[-1] if len(analytics["zscore"].dropna()) > 0 else 0
        signal = get_zscore_signal(current_z)
        
        # Determine colors and indicators based on z-score
        if current_z > 2:
            z_color = "#ef4444"
            change_class = "kpi-change-negative"
            signal_text = "↓ SELL Signal"
        elif current_z < -2:
            z_color = "#10b981"
            change_class = "kpi-change-positive"
            signal_text = "↑ BUY Signal"
        else:
            z_color = "#f8fafc"
            change_class = "kpi-change-neutral"
            signal_text = "— Neutral"
        
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Current Z-Score</div>
            <div class="kpi-value" style="color: {z_color};">{current_z:.2f}</div>
            <div class="kpi-change {change_class}">
                {signal_text}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Current Z-Score</div>
            <div class="kpi-value" style="color: #64748b;">—</div>
            <div class="kpi-change kpi-change-neutral">
                Awaiting data
            </div>
        </div>
        """, unsafe_allow_html=True)

with kpi_col4:
    alert_count = _global_state.alert_engine.alert_count
    alert_color = "#ef4444" if alert_count > 0 else "#10b981"
    alert_class = "kpi-change-negative" if alert_count > 0 else "kpi-change-positive"
    alert_text = f"{alert_count} Active" if alert_count > 0 else "✓ All Clear"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Alerts</div>
        <div class="kpi-value" style="color: {alert_color};">{alert_count}</div>
        <div class="kpi-change {alert_class}">
            {alert_text}
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# Charts Section with Glass Containers
st.markdown("""
<div class="chart-container">
    <div class="chart-title">Price Chart</div>
</div>
""", unsafe_allow_html=True)

if analytics.get("prices"):
    st.plotly_chart(
        create_price_chart(analytics["prices"], CHART_HEIGHT),
        use_container_width=True,
        key="price_chart"
    )
else:
    st.info("📊 Waiting for price data... Click **Start** to connect or **Load Demo Data** to test.")

# Spread and Z-Score in 2-column layout
col_spread, col_zscore = st.columns(2)

with col_spread:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Spread Analysis</div>
    </div>
    """, unsafe_allow_html=True)
    
    if analytics.get("spread") is not None:
        st.plotly_chart(
            create_spread_chart(analytics["spread"], 280),
            use_container_width=True,
            key="spread_chart"
        )
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Waiting for data from 2 symbols...</p>
        </div>
        """, unsafe_allow_html=True)

with col_zscore:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Z-Score with Entry/Exit Signals</div>
        <div style="font-size: 11px; color: #64748b; margin-top: -8px; margin-bottom: 8px;">
            🔴 SELL (Z > 2) • 🟢 BUY (Z < -2) • ⚪ EXIT (Z → 0)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if analytics.get("zscore") is not None and not analytics["zscore"].empty:
        st.plotly_chart(
            create_zscore_with_signals_chart(analytics["zscore"], 280),
            use_container_width=True,
            key="zscore_chart"
        )
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Need more data to calculate Z-score...</p>
        </div>
        """, unsafe_allow_html=True)

# Correlation Chart
st.markdown("""
<div class="chart-container">
    <div class="chart-title">Rolling Correlation</div>
</div>
""", unsafe_allow_html=True)

if analytics.get("correlation") is not None:
    st.plotly_chart(
        create_correlation_chart(analytics["correlation"], 220),
        use_container_width=True,
        key="correlation_chart"
    )
else:
    st.info("📊 Need data from 2 symbols to calculate correlation.")

# =============================================================================
# ADVANCED QUANT ANALYTICS SECTION
# =============================================================================
st.markdown("""
<div style="margin-top: 40px; margin-bottom: 20px;">
    <h2 style="font-size: 20px; font-weight: 600; color: #f8fafc; margin-bottom: 8px;">
        📊 Advanced Quant Analytics
    </h2>
    <p style="font-size: 13px; color: #64748b;">
        Statistical validation, regime detection, and signal efficacy analysis
    </p>
</div>
""", unsafe_allow_html=True)

# Row 1: Z-Score Distribution & Rolling Volatility
adv_col1, adv_col2 = st.columns(2)

with adv_col1:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Z-Score Distribution</div>
        <div style="font-size: 11px; color: #64748b; margin-top: -8px; margin-bottom: 12px;">
            Validates threshold selection • Shows tail behavior
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if analytics.get("zscore") is not None and not analytics["zscore"].empty:
        st.plotly_chart(
            create_zscore_histogram(analytics["zscore"], 250),
            use_container_width=True,
            key="zscore_histogram"
        )
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Need Z-score data...</p>
        </div>
        """, unsafe_allow_html=True)

with adv_col2:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Rolling Volatility of Spread</div>
        <div style="font-size: 11px; color: #64748b; margin-top: -8px; margin-bottom: 12px;">
            Regime detection • Low vol + high |Z| = ideal
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if analytics.get("spread") is not None and len(analytics["spread"].dropna()) >= 20:
        st.plotly_chart(
            create_rolling_volatility_chart(analytics["spread"], rolling_window, 250),
            use_container_width=True,
            key="rolling_vol"
        )
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Need more spread data...</p>
        </div>
        """, unsafe_allow_html=True)

# Row 2: Rolling Hedge Ratio & Signal Efficacy
adv_col3, adv_col4 = st.columns(2)

with adv_col3:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Rolling Hedge Ratio (β)</div>
        <div style="font-size: 11px; color: #64748b; margin-top: -8px; margin-bottom: 12px;">
            Structural change detection • Stable β = model valid
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if len(analytics.get("prices", {})) >= 2:
        symbol_list = list(analytics["prices"].keys())
        y_prices = analytics["prices"][symbol_list[0]]
        x_prices = analytics["prices"][symbol_list[1]]
        
        hedge_chart = create_rolling_hedge_ratio_chart(y_prices, x_prices, min(rolling_window, 30), 250)
        if hedge_chart.data:
            st.plotly_chart(hedge_chart, use_container_width=True, key="rolling_hedge")
        else:
            st.markdown("""
            <div style="padding: 40px; text-align: center; color: #64748b;">
                <p>Need more price data...</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Need 2 symbols...</p>
        </div>
        """, unsafe_allow_html=True)

with adv_col4:
    st.markdown("""
    <div class="chart-container">
        <div class="chart-title">Signal Efficacy (Z vs Future Δ)</div>
        <div style="font-size: 11px; color: #64748b; margin-top: -8px; margin-bottom: 12px;">
            Negative slope = strong mean reversion = good signal
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if analytics.get("zscore") is not None and analytics.get("spread") is not None:
        efficacy_chart = create_signal_efficacy_chart(analytics["zscore"], analytics["spread"], 5, 250)
        if efficacy_chart.data:
            st.plotly_chart(efficacy_chart, use_container_width=True, key="signal_efficacy")
        else:
            st.markdown("""
            <div style="padding: 40px; text-align: center; color: #64748b;">
                <p>Need more data...</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; color: #64748b;">
            <p>Need Z-score and spread data...</p>
        </div>
        """, unsafe_allow_html=True)


# Footer spacer
st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

# Auto-refresh when running
if _global_state.is_running:
    time.sleep(1)
    st.rerun()
