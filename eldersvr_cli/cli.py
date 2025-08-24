#!/usr/bin/env python3
"""
EldersVR CLI - ADB Onboarding Tool
Main CLI entry point with command handling
"""

import argparse
import sys
import os
import json
from typing import Dict, Any, Optional

from .core import ADBManager, ContentManager
from .utils import setup_logger, get_logger, TransferProgress, print_deployment_summary


class EldersVRCLI:
    """Main CLI application class"""

    def __init__(self):
        self.config: Optional[Dict[str, Any]] = None
        self.adb_manager = ADBManager()
        self.content_manager: Optional[ContentManager] = None
        self.logger = setup_logger('eldersvr-cli')

    def load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from file"""
        if config_path is None:
            # Look for config in common locations
            config_locations = [
                './eldersvr_config.json',
                '~/.eldersvr/config.json',
                '/etc/eldersvr/config.json'
            ]

            for location in config_locations:
                expanded_path = os.path.expanduser(location)
                if os.path.exists(expanded_path):
                    config_path = expanded_path
                    break

        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
                    self.logger.info(f"Loaded configuration from {config_path}")
                    return self.config
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Failed to load config from {config_path}: {e}")

        # Use default configuration
        self.config = self._get_default_config()
        self.logger.warning("Using default configuration")
        return self.config

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
                "device_path": "/storage/emulated/0/Download/EldersVR",
                "json_filename": "new_data.json"
            },
            "devices": {
                "master_serial": "",
                "slave_serial": ""
            },
            "auth": {
                "email": "clionboarding@eldervr.com",
                "password": "clionboarding@eldervr.com"
            }
        }

    def cmd_auth(self, args) -> int:
        """Handle authentication command"""
        if not self.config:
            self.load_config()

        self.content_manager = ContentManager(self.config)

        email = args.email or self.config['auth']['email']
        password = args.password or self.config['auth']['password']

        if not email or not password:
            self.logger.error("Email and password are required for authentication")
            return 1

        self.logger.info(f"Authenticating with {email}...")

        if self.content_manager.authenticate(email, password):
            user_info = self.content_manager.get_user_info()
            company_info = self.content_manager.get_company_info()

            self.logger.info("Authentication successful!")
            self.logger.info(f"User: {user_info.get('name', 'Unknown')} ({user_info.get('email', 'Unknown')})")
            self.logger.info(f"Company: {company_info.get('name', 'Unknown')}")
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

    def cmd_fetch_data(self, args) -> int:
        """Handle fetch data command (tags + films)"""
        if not self.config:
            self.load_config()

        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        if not self.content_manager.is_authenticated():
            self.logger.error("Not authenticated. Please run 'auth' command first.")
            return 1

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

        json_file = f"{self.config['paths']['local_downloads']}/new_data.json"
        if not os.path.exists(json_file):
            self.logger.error("new_data.json not found. Please run 'fetch-data' first.")
            return 1

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to read new_data.json: {e}")
            return 1

        self.logger.info("Starting download of all assets...")

        # Initialize content manager for downloads
        if not self.content_manager:
            self.content_manager = ContentManager(self.config)

        try:
            download_stats = self.content_manager.download_all_assets(data)

            self.logger.info("Download completed!")
            self.logger.info(f"High-res videos: {download_stats['videos_high']}")
            self.logger.info(f"Low-res videos: {download_stats['videos_low']}")
            self.logger.info(f"Thumbnails: {download_stats['thumbnails']}")
            self.logger.info(f"Tag images: {download_stats['tag_images']}")

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
        if not self.config:
            self.load_config()

        master_serial = self.config['devices']['master_serial']
        slave_serial = self.config['devices']['slave_serial']

        if not master_serial and not slave_serial:
            self.logger.error("No devices configured. Please run 'select-devices' first.")
            return 1

        # Initialize progress tracker
        progress = TransferProgress()

        if master_serial:
            progress.add_device(master_serial, "Master")
        if slave_serial:
            progress.add_device(slave_serial, "Slave")

        success = True

        try:
            # Transfer to master (JSON + videos + images)
            if master_serial and not args.slave_only:
                success &= self._transfer_to_master(master_serial, progress, args)

            # Transfer to slave (JSON + videos + images)
            if slave_serial and not args.master_only:
                success &= self._transfer_to_slave(slave_serial, progress, args)

            # Print final summary
            print_deployment_summary(progress)

            return 0 if success else 1

        except Exception as e:
            self.logger.error(f"Transfer failed: {e}")
            return 1

    def _transfer_to_master(self, serial: str, progress: TransferProgress, args) -> bool:
        """Transfer data to master device"""
        json_path = f"{self.config['paths']['local_downloads']}/new_data.json"
        videos_dir = f"{self.config['paths']['local_downloads']}/videos"
        images_dir = f"{self.config['paths']['local_downloads']}/images"

        success = True

        self.logger.info(f"Transferring to master device {serial}...")

        # Clear cache and logs first
        self.logger.info(f"Clearing existing files on master device {serial}...")
        if self.adb_manager.clear_cache_and_logs(serial):
            self.logger.info("Successfully cleared existing files")
        else:
            self.logger.warning("Some files could not be cleared, continuing anyway...")

        # Create directory structure
        if not self.adb_manager.create_eldersvr_structure(serial):
            return False

        # Transfer JSON
        if not args.videos_only:
            progress.update_json_status(serial, 'in_progress')
            if self.adb_manager.push_json(serial, json_path):
                file_size = os.path.getsize(json_path) if os.path.exists(json_path) else 0
                progress.update_json_status(serial, 'completed', file_size)
            else:
                progress.update_json_status(serial, 'failed')
                success = False

        # Transfer videos
        if not args.json_only and os.path.exists(videos_dir):
            video_files = len([f for f in os.listdir(videos_dir) if f.endswith('.mp4')])
            progress.update_videos_progress(serial, 0, video_files, 'in_progress')

            video_success, video_total = self.adb_manager.push_videos(serial, videos_dir)

            if video_success == video_total:
                progress.update_videos_progress(serial, video_success, video_total, 'completed')
            else:
                progress.update_videos_progress(serial, video_success, video_total, 'failed')
                success = False

        # Transfer images
        if not args.json_only and os.path.exists(images_dir):
            image_files = len([f for f in os.listdir(images_dir)
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            progress.update_images_progress(serial, 0, image_files, 'in_progress')

            image_success, image_total = self.adb_manager.push_images(serial, images_dir)

            if image_success == image_total:
                progress.update_images_progress(serial, image_success, image_total, 'completed')
            else:
                progress.update_images_progress(serial, image_success, image_total, 'failed')
                success = False

        return success

    def _transfer_to_slave(self, serial: str, progress: TransferProgress, args) -> bool:
        """Transfer data to slave device"""
        json_path = f"{self.config['paths']['local_downloads']}/new_data.json"
        videos_dir = f"{self.config['paths']['local_downloads']}/videos"
        images_dir = f"{self.config['paths']['local_downloads']}/images"

        success = True

        self.logger.info(f"Transferring to slave device {serial}...")

        # Clear cache and logs first
        self.logger.info(f"Clearing existing files on slave device {serial}...")
        if self.adb_manager.clear_cache_and_logs(serial):
            self.logger.info("Successfully cleared existing files")
        else:
            self.logger.warning("Some files could not be cleared, continuing anyway...")

        # Create directory structure
        if not self.adb_manager.create_eldersvr_structure(serial):
            return False

        # Transfer JSON
        if not args.videos_only:
            progress.update_json_status(serial, 'in_progress')
            if self.adb_manager.push_json(serial, json_path):
                file_size = os.path.getsize(json_path) if os.path.exists(json_path) else 0
                progress.update_json_status(serial, 'completed', file_size)
            else:
                progress.update_json_status(serial, 'failed')
                success = False

        # Transfer videos
        if not args.json_only and os.path.exists(videos_dir):
            video_files = len([f for f in os.listdir(videos_dir) if f.endswith('.mp4')])
            progress.update_videos_progress(serial, 0, video_files, 'in_progress')

            video_success, video_total = self.adb_manager.push_videos(serial, videos_dir)

            if video_success == video_total:
                progress.update_videos_progress(serial, video_success, video_total, 'completed')
            else:
                progress.update_videos_progress(serial, video_success, video_total, 'failed')
                success = False

        # Transfer images
        if not args.json_only and os.path.exists(images_dir):
            image_files = len([f for f in os.listdir(images_dir)
                             if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
            progress.update_images_progress(serial, 0, image_files, 'in_progress')

            image_success, image_total = self.adb_manager.push_images(serial, images_dir)

            if image_success == image_total:
                progress.update_images_progress(serial, image_success, image_total, 'completed')
            else:
                progress.update_images_progress(serial, image_success, image_total, 'failed')
                success = False

        return success

    def cmd_deploy(self, args) -> int:
        """Handle complete deployment command (CLI-only)"""
        self.logger.info("Starting complete deployment pipeline...")

        # Step 1: Load config
        if not self.config:
            self.load_config()

        # Step 2: Verify ADB
        if not self.adb_manager.verify_adb_available():
            self.logger.error("ADB not available. Please install ADB and add to PATH.")
            return 1

        # Step 3: Authenticate
        if not args.skip_auth:
            self.content_manager = ContentManager(self.config)
            email = self.config['auth']['email']
            password = self.config['auth']['password']

            if not self.content_manager.authenticate(email, password):
                self.logger.error("Authentication failed")
                return 1

            self.logger.info("Authentication successful")

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
        auth_parser.add_argument('--email', help='Email for authentication')
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
