# EldersVR CLI - ADB Onboarding Tool

A command-line tool for deploying EldersVR content to Android devices via ADB.

## Features

- **Backend Integration**: Authenticate and fetch content from EldersVR API
- **Device Management**: Auto-detect and manage Android devices via ADB
- **Quality-Specific Deployment**: Master gets low-res, slave gets high-res videos
- **Directory Mapping**: List and compare device directories for verification
- **Smart Downloads**: File existence checking with user confirmation
- **File Conflict Resolution**: Interactive prompts for existing files during transfers
- **Real-time Progress**: Live progress percentages for transfers and downloads
- **Security**: CLI-only operations for deployment and synchronization

## Prerequisites

### System Requirements
- Python 3.8 or higher
- ADB (Android Debug Bridge) installed and in PATH
- USB debugging enabled on target Android devices

### Device Requirements
- Master device: Android phone with USB debugging
- Slave device: Android VR headset with USB debugging
- Both devices connected via USB
- EldersVR app installed on both devices (com.q42.eldersvr)
- Write permissions to `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/`

## Installation

### From Source
```bash
git clone git@github.com:EldersVR/eldersvr-cli.git
cd eldersvr-cli
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Using pip (when published)
```bash
pip install eldersvr-cli
```

## Quick Start

1. **Verify ADB connectivity**:
   ```bash
   eldersvr-onboard list-devices
   ```

2. **Authenticate with EldersVR backend**:
   ```bash
   eldersvr-onboard auth
   ```

3. **Complete deployment** (automated):
   ```bash
   eldersvr-onboard deploy --auto
   ```

## Commands

### Help and Version
```bash
# Show help for all commands
eldersvr-onboard --help

# Show help for specific command
eldersvr-onboard <command> --help

# Show version
eldersvr-onboard --version

# Enable verbose output for debugging
eldersvr-onboard --verbose <command>
```

### Authentication
```bash
# Authenticate with default credentials
eldersvr-onboard auth

# Authenticate with custom credentials
eldersvr-onboard auth --email your@email.com --password yourpass

# Clear stored authentication
eldersvr-onboard logout
```

### Device Management
```bash
# List connected ADB devices with details
eldersvr-onboard list-devices

# Select master and slave devices
eldersvr-onboard select-devices --master ABC123 --slave XYZ789

# Select only master device
eldersvr-onboard select-devices --master ABC123

# Select only slave device
eldersvr-onboard select-devices --slave XYZ789

# Verify device storage access
eldersvr-onboard verify --device ABC123

# Verify complete deployment on configured devices
eldersvr-onboard verify --deployment
```

### Content Management
```bash
# Fetch videos and tags from backend
eldersvr-onboard fetch-data

# Download all video files and assets (both qualities)
eldersvr-onboard download-videos

# Download specific quality only
eldersvr-onboard download-videos --quality high    # High-res only
eldersvr-onboard download-videos --quality low     # Low-res only
eldersvr-onboard download-videos --quality both    # Both qualities (default)

# Sequential downloads (slower but more reliable)
eldersvr-onboard download-videos --sequential

# Custom parallel processing settings
eldersvr-onboard download-videos --max-workers 8
eldersvr-onboard download-videos --timeout 120
eldersvr-onboard download-videos --retry-attempts 5

# Limit progress table display
eldersvr-onboard download-videos --show-files 5

# Combined options
eldersvr-onboard download-videos --quality both --max-workers 6 --timeout 180 --show-files 10
```

### Directory Management
```bash
# List directories on all configured devices (master and slave)
eldersvr-onboard list-directories

# List directories on specific device by serial number
eldersvr-onboard list-directories --device ABC123

# Compare directories between master and slave devices
eldersvr-onboard list-directories --compare

# Show detailed file information (sizes, dates, permissions)
eldersvr-onboard list-directories --detailed

# Combine options: detailed comparison
eldersvr-onboard list-directories --compare --detailed

# Quick device check
eldersvr-onboard list-directories --device ABC123 --detailed
```

### Deployment (CLI-Only Operations)
```bash
# Transfer content to all selected devices
# Master gets: JSON + credential + low-res videos + images
# Slave gets: JSON + high-res videos + images
eldersvr-onboard transfer

# File Conflict Handling (New Feature!)
# When files already exist on device, CLI will prompt:
#   ⚠️  File conflict detected: video_file.mp4
#   📱 Device (Master): 15.2 MB
#   💻 Local: 16.1 MB
#   
#   Choose action:
#     [s]kip this file
#     [o]verride (replace on device)
#     [c]ancel transfer
#   Choice (s/o/c): 

