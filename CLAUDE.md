# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EldersVR CLI is a command-line tool for deploying VR content to Android devices via ADB. It manages content deployment to two device types:
- **Master device** (Android phone): Receives low-res videos, JSON metadata, and credentials
- **Slave device** (VR headset): Receives high-res videos and JSON metadata

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies and package
pip install -r requirements.txt
pip install -e .
```

### Testing
```bash
# Run all tests with pytest
make test
# or
python3 -m pytest tests/ -v

# Run tests with coverage
make test-coverage
# or
python3 -m pytest tests/ --cov=eldersvr_cli --cov-report=html --cov-report=term
```

### Code Quality
```bash
# Lint with flake8
make lint
# or
python3 -m flake8 eldersvr_cli/ tests/

# Format with black
make format
# or
python3 -m black eldersvr_cli/ tests/

# Type checking with mypy
make type-check
# or
python3 -m mypy eldersvr_cli/
```

### Build and Distribution
```bash
# Build distribution packages
make build
# or
python3 setup.py sdist bdist_wheel

# Clean build artifacts
make clean
```

### Running the CLI
```bash
# After installation
eldersvr-onboard <command> [options]

# During development (from source)
python3 -m eldersvr_cli.cli <command> [options]
```

## Architecture

### Core Components

1. **`eldersvr_cli/cli.py`**: Main entry point and command orchestrator
   - Class `EldersVRCLI`: Central command handler with configuration management and file conflict resolution
   - Handles all CLI commands (auth, deploy, transfer, etc.)
   - Manages interactive prompts for file conflicts (skip/override)

2. **`eldersvr_cli/core/adb_manager.py`**: Android device interaction
   - Class `ADBManager`: Handles all ADB operations
   - Device detection, file transfers, storage verification
   - Master/slave device differentiation for quality-specific deployments
   - Class `CLIAccessControl`: Security decorator for CLI-only operations

3. **`eldersvr_cli/core/content_manager.py`**: Backend API and downloads
   - Class `ContentManager`: API authentication and content fetching
   - Parallel download management with progress tracking
   - Token persistence and session management
   - Retry logic for network operations

4. **`eldersvr_cli/utils/`**: Utility modules
   - `logger.py`: Centralized logging configuration
   - `progress.py`: Progress bars and deployment summaries
   - Classes: `TransferProgress`, `DownloadProgressTable`

5. **`eldersvr_cli/config/`**: Configuration management
   - Default and custom configuration loading
   - Config file locations: `./eldersvr_config.json`, `~/.eldersvr/config.json`

### Key Workflows

**Authentication Flow**:
1. ContentManager authenticates with backend API
2. Stores auth token in `~/.eldersvr_auth_token`
3. Fetches user and company information

**Deployment Flow**:
1. ADBManager detects and selects master/slave devices
2. ContentManager fetches content metadata from API
3. Downloads videos (both qualities) and images with parallel processing
4. Transfers quality-specific content to devices (master: low-res, slave: high-res)
5. Handles file conflicts interactively (skip/override prompts)

**File Conflict Resolution**:
- During transfers, existing files trigger interactive prompts
- Options: skip, skip all, override, override all, cancel
- State tracked in `EldersVRCLI._conflict_action_all`

### Configuration Structure
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

### Important Patterns

1. **Quality-Based Content Separation**: 
   - Master devices receive `lowres_*` video files
   - Slave devices receive `highres_*` video files
   - Both receive JSON metadata and images

2. **CLI-Only Security**: 
   - `CLIAccessControl` decorator restricts operations
   - Transfer, sync, and deploy are CLI-only operations

3. **Progress Tracking**: 
   - Real-time progress bars for file transfers
   - Parallel download progress tables
   - Deployment summaries with success/failure counts

4. **Error Handling**: 
   - Retry mechanisms for network operations
   - Fallback paths for different Android storage configurations
   - Graceful degradation with informative error messages