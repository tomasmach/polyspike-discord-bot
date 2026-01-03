"""Unit tests for Discord embed builders."""

import time
import unittest
from datetime import datetime

import discord

from src.utils.embeds import (
    create_balance_update_embed,
    create_bot_error_embed,
    create_bot_started_embed,
    create_bot_stopped_embed,
    create_heartbeat_alert_embed,
    create_position_opened_embed,
    create_trade_completed_embed,
)


class TestPositionOpenedEmbed(unittest.TestCase):
    """Test cases for create_position_opened_embed()."""

    def test_position_opened_with_all_fields(self):
        """Test embed creation with all fields present."""
        payload = {
            "timestamp": 1735833715.789,
            "token_id": "0x1234abcd5678",
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "position_size": 5.0,
            "reason": "spike_down",
            "spike_magnitude": 0.032
        }

        embed = create_position_opened_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🟢 Position Opened")
        self.assertEqual(embed.description, "Will Trump win 2024?")
        self.assertEqual(embed.color.value, 0x00FF00)  # Green
        self.assertEqual(len(embed.fields), 4)
        self.assertEqual(embed.fields[0].value, "0.4800")
        self.assertEqual(embed.fields[1].value, "$5.00")
        self.assertIn("Spike Down", embed.fields[2].value)
        self.assertIn("+3.20%", embed.fields[3].value)

    def test_position_opened_without_spike_magnitude(self):
        """Test embed creation without spike_magnitude field."""
        payload = {
            "timestamp": 1735833715.789,
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "position_size": 5.0,
            "reason": "spike_down"
        }

        embed = create_position_opened_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(len(embed.fields), 3)  # No spike magnitude field

    def test_position_opened_with_missing_fields(self):
        """Test embed creation with missing optional fields."""
        payload = {}

        embed = create_position_opened_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.description, "Unknown Market")
        self.assertIn("0.0000", embed.fields[0].value)
        self.assertIn("$0.00", embed.fields[1].value)


class TestTradeCompletedEmbed(unittest.TestCase):
    """Test cases for create_trade_completed_embed()."""

    def test_trade_completed_profitable(self):
        """Test embed creation for profitable trade."""
        payload = {
            "timestamp": 1735833745.012,
            "trade_id": "a1b2c3d4-5678",
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "exit_price": 0.4992,
            "size": 5.0,
            "pnl": 0.20,
            "pnl_pct": 0.04,
            "duration_seconds": 30,
            "reason": "take_profit"
        }

        embed = create_trade_completed_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "💰 Trade Completed")
        self.assertEqual(embed.color.value, 0x00FF00)  # Green for profit
        self.assertIn("+0.20", embed.fields[2].value)
        self.assertIn("+4.00%", embed.fields[3].value)
        self.assertIn("30s", embed.fields[4].value)

    def test_trade_completed_loss(self):
        """Test embed creation for losing trade."""
        payload = {
            "timestamp": 1735833745.012,
            "market_name": "Will Trump win 2024?",
            "entry_price": 0.4800,
            "exit_price": 0.4600,
            "pnl": -0.42,
            "pnl_pct": -0.087,
            "duration_seconds": 120,
            "reason": "stop_loss"
        }

        embed = create_trade_completed_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.color.value, 0xFF0000)  # Red for loss
        self.assertIn("-0.42", embed.fields[2].value)
        self.assertIn("-8.70%", embed.fields[3].value)
        self.assertIn("2m", embed.fields[4].value)

    def test_trade_completed_duration_formatting(self):
        """Test duration formatting for different time ranges."""
        # Test seconds only
        payload = {"pnl": 0.0, "duration_seconds": 45}
        embed = create_trade_completed_embed(payload)
        self.assertIn("45s", embed.fields[4].value)

        # Test minutes and seconds
        payload = {"pnl": 0.0, "duration_seconds": 150}
        embed = create_trade_completed_embed(payload)
        self.assertIn("2m 30s", embed.fields[4].value)

        # Test hours, minutes and seconds
        payload = {"pnl": 0.0, "duration_seconds": 3665}
        embed = create_trade_completed_embed(payload)
        self.assertIn("1h 1m 5s", embed.fields[4].value)


