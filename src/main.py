"""Main entry point for PolySpike Discord Bot.

This module orchestrates the startup and shutdown of all bot components:
- Configuration loading
- Logging setup
- Discord bot initialization
- MQTT client connection
- Event handler registration
- Signal handling for graceful shutdown
"""

import asyncio
import sys
import time
from typing import Any, Dict

from src.bot import create_discord_bot, setup_signal_handlers
from src.commands import stats
from src.config import Config, load_config
from src.handlers import balance_handler, status_handler, trading_handler
from src.mqtt_client import MQTTClient
from src.utils.embeds import create_mqtt_connection_alert_embed
from src.utils.logger import get_logger, setup_logging


def register_mqtt_handlers(mqtt_client: MQTTClient, bot) -> None:
    """Register all MQTT event handlers.

    Maps MQTT topic patterns to handler functions.
    Handlers are called when matching messages arrive from trading bot.

    Args:
        mqtt_client: MQTT client instance to register handlers with.
        bot: Discord bot instance to pass to handlers.
    """
    logger = get_logger()
    logger.info("Registering MQTT event handlers")

    # Status event handlers
    mqtt_client.register_handler(
        "polyspike/status/bot/started",
        lambda payload: status_handler.handle_bot_started(payload, bot),
    )
    mqtt_client.register_handler(
        "polyspike/status/bot/stopped",
        lambda payload: status_handler.handle_bot_stopped(payload, bot),
    )
    mqtt_client.register_handler(
        "polyspike/status/bot/error",
        lambda payload: status_handler.handle_bot_error(payload, bot),
    )

    # Heartbeat handler (updates heartbeat monitor)
    mqtt_client.register_handler(
        "polyspike/status/bot/heartbeat",
        lambda payload: bot.heartbeat_monitor.update(payload)
        if bot.heartbeat_monitor
        else None,
    )

    # Trading event handlers
    mqtt_client.register_handler(
        "polyspike/trading/position/opened",
        lambda payload: trading_handler.handle_position_opened(payload, bot),
    )
    mqtt_client.register_handler(
        "polyspike/trading/trade/completed",
        lambda payload: trading_handler.handle_trade_completed(payload, bot),
    )

    # Balance event handler
    mqtt_client.register_handler(
        "polyspike/balance/update",
        lambda payload: balance_handler.handle_balance_update(payload, bot),
    )

    # Session stats handler (for /stats command cache)
    mqtt_client.register_handler(
        "polyspike/stats/session",
        lambda payload: stats.cache_session_stats(payload),
    )

    # Log registered handlers
    registered_topics = mqtt_client.list_handlers()
    logger.info(f"Registered {len(registered_topics)} MQTT handlers:")
    for topic in registered_topics:
        logger.info(f"  - {topic}")


def setup_mqtt_alert_callback(mqtt_client: MQTTClient, bot) -> None:
    """Setup MQTT connection alert callback.

    This callback is triggered when MQTT broker is unreachable for >5 minutes.
    Sends a Discord notification to alert about the connection issue.

    Args:
        mqtt_client: MQTT client instance to register alert callback with.
        bot: Discord bot instance for sending alerts.
    """
    logger = get_logger()

    def mqtt_alert_callback(message: str, downtime_seconds: float) -> None:
        """Callback function for MQTT connection alerts.

        Args:
            message: Alert message describing the issue.
            downtime_seconds: Number of seconds MQTT has been down.
        """
        try:
            if bot.notification_channel is None:
                logger.warning("Cannot send MQTT alert - notification channel not set")
                return

            embed = create_mqtt_connection_alert_embed(message, downtime_seconds)

            # Send alert synchronously (callback is called from MQTT thread)
            asyncio.run_coroutine_threadsafe(
                bot.notification_channel.send(embed=embed),
                bot.loop
            )

            logger.info(f"MQTT alert sent to Discord: {message}")

        except Exception as e:
            logger.error(f"Failed to send MQTT connection alert to Discord: {e}", exc_info=True)

    mqtt_client.set_alert_callback(mqtt_alert_callback)
    logger.info("✓ MQTT alert callback configured")


