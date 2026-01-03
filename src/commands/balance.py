"""Balance slash command for PolySpike Discord Bot.

Displays current trading bot balance and P&L information
from cached balance data received via MQTT.
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands

from src.handlers import balance_handler
from src.utils.logger import get_logger


def format_currency(value: float) -> str:
    """Format currency value with proper sign and 2 decimal places.

    Args:
        value: Currency value to format.

    Returns:
        Formatted string (e.g., "+$5.23", "-$2.50", "$100.00").
    """
    if value > 0:
        return f"+${value:.2f}"
    elif value < 0:
        return f"-${abs(value):.2f}"
    else:
        return f"${value:.2f}"


def format_percentage(value: float) -> str:
    """Format percentage value with proper sign.

    Args:
        value: Percentage value as decimal (e.g., 0.0523 for 5.23%).

    Returns:
        Formatted string (e.g., "+5.23%", "-2.15%", "0.00%").
    """
    pct = value * 100
    if pct > 0:
        return f"+{pct:.2f}%"
    elif pct < 0:
        return f"{pct:.2f}%"
    else:
        return f"{pct:.2f}%"


@app_commands.command(
    name="balance",
    description="Show current trading bot balance and P&L",
)
async def balance_command(interaction: discord.Interaction) -> None:
    """Handle /balance slash command.

    Displays trading bot balance information from cached MQTT data:
    - Current balance (cash)
    - Equity (balance + unrealized P&L)
    - Available balance (for new trades)
    - Locked in positions
    - Unrealized P&L (from open positions)
    - Total realized P&L (session total)

    Args:
        interaction: Discord interaction object from slash command invocation.
    """
    logger = get_logger()
    logger.info(f"/balance command invoked by {interaction.user} ({interaction.user.id})")

    try:
        # Defer response
        await interaction.response.defer(thinking=True)

        # Get cached balance data
        balance_data = balance_handler.get_last_balance_data()

        # Case 1: No balance data available yet
        if balance_data is None:
            embed = discord.Embed(
                title="⚪ Balance: No Data",
                description=(
                    "No balance update received from trading bot yet.\n\n"
                    "**Possible reasons:**\n"
                    "• Trading bot is not running\n"
                    "• No balance update sent yet (sent every 12h or after trades)\n"
                    "• MQTT connection issue"
                ),
                color=discord.Color.light_gray(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Balance updates: every 12h or after trades")

            await interaction.followup.send(embed=embed)
            logger.info("/balance: No balance data available")
            return

        # Extract balance fields with safe defaults
        balance = balance_data.get("balance", 0.0)
        equity = balance_data.get("equity", 0.0)
        available_balance = balance_data.get("available_balance", 0.0)
        locked_in_positions = balance_data.get("locked_in_positions", 0.0)
        unrealized_pnl = balance_data.get("unrealized_pnl", 0.0)
        total_pnl = balance_data.get("total_pnl", 0.0)
        update_reason = balance_data.get("update_reason", "unknown")
        timestamp = balance_data.get("timestamp", datetime.now(timezone.utc).timestamp())

        # Determine embed color based on total P&L
        if total_pnl > 0:
            color = discord.Color.green()
        elif total_pnl < 0:
            color = discord.Color.red()
        else:
            color = discord.Color.light_gray()

        # Create embed
        embed = discord.Embed(
            title="Trading Bot Balance",
            description=f"Current account status and P&L",
            color=color,
            timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
        )

        # Balance section
        embed.add_field(
            name="Cash Balance",
            value=f"**${balance:.2f}**",
            inline=True,
        )

        embed.add_field(
            name="Total Equity",
            value=f"**${equity:.2f}**",
            inline=True,
        )

        embed.add_field(
            name="Available",
            value=f"${available_balance:.2f}",
            inline=True,
        )

        # Position info
        if locked_in_positions > 0:
            embed.add_field(
                name="Locked (Open Positions)",
                value=f"${locked_in_positions:.2f}",
                inline=True,
            )

        # P&L section
        if unrealized_pnl != 0:
            unrealized_display = format_currency(unrealized_pnl)
            embed.add_field(
                name="Unrealized P&L",
                value=f"**{unrealized_display}**",
                inline=True,
            )

        # Total P&L (most important metric)
        total_pnl_display = format_currency(total_pnl)

        # Calculate P&L percentage if we can infer initial balance
        # Assuming total_pnl is profit/loss from initial balance
        # We don't have initial balance in the payload, so we can't calculate exact %
        # But we can show the absolute value prominently

        embed.add_field(
            name=f"{pnl_emoji} Total Realized P&L",
            value=f"**{total_pnl_display}**",
            inline=True,
        )

        # Update reason
        embed.add_field(
            name="Last Update Reason",
            value=f"{update_reason.replace('_', ' ').title()}",
            inline=False,
        )

        # Footer with update frequency info
        embed.set_footer(
            text="Balance updates: every 12h, after trades, or on significant changes"
        )

        await interaction.followup.send(embed=embed)
        logger.info(
            f"/balance: Balance sent successfully (balance=${balance:.2f}, pnl={total_pnl:+.2f})"
        )

    except Exception as e:
        logger.error(f"Error in /balance command: {e}", exc_info=True)

        # Send error message to user
        error_embed = discord.Embed(
            title="Error",
            description=(
                "An error occurred while fetching balance data. "
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
