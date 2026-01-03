"""Unit tests for trading event handlers."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from src.handlers.trading_handler import (
    clear_seen_trades,
    get_seen_trades_count,
    handle_position_opened,
    handle_trade_completed,
)


class TestTradingHandlers(unittest.IsolatedAsyncioTestCase):
    """Test cases for trading event handlers."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear seen trades before each test
        clear_seen_trades()

        # Create mock Discord bot
        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        # Create mock text channel
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()
        self.mock_bot.notification_channel = self.mock_channel
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=True)

        # Sample payloads
        self.position_opened_payload = {
            "timestamp": 1735833715.789,
            "token_id": "0x1234abcd5678",
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "position_size": 5.0,
            "reason": "spike_down",
            "spike_magnitude": 0.032,
        }

        self.trade_completed_payload = {
            "timestamp": 1735833745.012,
            "trade_id": "a1b2c3d4-5678-9abc",
            "token_id": "0x1234abcd5678",
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "exit_price": 0.4992,
            "size": 5.0,
            "pnl": 0.20,
            "pnl_pct": 0.04,
            "duration_seconds": 30,
            "reason": "take_profit",
        }

    async def test_handle_position_opened_success(self):
        """Test successful position opened notification."""
        # Call handler
        handle_position_opened(self.position_opened_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was sent
        self.mock_bot.safe_send_to_channel.assert_called_once()
        call_args = self.mock_bot.safe_send_to_channel.call_args[0]
        embed = call_args[0]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🟢 Position Opened")

    async def test_handle_trade_completed_success(self):
        """Test successful trade completed notification."""
        # Call handler
        handle_trade_completed(self.trade_completed_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was sent
        self.mock_bot.safe_send_to_channel.assert_called_once()
        call_args = self.mock_bot.safe_send_to_channel.call_args[0]
        embed = call_args[0]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "💰 Trade Completed")

    async def test_handle_trade_completed_duplicate_detection(self):
        """Test that duplicate trade_id is ignored."""
        # Send first trade
        handle_trade_completed(self.trade_completed_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify first message was sent
        self.assertEqual(self.mock_bot.safe_send_to_channel.call_count, 1)

        # Reset mock
        self.mock_bot.safe_send_to_channel.reset_mock()

        # Send duplicate with same trade_id
        handle_trade_completed(self.trade_completed_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify duplicate was NOT sent
        self.mock_bot.safe_send_to_channel.assert_not_called()

    async def test_handle_trade_completed_different_trade_ids(self):
        """Test that different trade_ids are both sent."""
        # Send first trade
        handle_trade_completed(self.trade_completed_payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Send second trade with different trade_id
        payload2 = self.trade_completed_payload.copy()
        payload2["trade_id"] = "different-trade-id-xyz"

        handle_trade_completed(payload2, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify both messages were sent
        self.assertEqual(self.mock_bot.safe_send_to_channel.call_count, 2)

    async def test_handle_trade_completed_without_trade_id(self):
        """Test trade completed without trade_id field."""
        # Payload without trade_id
        payload = self.trade_completed_payload.copy()
        del payload["trade_id"]

        # Call handler - should still send notification
        handle_trade_completed(payload, self.mock_bot)
        await asyncio.sleep(0.1)

        # Verify message was sent
        self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_seen_trades_cache_pruning(self):
        """Test that seen trades cache is pruned when limit exceeded."""
        # Mock the MAX limit to a small value for testing
        with patch("src.handlers.trading_handler._MAX_SEEN_TRADES", 5):
            # Add 10 different trades
            for i in range(10):
                payload = self.trade_completed_payload.copy()
                payload["trade_id"] = f"trade-id-{i}"
                handle_trade_completed(payload, self.mock_bot)
                await asyncio.sleep(0.05)

            # Verify cache size is limited
            cache_size = get_seen_trades_count()
            self.assertLessEqual(cache_size, 5)

    async def test_handle_position_opened_channel_not_found(self):
        """Test position opened handler when channel is not found."""
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=False)

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_position_opened(self.position_opened_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send position opened notification", error_msg)

    async def test_handle_trade_completed_wrong_channel_type(self):
        """Test trade completed handler when channel is not TextChannel."""
        # In new architecture, channel type validation happens at startup in on_ready
        # This test verifies the behavior when safe_send_to_channel fails for any reason
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=False)

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_trade_completed(self.trade_completed_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send trade completed notification", error_msg)

    async def test_handle_position_opened_permission_denied(self):
        """Test position opened handler when permission is denied."""
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=False)

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_position_opened(self.position_opened_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify permission error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send position opened notification", error_msg)

    async def test_handle_trade_completed_http_exception(self):
        """Test trade completed handler when HTTP exception occurs."""
        self.mock_bot.safe_send_to_channel = AsyncMock(return_value=False)

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_trade_completed(self.trade_completed_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify HTTP error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send trade completed notification", error_msg)

    async def test_handle_position_opened_with_missing_fields(self):
        """Test position opened handler with missing important fields."""
        # Payload with missing fields
        minimal_payload = {"timestamp": 1735833715.0}

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_position_opened(minimal_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify warning was logged for missing fields
            logger_instance.warning.assert_called()
            warning_msg = logger_instance.warning.call_args[0][0]
            self.assertIn("missing fields", warning_msg)

            # Verify message was still sent (with defaults)
            self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_handle_trade_completed_with_missing_fields(self):
        """Test trade completed handler with missing important fields."""
        # Payload with missing fields
        minimal_payload = {
            "trade_id": "test-trade-123",
            "timestamp": 1735833745.0,
        }

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_trade_completed(minimal_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify warning was logged for missing fields
            logger_instance.warning.assert_called()
            warning_msg = logger_instance.warning.call_args[0][0]
            self.assertIn("missing fields", warning_msg)

            # Verify message was still sent (with defaults)
            self.mock_bot.safe_send_to_channel.assert_called_once()

    async def test_handlers_are_non_blocking(self):
        """Test that handlers return immediately (non-blocking)."""
        # Create slow mock
        async def slow_send(*args, **kwargs):
            await asyncio.sleep(0.5)

        self.mock_bot.safe_send_to_channel = slow_send

        # Call handler and measure time
        import time

        start = time.time()
        handle_position_opened(self.position_opened_payload, self.mock_bot)
        duration = time.time() - start

        # Handler should return immediately (much less than 0.5s)
        self.assertLess(duration, 0.1)

    async def test_handle_position_opened_unexpected_exception(self):
        """Test position opened handler with unexpected exception."""
        self.mock_bot.safe_send_to_channel = AsyncMock(side_effect=Exception("test error"))

        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_position_opened(self.position_opened_payload, self.mock_bot)
            await asyncio.sleep(0.1)

            # Verify unexpected error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("test error", error_msg)


class TestTradingHandlerLogging(unittest.IsolatedAsyncioTestCase):
    """Test cases for logging in trading handlers."""

    def setUp(self):
        """Set up test fixtures."""
        clear_seen_trades()

        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        self.position_payload = {
            "timestamp": 1735833715.0,
            "market_name": "Test Market",
            "entry_price": 0.5,
            "position_size": 10.0,
        }

        self.trade_payload = {
            "timestamp": 1735833745.0,
            "trade_id": "test-trade-123",
            "market_name": "Test Market",
            "pnl": 1.0,
            "pnl_pct": 0.1,
        }

    async def test_handle_position_opened_logs_event(self):
        """Test that position opened handler logs the event."""
        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_position_opened(self.position_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Verify info log was called
            logger_instance.info.assert_called_with("Received position opened event")

    async def test_handle_trade_completed_logs_event(self):
        """Test that trade completed handler logs the event."""
        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_trade_completed(self.trade_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Verify info log was called
            logger_instance.info.assert_called_with("Received trade completed event")

    async def test_handle_trade_completed_logs_duplicate(self):
        """Test that duplicate trade_id is logged."""
        with patch("src.handlers.trading_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Send first trade
            handle_trade_completed(self.trade_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Reset mock
            logger_instance.reset_mock()

            # Send duplicate
            handle_trade_completed(self.trade_payload, self.mock_bot)
            await asyncio.sleep(0.01)

            # Verify debug log for duplicate was called
            logger_instance.debug.assert_called()
            debug_msg = logger_instance.debug.call_args[0][0]
            self.assertIn("duplicate", debug_msg.lower())
            self.assertIn("test-trade-123", debug_msg)


class TestCacheManagement(unittest.IsolatedAsyncioTestCase):
    """Test cases for trade ID cache management."""

    def setUp(self):
        """Set up test fixtures."""
        clear_seen_trades()

    def tearDown(self):
        """Clean up after tests."""
        clear_seen_trades()

    async def test_clear_seen_trades(self):
        """Test clearing the seen trades cache."""
        mock_bot = Mock()

        # Add some trades
        for i in range(5):
            payload = {"trade_id": f"trade-{i}"}
            handle_trade_completed(payload, mock_bot)

        # Wait for tasks
        await asyncio.sleep(0.01)

        # Verify trades were added
        self.assertGreater(get_seen_trades_count(), 0)

        # Clear cache
        clear_seen_trades()

        # Verify cache is empty
        self.assertEqual(get_seen_trades_count(), 0)

    async def test_get_seen_trades_count(self):
        """Test getting the seen trades count."""
        mock_bot = Mock()

        # Initially zero
        self.assertEqual(get_seen_trades_count(), 0)

        # Add trades
        for i in range(3):
            payload = {"trade_id": f"trade-{i}"}
            handle_trade_completed(payload, mock_bot)

        # Wait for tasks
        await asyncio.sleep(0.01)

        # Verify count
        self.assertEqual(get_seen_trades_count(), 3)


if __name__ == "__main__":
    unittest.main()
