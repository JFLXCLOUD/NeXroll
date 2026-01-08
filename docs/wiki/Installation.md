# Installation Guide

This guide covers installing NeXroll on different platforms.

## System Requirements

- **Plex Media Server** or **Jellyfin** (with Local Intros plugin)
- Network access between NeXroll and your media server
- Storage space for preroll videos

## Installation Options

| Platform | Recommended For |
|----------|-----------------|
| [Docker](#docker) | Most users, servers, NAS devices |
| [Windows](#windows) | Windows desktop users |
| [Python](#python-manual) | Developers, advanced users |

---

## Docker

Docker is the easiest and recommended installation method.

### Quick Start

```bash
docker run -d \
  --name nexroll \
  -p 9393:9393 \
  -v ./nexroll-data:/app/data \
  -v /path/to/prerolls:/prerolls \
  jbrns/nexroll:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  nexroll:
    image: jbrns/nexroll:latest
    container_name: nexroll
    ports:
      - "9393:9393"
    volumes:
      - ./nexroll-data:/app/data
      - /path/to/prerolls:/prerolls
    restart: unless-stopped
```

See the [Docker Setup](Docker) guide for detailed configuration options.

---

## Windows

### Windows Installer

1. Download the latest installer from [GitHub Releases](https://github.com/jbrfrn/NeXroll/releases)
2. Run `NeXroll-Setup.exe`
3. Follow the installation wizard
4. Launch NeXroll from the Start Menu

### Windows Service (Optional)

To run NeXroll as a background service:

1. Open the NeXroll installation folder
2. Run `install-service.bat` as Administrator
3. The service starts automatically on boot

### System Tray App

The installer includes a system tray application:
- Right-click the tray icon for quick access
- Start/stop the server
- Open the web interface

---

## Python (Manual)

For developers or advanced users who want to run from source.

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git (optional, for cloning)

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/jbrfrn/NeXroll.git
cd NeXroll

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run NeXroll
cd NeXroll/backend
python main.py
```

### Running as a Service (Linux)

Create a systemd service file `/etc/systemd/system/nexroll.service`:

```ini
[Unit]
Description=NeXroll Preroll Manager
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/NeXroll/NeXroll/backend
ExecStart=/path/to/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nexroll
sudo systemctl start nexroll
```

---

## Unraid

NeXroll is available in Unraid Community Applications.

1. Go to **Apps** in Unraid
2. Search for "NeXroll"
3. Click **Install**
4. Configure paths and ports
5. Click **Apply**

See [Docker Setup](Docker#unraid) for Unraid-specific configuration.

---

## Post-Installation

After installing:

1. Open NeXroll at `http://localhost:9393` (or your server's IP)
2. Go to **Connect** tab
3. Connect to your Plex or Jellyfin server
4. Configure [Path Mappings](Path-Mappings) if needed
5. Start adding prerolls!

## Updating

### Docker
```bash
docker pull jbrns/nexroll:latest
docker stop nexroll
docker rm nexroll
# Re-run your docker run command
```

### Windows
Download and run the latest installer - it will update your existing installation.

### Python
```bash
git pull
pip install -r requirements.txt --upgrade
```

## Next Steps

- [Getting Started](Getting-Started) - First-time setup walkthrough
- [Docker Setup](Docker) - Detailed Docker configuration
- [Configuration](Configuration) - All configuration options
