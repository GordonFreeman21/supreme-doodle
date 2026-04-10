"""
Command-Line Interface for Minecraft Server Monitor

This module provides the CLI entry point with comprehensive options
for configuring and running the monitoring service.

ETHICAL SAFEGUARDS IN CLI:
==========================
- Explicit warnings about ethical usage
- Required acknowledgment of compliance
- Clear documentation of permitted use cases
- No hidden or default scanning capabilities
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import ServerEntry, MonitorConfig, APIConfig
from .monitor import MonitoringService
from .api_clients import fetch_servers_from_apis
from .logger import setup_structlog, get_logger

# Initialize Rich console
console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="mcmonitor",
    help="Ethical Minecraft Server Monitoring Tool",
    add_completion=False,
)


def print_ethical_notice() -> None:
    """Display ethical usage notice."""
    notice = Panel.fit(
        """[bold yellow]ETHICAL USAGE NOTICE[/bold yellow]

This tool is designed for [green]ethical monitoring[/green] of Minecraft servers only.

✅ [green]Permitted:[/green]
  • Monitor servers you own or have permission to monitor
  • Query servers from public opt-in APIs
  • Collect publicly exposed status information

❌ [red]Prohibited:[/green]
  • IP range scanning or port sweeping
  • Authentication bypass attempts
  • Credential harvesting
  • Excessive polling that could impact server performance
  • Violation of Minecraft EULA or server ToS

By using this tool, you acknowledge responsibility for compliance
with applicable laws, regulations, and server terms of service.
""",
        title="⚠️  Compliance Notice",
        border_style="yellow",
    )
    console.print(notice)


def load_servers_from_file(file_path: Path) -> List[ServerEntry]:
    """Load server list from JSON or text file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Server list file not found: {file_path}")
    
    servers = []
    content = file_path.read_text().strip()
    
    # Try JSON format first
    if content.startswith('['):
        try:
            data = json.loads(content)
            for item in data:
                if isinstance(item, dict):
                    servers.append(ServerEntry(**item))
                elif isinstance(item, str):
                    # Simple string format: "host:port" or "host"
                    if ':' in item:
                        host, port = item.rsplit(':', 1)
                        servers.append(ServerEntry(host=host, port=int(port)))
                    else:
                        servers.append(ServerEntry(host=item))
            return servers
        except json.JSONDecodeError:
            pass
    
    # Fall back to line-by-line text format
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):  # Skip comments
            if ':' in line:
                parts = line.rsplit(':', 1)
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    port = 25565
            else:
                host = line
                port = 25565
            
            servers.append(ServerEntry(host=host, port=port))
    
    return servers


