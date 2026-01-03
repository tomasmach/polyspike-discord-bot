"""Discord Embed builders for PolySpike trading bot events.

This module provides functions to create rich Discord embeds for various
MQTT events from the PolySpike Hunter trading bot.
"""

from datetime import datetime
from typing import Any, Dict

import discord


def create_position_opened_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for position opened event.

    Args:
        payload: MQTT message payload containing position data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - market_name (str): Market name
            - entry_price (float): Entry price
            - position_size (float): Position size in USD
            - reason (str): Entry reason
            - spike_magnitude (float, optional): Spike magnitude

    Returns:
        Discord Embed with green color and position details.
    """
    market_name = payload.get("market_name", "Unknown Market")
    entry_price = payload.get("entry_price", 0.0)
    position_size = payload.get("position_size", 0.0)
    reason = payload.get("reason", "unknown")
    spike_magnitude = payload.get("spike_magnitude")
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    embed = discord.Embed(
        title="Position Opened",
        description=market_name,
        color=0x00FF00,  # Green
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Entry Price",
        value=f"{entry_price:.4f}",
        inline=True
    )
    embed.add_field(
        name="Size",
        value=f"${position_size:.2f}",
        inline=True
    )
    embed.add_field(
        name="Reason",
        value=reason.replace("_", " ").title(),
        inline=True
    )

    if spike_magnitude is not None:
        embed.add_field(
            name="Spike Magnitude",
            value=f"{spike_magnitude * 100:+.2f}%",
            inline=True
        )

    return embed


def create_trade_completed_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for trade completed event.

    Args:
        payload: MQTT message payload containing trade data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - market_name (str): Market name
            - entry_price (float): Entry price
            - exit_price (float): Exit price
            - size (float): Position size
            - pnl (float): Profit & Loss in USD
            - pnl_pct (float): P&L percentage
            - duration_seconds (int): Trade duration
            - reason (str): Exit reason

    Returns:
        Discord Embed with color based on P&L (green=profit, red=loss).
    """
    market_name = payload.get("market_name", "Unknown Market")
    entry_price = payload.get("entry_price", 0.0)
    exit_price = payload.get("exit_price", 0.0)
    pnl = payload.get("pnl", 0.0)
    pnl_pct = payload.get("pnl_pct", 0.0)
    duration_seconds = payload.get("duration_seconds", 0)
    reason = payload.get("reason", "unknown")
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    # Color based on P&L
    color = 0x00FF00 if pnl >= 0 else 0xFF0000  # Green if profit, red if loss

    embed = discord.Embed(
        title="Trade Completed",
        description=market_name,
        color=color,
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Entry Price",
        value=f"{entry_price:.4f}",
        inline=True
    )
    embed.add_field(
        name="Exit Price",
        value=f"{exit_price:.4f}",
        inline=True
    )
    embed.add_field(
        name="P&L",
        value=f"${pnl:+.2f}",
        inline=True
    )
    embed.add_field(
        name="P&L %",
        value=f"{pnl_pct * 100:+.2f}%",
        inline=True
    )
    embed.add_field(
        name="Duration",
        value=_format_duration(duration_seconds),
        inline=True
    )
    embed.add_field(
        name="Exit Reason",
        value=reason.replace("_", " ").title(),
        inline=True
    )

    return embed


def create_balance_update_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for balance update event.

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

    Returns:
        Discord Embed with blue color and balance details.
    """
    balance = payload.get("balance", 0.0)
    equity = payload.get("equity", 0.0)
    available_balance = payload.get("available_balance", 0.0)
    locked_in_positions = payload.get("locked_in_positions", 0.0)
    unrealized_pnl = payload.get("unrealized_pnl", 0.0)
    total_pnl = payload.get("total_pnl", 0.0)
    update_reason = payload.get("update_reason", "unknown")
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    embed = discord.Embed(
        title="Balance Update",
        description=f"Reason: {update_reason.replace('_', ' ').title()}",
        color=0x3498DB,  # Blue
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Balance",
        value=f"${balance:.2f}",
        inline=True
    )
    embed.add_field(
        name="Equity",
        value=f"${equity:.2f}",
        inline=True
    )
    embed.add_field(
        name="Available",
        value=f"${available_balance:.2f}",
        inline=True
    )
    embed.add_field(
        name="Locked",
        value=f"${locked_in_positions:.2f}",
        inline=True
    )
    embed.add_field(
        name="Unrealized P&L",
        value=f"${unrealized_pnl:+.2f}",
        inline=True
    )
    embed.add_field(
        name="Total P&L",
        value=f"${total_pnl:+.2f}",
        inline=True
    )

    return embed


def create_bot_started_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for bot started event.

    Args:
        payload: MQTT message payload containing startup data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - session_id (str): Unique session ID
            - config.initial_balance (float): Starting balance
            - config.spike_threshold (float): Spike threshold
            - config.position_size (float): Position size
            - config.monitored_markets (int): Number of markets

    Returns:
        Discord Embed with green color and startup info.
    """
    session_id = payload.get("session_id", "unknown")
    config = payload.get("config", {})
    initial_balance = config.get("initial_balance", 0.0)
    spike_threshold = config.get("spike_threshold", 0.0)
    position_size = config.get("position_size", 0.0)
    monitored_markets = config.get("monitored_markets", 0)
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    embed = discord.Embed(
        title="Bot Started",
        description=f"Session: `{session_id}`",
        color=0x00FF00,  # Green
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Initial Balance",
        value=f"${initial_balance:.2f}",
        inline=True
    )
    embed.add_field(
        name="Spike Threshold",
        value=f"{spike_threshold * 100:.1f}%",
        inline=True
    )
    embed.add_field(
        name="Position Size",
        value=f"${position_size:.2f}",
        inline=True
    )
    embed.add_field(
        name="Monitored Markets",
        value=str(monitored_markets),
        inline=True
    )

    return embed


