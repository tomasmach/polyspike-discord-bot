"""Trading event handlers for PolySpike trading bot.

This module handles trading-related events from MQTT:
- Position opened
- Trade completed (with duplicate detection)
"""

import asyncio
from collections import OrderedDict
from typing import Any, Dict

import discord

from src.utils.embeds import (
    create_position_opened_embed,
    create_trade_completed_embed,
)
from src.utils.logger import get_logger


# Global ordered dict to track seen trade IDs (prevents duplicates from QoS 1)
# Using OrderedDict for FIFO eviction when max size exceeded
_seen_trade_ids: OrderedDict[str, None] = OrderedDict()
# Limit size to prevent unbounded memory growth
_MAX_SEEN_TRADES = 1000


def handle_position_opened(payload: Dict[str, Any], bot: discord.Client) -> None:
    """Handle position opened event.

    Creates async task to send Discord notification when a trading position is opened.

    Args:
        payload: MQTT message payload containing position data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - token_id (str): Polymarket token ID
            - market_name (str): Market name
            - entry_price (float): Entry price
            - position_size (float): Position size in USD
            - reason (str): Entry reason
            - spike_magnitude (float, optional): Spike magnitude
        bot: Discord bot client instance.
    """
    logger = get_logger()
    logger.info("Received position opened event")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_position_opened_notification(payload, bot))


def handle_trade_completed(payload: Dict[str, Any], bot: discord.Client) -> None:
    """Handle trade completed event with duplicate detection.

    Creates async task to send Discord notification when a trade is completed.
    Implements duplicate detection using trade_id to prevent spam from QoS 1 redelivery.

    Args:
        payload: MQTT message payload containing trade data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - trade_id (str): Unique trade ID
            - token_id (str): Polymarket token ID
            - market_name (str): Market name
            - entry_price (float): Entry price
            - exit_price (float): Exit price
            - size (float): Position size
            - pnl (float): Profit & Loss in USD
            - pnl_pct (float): P&L percentage
            - duration_seconds (int): Trade duration
            - reason (str): Exit reason
        bot: Discord bot client instance.
    """
    logger = get_logger()

    # Check for duplicate trade_id (QoS 1 may deliver duplicates)
    trade_id = payload.get("trade_id")
    if trade_id:
        if trade_id in _seen_trade_ids:
            logger.debug(f"Ignoring duplicate trade_id: {trade_id}")
            return

        # Add to seen dict (move to end if already exists)
        _seen_trade_ids[trade_id] = None

        # Prevent unbounded memory growth - keep only last N trades
        if len(_seen_trade_ids) > _MAX_SEEN_TRADES:
            # Remove oldest entry (FIFO)
            _seen_trade_ids.popitem(last=False)
            logger.debug(f"Pruned seen_trade_ids cache (size: {len(_seen_trade_ids)})")

    logger.info("Received trade completed event")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_trade_completed_notification(payload, bot))


async def _send_position_opened_notification(
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send position opened notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["market_name", "entry_price", "position_size"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Position opened payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_position_opened_embed(payload)

        # Send using safe send method (handles all error cases)
        success = await bot.safe_send_to_channel(embed)

        if success:
            logger.info("Position opened notification sent successfully")
        else:
            logger.error("Failed to send position opened notification (see errors above)")

    except Exception as e:
        logger.error(
            f"Unexpected error in _send_position_opened_notification: {e}",
            exc_info=True,
        )


async def _send_trade_completed_notification(
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send trade completed notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["market_name", "pnl", "pnl_pct"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Trade completed payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_trade_completed_embed(payload)

        # Send using safe send method (handles all error cases)
        success = await bot.safe_send_to_channel(embed)

        if success:
            logger.info("Trade completed notification sent successfully")
        else:
            logger.error("Failed to send trade completed notification (see errors above)")

    except Exception as e:
        logger.error(
            f"Unexpected error in _send_trade_completed_notification: {e}",
            exc_info=True,
        )


def clear_seen_trades() -> None:
    """Clear the seen trade IDs set.

    Useful for testing or manual cache clearing.
    """
    global _seen_trade_ids
    _seen_trade_ids.clear()
    logger = get_logger()
    logger.info("Cleared seen trade IDs cache")


def get_seen_trades_count() -> int:
    """Get the number of tracked trade IDs.

    Returns:
        Number of trade IDs currently in the seen set.
    """
    return len(_seen_trade_ids)
