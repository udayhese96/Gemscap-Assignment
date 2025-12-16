"""
Time-series resampler for converting ticks to OHLCV bars
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from collections import defaultdict

import pandas as pd

from ..ingestion.data_normalizer import Tick
from .ohlcv import OHLCVBar, BarBuilder


class TimeSeriesResampler:
    """
    Resamples tick data into OHLCV bars at specified intervals.
    
    Supports multiple timeframes and symbols simultaneously.
    """
    
    TIMEFRAME_SECONDS = {
        "1S": 1,
        "1T": 60,      # 1 minute
        "5T": 300,     # 5 minutes
        "15T": 900,    # 15 minutes
        "1H": 3600,    # 1 hour
    }
    
    def __init__(self, timeframe: str = "1T"):
        """
        Initialize resampler.
        
        Args:
            timeframe: Pandas-style timeframe string (1S, 1T, 5T, etc.)
        """
        self.timeframe = timeframe
        self._interval_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 60)
        
        # Bar builders per symbol
        self._builders: Dict[str, BarBuilder] = {}
        
        # Current bar timestamps per symbol
        self._current_bar_time: Dict[str, datetime] = {}
        
        # Completed bars per symbol
        self._completed_bars: Dict[str, List[OHLCVBar]] = defaultdict(list)
        
        # Callbacks for new bars
        self._callbacks: List[Callable[[OHLCVBar], None]] = []
        
    def on_bar(self, callback: Callable[[OHLCVBar], None]) -> None:
        """Register a callback for completed bars."""
        self._callbacks.append(callback)
        
    def _get_bar_timestamp(self, tick_time: datetime) -> datetime:
        """Calculate the bar timestamp for a given tick time."""
        # Floor to interval boundary
        epoch = datetime(1970, 1, 1)
        total_seconds = (tick_time - epoch).total_seconds()
        bar_seconds = (total_seconds // self._interval_seconds) * self._interval_seconds
        return epoch + timedelta(seconds=bar_seconds)
    
    def add_tick(self, tick: Tick) -> Optional[OHLCVBar]:
        """
        Add a tick and return completed bar if interval boundary crossed.
        
        Args:
            tick: Tick to add
            
        Returns:
            Completed OHLCVBar if a bar was finished, None otherwise
        """
        symbol = tick.symbol
        bar_time = self._get_bar_timestamp(tick.timestamp)
        
        # Initialize builder if needed
        if symbol not in self._builders:
            self._builders[symbol] = BarBuilder(symbol=symbol)
            self._current_bar_time[symbol] = bar_time
            
        # Check if we've crossed into a new bar
        completed_bar = None
        if bar_time > self._current_bar_time.get(symbol, bar_time):
            # Complete the previous bar
            builder = self._builders[symbol]
            completed_bar = builder.build(self._current_bar_time[symbol])
            
            if completed_bar:
                self._completed_bars[symbol].append(completed_bar)
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(completed_bar)
                    except Exception:
                        pass
                        
            # Reset for new bar
            builder.reset()
            self._current_bar_time[symbol] = bar_time
            
        # Add tick to current bar
        self._builders[symbol].add_tick(tick)
        
        return completed_bar
    
    def get_bars(self, symbol: str, n: Optional[int] = None) -> List[OHLCVBar]:
        """
        Get completed bars for a symbol.
        
        Args:
            symbol: Symbol to get bars for
            n: Number of most recent bars (None for all)
            
        Returns:
            List of OHLCVBar objects
        """
        bars = self._completed_bars.get(symbol.upper(), [])
        if n is not None:
            return bars[-n:]
        return bars
    
    def get_dataframe(self, symbol: str, n: Optional[int] = None) -> pd.DataFrame:
        """
        Get bars as a pandas DataFrame.
        
        Args:
            symbol: Symbol to get bars for
            n: Number of most recent bars
            
        Returns:
            DataFrame with OHLCV columns
        """
        bars = self.get_bars(symbol, n)
        if not bars:
            return pd.DataFrame(columns=[
                "timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count"
            ])
            
        data = [bar.to_dict() for bar in bars]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
    
    def get_current_bar(self, symbol: str) -> Optional[OHLCVBar]:
        """Get the current (incomplete) bar for a symbol."""
        symbol = symbol.upper()
        if symbol in self._builders and symbol in self._current_bar_time:
            return self._builders[symbol].build(self._current_bar_time[symbol])
        return None
    
    def clear(self, symbol: Optional[str] = None) -> None:
        """Clear accumulated bars."""
        if symbol:
            symbol = symbol.upper()
            self._completed_bars[symbol] = []
            if symbol in self._builders:
                self._builders[symbol].reset()
        else:
            self._completed_bars.clear()
            for builder in self._builders.values():
                builder.reset()
                
    @property
    def symbols(self) -> List[str]:
        """Get list of symbols with data."""
        return list(self._builders.keys())
    
    @property
    def bar_count(self) -> Dict[str, int]:
        """Get count of bars per symbol."""
        return {s: len(bars) for s, bars in self._completed_bars.items()}


def resample_ticks_to_bars(
    ticks: List[Tick],
    timeframe: str = "1T"
) -> Dict[str, pd.DataFrame]:
    """
    Batch resample a list of ticks to OHLCV bars.
    
    Args:
        ticks: List of Tick objects
        timeframe: Pandas-style timeframe string
        
    Returns:
        Dictionary mapping symbol to DataFrame of bars
    """
    resampler = TimeSeriesResampler(timeframe)
    
    for tick in ticks:
        resampler.add_tick(tick)
        
    result = {}
    for symbol in resampler.symbols:
        result[symbol] = resampler.get_dataframe(symbol)
        
    return result
