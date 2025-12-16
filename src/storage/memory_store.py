"""
In-memory data store with thread-safe operations
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Deque, Any

import pandas as pd

from ..ingestion.data_normalizer import Tick
from ..processing.ohlcv import OHLCVBar


@dataclass
class SymbolData:
    """Container for all data related to a single symbol."""
    symbol: str
    ticks: Deque[Tick] = field(default_factory=lambda: deque(maxlen=100000))
    bars: Dict[str, Deque[OHLCVBar]] = field(default_factory=dict)  # timeframe -> bars
    
    def add_tick(self, tick: Tick) -> None:
        self.ticks.append(tick)
        
    def add_bar(self, timeframe: str, bar: OHLCVBar) -> None:
        if timeframe not in self.bars:
            self.bars[timeframe] = deque(maxlen=10000)
        self.bars[timeframe].append(bar)
        
    def get_ticks(self, n: Optional[int] = None) -> List[Tick]:
        if n is None:
            return list(self.ticks)
        return list(self.ticks)[-n:]
    
    def get_bars(self, timeframe: str, n: Optional[int] = None) -> List[OHLCVBar]:
        if timeframe not in self.bars:
            return []
        bars = list(self.bars[timeframe])
        if n is None:
            return bars
        return bars[-n:]


class MemoryStore:
    """
    Thread-safe in-memory storage for market data.
    
    Features:
    - Automatic pruning via deque maxlen
    - Thread-safe operations
    - Multi-symbol support
    - Multiple timeframes per symbol
    """
    
    def __init__(
        self,
        max_ticks: int = 100000,
        max_bars: int = 10000
    ):
        """
        Initialize memory store.
        
        Args:
            max_ticks: Maximum ticks to retain per symbol
            max_bars: Maximum bars to retain per symbol/timeframe
        """
        self._max_ticks = max_ticks
        self._max_bars = max_bars
        self._data: Dict[str, SymbolData] = {}
        self._lock = Lock()
        self._tick_count = 0
        self._last_update: Optional[datetime] = None
        
    def add_tick(self, tick: Tick) -> None:
        """Add a tick to the store."""
        with self._lock:
            symbol = tick.symbol.upper()
            if symbol not in self._data:
                self._data[symbol] = SymbolData(symbol=symbol)
                self._data[symbol].ticks = deque(maxlen=self._max_ticks)
            self._data[symbol].add_tick(tick)
            self._tick_count += 1
            self._last_update = tick.timestamp
            
    def add_bar(self, bar: OHLCVBar, timeframe: str) -> None:
        """Add an OHLCV bar to the store."""
        with self._lock:
            symbol = bar.symbol.upper()
            if symbol not in self._data:
                self._data[symbol] = SymbolData(symbol=symbol)
            if timeframe not in self._data[symbol].bars:
                self._data[symbol].bars[timeframe] = deque(maxlen=self._max_bars)
            self._data[symbol].add_bar(timeframe, bar)
            
    def get_ticks(self, symbol: str, n: Optional[int] = None) -> List[Tick]:
        """Get ticks for a symbol."""
        with self._lock:
            symbol = symbol.upper()
            if symbol not in self._data:
                return []
            return self._data[symbol].get_ticks(n)
            
    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        n: Optional[int] = None
    ) -> List[OHLCVBar]:
        """Get OHLCV bars for a symbol and timeframe."""
        with self._lock:
            symbol = symbol.upper()
            if symbol not in self._data:
                return []
            return self._data[symbol].get_bars(timeframe, n)
            
    def get_prices(
        self,
        symbol: str,
        timeframe: str,
        n: Optional[int] = None
    ) -> pd.Series:
        """Get close prices as a pandas Series."""
        bars = self.get_bars(symbol, timeframe, n)
        if not bars:
            return pd.Series(dtype=float)
        return pd.Series(
            [bar.close for bar in bars],
            index=[bar.timestamp for bar in bars],
            name=symbol
        )
        
    def get_dataframe(
        self,
        symbol: str,
        timeframe: str,
        n: Optional[int] = None
    ) -> pd.DataFrame:
        """Get OHLCV data as a pandas DataFrame."""
        bars = self.get_bars(symbol, timeframe, n)
        if not bars:
            return pd.DataFrame(columns=[
                "open", "high", "low", "close", "volume", "vwap", "trade_count"
            ])
        data = [bar.to_dict() for bar in bars]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
        
    def get_multi_symbol_prices(
        self,
        symbols: List[str],
        timeframe: str,
        n: Optional[int] = None
    ) -> pd.DataFrame:
        """Get close prices for multiple symbols as aligned DataFrame."""
        data = {}
        for symbol in symbols:
            prices = self.get_prices(symbol, timeframe, n)
            if not prices.empty:
                data[symbol] = prices
                
        if not data:
            return pd.DataFrame()
            
        return pd.DataFrame(data)
        
    @property
    def symbols(self) -> List[str]:
        """Get list of symbols in store."""
        with self._lock:
            return list(self._data.keys())
            
    @property
    def tick_count(self) -> int:
        """Get total tick count."""
        return self._tick_count
    
    @property
    def last_update(self) -> Optional[datetime]:
        """Get timestamp of last update."""
        return self._last_update
        
    def bar_count(self, symbol: Optional[str] = None, timeframe: Optional[str] = None) -> Dict:
        """Get bar counts."""
        with self._lock:
            if symbol:
                symbol = symbol.upper()
                if symbol in self._data:
                    if timeframe:
                        return {timeframe: len(self._data[symbol].bars.get(timeframe, []))}
                    return {tf: len(bars) for tf, bars in self._data[symbol].bars.items()}
                return {}
            return {
                s: {tf: len(bars) for tf, bars in data.bars.items()}
                for s, data in self._data.items()
            }
            
    def clear(self, symbol: Optional[str] = None) -> None:
        """Clear data from the store."""
        with self._lock:
            if symbol:
                symbol = symbol.upper()
                if symbol in self._data:
                    del self._data[symbol]
            else:
                self._data.clear()
                self._tick_count = 0
                
    def export_to_csv(
        self,
        symbol: str,
        timeframe: str,
        filepath: str
    ) -> bool:
        """Export data to CSV file."""
        try:
            df = self.get_dataframe(symbol, timeframe)
            if not df.empty:
                df.to_csv(filepath)
                return True
        except Exception:
            pass
        return False
