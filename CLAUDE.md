# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EldersVR CLI is an ADB onboarding tool for deploying VR content to Android devices. The tool authenticates with the EldersVR backend, downloads content, and transfers it to Android devices via ADB.

## Common Development Commands

### Environment Setup
```bash
# Setup development environment (includes venv, dependencies, and package install)
make setup-dev

# Manual setup (alternative)
make install-dev
source venv/bin/activate
```

### Development Tasks
```bash
# Run tests
make test

# Run tests with coverage
make test-coverage

# Lint code
make lint

# Format code
make format

# Type check
make type-check

# Run single test file
python -m pytest tests/test_specific.py -v
```

### CLI Operations
```bash
# Check ADB connectivity
make check-adb
# Or directly: adb devices

# Run authentication
make run-auth

# List connected devices  
make run-list

# List directories on configured devices
make run-list-dirs

# Compare directories between master and slave
make run-compare-dirs

# Run complete deployment
make run-deploy

# Run deployment verification
make run-verify

# Demo sequence
make demo
```

### Package Management
```bash
# Build distribution packages
make build

# Install built package
make install-package

# Uninstall package
make uninstall

# Clean build artifacts
make clean

# Clean downloaded content
make clean-downloads
```

## Code Architecture

### Core Components

#### CLI Entry Point (`eldersvr_cli/cli.py`)
- `EldersVRCLI` class: Main application controller
- Command routing and argument parsing
- Configuration management with fallbacks and validation
- Complete deployment pipeline orchestration

#### ADB Manager (`eldersvr_cli/core/adb_manager.py`)
- `ADBManager` class: Handles all ADB device operations
- Security controls via `CLIAccessControl` decorator for CLI-only operations
- Device discovery, storage verification, and file transfers
- Root access detection and fallback path handling
- Transfer progress tracking with callbacks

#### Content Manager (`eldersvr_cli/core/content_manager.py`) 
- `ContentManager` class: Backend API operations and content downloads
- Authentication with token storage
- Parallel/sequential download strategies with progress tables
- Content validation and data transformation
- Retry logic and error handling

#### Utilities (`eldersvr_cli/utils/`)
- `logger.py`: Structured logging setup
- `progress.py`: Transfer progress tracking and display tables

### Configuration System

- Default configuration embedded in code
- Custom config via `eldersvr_config.json` in working directory
- Hierarchical config loading: local → user home → system-wide
- Deep merge with defaults ensures all required keys exist
- Validation with detailed error reporting

### Security Model

CLI-only operations (protected by `@CLIAccessControl.require_cli_access`):
- `transfer` - Device content transfers  
- `sync` - Backend synchronization
- `deploy` - Complete deployment pipeline

### Device Architecture

**Master Device (Android Phone):**
- Content: JSON metadata + credential.json + low-res videos + images
- Path: `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/`
- Video Quality: Low-res only (files with `lowres_*` prefix)

**Slave Device (VR Headset):**  
- Content: JSON metadata + high-res videos + images
- Paths:
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/new_data.json`
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/Video/*.mp4` (high-res only)
  - `/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR/Image/*`
- Video Quality: High-res only (files with `highres_*` prefix)

### Data Flow

1. Authenticate with EldersVR backend API
2. Fetch tags and films metadata
3. Generate `new_data.json` in mobile app format
4. Download all assets (videos, thumbnails, tag images)
5. Transfer content to configured devices via ADB
6. Verify deployment success

## Development Notes

### Dependencies
- `requests>=2.28.0` - HTTP client for backend API
- `urllib3>=1.26.0` - URL handling utilities
- ADB must be installed and in PATH

### Entry Point
- Console script: `eldersvr-onboard` → `eldersvr_cli.cli:main`
- Direct execution: `python -m eldersvr_cli.cli`

### Testing
- Test files in `tests/` directory
- Use pytest for running tests
- Mock ADB commands for testing device operations

### Error Handling
- Comprehensive error handling with detailed logging
- Graceful fallbacks for storage paths and permissions
- Retry logic for network operations and file transfers