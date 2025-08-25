"""
ADB Manager for device operations
Handles ADB connectivity, storage verification, and file transfers
"""

import subprocess
import os
import glob
from typing import List, Tuple, Optional, Dict


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

    def __init__(self):
        self.eldersvr_path = "/storage/emulated/0/Download/EldersVR"
        self.video_path = f"{self.eldersvr_path}/Video"
        self.image_path = f"{self.eldersvr_path}/Image"

    def verify_adb_available(self) -> bool:
        """Check if ADB is available in system PATH"""
        try:
            result = subprocess.run(["adb", "version"],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
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
        try:
            # Check if directory exists
            check_dir = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-d", self.eldersvr_path
            ], capture_output=True, timeout=15)

            # Check if directory is writable
            check_write = subprocess.run([
                "adb", "-s", serial, "shell",
                "test", "-w", self.eldersvr_path
            ], capture_output=True, timeout=15)

            return check_dir.returncode == 0 and check_write.returncode == 0

        except subprocess.TimeoutExpired:
            return False

    def create_eldersvr_structure(self, serial: str) -> bool:
        """Create EldersVR directory structure on device"""
        directories = [
            self.eldersvr_path,
            self.video_path,
            self.image_path
        ]

        try:
            for dir_path in directories:
                result = subprocess.run([
                    "adb", "-s", serial, "shell",
                    "mkdir", "-p", dir_path
                ], capture_output=True, timeout=15)

                if result.returncode != 0:
                    return False

            return True

        except subprocess.TimeoutExpired:
            return False

    def test_write_permissions(self, serial: str) -> bool:
        """Test write permissions by creating and deleting a test file"""
        test_file_path = f"{self.eldersvr_path}/test_write.tmp"

        try:
            # Create test file
            create_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "touch", test_file_path
            ], capture_output=True, timeout=10)

            if create_result.returncode != 0:
                return False

            # Delete test file
            delete_result = subprocess.run([
                "adb", "-s", serial, "shell",
                "rm", test_file_path
            ], capture_output=True, timeout=10)

            return delete_result.returncode == 0

        except subprocess.TimeoutExpired:
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
    def push_videos(self, serial: str, local_videos_dir: str) -> Tuple[int, int]:
        """Push all video files to device. Returns (success_count, total_count)"""
        if not os.path.exists(local_videos_dir):
            raise FileNotFoundError(f"Local videos directory not found: {local_videos_dir}")

        video_files = glob.glob(f"{local_videos_dir}/*.mp4")
        success_count = 0

        for video_file in video_files:
            filename = os.path.basename(video_file)
            remote_path = f"{self.video_path}/{filename}"

            try:
                result = subprocess.run([
                    "adb", "-s", serial, "push",
                    video_file, remote_path
                ], capture_output=True, timeout=300)  # 5 minutes timeout for large files

                if result.returncode == 0:
                    success_count += 1

            except subprocess.TimeoutExpired:
                continue

        return success_count, len(video_files)

    @CLIAccessControl.require_cli_access("transfer")
    def push_images(self, serial: str, local_images_dir: str) -> Tuple[int, int]:
        """Push all image files to device. Returns (success_count, total_count)"""
        if not os.path.exists(local_images_dir):
            raise FileNotFoundError(f"Local images directory not found: {local_images_dir}")

        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
        image_files = []

        for ext in image_extensions:
            image_files.extend(glob.glob(f"{local_images_dir}/{ext}"))
            image_files.extend(glob.glob(f"{local_images_dir}/{ext.upper()}"))

        success_count = 0

        for image_file in image_files:
            filename = os.path.basename(image_file)
            remote_path = f"{self.image_path}/{filename}"

            try:
                result = subprocess.run([
                    "adb", "-s", serial, "push",
                    image_file, remote_path
                ], capture_output=True, timeout=60)

                if result.returncode == 0:
                    success_count += 1

            except subprocess.TimeoutExpired:
                continue

        return success_count, len(image_files)

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
