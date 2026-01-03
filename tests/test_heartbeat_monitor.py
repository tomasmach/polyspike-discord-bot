"""Unit tests for heartbeat monitoring."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from src.handlers.heartbeat_monitor import HeartbeatMonitor


class TestHeartbeatMonitor(unittest.IsolatedAsyncioTestCase):
    """Test cases for HeartbeatMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock Discord bot
        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        # Create mock text channel
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()

        # Sample heartbeat payload
        self.heartbeat_payload = {
            "timestamp": time.time(),
            "uptime_seconds": 3600,
            "balance": 105.23,
            "open_positions": 2,
            "total_trades": 15,
        }

    def test_init(self):
        """Test HeartbeatMonitor initialization."""
        monitor = HeartbeatMonitor(self.mock_bot, timeout_seconds=90)

        self.assertEqual(monitor.timeout_seconds, 90)
        self.assertIsNone(monitor.get_last_heartbeat_time())
        self.assertFalse(monitor.is_bot_online())

    def test_update_heartbeat(self):
        """Test updating heartbeat timestamp."""
        monitor = HeartbeatMonitor(self.mock_bot)

        # Update heartbeat
        monitor.update(self.heartbeat_payload)

        # Verify timestamp was updated
        last_time = monitor.get_last_heartbeat_time()
        self.assertIsNotNone(last_time)
        self.assertAlmostEqual(last_time, self.heartbeat_payload["timestamp"], delta=0.1)

    def test_update_heartbeat_clears_alert_flag(self):
        """Test that receiving heartbeat clears alert flag."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot)

            # Simulate alert was sent
            monitor._alert_sent = True

            # Update heartbeat
            monitor.update(self.heartbeat_payload)

            # Verify alert flag was cleared
            self.assertFalse(monitor._alert_sent)

            # Verify log message
            logger_instance.info.assert_called()
            info_msg = logger_instance.info.call_args[0][0]
            self.assertIn("back online", info_msg)

    def test_is_bot_online_no_heartbeat(self):
        """Test is_bot_online when no heartbeat received."""
        monitor = HeartbeatMonitor(self.mock_bot)

        self.assertFalse(monitor.is_bot_online())

    def test_is_bot_online_recent_heartbeat(self):
        """Test is_bot_online with recent heartbeat."""
        monitor = HeartbeatMonitor(self.mock_bot, timeout_seconds=90)

        # Update with current time
        monitor.update(self.heartbeat_payload)

        # Bot should be online
        self.assertTrue(monitor.is_bot_online())

    def test_is_bot_online_old_heartbeat(self):
        """Test is_bot_online with old heartbeat."""
        monitor = HeartbeatMonitor(self.mock_bot, timeout_seconds=10)

        # Update with old time
        old_payload = self.heartbeat_payload.copy()
        old_payload["timestamp"] = time.time() - 20  # 20 seconds ago

        monitor.update(old_payload)

        # Bot should be offline (heartbeat too old)
        self.assertFalse(monitor.is_bot_online())

    def test_get_time_since_last_heartbeat_no_heartbeat(self):
        """Test get_time_since_last_heartbeat with no heartbeat."""
        monitor = HeartbeatMonitor(self.mock_bot)

        result = monitor.get_time_since_last_heartbeat()

        self.assertIsNone(result)

    def test_get_time_since_last_heartbeat_with_heartbeat(self):
        """Test get_time_since_last_heartbeat with heartbeat."""
        monitor = HeartbeatMonitor(self.mock_bot)

        # Update heartbeat
        monitor.update(self.heartbeat_payload)

        # Get time since heartbeat
        time_since = monitor.get_time_since_last_heartbeat()

        # Should be very small (just updated)
        self.assertIsNotNone(time_since)
        self.assertLess(time_since, 1.0)

    async def test_start_monitoring(self):
        """Test starting heartbeat monitoring."""
        monitor = HeartbeatMonitor(self.mock_bot)

        # Start monitoring
        await monitor.start_monitoring()

        # Verify monitoring task was created
        self.assertIsNotNone(monitor._monitoring_task)
        self.assertFalse(monitor._stopping)

        # Clean up
        await monitor.stop_monitoring()

    async def test_stop_monitoring(self):
        """Test stopping heartbeat monitoring."""
        monitor = HeartbeatMonitor(self.mock_bot)

        # Start monitoring
        await monitor.start_monitoring()

        # Stop monitoring
        await monitor.stop_monitoring()

        # Verify monitoring stopped
        self.assertTrue(monitor._stopping)
        self.assertIsNone(monitor._monitoring_task)

    async def test_start_monitoring_already_running(self):
        """Test starting monitoring when already running."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot)

            # Start monitoring
            await monitor.start_monitoring()

            # Try to start again
            await monitor.start_monitoring()

            # Verify warning was logged
            logger_instance.warning.assert_called()
            warning_msg = logger_instance.warning.call_args[0][0]
            self.assertIn("already running", warning_msg)

            # Clean up
            await monitor.stop_monitoring()

    async def test_heartbeat_alert_is_sent(self):
        """Test that heartbeat alert is sent correctly."""
        monitor = HeartbeatMonitor(self.mock_bot)
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=True)

        # Update heartbeat timestamp so alert has valid data
        monitor.update(self.heartbeat_payload)

        # Send alert directly
        await monitor._send_heartbeat_alert(100)

        # Verify alert was sent
        self.mock_bot.safe_send_to_channel.assert_awaited_once()
        call_args = self.mock_bot.safe_send_to_channel.call_args[0]
        embed = call_args[0]
        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("Heartbeat Alert", embed.title)

    def test_heartbeat_timeout_detection(self):
        """Test that timeout is correctly detected."""
        monitor = HeartbeatMonitor(self.mock_bot, timeout_seconds=90)

        # No heartbeat - should be offline
        self.assertFalse(monitor.is_bot_online())

        # Recent heartbeat - should be online
        monitor.update(self.heartbeat_payload)
        self.assertTrue(monitor.is_bot_online())

        # Old heartbeat - should be offline
        old_payload = self.heartbeat_payload.copy()
        old_payload["timestamp"] = time.time() - 100  # 100s ago > 90s timeout
        monitor.update(old_payload)
        self.assertFalse(monitor.is_bot_online())

    def test_alert_spam_prevention_flag(self):
        """Test that alert_sent flag prevents spam."""
        monitor = HeartbeatMonitor(self.mock_bot)

        # Initially no alert sent
        self.assertFalse(monitor._alert_sent)

        # Set alert sent flag
        monitor._alert_sent = True
        self.assertTrue(monitor._alert_sent)

        # Receive heartbeat - flag should be cleared
        monitor.update(self.heartbeat_payload)
        self.assertFalse(monitor._alert_sent)

    async def test_alert_channel_not_found(self):
        """Test alert when channel is not found."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot, timeout_seconds=1)
            self.mock_bot.get_channel = Mock(return_value=None)

            # Trigger alert
            await monitor._send_heartbeat_alert(100)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("not found", error_msg)

    async def test_alert_wrong_channel_type(self):
        """Test alert when channel is not TextChannel."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot)
            mock_voice_channel = Mock(spec=discord.VoiceChannel)
            self.mock_bot.get_channel = Mock(return_value=mock_voice_channel)

            # Trigger alert
            await monitor._send_heartbeat_alert(100)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("not a text channel", error_msg)

    async def test_alert_permission_denied(self):
        """Test alert when permission is denied."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot)
            self.mock_bot.get_channel = Mock(return_value=self.mock_channel)
            self.mock_channel.send.side_effect = discord.errors.Forbidden(
                Mock(), "Forbidden"
            )

            # Update heartbeat timestamp so alert has valid data
            monitor.update(self.heartbeat_payload)

            # Trigger alert
            await monitor._send_heartbeat_alert(100)

            # Verify permission error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Permission denied", error_msg)

    async def test_alert_http_exception(self):
        """Test alert when HTTP exception occurs."""
        with patch("src.handlers.heartbeat_monitor.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            monitor = HeartbeatMonitor(self.mock_bot)
            self.mock_bot.get_channel = Mock(return_value=self.mock_channel)
            self.mock_channel.send.side_effect = discord.errors.HTTPException(
                Mock(), "HTTP error"
            )

            # Update heartbeat timestamp
            monitor.update(self.heartbeat_payload)

            # Trigger alert
            await monitor._send_heartbeat_alert(100)

            # Verify HTTP error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send heartbeat alert", error_msg)


if __name__ == "__main__":
    unittest.main()
