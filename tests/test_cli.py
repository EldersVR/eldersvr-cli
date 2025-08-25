"""
Basic tests for EldersVR CLI functionality
"""

import unittest
from unittest.mock import Mock, patch
import json
import tempfile
import os

from eldersvr_cli.core import ADBManager, ContentManager
from eldersvr_cli.config import load_config, get_default_config


class TestCLIBasics(unittest.TestCase):
    """Test basic CLI functionality"""
    
    def test_default_config_loading(self):
        """Test default configuration loading"""
        config = get_default_config()
        
        self.assertIn('backend', config)
        self.assertIn('paths', config)
        self.assertIn('devices', config)
        self.assertIn('auth', config)
        
        self.assertEqual(config['backend']['api_url'], 'https://api.eldersvr.com')
    
    def test_config_loading_from_file(self):
        """Test configuration loading from file"""
        test_config = {
            "backend": {"api_url": "https://test.api.com"},
            "auth": {"email": "test@test.com", "password": "testpass"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            self.assertEqual(config['backend']['api_url'], 'https://test.api.com')
            self.assertEqual(config['auth']['email'], 'test@test.com')
        finally:
            os.unlink(config_path)
    
    def test_adb_manager_initialization(self):
        """Test ADB manager initialization"""
        adb_manager = ADBManager()
        
        self.assertEqual(adb_manager.eldersvr_path, '/storage/emulated/0/Download/EldersVR')
        self.assertEqual(adb_manager.video_path, '/storage/emulated/0/Download/EldersVR/Video')
        self.assertEqual(adb_manager.image_path, '/storage/emulated/0/Download/EldersVR/Image')
    
    def test_adb_manager_custom_device_path(self):
        """Test ADB manager initialization with custom device path"""
        custom_path = "/sdcard/MyCustomPath"
        adb_manager = ADBManager(custom_path)
        
        self.assertEqual(adb_manager.eldersvr_path, custom_path)
        self.assertEqual(adb_manager.video_path, f"{custom_path}/Video")
        self.assertEqual(adb_manager.image_path, f"{custom_path}/Image")
    
    def test_content_manager_initialization(self):
        """Test content manager initialization"""
        config = get_default_config()
        content_manager = ContentManager(config)
        
        self.assertEqual(content_manager.config, config)
        self.assertIsNone(content_manager.auth_token)
        self.assertIsNone(content_manager.user_info)
        self.assertIsNone(content_manager.company_info)
    
    @patch('subprocess.run')
    def test_adb_version_check(self, mock_run):
        """Test ADB version check"""
        # Mock successful ADB version check
        mock_run.return_value.returncode = 0
        
        adb_manager = ADBManager()
        result = adb_manager.verify_adb_available()
        
        self.assertTrue(result)
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_adb_devices_list(self, mock_run):
        """Test ADB devices listing"""
        # Mock ADB devices output
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = """List of devices attached
ABC123DEF456	device product:phone model:Samsung_SM_G973F device:beyond1lte
XYZ789GHI012	device product:quest model:Meta_Quest_2 device:hollywood
"""
        
        adb_manager = ADBManager()
        devices = adb_manager.get_connected_devices()
        
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]['serial'], 'ABC123DEF456')
        self.assertEqual(devices[0]['model'], 'Samsung_SM_G973F')
        self.assertEqual(devices[1]['serial'], 'XYZ789GHI012')
        self.assertEqual(devices[1]['model'], 'Meta_Quest_2')
    
    def test_new_data_json_generation(self):
        """Test new_data.json generation"""
        config = get_default_config()
        content_manager = ContentManager(config)
        
        # Mock film data
        films_data = {
            "films": [
                {
                    "id": 1,
                    "title": "Test Video",
                    "description": "Test Description",
                    "thumbnailKey": "thumb_1.jpg",
                    "thumbnailUrl": "https://example.com/thumb_1.jpg",
                    "lowQualityFileKey": "lowres_1.mp4",
                    "fileKey": "highres_1.mp4",
                    "lowQualityFileUrl": "https://example.com/lowres_1.mp4",
                    "fileUrl": "https://example.com/highres_1.mp4",
                    "isActive": True,
                    "tags": []
                }
            ]
        }
        
        # Mock tags data
        tags_data = [
            {
                "id": 1,
                "name": "Test Tag",
                "imageUrl": "https://example.com/tag_1.jpg"
            }
        ]
        
        # Create temporary downloads directory
        with tempfile.TemporaryDirectory() as temp_dir:
            config['paths']['local_downloads'] = temp_dir
            
            result = content_manager.generate_new_data_json(films_data, tags_data)
            
            # Check structure
            self.assertIn('lastModified', result)
            self.assertIn('videos', result)
            self.assertIn('tags', result)
            
            # Check video transformation
            self.assertEqual(len(result['videos']), 1)
            video = result['videos'][0]
            self.assertEqual(video['id'], '1')
            self.assertEqual(video['title'], 'Test Video')
            self.assertEqual(video['fileKey'], 'highres_1.mp4')
            self.assertEqual(video['fileKeyLow'], 'lowres_1.mp4')
            
            # Check tags
            self.assertEqual(len(result['tags']), 1)
            self.assertEqual(result['tags'][0]['name'], 'Test Tag')
            
            # Check file was created
            json_file = os.path.join(temp_dir, 'new_data.json')
            self.assertTrue(os.path.exists(json_file))
    
    def test_data_validation(self):
        """Test JSON data validation"""
        config = get_default_config()
        content_manager = ContentManager(config)
        
        # Valid data
        valid_data = {
            "lastModified": "08/22/2025 08:46:06",
            "videos": [
                {
                    "id": "1",
                    "title": "Test",
                    "description": "Test",
                    "thumbnailKey": "thumb.jpg",
                    "thumbnailUrl": "https://example.com/thumb.jpg",
                    "fileKeyLow": "low.mp4",
                    "fileKey": "high.mp4",
                    "fileUrlLow": "https://example.com/low.mp4",
                    "fileUrl": "https://example.com/high.mp4",
                    "isActive": True,
                    "tags": []
                }
            ],
            "tags": [
                {
                    "id": 1,
                    "name": "Test Tag"
                }
            ]
        }
        
        issues = content_manager.validate_json_data(valid_data)
        self.assertEqual(len(issues), 0)
        
        # Invalid data - missing keys
        invalid_data = {
            "videos": [
                {
                    "id": "1",
                    "title": "Test"
                    # Missing required keys
                }
            ],
            "tags": []
            # Missing lastModified
        }
        
        issues = content_manager.validate_json_data(invalid_data)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any("Missing required key: lastModified" in issue for issue in issues))


if __name__ == '__main__':
    unittest.main()