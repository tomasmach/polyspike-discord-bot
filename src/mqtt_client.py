"""MQTT client for PolySpike trading bot integration."""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt
from src.config import Config
from src.utils.logger import get_logger


class MQTTClient:
    """Async MQTT client for PolySpike trading bot events.

    Provides an asynchronous interface to the paho-mqtt client with automatic
    reconnection, rate limiting detection, and topic-based message routing.

    Attributes:
        config: Bot configuration containing MQTT connection settings.
        connected: Whether the client is currently connected to the broker.
        startup_time: Unix timestamp when the client was initialized.
        message_handlers: List of registered (pattern, handler) tuples.

    Example:
        >>> client = MQTTClient(config)
        >>> client.register_handler("polyspike/trade/#", handle_trade)
        >>> await client.connect()
        >>> # ... handle messages ...
        >>> await client.disconnect()
    """

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

    def on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict[str, Any],
        rc: int | mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle MQTT connection callback.

        Called by paho-mqtt when the client connects to the broker.
        Subscribes to the configured topic prefix on successful connection.

        Args:
            client: MQTT client instance that triggered the callback.
            userdata: User data set in Client() or user_data_set().
            flags: Response flags sent by the broker (contains session_present).
            rc: Connection result code. 0 indicates success, other values
                indicate connection refused (see MQTT spec for codes).
            properties: MQTT v5.0 properties (optional, for protocol compatibility).

        Returns:
            None
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

    def on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int,
        properties: Any = None,
    ) -> None:
        """Handle MQTT disconnection callback.

        Called by paho-mqtt when the client disconnects from the broker.
        Logs the disconnection reason and initiates reconnection if unexpected.

        Args:
            client: MQTT client instance that triggered the callback.
            userdata: User data set in Client() or user_data_set().
            rc: Disconnection reason code. 0 indicates clean disconnect,
                other values indicate unexpected disconnection.
            properties: MQTT v5.0 properties (optional, for protocol compatibility).

        Returns:
            None
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

    def on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT messages.

        Called by paho-mqtt when a message is received on a subscribed topic.
        Parses JSON payload and routes to registered handlers based on topic pattern.

        Args:
            client: MQTT client instance that received the message.
            userdata: User data set in Client() or user_data_set().
            msg: MQTT message containing topic, payload, QoS, and retain flag.

        Returns:
            None
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

    async def connect(self) -> None:
        """Connect to MQTT broker asynchronously.

        Establishes connection to the MQTT broker, starts the network loop,
        and initiates the background retry task for automatic reconnection.

        Raises:
            ConnectionError: If initial connection fails or times out after 10 seconds.
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

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker gracefully.

        Stops the retry task, unsubscribes from topics, disconnects from
        the broker, and stops the network loop. Safe to call multiple times.
        """
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

    async def _retry_connection_task(self) -> None:
        """Background task for connection retry with exponential backoff.

        Continuously monitors the connection state and attempts reconnection
        when disconnected. Uses exponential backoff with 1-60 second delays.
        Sends Discord alert if MQTT is down for more than 5 minutes.

        Note:
            This is an internal method started by connect() and should not
            be called directly.
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
        """Check if a topic matches an MQTT wildcard pattern.

        Implements MQTT topic matching with single-level (+) and
        multi-level (#) wildcards according to the MQTT specification.

        Args:
            topic: Actual MQTT topic string received from broker.
            pattern: MQTT topic pattern with optional wildcards.
                '+' matches exactly one level, '#' matches any remaining levels.

        Returns:
            True if topic matches the pattern, False otherwise.

        Examples:
            _match_topic("a/b/c", "a/+/c") -> True
            _match_topic("a/b/c", "a/#") -> True
            _match_topic("a/b", "a/b/c") -> False
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

    def register_handler(
        self,
        topic_pattern: str,
        handler_func: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a message handler for a topic pattern.

        The handler will be called for any message whose topic matches the
        pattern. Multiple handlers can be registered for the same or
        overlapping patterns.

        Args:
            topic_pattern: MQTT topic pattern to match. Supports '+' for
                single-level wildcard and '#' for multi-level wildcard.
            handler_func: Callback function that receives the parsed JSON
                payload as a dictionary. Should not raise exceptions.

        Example:
            >>> mqtt.register_handler("polyspike/trade/#", handle_trade)
        """
        self.message_handlers.append((topic_pattern, handler_func))
        self.logger.info(f"Registered handler for topic pattern: {topic_pattern}")

    def unregister_handler(
        self,
        topic_pattern: str,
        handler_func: Callable[[dict[str, Any]], None],
    ) -> None:
        """Unregister a message handler for a topic pattern.

        Removes the handler if it exists. If the handler was not registered,
        this method has no effect.

        Args:
            topic_pattern: MQTT topic pattern that was used during registration.
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

    def set_alert_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set callback for MQTT connection alerts.

        Registers a callback that will be invoked when the MQTT broker
        is unreachable for more than 5 minutes. Used to send Discord alerts.

        Args:
            callback: Function to call with (message, downtime_seconds).
                The message describes the alert, downtime_seconds indicates
                how long the broker has been unreachable.
        """
        self._alert_callback = callback
        self.logger.info("MQTT alert callback registered")

    def stop(self) -> None:
        """Stop the MQTT client and cancel background tasks.

        Sets the stopping flag and cancels the retry task. Does not
        disconnect from the broker - use disconnect() for that.
        This method is synchronous and can be called from signal handlers.
        """
        self._stopping = True

        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
