"""Minecraft Server Monitoring Package."""

from .models import ServerEntry, ServerData, ServerStatus, MonitorConfig, APIConfig
from .monitor import ServerMonitor, MonitoringService, run_monitoring
from .rate_limiter import RateLimiter
from .logger import RotatingLogger, setup_structlog, get_logger
from .api_clients import (
    McstatusIOClient,
    MinecraftMPClient,
    fetch_servers_from_apis,
)

__version__ = "1.0.0"
__all__ = [
    "ServerEntry",
    "ServerData",
    "ServerStatus",
    "MonitorConfig",
    "APIConfig",
    "ServerMonitor",
    "MonitoringService",
    "run_monitoring",
    "RateLimiter",
    "RotatingLogger",
    "setup_structlog",
    "get_logger",
    "McstatusIOClient",
    "MinecraftMPClient",
    "fetch_servers_from_apis",
]
