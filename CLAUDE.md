# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EldersVR CLI is an ADB onboarding tool for deploying VR content to Android devices. It authenticates with the EldersVR backend, fetches video/image content, and transfers it to paired master (phone) and slave (VR headset) devices via ADB.

## Development Commands

### Setup and Installation
```bash
# Setup development environment
make setup-dev

# Install dependencies only
make install

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy
```

### Testing
```bash
# Run tests
make test
python -m pytest tests/ -v

# Run tests with coverage
make test-coverage
python -m pytest tests/ --cov=eldersvr_cli --cov-report=html --cov-report=term

# Run single test file
python -m pytest tests/test_cli.py -v
```

### Code Quality
```bash
# Lint code
make lint
python -m flake8 eldersvr_cli/ tests/

# Format code
make format  
python -m black eldersvr_cli/ tests/

# Type checking
make type-check
python -m mypy eldersvr_cli/
```

### Running the CLI
```bash
# Run from source (after make install)
eldersvr-onboard --help

# Or run directly
python -m eldersvr_cli.cli --help

# Quick commands
make run-list    # List devices
make run-auth    # Authenticate
make run-deploy  # Full deployment
```

## Architecture Overview

### Core Components

**CLI Layer (`eldersvr_cli/cli.py`)**
- Main CLI entry point with command parsing
- Orchestrates authentication, data fetching, and device operations
- Implements CLI-only security restrictions for deployment operations

**ADB Manager (`eldersvr_cli/core/adb_manager.py`)**
- Handles all Android Debug Bridge operations
- Manages device detection, storage verification, and file transfers
- Implements CLI-only access controls for sensitive operations

**Content Manager (`eldersvr_cli/core/content_manager.py`)**
- Handles backend API authentication and data fetching
- Downloads video files, images, and metadata from EldersVR API
- Generates `new_data.json` manifest for mobile apps

**Configuration System (`eldersvr_cli/config/`)**
- Loads configuration from `eldersvr_config.json` or uses defaults
- Manages API endpoints, device paths, and authentication credentials

### Security Model

**CLI-Only Operations**: The following operations are restricted to CLI usage only and cannot be performed through mobile apps:
- `transfer` - Moving content to devices  
- `deploy` - Complete deployment pipeline
- `sync` - Synchronizing content with backend

This is enforced through the `CLIAccessControl` class in `adb_manager.py`.

### Device Architecture

**Master Device (Android Phone)**:
- Receives: JSON metadata (`new_data.json`) + credentials (`credential.json`)  
- Purpose: Content browsing and selection interface
- Path: `/storage/emulated/0/Download/EldersVR/`

**Slave Device (VR Headset)**:
- Receives: JSON metadata + all videos + all images
- Purpose: Content playback and VR experience
- Paths: `/storage/emulated/0/Download/EldersVR/{Video/,Image/,new_data.json}`

## Configuration

The CLI loads configuration from:
1. `./eldersvr_config.json` (local override)
2. `~/.eldersvr/config.json` (user config)  
3. `eldersvr_cli/config/default_config.json` (defaults)

Key configuration sections:
- `backend`: API URLs and endpoints
- `paths`: Local download and device storage paths
- `devices`: Master/slave device serial numbers
- `auth`: Default authentication credentials

## Data Flow

1. **Authentication** (`auth`) → Backend login + token storage
2. **Data Fetching** (`fetch-data`) → Retrieve tags/films + generate `new_data.json`
3. **Download** (`download-videos`) → Download all video/image assets locally
4. **Device Selection** (`select-devices`) → Configure master/slave device pairs
5. **Transfer** (`transfer`) → Push content to devices via ADB
6. **Verification** (`verify --deployment`) → Confirm successful deployment

## Testing Strategy

Tests are located in `tests/` and use unittest framework. Key test areas:
- Configuration loading and validation
- ADB manager device operations (mocked)
- Content manager API operations (mocked) 
- JSON data generation and validation

## Common Development Tasks

**Add new CLI command**:
1. Add parser in `cli.py` `run()` method
2. Implement command handler method `cmd_<command>`
3. Add to `command_map` routing
4. Add tests in `tests/test_cli.py`

**Modify device transfer logic**:
- Edit `_transfer_to_master()` or `_transfer_to_slave()` in `cli.py`
- Update corresponding ADB manager methods in `adb_manager.py`
- Test with `make run-deploy` on connected test devices

**Change API integration**:
- Modify methods in `content_manager.py`
- Update default API URLs in `config/default_config.json`
- Add appropriate error handling and logging