from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from opening_range_monitor.config import AlertsConfig
from opening_range_monitor.models import Signal

logger = logging.getLogger("opening_range_monitor.alerts")


class AlertChannel(Protocol):
    def send(self, signal: Signal) -> str:
        ...


class LogAlertChannel:
    def send(self, signal: Signal) -> str:
        message = (
            f"{signal.timestamp} {signal.ticker} {signal.signal} "
            f"@ {signal.price:.2f} via {signal.rule_name}: {signal.reason}"
        )
        logger.info(message)
        return message


@dataclass
class AlertManager:
    channels: list[AlertChannel] = field(default_factory=lambda: [LogAlertChannel()])

    @classmethod
    def from_config(cls, config: AlertsConfig) -> "AlertManager":
        channels: list[AlertChannel] = []
        if "log" in config.channels:
            channels.append(LogAlertChannel())
        return cls(channels=channels or [LogAlertChannel()])

    def dispatch(self, signals: list[Signal]) -> list[str]:
        messages: list[str] = []
        for signal in signals:
            if signal.signal == "HOLD":
                continue
            for channel in self.channels:
                messages.append(channel.send(signal))
        return messages
