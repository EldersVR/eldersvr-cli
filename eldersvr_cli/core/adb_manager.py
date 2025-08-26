"""
ADB Manager for device operations
Handles ADB connectivity, storage verification, and file transfers
"""

import subprocess
import os
import glob
import time
from typing import List, Tuple, Optional, Dict
from ..utils import get_logger


class CLIAccessControl:
    """Security control for CLI-only operations"""

    CLI_ONLY_OPERATIONS = ["transfer", "sync", "deploy"]

    @staticmethod
    def require_cli_access(operation: str):
        """Decorator to ensure operation is CLI-only"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not CLIAccessControl.is_cli_environment():
                    raise PermissionError(f"Operation '{operation}' is CLI-only")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def is_cli_environment() -> bool:
        """Check if running from CLI environment"""
        # For now, assume CLI environment
        # In production, this would check environment variables or other indicators
        return True


class ADBManager:
    """Manages ADB operations for EldersVR device onboarding"""

    def __init__(self, device_path: str = "/storage/emulated/0/Android/data/com.q42.eldersvr/files/EldersVR"):
        self.eldersvr_path = device_path
        self.video_path = f"{self.eldersvr_path}/Video"
        self.image_path = f"{self.eldersvr_path}/Image"
        self.logger = get_logger('ADBManager')
        
        # Fallback paths for different Android storage configurations
        self.fallback_paths = [
            "/storage/emulated/0/Android/data",
            "/storage/emulated/0/Documents/EldersVR",
            "/sdcard/EldersVR",
            "/storage/sdcard0/EldersVR"
        ]
        
        # Track root status per device
        self._device_root_status = {}

    def verify_adb_available(self) -> bool:
        """Check if ADB is available in system PATH"""
        try:
            result = subprocess.run(["adb", "version"],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def check_root_access(self, serial: str) -> bool:
        """Check if device has root access available"""
        if serial in self._device_root_status:
            return self._device_root_status[serial]
            
        self.logger.debug(f"Checking root access for device {serial}")
        
        try:
            # Check if su command is available
            su_check = subprocess.run([
                "adb", "-s", serial, "shell",
                "which", "su"
            ], capture_output=True, text=True, timeout=10)
            
            has_su = su_check.returncode == 0 and su_check.stdout.strip()
            
            if has_su:
                # Test if we can actually gain root access
                root_test = subprocess.run([
                    "adb", "-s", serial, "shell",
                    "su", "-c", "id"
                ], capture_output=True, text=True, timeout=15)
                
                has_root = root_test.returncode == 0 and "uid=0(root)" in root_test.stdout
                self._device_root_status[serial] = has_root
                
                if has_root:
                    self.logger.info(f"✅ Root access available on device {serial}")
                else:
                    self.logger.info(f"⚠️ su command found but root access denied on device {serial}")
                
                return has_root
            else:
                self.logger.info(f"ℹ️ No su command found on device {serial} (non-rooted)")
                self._device_root_status[serial] = False
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.debug(f"Timeout checking root access on device {serial}")
            self._device_root_status[serial] = False
            return False

    def enable_adb_root(self, serial: str) -> bool:
        """Enable ADB root mode if device supports it"""
        self.logger.info(f"Attempting to enable ADB root mode on device {serial}")
        
        try:
            # Try to restart ADB in root mode
            root_result = subprocess.run([
                "adb", "-s", serial, "root"
            ], capture_output=True, text=True, timeout=30)
            
            if root_result.returncode == 0:
                self.logger.info(f"✅ ADB root mode enabled on device {serial}")
                # Wait a moment for ADB to restart
                import time
                time.sleep(2)
                
                # Verify root mode is active
                id_result = subprocess.run([
                    "adb", "-s", serial, "shell", "id"
                ], capture_output=True, text=True, timeout=10)
                
                if id_result.returncode == 0 and "uid=0(root)" in id_result.stdout:
                    self.logger.info(f"✅ Root access confirmed on device {serial}")
                    self._device_root_status[serial] = True
                    return True
                else:
                    self.logger.warning(f"⚠️ ADB root command succeeded but no root access on device {serial}")
                    return False
            else:
                self.logger.info(f"ℹ️ ADB root mode not available on device {serial}")
                if "production builds" in root_result.stderr:
                    self.logger.info("Device is running production build - root not available")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Timeout enabling ADB root on device {serial}")
            return False

    def get_connected_devices(self) -> List[Dict[str, str]]:
        """Get list of connected ADB devices with details"""
        if not self.verify_adb_available():
            raise RuntimeError("ADB is not available in system PATH")

        try:
            result = subprocess.run(["adb", "devices", "-l"],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise RuntimeError(f"ADB devices command failed: {result.stderr}")

            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header line

            for line in lines:
                if line.strip() and 'device' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        serial = parts[0]
                        status = parts[1]

                        # Extract model info if available
                        model = "Unknown"
                        product = "Unknown"
                        for part in parts[2:]:
                            if part.startswith('model:'):
                                model = part.split(':')[1]
                            elif part.startswith('product:'):
                                product = part.split(':')[1]

                        devices.append({
                            'serial': serial,
                            'status': status,
                            'model': model,
                            'product': product
                        })

            return devices

        except subprocess.TimeoutExpired:
            raise RuntimeError("ADB devices command timed out")

    def verify_storage_access(self, serial: str) -> bool:
        """Check if EldersVR directory exists and is writable"""
        self.logger.info(f"Verifying storage access on device {serial}")
        self.logger.info(f"Target path: {self.eldersvr_path}")
        
        try:
            # Check if directory exists
            self.logger.debug(f"Checking if directory exists: {self.eldersvr_path}")
            check_dir = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-d", self.eldersvr_path
            ], capture_output=True, text=True, timeout=15)

            # Check if directory is writable
            self.logger.debug(f"Checking if directory is writable: {self.eldersvr_path}")
            check_write = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-w", self.eldersvr_path
            ], capture_output=True, text=True, timeout=15)

            dir_exists = check_dir.returncode == 0
            is_writable = check_write.returncode == 0
            
            self.logger.info(f"Directory exists: {dir_exists}")
            self.logger.info(f"Directory writable: {is_writable}")
            
            if check_dir.stderr:
                self.logger.debug(f"Directory check stderr: {check_dir.stderr}")
            if check_write.stderr:
                self.logger.debug(f"Write check stderr: {check_write.stderr}")

            if not dir_exists or not is_writable:
                self.logger.warning(f"Storage verification failed - trying root access and fallback paths")
                
                # First try to gain root access if available
                has_root = self.check_root_access(serial)
                if has_root:
                    self.logger.info(f"Attempting root-level directory access on {serial}")
                    if self._try_root_storage_setup(serial):
                        return True
                
                # If root access doesn't help or isn't available, try fallback paths
                return self._try_fallback_paths(serial)
            
            self.logger.info(f"✅ Storage access verified successfully for {self.eldersvr_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Timeout during storage verification for device {serial}")
            return False

    def _try_fallback_paths(self, serial: str) -> bool:
        """Try fallback storage paths when primary path fails"""
        self.logger.info(f"Trying fallback storage paths for device {serial}")
        
        for fallback_path in self.fallback_paths:
            self.logger.info(f"Testing fallback path: {fallback_path}")
            
            try:
                # For Android/data, we need to create our app-specific directory
                if "Android/data" in fallback_path:
                    test_path = f"{fallback_path}/com.q42.eldersvr/files/EldersVR"
                else:
                    test_path = fallback_path
                    
                # Check if this path is writable
                check_result = subprocess.run([
                    "adb", "-s", serial, "shell",
                    f"mkdir -p {test_path} && test -w {test_path}"
                ], capture_output=True, text=True, timeout=15)
                
                if check_result.returncode == 0:
                    self.logger.info(f"✅ Found working fallback path: {test_path}")
                    # Update our paths to use this fallback
                    self.eldersvr_path = test_path
                    self.video_path = f"{self.eldersvr_path}/Video"
                    self.image_path = f"{self.eldersvr_path}/Image"
                    return True
                else:
                    self.logger.debug(f"❌ Fallback path not writable: {test_path}")
                    if check_result.stderr:
                        self.logger.debug(f"Error: {check_result.stderr}")
                        
            except subprocess.TimeoutExpired:
                self.logger.debug(f"Timeout testing fallback path: {fallback_path}")
                continue
        
        self.logger.error("❌ No writable storage path found on device")
        return False

    def _try_root_storage_setup(self, serial: str) -> bool:
        """Try to setup storage with root access"""
        try:
            # Try to create directory with root permissions
            self.logger.debug(f"Creating directory with root: {self.eldersvr_path}")
            create_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "su", "-c", f"mkdir -p {self.eldersvr_path}"
            ], capture_output=True, text=True, timeout=15)
            
            if create_result.returncode != 0:
                self.logger.debug(f"Root mkdir failed: {create_result.stderr}")
                return False
            
            # Try to set permissions to make it writable by shell user
            chmod_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "su", "-c", f"chmod 777 {self.eldersvr_path}"
            ], capture_output=True, text=True, timeout=15)
            
            if chmod_result.returncode != 0:
                self.logger.debug(f"Root chmod failed: {chmod_result.stderr}")
                return False
                
            # Verify the directory is now accessible
            verify_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-w", self.eldersvr_path
            ], capture_output=True, timeout=10)
            
            if verify_result.returncode == 0:
                self.logger.info(f"✅ Root access enabled write permissions for {self.eldersvr_path}")
                return True
            else:
                self.logger.debug(f"Directory still not writable after root setup")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.debug("Timeout during root storage setup")
            return False

    def create_eldersvr_structure(self, serial: str) -> bool:
        """Create EldersVR directory structure on device"""
        self.logger.info(f"Creating EldersVR directory structure on device {serial}")
        
        directories = [
            self.eldersvr_path,
            self.video_path,
            self.image_path
        ]

        try:
            for dir_path in directories:
                self.logger.debug(f"Creating directory: {dir_path}")
                result = subprocess.run([
                    "adb", "-s", serial, "shell",
                    "mkdir", "-p", dir_path
                ], capture_output=True, text=True, timeout=15)

                if result.returncode != 0:
                    self.logger.error(f"❌ Failed to create directory: {dir_path}")
                    if result.stderr:
                        self.logger.error(f"Error details: {result.stderr}")
                    return False
                else:
                    self.logger.debug(f"✅ Successfully created: {dir_path}")

            self.logger.info(f"✅ Directory structure created successfully at: {self.eldersvr_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Timeout while creating directory structure on device {serial}")
            return False

    def test_write_permissions(self, serial: str) -> bool:
        """Test write permissions by creating and deleting a test file"""
        test_file_path = f"{self.eldersvr_path}/test_write.tmp"
        self.logger.info(f"Testing write permissions on device {serial}")
        self.logger.debug(f"Test file path: {test_file_path}")

        try:
            # Create test file
            self.logger.debug("Creating test file...")
            create_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "touch", test_file_path
            ], capture_output=True, text=True, timeout=10)

            if create_result.returncode != 0:
                self.logger.error(f"❌ Failed to create test file: {test_file_path}")
                if create_result.stderr:
                    self.logger.error(f"Error: {create_result.stderr}")
                return False

            self.logger.debug("✅ Test file created successfully")

            # Delete test file
            self.logger.debug("Deleting test file...")
            delete_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "rm", test_file_path
            ], capture_output=True, text=True, timeout=10)

            if delete_result.returncode == 0:
                self.logger.info(f"✅ Write permissions verified successfully for {self.eldersvr_path}")
                return True
            else:
                self.logger.error(f"❌ Failed to delete test file: {test_file_path}")
                if delete_result.stderr:
                    self.logger.error(f"Error: {delete_result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Timeout during write permissions test on device {serial}")
            return False

    def clear_cache_and_logs(self, serial: str) -> bool:
        """Clear existing cache and logs in EldersVR directory to ensure clean transfer"""
        try:
            # First, remove all files in the directories
            clear_commands = [
                f"rm -rf {self.eldersvr_path}/*",
                f"rm -rf {self.video_path}",
                f"rm -rf {self.image_path}"
            ]

            success = True
            for cmd in clear_commands:
                result = subprocess.run([
                    "adb", "-s", serial, "shell", cmd
                ], capture_output=True, text=True, timeout=30)

                if result.returncode != 0 and "No such file" not in result.stderr:
                    success = False

            # Recreate the directory structure after clearing
            self.create_eldersvr_structure(serial)

            # Also try to clear app cache if possible (for EldersVR app)
            # This might fail if app is not installed, which is okay
            subprocess.run([
                "adb", "-s", serial, "shell",
                "pm", "clear", "com.q42.eldersvr"
            ], capture_output=True, timeout=15)

            return success

        except subprocess.TimeoutExpired:
            return False

    @CLIAccessControl.require_cli_access("transfer")
    def push_json(self, serial: str, local_json_path: str) -> bool:
        """Push JSON file to device"""
        if not os.path.exists(local_json_path):
            raise FileNotFoundError(f"Local JSON file not found: {local_json_path}")

        remote_path = f"{self.eldersvr_path}/new_data.json"

        try:
            result = subprocess.run([
                "adb", "-s", serial, "push",
                local_json_path, remote_path
            ], capture_output=True, text=True, timeout=60)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False

    @CLIAccessControl.require_cli_access("transfer")
    def push_credential_json(self, serial: str, local_credential_path: str) -> bool:
        """Push credential.json file to device"""
        if not os.path.exists(local_credential_path):
            print(f"Warning: credential.json not found at {local_credential_path}")
            return False

        remote_path = f"{self.eldersvr_path}/credential.json"

        try:
            result = subprocess.run([
                "adb", "-s", serial, "push",
                local_credential_path, remote_path
            ], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                print(f"Successfully transferred credential.json to {serial}")
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("Timeout while transferring credential.json")
            return False

    @CLIAccessControl.require_cli_access("transfer")
    def push_videos(self, serial: str, local_videos_dir: str, progress_callback=None) -> Tuple[int, int]:
        """Push all video files to device with real-time progress. Returns (success_count, total_count)"""
        if not os.path.exists(local_videos_dir):
            raise FileNotFoundError(f"Local videos directory not found: {local_videos_dir}")

        video_files = glob.glob(f"{local_videos_dir}/*.mp4")
        return self._push_video_files(serial, local_videos_dir, [os.path.basename(f) for f in video_files], progress_callback)
    
    @CLIAccessControl.require_cli_access("transfer")
    def push_videos_filtered(self, serial: str, local_videos_dir: str, filtered_files: List[str], progress_callback=None) -> Tuple[int, int]:
        """Push filtered video files to device with real-time progress. Returns (success_count, total_count)"""
        if not os.path.exists(local_videos_dir):
            raise FileNotFoundError(f"Local videos directory not found: {local_videos_dir}")
        
        return self._push_video_files(serial, local_videos_dir, filtered_files, progress_callback)
    
    def _push_video_files(self, serial: str, local_videos_dir: str, file_list: List[str], progress_callback=None) -> Tuple[int, int]:
        """Internal method to push specific video files with real-time progress tracking"""
        success_count = 0
        
        self.logger.info(f"Starting transfer of {len(file_list)} video files to {serial}")

        for idx, filename in enumerate(file_list, 1):
            video_file = os.path.join(local_videos_dir, filename)
            remote_path = f"{self.video_path}/{filename}"
            
            if not os.path.exists(video_file):
                self.logger.warning(f"❌ Video file not found: {video_file}")
                continue
                
            file_size = os.path.getsize(video_file)
            self.logger.debug(f"Transferring {filename} ({self._format_file_size(file_size)})")

            try:
                # Start ADB push with progress monitoring
                process = subprocess.Popen([
                    "adb", "-s", serial, "push",
                    video_file, remote_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor transfer progress
                start_time = time.time()
                while process.poll() is None:
                    elapsed = time.time() - start_time
                    # Estimate progress based on elapsed time (rough estimate)
                    if file_size > 0:
                        estimated_speed = 10 * 1024 * 1024  # 10 MB/s estimate
                        estimated_progress = min(95, (elapsed * estimated_speed / file_size) * 100)
                        if progress_callback:
                            progress_callback(idx - 1, len(file_list), estimated_progress)
                    time.sleep(0.5)
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    success_count += 1
                    self.logger.debug(f"✅ Successfully transferred {filename}")
                    if progress_callback:
                        progress_callback(success_count, len(file_list), 100)
                else:
                    self.logger.warning(f"❌ Failed to transfer {filename}: {stderr}")
                    if progress_callback:
                        progress_callback(success_count, len(file_list), 0)

            except Exception as e:
                self.logger.error(f"❌ Error transferring {filename}: {e}")
                if progress_callback:
                    progress_callback(success_count, len(file_list), 0)
                continue

        return success_count, len(file_list)

    @CLIAccessControl.require_cli_access("transfer")
    def push_images(self, serial: str, local_images_dir: str, progress_callback=None) -> Tuple[int, int]:
        """Push all image files to device with real-time progress. Returns (success_count, total_count)"""
        if not os.path.exists(local_images_dir):
            raise FileNotFoundError(f"Local images directory not found: {local_images_dir}")

        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
        image_files = []

        for ext in image_extensions:
            image_files.extend(glob.glob(f"{local_images_dir}/{ext}"))
            image_files.extend(glob.glob(f"{local_images_dir}/{ext.upper()}"))

        success_count = 0
        
        self.logger.info(f"Starting transfer of {len(image_files)} image files to {serial}")

        for idx, image_file in enumerate(image_files, 1):
            filename = os.path.basename(image_file)
            remote_path = f"{self.image_path}/{filename}"
            file_size = os.path.getsize(image_file)
            
            self.logger.debug(f"Transferring {filename} ({self._format_file_size(file_size)})")

            try:
                # Start ADB push with progress monitoring
                process = subprocess.Popen([
                    "adb", "-s", serial, "push",
                    image_file, remote_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor transfer progress
                start_time = time.time()
                while process.poll() is None:
                    elapsed = time.time() - start_time
                    # Estimate progress based on elapsed time (images are usually small and fast)
                    if file_size > 0:
                        estimated_speed = 20 * 1024 * 1024  # 20 MB/s estimate for images
                        estimated_progress = min(95, (elapsed * estimated_speed / file_size) * 100)
                        if progress_callback:
                            progress_callback(idx - 1, len(image_files), estimated_progress)
                    time.sleep(0.2)  # Shorter interval for images
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    success_count += 1
                    self.logger.debug(f"✅ Successfully transferred {filename}")
                    if progress_callback:
                        progress_callback(success_count, len(image_files), 100)
                else:
                    self.logger.warning(f"❌ Failed to transfer {filename}: {stderr}")
                    if progress_callback:
                        progress_callback(success_count, len(image_files), 0)

            except Exception as e:
                self.logger.error(f"❌ Error transferring {filename}: {e}")
                if progress_callback:
                    progress_callback(success_count, len(image_files), 0)
                continue

        return success_count, len(image_files)
    
    def _format_file_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"

    def get_device_storage_info(self, serial: str) -> Optional[Dict[str, str]]:
        """Get storage information for EldersVR directory"""
        try:
            # Get directory size
            size_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "du", "-sh", self.eldersvr_path
            ], capture_output=True, text=True, timeout=30)

            # Get free space
            space_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "df", "/storage/emulated/0"
            ], capture_output=True, text=True, timeout=30)

            storage_info = {}

            if size_result.returncode == 0:
                size_line = size_result.stdout.strip().split('\t')[0]
                storage_info['used_space'] = size_line

            if space_result.returncode == 0:
                lines = space_result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        storage_info['total_space'] = parts[1]
                        storage_info['available_space'] = parts[3]

            return storage_info

        except subprocess.TimeoutExpired:
            return None

    def verify_transfer(self, serial: str) -> Dict[str, any]:
        """Verify successful transfer by checking files on device"""
        verification = {
            'json_exists': False,
            'video_count': 0,
            'image_count': 0,
            'storage_info': None
        }

        try:
            # Check JSON file
            json_check = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-f", f"{self.eldersvr_path}/new_data.json"
            ], capture_output=True, timeout=10)
            verification['json_exists'] = json_check.returncode == 0

            # Count video files
            video_count = subprocess.run([
                "adb", "-s", serial, "shell",
                "find", self.video_path, "-name", "*.mp4", "|", "wc", "-l"
            ], capture_output=True, text=True, timeout=30)
            if video_count.returncode == 0:
                verification['video_count'] = int(video_count.stdout.strip() or "0")

            # Count image files
            image_count = subprocess.run([
                "adb", "-s", serial, "shell",
                "find", self.image_path, "-type", "f", "|", "wc", "-l"
            ], capture_output=True, text=True, timeout=30)
            if image_count.returncode == 0:
                verification['image_count'] = int(image_count.stdout.strip() or "0")

            # Get storage info
            verification['storage_info'] = self.get_device_storage_info(serial)

        except (subprocess.TimeoutExpired, ValueError):
            pass

        return verification
    
    def list_directory_contents(self, serial: str, detailed: bool = False) -> Dict[str, Any]:
        """List contents of EldersVR directory on device"""
        directory_info = {
            'device_serial': serial,
            'base_path': self.eldersvr_path,
            'video_path': self.video_path,
            'image_path': self.image_path,
            'directories': {},
            'files': {},
            'total_size': 0,
            'errors': []
        }
        
        try:
            # Check if base directory exists
            base_check = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-d", self.eldersvr_path
            ], capture_output=True, timeout=10)
            
            if base_check.returncode != 0:
                directory_info['errors'].append(f"Base directory {self.eldersvr_path} does not exist")
                return directory_info
            
            # List all directories and their contents
            directories_to_check = {
                'root': self.eldersvr_path,
                'videos': self.video_path,
                'images': self.image_path
            }
            
            for dir_name, dir_path in directories_to_check.items():
                try:
                    # Check if directory exists
                    dir_check = subprocess.run([
                        "adb", "-s", serial, "shell",
                        "test", "-d", dir_path
                    ], capture_output=True, timeout=10)
                    
                    if dir_check.returncode != 0:
                        directory_info['directories'][dir_name] = {
                            'path': dir_path,
                            'exists': False,
                            'files': [],
                            'file_count': 0,
                            'total_size': 0
                        }
                        continue
                    
                    # List files in directory
                    if detailed:
                        # Get detailed file listing with sizes
                        ls_result = subprocess.run([
                            "adb", "-s", serial, "shell",
                            "ls", "-la", dir_path
                        ], capture_output=True, text=True, timeout=30)
                    else:
                        # Simple file listing
                        ls_result = subprocess.run([
                            "adb", "-s", serial, "shell",
                            "ls", dir_path
                        ], capture_output=True, text=True, timeout=30)
                    
                    files_info = []
                    dir_total_size = 0
                    
                    if ls_result.returncode == 0 and ls_result.stdout.strip():
                        lines = ls_result.stdout.strip().split('\n')
                        
                        for line in lines:
                            line = line.strip()
                            if not line or line.startswith('total'):
                                continue
                                
                            if detailed and line.startswith('-'):
                                # Parse detailed listing (permissions size date filename)
                                parts = line.split()
                                if len(parts) >= 5:
                                    filename = ' '.join(parts[8:])  # Handle filenames with spaces
                                    size = int(parts[4]) if parts[4].isdigit() else 0
                                    files_info.append({
                                        'name': filename,
                                        'size': size,
                                        'size_formatted': self._format_file_size(size),
                                        'permissions': parts[0],
                                        'date': f"{parts[5]} {parts[6]} {parts[7]}"
                                    })
                                    dir_total_size += size
                            elif not detailed:
                                # Simple listing - just filenames
                                if line and not line.endswith('/'):
                                    files_info.append({
                                        'name': line,
                                        'size': None,
                                        'size_formatted': 'Unknown'
                                    })
                    
                    directory_info['directories'][dir_name] = {
                        'path': dir_path,
                        'exists': True,
                        'files': files_info,
                        'file_count': len(files_info),
                        'total_size': dir_total_size,
                        'total_size_formatted': self._format_file_size(dir_total_size) if dir_total_size > 0 else '0B'
                    }
                    
                    directory_info['total_size'] += dir_total_size
                    
                except subprocess.TimeoutExpired:
                    directory_info['errors'].append(f"Timeout listing directory: {dir_path}")
                except Exception as e:
                    directory_info['errors'].append(f"Error listing {dir_path}: {str(e)}")
            
            # Get device storage info
            try:
                storage_info = self.get_device_storage_info(serial)
                if storage_info:
                    directory_info['storage_info'] = storage_info
            except Exception as e:
                directory_info['errors'].append(f"Could not get storage info: {str(e)}")
                
        except Exception as e:
            directory_info['errors'].append(f"General error: {str(e)}")
        
        directory_info['total_size_formatted'] = self._format_file_size(directory_info['total_size'])
        return directory_info
    
    def compare_devices_directories(self, master_serial: str, slave_serial: str) -> Dict[str, Any]:
        """Compare directory contents between master and slave devices"""
        self.logger.info(f"Comparing directories between master ({master_serial}) and slave ({slave_serial})")
        
        # Get directory listings for both devices
        master_info = self.list_directory_contents(master_serial, detailed=True)
        slave_info = self.list_directory_contents(slave_serial, detailed=True)
        
        comparison = {
            'master': master_info,
            'slave': slave_info,
            'comparison': {
                'videos': self._compare_directory_files(master_info, slave_info, 'videos'),
                'images': self._compare_directory_files(master_info, slave_info, 'images'),
                'root': self._compare_directory_files(master_info, slave_info, 'root')
            }
        }
        
        return comparison
    
    def _compare_directory_files(self, master_info: Dict, slave_info: Dict, dir_type: str) -> Dict[str, Any]:
        """Compare files between two directory listings"""
        master_dir = master_info['directories'].get(dir_type, {})
        slave_dir = slave_info['directories'].get(dir_type, {})
        
        master_files = {f['name']: f for f in master_dir.get('files', [])}
        slave_files = {f['name']: f for f in slave_dir.get('files', [])}
        
        comparison = {
            'master_only': [],
            'slave_only': [], 
            'common_files': [],
            'size_differences': [],
            'master_count': len(master_files),
            'slave_count': len(slave_files),
            'master_total_size': master_dir.get('total_size', 0),
            'slave_total_size': slave_dir.get('total_size', 0)
        }
        
        # Find master-only files
        for filename, file_info in master_files.items():
            if filename not in slave_files:
                comparison['master_only'].append(file_info)
        
        # Find slave-only files
        for filename, file_info in slave_files.items():
            if filename not in master_files:
                comparison['slave_only'].append(file_info)
        
        # Find common files and size differences
        for filename in master_files.keys():
            if filename in slave_files:
                master_file = master_files[filename]
                slave_file = slave_files[filename]
                
                common_file = {
                    'name': filename,
                    'master_size': master_file.get('size', 0),
                    'slave_size': slave_file.get('size', 0),
                    'master_size_formatted': master_file.get('size_formatted', 'Unknown'),
                    'slave_size_formatted': slave_file.get('size_formatted', 'Unknown')
                }
                
                comparison['common_files'].append(common_file)
                
                # Check for size differences
                if master_file.get('size') != slave_file.get('size'):
                    comparison['size_differences'].append(common_file)
        
        return comparison

    @CLIAccessControl.require_cli_access("sync")
    def clean_eldersvr_directory(self, serial: str) -> bool:
        """Clean EldersVR directory on device (CLI-only operation)"""
        try:
            result = subprocess.run([
                "adb", "-s", serial, "shell",
                "rm", "-rf", f"{self.eldersvr_path}/*"
            ], capture_output=True, timeout=60)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False
