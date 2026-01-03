"""Status slash command for PolySpike Discord Bot.

Displays trading bot status based on heartbeat data.
Shows online/offline status, uptime, balance, and trade statistics.
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands

from src.utils.logger import get_logger


def format_uptime(seconds: int) -> str:
    """Format uptime seconds into human-readable string.

    Args:
        seconds: Uptime in seconds.

    Returns:
        Formatted uptime string (e.g., "2h 15m 30s").
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:  # Always show seconds if no other parts
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_timestamp_relative(timestamp: float) -> str:
    """Format timestamp as relative time (e.g., '2 minutes ago').

    Args:
        timestamp: Unix timestamp.

    Returns:
        Human-readable relative time string.
    """
    from datetime import datetime
    import time

    now = time.time()
    diff = int(now - timestamp)

    if diff < 60:
        return f"{diff} seconds ago"
    elif diff < 3600:
        minutes = diff // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = diff // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"


@app_commands.command(
    name="status",
    description="Show PolySpike trading bot status (online/offline, uptime, stats)",
)
async def status_command(interaction: discord.Interaction) -> None:
    """Handle /status slash command.

    Displays trading bot status based on heartbeat monitoring:
    - Online/Offline status
    - Last heartbeat time
    - Uptime, balance, open positions, total trades (if online)

    Args:
        interaction: Discord interaction object from slash command invocation.
    """
    logger = get_logger()
    logger.info(f"/status command invoked by {interaction.user} ({interaction.user.id})")

    try:
        # Defer response (commands can take a moment to process)
        await interaction.response.defer(thinking=True)

        # Get bot instance from interaction client
        bot = interaction.client

        # Check if heartbeat monitor exists
        if not hasattr(bot, "heartbeat_monitor") or bot.heartbeat_monitor is None:
            embed = discord.Embed(
                title="❓ Status Unknown",
                description="Heartbeat monitor not initialized. Bot may still be starting up.",
                color=discord.Color.light_gray(),
                timestamp=datetime.now(timezone.utc),
            )
            await interaction.followup.send(embed=embed)
            return

        heartbeat_monitor = bot.heartbeat_monitor

        # Get heartbeat data
        last_heartbeat_time = heartbeat_monitor.get_last_heartbeat_time()
        is_online = heartbeat_monitor.is_bot_online()
        time_since_heartbeat = heartbeat_monitor.get_time_since_last_heartbeat()

        # Case 1: No heartbeat data received yet
        if last_heartbeat_time is None:
            embed = discord.Embed(
                title="⚪ Trading Bot Status: No Data",
                description=(
                    "No heartbeat received from trading bot yet.\n\n"
                    "**Possible reasons:**\n"
                    "• Trading bot is not running\n"
                    "• Trading bot hasn't sent first heartbeat (wait ~30s)\n"
                    "• MQTT connection issue"
                ),
                color=discord.Color.light_gray(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Heartbeats are sent every 30 seconds")

            await interaction.followup.send(embed=embed)
            logger.info("/status: No heartbeat data available")
            return

        # Case 2: Bot is offline (heartbeat timeout)
        if not is_online:
            last_seen = format_timestamp_relative(last_heartbeat_time)

            embed = discord.Embed(
                title="🔴 Trading Bot Status: OFFLINE",
                description=(
                    f"⚠️ **Trading bot appears to be offline**\n\n"
                    f"Last heartbeat: **{last_seen}**\n"
                    f"Timeout threshold: {heartbeat_monitor.timeout_seconds}s"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )

            # Add last heartbeat timestamp
            last_heartbeat_dt = datetime.fromtimestamp(
                last_heartbeat_time, tz=timezone.utc
            )
            embed.add_field(
                name="Last Seen",
                value=f"<t:{int(last_heartbeat_time)}:F>",
                inline=False,
            )

            embed.set_footer(
                text="Bot is considered offline if heartbeat missing >90s"
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"/status: Bot offline (last heartbeat: {last_seen})")
            return

        # Case 3: Bot is online - show full status
        # Note: We only have basic heartbeat data, full stats would need caching
        # For now, we show what's available from the last heartbeat

        embed = discord.Embed(
            title="🟢 Trading Bot Status: ONLINE",
            description="Trading bot is active and sending heartbeats",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )

        # Last heartbeat time
        last_seen = format_timestamp_relative(last_heartbeat_time)
        embed.add_field(
            name="📡 Last Heartbeat",
            value=f"{last_seen}",
            inline=True,
        )

        # Connection quality indicator
        if time_since_heartbeat is not None:
            if time_since_heartbeat < 45:
                connection_status = "🟢 Excellent"
            elif time_since_heartbeat < 60:
                connection_status = "🟡 Good"
            else:
                connection_status = "🟠 Fair"

            embed.add_field(
                name="Connection",
                value=connection_status,
                inline=True,
            )

        # Note about detailed stats
        embed.add_field(
            name="ℹ️ Note",
            value=(
                "Detailed statistics (uptime, balance, trades) "
                "will be available in future updates.\n"
                "Use `/balance` for balance info (coming soon)."
            ),
            inline=False,
        )

        embed.set_footer(text="Heartbeat interval: 30 seconds")

        await interaction.followup.send(embed=embed)
        logger.info("/status: Bot online, status sent successfully")

    except Exception as e:
        logger.error(f"Error in /status command: {e}", exc_info=True)

        # Send error message to user
        error_embed = discord.Embed(
            title="❌ Error",
            description=(
                "An error occurred while fetching bot status. "
                "Please try again later."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception:
            # If sending error message fails, log it
            logger.error("Failed to send error message to user")
