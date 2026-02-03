#!/usr/bin/env python3
"""
EldersVR CLI - ADB Onboarding Tool
Main CLI entry point with command handling
"""

import argparse
import sys
import os
import json
import glob
from typing import Dict, Any, Optional, List

from .core import ADBManager, ContentManager
from .utils import setup_logger, get_logger, TransferProgress, print_deployment_summary


class EldersVRCLI:
    """Main CLI application class"""

    def __init__(self):
        self.config: Optional[Dict[str, Any]] = None
        self.adb_manager: Optional[ADBManager] = None
        self.content_manager: Optional[ContentManager] = None
        self.logger = setup_logger('eldersvr-cli')
        # File conflict handling state
        self._conflict_action_all = None  # 'skip_all', 'override_all', or None

    def load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from file with enhanced validation and logging"""
        self.logger.info("Starting configuration loading process...")

        if config_path is None:
            # Look for config in common locations
            config_locations = [
                './eldersvr_config.json',
                '~/.eldersvr/config.json',
                '/etc/eldersvr/config.json'
            ]

            self.logger.info("Searching for configuration file in standard locations:")
            for location in config_locations:
                self.logger.debug(f"  Checking: {location}")
                expanded_path = os.path.expanduser(location)
                if os.path.exists(expanded_path):
                    config_path = expanded_path
                    self.logger.info(f"  ✅ Found configuration file: {expanded_path}")
                    break
                else:
                    self.logger.debug(f"  ❌ Not found: {expanded_path}")

        if config_path and os.path.exists(config_path):
            self.logger.info(f"Attempting to load configuration from: {config_path}")

            # Verify file permissions before loading
            if not self._verify_config_file_permissions(config_path):
                self.logger.error(f"Configuration file permission check failed: {config_path}")
                return self._fallback_to_default_config()

            try:
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
                    self.logger.info(f"✅ Successfully loaded configuration from {config_path}")

                    # Merge with default config to ensure all required keys exist
                    self.config = self._merge_with_default_config(loaded_config)

                    # Validate the loaded configuration
                    validation_issues = self._validate_config(self.config)
                    if validation_issues:
                        self.logger.warning("Configuration validation issues found:")
                        for issue in validation_issues:
                            self.logger.warning(f"  - {issue}")

                    self.logger.info("Configuration summary:")
                    self.logger.info(f"  API URL: {self.config['backend']['api_url']}")
                    self.logger.info(f"  Device path: {self.config['paths']['device_path']}")
                    self.logger.info(f"  Local downloads: {self.config['paths']['local_downloads']}")

                    self._initialize_managers()
                    return self.config

            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Invalid JSON in config file {config_path}: {e}")
                return self._fallback_to_default_config()
            except IOError as e:
                self.logger.error(f"❌ Failed to read config file {config_path}: {e}")
                return self._fallback_to_default_config()
        else:
            if config_path:
                self.logger.warning(f"Configuration file not found: {config_path}")
            else:
                self.logger.info("No configuration file found in standard locations")
            return self._fallback_to_default_config()

    def _verify_config_file_permissions(self, config_path: str) -> bool:
        """Verify that configuration file can be read and written"""
        try:
            # Test read permissions
            if not os.access(config_path, os.R_OK):
                self.logger.error(f"❌ No read permission for config file: {config_path}")
                return False

            self.logger.debug(f"✅ Read permission verified for: {config_path}")

            # Test write permissions (for potential updates)
            if not os.access(config_path, os.W_OK):
                self.logger.warning(f"⚠️ No write permission for config file: {config_path}")
                self.logger.warning("Configuration updates will not be possible")
                # Still return True as read-only config is acceptable
            else:
                self.logger.debug(f"✅ Write permission verified for: {config_path}")

            # Check file size (avoid loading extremely large files)
            file_size = os.path.getsize(config_path)
            if file_size > 1024 * 1024:  # 1MB limit
                self.logger.error(f"❌ Configuration file too large ({file_size} bytes): {config_path}")
                return False

            self.logger.debug(f"✅ File size check passed ({file_size} bytes)")
            return True

        except OSError as e:
            self.logger.error(f"❌ Error checking config file permissions: {e}")
            return False

    def _fallback_to_default_config(self) -> Dict[str, Any]:
        """Fallback to default configuration with logging"""
        self.logger.info("🔄 Falling back to default configuration")
        self.config = self._get_default_config()

        self.logger.info("Default configuration loaded:")
        self.logger.info(f"  API URL: {self.config['backend']['api_url']}")
        self.logger.info(f"  Device path: {self.config['paths']['device_path']}")
        self.logger.info(f"  Local downloads: {self.config['paths']['local_downloads']}")

        self._initialize_managers()
        return self.config

    def _merge_with_default_config(self, loaded_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge loaded config with default to ensure all required keys exist"""
        default_config = self._get_default_config()

        # Deep merge - loaded config overrides default
        def deep_merge(default: dict, loaded: dict) -> dict:
            result = default.copy()
            for key, value in loaded.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        merged = deep_merge(default_config, loaded_config)
        self.logger.debug("✅ Configuration merged with defaults")
        return merged

    def _validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Required sections
        required_sections = ['backend', 'paths', 'devices', 'auth']
        for section in required_sections:
            if section not in config:
                issues.append(f"Missing required section: {section}")

        # Backend validation
        if 'backend' in config:
            required_backend_keys = ['api_url', 'auth_endpoint', 'tags_endpoint', 'films_endpoint']
            for key in required_backend_keys:
                if key not in config['backend']:
                    issues.append(f"Missing required backend key: {key}")

            # Validate api_url format
            api_url = config['backend'].get('api_url', '')
            if api_url and not api_url.startswith(('http://', 'https://')):
                issues.append(f"Invalid api_url format: must start with http:// or https://")

            # Validate endpoints start with /
            for ep_key in ['auth_endpoint', 'tags_endpoint', 'films_endpoint']:
                ep_val = config['backend'].get(ep_key, '')
                if ep_val and not ep_val.startswith('/'):
                    issues.append(f"Invalid {ep_key}: must start with /")

        # Paths validation
        if 'paths' in config:
            required_path_keys = ['local_downloads', 'device_path', 'json_filename']
            for key in required_path_keys:
                if key not in config['paths']:
                    issues.append(f"Missing required paths key: {key}")

            if not config['paths'].get('device_path'):
                issues.append("device_path must not be empty")

        # Auth validation
        if 'auth' in config:
            has_username = bool(config['auth'].get('username'))
            has_email = bool(config['auth'].get('email'))
            if not has_username and not has_email:
                issues.append("Auth requires at least one of: username or email")
            if not config['auth'].get('password'):
                issues.append("Missing or empty auth password")

        # Download settings validation
        if 'download' in config:
            dl = config['download']
            if dl.get('max_concurrent_downloads') is not None and dl['max_concurrent_downloads'] < 1:
                issues.append("max_concurrent_downloads must be >= 1")
            if dl.get('timeout') is not None and dl['timeout'] < 1:
                issues.append("download timeout must be >= 1")
            if dl.get('retry_attempts') is not None and dl['retry_attempts'] < 0:
                issues.append("retry_attempts must be >= 0")

        return issues

    def _preflight_check(self, checks: List[str]) -> bool:
        """Run preflight validation checks before a command.

        Args:
            checks: List of check names to run. Options:
                'config' - Validate configuration completeness and values
                'api'    - Test API connectivity
                'auth'   - Verify auth token is valid (includes api check)
                'data'   - Validate local new_data.json exists and is valid
                'devices'- Verify configured devices are connected

        Returns:
            True if all checks passed, False otherwise.
        """
        if not self.config:
            self.load_config()

        all_passed = True
        self.logger.info("Running preflight checks...")

        # Config check
        if 'config' in checks:
            config_issues = self._validate_config(self.config)
            if config_issues:
                self.logger.error("[FAIL] Configuration validation:")
                for issue in config_issues:
                    self.logger.error(f"       - {issue}")
                all_passed = False
            else:
                self.logger.info("[PASS] Configuration valid")

        # API connectivity check
        if 'api' in checks or 'auth' in checks:
            if not self.content_manager:
                self.content_manager = ContentManager(self.config)
            reachable, msg = self.content_manager.check_api_connectivity()
            if not reachable:
                self.logger.error(f"[FAIL] {msg}")
                all_passed = False
                # If API is unreachable, skip auth check since it depends on API
                if 'auth' in checks:
                    self.logger.error("[SKIP] Auth validation skipped (API unreachable)")
                return all_passed
            else:
                self.logger.info(f"[PASS] {msg}")

        # Auth token check
        if 'auth' in checks:
            if not self.content_manager:
                self.content_manager = ContentManager(self.config)
            valid, msg = self.content_manager.validate_token()
            if not valid:
                self.logger.error(f"[FAIL] {msg}")
                all_passed = False
            else:
                self.logger.info(f"[PASS] {msg}")

        # Local data check
        if 'data' in checks:
            json_file = os.path.join(
                self.config['paths']['local_downloads'],
                self.config['paths']['json_filename']
            )
            if not os.path.exists(json_file):
                self.logger.error(f"[FAIL] {json_file} not found - run 'fetch-data' first")
                all_passed = False
            else:
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    if not self.content_manager:
                        self.content_manager = ContentManager(self.config)
                    issues = self.content_manager.validate_json_data(data)
                    if issues:
                        self.logger.error("[FAIL] Data validation issues:")
                        for issue in issues:
                            self.logger.error(f"       - {issue}")
                        all_passed = False
                    else:
                        self.logger.info(f"[PASS] {json_file} is valid")
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.error(f"[FAIL] Cannot read {json_file}: {e}")
                    all_passed = False

        # Device connectivity check
        if 'devices' in checks:
            self._ensure_managers_initialized()
            master = self.config['devices'].get('master_serial', '')
            slave = self.config['devices'].get('slave_serial', '')

            if not master and not slave:
                self.logger.error("[FAIL] No devices configured - run 'select-devices' first")
                all_passed = False
            else:
                try:
                    connected = self.adb_manager.get_connected_devices()
                    connected_serials = [d['serial'] for d in connected]

                    if master:
                        if master in connected_serials:
                            self.logger.info(f"[PASS] Master device {master} connected")
                        else:
                            self.logger.error(f"[FAIL] Master device {master} not connected")
                            all_passed = False
                    if slave:
                        if slave in connected_serials:
                            self.logger.info(f"[PASS] Slave device {slave} connected")
                        else:
                            self.logger.error(f"[FAIL] Slave device {slave} not connected")
                            all_passed = False
                except Exception as e:
                    self.logger.error(f"[FAIL] Device check failed: {e}")
                    all_passed = False

        if all_passed:
            self.logger.info("All preflight checks passed")
        else:
            self.logger.error("Preflight checks failed - resolve issues before proceeding")

        return all_passed

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
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
            "devices": {
                "master_serial": "",
                "slave_serial": ""
            },
            "auth": {
                "username": "",
                "email": "clionboarding@eldervr.com",
                "password": "clionboarding@eldervr.com"
            }
        }

    def _initialize_managers(self):
        """Initialize managers with configuration"""
        if self.config:
            device_path = self.config.get("paths", {}).get("device_path", "/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR")
            self.adb_manager = ADBManager(device_path)

    def _ensure_managers_initialized(self):
        """Ensure managers are initialized with config"""
        if not self.config:
            self.load_config()
        if not self.adb_manager:
            self._initialize_managers()

    def cmd_auth(self, args) -> int:
        """Handle authentication command"""
        if not self.config:
            self.load_config()

        # Preflight: validate config and API connectivity before auth attempt
        if not self._preflight_check(['config', 'api']):
            return 1

        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        username = getattr(args, 'username', None) or self.config['auth'].get('username', '')
        email = getattr(args, 'email', None) or self.config['auth'].get('email', '')
        password = args.password or self.config['auth']['password']

        # User should fill just one: username or email. Prioritize username.
        if username:
            email = ''
        elif email:
            username = ''

        if not username and not email:
            self.logger.error("Either username or email is required for authentication")
            return 1

        if not password:
            self.logger.error("Password is required for authentication")
            return 1

        identifier = username or email
        self.logger.info(f"Authenticating with {identifier}...")

        if self.content_manager.authenticate(password, username=username, email=email):
            user_info = self.content_manager.get_user_info()
            company_info = self.content_manager.get_company_info()

            self.logger.info("Authentication successful!")
            self.logger.info(f"User: {user_info.get('name', 'Unknown')} ({user_info.get('email', 'Unknown')})")
            self.logger.info(f"Company: {company_info.get('name', 'Unknown')}")

            # Create credential.json for master device transfer
            self._create_credential_json(password, username=username, email=email)

            return 0
        else:
            self.logger.error("Authentication failed")
            return 1

    def cmd_logout(self, args) -> int:
        """Handle logout command"""
        if not self.config:
            self.load_config()

        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        self.content_manager.logout()
        self.logger.info("Logged out successfully")
        return 0

    def cmd_list_devices(self, args) -> int:
        """Handle list devices command"""
        self._ensure_managers_initialized()
        try:
            devices = self.adb_manager.get_connected_devices()

            if not devices:
                self.logger.warning("No ADB devices found")
                return 1

            print("\nAvailable ADB Devices:")
            for i, device in enumerate(devices, 1):
                model_info = f"{device['model']} ({device['product']})" if device['model'] != 'Unknown' else device['product']
                print(f"{i}. {device['serial']} - {model_info} [{device['status']}]")

            return 0

        except Exception as e:
            self.logger.error(f"Failed to list devices: {e}")
            return 1

    def cmd_verify(self, args) -> int:
        """Handle verify command"""
        if args.device:
            return self._verify_single_device(args.device)
        elif args.deployment:
            return self._verify_deployment()
        else:
            self.logger.error("Please specify --device <serial> or --deployment")
            return 1

    def _verify_single_device(self, serial: str) -> int:
        """Verify storage access for a single device"""
        self._ensure_managers_initialized()
        self.logger.info(f"Verifying device {serial}...")

        try:
            devices = self.adb_manager.get_connected_devices()
            device_found = any(d['serial'] == serial for d in devices)

            if not device_found:
                self.logger.error(f"Device {serial} not found")
                return 1

            # Check storage access
            if not self.adb_manager.verify_storage_access(serial):
                self.logger.info("EldersVR directory not accessible, creating...")
                if not self.adb_manager.create_eldersvr_structure(serial):
                    self.logger.error("Failed to create EldersVR directory structure")
                    return 1

            # Test write permissions
            if not self.adb_manager.test_write_permissions(serial):
                self.logger.error("No write permissions to EldersVR directory")
                return 1

            # Get storage info
            storage_info = self.adb_manager.get_device_storage_info(serial)
            if storage_info:
                self.logger.info(f"Storage info: {storage_info}")

            self.logger.info("Device verification successful!")
            return 0

        except Exception as e:
            self.logger.error(f"Device verification failed: {e}")
            return 1

    def _verify_deployment(self) -> int:
        """Verify deployment on configured devices"""
        if not self.config:
            self.load_config()

        devices_to_check = []
        if self.config['devices']['master_serial']:
            devices_to_check.append(('master', self.config['devices']['master_serial']))
        if self.config['devices']['slave_serial']:
            devices_to_check.append(('slave', self.config['devices']['slave_serial']))

        if not devices_to_check:
            self.logger.error("No devices configured for verification")
            return 1

        all_verified = True

        for device_type, serial in devices_to_check:
            self.logger.info(f"Verifying {device_type} device {serial}...")
            verification = self.adb_manager.verify_transfer(serial)

            print(f"\n{device_type.upper()} DEVICE ({serial}):")
            print(f"  JSON file: {'✅' if verification['json_exists'] else '❌'}")
            print(f"  Video files: {verification['video_count']}")
            print(f"  Image files: {verification['image_count']}")

            if verification['storage_info']:
                print(f"  Storage used: {verification['storage_info'].get('used_space', 'Unknown')}")

            if not verification['json_exists']:
                all_verified = False

        return 0 if all_verified else 1

    def cmd_list_directories(self, args) -> int:
        """Handle list directories command"""
        self._ensure_managers_initialized()

        try:
            if args.compare:
                # Compare master and slave directories
                master_serial = self.config['devices']['master_serial']
                slave_serial = self.config['devices']['slave_serial']

                if not master_serial or not slave_serial:
                    self.logger.error("Both master and slave devices must be configured for comparison")
                    self.logger.info("Use 'select-devices' command to configure devices first")
                    return 1

                self.logger.info(f"Comparing directories between master ({master_serial}) and slave ({slave_serial})")
                comparison = self.adb_manager.compare_devices_directories(master_serial, slave_serial)

                self._print_directory_comparison(comparison)

            elif args.device:
                # List specific device directory
                self.logger.info(f"Listing directories on device {args.device}")
                directory_info = self.adb_manager.list_directory_contents(args.device, detailed=args.detailed)

                self._print_device_directory_info(directory_info)

            else:
                # List both master and slave if configured
                devices_to_check = []

                master_serial = self.config['devices']['master_serial']
                slave_serial = self.config['devices']['slave_serial']

                if master_serial:
                    devices_to_check.append(('MASTER', master_serial))
                if slave_serial:
                    devices_to_check.append(('SLAVE', slave_serial))

                if not devices_to_check:
                    self.logger.error("No devices configured. Use 'select-devices' command first.")
                    return 1

                for device_type, serial in devices_to_check:
                    print(f"\n{'='*60}")
                    print(f"{device_type} DEVICE: {serial}")
                    print(f"{'='*60}")

                    directory_info = self.adb_manager.list_directory_contents(serial, detailed=args.detailed)
                    self._print_device_directory_info(directory_info)

            return 0

        except Exception as e:
            self.logger.error(f"Failed to list directories: {e}")
            return 1

    def _print_device_directory_info(self, directory_info: Dict[str, Any]):
        """Print formatted directory information for a single device"""
        print(f"Device: {directory_info['device_serial']}")
        print(f"Base Path: {directory_info['base_path']}")

        if directory_info['errors']:
            print("\n⚠️  ERRORS:")
            for error in directory_info['errors']:
                print(f"   {error}")

        # Print storage info if available
        if 'storage_info' in directory_info:
            storage = directory_info['storage_info']
            print(f"\n💾 STORAGE INFO:")
            if 'total_space' in storage:
                print(f"   Total Space: {storage.get('total_space', 'Unknown')}")
            if 'available_space' in storage:
                print(f"   Available: {storage.get('available_space', 'Unknown')}")
            if 'used_space' in storage:
                print(f"   EldersVR Used: {storage.get('used_space', 'Unknown')}")

        print(f"\n📁 DIRECTORIES:")
        print(f"   Total EldersVR Size: {directory_info['total_size_formatted']}")

        for dir_name, dir_info in directory_info['directories'].items():
            status = "✅" if dir_info['exists'] else "❌"
            print(f"\n   {status} {dir_name.upper()} ({dir_info['path']})")

            if dir_info['exists']:
                print(f"      Files: {dir_info['file_count']}")
                print(f"      Size: {dir_info.get('total_size_formatted', '0B')}")

                if dir_info['files']:
                    print(f"      Contents:")
                    # Show first 10 files
                    for i, file_info in enumerate(dir_info['files'][:10]):
                        size_info = f" ({file_info.get('size_formatted', 'Unknown')})" if file_info.get('size_formatted') else ""
                        print(f"        {i+1:2d}. {file_info['name']}{size_info}")

                    if len(dir_info['files']) > 10:
                        print(f"        ... and {len(dir_info['files']) - 10} more files")
                else:
                    print(f"      (empty directory)")

        print()

    def _print_directory_comparison(self, comparison: Dict[str, Any]):
        """Print formatted directory comparison between master and slave"""
        print("\n📊 DIRECTORY COMPARISON")
        print("=" * 60)

        master = comparison['master']
        slave = comparison['slave']
        comp = comparison['comparison']

        print(f"Master Device: {master['device_serial']}")
        print(f"Slave Device:  {slave['device_serial']}")

        # Print errors if any
        all_errors = master['errors'] + slave['errors']
        if all_errors:
            print("\n⚠️  ERRORS:")
            for error in all_errors:
                print(f"   {error}")

        # Compare each directory type
        for dir_type in ['root', 'videos', 'images']:
            dir_comp = comp[dir_type]

            print(f"\n📁 {dir_type.upper()} DIRECTORY COMPARISON:")
            print(f"   Master files: {dir_comp['master_count']} ({self._format_file_size(dir_comp['master_total_size'])})")
            print(f"   Slave files:  {dir_comp['slave_count']} ({self._format_file_size(dir_comp['slave_total_size'])})")

            # Files only on master
            if dir_comp['master_only']:
                print(f"\n   📱 MASTER ONLY ({len(dir_comp['master_only'])} files):")
                for file_info in dir_comp['master_only'][:5]:
                    size_info = f" ({file_info.get('size_formatted', 'Unknown')})" if file_info.get('size_formatted') else ""
                    print(f"      • {file_info['name']}{size_info}")
                if len(dir_comp['master_only']) > 5:
                    print(f"      ... and {len(dir_comp['master_only']) - 5} more files")

            # Files only on slave
            if dir_comp['slave_only']:
                print(f"\n   🥽 SLAVE ONLY ({len(dir_comp['slave_only'])} files):")
                for file_info in dir_comp['slave_only'][:5]:
                    size_info = f" ({file_info.get('size_formatted', 'Unknown')})" if file_info.get('size_formatted') else ""
                    print(f"      • {file_info['name']}{size_info}")
                if len(dir_comp['slave_only']) > 5:
                    print(f"      ... and {len(dir_comp['slave_only']) - 5} more files")

            # Common files
            if dir_comp['common_files']:
                print(f"\n   🤝 COMMON FILES ({len(dir_comp['common_files'])} files):")
                for file_info in dir_comp['common_files'][:3]:
                    print(f"      • {file_info['name']} (Master: {file_info.get('master_size_formatted', 'Unknown')}, Slave: {file_info.get('slave_size_formatted', 'Unknown')})")
                if len(dir_comp['common_files']) > 3:
                    print(f"      ... and {len(dir_comp['common_files']) - 3} more files")

            # Size differences
            if dir_comp['size_differences']:
                print(f"\n   ⚠️  SIZE DIFFERENCES ({len(dir_comp['size_differences'])} files):")
                for file_info in dir_comp['size_differences']:
                    print(f"      • {file_info['name']}: Master {file_info.get('master_size_formatted', 'Unknown')} ≠ Slave {file_info.get('slave_size_formatted', 'Unknown')}")

        print()

    def _format_file_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"

    def cmd_fetch_data(self, args) -> int:
        """Handle fetch data command (tags + films)"""
        if not self.config:
            self.load_config()

        # Preflight: validate config and auth token (which implies API connectivity)
        if not self._preflight_check(['config', 'auth']):
            return 1

        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        self.logger.info("Fetching tags from backend...")
        tags_data = self.content_manager.fetch_tags()

        if not tags_data:
            self.logger.error("Failed to fetch tags")
            return 1

        self.logger.info(f"Retrieved {len(tags_data)} tags")

        self.logger.info("Fetching films from backend...")
        films_data = self.content_manager.fetch_films()

        if not films_data:
            self.logger.error("Failed to fetch films")
            return 1

        self.logger.info(f"Retrieved {len(films_data.get('films', []))} films")

        # Generate new_data.json
        self.logger.info("Generating new_data.json...")
        try:
            data = self.content_manager.generate_new_data_json(films_data, tags_data)

            # Validate generated data
            issues = self.content_manager.validate_json_data(data)
            if issues:
                self.logger.warning(f"Data validation issues: {', '.join(issues)}")

            # Get download summary
            summary = self.content_manager.get_download_summary(data)
            self.logger.info(f"Generated manifest with {summary['estimated_files']} total assets to download")

            return 0

        except Exception as e:
            self.logger.error(f"Failed to generate new_data.json: {e}")
            return 1

    def cmd_download_videos(self, args) -> int:
        """Handle download videos command"""
        if not self.config:
            self.load_config()

        # Preflight: validate config and local data
        if not self._preflight_check(['config', 'data']):
            return 1

        json_file = f"{self.config['paths']['local_downloads']}/new_data.json"

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to read new_data.json: {e}")
            return 1

        # Check if images-only mode is requested
        images_only = getattr(args, 'images_only', False)

        # Determine download mode and apply overrides
        parallel_mode = not args.sequential if hasattr(args, 'sequential') else True

        # Apply configuration overrides from command line arguments
        if 'download' not in self.config:
            self.config['download'] = {}

        if hasattr(args, 'max_workers') and args.max_workers:
            self.config['download']['max_concurrent_downloads'] = args.max_workers
            self.logger.info(f"Using {args.max_workers} concurrent downloads")

        if hasattr(args, 'timeout') and args.timeout:
            self.config['download']['timeout'] = args.timeout
            self.logger.info(f"Using {args.timeout}s timeout")

        if hasattr(args, 'retry_attempts') and args.retry_attempts:
            self.config['download']['retry_attempts'] = args.retry_attempts
            self.logger.info(f"Using {args.retry_attempts} retry attempts")

        mode_str = "parallel" if parallel_mode else "sequential"

        # Initialize content manager for downloads
        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        try:
            # Get display limit from command line arguments
            max_display_files = getattr(args, 'show_files', 3)

            if images_only:
                self.logger.info(f"Starting {mode_str} download of images and thumbnails only...")
                download_stats = self.content_manager.download_images_only(data, parallel=parallel_mode, max_display_files=max_display_files)
            else:
                asset_type = "all assets"
                if hasattr(args, 'quality') and args.quality != 'both':
                    asset_type = f"{args.quality}-res videos and images"
                self.logger.info(f"Starting {mode_str} download of {asset_type}...")
                download_stats = self.content_manager.download_all_assets(data, parallel=parallel_mode, max_display_files=max_display_files, quality=getattr(args, 'quality', 'both'))

            self.logger.info("Download completed!")
            if not images_only:
                self.logger.info(f"High-res videos: {download_stats.get('videos_high', 0)}")
                self.logger.info(f"Low-res videos: {download_stats.get('videos_low', 0)}")
            self.logger.info(f"Thumbnails: {download_stats['thumbnails']}")
            self.logger.info(f"Tag images: {download_stats['tag_images']}")
            self.logger.info(f"Total completed: {download_stats['completed_files']}/{download_stats['total_files']}")

            if download_stats['failed_downloads'] > 0:
                self.logger.warning(f"Failed downloads: {download_stats['failed_downloads']}")
                return 1

            return 0

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return 1

    def cmd_select_devices(self, args) -> int:
        """Handle select devices command"""
        if not self.config:
            self.load_config()

        # Update config with selected devices
        if args.master:
            self.config['devices']['master_serial'] = args.master
            self.logger.info(f"Master device set to: {args.master}")

        if args.slave:
            self.config['devices']['slave_serial'] = args.slave
            self.logger.info(f"Slave device set to: {args.slave}")

        # Verify devices are connected
        try:
            connected_devices = self.adb_manager.get_connected_devices()
            connected_serials = [d['serial'] for d in connected_devices]

            if args.master and args.master not in connected_serials:
                self.logger.error(f"Master device {args.master} not connected")
                return 1

            if args.slave and args.slave not in connected_serials:
                self.logger.error(f"Slave device {args.slave} not connected")
                return 1

            self.logger.info("Device selection completed successfully")
            return 0

        except Exception as e:
            self.logger.error(f"Failed to verify device selection: {e}")
            return 1

    def cmd_transfer(self, args) -> int:
        """Handle transfer command (CLI-only)"""
        self._ensure_managers_initialized()

        # Preflight: validate config, local data, and device connectivity
        if not self._preflight_check(['config', 'data', 'devices']):
            return 1

        # Reset conflict action state for this transfer
        self._conflict_action_all = None

        master_serial = self.config['devices']['master_serial']
        slave_serial = self.config['devices']['slave_serial']

        # Initialize progress tracker
        progress = TransferProgress()

        # Only add devices to progress tracker if they will be processed
        if master_serial and not args.slave_only:
            progress.add_device(master_serial, "Master")
        if slave_serial and not args.master_only:
            progress.add_device(slave_serial, "Slave")

        success = True

        try:
            # Transfer to master (JSON + videos + images)
            if master_serial and not args.slave_only:
                self.logger.info("Processing master device transfer...")
                success &= self._transfer_to_master(master_serial, progress, args)
            elif master_serial and args.slave_only:
                self.logger.info("Skipping master device (slave-only mode)")

            # Transfer to slave (JSON + videos + images)
            if slave_serial and not args.master_only:
                self.logger.info("Processing slave device transfer...")
                success &= self._transfer_to_slave(slave_serial, progress, args)
            elif slave_serial and args.master_only:
                self.logger.info("Skipping slave device (master-only mode)")

            # Print final summary
            print_deployment_summary(progress)

            return 0 if success else 1

        except Exception as e:
            self.logger.error(f"Transfer failed: {e}")
            return 1

    def _handle_file_conflict(self, filename: str, local_size: int, remote_size: int, device_type: str) -> str:
        """
        Handle file conflict when file already exists on device.
        Returns: 'skip', 'override', or 'cancel'
        """
        # Debug logging to track when conflicts are triggered
        self.logger.debug(f"File conflict detected for {device_type} device: {filename}")

        # Check if we already have a global action set
        if self._conflict_action_all == 'skip_all':
            return 'skip'
        elif self._conflict_action_all == 'override_all':
            return 'override'

        print(f"\n⚠️  File conflict detected: {filename}")
        print(f"   📱 Device ({device_type}): {self._format_file_size(remote_size)}")
        print(f"   💻 Local: {self._format_file_size(local_size)}")

        while True:
            choice = input("\nChoose action:\n  [s]kip this file\n  [sa] skip all remaining files\n  [o]verride (replace on device)\n  [oa] override all remaining files\n  [c]ancel transfer\nChoice (s/sa/o/oa/c): ").lower().strip()

            if choice in ['s', 'skip']:
                return 'skip'
            elif choice in ['sa', 'skip_all']:
                self._conflict_action_all = 'skip_all'
                return 'skip'
            elif choice in ['o', 'override']:
                return 'override'
            elif choice in ['oa', 'override_all']:
                self._conflict_action_all = 'override_all'
                return 'override'
            elif choice in ['c', 'cancel']:
                return 'cancel'
            else:
                print("Invalid choice. Please enter 's', 'sa', 'o', 'oa', or 'c'.")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _create_credential_json(self, password: str, username: str = '', email: str = '') -> bool:
        """Create credential.json file with authentication data for master device"""
        try:
            # Ensure downloads directory exists
            downloads_dir = self.config['paths']['local_downloads']
            os.makedirs(downloads_dir, exist_ok=True)

            # Get the auth token from content manager
            token = self.content_manager.auth_token

            if not token:
                self.logger.error("No auth token available to create credential.json")
                return False

            # Create credential data - only include the identifier that was used
            credential_data = {"token": token, "password": password}
            if username:
                credential_data["username"] = username
            if email:
                credential_data["email"] = email

            # Write to credential.json
            credential_path = os.path.join(downloads_dir, "credential.json")
            with open(credential_path, 'w') as f:
                json.dump(credential_data, f, indent=2)

            self.logger.info(f"Created credential.json at {credential_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create credential.json: {e}")
            return False

    def _transfer_to_master(self, serial: str, progress: TransferProgress, args) -> bool:
        """Transfer data to master device (low-res videos only)"""
        json_path = f"{self.config['paths']['local_downloads']}/new_data.json"
        videos_dir = f"{self.config['paths']['local_downloads']}/videos"
        images_dir = f"{self.config['paths']['local_downloads']}/images"

        success = True

        self.logger.info(f"Transferring to master device {serial} (low-res videos only)...")

        # Create directory structure
        if not self.adb_manager.create_eldersvr_structure(serial):
            return False

        # Pre-transfer conflict check - get complete file list
        local_files_to_transfer = {}

        # Add JSON files if needed
        if not args.videos_only:
            if os.path.exists(json_path):
                local_files_to_transfer['new_data.json'] = json_path
            credential_path = f"{self.config['paths']['local_downloads']}/credential.json"
            if os.path.exists(credential_path):
                local_files_to_transfer['credential.json'] = credential_path

        # Add video files if needed
        if not args.json_only and os.path.exists(videos_dir):
            low_res_files = [f for f in os.listdir(videos_dir) if f.startswith('lowres_') and f.endswith('.mp4')]
            for filename in low_res_files:
                local_files_to_transfer[filename] = os.path.join(videos_dir, filename)

        # Add image files if needed
        if not args.json_only and os.path.exists(images_dir):
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            for ext in image_extensions:
                for filename in glob.glob(f"{images_dir}/*.{ext}") + glob.glob(f"{images_dir}/*.{ext.upper()}"):
                    basename = os.path.basename(filename)
                    local_files_to_transfer[basename] = filename

        # Check for conflicts with actual device contents
        files_to_skip = set()
        if local_files_to_transfer:
            conflict_check = self.adb_manager.check_transfer_conflicts(serial, local_files_to_transfer, "Master")

            if conflict_check['conflicts']:
                print(f"\n📋 Pre-transfer check for Master device:")
                print(f"   • {len(conflict_check['safe_files'])} new files to transfer")
                print(f"   • {len(conflict_check['conflicts'])} files already exist on device")

                print(f"\n⚠️  Files that already exist on Master device:")
                for conflict in conflict_check['conflicts'][:10]:  # Show first 10
                    print(f"   📱 {conflict['filename']} - Device: {conflict['remote_size_formatted']} | Local: {conflict['local_size_formatted']}")

                if len(conflict_check['conflicts']) > 10:
                    print(f"   ... and {len(conflict_check['conflicts']) - 10} more files")

                while True:
                    choice = input(f"\nChoose action for ALL {len(conflict_check['conflicts'])} conflicting files:\n  [sa] skip all conflicting files\n  [oa] override all conflicting files\n  [c] cancel transfer\nChoice (sa/oa/c): ").lower().strip()

                    if choice in ['sa', 'skip_all']:
                        self._conflict_action_all = 'skip_all'
                        # Add conflicting files to skip list
                        files_to_skip = {conflict['filename'] for conflict in conflict_check['conflicts']}
                        print(f"Will skip {len(conflict_check['conflicts'])} existing files and transfer {len(conflict_check['safe_files'])} new files")
                        break
                    elif choice in ['oa', 'override_all']:
                        self._conflict_action_all = 'override_all'
                        print(f"Will override {len(conflict_check['conflicts'])} existing files and transfer {len(conflict_check['safe_files'])} new files")
                        break
                    elif choice in ['c', 'cancel']:
                        self.logger.info("Transfer cancelled by user")
                        return False
                    else:
                        print("Please enter 'sa' for skip all, 'oa' for override all, or 'c' for cancel")

        # Transfer JSON files (new_data.json and credential.json)
        if not args.videos_only:
            progress.update_json_status(serial, 'in_progress')

            # Transfer new_data.json (skip if user chose skip all)
            json_transferred = True
            if 'new_data.json' in files_to_skip:
                self.logger.info("⏭️  Skipped new_data.json (skip all - already exists on device)")
            else:
                json_transferred = self.adb_manager.push_json(serial, json_path)

            # Transfer credential.json for master device
            credential_path = f"{self.config['paths']['local_downloads']}/credential.json"
            credential_transferred = True
            if os.path.exists(credential_path):
                if 'credential.json' in files_to_skip:
                    self.logger.info("⏭️  Skipped credential.json (skip all - already exists on device)")
                else:
                    credential_transferred = self.adb_manager.push_credential_json(serial, credential_path)
                    if not credential_transferred:
                        self.logger.warning("Failed to transfer credential.json to master device")
            else:
                self.logger.warning("credential.json not found - please run 'auth' command first")

            if json_transferred and credential_transferred:
                file_size = os.path.getsize(json_path) if os.path.exists(json_path) else 0
                progress.update_json_status(serial, 'completed', file_size)
            else:
                progress.update_json_status(serial, 'failed')
                success = False

        # Transfer videos (low-res only for master device)
        if not args.json_only and os.path.exists(videos_dir):
            # Filter for low-res videos only (files with 'lowres_' prefix)
            all_low_res_files = [f for f in os.listdir(videos_dir) if f.startswith('lowres_') and f.endswith('.mp4')]
            # Remove files that should be skipped
            low_res_files = [f for f in all_low_res_files if f not in files_to_skip]

            skipped_count = len(all_low_res_files) - len(low_res_files)
            if skipped_count > 0:
                self.logger.info(f"⏭️  Skipping {skipped_count} video files that already exist on device")

            progress.update_videos_progress(serial, 0, len(low_res_files), 'in_progress')

            self.logger.info(f"Transferring {len(low_res_files)} low-res videos to master device {serial}")

            # Create callback for real-time updates with percentage
            def video_progress_callback(current, total, current_file_progress=0):
                progress.update_videos_progress(serial, current, total, 'in_progress')
                if current_file_progress > 0:
                    print(f"\rTransferring video {current}/{total}: {current_file_progress:.1f}%", end='', flush=True)

            video_success, video_total = self.adb_manager.push_videos_filtered(serial, videos_dir, low_res_files, video_progress_callback, None, files_to_skip)

            if video_success == video_total:
                progress.update_videos_progress(serial, video_success, video_total, 'completed')
                print()  # New line after progress
            else:
                progress.update_videos_progress(serial, video_success, video_total, 'failed')
                print()  # New line after progress
                success = False

        # Transfer images
        if not args.json_only and os.path.exists(images_dir):
            image_files = len([f for f in os.listdir(images_dir)
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            progress.update_images_progress(serial, 0, image_files, 'in_progress')

            # Create callback for real-time updates with percentage
            def image_progress_callback(current, total, current_file_progress=0):
                progress.update_images_progress(serial, current, total, 'in_progress')
                if current_file_progress > 0:
                    print(f"\rTransferring image {current}/{total}: {current_file_progress:.1f}%", end='', flush=True)

            image_success, image_total = self.adb_manager.push_images(serial, images_dir, image_progress_callback, None, files_to_skip)

            if image_success == image_total:
                progress.update_images_progress(serial, image_success, image_total, 'completed')
                print()  # New line after progress
            else:
                progress.update_images_progress(serial, image_success, image_total, 'failed')
                print()  # New line after progress
                success = False

        return success

    def _transfer_to_slave(self, serial: str, progress: TransferProgress, args) -> bool:
        """Transfer data to slave device (high-res videos only)"""
        json_path = f"{self.config['paths']['local_downloads']}/new_data.json"
        videos_dir = f"{self.config['paths']['local_downloads']}/videos"
        images_dir = f"{self.config['paths']['local_downloads']}/images"

        success = True

        self.logger.info(f"Transferring to slave device {serial} (high-res videos only)...")

        # Create directory structure
        if not self.adb_manager.create_eldersvr_structure(serial):
            return False

        # Pre-transfer conflict check - get complete file list
        local_files_to_transfer = {}

        # Add JSON files if needed
        if not args.videos_only:
            if os.path.exists(json_path):
                local_files_to_transfer['new_data.json'] = json_path

        # Add video files if needed
        if not args.json_only and os.path.exists(videos_dir):
            high_res_files = [f for f in os.listdir(videos_dir) if f.startswith('highres_') and f.endswith('.mp4')]
            for filename in high_res_files:
                local_files_to_transfer[filename] = os.path.join(videos_dir, filename)

        # Add image files if needed
        if not args.json_only and os.path.exists(images_dir):
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            for ext in image_extensions:
                for filename in glob.glob(f"{images_dir}/*.{ext}") + glob.glob(f"{images_dir}/*.{ext.upper()}"):
                    basename = os.path.basename(filename)
                    local_files_to_transfer[basename] = filename

        # Check for conflicts with actual device contents
        files_to_skip = set()
        if local_files_to_transfer:
            conflict_check = self.adb_manager.check_transfer_conflicts(serial, local_files_to_transfer, "Slave")

            if conflict_check['conflicts']:
                print(f"\n📋 Pre-transfer check for Slave device:")
                print(f"   • {len(conflict_check['safe_files'])} new files to transfer")
                print(f"   • {len(conflict_check['conflicts'])} files already exist on device")

                print(f"\n⚠️  Files that already exist on Slave device:")
                for conflict in conflict_check['conflicts'][:10]:  # Show first 10
                    print(f"   🥽 {conflict['filename']} - Device: {conflict['remote_size_formatted']} | Local: {conflict['local_size_formatted']}")

                if len(conflict_check['conflicts']) > 10:
                    print(f"   ... and {len(conflict_check['conflicts']) - 10} more files")

                while True:
                    choice = input(f"\nChoose action for ALL {len(conflict_check['conflicts'])} conflicting files:\n  [sa] skip all conflicting files\n  [oa] override all conflicting files\n  [c] cancel transfer\nChoice (sa/oa/c): ").lower().strip()

                    if choice in ['sa', 'skip_all']:
                        self._conflict_action_all = 'skip_all'
                        # Add conflicting files to skip list
                        files_to_skip = {conflict['filename'] for conflict in conflict_check['conflicts']}
                        print(f"Will skip {len(conflict_check['conflicts'])} existing files and transfer {len(conflict_check['safe_files'])} new files")
                        break
                    elif choice in ['oa', 'override_all']:
                        self._conflict_action_all = 'override_all'
                        print(f"Will override {len(conflict_check['conflicts'])} existing files and transfer {len(conflict_check['safe_files'])} new files")
                        break
                    elif choice in ['c', 'cancel']:
                        self.logger.info("Transfer cancelled by user")
                        return False
                    else:
                        print("Please enter 'sa' for skip all, 'oa' for override all, or 'c' for cancel")

        # Transfer JSON
        if not args.videos_only:
            progress.update_json_status(serial, 'in_progress')
            if self.adb_manager.push_json(serial, json_path):
                file_size = os.path.getsize(json_path) if os.path.exists(json_path) else 0
                progress.update_json_status(serial, 'completed', file_size)
            else:
                progress.update_json_status(serial, 'failed')
                success = False

        # Transfer videos (high-res only for slave device)
        if not args.json_only and os.path.exists(videos_dir):
            # Filter for high-res videos only (files with 'highres_' prefix)
            high_res_files = [f for f in os.listdir(videos_dir) if f.startswith('highres_') and f.endswith('.mp4')]
            progress.update_videos_progress(serial, 0, len(high_res_files), 'in_progress')

            self.logger.info(f"Transferring {len(high_res_files)} high-res videos to slave device {serial}")

            # Create callback for real-time updates with percentage
            def video_progress_callback(current, total, current_file_progress=0):
                progress.update_videos_progress(serial, current, total, 'in_progress')
                if current_file_progress > 0:
                    print(f"\rTransferring video {current}/{total}: {current_file_progress:.1f}%", end='', flush=True)

            video_success, video_total = self.adb_manager.push_videos_filtered(serial, videos_dir, high_res_files, video_progress_callback, None, files_to_skip)

            if video_success == video_total:
                progress.update_videos_progress(serial, video_success, video_total, 'completed')
                print()  # New line after progress
            else:
                progress.update_videos_progress(serial, video_success, video_total, 'failed')
                print()  # New line after progress
                success = False

        # Transfer images
        if not args.json_only and os.path.exists(images_dir):
            image_files = len([f for f in os.listdir(images_dir)
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            progress.update_images_progress(serial, 0, image_files, 'in_progress')

            # Create callback for real-time updates with percentage
            def image_progress_callback(current, total, current_file_progress=0):
                progress.update_images_progress(serial, current, total, 'in_progress')
                if current_file_progress > 0:
                    print(f"\rTransferring image {current}/{total}: {current_file_progress:.1f}%", end='', flush=True)

            image_success, image_total = self.adb_manager.push_images(serial, images_dir, image_progress_callback, None, files_to_skip)

            if image_success == image_total:
                progress.update_images_progress(serial, image_success, image_total, 'completed')
                print()  # New line after progress
            else:
                progress.update_images_progress(serial, image_success, image_total, 'failed')
                print()  # New line after progress
                success = False

        return success

    def cmd_deploy(self, args) -> int:
        """Handle complete deployment command (CLI-only)"""
        self.logger.info("Starting complete deployment pipeline...")

        # Step 1: Ensure managers initialized
        self._ensure_managers_initialized()

        # Preflight: validate config, API, and devices before starting pipeline
        preflight_checks = ['config']
        if not args.skip_auth:
            preflight_checks.append('api')
        if self.config['devices'].get('master_serial') or self.config['devices'].get('slave_serial'):
            preflight_checks.append('devices')

        if not self._preflight_check(preflight_checks):
            return 1

        # Step 2: Verify ADB
        if not self.adb_manager.verify_adb_available():
            self.logger.error("ADB not available. Please install ADB and add to PATH.")
            return 1

        # Step 3: Authenticate
        if not args.skip_auth:
            self.content_manager = ContentManager(self.config)
            username = self.config['auth'].get('username', '')
            email = self.config['auth'].get('email', '')
            password = self.config['auth']['password']

            # User should fill just one: username or email. Prioritize username.
            if username:
                email = ''
            elif email:
                username = ''

            if not self.content_manager.authenticate(password, username=username, email=email):
                self.logger.error("Authentication failed")
                return 1

            self.logger.info("Authentication successful")

            # Create credential.json for master device transfer
            self._create_credential_json(password, username=username, email=email)

        # Step 4: Fetch data
        if not args.skip_fetch:
            if not self.content_manager:
                self.logger.error("Not authenticated for data fetching")
                return 1

            # Simulate fetch-data command
            fetch_args = argparse.Namespace()
            if self.cmd_fetch_data(fetch_args) != 0:
                return 1

        # Step 5: Download assets
        if not args.skip_download:
            download_args = argparse.Namespace(quality='both')
            if self.cmd_download_videos(download_args) != 0:
                return 1

        # Step 6: Auto-detect devices if not configured
        if args.auto:
            if not self._auto_detect_devices():
                return 1

        # Step 7: Transfer to devices
        transfer_args = argparse.Namespace(
            master_only=False,
            slave_only=False,
            videos_only=False,
            json_only=False
        )

        if self.cmd_transfer(transfer_args) != 0:
            return 1

        # Step 8: Verify deployment
        verify_args = argparse.Namespace(device=None, deployment=True)
        if self.cmd_verify(verify_args) != 0:
            self.logger.warning("Deployment verification had issues")

        self.logger.info("Complete deployment pipeline finished!")
        return 0

    def _auto_detect_devices(self) -> bool:
        """Auto-detect master and slave devices"""
        try:
            devices = self.adb_manager.get_connected_devices()

            if len(devices) < 2:
                self.logger.error("At least 2 devices required for auto-detection")
                return False

            # Simple heuristic: first device is master, second is slave
            # In production, this could be more sophisticated
            master = devices[0]['serial']
            slave = devices[1]['serial']

            self.config['devices']['master_serial'] = master
            self.config['devices']['slave_serial'] = slave

            self.logger.info(f"Auto-detected master: {master}")
            self.logger.info(f"Auto-detected slave: {slave}")

            return True

        except Exception as e:
            self.logger.error(f"Auto-detection failed: {e}")
            return False

    def run(self) -> int:
        """Main CLI entry point"""
        parser = argparse.ArgumentParser(
            prog='eldersvr-onboard',
            description='EldersVR ADB Onboarding CLI Tool'
        )

        parser.add_argument('--config', help='Configuration file path')
        parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
        parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Auth command
        auth_parser = subparsers.add_parser('auth', help='Authenticate with backend')
        auth_parser.add_argument('--username', help='Username for authentication (alternative to email)')
        auth_parser.add_argument('--email', help='Email for authentication (alternative to username)')
        auth_parser.add_argument('--password', help='Password for authentication')

        # Logout command
        subparsers.add_parser('logout', help='Clear stored authentication')

        # List devices command
        subparsers.add_parser('list-devices', help='List connected ADB devices')

        # Verify command
        verify_parser = subparsers.add_parser('verify', help='Verify device or deployment')
        verify_group = verify_parser.add_mutually_exclusive_group(required=True)
        verify_group.add_argument('--device', help='Verify specific device by serial')
        verify_group.add_argument('--deployment', action='store_true', help='Verify complete deployment')

        # Fetch data command
        subparsers.add_parser('fetch-data', help='Fetch videos and tags from backend')

        # Download videos command
        download_parser = subparsers.add_parser('download-videos', help='Download all video files')
        download_parser.add_argument('--quality', choices=['high', 'low', 'both'],
                                   default='both', help='Video quality to download')
        download_parser.add_argument('--images-only', action='store_true',
                                   help='Download only images and thumbnails (no videos)')
        download_parser.add_argument('--sequential', action='store_true',
                                   help='Use sequential downloads instead of parallel')
        download_parser.add_argument('--max-workers', type=int, metavar='N',
                                   help='Maximum number of concurrent downloads (overrides config)')
        download_parser.add_argument('--timeout', type=int, metavar='SECONDS',
                                   help='Download timeout in seconds (overrides config)')
        download_parser.add_argument('--retry-attempts', type=int, metavar='N',
                                   help='Number of retry attempts for failed downloads (overrides config)')
        download_parser.add_argument('--show-files', type=int, metavar='N', default=3,
                                   help='Maximum number of files to show in progress table (default: 3)')

        # Select devices command
        select_parser = subparsers.add_parser('select-devices', help='Select master and slave devices')
        select_parser.add_argument('--master', help='Master device serial')
        select_parser.add_argument('--slave', help='Slave device serial')

        # Transfer command (CLI-only)
        transfer_parser = subparsers.add_parser('transfer', help='Transfer data to devices (CLI-only)')
        transfer_parser.add_argument('--master-only', action='store_true', help='Transfer to master only')
        transfer_parser.add_argument('--slave-only', action='store_true', help='Transfer to slave only')
        transfer_parser.add_argument('--videos-only', action='store_true', help='Transfer videos only')
        transfer_parser.add_argument('--json-only', action='store_true', help='Transfer JSON only')

        # Deploy command (CLI-only)
        deploy_parser = subparsers.add_parser('deploy', help='Complete deployment pipeline (CLI-only)')
        deploy_parser.add_argument('--auto', action='store_true', help='Auto-detect devices')
        deploy_parser.add_argument('--skip-auth', action='store_true', help='Skip authentication')
        deploy_parser.add_argument('--skip-fetch', action='store_true', help='Skip data fetching')
        deploy_parser.add_argument('--skip-download', action='store_true', help='Skip asset download')

        # List directories command
        list_dir_parser = subparsers.add_parser('list-directories', help='List and compare EldersVR directories on devices')
        list_dir_group = list_dir_parser.add_mutually_exclusive_group()
        list_dir_group.add_argument('--device', help='List directories on specific device by serial')
        list_dir_group.add_argument('--compare', action='store_true', help='Compare directories between master and slave devices')
        list_dir_parser.add_argument('--detailed', action='store_true', help='Show detailed file information including sizes and dates')

        # Parse arguments
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return 1

        # Set up logging level
        if args.verbose:
            self.logger.setLevel('DEBUG')

        # Load configuration
        self.load_config(args.config)

        # Route to appropriate command handler
        command_map = {
            'auth': self.cmd_auth,
            'logout': self.cmd_logout,
            'list-devices': self.cmd_list_devices,
            'list-directories': self.cmd_list_directories,
            'verify': self.cmd_verify,
            'fetch-data': self.cmd_fetch_data,
            'download-videos': self.cmd_download_videos,
            'select-devices': self.cmd_select_devices,
            'transfer': self.cmd_transfer,
            'deploy': self.cmd_deploy,
        }

        handler = command_map.get(args.command)
        if handler:
            return handler(args)
        else:
            self.logger.error(f"Unknown command: {args.command}")
            return 1


def main():
    """Entry point for CLI application"""
    cli = EldersVRCLI()
    try:
        exit_code = cli.run()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