class TestBalanceUpdateEmbed(unittest.TestCase):
    """Test cases for create_balance_update_embed()."""

    def test_balance_update_with_all_fields(self):
        """Test embed creation with all fields present."""
        payload = {
            "timestamp": 1735833750.345,
            "balance": 100.20,
            "equity": 100.45,
            "available_balance": 90.20,
            "locked_in_positions": 10.0,
            "unrealized_pnl": 0.25,
            "total_pnl": 0.20,
            "update_reason": "periodic"
        }

        embed = create_balance_update_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "💵 Balance Update")
        self.assertIn("Periodic", embed.description)
        self.assertEqual(embed.color.value, 0x3498DB)  # Blue
        self.assertEqual(len(embed.fields), 6)
        self.assertIn("$100.20", embed.fields[0].value)
        self.assertIn("$100.45", embed.fields[1].value)
        self.assertIn("$90.20", embed.fields[2].value)
        self.assertIn("$10.00", embed.fields[3].value)
        self.assertIn("+0.25", embed.fields[4].value)
        self.assertIn("+0.20", embed.fields[5].value)

    def test_balance_update_with_negative_pnl(self):
        """Test embed with negative P&L values."""
        payload = {
            "balance": 95.50,
            "equity": 94.75,
            "unrealized_pnl": -0.75,
            "total_pnl": -4.50
        }

        embed = create_balance_update_embed(payload)

        self.assertIn("-0.75", embed.fields[4].value)
        self.assertIn("-4.50", embed.fields[5].value)


class TestBotStartedEmbed(unittest.TestCase):
    """Test cases for create_bot_started_embed()."""

    def test_bot_started_with_all_fields(self):
        """Test embed creation with all fields present."""
        payload = {
            "timestamp": 1735833600.123,
            "session_id": "20260102_180000",
            "config": {
                "initial_balance": 100.0,
                "spike_threshold": 0.03,
                "position_size": 5.0,
                "monitored_markets": 50
            }
        }

        embed = create_bot_started_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🚀 Bot Started")
        self.assertIn("20260102_180000", embed.description)
        self.assertEqual(embed.color.value, 0x00FF00)  # Green
        self.assertEqual(len(embed.fields), 4)
        self.assertIn("$100.00", embed.fields[0].value)
        self.assertIn("3.0%", embed.fields[1].value)
        self.assertIn("$5.00", embed.fields[2].value)
        self.assertIn("50", embed.fields[3].value)

    def test_bot_started_with_missing_config(self):
        """Test embed creation with missing config fields."""
        payload = {
            "session_id": "test_session",
            "config": {}
        }

        embed = create_bot_started_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("test_session", embed.description)


class TestBotStoppedEmbed(unittest.TestCase):
    """Test cases for create_bot_stopped_embed()."""

    def test_bot_stopped_with_all_fields(self):
        """Test embed creation with all fields present."""
        payload = {
            "timestamp": 1735837200.789,
            "session_id": "20260102_180000",
            "final_stats": {
                "total_pnl": 5.23,
                "total_trades": 25,
                "win_rate": 0.72
            }
        }

        embed = create_bot_stopped_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🛑 Bot Stopped")
        self.assertIn("20260102_180000", embed.description)
        self.assertEqual(embed.color.value, 0xFF0000)  # Red
        self.assertEqual(len(embed.fields), 3)
        self.assertIn("+5.23", embed.fields[0].value)
        self.assertIn("25", embed.fields[1].value)
        self.assertIn("72.0%", embed.fields[2].value)

    def test_bot_stopped_with_negative_pnl(self):
        """Test embed with negative total P&L."""
        payload = {
            "session_id": "test",
            "final_stats": {
                "total_pnl": -3.50,
                "total_trades": 10,
                "win_rate": 0.40
            }
        }

        embed = create_bot_stopped_embed(payload)

        self.assertIn("-3.50", embed.fields[0].value)


class TestBotErrorEmbed(unittest.TestCase):
    """Test cases for create_bot_error_embed()."""

    def test_bot_error_critical(self):
        """Test embed creation for critical error."""
        payload = {
            "timestamp": 1735833650.789,
            "error_type": "ConnectionError",
            "error_message": "Failed to connect to Polymarket API",
            "severity": "critical"
        }

        embed = create_bot_error_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("CRITICAL", embed.title)
        self.assertEqual(embed.description, "Failed to connect to Polymarket API")
        self.assertEqual(embed.color.value, 0xFF0000)  # Red
        self.assertIn("ConnectionError", embed.fields[0].value)

    def test_bot_error_warning(self):
        """Test embed creation for warning severity."""
        payload = {
            "error_type": "RateLimitWarning",
            "error_message": "API rate limit approaching",
            "severity": "warning"
        }

        embed = create_bot_error_embed(payload)

        self.assertIn("WARNING", embed.title)
        self.assertEqual(embed.color.value, 0xFFAA00)  # Yellow

    def test_bot_error_with_missing_fields(self):
        """Test embed creation with missing fields."""
        payload = {}

        embed = create_bot_error_embed(payload)

        self.assertIsInstance(embed, discord.Embed)
        self.assertIn("UnknownError", embed.fields[0].value)
        self.assertIn("No error message provided", embed.description)