def create_bot_stopped_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for bot stopped event.

    Args:
        payload: MQTT message payload containing shutdown data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - session_id (str): Session ID
            - final_stats.total_pnl (float): Total P&L
            - final_stats.total_trades (int): Total trades
            - final_stats.win_rate (float): Win rate

    Returns:
        Discord Embed with red color and final statistics.
    """
    session_id = payload.get("session_id", "unknown")
    final_stats = payload.get("final_stats", {})
    total_pnl = final_stats.get("total_pnl", 0.0)
    total_trades = final_stats.get("total_trades", 0)
    win_rate = final_stats.get("win_rate", 0.0)
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    embed = discord.Embed(
        title="Bot Stopped",
        description=f"Session: `{session_id}`",
        color=0xFF0000,  # Red
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Total P&L",
        value=f"${total_pnl:+.2f}",
        inline=True
    )
    embed.add_field(
        name="Total Trades",
        value=str(total_trades),
        inline=True
    )
    embed.add_field(
        name="Win Rate",
        value=f"{win_rate * 100:.1f}%",
        inline=True
    )

    return embed


def create_bot_error_embed(payload: Dict[str, Any]) -> discord.Embed:
    """Create embed for bot error event.

    Args:
        payload: MQTT message payload containing error data.
            Expected fields:
            - timestamp (float): Unix timestamp
            - error_type (str): Error type
            - error_message (str): Error message
            - severity (str): Error severity (critical/error/warning)

    Returns:
        Discord Embed with color based on severity (red/orange/yellow).
    """
    error_type = payload.get("error_type", "UnknownError")
    error_message = payload.get("error_message", "No error message provided")
    severity = payload.get("severity", "error").lower()
    timestamp = payload.get("timestamp", datetime.now().timestamp())

    # Color based on severity
    color_map = {
        "critical": 0xFF0000,  # Red
        "error": 0xFF6B35,     # Orange
        "warning": 0xFFAA00    # Yellow
    }
    color = color_map.get(severity, 0xFF0000)

    embed = discord.Embed(
        title=f"Bot Error ({severity.upper()})",
        description=error_message,
        color=color,
        timestamp=datetime.fromtimestamp(timestamp)
    )

    embed.add_field(
        name="Error Type",
        value=f"`{error_type}`",
        inline=False
    )

    return embed


def create_heartbeat_alert_embed(data: Dict[str, Any]) -> discord.Embed:
    """Create embed for heartbeat timeout alert.

    Args:
        data: Alert data containing heartbeat information.
            Expected fields:
            - last_heartbeat (float): Last heartbeat timestamp
            - missing_seconds (int): Seconds since last heartbeat

    Returns:
        Discord Embed with yellow color and alert details.
    """
    last_heartbeat = data.get("last_heartbeat")
    missing_seconds = data.get("missing_seconds", 0)

    embed = discord.Embed(
        title="Heartbeat Alert",
        description="No heartbeat received from trading bot",
        color=0xFFAA00,  # Yellow
        timestamp=datetime.now()
    )

    if last_heartbeat:
        last_time = datetime.fromtimestamp(last_heartbeat)
        embed.add_field(
            name="Last Heartbeat",
            value=last_time.strftime("%Y-%m-%d %H:%M:%S"),
            inline=True
        )

    embed.add_field(
        name="Missing For",
        value=_format_duration(missing_seconds),
        inline=True
    )

    embed.add_field(
        name="Status",
        value="Bot may be offline or experiencing issues",
        inline=False
    )

    return embed


def create_mqtt_connection_alert_embed(message: str, downtime_seconds: float) -> discord.Embed:
    """Create embed for MQTT connection alert.

    Args:
        message: Alert message describing the issue.
        downtime_seconds: Number of seconds MQTT has been down.

    Returns:
        Discord Embed with red color and connection alert details.
    """
    downtime_int = int(downtime_seconds)

    embed = discord.Embed(
        title="MQTT Connection Alert",
        description=message,
        color=0xFF0000,  # Red
        timestamp=datetime.now()
    )

    embed.add_field(
        name="Downtime",
        value=_format_duration(downtime_int),
        inline=True
    )

    embed.add_field(
        name="Status",
        value="Unable to reach MQTT broker",
        inline=True
    )

    embed.add_field(
        name="Action Required",
        value=(
            "• Check MQTT broker is running: `systemctl status mosquitto`\n"
            "• Check network connectivity\n"
            "• Review bot logs for connection errors"
        ),
        inline=False
    )

    return embed


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., "1h 23m 45s", "45s", "2m 30s").
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        if remaining_seconds > 0:
            return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
        elif remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h"
