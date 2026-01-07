# PolySpike Discord Bot - Manual Testing Checklist

This checklist covers manual verification of all bot features after integration tests pass.
Use this to verify the bot works correctly in a real Discord environment.

## Pre-flight Checks

Before running tests, verify the infrastructure is operational:

- [ ] **Mosquitto is running**
  ```bash
  systemctl status mosquitto
  ```

- [ ] **Bot is running**
  ```bash
  systemctl status polyspike-discord-bot
  ```

- [ ] **Bot is in the correct Discord channel**
  - Verify bot appears online in Discord server member list
  - Verify bot has access to the configured channel (`DISCORD_CHANNEL_ID`)

- [ ] **Bot has required permissions**
  - Send Messages
  - Embed Links
  - Use Application Commands (Slash Commands)
  - Read Message History

---

## Slash Command Tests

### `/status` Command

- [ ] **`/status` - Shows online status when trading bot is active**
  - Expected: Green embed with "Trading Bot Status: ONLINE"
  - Shows last heartbeat time
  - Shows connection quality (Excellent/Good/Fair)

- [ ] **`/status` - Shows offline status when trading bot is stopped**
  - Stop the trading bot, wait 90+ seconds
  - Expected: Orange embed with "Trading Bot Status: OFFLINE"
  - Shows "Last heartbeat: X minutes ago"

- [ ] **`/status` - Shows "No Data" when no heartbeat received**
  - Fresh bot start before any heartbeat
  - Expected: Gray embed with "Trading Bot Status: No Data"

### `/balance` Command

- [ ] **`/balance` - Shows balance information**
  - Expected: Embed with cash balance, equity, available balance
  - Shows unrealized P&L if positions are open
  - Shows total realized P&L
  - Color: Green (profit), Red (loss), Gray (neutral)

- [ ] **`/balance` - Shows "No Data" before any balance update**
  - Fresh bot start before balance message received
  - Expected: Gray embed with "Balance: No Data"

### `/stats` Command

- [ ] **`/stats` - Shows session statistics**
  - Expected: Embed with session ID, duration
  - Shows total trades, winning/losing trades, win rate
  - Shows P&L and P&L percentage
  - Shows max drawdown, avg win/loss

- [ ] **`/stats` - Shows "No Data" before any stats received**
  - Fresh bot start before session stats message
  - Expected: Gray embed with "Session Stats: No Data"

---

## MQTT Event Tests

Use `mosquitto_pub` to simulate trading bot events. Replace `polyspike/` with your `MQTT_TOPIC_PREFIX` if different.

### Bot Started Event

```bash
mosquitto_pub -h localhost -t "polyspike/status/started" -m '{
  "timestamp": '"$(date +%s)"',
  "session_id": "test-session-001",
  "config": {
    "initial_balance": 1000.00,
    "spike_threshold": 0.15,
    "position_size": 50.00,
    "monitored_markets": 25
  }
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Bot Started" (green color)
  - Shows session ID, initial balance, spike threshold, position size, monitored markets
  - Screenshot: `_screenshots/bot_started.png`

### Bot Stopped Event

```bash
mosquitto_pub -h localhost -t "polyspike/status/stopped" -m '{
  "timestamp": '"$(date +%s)"',
  "session_id": "test-session-001",
  "final_stats": {
    "total_pnl": 52.30,
    "total_trades": 15,
    "win_rate": 0.67
  }
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Bot Stopped" (orange/yellow color)
  - Shows session ID, final P&L, total trades, win rate
  - Screenshot: `_screenshots/bot_stopped.png`

### Bot Error Event