async def main() -> None:
    """Main entry point for the bot.

    Orchestrates the startup sequence:
    1. Load configuration from .env
    2. Setup logging
    3. Create Discord bot
    4. Create MQTT client
    5. Register event handlers
    6. Connect to MQTT broker
    7. Setup signal handlers for graceful shutdown
    8. Start Discord bot
    9. Wait for shutdown signal

    Exits with code 0 on successful shutdown, 1 on error.
    """
    logger = None

    try:
        # 1. Load configuration
        print("Loading configuration from .env...")
        config: Config = load_config()
        print("✓ Configuration loaded")

        # 2. Setup logging
        print("Setting up logging...")
        setup_logging(config.log_level)
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("PolySpike Discord Bot Starting")
        logger.info("=" * 60)
        logger.info(f"Log level: {config.log_level}")
        logger.info(f"Discord Guild ID: {config.discord_guild_id}")
        logger.info(f"Discord Channel ID: {config.discord_channel_id}")
        logger.info(f"MQTT Broker: {config.mqtt_broker_host}:{config.mqtt_broker_port}")
        logger.info(f"MQTT Topic Prefix: {config.mqtt_topic_prefix}")
        logger.info(
            f"Heartbeat Timeout: {config.heartbeat_timeout_seconds}s "
            f"(check interval: {config.heartbeat_check_interval}s)"
        )

        # 3. Create Discord bot
        logger.info("Creating Discord bot...")
        bot = create_discord_bot(config)
        logger.info("✓ Discord bot created")

        # 4. Create MQTT client
        logger.info("Creating MQTT client...")
        mqtt_client = MQTTClient(config)
        bot.mqtt_client = mqtt_client  # Attach MQTT client to bot for shutdown
        logger.info("✓ MQTT client created")

        # 5. Register event handlers
        logger.info("Registering MQTT event handlers...")
        register_mqtt_handlers(mqtt_client, bot)
        logger.info("✓ Event handlers registered")

        # 5a. Setup MQTT connection alert callback
        logger.info("Setting up MQTT alert callback...")
        setup_mqtt_alert_callback(mqtt_client, bot)

        # 6. Set startup time for balance handler (before MQTT connection)
        startup_time = time.time()
        balance_handler.set_startup_time(startup_time)
        logger.info(f"✓ Startup time set: {startup_time}")

        # 7. Connect to MQTT broker
        logger.info(
            f"Connecting to MQTT broker at {config.mqtt_broker_host}:{config.mqtt_broker_port}..."
        )
        try:
            await mqtt_client.connect()
            logger.info("✓ MQTT client connected and subscribed to topics")
        except ConnectionError as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            logger.error("Please ensure:")
            logger.error("  1. Mosquitto broker is running: sudo systemctl status mosquitto")
            logger.error("  2. MQTT_BROKER_HOST and MQTT_BROKER_PORT are correct in .env")
            logger.error("  3. Firewall allows connection to MQTT port")
            logger.error("\nBot will continue running and retry connection automatically.")
            # Don't exit - MQTT client has retry logic

        # 8. Setup signal handlers for graceful shutdown
        logger.info("Setting up signal handlers...")
        await setup_signal_handlers(bot)
        logger.info("✓ Signal handlers registered")

        # 9. Start Discord bot (this blocks until bot shuts down)
        logger.info("Starting Discord bot...")
        logger.info("=" * 60)
        logger.info("Bot is starting - waiting for Discord connection...")
        logger.info("=" * 60)

        try:
            await bot.start(config.discord_bot_token)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt (Ctrl+C)")
        except Exception as e:
            logger.error(f"Discord bot error: {e}", exc_info=True)
            raise

        # 10. Cleanup (reached after bot.close() is called)
        logger.info("Bot shutdown complete")
        logger.info("=" * 60)

    except ValueError as e:
        # Configuration error
        error_msg = f"Configuration error: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("See .env.example for reference.")
        sys.exit(1)

    except Exception as e:
        # Unexpected error during startup
        error_msg = f"Unexpected error during startup: {e}"
        if logger:
            logger.error(error_msg, exc_info=True)
        else:
            print(f"ERROR: {error_msg}", file=sys.stderr)
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    """Entry point when running the script directly.

    Runs the async main() function using asyncio.run().
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C (already handled in main)
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
