#!/usr/bin/env python3
"""
Integration tests for PolySpike Discord Bot MQTT connectivity.

This script verifies that the bot can communicate with a real Mosquitto broker
by publishing test messages to all expected topics and verifying delivery.

Usage:
    # Run with default settings (localhost:1883, prefix: polyspike)
    python scripts/test_integration.py

    # Specify custom broker
    python scripts/test_integration.py --broker 192.168.1.100 --port 1883

    # Specify custom topic prefix
    python scripts/test_integration.py --prefix mybot

Requirements:
    - Mosquitto broker running and accessible
    - paho-mqtt package installed (pip install paho-mqtt)

Example workflow for Raspberry Pi deployment:
    1. Start Mosquitto: sudo systemctl start mosquitto
    2. Run tests: python scripts/test_integration.py
    3. Verify all tests pass before starting the bot
    4. Optionally monitor topics: mosquitto_sub -v -t 'polyspike/#'
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

import paho.mqtt.client as mqtt


class TestStatus(Enum):
    """Test result status."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TestResult:
    """Result of a single test case."""

    name: str
    status: TestStatus
    topic: str
    payload: dict[str, Any]
    error: str | None = None
    duration_ms: float = 0.0


class MQTTIntegrationTester:
    """Integration tester for MQTT broker connectivity."""

    # MQTT connection result codes
    _CONNECTION_ERRORS = {
        1: "Incorrect protocol version",
        2: "Invalid client identifier",
        3: "Server unavailable",
        4: "Bad username or password",
        5: "Not authorized",
    }

    def __init__(self, broker: str, port: int, prefix: str) -> None:
        """Initialize the tester.

        Args:
            broker: MQTT broker hostname or IP address.
            port: MQTT broker port.
            prefix: Topic prefix (without trailing slash).
        """
        self.broker = broker
        self.port = port
        self.prefix = prefix.rstrip("/")
        self.client: mqtt.Client | None = None
        self.connected = False
        self.results: list[TestResult] = []
        self._publish_confirmed = False
        self._last_mid: int | None = None

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        """Handle MQTT connection callback."""
        # Handle both int and ReasonCode for compatibility
        rc_value = rc if isinstance(rc, int) else rc.value
        if rc_value == 0:
            self.connected = True
        else:
            error_msg = self._CONNECTION_ERRORS.get(
                rc_value, f"Unknown error (code {rc_value})"
            )
            print(f"Connection failed: {error_msg}")
            self.connected = False

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        """Handle MQTT disconnection callback."""
        self.connected = False

    def _on_publish(
        self, client: mqtt.Client, userdata: Any, mid: int, *args: Any
    ) -> None:
        """Handle MQTT publish confirmation."""
        if mid == self._last_mid:
            self._publish_confirmed = True

    def connect(self) -> bool:
        """Connect to the MQTT broker.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"polyspike_integration_test_{uuid.uuid4().hex[:8]}",
            )
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            print(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()

            # Wait for connection with timeout
            timeout = 10.0
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if not self.connected:
                print(f"Connection timeout after {timeout}s")
                return False

            print(f"Connected successfully to {self.broker}:{self.port}")
            return True

        except ConnectionRefusedError:
            print(f"Connection refused - is Mosquitto running on {self.broker}:{self.port}?")
            return False
        except OSError as e:
            print(f"Network error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during connection: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            print("Disconnected from MQTT broker")

    def _publish_and_verify(
        self, topic: str, payload: dict[str, Any], timeout: float = 5.0
    ) -> tuple[bool, str | None]:
        """Publish a message and verify delivery.

        Args:
            topic: Full MQTT topic.
            payload: Message payload as dictionary.
            timeout: Maximum time to wait for confirmation.

        Returns:
            Tuple of (success, error_message).
        """
        if not self.client or not self.connected:
            return False, "Not connected to broker"

        self._publish_confirmed = False
        payload_json = json.dumps(payload)

        try:
            result = self.client.publish(topic, payload_json, qos=1)
            self._last_mid = result.mid

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                return False, f"Publish failed with code {result.rc}"

            # Wait for publish confirmation
            start = time.time()
            while not self._publish_confirmed and (time.time() - start) < timeout:
                time.sleep(0.05)

            if not self._publish_confirmed:
                return False, f"Publish confirmation timeout after {timeout}s"

            return True, None

        except Exception as e:
            return False, str(e)

    def _run_test(
        self, name: str, topic_suffix: str, payload: dict[str, Any]
    ) -> TestResult:
        """Run a single test case.

        Args:
            name: Test name for display.
            topic_suffix: Topic suffix (appended to prefix).
            payload: Message payload.

        Returns:
            TestResult with outcome.
        """
        full_topic = f"{self.prefix}/{topic_suffix}"

        # Ensure timestamp is present
        if "timestamp" not in payload:
            payload["timestamp"] = time.time()

        start_time = time.time()
        success, error = self._publish_and_verify(full_topic, payload)
        duration_ms = (time.time() - start_time) * 1000

        status = TestStatus.PASSED if success else TestStatus.FAILED

        return TestResult(
            name=name,
            status=status,
            topic=full_topic,
            payload=payload,
            error=error,
            duration_ms=duration_ms,
        )

    def run_all_tests(self) -> list[TestResult]:
        """Run all integration tests.

        Returns:
            List of test results.
        """
        self.results = []
        current_time = time.time()

        # Test 1: Bot Started Event
        self.results.append(
            self._run_test(
                name="Bot Started Event",
                topic_suffix="status/bot/started",
                payload={
                    "timestamp": current_time,
                    "session_id": f"test-{uuid.uuid4().hex[:8]}",
                    "initial_balance": 100.0,
                    "version": "1.0.0-test",
                    "environment": "integration-test",
                },
            )
        )

        # Test 2: Position Opened Event
        self.results.append(
            self._run_test(
                name="Position Opened Event",
                topic_suffix="trading/position/opened",
                payload={
                    "timestamp": current_time,
                    "token_id": "test-token-123",
                    "market_name": "Test Market - Will Bitcoin reach $100k?",
                    "side": "YES",
                    "amount": 10.0,
                    "price": 0.55,
                    "cost": 5.50,
                },
            )
        )

        # Test 3: Trade Completed Event
        self.results.append(
            self._run_test(
                name="Trade Completed Event",
                topic_suffix="trading/trade/completed",
                payload={
                    "timestamp": current_time,
                    "trade_id": f"trade-{uuid.uuid4().hex[:8]}",
                    "token_id": "test-token-123",
                    "market_name": "Test Market",
                    "side": "SELL",
                    "pnl": 0.50,
                    "pnl_percent": 9.09,
                    "exit_price": 0.60,
                    "hold_time_seconds": 3600,
                },
            )
        )

        # Test 4: Balance Update Event
        self.results.append(
            self._run_test(
                name="Balance Update Event",
                topic_suffix="balance/update",
                payload={
                    "timestamp": current_time,
                    "balance": 100.50,
                    "previous_balance": 100.0,
                    "change": 0.50,
                    "change_percent": 0.5,
                },
            )
        )

        # Test 5: Heartbeat Event
        self.results.append(
            self._run_test(
                name="Heartbeat Event",
                topic_suffix="status/bot/heartbeat",
                payload={
                    "timestamp": current_time,
                    "uptime_seconds": 60,
                    "active_positions": 1,
                    "balance": 100.50,
                    "memory_mb": 128.5,
                    "cpu_percent": 5.2,
                },
            )
        )

        # Test 6: Bot Error Event
        self.results.append(
            self._run_test(
                name="Bot Error Event",
                topic_suffix="status/bot/error",
                payload={
                    "timestamp": current_time,
                    "error_type": "TestError",
                    "message": "This is a test error message for integration testing",
                    "severity": "warning",
                    "recoverable": True,
                    "context": {"test_run": True, "source": "integration_test"},
                },
            )
        )

        return self.results

    def print_results(self) -> None:
        """Print test results in a formatted output."""
        print("\n" + "=" * 70)
        print("INTEGRATION TEST RESULTS")
        print("=" * 70)
        print(f"Broker: {self.broker}:{self.port}")
        print(f"Topic Prefix: {self.prefix}/")
        print("-" * 70)

        passed = 0
        failed = 0

        for result in self.results:
            status_icon = "[PASS]" if result.status == TestStatus.PASSED else "[FAIL]"
            print(f"\n{status_icon} {result.name}")
            print(f"       Topic: {result.topic}")
            print(f"       Duration: {result.duration_ms:.1f}ms")

            if result.status == TestStatus.PASSED:
                passed += 1
                # Print payload for manual Discord verification
                print("       Payload:")
                payload_formatted = json.dumps(result.payload, indent=8)
                for line in payload_formatted.split("\n"):
                    print(f"         {line}")
            else:
                failed += 1
                print(f"       Error: {result.error}")

        print("\n" + "-" * 70)
        print("SUMMARY")
        print("-" * 70)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed == 0:
            print("\nAll tests passed! Bot is ready to connect to the broker.")
        else:
            print(f"\n{failed} test(s) failed. Check broker connectivity and configuration.")

        print("=" * 70)

    def get_exit_code(self) -> int:
        """Get exit code based on test results.

        Returns:
            0 if all tests passed, 1 otherwise.
        """
        return 0 if all(r.status == TestStatus.PASSED for r in self.results) else 1


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Integration tests for PolySpike Discord Bot MQTT connectivity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Run with defaults (localhost:1883)
  %(prog)s --broker 192.168.1.100    Connect to remote broker
  %(prog)s --prefix mybot            Use custom topic prefix
  %(prog)s --port 8883               Use non-standard port
        """,
    )

    parser.add_argument(
        "--broker",
        type=str,
        default="localhost",
        help="MQTT broker hostname or IP address (default: localhost)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)",
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="polyspike",
        help="MQTT topic prefix (default: polyspike)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    print("PolySpike Discord Bot - MQTT Integration Tests")
    print("-" * 50)

    tester = MQTTIntegrationTester(
        broker=args.broker,
        port=args.port,
        prefix=args.prefix,
    )

    if not tester.connect():
        print("\nFailed to connect to MQTT broker. Aborting tests.")
        print("\nTroubleshooting tips:")
        print("  1. Verify Mosquitto is running: systemctl status mosquitto")
        print("  2. Check if port is open: nc -zv localhost 1883")
        print("  3. Review broker logs: journalctl -u mosquitto -f")
        return 1

    try:
        tester.run_all_tests()
        tester.print_results()
        return tester.get_exit_code()

    finally:
        tester.disconnect()


if __name__ == "__main__":
    sys.exit(main())