```bash
mosquitto_pub -h localhost -t "polyspike/status/error" -m '{
  "timestamp": '"$(date +%s)"',
  "error_type": "ConnectionError",
  "error_message": "Failed to connect to Polymarket API",
  "severity": "critical"
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Bot Error" (red color)
  - Shows error type, error message, severity
  - Screenshot: `_screenshots/bot_error.png`

### Position Opened Event

```bash
mosquitto_pub -h localhost -t "polyspike/trading/position_opened" -m '{
  "timestamp": '"$(date +%s)"',
  "token_id": "0x1234567890abcdef",
  "market_name": "Will BTC reach $100k by end of 2025?",
  "entry_price": 0.45,
  "position_size": 50.00,
  "reason": "spike_detected",
  "spike_magnitude": 0.18
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Position Opened" (blue color)
  - Shows market name, entry price, position size, reason
  - Screenshot: `_screenshots/position_opened.png`

### Trade Completed Event (Profit)

```bash
mosquitto_pub -h localhost -t "polyspike/trading/trade_completed" -m '{
  "timestamp": '"$(date +%s)"',
  "trade_id": "trade-test-001",
  "token_id": "0x1234567890abcdef",
  "market_name": "Will BTC reach $100k by end of 2025?",
  "entry_price": 0.45,
  "exit_price": 0.52,
  "size": 50.00,
  "pnl": 7.78,
  "pnl_pct": 0.1556,
  "duration_seconds": 3600,
  "reason": "take_profit"
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Trade Completed" (green color for profit)
  - Shows market name, entry/exit price, P&L, duration
  - Screenshot: `_screenshots/trade_completed_profit.png`

### Trade Completed Event (Loss)

```bash
mosquitto_pub -h localhost -t "polyspike/trading/trade_completed" -m '{
  "timestamp": '"$(date +%s)"',
  "trade_id": "trade-test-002",
  "token_id": "0xabcdef1234567890",
  "market_name": "Will ETH flip BTC in 2025?",
  "entry_price": 0.35,
  "exit_price": 0.28,
  "size": 50.00,
  "pnl": -10.00,
  "pnl_pct": -0.20,
  "duration_seconds": 7200,
  "reason": "stop_loss"
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Trade Completed" (red color for loss)
  - Shows market name, entry/exit price, negative P&L, duration
  - Screenshot: `_screenshots/trade_completed_loss.png`

### Balance Update Event

```bash
mosquitto_pub -h localhost -t "polyspike/balance/update" -m '{
  "timestamp": '"$(date +%s)"',
  "balance": 1052.30,
  "equity": 1067.50,
  "available_balance": 1002.30,
  "locked_in_positions": 50.00,
  "unrealized_pnl": 15.20,
  "total_pnl": 52.30,
  "update_reason": "trade_completed"
}'
```

- [ ] **Expected Discord embed:**
  - Title: "Balance Update" (color based on P&L)
  - Shows cash balance, equity, available, locked
  - Shows unrealized and total P&L
  - Screenshot: `_screenshots/balance_update.png`

### Heartbeat Event

```bash
mosquitto_pub -h localhost -t "polyspike/heartbeat" -m '{
  "timestamp": '"$(date +%s)"',
  "uptime_seconds": 3600,
  "balance": 1052.30,
  "open_positions": 1,
  "total_trades": 15
}'
```

- [ ] **Expected behavior:**
  - No Discord message (heartbeat updates internal state only)
  - `/status` command should show "ONLINE" after this

---

## Heartbeat Monitoring Tests

### Timeout Alert Test

1. [ ] **Ensure trading bot is sending heartbeats**
   - Run `/status` - should show "ONLINE"

2. [ ] **Stop the trading bot**
   ```bash
   systemctl stop polyspike-trading-bot  # or your trading bot service
   ```

3. [ ] **Wait 90+ seconds (heartbeat timeout)**
   - Default timeout is 90 seconds (3 missed heartbeats at 30s interval)

4. [ ] **Verify timeout alert appears in Discord**
   - Expected: Red/orange embed "Heartbeat Timeout Alert"
   - Shows "Last heartbeat: X seconds ago"
   - Screenshot: `_screenshots/heartbeat_timeout.png`

