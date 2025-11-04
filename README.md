# NeXroll 🎬

**Advanced Preroll Management for Plex and Jellyfin**

[![Version](https://img.shields.io/badge/version-1.7.0-blue.svg)](https://github.com/JFLXCLOUD/NeXroll/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-jbrns%2Fnexroll-blue.svg)](https://hub.docker.com/r/jbrns/nexroll)

## 📖 Overview

NeXroll is a powerful preroll management system that automates the scheduling and organization of video prerolls (intros, trailers, ads) for Plex and Jellyfin media servers. With an intuitive web interface and robust scheduling engine, NeXroll makes it easy to create dynamic viewing experiences.

## ✨ Key Features

### 🌟 Core Features
- **Smart Scheduling**: Time-based, date-based, and recurring schedule support
- **Category Management**: Organize prerolls into categories with custom ordering
- **Automatic Application**: Apply prerolls to Plex/Jellyfin libraries automatically
- **Genre-based Mapping**: Map genres to specific preroll categories (experimental)
- **Holiday Presets**: Quick setup for holidays and special occasions
- **Path Mappings**: Support for Docker, NAS, and UNC path translations

### Community Prerolls (NEW in v1.7.0)
- Access thousands of community-curated prerolls from prerolls.typicalnerds.uk
- Smart search with synonym expansion and category filtering
- Platform filtering (Plex/Jellyfin/Emby)
- Local indexing for instant searches across 1,300+ prerolls
- One-click downloads with no automatic tagging
- Random preroll discovery
- Fair Use Policy protection

### 🔌 Media Server Integration
- **Plex**: Full support with multiple connection methods
- **Jellyfin**: Complete integration with API key authentication
- **OAuth**: Plex.tv authentication for easy setup
- **Docker-friendly**: Auto-discovery for containerized environments

### 🎨 Modern Interface
- Dark/Light theme support
- Responsive design
- Real-time status updates
- Drag-and-drop file uploads
- Advanced filtering and search

## 🚀 Quick Start

### Windows Installation

1. **Download** the latest installer:
   - [NeXroll_Installer.exe](https://github.com/JFLXCLOUD/NeXroll/releases/latest) (90.92 MB)

2. **Run** the installer as Administrator

3. **Launch** NeXroll from Start Menu or Desktop

4. **Connect** to your Plex or Jellyfin server:
   - Open `http://localhost:9393` in your browser
   - Go to the **Connect** tab
   - Choose your connection method

### Docker Installation

#### Using Docker Compose (Recommended)

```yaml
version: '3.8'

services:
  nexroll:
    image: jbrns/nexroll:latest
    container_name: nexroll
    restart: unless-stopped
    ports:
      - "9393:9393"
    volumes:
      - /path/to/your/prerolls:/app/data/prerolls
      - nexroll-data:/app/data
    environment:
      - PLEX_TOKEN=${PLEX_TOKEN}
      - TZ=America/New_York

volumes:
  nexroll-data:
```

```bash
docker-compose up -d
```

#### Using Docker Run

```bash
docker run -d \
  --name nexroll \
  -p 9393:9393 \
  -v /path/to/prerolls:/app/data/prerolls \
  -v nexroll-data:/app/data \
  -e PLEX_TOKEN=your_plex_token \
  -e TZ=America/New_York \
  jbrns/nexroll:latest
```

Access the interface at `http://localhost:9393`

## 📋 Requirements

### Windows
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 512 MB minimum, 1 GB recommended
- **Disk**: 200 MB for application + space for prerolls
- **Network**: Internet connection for Community Prerolls

### Docker
- **Docker**: 20.10 or later
- **Docker Compose**: 1.29 or later (optional)
- **Platforms**: linux/amd64, linux/arm64

### Media Server
- **Plex**: Version 1.20+ (Remote Access recommended)
- **Jellyfin**: Version 10.8+ with API key

## 🔧 Configuration

### First-Time Setup

1. **Connect to Media Server**
   - Navigate to **Connect** tab
   - Choose connection method:
     - **Plex.tv OAuth** (recommended for Docker)
     - **Manual URL + Token**
     - **Saved Token**

2. **Set Root Path**
   - Go to **Settings** → **Root Path**
   - Enter the location where prerolls are stored
   - For Docker: Use container path (e.g., `/app/data/prerolls`)

3. **Configure Path Mappings** (if needed)
   - For Docker/NAS setups
   - Translate between local and Plex-visible paths
   - Example: `/app/data/prerolls` → `Z:\Prerolls`

### Community Prerolls Setup

1. **Accept Fair Use Policy**
   - Go to **Community** tab
   - Read and accept the Fair Use Policy
   - Checkbox will persist your acceptance

2. **Search and Download**
   - Use the search bar to find prerolls
   - Filter by platform (Plex/Jellyfin)
   - Click download button to add to your library

## 📚 Documentation

### User Guides
- [Installation Guide](Docs/INSTALLATION.md)
- [Docker Setup](Docs/DOCKER.md)
- [Path Mappings Guide](Docs/PATH_MAPPINGS.md)
- [Troubleshooting](Docs/TROUBLESHOOTING.md)

### Developer Docs
- [Build Instructions](Docs/BUILD_INSTRUCTIONS.md)
- [API Documentation](Docs/API.md)
- [Contributing Guide](CONTRIBUTING.md)

## 🐛 Bug Reports & Feature Requests

Found a bug or have a feature idea?

1. **Download Diagnostics**: Settings → Download Diagnostics
2. **Report Issue**: 
   - [🐛 Bug Report](https://github.com/JFLXCLOUD/NeXroll/issues/new?template=bug_report.md)
   - [💡 Feature Request](https://github.com/JFLXCLOUD/NeXroll/issues/new?template=feature_request.md)
3. **Attach Diagnostics** to your issue

Or use the built-in reporting from **Settings** tab!

## 🔄 Upgrading

### From v1.5.12 or Earlier

**Automatic Migration** - NeXroll will automatically:
- Migrate database schema
- Move tokens to secure storage
- Update configuration files

**Steps:**
1. Download new installer
2. Run installer (settings preserved)
3. Launch NeXroll
4. Check logs for migration status

**Expected Console Output:**
```
>>> UPGRADE DETECTED: Migrating database schema...
>>> MIGRATION SUCCESS: Database schema migration completed
```

### From v1.6.x

Direct upgrade supported. No special steps required.

## 🏗️ Building from Source

### Prerequisites
- Python 3.11+
- Node.js 18+
- NSIS (for Windows installer)
- PyInstaller

### Build Steps

```bash
# Clone repository
git clone https://github.com/JFLXCLOUD/NeXroll.git
cd NeXroll/NeXroll

# Install Python dependencies
pip install -r requirements.txt

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Build executable
python -m PyInstaller build/neXroll.spec

# Create installer (Windows)
makensis installer.nsi
```

See [BUILD_INSTRUCTIONS.md](Docs/BUILD_INSTRUCTIONS.md) for detailed guide.

## 🐳 Docker Development

### Build Docker Image

```bash
cd NeXroll
docker build -t nexroll:dev .
```

### Run Development Container

```bash
docker run -p 9393:9393 \
  -v $(pwd)/prerolls:/app/data/prerolls \
  nexroll:dev
```

## 📊 Architecture

```
NeXroll/
├── backend/          # FastAPI Python backend
│   ├── main.py      # API routes
│   ├── models.py    # Database models
│   ├── scheduler.py # Scheduling engine
│   └── ...
├── frontend/        # React web interface
│   └── src/
│       └── App.js   # Main React component
├── scripts/         # Utility scripts
└── build/          # Build configurations
```

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Community Prerolls**: Powered by [prerolls.typicalnerds.uk](https://prerolls.typicalnerds.uk/)
- **Plex**: For their excellent media server platform
- **Jellyfin**: For their open-source media server
- **Contributors**: Thank you to everyone who has contributed!

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/JFLXCLOUD/NeXroll/issues)
- **Documentation**: Check the `Docs/` folder
- **Community**: Join discussions in Issues

## 🗺️ Roadmap

### Planned Features
- [ ] Additional media server support
- [ ] Mobile-responsive UI improvements
- [ ] Advanced scheduling rules
- [ ] Plugin system
- [ ] Cloud backup integration
- [ ] Multi-language support

### In Progress
- [x] Community Prerolls integration
- [x] Enhanced Plex connection methods
- [x] Secure token storage
- [x] Database migration system

## 📈 Statistics

- **Version**: 1.7.0
- **First Release**: 2024
- **Active Installations**: Growing
- **Community Prerolls**: 1000+
- **Lines of Code**: 25,000+

## ⭐ Show Your Support

If you find NeXroll useful, please consider:
- ⭐ Starring the repository
- 🐛 Reporting bugs
- 💡 Suggesting features
- 🤝 Contributing code
- 📢 Spreading the word

---

**Made with ❤️ for the Plex and Jellyfin community**

*NeXroll - Elevate your viewing experience* 🎬
