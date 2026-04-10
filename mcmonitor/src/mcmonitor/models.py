"""
Ethical Minecraft Server Monitoring Tool

ARCHITECTURE OVERVIEW:
======================
This tool implements a continuous, background-running monitoring system for Minecraft servers.
It uses the official Minecraft Server List Ping protocol (RFC-compliant) to query server status.

KEY DESIGN PRINCIPLES:
1. ETHICAL COMPLIANCE: Only monitors servers from user-provided lists or public opt-in APIs
2. RATE LIMITING: Strict global rate limits (1 query/sec default) with per-server caps
3. RESILIENCE: Exponential backoff + jitter for failed queries
4. TRANSPARENCY: Structured logging with timestamps and full audit trail
5. PRIVACY: Only collects publicly exposed data (no auth bypass, no credential harvesting)

COMPONENTS:
- models.py: Pydantic models for configuration and data structures
- monitor.py: Core monitoring logic with async concurrency control
- rate_limiter.py: Token bucket rate limiter with global and per-server limits
- logger.py: Structured JSON/CSV logging with rotation
- api_clients.py: Public API clients (mcstatus.io, minecraft-mp.com)
- cli.py: Command-line interface with ethical safeguards

DEPLOYMENT OPTIONS:
- systemd service (Linux)
- Docker container
- Direct Python execution

See docs/ETHICS.md and docs/DEPLOYMENT.md for detailed guidance.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ServerStatus(str, Enum):
    """Server online status."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


class ServerEntry(BaseModel):
    """
    Represents a Minecraft server to monitor.
    
    ETHICAL SAFEGUARD: Servers must be explicitly provided by the user
    or obtained from public opt-in APIs. No IP scanning or unauthorized
    discovery is permitted.
    """
    host: str = Field(..., description="Server hostname or IP address")
    port: int = Field(default=25565, ge=1, le=65535, description="Server port")
    name: Optional[str] = Field(default=None, description="Friendly name for the server")
    enabled: bool = Field(default=True, description="Whether to monitor this server")
    
    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host format - must be hostname or valid IP."""
        import re
        # Allow hostnames and IPv4 addresses
        hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        # Allow IPv6 in brackets
        ipv6_pattern = r'^\[([0-9a-fA-F:]+)\]$'
        
        if not (re.match(hostname_pattern, v) or 
                re.match(ipv4_pattern, v) or 
                re.match(ipv6_pattern, v)):
            raise ValueError(f"Invalid host format: {v}")
        return v
    
    @property
    def address(self) -> str:
        """Return full address string."""
        return f"{self.host}:{self.port}"


class ServerData(BaseModel):
    """
    Data collected from a server ping response.
    
    PRIVACY COMPLIANCE: Only collects data voluntarily exposed by the server
    in its status response. Player names are only recorded if the server
    explicitly includes them in the ping response (many privacy-conscious
    servers omit this).
    """
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    server: ServerEntry
    status: ServerStatus
    online: bool = False
    players_online: int = 0
    players_max: Optional[int] = None
    player_names: Optional[list[str]] = Field(default=None, description="Only if server voluntarily provides")
    version: Optional[str] = None
    motd_raw: Optional[str] = None
    motd_clean: Optional[str] = None
    protocol_version: Optional[int] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "server_address": self.server.address,
            "server_name": self.server.name or self.server.address,
            "status": self.status.value,
            "online": self.online,
            "players_online": self.players_online,
            "players_max": self.players_max,
            "player_names": self.player_names,
            "version": self.version,
            "motd_raw": self.motd_raw,
            "motd_clean": self.motd_clean,
            "protocol_version": self.protocol_version,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
        }


class MonitorConfig(BaseModel):
    """
    Configuration for the monitoring system.
    
    RATE LIMITING STRATEGY:
    - Global limit: Max queries per second across all servers (default: 1)
    - Per-server limit: Max concurrent queries per server (default: 1)
    - Backoff: Exponential backoff with jitter for failures
    - Pause on 429: Automatic pause when rate limited
    
    ETHICAL SAFEGUARDS:
    - No IP range scanning
    - No port sweeping
    - No authentication bypass attempts
    - No credential harvesting
    - Compliance with Minecraft EULA
    - GDPR compliance for player data
    """
    # Rate limiting
    global_rate_limit: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Max queries per second globally"
    )
    per_server_concurrency: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Max concurrent queries per server"
    )
    
    # Polling configuration
    polling_interval: float = Field(
        default=60.0,
        ge=5.0,
        le=3600.0,
        description="Base polling interval in seconds"
    )
    
    # Backoff configuration
    max_retries: int = Field(default=3, ge=0, le=10)
    base_backoff: float = Field(default=1.0, ge=0.1)
    max_backoff: float = Field(default=300.0, ge=1.0)  # 5 minutes max
    jitter_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Timeout configuration
    connection_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    read_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    
    # Output configuration
    output_format: str = Field(default="json", pattern="^(json|csv|both)$")
    log_dir: str = Field(default="logs")
    data_dir: str = Field(default="data")
    rotate_logs: bool = Field(default=True)
    max_log_size_mb: int = Field(default=100, ge=10, le=1000)
    
    # Ethical compliance flags
    respect_robots_txt: bool = Field(
        default=True,
        description="Respect robots.txt for API endpoints"
    )
    user_agent: str = Field(
        default="MCMonitor/1.0 (Ethical Monitoring Tool - https://github.com/example/mcmonitor)",
        description="User agent string identifying this tool"
    )
    
    class Config:
        frozen = False  # Allow mutation for CLI overrides


class APIConfig(BaseModel):
    """Configuration for public API integrations."""
    # mcstatus.io API
    mcstatus_io_enabled: bool = Field(default=False)
    mcstatus_io_base_url: str = "https://api.mcstatus.io/v2"
    
    # minecraft-mp.com API
    minecraft_mp_enabled: bool = Field(default=False)
    minecraft_mp_base_url: str = "https://api.minecraft-mp.com/v2"
    minecraft_mp_api_key: Optional[str] = Field(default=None)
    
    class Config:
        frozen = False
