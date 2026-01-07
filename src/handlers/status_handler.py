"""Status event handlers for PolySpike trading bot.

This module handles bot status events from MQTT:
- Bot started
- Bot stopped
- Bot error/critical events
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict

import discord

if TYPE_CHECKING:
    from src.bot import PolySpikeBot

from src.utils.embeds import (
    create_bot_error_embed,
    create_bot_started_embed,
    create_bot_stopped_embed,
)
from src.utils.logger import get_logger


def handle_bot_started(payload: Dict[str, Any], bot: PolySpikeBot) -> None:
    """Handle bot started event.

    Creates async task to send Discord notification when trading bot starts.

    Args:
        payload: MQTT message payload containing startup data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - session_id (str): Unique session ID
            - config.initial_balance (float): Starting balance
            - config.spike_threshold (float): Spike threshold
            - config.position_size (float): Position size
            - config.monitored_markets (int): Number of markets
        bot: Discord bot client instance.
    """
    logger = get_logger()
    logger.info("Received bot started event")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_bot_started_notification(payload, bot))


def handle_bot_stopped(payload: Dict[str, Any], bot: PolySpikeBot) -> None:
    """Handle bot stopped event.

    Creates async task to send Discord notification when trading bot stops.

    Args:
        payload: MQTT message payload containing shutdown data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - session_id (str): Session ID
            - final_stats.total_pnl (float): Total P&L
            - final_stats.total_trades (int): Total trades
            - final_stats.win_rate (float): Win rate
        bot: Discord bot client instance.
    """
    logger = get_logger()
    logger.info("Received bot stopped event")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_bot_stopped_notification(payload, bot))


def handle_bot_error(payload: Dict[str, Any], bot: PolySpikeBot) -> None:
    """Handle bot error event.

    Creates async task to send Discord notification when trading bot encounters an error.

    Args:
        payload: MQTT message payload containing error data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - error_type (str): Error type
            - error_message (str): Error message
            - severity (str): Error severity (critical/error/warning)
        bot: Discord bot client instance.
    """
    logger = get_logger()
    severity = payload.get("severity", "error")
    logger.info(f"Received bot error event (severity: {severity})")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_bot_error_notification(payload, bot))


async def _send_bot_started_notification(
    payload: Dict[str, Any], bot: PolySpikeBot
) -> None:
    """Send bot started notification to Discord channel.

    Args:
        payload: MQTT message payload containing startup configuration.
        bot: PolySpikeBot instance with safe_send_to_channel method.
    """
    logger = get_logger()

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["session_id", "config"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Bot started payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Check nested config fields
        if "config" in payload:
            config_fields = ["initial_balance", "spike_threshold", "position_size"]
            missing_config = [
                f for f in config_fields if f not in payload.get("config", {})
            ]
            if missing_config:
                logger.warning(
                    f"Bot started config missing fields: {missing_config}. "
                    f"Notification will use default values."
                )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_bot_started_embed(payload)

        # Send using safe send method (handles all error cases)
        success = await bot.safe_send_to_channel(embed)

        if success:
            logger.info("Bot started notification sent successfully")
        else:
            logger.error("Failed to send bot started notification (see errors above)")

    except Exception as e:
        logger.error(
            f"Unexpected error in _send_bot_started_notification: {e}",
            exc_info=True,
        )


async def _send_bot_stopped_notification(
    payload: Dict[str, Any], bot: PolySpikeBot
) -> None:
    """Send bot stopped notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["session_id", "final_stats"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Bot stopped payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Check nested final_stats fields
        if "final_stats" in payload:
            stats_fields = ["total_pnl", "total_trades", "win_rate"]
            missing_stats = [
                f for f in stats_fields if f not in payload.get("final_stats", {})
            ]
            if missing_stats:
                logger.warning(
                    f"Bot stopped final_stats missing fields: {missing_stats}. "
                    f"Notification will use default values."
                )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_bot_stopped_embed(payload)

        # Send using safe send method (handles all error cases)
        success = await bot.safe_send_to_channel(embed)

        if success:
            logger.info("Bot stopped notification sent successfully")
        else:
            logger.error("Failed to send bot stopped notification (see errors above)")

    except Exception as e:
        logger.error(
            f"Unexpected error in _send_bot_stopped_notification: {e}",
            exc_info=True,
        )


async def _send_bot_error_notification(
    payload: Dict[str, Any], bot: PolySpikeBot
) -> None:
    """Send bot error notification to Discord channel.

    Args:
        payload: MQTT message payload containing error details.
        bot: PolySpikeBot instance with safe_send_to_channel method.
    """
    logger = get_logger()
    severity = payload.get("severity", "error")

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["error_type", "error_message"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Bot error payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_bot_error_embed(payload)

        # Send using safe send method (handles all error cases)
        success = await bot.safe_send_to_channel(embed)

        if success:
            logger.info(f"Bot error notification ({severity}) sent successfully")
        else:
            logger.error("Failed to send bot error notification (see errors above)")

    except Exception as e:
        logger.error(
            f"Unexpected error in _send_bot_error_notification: {e}",
            exc_info=True,
        )
