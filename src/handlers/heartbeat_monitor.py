"""Heartbeat monitoring for PolySpike trading bot.

This module monitors trading bot heartbeat messages and sends Discord alerts
when the bot appears to be offline (heartbeat timeout).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

import discord

if TYPE_CHECKING:
    from src.bot import PolySpikeBot

from src.utils.embeds import create_heartbeat_alert_embed
from src.utils.logger import get_logger


class HeartbeatMonitor:
    """Monitor trading bot heartbeat and send alerts on timeout.

    Tracks heartbeat messages from MQTT and sends Discord alerts when
    heartbeat is missing for longer than the timeout threshold.
    Prevents alert spam by only sending one alert per timeout event.
    """

    def __init__(self, bot: PolySpikeBot, timeout_seconds: int = 90):
        """Initialize heartbeat monitor.

        Args:
            bot: PolySpikeBot instance used to send timeout alerts to Discord.
            timeout_seconds: Heartbeat timeout in seconds (default: 90).
                Trading bot sends heartbeat every 30s, so 90s = 3 missed heartbeats.
        """
        self.bot: PolySpikeBot = bot
        self.timeout_seconds = timeout_seconds
        self.logger = get_logger()

        self._last_heartbeat_time: Optional[float] = None
        self._alert_sent = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stopping = False

    def update(self, payload: Dict[str, Any]) -> None:
        """Update heartbeat timestamp.

        Called when heartbeat message is received from MQTT.
        Clears alert flag so new alert can be sent if timeout happens again.

        Args:
            payload: MQTT heartbeat payload containing timestamp and bot status.
                Expected fields:
                - timestamp (float): Unix timestamp
                - uptime_seconds (int): Bot uptime
                - balance (float): Current balance
                - open_positions (int): Number of open positions
                - total_trades (int): Total trades count
        """
        timestamp = payload.get("timestamp", time.time())
        self._last_heartbeat_time = timestamp

        # Clear alert flag - bot is alive again
        if self._alert_sent:
            self.logger.info("Heartbeat received - trading bot is back online")
            self._alert_sent = False

        self.logger.debug(f"Heartbeat updated: {timestamp}")

    async def start_monitoring(self) -> None:
        """Start the heartbeat monitoring loop.

        Raises:
            RuntimeError: If monitoring is already running.
        """
        if self._monitoring_task is not None:
            self.logger.warning("Heartbeat monitoring already running")
            return

        self.logger.info(
            f"Starting heartbeat monitoring (timeout: {self.timeout_seconds}s)"
        )
        self._stopping = False
        self._monitoring_task = asyncio.create_task(self._check_heartbeat_loop())

    async def stop_monitoring(self) -> None:
        """Stop the heartbeat monitoring loop gracefully."""
        self.logger.info("Stopping heartbeat monitoring")
        self._stopping = True

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self._monitoring_task = None

    async def _check_heartbeat_loop(self) -> None:
        """Background loop that checks heartbeat every 30 seconds.

        Runs continuously until stopped. Checks if heartbeat is missing
        and sends Discord alert if timeout threshold is exceeded.
        """
        check_interval = 30  # seconds

        while not self._stopping:
            try:
                await asyncio.sleep(check_interval)

                if self._stopping:
                    break

                # Check if heartbeat is missing
                if self._last_heartbeat_time is None:
                    self.logger.debug("No heartbeat received yet - bot may not be started")
                    continue

                current_time = time.time()
                time_since_heartbeat = current_time - self._last_heartbeat_time

                if time_since_heartbeat > self.timeout_seconds:
                    # Heartbeat timeout - send alert (but only once)
                    if not self._alert_sent:
                        self.logger.warning(
                            f"Heartbeat timeout! Last heartbeat: {time_since_heartbeat:.0f}s ago "
                            f"(threshold: {self.timeout_seconds}s)"
                        )
                        await self._send_heartbeat_alert(time_since_heartbeat)
                        self._alert_sent = True
                else:
                    self.logger.debug(
                        f"Heartbeat OK (last: {time_since_heartbeat:.0f}s ago)"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Error in heartbeat monitoring loop: {e}", exc_info=True
                )

    async def _send_heartbeat_alert(self, missing_seconds: float) -> None:
        """Send heartbeat timeout alert to Discord.

        Args:
            missing_seconds: Seconds since last heartbeat.
        """
        try:
            # Create alert embed
            alert_data = {
                "last_heartbeat": self._last_heartbeat_time,
                "missing_seconds": int(missing_seconds),
            }
            embed = create_heartbeat_alert_embed(alert_data)

            # Send using safe send method (handles all error cases)
            success = await self.bot.safe_send_to_channel(embed)

            if success:
                self.logger.info("Heartbeat timeout alert sent to Discord")
            else:
                self.logger.error("Failed to send heartbeat alert (see errors above)")

        except Exception as e:
            self.logger.error(
                f"Unexpected error sending heartbeat alert: {e}", exc_info=True
            )

    def get_last_heartbeat_time(self) -> Optional[float]:
        """Get the last heartbeat timestamp.

        Returns:
            Last heartbeat timestamp, or None if no heartbeat received.
        """
        return self._last_heartbeat_time

    def is_bot_online(self) -> bool:
        """Check if trading bot is online based on heartbeat.

        Returns:
            True if heartbeat is recent (within timeout), False otherwise.
        """
        if self._last_heartbeat_time is None:
            return False

        current_time = time.time()
        time_since_heartbeat = current_time - self._last_heartbeat_time

        return time_since_heartbeat <= self.timeout_seconds

    def get_time_since_last_heartbeat(self) -> Optional[float]:
        """Get time elapsed since last heartbeat.

        Returns:
            Seconds since last heartbeat, or None if no heartbeat received.
        """
        if self._last_heartbeat_time is None:
            return None

        return time.time() - self._last_heartbeat_time
