"""
OHLCV Bar data structure for candlestick representation
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..ingestion.data_normalizer import Tick


@dataclass
class OHLCVBar:
    """
    OHLCV (Open, High, Low, Close, Volume) bar representation.
    """
    symbol: str
    timestamp: datetime  # Bar open time
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float = 0.0  # Volume-weighted average price
    trade_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bar to dictionary for DataFrame creation."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
            "trade_count": self.trade_count,
        }


@dataclass
class BarBuilder:
    """
    Accumulates ticks and builds OHLCV bars.
    """
    symbol: str
    bar_start: Optional[datetime] = None
    open: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    close: float = 0.0
    volume: float = 0.0
    vwap_numerator: float = 0.0  # Sum of price * quantity
    trade_count: int = 0
    
    def add_tick(self, tick: Tick) -> None:
        """Add a tick to the current bar."""
        if self.bar_start is None:
            self.bar_start = tick.timestamp
            self.open = tick.price
            self.high = tick.price
            self.low = tick.price
            
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.quantity
        self.vwap_numerator += tick.price * tick.quantity
        self.trade_count += 1
        
    def build(self, bar_timestamp: datetime) -> Optional[OHLCVBar]:
        """
        Build the OHLCV bar from accumulated ticks.
        
        Args:
            bar_timestamp: The normalized bar timestamp (start of the period)
            
        Returns:
            OHLCVBar or None if no ticks accumulated
        """
        if self.trade_count == 0:
            return None
            
        vwap = self.vwap_numerator / self.volume if self.volume > 0 else self.close
        
        return OHLCVBar(
            symbol=self.symbol,
            timestamp=bar_timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            vwap=vwap,
            trade_count=self.trade_count,
        )
        
    def reset(self) -> None:
        """Reset the bar builder for a new bar."""
        self.bar_start = None
        self.open = 0.0
        self.high = 0.0
        self.low = float("inf")
        self.close = 0.0
        self.volume = 0.0
        self.vwap_numerator = 0.0
        self.trade_count = 0
