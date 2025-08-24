# EldersVR CLI - ADB Onboarding Tool

A command-line tool for deploying EldersVR content to Android devices via ADB.

## Features

- **Backend Integration**: Authenticate and fetch content from EldersVR API
- **Device Management**: Auto-detect and manage Android devices via ADB
- **Content Deployment**: Transfer videos, images, and metadata to devices
- **Security**: CLI-only operations for deployment and synchronization
- **Progress Tracking**: Real-time progress indicators for transfers

## Prerequisites

### System Requirements
- Python 3.8 or higher
- ADB (Android Debug Bridge) installed and in PATH
- USB debugging enabled on target Android devices

### Device Requirements
- Master device: Android phone with USB debugging
- Slave device: Android VR headset with USB debugging
- Both devices connected via USB
- Write permissions to `/storage/emulated/0/Download/EldersVR/`

## Installation

### From Source
```bash
git clone git@github.com:EldersVR/eldersvr-cli.git
cd eldersvr-cli
python3 -m venv venv
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

### Authentication
```bash
# Authenticate with default credentials
eldersvr-onboard auth

# Authenticate with custom credentials
eldersvr-onboard auth --email your@email.com --password yourpass
```

### Device Management
```bash
# List connected ADB devices
eldersvr-onboard list-devices

# Select master and slave devices
eldersvr-onboard select-devices --master ABC123 --slave XYZ789

# Verify device storage access
eldersvr-onboard verify --device ABC123
```

### Content Management
```bash
# Fetch videos and tags from backend
eldersvr-onboard fetch-data

# Download all video files and assets
eldersvr-onboard download-videos

# Download specific quality only
eldersvr-onboard download-videos --quality low
```

### Deployment (CLI-Only Operations)
```bash
# Transfer content to selected devices
eldersvr-onboard transfer

# Transfer to master device only (JSON only)
eldersvr-onboard transfer --master-only

# Transfer to slave device only (JSON + videos + images)  
eldersvr-onboard transfer --slave-only

# Complete automated deployment
eldersvr-onboard deploy --auto

# Verify deployment
eldersvr-onboard verify --deployment
```

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
    "device_path": "/storage/emulated/0/Download/EldersVR",
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
- **Content**: JSON metadata only (`new_data.json`)
- **Purpose**: Content browsing and selection
- **Storage**: `/storage/emulated/0/Download/EldersVR/new_data.json`

### Slave Device (VR Headset)
- **Content**: JSON metadata + all videos + images
- **Purpose**: Content playback and VR experience
- **Storage**: 
  - `/storage/emulated/0/Download/EldersVR/new_data.json`
  - `/storage/emulated/0/Download/EldersVR/Video/*.mp4`
  - `/storage/emulated/0/Download/EldersVR/Image/*`

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
      "fileKeyLow": "lowres_19_video.mp4",
      "fileKey": "highres_19_video.mp4", 
      "fileUrlLow": "https://storage.googleapis.com/.../low.mp4",
      "fileUrl": "https://storage.googleapis.com/.../high.mp4",
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

### Recovery Commands
```bash
# Clean EldersVR directory on device
eldersvr-onboard clean-devices --serial <serial>

# Retry failed transfers only
eldersvr-onboard retry-transfer --failed-only

# Fix storage permissions
eldersvr-onboard fix-permissions --serial <serial>
```

## Development

### Running from Source
```bash
cd eldersvr-cli
source venv/bin/activate
python -m eldersvr_cli.cli --help
```

### Running Tests
```bash
python -m pytest tests/
```

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