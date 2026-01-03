"""Unit tests for MQTT client message routing."""

import json
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from src.config import Config
from src.mqtt_client import MQTTClient


class TestMQTTTopicMatching(unittest.TestCase):
    """Test cases for _match_topic() helper method."""

    def setUp(self):
        """Set up test configuration and MQTT client."""
        self.config = Config(
            discord_bot_token="test_token",
            discord_guild_id=123456789,
            discord_channel_id=987654321,
            mqtt_broker_host="localhost",
            mqtt_broker_port=1883,
            mqtt_topic_prefix="polyspike/",
            heartbeat_timeout_seconds=90,
            heartbeat_check_interval=30,
            log_level="INFO"
        )
        self.mqtt_client = MQTTClient(self.config)

    def test_exact_topic_match(self):
        """Test exact topic match."""
        topic = "polyspike/status/bot/started"
        pattern = "polyspike/status/bot/started"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertTrue(result)

    def test_single_wildcard_match(self):
        """Test single wildcard + match."""
        topic = "polyspike/status/bot"
        pattern = "polyspike/status/+"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertTrue(result)

    def test_multi_wildcard_match(self):
        """Test multi wildcard # match."""
        topic = "polyspike/status/bot/started"
        pattern = "polyspike/#"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertTrue(result)

    def test_multiple_single_wildcards_match(self):
        """Test multiple single wildcards match."""
        topic = "polyspike/status/bot/started"
        pattern = "polyspike/+/+/started"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertTrue(result)

    def test_non_matching_pattern(self):
        """Test non-matching patterns."""
        topic = "polyspike/status/bot/started"
        pattern = "polyspike/trading/+"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertFalse(result)

    def test_complex_pattern_match(self):
        """Test complex patterns."""
        topic = "polyspike/trading/position/opened"
        pattern = "polyspike/trading/+/+"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertTrue(result)

    def test_multi_wildcard_requires_minimum_parts(self):
        """Test # wildcard requires minimum topic parts."""
        topic = "polyspike/status"
        pattern = "polyspike/status/bot/#"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertFalse(result)

    def test_single_wildcard_wrong_length(self):
        """Test + wildcard requires exact same number of parts."""
        topic = "polyspike/status/bot"
        pattern = "polyspike/status/+/+/extra"
        result = self.mqtt_client._match_topic(topic, pattern)
        self.assertFalse(result)


class TestHandlerRegistration(unittest.TestCase):
    """Test cases for handler registration and management."""

    def setUp(self):
        """Set up test configuration and MQTT client."""
        self.config = Config(
            discord_bot_token="test_token",
            discord_guild_id=123456789,
            discord_channel_id=987654321,
            mqtt_broker_host="localhost",
            mqtt_broker_port=1883,
            mqtt_topic_prefix="polyspike/",
            heartbeat_timeout_seconds=90,
            heartbeat_check_interval=30,
            log_level="INFO"
        )
        self.mqtt_client = MQTTClient(self.config)
        self.mock_handler = Mock()

    def test_register_handler_exact_topic(self):
        """Test registering handler for exact topic."""
        pattern = "polyspike/status/bot/started"
        self.mqtt_client.register_handler(pattern, self.mock_handler)
        self.assertIn((pattern, self.mock_handler), self.mqtt_client.message_handlers)

    def test_register_handler_wildcard_pattern(self):
        """Test registering handler for wildcard pattern."""
        pattern = "polyspike/trading/+"
        self.mqtt_client.register_handler(pattern, self.mock_handler)
        self.assertIn((pattern, self.mock_handler), self.mqtt_client.message_handlers)

    def test_list_handlers(self):
        """Test list_handlers returns registered patterns."""
        patterns = ["polyspike/status/+", "polyspike/trading/#"]
        for pattern in patterns:
            self.mqtt_client.register_handler(pattern, self.mock_handler)
        result = self.mqtt_client.list_handlers()
        self.assertEqual(set(result), set(patterns))

    def test_unregister_handler(self):
        """Test unregister_handler removes handler."""
        pattern = "polyspike/status/+"
        self.mqtt_client.register_handler(pattern, self.mock_handler)
        self.assertIn((pattern, self.mock_handler), self.mqtt_client.message_handlers)
        self.mqtt_client.unregister_handler(pattern, self.mock_handler)
        self.assertNotIn((pattern, self.mock_handler), self.mqtt_client.message_handlers)

    def test_unregister_specific_handler_only(self):
        """Test unregister removes only matching handler, not others."""
        pattern = "polyspike/status/+"
        handler1 = Mock()
        handler2 = Mock()
        self.mqtt_client.register_handler(pattern, handler1)
        self.mqtt_client.register_handler(pattern, handler2)
        self.assertEqual(len(self.mqtt_client.message_handlers), 2)
        self.mqtt_client.unregister_handler(pattern, handler1)
        self.assertEqual(len(self.mqtt_client.message_handlers), 1)
        self.assertIn((pattern, handler2), self.mqtt_client.message_handlers)


