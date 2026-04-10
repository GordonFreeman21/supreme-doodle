# MCMonitor - Ethical Minecraft Server Monitoring Tool

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A continuous, background-running Minecraft server monitoring tool that uses the official Minecraft Server List Ping protocol to query server status ethically and responsibly.

## ⚠️ Ethical Usage Notice

**This tool is designed for ethical monitoring only.** By using this tool, you agree to:

### ✅ Permitted Uses
- Monitor servers you own or have explicit permission to monitor
- Query servers from public opt-in APIs (mcstatus.io, minecraft-mp.com)
- Collect publicly exposed status information (online status, player count, MOTD, version)
- Record player names **only if** the server voluntarily provides them in its ping response

### ❌ Prohibited Uses
- **IP range scanning** or **port sweeping** to discover servers
- **Authentication bypass** attempts of any kind
- **Credential harvesting** or attempting to access non-public data
- **Excessive polling** that could impact server performance
- Violation of **Minecraft EULA** or individual server Terms of Service
- Scraping servers without owner consent

## Features

- 🎯 **Official Protocol**: Uses mcstatus library for RFC-compliant server pings
- 🛡️ **Rate Limiting**: Token bucket algorithm with configurable global and per-server limits
- 🔄 **Resilience**: Exponential backoff + jitter for failed queries
- 📊 **Structured Logging**: JSON/CSV output with automatic rotation
- 🔒 **Privacy Controls**: Optional exclusion of player names from logs
- 🌐 **API Integration**: Optional fetching from public opt-in server list APIs
- 🚀 **Async Performance**: Concurrent monitoring with proper concurrency control
- 🛑 **Graceful Shutdown**: Handles SIGINT/SIGTERM for clean termination

## Installation

### From Source

```bash
cd mcmonitor
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Create a Server List

Create a JSON file with servers to monitor:

```json
[
  {"host": "hypixel.net", "port": 25565, "name": "Hypixel Network"},
  {"host": "mineplex.com", "port": 25565, "name": "Mineplex"},
  {"host": "play.cubecraft.net", "port": 25565, "name": "CubeCraft"}
]
```

Or use a simple text format (one server per line):

```
hypixel.net
mineplex.com:25565
play.cubecraft.net
```

### 2. Run the Monitor

```bash
# Basic usage
mcmonitor run --servers servers.json

# With custom settings
mcmonitor run -s servers.json -i 120 -r 0.5 -f csv

# Privacy mode (no player names in logs)
mcmonitor run -s servers.txt --no-player-names

# Monitor specific servers from command line
mcmonitor run -S hypixel.net -S mineplex.com

# Fetch servers from public APIs
mcmonitor run --minecraft-mp --minecraft-mp-key YOUR_API_KEY
```

### 3. View Logs

Logs are saved to the `logs/` directory:
- `logs/monitor.jsonl` - JSON Lines format (machine-parseable)
- `logs/monitor.csv` - CSV format (spreadsheet-compatible)

## CLI Commands

### `run` - Start Monitoring

```bash
mcmonitor run [OPTIONS]

Options:
  -s, --servers PATH        Path to server list file (JSON or text)
  -S, --server TEXT         Individual server (can repeat)
  -i, --interval FLOAT      Polling interval in seconds (default: 60)
  -r, --rate-limit FLOAT    Max queries/second globally (default: 1.0)
  -f, --format TEXT         Output format: json, csv, both (default: json)
  -l, --log-dir PATH        Directory for log files (default: logs)
  --no-player-names         Exclude player names from logs
  --mcstatus-io             Fetch from mcstatus.io API
  --minecraft-mp            Fetch from minecraft-mp.com API
  --minecraft-mp-key TEXT   API key for minecraft-mp.com
  --notice / --no-notice    Show ethical notice (default: show)
