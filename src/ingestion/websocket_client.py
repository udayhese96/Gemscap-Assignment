"""
WebSocket client for Binance Futures real-time trade data
"""
import asyncio
import json
import logging
from typing import Callable, List, Optional, Set
from datetime import datetime

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
except ImportError:
    websockets = None

from .data_normalizer import Tick, normalize_tick

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """
    Async WebSocket client for Binance Futures trade streams.
    
    Usage:
        client = BinanceWebSocketClient()
        client.on_tick(my_callback)
        await client.connect(["btcusdt", "ethusdt"])
    """
    
    BASE_URL = "wss://fstream.binance.com/ws"
    
    def __init__(
        self,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
        reconnect_multiplier: float = 2.0,
    ):
        """
        Initialize WebSocket client.
        
        Args:
            reconnect_delay: Initial delay before reconnection
            max_reconnect_delay: Maximum delay between reconnection attempts
            reconnect_multiplier: Multiplier for exponential backoff
        """
        self._callbacks: List[Callable[[Tick], None]] = []
        self._websockets: dict = {}
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        
        # Reconnection settings
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._reconnect_multiplier = reconnect_multiplier
        
        # Stats
        self._tick_count = 0
        self._last_tick_time: Optional[datetime] = None
        self._connected_symbols: Set[str] = set()
        
    def on_tick(self, callback: Callable[[Tick], None]) -> None:
        """
        Register a callback to be called for each incoming tick.
        
        Args:
            callback: Function that accepts a Tick object
        """
        self._callbacks.append(callback)
        
    def remove_callback(self, callback: Callable[[Tick], None]) -> None:
        """Remove a previously registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    async def connect(self, symbols: List[str]) -> None:
        """
        Connect to Binance WebSocket for specified symbols.
        
        Args:
            symbols: List of symbol names (e.g., ["btcusdt", "ethusdt"])
        """
        if websockets is None:
            raise ImportError("websockets package is required. Install with: pip install websockets")
            
        self._running = True
        
        # Create a task for each symbol
        for symbol in symbols:
            symbol_lower = symbol.lower()
            task = asyncio.create_task(self._connect_symbol(symbol_lower))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            
        # Wait for all connections to be established
        await asyncio.sleep(0.5)
        
    async def _connect_symbol(self, symbol: str) -> None:
        """Connect to WebSocket for a single symbol with reconnection logic."""
        url = f"{self.BASE_URL}/{symbol}@trade"
        delay = self._reconnect_delay
        
        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self._websockets[symbol] = ws
                    self._connected_symbols.add(symbol.upper())
                    logger.info(f"Connected to {symbol.upper()}")
                    delay = self._reconnect_delay  # Reset delay on successful connection
                    
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_message(message)
                        
            except ConnectionClosed as e:
                logger.warning(f"Connection closed for {symbol}: {e}")
            except WebSocketException as e:
                logger.error(f"WebSocket error for {symbol}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error for {symbol}: {e}")
            finally:
                self._connected_symbols.discard(symbol.upper())
                if symbol in self._websockets:
                    del self._websockets[symbol]
                    
            # Reconnection logic with exponential backoff
            if self._running:
                logger.info(f"Reconnecting to {symbol} in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * self._reconnect_multiplier, self._max_reconnect_delay)
                
    async def _handle_message(self, message: str) -> None:
        """Parse message and dispatch to callbacks."""
        try:
            data = json.loads(message)
            tick = normalize_tick(data)
            
            if tick:
                self._tick_count += 1
                self._last_tick_time = tick.timestamp
                
                # Call all registered callbacks
                for callback in self._callbacks:
                    try:
                        # Handle both sync and async callbacks
                        result = callback(tick)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            
    async def disconnect(self) -> None:
        """Disconnect from all WebSocket connections."""
        self._running = False
        
        # Close all WebSocket connections
        for symbol, ws in list(self._websockets.items()):
            try:
                await ws.close()
                logger.info(f"Disconnected from {symbol.upper()}")
            except Exception as e:
                logger.error(f"Error closing {symbol}: {e}")
                
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        self._websockets.clear()
        self._connected_symbols.clear()
        
    @property
    def is_connected(self) -> bool:
        """Check if connected to at least one stream."""
        return len(self._connected_symbols) > 0
    
    @property
    def connected_symbols(self) -> Set[str]:
        """Get set of currently connected symbols."""
        return self._connected_symbols.copy()
    
    @property
    def tick_count(self) -> int:
        """Get total number of ticks received."""
        return self._tick_count
    
    @property
    def last_tick_time(self) -> Optional[datetime]:
        """Get timestamp of last received tick."""
        return self._last_tick_time


class SyncWebSocketClient:
    """
    Synchronous wrapper for the async WebSocket client.
    Useful for integration with Streamlit's synchronous execution model.
    """
    
    def __init__(self):
        self._client = BinanceWebSocketClient()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread = None
        self._started = False
        
    def on_tick(self, callback: Callable[[Tick], None]) -> None:
        """Register a tick callback."""
        self._client.on_tick(callback)
        
    def start(self, symbols: List[str]) -> None:
        """Start WebSocket connection in background thread."""
        if self._started:
            return
            
        import threading
        
        def run_loop():
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._loop.run_until_complete(self._client.connect(symbols))
                self._loop.run_forever()
            except Exception as e:
                logger.error(f"Event loop error: {e}")
            finally:
                try:
                    self._loop.close()
                except:
                    pass
            
        self._thread = threading.Thread(target=run_loop, daemon=True, name="WebSocket-Loop")
        self._thread.start()
        self._started = True
        
        # Wait a moment for connection to establish
        import time
        time.sleep(0.5)
        
    def stop(self) -> None:
        """Stop WebSocket connection."""
        if not self._started:
            return
            
        self._client._running = False
        
        if self._loop and self._loop.is_running():
            try:
                # Schedule disconnect on the event loop
                future = asyncio.run_coroutine_threadsafe(
                    self._client.disconnect(), 
                    self._loop
                )
                # Wait up to 2 seconds for disconnect
                try:
                    future.result(timeout=2.0)
                except:
                    pass
                    
                # Stop the loop
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception as e:
                logger.error(f"Error stopping WebSocket: {e}")
                
        self._started = False
            
    @property
    def is_connected(self) -> bool:
        return self._client.is_connected and self._started
    
    @property
    def tick_count(self) -> int:
        return self._client.tick_count

