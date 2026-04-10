"""
Core Minecraft Server Monitor

This module implements the main monitoring logic using the official
Minecraft Server List Ping protocol via mcstatus library.

MONITORING APPROACH:
====================
1. Uses mcstatus library for RFC-compliant server pings
2. Async concurrency with rate limiting
3. Exponential backoff for failed queries
4. Structured logging of all results

ETHICAL COMPLIANCE:
===================
- Only pings servers explicitly provided by user
- Respects server response (no forced data extraction)
- Rate limited to prevent server overload
- Player names only recorded if voluntarily provided
- No authentication bypass attempts
- No credential harvesting
- Complies with Minecraft EULA
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcstatus import JavaServer

from .models import ServerEntry, ServerData, ServerStatus, MonitorConfig
from .rate_limiter import RateLimiter
from .logger import RotatingLogger, get_logger

logger = get_logger(__name__)


class ServerMonitor:
    """
    Core server monitoring class.
    
    Handles individual server ping operations with proper error handling,
    timeout management, and data extraction.
    """
    
    def __init__(self, config: MonitorConfig):
        self.config = config
    
    async def ping_server(
        self,
        server: ServerEntry,
        rate_limiter: RateLimiter,
    ) -> ServerData:
        """
        Ping a single Minecraft server and collect status data.
        
        Args:
            server: Server entry to ping
            rate_limiter: Rate limiter instance
            
        Returns:
            ServerData with ping results
        """
        address = server.address
        start_time = datetime.now(timezone.utc)
        
        # Check if we should skip due to backoff
        if await rate_limiter.should_skip_due_to_backoff(address):
            backoff = await rate_limiter.get_backoff_delay(address)
            return ServerData(
                timestamp=start_time,
                server=server,
                status=ServerStatus.ERROR,
                online=False,
                error_message=f"Skipping due to backoff ({backoff:.1f}s remaining)",
            )
        
        # Acquire global rate limit token
        wait_time = await rate_limiter.acquire_global()
        if wait_time > 0:
            logger.debug(f"Waited {wait_time:.2f}s for global rate limit", server=address)
        
        # Acquire per-server semaphore
        semaphore = await rate_limiter.acquire_server(address)
        
        async with semaphore:
            try:
                # Create mcstatus server instance
                mc_server = JavaServer.lookup(f"{server.host}:{server.port}")
                
                # Perform ping with timeout
                latency_start = asyncio.get_event_loop().time()
                
                status = await asyncio.wait_for(
                    self._get_status(mc_server),
                    timeout=self.config.connection_timeout + self.config.read_timeout,
                )
                
                latency_end = asyncio.get_event_loop().time()
                latency_ms = (latency_end - latency_start) * 1000
                
                # Record success
                await rate_limiter.record_success(address)
                
                # Extract player names only if voluntarily provided
                player_names = None
                if hasattr(status, 'players') and status.players:
                    player_list = getattr(status.players, 'sample', None)
                    if player_list:
                        # Only collect names if server provides them
                        player_names = [
                            player.name for player in player_list
                            if hasattr(player, 'name')
                        ]
                
                # Build MOTD string
                motd_raw = None
                motd_clean = None
                if hasattr(status, 'motd') and status.motd:
                    motd_raw = str(status.motd)
                    # Try to get clean text if available
                    if hasattr(status.motd, 'to_plain'):
                        motd_clean = status.motd.to_plain()
                    else:
                        motd_clean = motd_raw
                
                # Extract version info
                version = None
                protocol_version = None
                if hasattr(status, 'version') and status.version:
                    version = status.version.name
                    protocol_version = status.version.protocol
                
                # Extract player counts
                players_online = 0
                players_max = None
                if hasattr(status, 'players') and status.players:
                    players_online = status.players.online
                    players_max = getattr(status.players, 'max', None)
                
                return ServerData(
                    timestamp=start_time,
                    server=server,
                    status=ServerStatus.ONLINE,
                    online=True,
                    players_online=players_online,
                    players_max=players_max,
                    player_names=player_names,
                    version=version,
                    motd_raw=motd_raw,
                    motd_clean=motd_clean,
                    protocol_version=protocol_version,
                    latency_ms=latency_ms,
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout pinging {address}", server=address)
                backoff = await rate_limiter.record_failure(address)
                return ServerData(
                    timestamp=start_time,
                    server=server,
                    status=ServerStatus.TIMEOUT,
                    online=False,
                    error_message=f"Connection timeout after {self.config.connection_timeout}s",
                )
                
            except Exception as e:
                # Handle connection errors and other exceptions
                error_msg = str(e).lower()
                if any(x in error_msg for x in ["connection", "refused", "timeout", "offline"]):
                    logger.warning(f"Connection error for {address}: {e}", server=address)
                    backoff = await rate_limiter.record_failure(address)
                    return ServerData(
                        timestamp=start_time,
                        server=server,
                        status=ServerStatus.OFFLINE,
                        online=False,
                        error_message=f"Connection error: {str(e)}",
                    )
                else:
                    logger.error(f"Unexpected error pinging {address}: {e}", server=address)
                    backoff = await rate_limiter.record_failure(address)
                    return ServerData(
                        timestamp=start_time,
                        server=server,
                        status=ServerStatus.ERROR,
                        online=False,
                        error_message=f"Unexpected error: {str(e)}",
                    )
    
    async def _get_status(self, server: JavaServer) -> Any:
        """
        Get server status using mcstatus.
        
        This is a wrapper to handle both sync and async mcstatus versions.
        """
        # mcstatus may have sync or async API depending on version
        # Try async first, fall back to sync
        try:
            if hasattr(server, 'async_status'):
                return await server.async_status()
            else:
                # Run sync in executor to avoid blocking
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, server.status)
        except AttributeError:
            # Fallback to sync
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, server.status)


class MonitoringService:
    """
    Main monitoring service that coordinates multiple server monitors.
    
    Features:
    - Continuous background monitoring
    - Configurable polling intervals
    - Concurrent server monitoring with rate limits
    - Structured logging to JSON/CSV
    - Graceful shutdown support
    """
    
    def __init__(
        self,
        servers: List[ServerEntry],
        config: MonitorConfig,
        log_path: Optional[str] = None,
    ):
        self.servers = [s for s in servers if s.enabled]
        self.config = config
        self.rate_limiter = RateLimiter(
            global_rate=config.global_rate_limit,
            per_server_concurrency=config.per_server_concurrency,
            base_backoff=config.base_backoff,
            max_backoff=config.max_backoff,
            jitter_factor=config.jitter_factor,
        )
        
        # Setup logger
        if log_path:
            from pathlib import Path
            self.logger = RotatingLogger(
                base_path=Path(log_path),
                max_size_mb=config.max_log_size_mb,
                output_format=config.output_format,
                include_player_names=True,  # Can be configured via CLI
            )
        else:
            self.logger = None
        
        self.monitor = ServerMonitor(config)
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start continuous monitoring loop."""
        self._running = True
        self._shutdown_event.clear()
        
        logger.info(
            f"Starting monitoring service with {len(self.servers)} servers",
            servers=len(self.servers),
            polling_interval=self.config.polling_interval,
        )
        
        while self._running:
            cycle_start = datetime.now(timezone.utc)
            logger.info(f"Starting monitoring cycle", cycle_start=cycle_start.isoformat())
            
            # Monitor all servers concurrently (respecting rate limits)
            tasks = [
                self._monitor_single_server(server)
                for server in self.servers
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            cycle_end = datetime.now(timezone.utc)
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            logger.info(
                f"Completed monitoring cycle",
                cycle_end=cycle_end.isoformat(),
                duration_seconds=cycle_duration,
            )
            
            # Wait until next polling interval
            sleep_time = max(0, self.config.polling_interval - cycle_duration)
            if sleep_time > 0:
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=sleep_time,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue to next cycle
            
            if not self._running:
                break
        
        logger.info("Monitoring service stopped")
    
    async def _monitor_single_server(self, server: ServerEntry) -> None:
        """Monitor a single server and log results."""
        try:
            result = await self.monitor.ping_server(server, self.rate_limiter)
            
            # Log result
            if self.logger:
                await self.logger.log(result)
            
            # Log summary
            if result.online:
                logger.info(
                    f"Server online: {result.players_online}/{result.players_max} players",
                    server=server.address,
                    status="online",
                    players=result.players_online,
                )
            else:
                logger.warning(
                    f"Server offline or error: {result.error_message}",
                    server=server.address,
                    status=result.status.value,
                )
                
        except Exception as e:
            logger.error(f"Error monitoring {server.address}: {e}", server=server.address)
    
    async def stop(self) -> None:
        """Stop monitoring gracefully."""
        logger.info("Stopping monitoring service...")
        self._running = False
        self._shutdown_event.set()
    
    def request_stop(self) -> None:
        """Request stop (non-async)."""
        self._running = False
        self._shutdown_event.set()


async def run_monitoring(
    servers: List[ServerEntry],
    config: MonitorConfig,
    log_path: Optional[str] = None,
    shutdown_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Run the monitoring service.
    
    Args:
        servers: List of servers to monitor
        config: Monitoring configuration
        log_path: Path for log files
        shutdown_event: Optional event to signal shutdown
    """
    service = MonitoringService(servers, config, log_path)
    
    # Handle shutdown signals
    if shutdown_event:
        async def wait_for_shutdown():
            await shutdown_event.wait()
            await service.stop()
        asyncio.create_task(wait_for_shutdown())
    
    await service.start()