class TestMessageRouting(unittest.TestCase):
    """Test cases for message routing functionality."""

    def setUp(self):
        """Set up test configuration and MQTT client."""
        self.config = Config(
            discord_bot_token="test_token",
            discord_guild_id=123456789,
            discord_channel_id=987654321,
            mqtt_broker_host="localhost",
            mqtt_broker_port=1883,
            mqtt_topic_prefix="polyspike/",
            heartbeat_timeout_seconds=90,
            heartbeat_check_interval=30,
            log_level="INFO"
        )
        self.mqtt_client = MQTTClient(self.config)

    def create_mock_message(self, topic, payload):
        """Create a mock MQTT message object."""
        msg = Mock()
        msg.topic = topic
        msg.payload = json.dumps(payload).encode('utf-8')
        return msg

    def test_message_routing_to_single_handler(self):
        """Test message routes to correct handler."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/trading/+/+", handler)
        msg = self.create_mock_message("polyspike/trading/position/opened", {"test": "data", "timestamp": time.time()})
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_called_once()

    def test_message_routing_to_multiple_handlers(self):
        """Test message routes to multiple matching handlers."""
        handler1 = Mock()
        handler2 = Mock()
        self.mqtt_client.register_handler("polyspike/trading/+/+", handler1)
        self.mqtt_client.register_handler("polyspike/#", handler2)
        msg = self.create_mock_message("polyspike/trading/position/opened", {"test": "data", "timestamp": time.time()})
        self.mqtt_client.on_message(None, None, msg)
        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_no_matching_handler(self):
        """Test message with no matching handler."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/status/+", handler)
        msg = self.create_mock_message("polyspike/trading/position", {"test": "data"})
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_not_called()

    def test_old_retained_message_filtered(self):
        """Test old retained messages are filtered out."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        old_timestamp = self.mqtt_client.startup_time - 400
        msg = self.create_mock_message("polyspike/test", {"timestamp": old_timestamp})
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_not_called()

    def test_recent_message_not_filtered(self):
        """Test recent messages are not filtered out."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        recent_timestamp = time.time()
        msg = self.create_mock_message("polyspike/test", {"timestamp": recent_timestamp})
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_called_once()

    def test_message_without_timestamp(self):
        """Test message without timestamp field."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        msg = self.create_mock_message("polyspike/test", {"data": "value"})
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_called_once()

    @patch('src.mqtt_client.get_logger')
    def test_handler_error_logged(self, mock_get_logger):
        """Test handler errors are logged."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        self.mqtt_client.logger = mock_logger
        handler = Mock(side_effect=Exception("Handler error"))
        self.mqtt_client.register_handler("polyspike/+", handler)
        msg = self.create_mock_message("polyspike/test", {"test": "data", "timestamp": time.time()})
        self.mqtt_client.on_message(None, None, msg)
        mock_logger.error.assert_called()


