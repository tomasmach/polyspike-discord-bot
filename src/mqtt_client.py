"""MQTT client for PolySpike trading bot integration."""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt
from src.config import Config
from src.utils.logger import get_logger


class MQTTClient:
    """Async MQTT client for PolySpike trading bot events."""

    def __init__(self, config: Config):
        """Initialize MQTT client.

        Args:
            config: Bot configuration with MQTT settings.
        """
        self.config = config
        self.logger = get_logger()

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="polyspike_discord_bot"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.connected = False
        self.startup_time = time.time()
        self._retry_task: Optional[asyncio.Task] = None
        self._retry_count = 0
        self._stopping = False
        self._loop_running = False
        self.message_handlers: list[tuple[str, Callable]] = []

    def on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection callback.

        Args:
            client: MQTT client instance.
            userdata: User data.
            flags: Connection flags.
            rc: Return code (0 = success).
        """
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            client.subscribe(f"{self.config.mqtt_topic_prefix}#")
            self.connected = True
            self._retry_count = 0
        else:
            self.logger.error(f"MQTT connection failed with code: {rc}")
            self.connected = False

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages.

        Args:
            client: MQTT client instance.
            userdata: User data.
            msg: MQTT message object.
        """
        topic = msg.topic
        self.logger.info(f"Received message on topic: {topic}")

        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)

            try:
                self.logger.debug(f"Payload: {str(data)}")
            except Exception:
                pass

            if data.get("timestamp", 0) < self.startup_time - 300:
                self.logger.debug(f"Ignoring old retained message on topic: {topic}")
                return

            matched = False
            for pattern, handler in self.message_handlers:
                if self._match_topic(topic, pattern):
                    matched = True
                    try:
                        self.logger.info(f"Routing topic '{topic}' to handler for pattern '{pattern}'")
                        handler(data)
                    except Exception as e:
                        self.logger.error(f"Handler error for pattern {pattern} on topic {topic}: {e}", exc_info=True)

            if not matched:
                self.logger.debug(f"No handler matched for topic: {topic}")

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error on topic {topic}: {e}")
        except UnicodeDecodeError as e:
            self.logger.error(f"Unicode decode error on topic {topic}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error processing message on topic {topic}: {e}", exc_info=True)

    async def connect(self):
        """Connect to MQTT broker.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.connect,
                    self.config.mqtt_broker_host,
                    self.config.mqtt_broker_port,
                    keepalive=60
                ),
                timeout=10.0
            )
            if not self._loop_running:
                self.client.loop_start()
                self._loop_running = True
            self.logger.info("MQTT client started")
        except asyncio.TimeoutError:
            raise ConnectionError(f"Connection timeout to {self.config.mqtt_broker_host}:{self.config.mqtt_broker_port}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MQTT broker: {e}")

        self._retry_task = asyncio.create_task(self._retry_connection_task())

    async def disconnect(self):
        """Disconnect from MQTT broker."""
        self._stopping = True

        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        self.client.unsubscribe(f"{self.config.mqtt_topic_prefix}#")

        try:
            await asyncio.to_thread(self.client.disconnect)
        except Exception as e:
            self.logger.warning(f"Error during disconnect: {e}")

        self.client.loop_stop()
        self._loop_running = False
        self.connected = False
        self.logger.info("MQTT client disconnected")

    async def _retry_connection_task(self):
        """Background task for connection retry with exponential backoff."""
        base_delay = 1.0
        max_delay = 60.0

        while not self._stopping:
            if not self.connected:
                delay = min(base_delay * (2 ** self._retry_count), max_delay)
                self.logger.info(f"Retry connection in {delay:.1f}s (attempt {self._retry_count + 1})")
                await asyncio.sleep(delay)

                try:
                    await asyncio.to_thread(
                        self.client.connect,
                        self.config.mqtt_broker_host,
                        self.config.mqtt_broker_port,
                        keepalive=60
                    )
                    if not self._loop_running:
                        self.client.loop_start()
                        self._loop_running = True
                    self._retry_count = 0
                    self.logger.info("Reconnected to MQTT broker")
                except Exception as e:
                    self._retry_count += 1
                    self.logger.error(f"Reconnection failed: {e}")

            if self._stopping:
                break

            await asyncio.sleep(5.0)

    def _match_topic(self, topic: str, pattern: str) -> bool:
        """Check if a topic matches an MQTT pattern.

        Args:
            topic: Actual MQTT topic received.
            pattern: MQTT pattern with wildcards (+ and #).

        Returns:
            True if topic matches pattern, False otherwise.
        """
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')

        if not pattern_parts:
            return False

        if pattern_parts[-1] == '#':
            if len(topic_parts) < len(pattern_parts) - 1:
                return False
            for i in range(len(pattern_parts) - 1):
                if pattern_parts[i] != '+' and pattern_parts[i] != topic_parts[i]:
                    return False
            return True

        if len(topic_parts) != len(pattern_parts):
            return False

        for topic_part, pattern_part in zip(topic_parts, pattern_parts):
            if pattern_part == '+':
                continue
            if pattern_part != topic_part:
                return False

        return True

    def register_handler(self, topic_pattern: str, handler_func: Callable):
        """Register a message handler for a topic pattern.

        Args:
            topic_pattern: MQTT topic pattern to match (supports + and # wildcards).
            handler_func: Callback function to handle messages.
        """
        self.message_handlers.append((topic_pattern, handler_func))
        self.logger.info(f"Registered handler for topic pattern: {topic_pattern}")

    def unregister_handler(self, topic_pattern: str, handler_func: Callable):
        """Unregister a message handler for a topic pattern.

        Args:
            topic_pattern: MQTT topic pattern.
            handler_func: Callback function to remove.
        """
        self.message_handlers = [(p, h) for p, h in self.message_handlers if not (p == topic_pattern and h == handler_func)]
        self.logger.info(f"Unregistered handler for topic pattern: {topic_pattern}")

    def list_handlers(self) -> list[str]:
        """List all registered topic patterns.

        Returns:
            List of registered topic patterns.
        """
        return [pattern for pattern, _ in self.message_handlers]

    def stop(self):
        """Stop the MQTT client and background tasks."""
        self._stopping = True

        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
