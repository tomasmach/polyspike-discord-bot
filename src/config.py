"""Configuration loader for the Discord bot."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    # Discord
    discord_bot_token: str
    discord_guild_id: int
    discord_channel_id: int

    # MQTT
    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_topic_prefix: str

    # Monitoring
    heartbeat_timeout_seconds: int
    heartbeat_check_interval: int

    # Logging
    log_level: str
    log_file_path: str | None = None  # Optional file logging path


def load_config() -> Config:
    """Load configuration from .env file.

    Returns:
        Config: Configuration object with all settings.

    Raises:
        ValueError: If required environment variables are missing.
    """
    # Load .env file
    load_dotenv()

    # Validate required Discord variables
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN is required in .env file")

    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not guild_id:
        raise ValueError("DISCORD_GUILD_ID is required in .env file")

    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not channel_id:
        raise ValueError("DISCORD_CHANNEL_ID is required in .env file")

    # Create config object with defaults
    config = Config(
        # Discord
        discord_bot_token=discord_token,
        discord_guild_id=int(guild_id),
        discord_channel_id=int(channel_id),

        # MQTT
        mqtt_broker_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
        mqtt_broker_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
        mqtt_topic_prefix=os.getenv("MQTT_TOPIC_PREFIX", "polyspike/"),

        # Monitoring
        heartbeat_timeout_seconds=int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "90")),
        heartbeat_check_interval=int(os.getenv("HEARTBEAT_CHECK_INTERVAL", "30")),

        # Logging
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file_path=os.getenv("LOG_FILE_PATH"),  # None if not set
    )

    return config
