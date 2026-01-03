"""MQTT client for PolySpike trading bot integration."""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
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
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.connected = False
        self.startup_time = time.time()
        self._retry_task: Optional[asyncio.Task] = None
        self._retry_count = 0
        self._stopping = False
        self._loop_running = False
        self._disconnect_time: Optional[float] = None
        self._disconnect_alert_sent = False
        self._alert_callback: Optional[Callable] = None
        self.message_handlers: list[tuple[str, Callable]] = []

        # Rate limiting detection (for spam prevention)
        self._message_timestamps: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._rate_limit_warnings: dict[str, float] = {}
        self._rate_limit_threshold = 50  # messages per minute (for non-periodic topics)
        self._rate_warning_cooldown = 300  # seconds (5 min between warnings)

    def on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection callback.

        Args:
            client: MQTT client instance.
            userdata: User data.
            flags: Connection flags.
            rc: Return code (0 = success).
        """
        if rc == 0:
            # Log reconnection info if we were disconnected
            if self._disconnect_time is not None:
                downtime = time.time() - self._disconnect_time
                self.logger.info(f"Reconnected to MQTT broker after {downtime:.1f}s downtime")
            else:
                self.logger.info("Connected to MQTT broker successfully")

            client.subscribe(f"{self.config.mqtt_topic_prefix}#")
            self.connected = True
            self._retry_count = 0
            self._disconnect_time = None
            self._disconnect_alert_sent = False
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            self.logger.error(f"MQTT connection failed: {error_msg} (code {rc})")
            self.connected = False

    def on_disconnect(self, client, userdata, rc, properties=None):
        """Handle MQTT disconnection callback.

        Args:
            client: MQTT client instance.
            userdata: User data.
            rc: Return code (0 = clean disconnect, >0 = unexpected).
            properties: MQTT v5 properties (optional, for compatibility).
        """
        self.connected = False

        if self._disconnect_time is None:
            self._disconnect_time = time.time()

        if rc == 0:
            self.logger.info("Disconnected from MQTT broker (clean disconnect)")
        else:
            disconnect_reasons = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized",
                7: "Connection lost",
            }
            reason = disconnect_reasons.get(rc, f"Unknown reason (code {rc})")
            self.logger.warning(f"Disconnected from MQTT broker unexpectedly: {reason}")

        if not self._stopping:
            self.logger.info("Will attempt to reconnect via retry task...")

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

            # Validate critical fields
            if "timestamp" not in data:
                self.logger.warning(
                    f"MQTT payload missing critical field 'timestamp' on topic {topic}. "
                    f"Message may be malformed."
                )
            elif data.get("timestamp", 0) < self.startup_time - 300:
                self.logger.debug(f"Ignoring old retained message on topic: {topic}")
                return

            # Rate limiting detection (spam prevention)
            self._check_message_rate(topic)

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
        """Background task for connection retry with exponential backoff.

        Sends Discord alert if MQTT is down for >5 minutes.
        """
        base_delay = 1.0
        max_delay = 60.0
        alert_threshold = 300.0  # 5 minutes

        while not self._stopping:
            if not self.connected:
                # Check if we should send a Discord alert
                if (self._disconnect_time is not None and
                    not self._disconnect_alert_sent and
                    self._alert_callback is not None):

                    downtime = time.time() - self._disconnect_time

                    if downtime >= alert_threshold:
                        self.logger.warning(
                            f"MQTT broker down for {downtime:.0f}s (>{alert_threshold:.0f}s threshold). "
                            "Sending Discord alert..."
                        )
                        try:
                            self._alert_callback(
                                f"MQTT broker unreachable for {downtime:.0f}s",
                                downtime
                            )
                            self._disconnect_alert_sent = True
                            self.logger.info("Discord alert sent successfully")
                        except Exception as e:
                            self.logger.error(f"Failed to send Discord alert: {e}", exc_info=True)

                # Retry connection with exponential backoff
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
                    self.logger.error(f"Reconnection attempt {self._retry_count} failed: {e}")

            if self._stopping:
                break

            await asyncio.sleep(5.0)

    def _check_message_rate(self, topic: str) -> None:
        """Check message rate for spam detection.

        Tracks message timestamps and logs warning if rate exceeds threshold.
        Excludes periodic topics (stats, heartbeat) from rate limiting.

        Args:
            topic: MQTT topic of the message.
        """
        # Skip rate limiting for expected high-frequency topics
        high_frequency_topics = ["stats/periodic", "heartbeat"]
        if any(freq_topic in topic for freq_topic in high_frequency_topics):
            return

        current_time = time.time()
        topic_queue = self._message_timestamps[topic]

        # Add current timestamp
        topic_queue.append(current_time)

        # Count messages in last 60 seconds
        cutoff_time = current_time - 60
        recent_messages = sum(1 for ts in topic_queue if ts >= cutoff_time)

        # Check if rate exceeds threshold
        if recent_messages > self._rate_limit_threshold:
            # Only log warning if we haven't warned recently (cooldown)
            last_warning = self._rate_limit_warnings.get(topic, 0)
            if current_time - last_warning > self._rate_warning_cooldown:
                self.logger.warning(
                    f"High message rate detected on topic '{topic}': "
                    f"{recent_messages} messages in last 60s (threshold: {self._rate_limit_threshold}/min). "
                    f"Possible spam or bot malfunction."
                )
                self._rate_limit_warnings[topic] = current_time

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

    def set_alert_callback(self, callback: Callable[[str, float], None]):
        """Set callback for MQTT connection alerts.

        Callback will be called when MQTT broker is down for >5 minutes.

        Args:
            callback: Function to call with (message, downtime_seconds).
        """
        self._alert_callback = callback
        self.logger.info("MQTT alert callback registered")

    def stop(self):
        """Stop the MQTT client and background tasks."""
        self._stopping = True

        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
