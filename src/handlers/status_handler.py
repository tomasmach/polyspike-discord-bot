"""Status event handlers for PolySpike trading bot.

This module handles bot status events from MQTT:
- Bot started
- Bot stopped
- Bot error/critical events
"""

import asyncio
from typing import Any, Dict

import discord

from src.utils.embeds import (
    create_bot_error_embed,
    create_bot_started_embed,
    create_bot_stopped_embed,
)
from src.utils.logger import get_logger


def handle_bot_started(payload: Dict[str, Any], bot: discord.Client) -> None:
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


def handle_bot_stopped(payload: Dict[str, Any], bot: discord.Client) -> None:
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


def handle_bot_error(payload: Dict[str, Any], bot: discord.Client) -> None:
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
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send bot started notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    # Create embed
    embed = create_bot_started_embed(payload)

    # Send using safe send method (handles all error cases)
    success = await bot.safe_send_to_channel(embed)

    if success:
        logger.info("Bot started notification sent successfully")
    else:
        logger.error("Failed to send bot started notification (see errors above)")


async def _send_bot_stopped_notification(
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send bot stopped notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    # Create embed
    embed = create_bot_stopped_embed(payload)

    # Send using safe send method (handles all error cases)
    success = await bot.safe_send_to_channel(embed)

    if success:
        logger.info("Bot stopped notification sent successfully")
    else:
        logger.error("Failed to send bot stopped notification (see errors above)")


async def _send_bot_error_notification(
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send bot error notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()
    severity = payload.get("severity", "error")

    # Create embed
    embed = create_bot_error_embed(payload)

    # Send using safe send method (handles all error cases)
    success = await bot.safe_send_to_channel(embed)

    if success:
        logger.info(f"Bot error notification ({severity}) sent successfully")
    else:
        logger.error("Failed to send bot error notification (see errors above)")
