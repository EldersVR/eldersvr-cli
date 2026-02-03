"""
Content Manager for backend API operations
Handles authentication, data fetching, and content downloads
"""

import requests
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Callable
from urllib.parse import urlparse
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from ..utils import DownloadProgressTable


class ContentManager:
    """Manages content operations with EldersVR backend API"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auth_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.company_info: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
        self.token_file = os.path.expanduser("~/.eldersvr_auth_token")

        # Download configuration
        self.download_config = config.get('download', {})
        self.max_concurrent_downloads = self.download_config.get('max_concurrent_downloads', 4)
        self.chunk_size = self.download_config.get('chunk_size', 8192)
        self.timeout = self.download_config.get('timeout', 60)
        self.retry_attempts = self.download_config.get('retry_attempts', 3)
        self.retry_delay = self.download_config.get('retry_delay', 1.0)

        # Progress tracking
        self._download_stats_lock = Lock()
        self._current_downloads = 0

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'EldersVR-CLI/1.0.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        # Load existing token if available
        self._load_stored_token()

    def authenticate(self, password: str, username: str = '', email: str = '') -> bool:
        """Authenticate with EldersVR backend API.

        Args:
            password: Account password.
            username: Username for authentication (alternative to email).
            email: Email for authentication (alternative to username).
            At least one of username or email must be provided.
        """
        if not username and not email:
            print("Authentication failed: either username or email is required")
            return False

        auth_endpoint = f"{self.config['backend']['api_url']}{self.config['backend']['auth_endpoint']}"
        auth_data = {"password": password}
        if username:
            auth_data["username"] = username
        if email:
            auth_data["email"] = email

        try:
            response = self.session.post(auth_endpoint, json=auth_data, timeout=30)
            response.raise_for_status()

            result = response.json()

            if result.get("success") and "data" in result:
                data = result["data"]
                if data.get("success") and "accessToken" in data:
                    self.auth_token = data["accessToken"]
                    self.user_info = data.get("user", {})
                    self.company_info = data.get("company", {})

                    # Update session headers with auth token
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.auth_token}'
                    })

                    # Store token to disk
                    self._store_token()

                    return True

            return False

        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Authentication failed: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if currently authenticated (token exists locally)"""
        return self.auth_token is not None

    def check_api_connectivity(self) -> Tuple[bool, str]:
        """Check if the backend API is reachable.
        Returns (reachable, message).
        """
        api_url = self.config['backend']['api_url']
        try:
            response = self.session.get(api_url, timeout=10)
            return True, f"API reachable ({api_url})"
        except requests.ConnectionError:
            return False, f"Cannot connect to API at {api_url} - check network or URL"
        except requests.Timeout:
            return False, f"API connection timed out ({api_url})"
        except requests.RequestException as e:
            return False, f"API connectivity check failed: {e}"

    def validate_token(self) -> Tuple[bool, str]:
        """Actively validate the stored auth token against the API.
        Makes a lightweight request to verify the token is still accepted.
        Returns (is_valid, message).
        """
        if not self.auth_token:
            return False, "No auth token stored - please run 'auth' command"

        tags_endpoint = f"{self.config['backend']['api_url']}{self.config['backend']['tags_endpoint']}"
        try:
            response = self.session.get(tags_endpoint, timeout=15)
            if response.status_code == 200:
                return True, "Auth token is valid"
            elif response.status_code in (401, 403):
                return False, "Auth token expired or invalid - please run 'auth' command"
            else:
                return False, f"Unexpected API response (status {response.status_code}) during token validation"
        except requests.ConnectionError:
            return False, "Cannot reach API to validate token - check network"
        except requests.Timeout:
            return False, "API request timed out during token validation"
        except requests.RequestException as e:
            return False, f"Token validation failed: {e}"

    def fetch_tags(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch available tags from backend"""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Please call authenticate() first.")

        tags_endpoint = f"{self.config['backend']['api_url']}{self.config['backend']['tags_endpoint']}"

        try:
            response = self.session.get(tags_endpoint, timeout=30)
            response.raise_for_status()

            result = response.json()

            if result.get("success") and "data" in result:
                return result["data"]

            return None

        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Failed to fetch tags: {e}")
            return None

    def fetch_films(self) -> Optional[Dict[str, Any]]:
        """Fetch films data from backend"""
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Please call authenticate() first.")

        films_endpoint = f"{self.config['backend']['api_url']}{self.config['backend']['films_endpoint']}"

        try:
            response = self.session.get(films_endpoint, timeout=30)
            response.raise_for_status()

            result = response.json()

            if result.get("success") and "data" in result:
                return result["data"]

            return None

        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Failed to fetch films: {e}")
            return None

    def generate_new_data_json(self, films_data: Dict[str, Any], tags_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate new_data.json in mobile app format"""
        if not films_data or not tags_data:
            raise ValueError("Films data and tags data are required")

        # Transform films API response to mobile app format
        videos = []

        for film in films_data.get("films", []):
            video = {
                "id": str(film["id"]),
                "title": film["title"],
                "description": film["description"],
                "thumbnailKey": film["thumbnailKey"],
                "thumbnailUrl": film["thumbnailUrl"],
                "fileKeyLow": film["lowQualityFileKey"],
                "fileKey": film["fileKey"],
                "fileUrlLow": film["lowQualityFileUrl"],
                "fileUrl": film["fileUrl"],
                "isActive": film["isActive"],
                "tags": film.get("tags", [])
            }
            videos.append(video)

        # Generate final new_data.json structure
        new_data = {
            "lastModified": datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
            "videos": videos,
            "tags": tags_data
        }

        # Ensure downloads directory exists
        downloads_dir = self.config['paths']['local_downloads']
        os.makedirs(downloads_dir, exist_ok=True)

        # Save to local file
        json_file_path = f"{downloads_dir}/new_data.json"
        with open(json_file_path, "w", encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)

        return new_data

    def download_file(self, url: str, local_path: str, chunk_size: int = None,
                      progress_callback: Optional[Callable[[str, int, int], None]] = None) -> bool:
        """Download a file from URL to local path with retry logic"""
        if chunk_size is None:
            chunk_size = self.chunk_size

        for attempt in range(self.retry_attempts):
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                # Parse URL to get filename if not provided
                if os.path.isdir(local_path):
                    filename = os.path.basename(urlparse(url).path)
                    local_path = os.path.join(local_path, filename)

                # Download with progress indication for large files
                response = requests.get(url, stream=True, timeout=self.timeout)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                filename = os.path.basename(local_path)

                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # Call progress callback if provided
                            if progress_callback:
                                progress_callback(filename, downloaded_size, total_size)
                            elif total_size > 1024 * 1024:  # Fallback progress for large files
                                progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                                print(f"\rDownloading {filename}: {progress:.1f}%", end='')

                if total_size > 1024 * 1024 and not progress_callback:
                    print()  # New line after progress

                return True

            except (requests.RequestException, OSError, IOError) as e:
                if attempt < self.retry_attempts - 1:
                    print(f"Download attempt {attempt + 1} failed for {url}, retrying in {self.retry_delay}s: {e}")
                    time.sleep(self.retry_delay)
                else:
                    print(f"Failed to download {url} after {self.retry_attempts} attempts: {e}")
                    return False

        return False

    def _download_single_file(self, download_task: Dict[str, Any], progress_callback: Optional[Callable] = None) -> Tuple[bool, str, str]:
        """Download a single file (for use with ThreadPoolExecutor)"""
        url = download_task['url']
        local_path = download_task['local_path']
        file_type = download_task['file_type']

        success = self.download_file(url, local_path, progress_callback=progress_callback)
        return success, file_type, os.path.basename(local_path)

    def check_existing_files(self, download_tasks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Check which files already exist and get user confirmation for overrides"""
        existing_files = []
        tasks_to_download = []

        for task in download_tasks:
            if os.path.exists(task['local_path']):
                file_size = os.path.getsize(task['local_path'])
                filename = os.path.basename(task['local_path'])
                existing_files.append(f"{filename} ({self._format_file_size(file_size)})")
            else:
                tasks_to_download.append(task)

        if existing_files:
            print(f"\n{len(existing_files)} files already exist:")
            for i, file_info in enumerate(existing_files[:5], 1):  # Show first 5
                print(f"  {i}. {file_info}")

            if len(existing_files) > 5:
                print(f"  ... and {len(existing_files) - 5} more files")

            while True:
                choice = input("\nDo you want to (o)verride existing files, (s)kip them, or (c)ancel? [o/s/c]: ").lower().strip()
                if choice in ['o', 'override']:
                    return download_tasks, []  # Download all
                elif choice in ['s', 'skip']:
                    return tasks_to_download, [os.path.basename(task['local_path']) for task in download_tasks if task not in tasks_to_download]
                elif choice in ['c', 'cancel']:
                    print("Download cancelled by user")
                    return [], []
                else:
                    print("Please enter 'o' for override, 's' for skip, or 'c' for cancel")

        return download_tasks, []

    def _format_file_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"

    def download_all_assets(self, data: Dict[str, Any], parallel: bool = True, max_display_files: int = 3, quality: str = 'both') -> Dict[str, int]:
        """Download all videos, thumbnails, and tag images with optional parallel processing

        Args:
            data: The data dictionary containing videos and tags
            parallel: Whether to use parallel downloads
            max_display_files: Maximum number of files to display in progress table
            quality: Video quality to download ('high', 'low', or 'both')
        """
        downloads_dir = self.config['paths']['local_downloads']

        # Create subdirectories
        videos_dir = f"{downloads_dir}/videos"
        images_dir = f"{downloads_dir}/images"
        os.makedirs(videos_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)

        download_stats = {
            'videos_high': 0,
            'videos_low': 0,
            'thumbnails': 0,
            'tag_images': 0,
            'failed_downloads': 0,
            'total_files': 0,
            'completed_files': 0,
            'skipped_files': 0
        }

        # Prepare download tasks
        download_tasks = []

        # Add video file tasks based on quality parameter
        for video in data.get("videos", []):
            # High resolution video
            if quality in ['high', 'both']:
                download_tasks.append({
                    'url': video["fileUrl"],
                    'local_path': f"{videos_dir}/{video['fileKey']}",
                    'file_type': 'videos_high'
                })

            # Low resolution video
            if quality in ['low', 'both']:
                download_tasks.append({
                    'url': video["fileUrlLow"],
                    'local_path': f"{videos_dir}/{video['fileKeyLow']}",
                    'file_type': 'videos_low'
                })

            # Thumbnail (always download with videos)
            download_tasks.append({
                'url': video["thumbnailUrl"],
                'local_path': f"{images_dir}/{video['thumbnailKey']}",
                'file_type': 'thumbnails'
            })

        # Add tag image tasks
        for tag in data.get("tags", []):
            if "imageUrl" in tag and tag["imageUrl"]:
                filename = tag["imageUrl"].split("/")[-1]
                download_tasks.append({
                    'url': tag["imageUrl"],
                    'local_path': f"{images_dir}/{filename}",
                    'file_type': 'tag_images'
                })

        # Check for existing files and get user confirmation
        tasks_to_download, skipped_files = self.check_existing_files(download_tasks)

        if not tasks_to_download:
            download_stats['total_files'] = len(download_tasks)
            download_stats['skipped_files'] = len(skipped_files)
            return download_stats

        download_stats['total_files'] = len(tasks_to_download)
        download_stats['skipped_files'] = len(skipped_files)

        if len(skipped_files) > 0:
            print(f"Skipping {len(skipped_files)} existing files")

        if parallel and len(tasks_to_download) > 1:
            return self._download_assets_parallel(tasks_to_download, download_stats, max_display_files)
        else:
            return self._download_assets_sequential(tasks_to_download, download_stats)

    def download_images_only(self, data: Dict[str, Any], parallel: bool = True, max_display_files: int = 3) -> Dict[str, int]:
        """Download only thumbnails and tag images (no videos)

        Args:
            data: The data dictionary containing videos and tags
            parallel: Whether to use parallel downloads
            max_display_files: Maximum number of files to display in progress table
        """
        downloads_dir = self.config['paths']['local_downloads']

        # Create images directory
        images_dir = f"{downloads_dir}/images"
        os.makedirs(images_dir, exist_ok=True)

        download_stats = {
            'thumbnails': 0,
            'tag_images': 0,
            'failed_downloads': 0,
            'total_files': 0,
            'completed_files': 0,
            'skipped_files': 0
        }

        # Prepare download tasks for images only
        download_tasks = []

        # Add thumbnail tasks
        for video in data.get("videos", []):
            download_tasks.append({
                'url': video["thumbnailUrl"],
                'local_path': f"{images_dir}/{video['thumbnailKey']}",
                'file_type': 'thumbnails'
            })

        # Add tag image tasks
        for tag in data.get("tags", []):
            if "imageUrl" in tag and tag["imageUrl"]:
                filename = tag["imageUrl"].split("/")[-1]
                download_tasks.append({
                    'url': tag["imageUrl"],
                    'local_path': f"{images_dir}/{filename}",
                    'file_type': 'tag_images'
                })

        # Check for existing files and get user confirmation
        tasks_to_download, skipped_files = self.check_existing_files(download_tasks)

        if not tasks_to_download:
            download_stats['total_files'] = len(download_tasks)
            download_stats['skipped_files'] = len(skipped_files)
            return download_stats

        download_stats['total_files'] = len(tasks_to_download)
        download_stats['skipped_files'] = len(skipped_files)

        if len(skipped_files) > 0:
            print(f"Skipping {len(skipped_files)} existing files")

        if parallel and len(tasks_to_download) > 1:
            return self._download_assets_parallel(tasks_to_download, download_stats, max_display_files)
        else:
            return self._download_assets_sequential(tasks_to_download, download_stats)

    def _download_assets_parallel(self, download_tasks: List[Dict[str, Any]],
                                  download_stats: Dict[str, int], max_display_files: int = 3) -> Dict[str, int]:
        """Download assets using parallel processing with table display"""
        print(f"Starting parallel downloads with {self.max_concurrent_downloads} concurrent connections...")
        print(f"Total files to download: {len(download_tasks)}")

        # Initialize progress table with configurable display limit
        progress_table = DownloadProgressTable(max_display_files=max_display_files)

        # Add all downloads to progress table
        for task in download_tasks:
            filename = os.path.basename(task['local_path'])
            progress_table.add_download(filename, task['file_type'], task['url'])

        # Create thread-safe progress callback
        def progress_callback(filename: str, downloaded: int, total: int):
            """Thread-safe progress callback for table updates"""
            progress_table.update_download(filename, downloaded, total, 'downloading')

        # Create enhanced download function that reports progress
        def download_with_progress(task):
            """Download a single file with progress reporting"""
            filename = os.path.basename(task['local_path'])
            try:
                # Mark as starting
                progress_table.update_download(filename, 0, 1, 'downloading')

                # Download the file
                success = self.download_file(
                    task['url'],
                    task['local_path'],
                    progress_callback=lambda fn, dl, tot: progress_callback(filename, dl, tot)
                )

                # Mark completion
                if success:
                    progress_table.mark_completed(filename, success=True)
                    return True, task['file_type'], filename
                else:
                    progress_table.mark_completed(filename, success=False, error="Download failed")
                    return False, task['file_type'], filename

            except Exception as e:
                progress_table.mark_completed(filename, success=False, error=str(e))
                return False, task['file_type'], filename

        with ThreadPoolExecutor(max_workers=self.max_concurrent_downloads) as executor:
            # Submit all download tasks
            future_to_task = {
                executor.submit(download_with_progress, task): task
                for task in download_tasks
            }

            # Process completed downloads
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success, file_type, filename = future.result()

                    with self._download_stats_lock:
                        download_stats['completed_files'] += 1

                        if success:
                            download_stats[file_type] += 1
                        else:
                            download_stats['failed_downloads'] += 1

                except Exception as e:
                    with self._download_stats_lock:
                        download_stats['completed_files'] += 1
                        download_stats['failed_downloads'] += 1
                        filename = os.path.basename(task['local_path'])

        # Show final summary
        progress_table.finish()

        return download_stats

    def _download_assets_sequential(self, download_tasks: List[Dict[str, Any]],
                                    download_stats: Dict[str, int]) -> Dict[str, int]:
        """Download assets sequentially (fallback method)"""
        print("Starting sequential downloads...")
        print(f"Total files to download: {len(download_tasks)}")

        for i, task in enumerate(download_tasks, 1):
            filename = os.path.basename(task['local_path'])
            print(f"[{i}/{len(download_tasks)}] Downloading {filename}...")

            success = self.download_file(task['url'], task['local_path'])

            download_stats['completed_files'] += 1

            if success:
                download_stats[task['file_type']] += 1
                print(f"✅ {filename}")
            else:
                download_stats['failed_downloads'] += 1
                print(f"❌ {filename} - FAILED")

        print("Sequential download completed!")
        return download_stats

    def get_download_summary(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Get summary of files that would be downloaded"""
        summary = {
            'total_videos': len(data.get("videos", [])) * 2,  # High + Low quality
            'total_thumbnails': len(data.get("videos", [])),
            'total_tag_images': len([tag for tag in data.get("tags", []) if tag.get("imageUrl")]),
            'estimated_files': 0
        }

        summary['estimated_files'] = (
            summary['total_videos'] +
            summary['total_thumbnails'] +
            summary['total_tag_images']
        )

        return summary

    def validate_json_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate new_data.json structure and return any issues"""
        issues = []

        # Check required top-level keys
        required_keys = ["lastModified", "videos", "tags"]
        for key in required_keys:
            if key not in data:
                issues.append(f"Missing required key: {key}")

        # Validate videos structure
        if "videos" in data:
            for i, video in enumerate(data["videos"]):
                video_issues = []
                required_video_keys = [
                    "id", "title", "description", "thumbnailKey", "thumbnailUrl",
                    "fileKeyLow", "fileKey", "fileUrlLow", "fileUrl", "isActive", "tags"
                ]

                for key in required_video_keys:
                    if key not in video:
                        video_issues.append(f"Missing key: {key}")

                if video_issues:
                    issues.append(f"Video {i}: {', '.join(video_issues)}")

        # Validate tags structure
        if "tags" in data:
            for i, tag in enumerate(data["tags"]):
                tag_issues = []
                required_tag_keys = ["id", "name"]

                for key in required_tag_keys:
                    if key not in tag:
                        tag_issues.append(f"Missing key: {key}")

                if tag_issues:
                    issues.append(f"Tag {i}: {', '.join(tag_issues)}")

        return issues

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get authenticated user information"""
        return self.user_info

    def get_company_info(self) -> Optional[Dict[str, Any]]:
        """Get company information"""
        return self.company_info

    def _store_token(self):
        """Store authentication token to disk"""
        if self.auth_token and self.user_info and self.company_info:
            token_data = {
                "token": self.auth_token,
                "user_info": self.user_info,
                "company_info": self.company_info
            }
            try:
                with open(self.token_file, 'w') as f:
                    json.dump(token_data, f)
                # Set restrictive permissions (readable only by owner)
                os.chmod(self.token_file, 0o600)
            except (IOError, OSError) as e:
                print(f"Warning: Could not store auth token: {e}")

    def _load_stored_token(self):
        """Load stored authentication token from disk"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)

                self.auth_token = token_data.get("token")
                self.user_info = token_data.get("user_info")
                self.company_info = token_data.get("company_info")

                if self.auth_token:
                    # Update session headers with stored token
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.auth_token}'
                    })
        except (IOError, json.JSONDecodeError, KeyError) as e:
            # Ignore errors loading stored token - user will need to re-authenticate
            pass

    def logout(self):
        """Clear authentication and session data"""
        self.auth_token = None
        self.user_info = None
        self.company_info = None

        # Remove auth header from session
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

        # Remove stored token file
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
        except OSError as e:
            print(f"Warning: Could not remove stored token: {e}")
