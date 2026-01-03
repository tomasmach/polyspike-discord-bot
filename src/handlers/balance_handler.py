"""Balance event handlers for PolySpike trading bot.

This module handles balance update events from MQTT:
- Balance updates (periodic, after trades, significant changes)
- Old retained message filtering
- Balance data caching for slash commands
"""

import asyncio
import time
from typing import Any, Dict, Optional

import discord

from src.utils.embeds import create_balance_update_embed
from src.utils.logger import get_logger


# Bot startup time (set when handler is initialized)
_startup_time: float = time.time()

# Cache for last balance data (used by /balance slash command)
_last_balance_data: Optional[Dict[str, Any]] = None

# Time threshold for ignoring old retained messages (5 minutes)
_OLD_MESSAGE_THRESHOLD = 300  # seconds


def set_startup_time(timestamp: float) -> None:
    """Set the bot startup time for old message filtering.

    Should be called when the bot starts, before connecting to MQTT.
    This allows filtering out old retained messages that were published
    before the bot started.

    Args:
        timestamp: Unix timestamp of bot startup.
    """
    global _startup_time
    _startup_time = timestamp
    logger = get_logger()
    logger.info(f"Balance handler startup time set to {timestamp}")


def handle_balance_update(payload: Dict[str, Any], bot: discord.Client) -> None:
    """Handle balance update event with old message filtering.

    Creates async task to send Discord notification when balance updates.
    Filters out old retained messages that were published before bot startup.
    Caches balance data for /balance slash command.

    Args:
        payload: MQTT message payload containing balance data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - balance (float): Cash balance
            - equity (float): Balance + unrealized P&L
            - available_balance (float): Available balance
            - locked_in_positions (float): Locked capital
            - unrealized_pnl (float): Unrealized P&L
            - total_pnl (float): Total realized P&L
            - update_reason (str): Update reason
        bot: Discord bot client instance.
    """
    logger = get_logger()

    # Check if message is old retained message
    msg_timestamp = payload.get("timestamp", 0)
    if msg_timestamp < _startup_time - _OLD_MESSAGE_THRESHOLD:
        logger.debug(
            f"Ignoring old retained balance message "
            f"(msg_time={msg_timestamp}, startup={_startup_time})"
        )
        return

    logger.info("Received balance update event")

    # Cache balance data for /balance command
    global _last_balance_data
    _last_balance_data = payload.copy()
    logger.debug("Cached balance data for /balance command")

    # Schedule async task on bot's event loop
    asyncio.create_task(_send_balance_update_notification(payload, bot))


async def _send_balance_update_notification(
    payload: Dict[str, Any], bot: discord.Client
) -> None:
    """Send balance update notification to Discord channel.

    Args:
        payload: MQTT message payload.
        bot: Discord bot client instance.
    """
    logger = get_logger()

    try:
        # Validate important fields (warn if missing, but still send notification)
        important_fields = ["balance", "equity", "total_pnl"]
        missing_fields = [f for f in important_fields if f not in payload]

        if missing_fields:
            logger.warning(
                f"Balance update payload missing fields: {missing_fields}. "
                f"Notification will use default values."
            )

        # Create embed (embed builder handles missing fields gracefully)
        embed = create_balance_update_embed(payload)

        # Get notification channel
        channel_id = bot.config.discord_channel_id
        channel = bot.get_channel(channel_id)

        if channel is None:
            logger.error(
                f"Notification channel {channel_id} not found. "
                "Please check DISCORD_CHANNEL_ID in .env"
            )
            return

        if not isinstance(channel, discord.TextChannel):
            logger.error(
                f"Channel {channel_id} is not a text channel. "
                f"Got {type(channel).__name__}"
            )
            return

        # Send embed
        await channel.send(embed=embed)
        logger.info("Balance update notification sent successfully")

    except discord.errors.Forbidden:
        logger.error(
            "Permission denied: Cannot send messages to notification channel. "
            "Please check bot permissions in Discord server settings."
        )
    except discord.errors.HTTPException as e:
        logger.error(f"Failed to send balance update notification: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error in _send_balance_update_notification: {e}",
            exc_info=True,
        )


def get_last_balance_data() -> Optional[Dict[str, Any]]:
    """Get the last cached balance data.

    Used by /balance slash command to display current balance without
    waiting for next MQTT update.

    Returns:
        Copy of last balance data dict, or None if no balance update received yet.
    """
    return _last_balance_data.copy() if _last_balance_data else None


def clear_balance_cache() -> None:
    """Clear the cached balance data.

    Useful for testing or manual cache reset.
    """
    global _last_balance_data
    _last_balance_data = None
    logger = get_logger()
    logger.info("Cleared balance cache")


def get_startup_time() -> float:
    """Get the current startup time threshold.

    Returns:
        Startup time as Unix timestamp.
    """
    return _startup_time
