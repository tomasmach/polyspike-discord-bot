"""Stats slash command and session stats caching for PolySpike Discord Bot.

Displays trading session statistics from MQTT session stats messages.
Caches last session stats for display via /stats command.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord
from discord import app_commands

from src.utils.logger import get_logger


# Cache for last session stats (from polyspike/stats/session retained message)
_last_session_stats: Optional[Dict[str, Any]] = None


def cache_session_stats(payload: Dict[str, Any]) -> None:
    """Cache session stats data for /stats command.

    Should be called by MQTT handler when session stats message is received.

    Args:
        payload: Session stats payload from MQTT.
            Expected fields:
            - timestamp, session_id, duration_seconds
            - initial_balance, final_balance
            - total_pnl, total_pnl_pct
            - total_trades, winning_trades, losing_trades, win_rate
            - max_drawdown, avg_win, avg_loss
    """
    global _last_session_stats
    _last_session_stats = payload.copy()

    logger = get_logger()
    logger.debug("Cached session stats for /stats command")


def get_last_session_stats() -> Optional[Dict[str, Any]]:
    """Get the last cached session stats.

    Returns:
        Copy of last session stats dict, or None if no stats received yet.
    """
    return _last_session_stats.copy() if _last_session_stats else None


def clear_stats_cache() -> None:
    """Clear the cached session stats.

    Useful for testing or manual cache reset.
    """
    global _last_session_stats
    _last_session_stats = None
    logger = get_logger()
    logger.info("Cleared session stats cache")


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string (e.g., "2h 15m", "45m 30s").
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:  # Show minutes if we have hours
        parts.append(f"{minutes}m")
    if secs > 0 and hours == 0:  # Only show seconds if less than 1 hour
        parts.append(f"{secs}s")

    return " ".join(parts) if parts else "0s"


@app_commands.command(
    name="stats",
    description="Show trading session statistics (trades, win rate, P&L, drawdown)",
)
async def stats_command(interaction: discord.Interaction) -> None:
    """Handle /stats slash command.

    Displays trading session statistics from cached MQTT data:
    - Session duration and timeframe
    - Total trades (winning/losing)
    - Win rate percentage
    - Total P&L and P&L percentage
    - Maximum drawdown
    - Average win/loss per trade

    Args:
        interaction: Discord interaction object from slash command invocation.
    """
    logger = get_logger()
    logger.info(f"/stats command invoked by {interaction.user} ({interaction.user.id})")

    try:
        # Defer response
        await interaction.response.defer(thinking=True)

        # Get cached session stats
        stats_data = get_last_session_stats()

        # Case 1: No stats data available yet
        if stats_data is None:
            embed = discord.Embed(
                title="⚪ Session Stats: No Data",
                description=(
                    "No session statistics received from trading bot yet.\n\n"
                    "**Possible reasons:**\n"
                    "• Trading bot hasn't completed a session yet\n"
                    "• No session summary published (sent on bot shutdown)\n"
                    "• MQTT connection issue\n\n"
                    "Stats are published as retained messages when the trading bot stops."
                ),
                color=discord.Color.light_gray(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Session stats are sent when trading bot stops")

            await interaction.followup.send(embed=embed)
            logger.info("/stats: No session stats data available")
            return

        # Extract stats fields with safe defaults
        session_id = stats_data.get("session_id", "Unknown")
        duration_seconds = stats_data.get("duration_seconds", 0)
        initial_balance = stats_data.get("initial_balance", 0.0)
        final_balance = stats_data.get("final_balance", 0.0)
        total_pnl = stats_data.get("total_pnl", 0.0)
        total_pnl_pct = stats_data.get("total_pnl_pct", 0.0)
        total_trades = stats_data.get("total_trades", 0)
        winning_trades = stats_data.get("winning_trades", 0)
        losing_trades = stats_data.get("losing_trades", 0)
        win_rate = stats_data.get("win_rate", 0.0)
        max_drawdown = stats_data.get("max_drawdown", 0.0)
        avg_win = stats_data.get("avg_win", 0.0)
        avg_loss = stats_data.get("avg_loss", 0.0)
        timestamp = stats_data.get("timestamp", datetime.now(timezone.utc).timestamp())

        # Determine embed color based on total P&L
        if total_pnl > 0:
            color = discord.Color.green()
        elif total_pnl < 0:
            color = discord.Color.red()
        else:
            color = discord.Color.light_gray()

        # Create embed
        embed = discord.Embed(
            title="Trading Session Statistics",
            description=f"Session: `{session_id}`",
            color=color,
            timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
        )

        # Session info
        duration_str = format_duration(duration_seconds)
        embed.add_field(
            name="Session Duration",
            value=duration_str,
            inline=True,
        )

        embed.add_field(
            name="Initial Balance",
            value=f"${initial_balance:.2f}",
            inline=True,
        )

        embed.add_field(
            name="Final Balance",
            value=f"${final_balance:.2f}",
            inline=True,
        )

        # P&L metrics
        pnl_sign = "+" if total_pnl >= 0 else ""
        pnl_pct_sign = "+" if total_pnl_pct >= 0 else ""
        status_emoji = "📈" if total_pnl >= 0 else "📉"

        embed.add_field(
            name=f"{status_emoji} Total P&L",
            value=f"**{pnl_sign}${total_pnl:.2f}** ({pnl_pct_sign}{total_pnl_pct*100:.2f}%)",
            inline=False,
        )

        # Trade statistics
        embed.add_field(
            name="Total Trades",
            value=f"**{total_trades}**",
            inline=True,
        )

        embed.add_field(
            name="Winning Trades",
            value=f"{winning_trades}",
            inline=True,
        )

        embed.add_field(
            name="Losing Trades",
            value=f"{losing_trades}",
            inline=True,
        )

        # Win rate
        win_rate_pct = win_rate * 100

        embed.add_field(
            name="Win Rate",
            value=f"**{win_rate_pct:.1f}%**",
            inline=True,
        )

        # Average metrics
        embed.add_field(
            name="Avg Win",
            value=f"${avg_win:.2f}",
            inline=True,
        )

        embed.add_field(
            name="Avg Loss",
            value=f"${abs(avg_loss):.2f}",
            inline=True,
        )

        # Risk metrics
        embed.add_field(
            name="Max Drawdown",
            value=f"${max_drawdown:.2f}",
            inline=True,
        )

        # Profit factor (if we have data)
        if avg_loss != 0 and losing_trades > 0:
            profit_factor = (avg_win * winning_trades) / abs(avg_loss * losing_trades)
            embed.add_field(
                name="Profit Factor",
                value=f"{profit_factor:.2f}",
                inline=True,
            )

        # Footer
        embed.set_footer(text="Last completed trading session")

        await interaction.followup.send(embed=embed)
        logger.info(
            f"/stats: Stats sent successfully (session={session_id}, "
            f"trades={total_trades}, win_rate={win_rate_pct:.1f}%, pnl={total_pnl:+.2f})"
        )

    except Exception as e:
        logger.error(f"Error in /stats command: {e}", exc_info=True)

        # Send error message to user
        error_embed = discord.Embed(
            title="Error",
            description=(
                "An error occurred while fetching session statistics. "
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
            logger.error("Failed to send error message to user")