# Transfer to specific device types only
eldersvr-onboard transfer --master-only  # Low-res videos + JSON + credential
eldersvr-onboard transfer --slave-only    # High-res videos + JSON + images

# Transfer specific content types
eldersvr-onboard transfer --videos-only   # Only videos (quality-specific per device)
eldersvr-onboard transfer --json-only     # Only JSON and credential files

# Combined transfer options
eldersvr-onboard transfer --master-only --videos-only  # Only low-res videos to master
eldersvr-onboard transfer --slave-only --json-only     # Only JSON to slave

# Complete automated deployment pipeline
eldersvr-onboard deploy --auto                    # Auto-detect devices
eldersvr-onboard deploy --skip-auth               # Skip authentication step
eldersvr-onboard deploy --skip-fetch              # Skip data fetching
eldersvr-onboard deploy --skip-download           # Skip asset download
eldersvr-onboard deploy --auto --skip-auth        # Combined options

# Verify deployment results
eldersvr-onboard verify --deployment              # Verify all configured devices
eldersvr-onboard verify --device ABC123           # Verify specific device
```

## Command Reference

### Complete Command List

| Command | Description | Key Options |
|---------|-------------|-------------|
| `auth` | Authenticate with backend | `--email`, `--password` |
| `logout` | Clear stored authentication | None |
| `list-devices` | List connected ADB devices | None |
| `select-devices` | Configure master/slave devices | `--master`, `--slave` |
| `verify` | Verify device or deployment | `--device`, `--deployment` |
| `fetch-data` | Fetch content from backend | None |
| `download-videos` | Download video assets | `--quality`, `--sequential`, `--max-workers`, `--timeout`, `--retry-attempts`, `--show-files` |
| `list-directories` | List/compare device directories | `--device`, `--compare`, `--detailed` |
| `transfer` | Transfer content to devices | `--master-only`, `--slave-only`, `--videos-only`, `--json-only` |
| `deploy` | Complete deployment pipeline | `--auto`, `--skip-auth`, `--skip-fetch`, `--skip-download` |

### Global Options

| Option | Description | Usage |
|--------|-------------|-------|
| `--config` | Custom configuration file path | `--config /path/to/config.json` |
| `--verbose`, `-v` | Enable verbose output | `--verbose` or `-v` |
| `--version` | Show version information | `--version` |
| `--help` | Show help information | `--help` |

### Common Usage Patterns

```bash
# Complete setup workflow
eldersvr-onboard auth
eldersvr-onboard list-devices
eldersvr-onboard select-devices --master ABC123 --slave XYZ789
eldersvr-onboard fetch-data
eldersvr-onboard download-videos
eldersvr-onboard transfer
eldersvr-onboard verify --deployment

# Quick deployment (if devices already configured)
eldersvr-onboard deploy --auto

# Troubleshooting workflow
eldersvr-onboard list-devices
eldersvr-onboard list-directories --compare
eldersvr-onboard verify --deployment