@app.command()
def run(
    server_list: Optional[Path] = typer.Option(
        None,
        "--servers", "-s",
        help="Path to server list file (JSON or text format)",
    ),
    server: Optional[List[str]] = typer.Option(
        None,
        "--server", "-S",
        help="Individual server to monitor (can be specified multiple times)",
    ),
    polling_interval: float = typer.Option(
        60.0,
        "--interval", "-i",
        min=5.0,
        max=3600.0,
        help="Polling interval in seconds (default: 60)",
    ),
    global_rate_limit: float = typer.Option(
        1.0,
        "--rate-limit", "-r",
        min=0.1,
        max=10.0,
        help="Max queries per second globally (default: 1.0)",
    ),
    output_format: str = typer.Option(
        "json",
        "--format", "-f",
        case_sensitive=False,
        help="Output format: json, csv, or both",
    ),
    log_dir: Path = typer.Option(
        Path("logs"),
        "--log-dir", "-l",
        help="Directory for log files",
    ),
    no_player_names: bool = typer.Option(
        False,
        "--no-player-names",
        help="Exclude player names from logs (privacy mode)",
    ),
    mcstatus_io: bool = typer.Option(
        False,
        "--mcstatus-io",
        help="Fetch servers from mcstatus.io API",
    ),
    minecraft_mp: bool = typer.Option(
        False,
        "--minecraft-mp",
        help="Fetch servers from minecraft-mp.com API",
    ),
    minecraft_mp_key: Optional[str] = typer.Option(
        None,
        "--minecraft-mp-key",
        help="API key for minecraft-mp.com",
    ),
    show_notice: bool = typer.Option(
        True,
        "--notice/--no-notice",
        help="Show ethical usage notice",
    ),
) -> None:
    """
    Run the Minecraft server monitoring service.
    
    Examples:
    
    # Monitor servers from a file:
    mcmonitor run --servers servers.json
    
    # Monitor specific servers:
    mcmonitor run -S hypixel.net -S mineplex.com
    
    # With custom settings:
    mcmonitor run -s servers.txt -i 120 -r 0.5 -f csv
    
    # Privacy mode (no player names):
    mcmonitor run -s servers.txt --no-player-names
    """
    # Show ethical notice
    if show_notice:
        print_ethical_notice()
        typer.echo()
    
    # Setup logging
    setup_structlog("INFO")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "monitor"
    
    # Build server list
    servers: List[ServerEntry] = []
    
    # Load from file
    if server_list:
        try:
            file_servers = load_servers_from_file(server_list)
            servers.extend(file_servers)
            console.print(f"[green]✓[/green] Loaded {len(file_servers)} servers from {server_list}")
        except Exception as e:
            console.print(f"[red]✗[/red] Error loading server list: {e}")
            raise typer.Exit(code=1)
    
    # Add individual servers
    if server:
        for s in server:
            if ':' in s:
                host, port_str = s.rsplit(':', 1)
                port = int(port_str)
            else:
                host = s
                port = 25565
            servers.append(ServerEntry(host=host, port=port))
        console.print(f"[green]✓[/green] Added {len(server)} command-line servers")
    
    # Fetch from APIs
    if mcstatus_io or minecraft_mp:
        console.print("[yellow]⏳[/yellow] Fetching servers from public APIs...")
        api_servers = asyncio.run(fetch_servers_from_apis(
            mcstatus_io_enabled=mcstatus_io,
            minecraft_mp_enabled=minecraft_mp,
            minecraft_mp_api_key=minecraft_mp_key,
        ))
        servers.extend(api_servers)
        console.print(f"[green]✓[/green] Fetched {len(api_servers)} servers from APIs")
    
    # Validate server list
    if not servers:
        console.print(Panel(
            "[red]No servers to monitor![/red]\n\n"
            "Provide servers via:\n"
            "  • --servers FILE (load from file)\n"
            "  • --server HOST:PORT (command line)\n"
            "  • --mcstatus-io or --minecraft-mp (public APIs)",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)
    
    # Display server summary
    table = Table(title=f"Monitoring {len(servers)} Servers")
    table.add_column("Host", style="cyan")
    table.add_column("Port", justify="right")
    table.add_column("Name", style="green")
    
    for s in servers[:10]:  # Show first 10
        table.add_row(s.host, str(s.port), s.name or "-")
    
    if len(servers) > 10:
        table.add_row(f"... and {len(servers) - 10} more", "", "")
    
    console.print(table)
    typer.echo()
    
    # Create configuration
    config = MonitorConfig(
        polling_interval=polling_interval,
        global_rate_limit=global_rate_limit,
        output_format=output_format,
        log_dir=str(log_dir),
    )
    
    # Handle shutdown signals
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        console.print("\n[yellow]⏹️  Shutdown requested...[/yellow]")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run monitoring service
    console.print(f"[green]▶[/green] Starting monitoring service...")
    console.print(f"   Polling interval: {polling_interval}s")
    console.print(f"   Rate limit: {global_rate_limit} queries/sec")
    console.print(f"   Log directory: {log_dir.absolute()}")
    if no_player_names:
        console.print(f"   [yellow]Privacy mode: Player names excluded[/yellow]")
    typer.echo()
    
    # Create and run service
    service = MonitoringService(
        servers=servers,
        config=config,
        log_path=str(log_path),
    )
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(service.stop())
    
    console.print("[green]✓[/green] Monitoring service stopped")


@app.command()
def test(
    server: str = typer.Argument(..., help="Server to test (host:port or host)"),
) -> None:
    """Test connection to a single Minecraft server."""
    from mcstatus import JavaServer
    
    setup_structlog("INFO")
    
    # Parse server address
    if ':' in server:
        host, port_str = server.rsplit(':', 1)
        port = int(port_str)
    else:
        host = server
        port = 25565
    
    console.print(f"[cyan]Testing connection to {host}:{port}...[/cyan]")
    
    try:
        mc_server = JavaServer.lookup(f"{host}:{port}")
        status = mc_server.status()
        
        table = Table(title=f"Server Status: {host}:{port}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Status", "[green]Online[/green]")
        table.add_row("Version", status.version.name if status.version else "Unknown")
        table.add_row("Protocol", str(status.version.protocol) if status.version else "Unknown")
        table.add_row("Players", f"{status.players.online}/{status.players.max}")
        table.add_row("Latency", f"{status.latency:.1f}ms")
        
        if status.motd:
            motd = status.motd.to_plain() if hasattr(status.motd, 'to_plain') else str(status.motd)
            table.add_row("MOTD", motd[:50] + "..." if len(motd) > 50 else motd)
        
        if status.players.sample:
            player_names = [p.name for p in status.players.sample[:5]]
            players_str = ", ".join(player_names)
            if len(status.players.sample) > 5:
                players_str += f" (+{len(status.players.sample) - 5} more)"
            table.add_row("Sample Players", players_str)
        
        console.print(table)
        
    except Exception as e:
        console.print(Panel(
            f"[red]Connection failed:[/red] {e}",
            title="Error",
            border_style="red",
        ))
        raise typer.Exit(code=1)


@app.command()
def validate(
    server_list: Path = typer.Argument(..., help="Server list file to validate"),
) -> None:
    """Validate a server list file."""
    try:
        servers = load_servers_from_file(server_list)
        
        table = Table(title=f"Validated {len(servers)} Servers")
        table.add_column("#", justify="right")
        table.add_column("Host", style="cyan")
        table.add_column("Port", justify="right")
        table.add_column("Valid", style="green")
        
        valid_count = 0
        for i, s in enumerate(servers, 1):
            # Basic validation
            is_valid = bool(s.host) and 1 <= s.port <= 65535
            if is_valid:
                valid_count += 1
            table.add_row(
                str(i),
                s.host,
                str(s.port),
                "[green]✓[/green]" if is_valid else "[red]✗[/red]",
            )
        
        console.print(table)
        console.print(f"\n[green]Valid:[/green] {valid_count}/{len(servers)} servers")
        
    except Exception as e:
        console.print(f"[red]Validation error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def example() -> None:
    """Generate an example server list file."""
    example_data = [
        {"host": "hypixel.net", "port": 25565, "name": "Hypixel Network"},
        {"host": "mineplex.com", "port": 25565, "name": "Mineplex"},
        {"host": "play.cubecraft.net", "port": 25565, "name": "CubeCraft Games"},
        {"host": "mc.hypixel.net", "port": 25565, "name": "Hypixel (alt)"},
    ]
    
    output_file = Path("example_servers.json")
    output_file.write_text(json.dumps(example_data, indent=2))
    
    console.print(Panel(
        f"[green]✓[/green] Created [cyan]{output_file}[/cyan]\n\n"
        f"Example content:\n"
        f"[dim]{json.dumps(example_data, indent=2)}[/dim]",
        title="Example Server List Created",
        border_style="green",
    ))


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
