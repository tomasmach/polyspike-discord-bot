# PolySpike Discord Bot

A Discord bot that monitors the PolySpike Hunter trading bot via MQTT and provides real-time notifications for trades, balance changes, and bot status.

## Features

- **Real-time Trade Notifications** - Instant Discord alerts when positions are opened or trades complete
- **Balance Monitoring** - Track account balance and P&L changes
- **Heartbeat Monitoring** - Detect when the trading bot goes offline
- **Slash Commands** - Interactive commands for on-demand status checks
  - `/status` - Check if trading bot is online/offline
  - `/balance` - View current balance and P&L
  - `/stats` - View session trading statistics

## Architecture

```
+------------------+       +----------------+       +------------------+       +---------+
|                  |       |                |       |                  |       |         |
| PolySpike Hunter | ----> | MQTT Broker    | ----> | Discord Bot      | ----> | Discord |
| (Trading Bot)    |       | (Mosquitto)    |       | (This Project)   |       | Server  |
|                  |       |                |       |                  |       |         |
+------------------+       +----------------+       +------------------+       +---------+
     Publishes:                 Routes:                 Subscribes:              Receives:
     - Trade events             - polyspike/#           - polyspike/#            - Embeds
     - Balance updates                                  - Handles events         - Notifications
     - Heartbeats                                       - Slash commands         - Commands
     - Status changes
```

## Prerequisites

- **Python 3.11+** - Required for modern async features
- **Mosquitto MQTT Broker** - Must be installed and running on the Pi
- **Discord Bot Token** - From Discord Developer Portal
- **Discord Server** - With a channel for bot notifications

### Verify Mosquitto is Running

```bash
sudo systemctl status mosquitto
```

If not running:
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

## Discord Bot Setup

### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application**
3. Enter a name (e.g., "PolySpike Monitor") and click **Create**

### Step 2: Create Bot User

1. In your application, go to the **Bot** section in the left sidebar
2. Click **Add Bot** and confirm
3. Under **Token**, click **Reset Token** and copy the token
4. Save this token securely - you will need it for `DISCORD_BOT_TOKEN`

**Important Bot Settings:**
- Disable **Public Bot** if you want to restrict who can add the bot
- Enable **Message Content Intent** if needed for future features

### Step 3: Configure Bot Permissions

The bot requires these permissions:
- **Send Messages** - To post trade notifications
- **Embed Links** - To send rich embed messages
- **Use Slash Commands** - For `/status`, `/balance`, `/stats` commands

### Step 4: Generate Invite URL

1. Go to **OAuth2** > **URL Generator**
2. Under **Scopes**, select:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions**, select:
   - Send Messages
   - Embed Links
   - Use Application Commands
4. Copy the generated URL and open it in your browser
5. Select your Discord server and authorize the bot

### Step 5: Get Guild ID and Channel ID

1. In Discord, go to **User Settings** > **Advanced**
2. Enable **Developer Mode**
3. Right-click your server name and select **Copy Server ID** - this is your `DISCORD_GUILD_ID`
4. Right-click the channel for notifications and select **Copy Channel ID** - this is your `DISCORD_CHANNEL_ID`

## Installation

### Clone Repository

```bash
cd /home/pi
git clone https://github.com/your-org/polyspike-discord-bot.git
cd polyspike-discord-bot
```

### Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

```bash
cp .env.example .env
nano .env
```

## Configuration

Edit the `.env` file with your settings:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | - | Bot token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | Yes | - | Your Discord server ID |
| `DISCORD_CHANNEL_ID` | Yes | - | Channel ID for trade notifications |
| `MQTT_BROKER_HOST` | No | `localhost` | MQTT broker hostname or IP |
| `MQTT_BROKER_PORT` | No | `1883` | MQTT broker port |
| `MQTT_TOPIC_PREFIX` | No | `polyspike/` | Topic prefix for MQTT subscriptions |
| `HEARTBEAT_TIMEOUT_SECONDS` | No | `90` | Seconds before bot is considered offline |
| `HEARTBEAT_CHECK_INTERVAL` | No | `30` | Interval between heartbeat checks |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Example .env

```env
# Discord Configuration
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXX
DISCORD_GUILD_ID=123456789012345678
DISCORD_CHANNEL_ID=123456789012345678

# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_TOPIC_PREFIX=polyspike/

# Monitoring
HEARTBEAT_TIMEOUT_SECONDS=90
HEARTBEAT_CHECK_INTERVAL=30

# Logging
LOG_LEVEL=INFO
```

## Running the Bot

### Manual Run (Testing)

```bash
cd /home/pi/polyspike-discord-bot
source venv/bin/activate
python -m src.main
```

Press `Ctrl+C` to stop.

### Systemd Service (Production)

#### Install the Service

```bash
sudo cp polyspike-discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable polyspike-discord-bot
sudo systemctl start polyspike-discord-bot
```

#### Useful Commands

