"""Unit tests for balance event handlers."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from src.handlers.balance_handler import (
    clear_balance_cache,
    get_last_balance_data,
    get_startup_time,
    handle_balance_update,
    set_startup_time,
)


class TestBalanceHandler(unittest.IsolatedAsyncioTestCase):
    """Test cases for balance event handlers."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear balance cache and reset startup time before each test
        clear_balance_cache()
        set_startup_time(time.time())

        # Create mock Discord bot
        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789
        self.mock_bot.logger = Mock()

        # Create mock text channel
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()
        self.mock_channel.name = "test-channel"
        self.mock_channel.id = 123456789
        self.mock_bot.notification_channel = self.mock_channel
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=True)

        # Sample payload
        self.balance_payload = {
            "timestamp": time.time(),
            "balance": 100.20,
            "equity": 100.45,
            "available_balance": 90.20,
            "locked_in_positions": 10.0,
            "unrealized_pnl": 0.25,
            "total_pnl": 0.20,
            "update_reason": "periodic",
        }

    async def test_handle_balance_update_success(self):
        """Test successful balance update notification."""
        # Call handler
        handle_balance_update(self.balance_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was sent
        self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_handle_balance_update_filters_old_retained_messages(self):
        """Test that old retained messages are filtered out."""
        # Set startup time to now
        current_time = time.time()
        set_startup_time(current_time)

        # Create old message (10 minutes ago = 600 seconds)
        old_payload = self.balance_payload.copy()
        old_payload["timestamp"] = current_time - 600

        # Call handler with old message
        handle_balance_update(old_payload, self.mock_bot)

        # Wait for potential async task
        await asyncio.sleep(0.1)

        # Verify message was NOT sent (filtered out)
        self.mock_bot.safe_send_to_channel.assert_not_called()

    async def test_handle_balance_update_accepts_recent_messages(self):
        """Test that recent messages within threshold are accepted."""
        # Set startup time to now
        current_time = time.time()
        set_startup_time(current_time)

        # Create recent message (2 minutes ago = 120 seconds < 300 threshold)
        recent_payload = self.balance_payload.copy()
        recent_payload["timestamp"] = current_time - 120

        # Call handler with recent message
        handle_balance_update(recent_payload, self.mock_bot)

        # Wait for async task
        await asyncio.sleep(0.1)

        # Verify message WAS sent (within threshold)
        self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_handle_balance_update_caches_data(self):
        """Test that balance data is cached for slash command."""
        # Initially no cached data
        self.assertIsNone(get_last_balance_data())

        # Send balance update
        handle_balance_update(self.balance_payload, self.mock_bot)

        # Wait for handler to process
        await asyncio.sleep(0.1)

        # Verify data was cached
        cached_data = get_last_balance_data()
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["balance"], 100.20)
        self.assertEqual(cached_data["equity"], 100.45)
        self.assertEqual(cached_data["total_pnl"], 0.20)

    async def test_handle_balance_update_cache_is_copy(self):
        """Test that cached data is a copy, not reference."""
        # Send balance update
        handle_balance_update(self.balance_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Get cached data
        cached_data = get_last_balance_data()

        # Modify cached data
        cached_data["balance"] = 999.99

        # Get cached data again
        cached_data2 = get_last_balance_data()

        # Verify original cache was not modified
        self.assertEqual(cached_data2["balance"], 100.20)
        self.assertNotEqual(cached_data2["balance"], 999.99)

    async def test_handle_balance_update_channel_not_found(self):
        """Test balance update handler when channel is not found."""
        # Create safe_send_to_channel implementation that logs errors
        async def safe_send_to_channel(embed, content=None):
            if self.mock_bot.notification_channel is None:
                self.mock_bot.logger.error(
                    "Cannot send message: notification channel not set. "
                    "Channel may not exist or bot lacks access."
                )
                return False
            if not isinstance(self.mock_bot.notification_channel, discord.TextChannel):
                self.mock_bot.logger.error(
                    f"Cannot send message: channel is not a text channel"
                )
                return False
            return True

        self.mock_bot.safe_send_to_channel = safe_send_to_channel
        self.mock_bot.notification_channel = None

        handle_balance_update(self.balance_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify error was logged by bot
        self.mock_bot.logger.error.assert_called()
        error_msg = self.mock_bot.logger.error.call_args[0][0]
        self.assertIn("not set", error_msg)

    async def test_handle_balance_update_wrong_channel_type(self):
        """Test balance update handler when channel is not TextChannel."""
        # Create safe_send_to_channel implementation that logs errors
        async def safe_send_to_channel(embed, content=None):
            if self.mock_bot.notification_channel is None:
                self.mock_bot.logger.error(
                    "Cannot send message: notification channel not set. "
                    "Channel may not exist or bot lacks access."
                )
                return False
            if not isinstance(self.mock_bot.notification_channel, discord.TextChannel):
                self.mock_bot.logger.error(
                    f"Cannot send message: channel is not a text channel"
                )
                return False
            return True

        self.mock_bot.safe_send_to_channel = safe_send_to_channel
        self.mock_bot.notification_channel = Mock(spec=discord.VoiceChannel)

        handle_balance_update(self.balance_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify error was logged by bot
        self.mock_bot.logger.error.assert_called()
        error_msg = self.mock_bot.logger.error.call_args[0][0]
        self.assertIn("not a text channel", error_msg)

    async def test_handle_balance_update_permission_denied(self):
        """Test balance update handler when permission is denied."""
        # Create safe_send_to_channel implementation that logs errors
        async def safe_send_to_channel(embed, content=None):
            self.mock_bot.logger.error(
                f"Permission denied when sending to channel "
                f"(ID: {self.mock_bot.notification_channel.id}). "
                "Bot may be missing 'Send Messages' or 'Embed Links' permission."
            )
            return False

        self.mock_bot.safe_send_to_channel = safe_send_to_channel

        handle_balance_update(self.balance_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify permission error was logged by bot
        self.mock_bot.logger.error.assert_called()
        error_msg = self.mock_bot.logger.error.call_args[0][0]
        self.assertIn("Permission denied", error_msg)

    async def test_handle_balance_update_http_exception(self):
        """Test balance update handler when HTTP exception occurs."""
        # Create safe_send_to_channel implementation that logs errors
        async def safe_send_to_channel(embed, content=None):
            self.mock_bot.logger.error("Failed to send balance update notification (see errors above)")
            return False

        self.mock_bot.safe_send_to_channel = safe_send_to_channel

        handle_balance_update(self.balance_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify HTTP error was logged by bot
        self.mock_bot.logger.error.assert_called()
        error_msg = self.mock_bot.logger.error.call_args[0][0]
        self.assertIn("Failed to send", error_msg)

    async def test_handle_balance_update_with_missing_fields(self):
        """Test balance update handler with missing important fields."""
        # Payload with missing fields
        minimal_payload = {"timestamp": time.time()}

        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_balance_update(minimal_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify warning was logged for missing fields
            logger_instance.warning.assert_called()
            warning_msg = logger_instance.warning.call_args[0][0]
            self.assertIn("missing fields", warning_msg)

            # Verify message was still sent (with defaults)
            self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_handle_balance_update_unexpected_exception(self):
        """Test balance update handler with unexpected exception."""
        self.mock_bot.safe_send_to_channel = AsyncMock(side_effect=Exception("test error"))

        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_balance_update(self.balance_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify unexpected error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Unexpected error", error_msg)

    async def test_handler_is_non_blocking(self):
        """Test that handler returns immediately (non-blocking)."""
        # Create slow mock
        async def slow_send(*args, **kwargs):
            await asyncio.sleep(0.5)

        self.mock_bot.safe_send_to_channel = slow_send

        # Call handler and measure time
        start = time.time()
        handle_balance_update(self.balance_payload, self.mock_bot)
        duration = time.time() - start

        # Handler should return immediately (much less than 0.5s)
        self.assertLess(duration, 0.1)


class TestBalanceHandlerUtilities(unittest.IsolatedAsyncioTestCase):
    """Test cases for balance handler utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        clear_balance_cache()

        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789
        self.mock_bot.logger = Mock()
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()
        self.mock_channel.name = "test-channel"
        self.mock_channel.id = 123456789
        self.mock_bot.notification_channel = self.mock_channel
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=True)

    def test_set_startup_time(self):
        """Test setting the startup time."""
        test_time = 1735833600.0

        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            set_startup_time(test_time)

            # Verify startup time was set
            self.assertEqual(get_startup_time(), test_time)

            # Verify log was called
            logger_instance.info.assert_called()

    def test_get_startup_time(self):
        """Test getting the startup time."""
        # Set a known time
        test_time = 1735833600.0
        set_startup_time(test_time)

        # Verify we can get it back
        self.assertEqual(get_startup_time(), test_time)

    async def test_clear_balance_cache(self):
        """Test clearing the balance cache."""
        # Add balance data
        payload = {
            "timestamp": time.time(),
            "balance": 100.0,
            "equity": 100.0,
            "total_pnl": 0.0,
        }
        handle_balance_update(payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify data was cached
        self.assertIsNotNone(get_last_balance_data())

        # Clear cache
        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            clear_balance_cache()

            # Verify cache is empty
            self.assertIsNone(get_last_balance_data())

            # Verify log was called
            logger_instance.info.assert_called()

    async def test_get_last_balance_data_returns_none_when_empty(self):
        """Test that get_last_balance_data returns None when cache is empty."""
        clear_balance_cache()

        result = get_last_balance_data()

        self.assertIsNone(result)

    async def test_balance_cache_updates_with_latest_data(self):
        """Test that balance cache updates with latest data."""
        # Send first balance update
        payload1 = {
            "timestamp": time.time(),
            "balance": 100.0,
            "equity": 100.0,
            "total_pnl": 0.0,
        }
        handle_balance_update(payload1, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify first data
        cached = get_last_balance_data()
        self.assertEqual(cached["balance"], 100.0)

        # Send second balance update
        payload2 = {
            "timestamp": time.time(),
            "balance": 105.50,
            "equity": 105.75,
            "total_pnl": 5.50,
        }
        handle_balance_update(payload2, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify cache was updated
        cached = get_last_balance_data()
        self.assertEqual(cached["balance"], 105.50)
        self.assertEqual(cached["total_pnl"], 5.50)


class TestBalanceHandlerLogging(unittest.IsolatedAsyncioTestCase):
    """Test cases for logging in balance handler."""

    def setUp(self):
        """Set up test fixtures."""
        clear_balance_cache()
        set_startup_time(time.time())

        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        self.balance_payload = {
            "timestamp": time.time(),
            "balance": 100.0,
            "equity": 100.0,
            "total_pnl": 0.0,
        }

    async def test_handle_balance_update_logs_event(self):
        """Test that balance update handler logs the event."""
        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_balance_update(self.balance_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Verify info log was called
            logger_instance.info.assert_called()
            info_calls = [call[0][0] for call in logger_instance.info.call_args_list]
            self.assertTrue(
                any("Received balance update event" in call for call in info_calls)
            )

    async def test_handle_balance_update_logs_old_message_filter(self):
        """Test that old message filtering is logged."""
        current_time = time.time()
        set_startup_time(current_time)

        # Create old message
        old_payload = self.balance_payload.copy()
        old_payload["timestamp"] = current_time - 600

        with patch("src.handlers.balance_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_balance_update(old_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Verify debug log was called for filtering
            logger_instance.debug.assert_called()
            debug_msg = logger_instance.debug.call_args[0][0]
            self.assertIn("Ignoring old retained", debug_msg)


if __name__ == "__main__":
    unittest.main()