class TestJSONParsingErrors(unittest.TestCase):
    """Test cases for JSON parsing error handling."""

    def setUp(self):
        """Set up test configuration and MQTT client."""
        self.config = Config(
            discord_bot_token="test_token",
            discord_guild_id=123456789,
            discord_channel_id=987654321,
            mqtt_broker_host="localhost",
            mqtt_broker_port=1883,
            mqtt_topic_prefix="polyspike/",
            heartbeat_timeout_seconds=90,
            heartbeat_check_interval=30,
            log_level="INFO"
        )
        self.mqtt_client = MQTTClient(self.config)

    @patch('src.mqtt_client.get_logger')
    def test_invalid_json_handler_not_called(self, mock_get_logger):
        """Test invalid JSON is logged and handler not called."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        self.mqtt_client.logger = mock_logger
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        msg = Mock()
        msg.topic = "polyspike/test"
        msg.payload = b"invalid json"
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_not_called()
        mock_logger.error.assert_called()

    @patch('src.mqtt_client.get_logger')
    def test_unicode_decode_error_logged(self, mock_get_logger):
        """Test unicode decode errors are logged."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        self.mqtt_client.logger = mock_logger
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        msg = Mock()
        msg.topic = "polyspike/test"
        msg.payload = b'\xff\xfe invalid'
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_not_called()
        mock_logger.error.assert_called()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        """Set up test configuration and MQTT client."""
        self.config = Config(
            discord_bot_token="test_token",
            discord_guild_id=123456789,
            discord_channel_id=987654321,
            mqtt_broker_host="localhost",
            mqtt_broker_port=1883,
            mqtt_topic_prefix="polyspike/",
            heartbeat_timeout_seconds=90,
            heartbeat_check_interval=30,
            log_level="INFO"
        )
        self.mqtt_client = MQTTClient(self.config)

    def create_mock_message(self, topic, payload):
        """Create a mock MQTT message object."""
        msg = Mock()
        msg.topic = topic
        msg.payload = json.dumps(payload).encode('utf-8')
        return msg

    def test_empty_handlers_list(self):
        """Test message with empty handlers list."""
        msg = self.create_mock_message("polyspike/test", {"test": "data"})
        self.assertEqual(len(self.mqtt_client.message_handlers), 0)
        self.mqtt_client.on_message(None, None, msg)

    def test_multiple_handlers_same_pattern(self):
        """Test multiple handlers registered for same pattern."""
        handler1 = Mock()
        handler2 = Mock()
        pattern = "polyspike/#"
        self.mqtt_client.register_handler(pattern, handler1)
        self.mqtt_client.register_handler(pattern, handler2)
        msg = self.create_mock_message("polyspike/trading/position", {"test": "data", "timestamp": time.time()})
        self.mqtt_client.on_message(None, None, msg)
        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_handler_receives_correct_payload(self):
        """Test handler receives the correct payload."""
        handler = Mock()
        self.mqtt_client.register_handler("polyspike/+", handler)
        payload = {"event": "test", "value": 123, "timestamp": time.time()}
        msg = self.create_mock_message("polyspike/test", payload)
        self.mqtt_client.on_message(None, None, msg)
        handler.assert_called_once_with(payload)

    def test_match_topic_empty_pattern(self):
        """Test _match_topic with empty pattern."""
        result = self.mqtt_client._match_topic("polyspike/test", "")
        self.assertFalse(result)

    def test_match_topic_empty_topic(self):
        """Test _match_topic with empty topic."""
        result = self.mqtt_client._match_topic("", "polyspike/+")
        self.assertFalse(result)

    @patch('src.mqtt_client.get_logger')
    def test_unexpected_error_logged(self, mock_get_logger):
        """Test unexpected errors are logged with exception info."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        self.mqtt_client.logger = mock_logger
        msg = Mock()
        msg.topic = "polyspike/test"
        msg.payload = Mock()
        msg.payload.decode = Mock(side_effect=Exception("Unexpected error"))
        self.mqtt_client.on_message(None, None, msg)
        mock_logger.error.assert_called()


if __name__ == '__main__':
    unittest.main()
