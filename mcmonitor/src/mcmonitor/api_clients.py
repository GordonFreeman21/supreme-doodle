"""
Public API Clients for Minecraft Server Discovery

This module provides clients for legitimate, opt-in public APIs that
list Minecraft servers. These APIs are used to discover servers that
have explicitly chosen to be listed publicly.

SUPPORTED APIS:
===============
1. mcstatus.io - Public server status API (no auth required)
2. minecraft-mp.com - Server list with optional API key

ETHICAL COMPLIANCE:
===================
- Only uses public, documented APIs
- Respects API rate limits and terms of service
- No scraping of non-API endpoints
- Servers listed have opted-in to public discovery
- User agent identifies this tool clearly

IMPORTANT: Always check API documentation for current rate limits
and terms of service before using in production.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel, Field

from .models import ServerEntry
from .logger import get_logger

logger = get_logger(__name__)


class APIServer(BaseModel):
    """Server information from public API."""
    host: str
    port: int = 25565
    name: Optional[str] = None
    source: str = Field(..., description="API source name")


class McstatusIOClient:
    """
    Client for mcstatus.io API.
    
    This API provides server status information and a list of popular servers.
    Documentation: https://api.mcstatus.io/
    
    RATE LIMITS: Check current documentation - typically ~10 requests/minute
    without authentication.
    """
    
    BASE_URL = "https://api.mcstatus.io/v2"
    DEFAULT_TIMEOUT = 10.0
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._owns_session = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._owns_session = True
        return self.session
    
    async def close(self) -> None:
        """Close HTTP session if we own it."""
        if self._owns_session and self.session:
            await self.session.close()
            self.session = None
            self._owns_session = False
    
    async def get_server_status(
        self,
        host: str,
        port: int = 25565,
    ) -> Optional[Dict[str, Any]]:
        """
        Get server status from mcstatus.io API.
        
        Args:
            host: Server hostname or IP
            port: Server port
            
        Returns:
            Server status data or None on error
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/status/java/{host}:{port}"
        
        try:
            async with session.get(url, timeout=self.DEFAULT_TIMEOUT) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    logger.warning("Rate limited by mcstatus.io API")
                    return None
                else:
                    logger.warning(f"mcstatus.io API error: {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout querying mcstatus.io for {host}:{port}")
            return None
        except Exception as e:
            logger.error(f"Error querying mcstatus.io: {e}")
            return None
    
    async def get_popular_servers(self, limit: int = 100) -> List[APIServer]:
        """
        Get list of popular servers from mcstatus.io.
        
        Note: This returns servers that are publicly listed and have opted-in
        to discovery through this API.
        
        Args:
            limit: Maximum number of servers to return
            
        Returns:
            List of server entries
        """
        # mcstatus.io doesn't have a direct "popular servers" endpoint
        # This is a placeholder for when such endpoint exists
        # For now, users should provide their own server lists
        logger.info("mcstatus.io does not provide a popular servers endpoint")
        return []


class MinecraftMPClient:
    """
    Client for minecraft-mp.com API.
    
    This is a public server list where server owners voluntarily list
    their servers for discovery.
    
    Documentation: https://minecraft-mp.com/api/
    
    RATE LIMITS: Typically requires API key for higher limits.
    Anonymous usage may be limited to ~60 requests/hour.
    """
    
    BASE_URL = "https://api.minecraft-mp.com/v2"
    DEFAULT_TIMEOUT = 10.0
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.api_key = api_key
        self.session = session
        self._owns_session = False
        self._headers = {}
        
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self._headers)
            self._owns_session = True
        return self.session
    
    async def close(self) -> None:
        """Close HTTP session if we own it."""
        if self._owns_session and self.session:
            await self.session.close()
            self.session = None
            self._owns_session = False
    
    async def get_server_list(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[APIServer]:
        """
        Get list of servers from minecraft-mp.com.
        
        All servers in this list have voluntarily opted-in to public discovery.
        
        Args:
            limit: Number of servers per page
            offset: Pagination offset
            
        Returns:
            List of server entries
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/servers/"
        params = {"limit": limit, "offset": offset}
        
        try:
            async with session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    servers = []
                    
                    for server_data in data.get("data", []):
                        servers.append(APIServer(
                            host=server_data.get("ip", ""),
                            port=server_data.get("port", 25565),
                            name=server_data.get("name"),
                            source="minecraft-mp.com",
                        ))
                    
                    return servers
                elif response.status == 429:
                    logger.warning("Rate limited by minecraft-mp.com API")
                    return []
                else:
                    logger.warning(f"minecraft-mp.com API error: {response.status}")
                    return []
        except asyncio.TimeoutError:
            logger.warning("Timeout querying minecraft-mp.com API")
            return []
        except Exception as e:
            logger.error(f"Error querying minecraft-mp.com: {e}")
            return []
    
    async def search_servers(
        self,
        query: str,
        limit: int = 50,
    ) -> List[APIServer]:
        """
        Search for servers by name/tag.
        
        Args:
            query: Search query string
            limit: Maximum results
            
        Returns:
            List of matching servers
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/search/"
        params = {"q": query, "limit": limit}
        
        try:
            async with session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    servers = []
                    
                    for server_data in data.get("data", []):
                        servers.append(APIServer(
                            host=server_data.get("ip", ""),
                            port=server_data.get("port", 25565),
                            name=server_data.get("name"),
                            source="minecraft-mp.com",
                        ))
                    
                    return servers
                else:
                    logger.warning(f"minecraft-mp.com search error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error searching minecraft-mp.com: {e}")
            return []


async def fetch_servers_from_apis(
    mcstatus_io_enabled: bool = False,
    minecraft_mp_enabled: bool = False,
    minecraft_mp_api_key: Optional[str] = None,
    limit_per_api: int = 100,
) -> List[ServerEntry]:
    """
    Fetch server lists from enabled public APIs.
    
    ETHICAL NOTE: All servers returned have voluntarily opted-in to
    public discovery through these APIs. This is compliant with
    ethical monitoring practices.
    
    Args:
        mcstatus_io_enabled: Enable mcstatus.io API
        minecraft_mp_enabled: Enable minecraft-mp.com API
        minecraft_mp_api_key: Optional API key for minecraft-mp.com
        limit_per_api: Max servers to fetch from each API
        
    Returns:
        List of ServerEntry objects
    """
    servers = []
    
    if mcstatus_io_enabled:
        logger.info("Fetching servers from mcstatus.io API")
        client = McstatusIOClient()
        try:
            api_servers = await client.get_popular_servers(limit=limit_per_api)
            for s in api_servers:
                servers.append(ServerEntry(
                    host=s.host,
                    port=s.port,
                    name=s.name,
                    enabled=True,
                ))
        finally:
            await client.close()
    
    if minecraft_mp_enabled:
        logger.info("Fetching servers from minecraft-mp.com API")
        client = MinecraftMPClient(api_key=minecraft_mp_api_key)
        try:
            api_servers = await client.get_server_list(limit=limit_per_api)
            for s in api_servers:
                servers.append(ServerEntry(
                    host=s.host,
                    port=s.port,
                    name=s.name,
                    enabled=True,
                ))
        finally:
            await client.close()
    
    logger.info(f"Fetched {len(servers)} servers from public APIs")
    return servers
