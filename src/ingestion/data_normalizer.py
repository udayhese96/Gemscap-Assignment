"""
Data normalizer for Binance WebSocket tick data
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class Tick:
    """Normalized tick data structure"""
    symbol: str
    timestamp: datetime
    price: float
    quantity: float
    trade_id: Optional[int] = None
    is_buyer_maker: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tick to dictionary for DataFrame creation"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "price": self.price,
            "quantity": self.quantity,
            "trade_id": self.trade_id,
            "is_buyer_maker": self.is_buyer_maker,
        }


def normalize_tick(raw_message: Dict[str, Any]) -> Optional[Tick]:
    """
    Normalize raw Binance WebSocket trade message to Tick dataclass.
    
    Binance trade message format:
    {
        "e": "trade",       # Event type
        "E": 1672515782136, # Event time
        "T": 1672515782136, # Trade time (use this for timestamp)
        "s": "BTCUSDT",     # Symbol
        "t": 12345,         # Trade ID
        "p": "0.001",       # Price
        "q": "100",         # Quantity
        "m": true           # Is buyer maker
    }
    
    Args:
        raw_message: Raw JSON message from WebSocket
        
    Returns:
        Normalized Tick object or None if invalid message
    """
    try:
        # Check if it's a trade event
        if raw_message.get("e") != "trade":
            return None
        
        # Parse timestamp - use trade time (T) for accuracy
        trade_time_ms = raw_message.get("T") or raw_message.get("E")
        if trade_time_ms is None:
            return None
            
        timestamp = datetime.utcfromtimestamp(trade_time_ms / 1000.0)
        
        # Parse other fields
        symbol = raw_message.get("s", "").upper()
        price = float(raw_message.get("p", 0))
        quantity = float(raw_message.get("q", 0))
        trade_id = raw_message.get("t")
        is_buyer_maker = raw_message.get("m")
        
        if not symbol or price <= 0:
            return None
            
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            quantity=quantity,
            trade_id=trade_id,
            is_buyer_maker=is_buyer_maker,
        )
        
    except (KeyError, ValueError, TypeError) as e:
        # Log error in production
        return None


def normalize_from_ndjson(record: Dict[str, Any]) -> Optional[Tick]:
    """
    Normalize tick from NDJSON format (as saved by the browser collector).
    
    NDJSON format:
    {"symbol":"BTCUSDT","ts":"2025-12-15T09:34:06.419Z","price":89795.4,"size":0.003}
    
    Args:
        record: Parsed JSON record from NDJSON file
        
    Returns:
        Normalized Tick object or None if invalid
    """
    try:
        timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        # Convert to naive UTC datetime for consistency
        timestamp = timestamp.replace(tzinfo=None)
        
        return Tick(
            symbol=record["symbol"].upper(),
            timestamp=timestamp,
            price=float(record["price"]),
            quantity=float(record.get("size", record.get("quantity", 0))),
        )
    except (KeyError, ValueError, TypeError):
        return None
