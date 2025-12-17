"""
Rule-based alert system for quantitative signals
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Callable
from collections import deque
import threading


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    ZSCORE_HIGH = "zscore_high"
    ZSCORE_LOW = "zscore_low"
    PRICE_SPIKE = "price_spike"
    CORRELATION_BREAK = "correlation_break"
    STATIONARITY_CHANGE = "stationarity_change"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert data structure."""
    timestamp: datetime
    alert_type: AlertType
    message: str
    severity: AlertSeverity
    value: float
    symbol: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.alert_type.value,
            "message": self.message,
            "severity": self.severity.value,
            "value": self.value,
            "symbol": self.symbol,
            "metadata": self.metadata,
        }


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    name: str
    alert_type: AlertType
    condition: Callable[[float], bool]
    message_template: str
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_seconds: int = 60


class AlertEngine:
    """
    Rule-based alert engine for quantitative signals.
    
    Features:
    - Configurable alert rules
    - Cooldown to prevent alert spam
    - Alert history
    - Callbacks for new alerts
    """
    
    DEFAULT_RULES = [
        AlertRule(
            name="zscore_high",
            alert_type=AlertType.ZSCORE_HIGH,
            condition=lambda z: z > 2.0,
            message_template="Z-score exceeded upper threshold: {value:.2f}",
            severity=AlertSeverity.WARNING,
            cooldown_seconds=60,
        ),
        AlertRule(
            name="zscore_low",
            alert_type=AlertType.ZSCORE_LOW,
            condition=lambda z: z < -2.0,
            message_template="Z-score exceeded lower threshold: {value:.2f}",
            severity=AlertSeverity.WARNING,
            cooldown_seconds=60,
        ),
        AlertRule(
            name="zscore_critical_high",
            alert_type=AlertType.ZSCORE_HIGH,
            condition=lambda z: z > 3.0,
            message_template="Z-score critically high: {value:.2f}",
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=120,
        ),
        AlertRule(
            name="zscore_critical_low",
            alert_type=AlertType.ZSCORE_LOW,
            condition=lambda z: z < -3.0,
            message_template="Z-score critically low: {value:.2f}",
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=120,
        ),
    ]
    
    def __init__(
        self,
        max_history: int = 100,
        default_cooldown: int = 60
    ):
        """
        Initialize alert engine.
        
        Args:
            max_history: Maximum alerts to retain in history
            default_cooldown: Default cooldown in seconds
        """
        self._rules: List[AlertRule] = list(self.DEFAULT_RULES)
        self._history: deque = deque(maxlen=max_history)
        self._last_triggered: Dict[str, datetime] = {}
        self._callbacks: List[Callable[[Alert], None]] = []
        self._lock = threading.Lock()
        self._default_cooldown = default_cooldown
        
    def add_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule."""
        self._rules.append(rule)
        
    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False
        
    def on_alert(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback for new alerts."""
        self._callbacks.append(callback)
        
    def check_zscore(
        self,
        zscore: float,
        symbol: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[Alert]:
        """
        Check z-score against configured rules.
        
        Args:
            zscore: Current z-score value
            symbol: Symbol associated with the signal
            timestamp: Timestamp of the signal
            
        Returns:
            List of triggered alerts
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        triggered = []
        
        with self._lock:
            for rule in self._rules:
                if rule.alert_type not in (AlertType.ZSCORE_HIGH, AlertType.ZSCORE_LOW):
                    continue
                    
                # Check condition
                try:
                    if not rule.condition(zscore):
                        continue
                except Exception:
                    continue
                    
                # Check cooldown
                rule_key = f"{rule.name}_{symbol or 'all'}"
                last_time = self._last_triggered.get(rule_key)
                if last_time:
                    elapsed = (timestamp - last_time).total_seconds()
                    if elapsed < rule.cooldown_seconds:
                        continue
                        
                # Create alert
                alert = Alert(
                    timestamp=timestamp,
                    alert_type=rule.alert_type,
                    message=rule.message_template.format(value=zscore),
                    severity=rule.severity,
                    value=zscore,
                    symbol=symbol,
                )
                
                # Record and trigger
                self._history.append(alert)
                self._last_triggered[rule_key] = timestamp
                triggered.append(alert)
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(alert)
                    except Exception:
                        pass
                        
        return triggered
        
    def check_custom(
        self,
        value: float,
        condition: Callable[[float], bool],
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        symbol: Optional[str] = None,
        alert_type: AlertType = AlertType.CUSTOM,
        cooldown_key: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[Alert]:
        """
        Check a custom condition.
        
        Args:
            value: Value to check
            condition: Function that returns True if alert should trigger
            message: Alert message
            severity: Alert severity
            symbol: Associated symbol
            alert_type: Type of alert
            cooldown_key: Key for cooldown tracking
            timestamp: Timestamp
            
        Returns:
            Alert if triggered, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        try:
            if not condition(value):
                return None
        except Exception:
            return None
            
        with self._lock:
            # Check cooldown
            if cooldown_key:
                last_time = self._last_triggered.get(cooldown_key)
                if last_time:
                    elapsed = (timestamp - last_time).total_seconds()
                    if elapsed < self._default_cooldown:
                        return None
                        
            # Create alert
            alert = Alert(
                timestamp=timestamp,
                alert_type=alert_type,
                message=message,
                severity=severity,
                value=value,
                symbol=symbol,
            )
            
            self._history.append(alert)
            if cooldown_key:
                self._last_triggered[cooldown_key] = timestamp
                
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(alert)
                except Exception:
                    pass
                    
            return alert
            
    def get_history(
        self,
        n: Optional[int] = None,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None
    ) -> List[Alert]:
        """
        Get alert history.
        
        Args:
            n: Number of most recent alerts
            severity: Filter by severity
            alert_type: Filter by type
            
        Returns:
            List of alerts
        """
        with self._lock:
            alerts = list(self._history)
            
        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
            
        # Sort by timestamp descending
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        if n:
            return alerts[:n]
        return alerts
        
    def clear_history(self) -> None:
        """Clear alert history."""
        with self._lock:
            self._history.clear()
    
    def clear_all(self) -> None:
        """Clear all alert state including history and cooldown tracking."""
        with self._lock:
            self._history.clear()
            self._last_triggered.clear()
            
    @property
    def alert_count(self) -> int:
        """Get total alerts in history."""
        return len(self._history)