# Development/testing workflow
eldersvr-onboard --verbose download-videos --sequential --show-files 10
eldersvr-onboard --verbose transfer --master-only --videos-only
```

### Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | General error or command failed |
| 130 | Operation cancelled by user (Ctrl+C) |

## Configuration

### Default Configuration
The CLI uses the following default configuration:

```json
{
  "backend": {
    "api_url": "https://api.eldersvr.com",
    "auth_endpoint": "/integration/auth/login",
    "tags_endpoint": "/integration/tags",
    "films_endpoint": "/integration/films"
  },
  "paths": {
    "local_downloads": "./downloads",
    "device_path": "/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR",
    "json_filename": "new_data.json"
  },
  "auth": {
    "email": "clionboarding@eldervr.com",
    "password": "clionboarding@eldervr.com"
  }
}
```

### Custom Configuration
Create `eldersvr_config.json` in your working directory:

```json
{
  "backend": {
    "api_url": "https://your-api.com"
  },
  "auth": {
    "email": "your@email.com",
    "password": "yourpassword"
  }
}
```

## Device Deployment Architecture

### Master Device (Android Phone)
- **Content**: JSON metadata + credential.json + low-res videos + images
- **Purpose**: Content browsing and selection
- **Video Quality**: Low-res only (files with `lowres_*` prefix)
- **Storage**: `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/`
- **Transfer Features**: Real-time progress, selective quality deployment

### Slave Device (VR Headset)
- **Content**: JSON metadata + high-res videos + images
- **Purpose**: Content playback and VR experience
- **Video Quality**: High-res only (files with `highres_*` prefix)
- **Storage**:
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/new_data.json`
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/Video/*.mp4`
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/Image/*`
- **Transfer Features**: Real-time progress, high-quality content optimization

### Directory Structure Verification
Use `list-directories` commands to verify deployment:
```bash
# Check all configured devices
eldersvr-onboard list-directories

# Compare master vs slave content
eldersvr-onboard list-directories --compare

# Detailed file analysis
eldersvr-onboard list-directories --detailed
```

## Security Model

### CLI-Only Operations
The following operations are **restricted to CLI usage only** and cannot be performed through mobile apps:

- `transfer` - Moving content to devices
- `sync` - Synchronizing content with backend
- `deploy` - Complete deployment pipeline
- Any bulk content management operations

### User Interface Restrictions
Mobile app users can:
- ✅ View available content (read `new_data.json`)
- ✅ Play videos and view images
- ✅ Navigate content library
- ✅ Use app features for content consumption

Mobile app users **cannot**:
- ❌ Initiate content transfers to devices
- ❌ Sync content with backend
- ❌ Trigger deployment processes
- ❌ Access bulk download functionality

## Data Structure

### new_data.json Format
```json
{
  "lastModified": "08/22/2025 08:46:06",
  "videos": [
    {
      "id": "19",
      "title": "Video Title",
      "description": "Video Description",
      "thumbnailKey": "thumbnail_19_image.jpg",
      "thumbnailUrl": "https://storage.googleapis.com/.../image.jpg",
      "fileKeyLow": "lowres_19_VideoTitle.mp4",
      "fileKey": "highres_19_VideoTitle.mp4",
      "fileUrlLow": "https://storage.googleapis.com/.../lowres.mp4",
      "fileUrl": "https://storage.googleapis.com/.../highres.mp4",
      "isActive": true,
      "tags": [
        {
          "id": 1,
          "name": "Tag Name",
          "imageUrl": "https://storage.googleapis.com/.../tag.jpg"
        }
      ]
    }
  ],
  "tags": [
    {
      "id": 1,
      "name": "Tag Name",
      "imageUrl": "https://storage.googleapis.com/.../tag.jpg"
    }
  ]
}
```

## Usage Examples

### First-Time Setup
```bash
# 1. Check if ADB devices are connected
eldersvr-onboard list-devices

# 2. Authenticate with backend
eldersvr-onboard auth --email admin@eldersvr.com --password mypassword

# 3. Select your devices
eldersvr-onboard select-devices --master ABC123 --slave XYZ789

# 4. Verify devices can be accessed
eldersvr-onboard verify --device ABC123
eldersvr-onboard verify --device XYZ789

# 5. Fetch latest content
eldersvr-onboard fetch-data

# 6. Download all assets
eldersvr-onboard download-videos

# 7. Deploy to devices
eldersvr-onboard transfer

# 8. Verify deployment
eldersvr-onboard verify --deployment
```

### Quick Deployment (Automated)
```bash
# One-command deployment (auto-detects devices)
eldersvr-onboard deploy --auto

# Skip steps if already done
eldersvr-onboard deploy --skip-auth --skip-download
```

### Selective Operations
```bash
# Only update master device with new JSON
eldersvr-onboard transfer --master-only --json-only

# Only transfer high-res videos to slave
eldersvr-onboard transfer --slave-only --videos-only

# Download only low-res videos
eldersvr-onboard download-videos --quality low

# Transfer with verbose progress
eldersvr-onboard --verbose transfer

# Handle file conflicts during transfer
eldersvr-onboard transfer  # Will prompt for each existing file:
                          # [s]kip, [o]verride, or [c]ancel
```

### Directory Management
```bash
# Check what's on devices
eldersvr-onboard list-directories

# Detailed comparison between master and slave
eldersvr-onboard list-directories --compare --detailed

# Check specific device storage
eldersvr-onboard list-directories --device ABC123 --detailed
```

### Download Management
```bash
# Handle existing files interactively
eldersvr-onboard download-videos  # Will prompt: (o)verride, (s)kip, (c)ancel

# Custom download settings for slow/unreliable connections
eldersvr-onboard download-videos --sequential --timeout 300 --retry-attempts 5

# Fast parallel downloads
eldersvr-onboard download-videos --max-workers 10 --show-files 20
```

### Troubleshooting Commands
```bash
# Debug connection issues
eldersvr-onboard --verbose list-devices

# Check authentication
eldersvr-onboard --verbose auth

# Verify specific device access
eldersvr-onboard --verbose verify --device ABC123

# Compare device contents
eldersvr-onboard list-directories --compare

# Re-authenticate and retry
eldersvr-onboard logout
eldersvr-onboard auth
```

### Workflow Examples

#### Content Update Workflow
```bash
# 1. Fetch latest content from backend
eldersvr-onboard fetch-data

# 2. Download new/updated assets (with file existence prompts)
eldersvr-onboard download-videos

# 3. Transfer to devices (quality-specific)
eldersvr-onboard transfer

# 4. Verify successful deployment
eldersvr-onboard list-directories --compare
```

#### Device Maintenance Workflow
```bash
# 1. Check current device status
eldersvr-onboard list-directories --detailed

# 2. Compare master vs slave content
eldersvr-onboard list-directories --compare

# 3. Re-deploy if inconsistencies found
eldersvr-onboard transfer

# 4. Final verification
eldersvr-onboard verify --deployment
```

#### Development/Testing Workflow
```bash
# 1. Use verbose mode for debugging
eldersvr-onboard --verbose download-videos --sequential

# 2. Test master device only
eldersvr-onboard transfer --master-only

# 3. Check results
eldersvr-onboard list-directories --device ABC123 --detailed

# 4. Test slave device
eldersvr-onboard transfer --slave-only

# 5. Compare final results
eldersvr-onboard list-directories --compare
```

## Troubleshooting

### Common Issues

**ADB device not found**:
```bash
# Check USB connection and authorization
adb devices
# Enable USB debugging on device
# Accept authorization dialog on device
```

**Permission denied errors**:
```bash
# Verify storage permissions
eldersvr-onboard verify --device <serial>
# Grant storage permissions in Android settings
```

**Transfer failures**:
```bash
# Check available storage space
eldersvr-onboard verify --deployment
# Clean and retry
eldersvr-onboard transfer --retry-failed
```

**Authentication failures**:
```bash
# Verify credentials
eldersvr-onboard auth --email your@email.com --password yourpass
# Check network connectivity
# Verify API endpoint accessibility
```

### Directory and Storage Management
```bash
# List device directories
eldersvr-onboard list-directories --device <serial>

# Compare master and slave directories
eldersvr-onboard list-directories --compare

# Show detailed file information
eldersvr-onboard list-directories --detailed
```

### Download Management
```bash
# Check for existing files before downloading
# CLI will prompt: (o)verride, (s)kip, or (c)ancel
eldersvr-onboard download-videos

# Sequential downloads (slower but more reliable)
eldersvr-onboard download-videos --sequential

# Custom parallel settings
eldersvr-onboard download-videos --max-workers 8 --timeout 120
```

## Development

### Running from Source
```bash
cd eldersvr-cli
source venv/bin/activate
python -m eldersvr_cli.cli --help
```

### Make Commands (Development)
```bash
# Setup development environment
make setup-dev

# Run tests
make test

# Run tests with coverage
make test-coverage

# Lint and format code
make lint
make format

# Type checking
make type-check

# Quick operations
make run-auth          # Authenticate
make run-list          # List devices
make run-list-dirs     # List directories
make run-compare-dirs  # Compare master/slave
make run-deploy        # Full deployment
make run-verify        # Verify deployment
```

### Running Tests
```bash
python -m pytest tests/
```

### Key Features for Development
- **Quality-based transfers**: Master (low-res) vs Slave (high-res)
- **Real-time progress**: File transfer percentages
- **Smart downloads**: Existence checking with user prompts
- **Directory mapping**: Complete device directory analysis
- **Error handling**: Comprehensive fallback mechanisms

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Author

**Indra Gunanda**
Email: info@ciptadusa.com
Company: EldersVR

---

For issues and support, please visit: https://github.com/EldersVR/eldersvr-cli/issues

## Recent Updates

- **v1.0.0**: Initial release with basic ADB deployment
- **v1.1.0**: Added quality-specific transfers (master: low-res, slave: high-res)
- **v1.2.0**: Real-time transfer progress with percentages
- **v1.3.0**: Smart download management with file existence checking
- **v1.4.0**: Directory listing and comparison tools
- **v1.5.0**: Updated to use app-specific Android directories
- **v1.6.0**: Enhanced file conflict resolution for transfers (interactive skip/override prompts)
