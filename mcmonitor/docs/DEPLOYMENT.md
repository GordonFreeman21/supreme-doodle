# Deployment Guide

This guide covers deploying MCMonitor as a long-running service in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Linux systemd Service](#linux-systemd-service)
3. [Docker Container](#docker-container)
4. [Docker Compose](#docker-compose)
5. [Kubernetes](#kubernetes)
6. [Windows Task Scheduler](#windows-task-scheduler)
7. [Supervisor (Alternative to systemd)](#supervisor-alternative-to-systemd)
8. [Monitoring and Alerting](#monitoring-and-alerting)

---

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **Memory**: 100-500 MB depending on server count
- **Disk**: 1 GB for application + log storage
- **Network**: Outbound access to Minecraft servers (port 25565 by default)

### Installation

```bash
# Clone or download the project
cd /path/to/mcmonitor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

---

## Linux systemd Service

### Step 1: Create System User

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin mcmonitor
```

### Step 2: Set Up Application Directory

```bash
sudo mkdir -p /opt/mcmonitor
sudo chown mcmonitor:mcmonitor /opt/mcmonitor

# Copy application
sudo cp -r * /opt/mcmonitor/
cd /opt/mcmonitor

# Create virtual environment
sudo -u mcmonitor python -m venv venv
sudo -u mcmonitor /opt/mcmonitor/venv/bin/pip install -e .

# Create directories
sudo mkdir -p /opt/mcmonitor/logs /opt/mcmonitor/data /opt/mcmonitor/config
sudo chown -R mcmonitor:mcmonitor /opt/mcmonitor
```

### Step 3: Create Configuration File

```bash
sudo -u mcmonitor cat > /opt/mcmonitor/config/servers.json << 'EOF'
[
  {"host": "hypixel.net", "port": 25565, "name": "Hypixel"},
  {"host": "mineplex.com", "port": 25565, "name": "Mineplex"}
]
EOF
```

### Step 4: Create systemd Service Unit

```bash
sudo tee /etc/systemd/system/mcmonitor.service > /dev/null << 'EOF'
[Unit]
Description=Minecraft Server Monitor
Documentation=https://github.com/example/mcmonitor
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mcmonitor
Group=mcmonitor

WorkingDirectory=/opt/mcmonitor
Environment="PATH=/opt/mcmonitor/venv/bin"
ExecStart=/opt/mcmonitor/venv/bin/mcmonitor run \
    -s /opt/mcmonitor/config/servers.json \
    -i 60 \
    -r 1.0 \
    -f json \
    -l /opt/mcmonitor/logs

# Restart configuration
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/mcmonitor/logs /opt/mcmonitor/data
RestrictAddressFamilies=AF_INET AF_INET6

# Resource limits
MemoryMax=512M
CPUQuota=50%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mcmonitor

[Install]
WantedBy=multi-user.target
EOF
```

### Step 5: Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcmonitor
sudo systemctl start mcmonitor
```

### Step 6: Verify and Monitor

```bash
# Check status
sudo systemctl status mcmonitor

# View logs
sudo journalctl -u mcmonitor -f

# Stop service
sudo systemctl stop mcmonitor

# Restart service
sudo systemctl restart mcmonitor
```

### Log Rotation (Optional)

Create `/etc/logrotate.d/mcmonitor`:

```bash
sudo tee /etc/logrotate.d/mcmonitor > /dev/null << 'EOF'
/opt/mcmonitor/logs/*.jsonl /opt/mcmonitor/logs/*.csv {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 mcmonitor mcmonitor
}
EOF
```

---

## Docker Container

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home --uid 1000 mcmonitor && \
    mkdir -p /app/logs /app/data /app/config && \
    chown -R mcmonitor:mcmonitor /app

USER mcmonitor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "mcmonitor" || exit 1

# Default command
CMD ["mcmonitor", "run", "-s", "/app/config/servers.json"]
```

### Build and Run

```bash
# Build image
docker build -t mcmonitor:latest .

# Create config directory
mkdir -p config
cat > config/servers.json << 'EOF'
[
  {"host": "hypixel.net", "port": 25565, "name": "Hypixel"}
]
EOF

# Run container
docker run -d \
  --name mcmonitor \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --memory 512m \
  --cpus 0.5 \
  mcmonitor:latest

# View logs
docker logs -f mcmonitor

# Stop container
docker stop mcmonitor
```

---

## Docker Compose

### docker-compose.yml

```yaml
version: '3.8'

services:
  mcmonitor:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mcmonitor
    restart: unless-stopped
    
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./data:/app/data
    
    # Resource limits
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 128M
    
    # Health check
    healthcheck:
      test: ["CMD", "pgrep", "-f", "mcmonitor"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    
    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    
    # Security options
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp

  # Optional: Grafana for visualization
  grafana:
    image: grafana/grafana:latest
    container_name: mcmonitor-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - mcmonitor

volumes:
  grafana-data:
```

### Usage

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f mcmonitor

# Stop all services
docker-compose down

# Update and restart
docker-compose pull
docker-compose up -d --force-recreate
```

---

## Kubernetes

### Deployment YAML

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcmonitor-config
data:
  servers.json: |
    [
      {"host": "hypixel.net", "port": 25565, "name": "Hypixel"}
    ]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcmonitor
  labels:
    app: mcmonitor
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcmonitor
  template:
    metadata:
      labels:
        app: mcmonitor
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      
      containers:
      - name: mcmonitor
        image: mcmonitor:latest
        imagePullPolicy: Always
        
        args:
        - run
        - -s
        - /app/config/servers.json
        - -i
        - "60"
        - -f
        - json
        
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: logs
          mountPath: /app/logs
        - name: data
          mountPath: /app/data
        
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        
        livenessProbe:
          exec:
            command: ["pgrep", "-f", "mcmonitor"]
          initialDelaySeconds: 30
          periodSeconds: 30
        
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
      
      volumes:
      - name: config
        configMap:
          name: mcmonitor-config
      - name: logs
        emptyDir: {}
      - name: data
        emptyDir: {}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mcmonitor-logs-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

---

## Windows Task Scheduler

### PowerShell Script

Create `mcmonitor-runner.ps1`:

```powershell
$workingDir = "C:\mcmonitor"
$venvPython = "C:\mcmonitor\venv\Scripts\python.exe"
$script = "C:\mcmonitor\src\mcmonitor\cli.py"

Set-Location $workingDir

& $venvPython -m mcmonitor run `
    -s "C:\mcmonitor\config\servers.json" `
    -i 60 `
    -f json `
    -l "C:\mcmonitor\logs"
```

### Task Scheduler Setup

1. Open Task Scheduler
2. Create Basic Task
3. Name: "Minecraft Server Monitor"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Program: `powershell.exe`
7. Arguments: `-ExecutionPolicy Bypass -File "C:\mcmonitor\mcmonitor-runner.ps1"`
8. Finish and configure additional properties:
   - Run whether user is logged on or not
   - Run with highest privileges
   - Restart every 1 minute if fails

---

## Supervisor (Alternative to systemd)

### Installation

```bash
# Ubuntu/Debian
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install supervisor
```

### Configuration

Create `/etc/supervisor/conf.d/mcmonitor.conf`:

```ini
[program:mcmonitor]
command=/opt/mcmonitor/venv/bin/mcmonitor run -s /opt/mcmonitor/config/servers.json -i 60
directory=/opt/mcmonitor
user=mcmonitor
autostart=true
autorestart=true
stderr_logfile=/var/log/mcmonitor/err.log
stdout_logfile=/var/log/mcmonitor/out.log
environment=PATH="/opt/mcmonitor/venv/bin"
stopsignal=TERM
stopwaitsecs=10
numprocs=1
process_name=%(program_name)s
```

### Management

```bash
# Reload configuration
sudo supervisorctl reread
sudo supervisorctl update

# Start service
sudo supervisorctl start mcmonitor

# Check status
sudo supervisorctl status mcmonitor

# View logs
sudo tail -f /var/log/mcmonitor/out.log
```

---

## Monitoring and Alerting

### Health Check Endpoint

Add a simple HTTP health check by creating a sidecar or modifying the service.

### Prometheus Metrics (Future Enhancement)

Export metrics for monitoring:

```python
# Example metrics to expose:
# - mcmonitor_servers_total
# - mcmonitor_servers_online
# - mcmonitor_query_duration_seconds
# - mcmonitor_query_errors_total
```

### Alerting Rules

Example Prometheus alert rules:

```yaml
groups:
- name: mcmonitor
  rules:
  - alert: McmonitorDown
    expr: up{job="mcmonitor"} == 0
    for: 5m
    annotations:
      summary: "MCMonitor is down"
  
  - alert: HighErrorRate
    expr: rate(mcmonitor_query_errors_total[5m]) > 0.1
    for: 10m
    annotations:
      summary: "High error rate in server monitoring"
```

### Log Aggregation

Configure log shipping to centralized logging:

```yaml
# Fluentd example
<match mcmonitor.**>
  @type elasticsearch
  host elasticsearch.example.com
  port 9200
  index_name mcmonitor-logs
</match>
```

---

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
sudo journalctl -u mcmonitor -n 50

# Verify Python path
which python
/opt/mcmonitor/venv/bin/python --version

# Test manually
sudo -u mcmonitor /opt/mcmonitor/venv/bin/mcmonitor run --help
```

**High memory usage:**
```bash
# Check resource limits in service file
# Reduce server count or polling frequency
# Increase MemoryMax limit if needed
```

**Permission denied errors:**
```bash
# Fix ownership
sudo chown -R mcmonitor:mcmonitor /opt/mcmonitor/logs

# Check SELinux/AppArmor
getenforce  # Should be Permissive or add exceptions
```

**Network connectivity issues:**
```bash
# Test outbound connection
nc -zv hypixel.net 25565

# Check firewall rules
sudo iptables -L -n | grep 25565
```

---

## Best Practices

1. **Run as non-root**: Always use a dedicated service account
2. **Resource limits**: Set memory and CPU limits
3. **Log rotation**: Prevent disk exhaustion
4. **Health checks**: Enable automatic restart on failure
5. **Security hardening**: Use systemd security options
6. **Regular updates**: Keep dependencies current
7. **Backup configs**: Version control your configuration
8. **Monitor the monitor**: Set up alerts for the monitoring service itself

---

For more information, see:
- [ETHICS.md](ETHICS.md) - Ethical usage guidelines
- [README.md](../README.md) - General documentation
