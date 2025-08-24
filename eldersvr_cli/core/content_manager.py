"""
Content Manager for backend API operations
Handles authentication, data fetching, and content downloads
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import urllib.request


class ContentManager:
    """Manages content operations with EldersVR backend API"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auth_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.company_info: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'EldersVR-CLI/1.0.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def authenticate(self, email: str, password: str) -> bool:
        """Authenticate with EldersVR backend API"""
        auth_endpoint = f"{self.config['backend']['api_url']}{self.config['backend']['auth_endpoint']}"
        auth_data = {
            "email": email,
            "password": password
        }
        
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
                    
                    return True
            
            return False
            
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self.auth_token is not None
    
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
    
    def download_file(self, url: str, local_path: str, chunk_size: int = 8192) -> bool:
        """Download a file from URL to local path"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Parse URL to get filename if not provided
            if os.path.isdir(local_path):
                filename = os.path.basename(urlparse(url).path)
                local_path = os.path.join(local_path, filename)
            
            # Download with progress indication for large files
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Print progress for large files (> 1MB)
                        if total_size > 1024 * 1024:
                            progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                            print(f"\rDownloading {os.path.basename(local_path)}: {progress:.1f}%", end='')
            
            if total_size > 1024 * 1024:
                print()  # New line after progress
            
            return True
            
        except (requests.RequestException, OSError, IOError) as e:
            print(f"Failed to download {url}: {e}")
            return False
    
    def download_all_assets(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Download all videos, thumbnails, and tag images"""
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
            'failed_downloads': 0
        }
        
        # Download video files
        print("Downloading videos...")
        for video in data.get("videos", []):
            # Download high resolution video
            if self.download_file(video["fileUrl"], f"{videos_dir}/{video['fileKey']}"):
                download_stats['videos_high'] += 1
            else:
                download_stats['failed_downloads'] += 1
            
            # Download low resolution video
            if self.download_file(video["fileUrlLow"], f"{videos_dir}/{video['fileKeyLow']}"):
                download_stats['videos_low'] += 1
            else:
                download_stats['failed_downloads'] += 1
            
            # Download thumbnail
            if self.download_file(video["thumbnailUrl"], f"{images_dir}/{video['thumbnailKey']}"):
                download_stats['thumbnails'] += 1
            else:
                download_stats['failed_downloads'] += 1
        
        # Download tag images
        print("Downloading tag images...")
        for tag in data.get("tags", []):
            if "imageUrl" in tag and tag["imageUrl"]:
                filename = tag["imageUrl"].split("/")[-1]
                if self.download_file(tag["imageUrl"], f"{images_dir}/{filename}"):
                    download_stats['tag_images'] += 1
                else:
                    download_stats['failed_downloads'] += 1
        
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
    
    def logout(self):
        """Clear authentication and session data"""
        self.auth_token = None
        self.user_info = None
        self.company_info = None
        
        # Remove auth header from session
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']