```bash
# Check service status
sudo systemctl status polyspike-discord-bot

# View logs (live)
sudo journalctl -u polyspike-discord-bot -f

# View last 100 log lines
sudo journalctl -u polyspike-discord-bot -n 100

# Restart the bot
sudo systemctl restart polyspike-discord-bot

# Stop the bot
sudo systemctl stop polyspike-discord-bot
```

## Testing the Setup

### Verify MQTT Connection

Check if the bot is receiving MQTT messages:

```bash
# In one terminal, watch the bot logs
sudo journalctl -u polyspike-discord-bot -f

# In another terminal, publish a test heartbeat
mosquitto_pub -t "polyspike/status/bot/heartbeat" -m '{"timestamp": 1234567890}'
```

### Test Discord Commands

In your Discord server, try these commands:
- `/status` - Should show "No Data" or current status
- `/balance` - Should show "No Data" or cached balance
- `/stats` - Should show "No Data" or session statistics

### Simulate Trading Events

Use these commands to test notifications:

```bash
# Simulate bot started
mosquitto_pub -t "polyspike/status/bot/started" -m '{
  "timestamp": 1234567890,
  "version": "1.0.0",
  "initial_balance": 1000.00
}'

# Simulate position opened
mosquitto_pub -t "polyspike/trading/position/opened" -m '{
  "timestamp": 1234567890,
  "symbol": "BTC/USD",
  "side": "long",
  "entry_price": 50000.00,
  "size": 0.01,
  "stop_loss": 49000.00,
  "take_profit": 52000.00
}'

# Simulate trade completed
mosquitto_pub -t "polyspike/trading/trade/completed" -m '{
  "timestamp": 1234567890,
  "symbol": "BTC/USD",
  "side": "long",
  "entry_price": 50000.00,
  "exit_price": 51000.00,
  "pnl": 10.00,
  "pnl_pct": 0.02,
  "duration_seconds": 3600
}'

# Simulate balance update
mosquitto_pub -t "polyspike/balance/update" -m '{
  "timestamp": 1234567890,
  "balance": 1010.00,
  "equity": 1010.00,
  "available_balance": 1010.00,
  "locked_in_positions": 0.00,
  "unrealized_pnl": 0.00,
  "total_pnl": 10.00,
  "update_reason": "trade_closed"
}'

# Simulate heartbeat
mosquitto_pub -t "polyspike/status/bot/heartbeat" -m '{
  "timestamp": 1234567890,
  "uptime_seconds": 3600
}'
```

## Troubleshooting

### Bot Not Starting

**Check logs for errors:**
```bash
sudo journalctl -u polyspike-discord-bot -n 50
```

**Common issues:**
- Missing `.env` file or required variables
- Invalid Discord bot token
- Python virtual environment not activated in service file

### Bot Not Receiving MQTT Messages

**Verify Mosquitto is running:**
```bash
sudo systemctl status mosquitto
```

**Test MQTT connectivity:**
```bash
# Subscribe to all polyspike topics
mosquitto_sub -v -t "polyspike/#"

# In another terminal, publish a test message
mosquitto_pub -t "polyspike/test" -m "hello"
```

**Check firewall:**
```bash
sudo ufw status
# If active, ensure port 1883 is allowed for localhost
```

### Discord Commands Not Appearing

**Slash commands can take up to 1 hour to sync globally.** For faster testing:
- Commands sync immediately to the configured guild
- Ensure `DISCORD_GUILD_ID` is set correctly
- Restart the bot after changing guild ID

### Bot Shows "No Data" for Status/Balance

This is normal if:
- The trading bot (PolySpike Hunter) is not running
- The trading bot hasn't sent any messages yet
- MQTT topics don't match (check `MQTT_TOPIC_PREFIX`)

### Log File Locations

| Log Type | Location |
|----------|----------|
| Systemd journal | `sudo journalctl -u polyspike-discord-bot` |
| Python output | Included in systemd journal |

### Service Won't Start After Reboot

```bash
# Check if service is enabled
sudo systemctl is-enabled polyspike-discord-bot

# Enable if needed
sudo systemctl enable polyspike-discord-bot

# Check if mosquitto starts first
sudo systemctl status mosquitto
```

## MQTT Topics Reference

The bot subscribes to these topics:

| Topic | Description |
|-------|-------------|
| `polyspike/status/bot/started` | Trading bot startup notification |
| `polyspike/status/bot/stopped` | Trading bot shutdown notification |
| `polyspike/status/bot/error` | Trading bot error events |
| `polyspike/status/bot/heartbeat` | Periodic heartbeat (every 30s) |
| `polyspike/trading/position/opened` | New position opened |
| `polyspike/trading/trade/completed` | Trade closed with P&L |
| `polyspike/balance/update` | Balance change notification |
| `polyspike/stats/session` | Session statistics summary |

## License

MIT License - See [LICENSE](LICENSE) file for details.