```

### `test` - Test Single Server

```bash
mcmonitor test hypixel.net:25565
```

### `validate` - Validate Server List

```bash
mcmonitor validate servers.json
```

### `example` - Generate Example File

```bash
mcmonitor example
```

## Configuration

### Rate Limiting Strategy

The tool implements sophisticated rate limiting to prevent server overload:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `global_rate_limit` | 1.0 qps | Max queries per second across all servers |
| `per_server_concurrency` | 1 | Max concurrent queries per individual server |
| `polling_interval` | 60s | Time between monitoring cycles |
| `base_backoff` | 1.0s | Initial backoff time after failure |
| `max_backoff` | 300s | Maximum backoff time (5 minutes) |
| `jitter_factor` | 0.1 | Randomness added to backoff (prevents thundering herd) |

### Backoff Algorithm

When a query fails, the tool applies exponential backoff:

```
backoff = min(base_backoff × 2^retries + jitter, max_backoff)
```

Where `jitter` is a random value between 0 and `jitter_factor × exponential_backoff`.

## Output Format

### JSON Lines (`.jsonl`)

Each line is a complete JSON object:

```json
{"timestamp":"2024-01-15T10:30:00Z","server_address":"hypixel.net:25565","server_name":"Hypixel Network","status":"online","online":true,"players_online":45234,"players_max":200000,"player_names":["Player1","Player2"],"version":"Requires MC 1.8 / 1.20","motd_clean":"Hypixel Network","protocol_version":47,"latency_ms":23.5}
```

### CSV (`.csv`)

Standard CSV with headers:

```csv
timestamp,server_address,server_name,status,online,players_online,players_max,player_names,version,motd_clean,protocol_version,latency_ms,error_message
2024-01-15T10:30:00Z,hypixel.net:25565,Hypixel Network,online,true,45234,200000,Player1|Player2,Requires MC 1.8 / 1.20,Hypixel Network,47,23.5,
```

## Architecture

```
mcmonitor/
├── src/mcmonitor/
│   ├── __init__.py       # Package exports
│   ├── models.py         # Pydantic data models
│   ├── monitor.py        # Core monitoring logic
│   ├── rate_limiter.py   # Token bucket rate limiter
│   ├── logger.py         # Structured logging
│   ├── api_clients.py    # Public API clients
│   └── cli.py            # Command-line interface
├── config/               # Configuration files
├── logs/                 # Log output
├── data/                 # Persistent data
└── docs/                 # Documentation
```

### Component Overview

1. **models.py**: Pydantic models for configuration and data structures
2. **monitor.py**: Async monitoring with mcstatus integration
3. **rate_limiter.py**: Token bucket + semaphore-based rate limiting
4. **logger.py**: JSON/CSV writers with automatic rotation
5. **api_clients.py**: Clients for mcstatus.io and minecraft-mp.com APIs
6. **cli.py**: Typer-based CLI with ethical safeguards

## Deployment

### As a systemd Service (Linux)

1. Create service file `/etc/systemd/system/mcmonitor.service`:

```ini
[Unit]
Description=Minecraft Server Monitor
After=network.target

[Service]
Type=simple
User=mcmonitor
Group=mcmonitor
WorkingDirectory=/opt/mcmonitor
Environment="PATH=/opt/mcmonitor/venv/bin"
ExecStart=/opt/mcmonitor/venv/bin/mcmonitor run -s /opt/mcmonitor/servers.json -i 60
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/mcmonitor/logs /opt/mcmonitor/data

[Install]
WantedBy=multi-user.target
```

2. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcmonitor
sudo systemctl start mcmonitor
sudo systemctl status mcmonitor
```

### Docker Container

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 mcmonitor && \
    chown -R mcmonitor:mcmonitor /app

USER mcmonitor

# Default command
CMD ["mcmonitor", "run", "-s", "/app/config/servers.json"]
```

Build and run:

```bash
docker build -t mcmonitor .
docker run -d \
  --name mcmonitor \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  mcmonitor
```

### Docker Compose

```yaml
version: '3.8'

services:
  mcmonitor:
    build: .
    container_name: mcmonitor
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "pgrep", "-f", "mcmonitor"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Compliance & Ethics

### Minecraft EULA Compliance

This tool complies with the [Minecraft EULA](https://account.mojang.com/documents/minecraft_eula):

- **Section 2.E**: Does not modify game clients or servers
- **Section 3.A**: Only accesses publicly available information
- **Section 5**: No commercial use without separate agreement

### GDPR Considerations

Player names are considered personal data under GDPR. This tool:

- Only records player names if **voluntarily provided** by the server
- Provides `--no-player-names` flag for privacy-focused operation
- Does not store any additional personal information
- Logs can be configured to exclude player identifiers

### Best Practices

1. **Obtain Permission**: Always get server owner consent before monitoring
2. **Reasonable Polling**: Use intervals ≥60 seconds unless necessary
3. **Respect Rate Limits**: Honor API and server rate limits immediately
4. **Minimize Data**: Only collect what you actually need
5. **Secure Logs**: Protect log files with appropriate permissions
6. **Document Usage**: Keep records of why you're monitoring each server

## Troubleshooting

### Common Issues

**Connection Timeouts**
- Check firewall rules allow outbound connections to port 25565
- Verify server address is correct
- Increase timeout in configuration if needed

**Rate Limiting Errors**
- Reduce `--rate-limit` value
- Increase `--interval` between polling cycles
- Check if server has specific rate limit requirements

**No Player Names in Logs**
- Many servers don't provide player lists in ping responses (privacy feature)
- This is normal and expected behavior
- Use `--no-player-names` if you want to ensure no player data is logged

### Debug Mode

Enable verbose logging:

```bash
RUST_LOG=debug mcmonitor run -s servers.json
```

## API Reference

### Public APIs Supported

#### mcstatus.io
- **Base URL**: `https://api.mcstatus.io/v2`
- **Authentication**: None required
- **Rate Limit**: ~10 requests/minute (check current docs)
- **Usage**: `--mcstatus-io`

#### minecraft-mp.com
- **Base URL**: `https://api.minecraft-mp.com/v2`
- **Authentication**: Optional API key for higher limits
- **Rate Limit**: ~60 requests/hour (anonymous), higher with key
- **Usage**: `--minecraft-mp [--minecraft-mp-key KEY]`

## Contributing

Contributions welcome! Please read our contributing guidelines first.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is provided "as is" without warranty. Users are solely responsible for ensuring their use complies with all applicable laws, regulations, and terms of service. The authors are not liable for any misuse of this software.

---

**Remember**: Ethical monitoring respects server resources, privacy, and ownership rights. Always obtain permission before monitoring servers you don't own.
