"""Trading event handlers for PolySpike trading bot.

This module handles trading-related events from MQTT:
- Position opened
- Trade completed (with duplicate detection)
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Dict

import discord

if TYPE_CHECKING:
    from src.bot import PolySpikeBot

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


def handle_position_opened(payload: Dict[str, Any], bot: PolySpikeBot) -> None:
    """Handle position opened event from MQTT.

    Creates an async task to send a Discord notification when a trading
    position is opened. This function is called synchronously by the MQTT
    message handler and schedules the Discord notification asynchronously.

    Args:
        payload: MQTT message payload containing position data.
            Expected fields:
            - timestamp (float): Unix timestamp of the event.
            - token_id (str): Polymarket token ID.
            - market_name (str): Human-readable market name.
            - entry_price (float): Entry price for the position.
            - position_size (float): Position size in USD.
            - reason (str): Entry reason (e.g., "spike_detected").
            - spike_magnitude (float, optional): Magnitude of detected spike.
        bot: Discord bot client instance used to send notifications.

    Returns:
        None. The notification is sent asynchronously.
    """
    logger = get_logger()
    logger.info("Received position opened event")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_position_opened_notification(payload, bot))


def handle_trade_completed(payload: Dict[str, Any], bot: PolySpikeBot) -> None:
    """Handle trade completed event with duplicate detection.

    Creates an async task to send a Discord notification when a trade is completed.
    Implements duplicate detection using trade_id to prevent notification spam
    from MQTT QoS 1 message redelivery.

    Args:
        payload: MQTT message payload containing trade data.
            Expected fields:
            - timestamp (float): Unix timestamp of the event.
            - trade_id (str): Unique trade identifier for deduplication.
            - token_id (str): Polymarket token ID.
            - market_name (str): Human-readable market name.
            - entry_price (float): Entry price for the position.
            - exit_price (float): Exit price for the position.
            - size (float): Position size in USD.
            - pnl (float): Realized profit/loss in USD.
            - pnl_pct (float): P&L as a decimal (0.05 = 5%).
            - duration_seconds (int): Trade duration in seconds.
            - reason (str): Exit reason (e.g., "take_profit", "stop_loss").
        bot: Discord bot client instance used to send notifications.

    Returns:
        None. The notification is sent asynchronously, or skipped if duplicate.
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
    payload: Dict[str, Any], bot: PolySpikeBot
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
    payload: Dict[str, Any], bot: PolySpikeBot
) -> None:
    """Send trade completed notification to Discord channel.

    Args:
        payload: MQTT message payload containing trade data.
        bot: PolySpikeBot instance with safe_send_to_channel method.
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
