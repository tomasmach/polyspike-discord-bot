# Deployment Checklist

Complete this checklist before deploying the PolySpike Discord Bot to production.

---

## Before Deployment

### Discord Setup
- [ ] Discord bot created at [Discord Developer Portal](https://discord.com/developers/applications)
- [ ] Bot token obtained and securely stored
- [ ] Bot invited to your Discord server with required permissions
- [ ] Guild ID collected (Server Settings > Widget > Server ID)
- [ ] Channel ID collected (Right-click channel > Copy ID)

### Environment Configuration
- [ ] `.env` file created from `.env.example`
- [ ] `DISCORD_BOT_TOKEN` configured
- [ ] `DISCORD_GUILD_ID` configured
- [ ] `DISCORD_CHANNEL_ID` configured
- [ ] `MQTT_BROKER_HOST` configured (default: localhost)
- [ ] `MQTT_BROKER_PORT` configured (default: 1883)

### Dependencies
- [ ] Mosquitto MQTT broker installed and running
- [ ] Mosquitto tested with `mosquitto_pub` and `mosquitto_sub`
- [ ] PolySpike Hunter bot is configured and ready

---

## Installation

### Repository Setup
- [ ] Repository cloned to `/home/pi/polyspike-discord-bot`
  ```bash
  git clone <repository-url> /home/pi/polyspike-discord-bot
  cd /home/pi/polyspike-discord-bot
  ```

### Python Environment
- [ ] Virtual environment created
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- [ ] Dependencies installed
  ```bash
  pip install -r requirements.txt
  ```

### Systemd Service
- [ ] Service file copied to systemd
  ```bash
  sudo cp polyspike-discord-bot.service /etc/systemd/system/
  ```
- [ ] Systemd daemon reloaded
  ```bash
  sudo systemctl daemon-reload
  ```
- [ ] Service enabled for auto-start
  ```bash
  sudo systemctl enable polyspike-discord-bot
  ```

---

## Verification

### Pre-Start Tests
- [ ] Run integration tests
  ```bash
  source venv/bin/activate
  python scripts/test_integration.py
  ```
- [ ] All tests pass without errors

### Service Start
- [ ] Start the service
  ```bash
  sudo systemctl start polyspike-discord-bot
  ```
- [ ] Check service status
  ```bash
  sudo systemctl status polyspike-discord-bot
  ```
- [ ] Service shows "active (running)"

### Discord Verification
- [ ] Bot appears online in Discord server
- [ ] Test `/status` command in Discord
- [ ] Status response shows correct information
- [ ] Verify heartbeat monitoring works (wait for heartbeat interval)

---

## Post-Deployment

### Initial Monitoring
- [ ] Monitor logs for first hour
  ```bash
  journalctl -u polyspike-discord-bot -f
  ```
- [ ] No errors or warnings in logs
- [ ] Verify trading bot events appear in Discord channel
- [ ] Confirm MQTT messages are being received

### Reliability Testing
- [ ] Test system restart
  ```bash
  sudo reboot
  ```
- [ ] After reboot, verify Mosquitto auto-started
  ```bash
  sudo systemctl status mosquitto
  ```
- [ ] Verify Discord bot auto-started
  ```bash
  sudo systemctl status polyspike-discord-bot
  ```
- [ ] Both services should be "active (running)"

---

## Maintenance

### Updating the Bot

1. Stop the service:
   ```bash
   sudo systemctl stop polyspike-discord-bot
   ```

2. Pull latest changes:
   ```bash
   cd /home/pi/polyspike-discord-bot
   git pull origin main
   ```

3. Update dependencies (if needed):
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Restart the service:
   ```bash
   sudo systemctl start polyspike-discord-bot
   ```

### Checking Logs

View recent logs:
```bash
journalctl -u polyspike-discord-bot -n 100
```

Follow logs in real-time:
```bash
journalctl -u polyspike-discord-bot -f
```

View logs since last boot:
```bash
journalctl -u polyspike-discord-bot -b
```

Filter logs by time:
```bash
journalctl -u polyspike-discord-bot --since "1 hour ago"
journalctl -u polyspike-discord-bot --since "2024-01-01" --until "2024-01-02"
```

### Restarting Services

Restart Discord bot:
```bash
sudo systemctl restart polyspike-discord-bot
```

Restart Mosquitto:
```bash
sudo systemctl restart mosquitto
```

Restart both services:
```bash
sudo systemctl restart mosquitto polyspike-discord-bot
```

### Troubleshooting

**Bot not connecting to Discord:**
- Check token in `.env` file
- Verify internet connectivity
- Check Discord API status

**MQTT messages not received:**
- Verify Mosquitto is running: `sudo systemctl status mosquitto`
- Test MQTT manually: `mosquitto_sub -t "polyspike/#" -v`
- Check broker host/port in `.env`

**Service fails to start:**
- Check logs: `journalctl -u polyspike-discord-bot -n 50`
- Verify Python path in service file
- Check file permissions

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start bot | `sudo systemctl start polyspike-discord-bot` |
| Stop bot | `sudo systemctl stop polyspike-discord-bot` |
| Restart bot | `sudo systemctl restart polyspike-discord-bot` |
| Check status | `sudo systemctl status polyspike-discord-bot` |
| View logs | `journalctl -u polyspike-discord-bot -f` |
| Enable auto-start | `sudo systemctl enable polyspike-discord-bot` |
| Disable auto-start | `sudo systemctl disable polyspike-discord-bot` |
