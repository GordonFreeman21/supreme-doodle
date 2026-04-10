"""
Structured Logging for Minecraft Server Monitoring

This module provides structured JSON and CSV logging with rotation support.
All logs include timestamps, server information, and compliance metadata.

LOGGING FEATURES:
=================
- JSON format for machine parsing
- CSV format for spreadsheet analysis
- Automatic log rotation to prevent disk exhaustion
- Timestamped entries with UTC timezone
- Audit trail for ethical compliance

PRIVACY COMPLIANCE:
===================
- Player names only logged if voluntarily provided by server
- No personal data storage beyond what's publicly exposed
- Logs can be configured to exclude player names entirely
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from structlog.typing import Processor


class JSONLogWriter:
    """Write logs to JSON Lines format (.jsonl)."""
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self._lock = asyncio.Lock()
    
    async def write(self, data: Dict[str, Any]) -> None:
        """Append a single log entry as JSON."""
        async with self._lock:
            with open(self.output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, default=str) + '\n')


class CSVLogWriter:
    """Write logs to CSV format."""
    
    FIELDNAMES = [
        "timestamp",
        "server_address",
        "server_name",
        "status",
        "online",
        "players_online",
        "players_max",
        "player_names",
        "version",
        "motd_clean",
        "protocol_version",
        "latency_ms",
        "error_message",
    ]
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def _ensure_header(self) -> None:
        """Write CSV header if file doesn't exist or is empty."""
        if not self.output_path.exists() or self.output_path.stat().st_size == 0:
            with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()
    
    async def write(self, data: Dict[str, Any]) -> None:
        """Append a single log entry as CSV row."""
        async with self._lock:
            await self._ensure_header()
            
            # Prepare row data
            row = {
                "timestamp": data.get("timestamp", ""),
                "server_address": data.get("server_address", ""),
                "server_name": data.get("server_name", ""),
                "status": data.get("status", ""),
                "online": str(data.get("online", False)),
                "players_online": str(data.get("players_online", 0)),
                "players_max": str(data.get("players_max", "")),
                "player_names": "|".join(data.get("player_names") or []) if data.get("player_names") else "",
                "version": data.get("version", ""),
                "motd_clean": data.get("motd_clean", ""),
                "protocol_version": str(data.get("protocol_version", "")),
                "latency_ms": str(data.get("latency_ms", "")),
                "error_message": data.get("error_message", ""),
            }
            
            with open(self.output_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writerow(row)


class RotatingLogger:
    """
    Logger with automatic rotation based on file size.
    
    When max size is reached, current log is archived with timestamp
    and a new log file is created.
    """
    
    def __init__(
        self,
        base_path: Path,
        max_size_mb: int = 100,
        output_format: str = "json",
        include_player_names: bool = True,
    ):
        self.base_path = base_path
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.output_format = output_format
        self.include_player_names = include_player_names
        
        self.json_writer: Optional[JSONLogWriter] = None
        self.csv_writer: Optional[CSVLogWriter] = None
        
        self._setup_writers()
    
    def _setup_writers(self) -> None:
        """Initialize writers based on output format."""
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.output_format in ("json", "both"):
            json_path = self.base_path.with_suffix('.jsonl')
            self.json_writer = JSONLogWriter(json_path)
        
        if self.output_format in ("csv", "both"):
            csv_path = self.base_path.with_suffix('.csv')
            self.csv_writer = CSVLogWriter(csv_path)
    
    def _should_rotate(self) -> bool:
        """Check if log files exceed max size."""
        for writer in [self.json_writer, self.csv_writer]:
            if writer and writer.output_path.exists():
                if writer.output_path.stat().st_size >= self.max_size_bytes:
                    return True
        return False
    
    def _rotate(self) -> None:
        """Rotate log files by renaming with timestamp."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        for writer in [self.json_writer, self.csv_writer]:
            if writer and writer.output_path.exists():
                archive_name = f"{writer.output_path.stem}_{timestamp}{writer.output_path.suffix}"
                archive_path = writer.output_path.parent / archive_name
                writer.output_path.rename(archive_path)
        
        # Re-setup writers to create new files
        self._setup_writers()
    
    async def log(self, server_data: Any) -> None:
        """
        Log server data to configured outputs.
        
        Args:
            server_data: ServerData object or dict with monitoring results
        """
        # Check rotation
        if self._should_rotate():
            self._rotate()
        
        # Convert to dict if needed
        if hasattr(server_data, 'to_dict'):
            data = server_data.to_dict()
        else:
            data = dict(server_data)
        
        # Privacy filter: remove player names if configured
        if not self.include_player_names:
            data["player_names"] = None
        
        # Write to configured formats
        tasks = []
        if self.json_writer:
            tasks.append(self.json_writer.write(data))
        if self.csv_writer:
            tasks.append(self.csv_writer.write(data))
        
        if tasks:
            await asyncio.gather(*tasks)


def setup_structlog(log_level: str = "INFO") -> None:
    """
    Configure structlog for application-wide structured logging.
    
    This provides consistent, parseable log output for the entire application.
    """
    
    def add_timestamp(
        logger: Any,
        method_name: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        """Add UTC timestamp to all log entries."""
        event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
        return event_dict
    
    structlog.configure(
        processors=[
            add_timestamp,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """Get a structured logger instance."""
    return structlog.get_logger(name)