class TestHeartbeatAlertEmbed(unittest.TestCase):
    """Test cases for create_heartbeat_alert_embed()."""

    def test_heartbeat_alert_with_all_fields(self):
        """Test embed creation with all fields present."""
        last_heartbeat = time.time() - 120  # 2 minutes ago
        data = {
            "last_heartbeat": last_heartbeat,
            "missing_seconds": 120
        }

        embed = create_heartbeat_alert_embed(data)

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "⚠️ Heartbeat Alert")
        self.assertIn("No heartbeat received", embed.description)
        self.assertEqual(embed.color.value, 0xFFAA00)  # Yellow
        self.assertEqual(len(embed.fields), 3)
        self.assertIn("2m", embed.fields[1].value)
        self.assertIn("offline", embed.fields[2].value.lower())

    def test_heartbeat_alert_with_missing_last_heartbeat(self):
        """Test embed creation without last_heartbeat field."""
        data = {
            "missing_seconds": 150
        }

        embed = create_heartbeat_alert_embed(data)

        self.assertIsInstance(embed, discord.Embed)
        # Should only have 2 fields (Missing For and Status)
        self.assertEqual(len(embed.fields), 2)

    def test_heartbeat_alert_duration_formatting(self):
        """Test duration formatting in heartbeat alert."""
        # Test with large duration
        data = {
            "missing_seconds": 7265  # 2h 1m 5s
        }

        embed = create_heartbeat_alert_embed(data)

        # Missing For is the first field (index 0) when no last_heartbeat
        self.assertIn("2h 1m 5s", embed.fields[0].value)


class TestEmbedTimestamps(unittest.TestCase):
    """Test cases for timestamp handling in embeds."""

    def test_embed_timestamp_conversion(self):
        """Test that timestamps are correctly converted to datetime."""
        payload = {
            "timestamp": 1735833600.0,
            "market_name": "Test Market",
            "entry_price": 0.5,
            "position_size": 10.0
        }

        embed = create_position_opened_embed(payload)

        self.assertIsNotNone(embed.timestamp)
        self.assertIsInstance(embed.timestamp, datetime)
        # Check that the timestamp is approximately correct (within 1 second)
        expected_dt = datetime.fromtimestamp(1735833600.0)
        self.assertEqual(embed.timestamp.date(), expected_dt.date())

    def test_embed_without_timestamp_uses_now(self):
        """Test that missing timestamp defaults to current time."""
        payload = {
            "market_name": "Test Market",
            "entry_price": 0.5,
            "position_size": 10.0
        }

        import time
        before_timestamp = time.time()
        embed = create_position_opened_embed(payload)
        after_timestamp = time.time()

        self.assertIsNotNone(embed.timestamp)
        # Check that embed timestamp is within the expected range
        embed_timestamp = embed.timestamp.timestamp()
        self.assertGreaterEqual(embed_timestamp, before_timestamp - 1)
        self.assertLessEqual(embed_timestamp, after_timestamp + 1)


class TestEmbedFieldFormatting(unittest.TestCase):
    """Test cases for field value formatting."""

    def test_price_formatting(self):
        """Test that prices are formatted to 4 decimal places."""
        payload = {
            "entry_price": 0.123456789,
            "position_size": 5.0
        }

        embed = create_position_opened_embed(payload)

        # Entry price should be rounded to 4 decimals
        self.assertEqual(embed.fields[0].value, "0.1235")

    def test_currency_formatting(self):
        """Test that currency values are formatted to 2 decimal places."""
        payload = {
            "balance": 100.123456789,
            "equity": 99.999,
            "total_pnl": 0.001
        }

        embed = create_balance_update_embed(payload)

        self.assertIn("$100.12", embed.fields[0].value)
        self.assertIn("$100.00", embed.fields[1].value)
        self.assertIn("+0.00", embed.fields[5].value)

    def test_percentage_formatting(self):
        """Test that percentages are formatted correctly."""
        payload = {
            "pnl": 1.0,
            "pnl_pct": 0.12345
        }

        embed = create_trade_completed_embed(payload)

        # P&L % should show +12.35%
        self.assertIn("+12.35%", embed.fields[3].value)

    def test_reason_formatting(self):
        """Test that underscore reasons are formatted nicely."""
        payload = {
            "entry_price": 0.5,
            "position_size": 5.0,
            "reason": "spike_down_detected"
        }

        embed = create_position_opened_embed(payload)

        # Reason should be title-cased with spaces
        self.assertIn("Spike Down Detected", embed.fields[2].value)


if __name__ == "__main__":
    unittest.main()