5. [ ] **Start trading bot again**
   ```bash
   systemctl start polyspike-trading-bot
   ```

6. [ ] **Verify `/status` shows online after heartbeat resumes**
   - Expected: Green embed "Trading Bot Status: ONLINE"

---

## Error Handling Tests

### Malformed JSON

```bash
mosquitto_pub -h localhost -t "polyspike/trading/position_opened" -m 'not valid json {'
```

- [ ] **Expected behavior:**
  - Bot logs error: "JSON decode error on topic..."
  - Bot does NOT crash
  - Bot continues processing other messages

### Missing Required Fields

```bash
mosquitto_pub -h localhost -t "polyspike/trading/trade_completed" -m '{
  "timestamp": '"$(date +%s)"'
}'
```

- [ ] **Expected behavior:**
  - Bot logs warning about missing fields
  - Notification sent with default/placeholder values
  - Bot does NOT crash

### Missing Timestamp (Critical Field)

```bash
mosquitto_pub -h localhost -t "polyspike/trading/position_opened" -m '{
  "market_name": "Test Market",
  "entry_price": 0.50
}'
```

- [ ] **Expected behavior:**
  - Bot logs warning: "MQTT payload missing critical field 'timestamp'"
  - Message is still processed (uses current time)

### MQTT Broker Disconnect/Reconnect

1. [ ] **Stop Mosquitto broker**
   ```bash
   sudo systemctl stop mosquitto
   ```

2. [ ] **Verify bot logs reconnection attempts**
   - Check bot logs for "Disconnected from MQTT broker unexpectedly"
   - Check for "Retry connection in X.Xs" messages

3. [ ] **Restart Mosquitto broker**
   ```bash
   sudo systemctl start mosquitto
   ```

4. [ ] **Verify bot reconnects automatically**
   - Check logs for "Reconnected to MQTT broker"
   - Send a test message and verify it's received

5. [ ] **If down for >5 minutes, verify Discord alert**
   - Expected: Alert about MQTT broker unreachable
   - Screenshot: `_screenshots/mqtt_disconnect_alert.png`

---

## Duplicate Message Prevention Test

### QoS 1 Duplicate Handling

```bash
# Send same trade_id twice
mosquitto_pub -h localhost -t "polyspike/trading/trade_completed" -m '{
  "timestamp": '"$(date +%s)"',
  "trade_id": "duplicate-test-001",
  "market_name": "Duplicate Test",
  "pnl": 5.00,
  "pnl_pct": 0.10
}'

# Send again with same trade_id
mosquitto_pub -h localhost -t "polyspike/trading/trade_completed" -m '{
  "timestamp": '"$(date +%s)"',
  "trade_id": "duplicate-test-001",
  "market_name": "Duplicate Test",
  "pnl": 5.00,
  "pnl_pct": 0.10
}'
```

- [ ] **Expected behavior:**
  - Only ONE Discord notification sent
  - Bot logs: "Ignoring duplicate trade_id: duplicate-test-001"

---

## Screenshot Placeholders

Create a `_screenshots/` directory in `docs/` and add screenshots after testing:

```
docs/_screenshots/
  bot_started.png
  bot_stopped.png
  bot_error.png
  position_opened.png
  trade_completed_profit.png
  trade_completed_loss.png
  balance_update.png
  heartbeat_timeout.png
  mqtt_disconnect_alert.png
```

---

## Test Completion Summary

| Category | Tests Passed | Tests Failed | Notes |
|----------|-------------|--------------|-------|
| Pre-flight Checks | /4 | | |
| Slash Commands | /6 | | |
| MQTT Events | /8 | | |
| Heartbeat Monitoring | /4 | | |
| Error Handling | /5 | | |
| Duplicate Prevention | /1 | | |
| **Total** | **/28** | | |

**Tested by:** ________________  
**Date:** ________________  
**Bot Version:** ________________
