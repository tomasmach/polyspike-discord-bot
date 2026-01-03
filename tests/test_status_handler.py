"""Unit tests for status event handlers."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord

from src.handlers.status_handler import (
    handle_bot_error,
    handle_bot_started,
    handle_bot_stopped,
)


class TestStatusHandlers(unittest.IsolatedAsyncioTestCase):
    """Test cases for status event handlers."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock Discord bot
        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        # Create mock text channel
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()

        # Sample payloads
        self.bot_started_payload = {
            "timestamp": 1735833600.123,
            "session_id": "20260102_180000",
            "config": {
                "initial_balance": 100.0,
                "spike_threshold": 0.03,
                "position_size": 5.0,
                "monitored_markets": 50,
            },
        }

        self.bot_stopped_payload = {
            "timestamp": 1735837200.789,
            "session_id": "20260102_180000",
            "final_stats": {
                "total_pnl": 5.23,
                "total_trades": 25,
                "win_rate": 0.72,
            },
        }

        self.bot_error_payload = {
            "timestamp": 1735833650.789,
            "error_type": "ConnectionError",
            "error_message": "Failed to connect to Polymarket API",
            "severity": "critical",
        }

    async def test_handle_bot_started_success(self):
        """Test successful bot started notification."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        # Call handler (creates async task)
        handle_bot_started(self.bot_started_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify channel was retrieved
        self.mock_bot.get_channel.assert_called_once_with(123456789)

        # Verify message was sent
        self.mock_channel.send.assert_called_once()
        call_kwargs = self.mock_channel.send.call_args[1]
        self.assertIn("embed", call_kwargs)
        embed = call_kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🚀 Bot Started")

    async def test_handle_bot_stopped_success(self):
        """Test successful bot stopped notification."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        # Call handler
        handle_bot_stopped(self.bot_stopped_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify channel was retrieved
        self.mock_bot.get_channel.assert_called_once_with(123456789)

        # Verify message was sent
        self.mock_channel.send.assert_called_once()
        call_kwargs = self.mock_channel.send.call_args[1]
        embed = call_kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🛑 Bot Stopped")

    async def test_handle_bot_error_success(self):
        """Test successful bot error notification."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        # Call handler
        handle_bot_error(self.bot_error_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify channel was retrieved
        self.mock_bot.get_channel.assert_called_once_with(123456789)

        # Verify message was sent
        self.mock_channel.send.assert_called_once()
        call_kwargs = self.mock_channel.send.call_args[1]
        embed = call_kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("CRITICAL", embed.title)

    async def test_handle_bot_started_channel_not_found(self):
        """Test bot started handler when channel is not found."""
        self.mock_bot.get_channel = Mock(return_value=None)

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Call handler
            handle_bot_started(self.bot_started_payload, self.mock_bot)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("not found", error_msg)
            self.assertIn("123456789", error_msg)

    async def test_handle_bot_stopped_wrong_channel_type(self):
        """Test bot stopped handler when channel is not TextChannel."""
        # Create mock voice channel (wrong type)
        mock_voice_channel = Mock(spec=discord.VoiceChannel)
        self.mock_bot.get_channel = Mock(return_value=mock_voice_channel)

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Call handler
            handle_bot_stopped(self.bot_stopped_payload, self.mock_bot)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("not a text channel", error_msg)

    async def test_handle_bot_error_permission_denied(self):
        """Test bot error handler when permission is denied."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)
        self.mock_channel.send.side_effect = discord.errors.Forbidden(
            Mock(), "Forbidden"
        )

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Call handler
            handle_bot_error(self.bot_error_payload, self.mock_bot)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify permission error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Permission denied", error_msg)

    async def test_handle_bot_started_http_exception(self):
        """Test bot started handler when HTTP exception occurs."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)
        self.mock_channel.send.side_effect = discord.errors.HTTPException(
            Mock(), "HTTP error"
        )

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Call handler
            handle_bot_started(self.bot_started_payload, self.mock_bot)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify HTTP error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Failed to send bot started notification", error_msg)

    async def test_handle_bot_error_with_different_severities(self):
        """Test bot error handler with different severity levels."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        severities = ["critical", "error", "warning"]

        for severity in severities:
            self.mock_channel.send.reset_mock()

            payload = {
                "error_type": "TestError",
                "error_message": f"Test {severity} message",
                "severity": severity,
            }

            with patch("src.handlers.status_handler.get_logger") as mock_logger:
                logger_instance = Mock()
                mock_logger.return_value = logger_instance

                # Call handler
                handle_bot_error(payload, self.mock_bot)

                # Wait for async task to complete
                await asyncio.sleep(0.1)

                # Verify correct severity was logged
                logger_instance.info.assert_called()
                info_msg = logger_instance.info.call_args[0][0]
                self.assertIn(severity, info_msg)

                # Verify message was sent
                self.mock_channel.send.assert_called_once()

    async def test_handle_bot_started_unexpected_exception(self):
        """Test bot started handler with unexpected exception."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)
        self.mock_channel.send.side_effect = RuntimeError("Unexpected error")

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            # Call handler
            handle_bot_started(self.bot_started_payload, self.mock_bot)

            # Wait for async task to complete
            await asyncio.sleep(0.1)

            # Verify unexpected error was logged
            logger_instance.error.assert_called()
            error_msg = logger_instance.error.call_args[0][0]
            self.assertIn("Unexpected error", error_msg)

    async def test_handlers_are_non_blocking(self):
        """Test that handlers return immediately (non-blocking)."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        # Create slow mock that takes time to send
        async def slow_send(*args, **kwargs):
            await asyncio.sleep(0.5)

        self.mock_channel.send = slow_send

        # Call handler and measure time
        import time

        start = time.time()
        handle_bot_started(self.bot_started_payload, self.mock_bot)
        duration = time.time() - start

        # Handler should return immediately (much less than 0.5s)
        self.assertLess(duration, 0.1)

    async def test_handle_bot_started_with_minimal_payload(self):
        """Test bot started handler with minimal payload."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        minimal_payload = {"timestamp": 1735833600.0}

        # Call handler - should not crash with missing fields
        handle_bot_started(minimal_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was still sent
        self.mock_channel.send.assert_called_once()

    async def test_handle_bot_stopped_with_minimal_payload(self):
        """Test bot stopped handler with minimal payload."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        minimal_payload = {}

        # Call handler - should not crash with missing fields
        handle_bot_stopped(minimal_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was still sent
        self.mock_channel.send.assert_called_once()

    async def test_handle_bot_error_with_minimal_payload(self):
        """Test bot error handler with minimal payload."""
        self.mock_bot.get_channel = Mock(return_value=self.mock_channel)

        minimal_payload = {}

        # Call handler - should not crash with missing fields
        handle_bot_error(minimal_payload, self.mock_bot)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Verify message was still sent
        self.mock_channel.send.assert_called_once()


class TestStatusHandlerLogging(unittest.IsolatedAsyncioTestCase):
    """Test cases for logging in status handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = Mock(spec=discord.Client)
        self.mock_bot.config = Mock()
        self.mock_bot.config.discord_channel_id = 123456789

        self.payload = {
            "timestamp": 1735833600.0,
            "session_id": "test_session",
        }

    async def test_handle_bot_started_logs_event(self):
        """Test that bot started handler logs the event."""
        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_bot_started(self.payload, self.mock_bot)

            # Wait for async task
            await asyncio.sleep(0.01)

            # Verify info log was called
            logger_instance.info.assert_called_with("Received bot started event")

    async def test_handle_bot_stopped_logs_event(self):
        """Test that bot stopped handler logs the event."""
        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_bot_stopped(self.payload, self.mock_bot)

            # Wait for async task
            await asyncio.sleep(0.01)

            # Verify info log was called
            logger_instance.info.assert_called_with("Received bot stopped event")

    async def test_handle_bot_error_logs_event_with_severity(self):
        """Test that bot error handler logs the event with severity."""
        payload = {
            "error_type": "TestError",
            "error_message": "Test message",
            "severity": "warning",
        }

        with patch("src.handlers.status_handler.get_logger") as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance

            handle_bot_error(payload, self.mock_bot)

            # Wait for async task
            await asyncio.sleep(0.01)

            # Verify info log was called with severity
            logger_instance.info.assert_called()
            log_msg = logger_instance.info.call_args[0][0]
            self.assertIn("warning", log_msg)


if __name__ == "__main__":
    unittest.main()
