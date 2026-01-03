"""Discord bot for PolySpike Hunter integration.

This module contains the main Discord bot class that handles:
- Discord client initialization and event handling
- MQTT client integration
- Heartbeat monitoring
- Slash command registration
"""

import asyncio
import signal
from typing import Optional

import discord
from discord import app_commands

from src.config import Config
from src.handlers.heartbeat_monitor import HeartbeatMonitor
from src.utils.logger import get_logger


class PolySpikeBot(discord.Client):
    """Discord bot client for PolySpike Hunter notifications.

    Integrates with MQTT broker to receive trading bot events and
    sends notifications to Discord channel. Monitors trading bot
    health via heartbeat messages.

    Attributes:
        config: Bot configuration loaded from environment.
        tree: Discord slash command tree for app commands.
        heartbeat_monitor: Monitor for trading bot heartbeat.
        mqtt_client: MQTT client for receiving events (set in main.py).
        notification_channel: Discord channel for bot notifications.
    """

    def __init__(
        self,
        config: Config,
        *,
        intents: discord.Intents,
    ):
        """Initialize Discord bot.

        Args:
            config: Bot configuration object.
            intents: Discord intents defining bot permissions.
        """
        super().__init__(intents=intents)

        self.config = config
        self.logger = get_logger()

        # Slash command tree
        self.tree = app_commands.CommandTree(self)

        # Components (initialized in on_ready)
        self.heartbeat_monitor: Optional[HeartbeatMonitor] = None
        self.mqtt_client = None  # Will be set by main.py

        # Discord channel cache
        self.notification_channel: Optional[discord.TextChannel] = None

        # Shutdown flag
        self._shutdown_requested = False

        self.logger.info("PolySpikeBot initialized")

    async def setup_hook(self) -> None:
        """Set up bot before connecting to Discord.

        This hook is called once when the bot is starting up.
        Used for:
        - Registering slash commands
        - Syncing command tree with Discord
        """
        self.logger.info("Running setup hook")

        # Register slash commands
        # TODO: Import and register commands in Phase 6
        # from src.commands import status, balance, stats
        # self.tree.add_command(status.status_command)
        # self.tree.add_command(balance.balance_command)
        # self.tree.add_command(stats.stats_command)

        # Sync commands with Discord guild
        guild = discord.Object(id=self.config.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        self.logger.info("Slash commands synced with Discord guild")

    async def on_ready(self) -> None:
        """Called when bot successfully connects to Discord.

        Initializes:
        - Notification channel reference
        - Heartbeat monitor
        - MQTT client (if not already connected)

        This event can fire multiple times during bot lifetime
        (on reconnection), so initialization is idempotent.
        """
        self.logger.info(f"Discord bot connected as {self.user} (ID: {self.user.id})")

        # Get and validate notification channel
        channel = self.get_channel(self.config.discord_channel_id)

        if channel is None:
            self.logger.error(
                f"Notification channel {self.config.discord_channel_id} not found! "
                "Please verify DISCORD_CHANNEL_ID in .env and bot has access to the channel."
            )
        elif not isinstance(channel, discord.TextChannel):
            self.logger.error(
                f"Channel {self.config.discord_channel_id} is not a text channel "
                f"(got {type(channel).__name__}). Please use a text channel ID."
            )
        else:
            self.notification_channel = channel
            self.logger.info(
                f"Notification channel set: #{channel.name} (ID: {channel.id})"
            )

        # Initialize heartbeat monitor (only once)
        if self.heartbeat_monitor is None:
            self.heartbeat_monitor = HeartbeatMonitor(
                bot=self,
                timeout_seconds=self.config.heartbeat_timeout_seconds,
            )
            await self.heartbeat_monitor.start_monitoring()
            self.logger.info(
                f"Heartbeat monitor started (timeout: {self.config.heartbeat_timeout_seconds}s)"
            )

        # MQTT client will be connected by main.py after on_ready
        # We don't connect here to avoid race conditions

        self.logger.info("Bot is ready and waiting for MQTT events")

    async def on_disconnect(self) -> None:
        """Called when bot disconnects from Discord.

        Logs disconnection for monitoring purposes.
        """
        self.logger.warning("Discord bot disconnected")

    async def on_resumed(self) -> None:
        """Called when bot resumes connection after disconnect.

        Logs reconnection for monitoring purposes.
        """
        self.logger.info("Discord bot connection resumed")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Global error handler for Discord events.

        Args:
            event: Name of event that raised error.
            *args: Event arguments.
            **kwargs: Event keyword arguments.
        """
        self.logger.error(
            f"Discord event error in {event}",
            exc_info=True,
        )

    async def shutdown(self) -> None:
        """Gracefully shutdown bot and all components.

        Stops:
        - Heartbeat monitor
        - MQTT client
        - Discord connection

        Should be called before application exit.
        """
        if self._shutdown_requested:
            self.logger.info("Shutdown already in progress")
            return

        self._shutdown_requested = True
        self.logger.info("Initiating graceful shutdown...")

        # Stop heartbeat monitor
        if self.heartbeat_monitor is not None:
            await self.heartbeat_monitor.stop_monitoring()
            self.logger.info("Heartbeat monitor stopped")

        # Disconnect MQTT client (handled by main.py)
        if self.mqtt_client is not None:
            self.mqtt_client.disconnect()
            self.logger.info("MQTT client disconnected")

        # Close Discord connection
        await self.close()
        self.logger.info("Discord connection closed")

        self.logger.info("Shutdown complete")


def create_discord_bot(config: Config) -> PolySpikeBot:
    """Factory function to create Discord bot with proper intents.

    Args:
        config: Bot configuration.

    Returns:
        Configured PolySpikeBot instance ready to connect.
    """
    # Configure Discord intents
    # We need:
    # - guilds: Access to guild/channel information
    # - message_content: Not needed (we don't read messages)
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = False  # We only send messages, don't read them

    bot = PolySpikeBot(config=config, intents=intents)

    return bot


async def setup_signal_handlers(bot: PolySpikeBot) -> None:
    """Set up signal handlers for graceful shutdown.

    Handles:
    - SIGINT (Ctrl+C)
    - SIGTERM (kill command)

    Args:
        bot: Discord bot instance to shutdown on signal.
    """
    logger = get_logger()

    def signal_handler(sig: int) -> None:
        """Handle shutdown signals."""
        signal_name = signal.Signals(sig).name
        logger.info(f"Received {signal_name}, initiating shutdown...")
        asyncio.create_task(bot.shutdown())

    # Register signal handlers
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: signal_handler(s)
        )

    logger.info("Signal handlers registered (SIGINT, SIGTERM)")
