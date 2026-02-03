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


class TestConfigValidation(unittest.TestCase):
    """Test enhanced configuration validation"""

    def setUp(self):
        from eldersvr_cli.cli import EldersVRCLI
        self.cli = EldersVRCLI()
        self.cli.config = get_default_config()

    def test_valid_config_passes(self):
        """Valid default config should have no issues"""
        issues = self.cli._validate_config(self.cli.config)
        self.assertEqual(len(issues), 0)

    def test_invalid_api_url_format(self):
        """api_url without http(s):// should fail"""
        self.cli.config['backend']['api_url'] = 'ftp://bad.url.com'
        issues = self.cli._validate_config(self.cli.config)
        self.assertTrue(any('api_url' in i for i in issues))

    def test_invalid_endpoint_format(self):
        """Endpoints not starting with / should fail"""
        self.cli.config['backend']['auth_endpoint'] = 'no-slash'
        issues = self.cli._validate_config(self.cli.config)
        self.assertTrue(any('auth_endpoint' in i for i in issues))

    def test_empty_device_path(self):
        """Empty device_path should fail"""
        self.cli.config['paths']['device_path'] = ''
        issues = self.cli._validate_config(self.cli.config)
        self.assertTrue(any('device_path' in i for i in issues))

    def test_invalid_download_settings(self):
        """Negative/zero download settings should fail"""
        self.cli.config['download'] = {
            'max_concurrent_downloads': 0,
            'timeout': -1,
            'retry_attempts': -1
        }
        issues = self.cli._validate_config(self.cli.config)
        self.assertTrue(any('max_concurrent_downloads' in i for i in issues))
        self.assertTrue(any('timeout' in i for i in issues))
        self.assertTrue(any('retry_attempts' in i for i in issues))

    def test_missing_auth_identifier(self):
        """Empty both username and email should fail"""
        self.cli.config['auth']['username'] = ''
        self.cli.config['auth']['email'] = ''
        issues = self.cli._validate_config(self.cli.config)
        self.assertTrue(any('username or email' in i for i in issues))

    def test_auth_username_only_passes(self):
        """Having only username (no email) should pass"""
        self.cli.config['auth']['username'] = 'mycompany'
        self.cli.config['auth']['email'] = ''
        issues = self.cli._validate_config(self.cli.config)
        self.assertFalse(any('username or email' in i for i in issues))

    def test_auth_email_only_passes(self):
        """Having only email (no username) should pass"""
        self.cli.config['auth']['username'] = ''
        self.cli.config['auth']['email'] = 'user@example.com'
        issues = self.cli._validate_config(self.cli.config)
        self.assertFalse(any('username or email' in i for i in issues))


class TestContentManagerValidation(unittest.TestCase):
    """Test ContentManager validation methods"""

    def setUp(self):
        self.config = get_default_config()
        self.cm = ContentManager(self.config)

    @patch.object(ContentManager, '_load_stored_token')
    def test_check_api_connectivity_success(self, mock_load):
        """API connectivity check returns True when reachable"""
        mock_response = Mock()
        mock_response.status_code = 200
        self.cm.session.get = Mock(return_value=mock_response)

        reachable, msg = self.cm.check_api_connectivity()
        self.assertTrue(reachable)
        self.assertIn('reachable', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_check_api_connectivity_connection_error(self, mock_load):
        """API connectivity check returns False on connection error"""
        import requests
        self.cm.session.get = Mock(side_effect=requests.ConnectionError("refused"))

        reachable, msg = self.cm.check_api_connectivity()
        self.assertFalse(reachable)
        self.assertIn('Cannot connect', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_check_api_connectivity_timeout(self, mock_load):
        """API connectivity check returns False on timeout"""
        import requests
        self.cm.session.get = Mock(side_effect=requests.Timeout("timed out"))

        reachable, msg = self.cm.check_api_connectivity()
        self.assertFalse(reachable)
        self.assertIn('timed out', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_validate_token_no_token(self, mock_load):
        """Token validation fails when no token is stored"""
        self.cm.auth_token = None
        valid, msg = self.cm.validate_token()
        self.assertFalse(valid)
        self.assertIn('No auth token', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_validate_token_valid(self, mock_load):
        """Token validation succeeds with 200 response"""
        self.cm.auth_token = 'valid-token'
        mock_response = Mock()
        mock_response.status_code = 200
        self.cm.session.get = Mock(return_value=mock_response)

        valid, msg = self.cm.validate_token()
        self.assertTrue(valid)
        self.assertIn('valid', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_validate_token_expired(self, mock_load):
        """Token validation fails with 401 response"""
        self.cm.auth_token = 'expired-token'
        mock_response = Mock()
        mock_response.status_code = 401
        self.cm.session.get = Mock(return_value=mock_response)

        valid, msg = self.cm.validate_token()
        self.assertFalse(valid)
        self.assertIn('expired', msg)

    @patch.object(ContentManager, '_load_stored_token')
    def test_validate_token_forbidden(self, mock_load):
        """Token validation passes with 403 (token recognized but limited permissions)"""
        self.cm.auth_token = 'valid-token'
        mock_response = Mock()
        mock_response.status_code = 403
        self.cm.session.get = Mock(return_value=mock_response)

        valid, msg = self.cm.validate_token()
        self.assertTrue(valid)
        self.assertIn('limited permissions', msg)


class TestPreflightCheck(unittest.TestCase):
    """Test CLI preflight check orchestration"""

    def setUp(self):
        from eldersvr_cli.cli import EldersVRCLI
        self.cli = EldersVRCLI()
        self.cli.config = get_default_config()
        self.cli.config['devices'] = {
            'master_serial': 'MASTER123',
            'slave_serial': 'SLAVE456'
        }

    def test_preflight_config_pass(self):
        """Preflight config check passes with valid config"""
        result = self.cli._preflight_check(['config'])
        self.assertTrue(result)

    def test_preflight_config_fail(self):
        """Preflight config check fails with invalid config"""
        self.cli.config['backend']['api_url'] = 'invalid-url'
        result = self.cli._preflight_check(['config'])
        self.assertFalse(result)

    @patch.object(ContentManager, '_load_stored_token')
    def test_preflight_api_pass(self, mock_load):
        """Preflight API check passes when reachable"""
        mock_cm = Mock()
        mock_cm.check_api_connectivity.return_value = (True, "API reachable")
        self.cli.content_manager = mock_cm

        result = self.cli._preflight_check(['api'])
        self.assertTrue(result)

    @patch.object(ContentManager, '_load_stored_token')
    def test_preflight_api_fail(self, mock_load):
        """Preflight API check fails when unreachable"""
        mock_cm = Mock()
        mock_cm.check_api_connectivity.return_value = (False, "Cannot connect")
        self.cli.content_manager = mock_cm

        result = self.cli._preflight_check(['api'])
        self.assertFalse(result)

    @patch.object(ContentManager, '_load_stored_token')
    def test_preflight_auth_pass(self, mock_load):
        """Preflight auth check passes with valid token"""
        mock_cm = Mock()
        mock_cm.check_api_connectivity.return_value = (True, "API reachable")
        mock_cm.validate_token.return_value = (True, "Token valid")
        self.cli.content_manager = mock_cm

        result = self.cli._preflight_check(['auth'])
        self.assertTrue(result)

    @patch.object(ContentManager, '_load_stored_token')
    def test_preflight_auth_fail_expired(self, mock_load):
        """Preflight auth check fails with expired token"""
        mock_cm = Mock()
        mock_cm.check_api_connectivity.return_value = (True, "API reachable")
        mock_cm.validate_token.return_value = (False, "Token expired")
        self.cli.content_manager = mock_cm

        result = self.cli._preflight_check(['auth'])
        self.assertFalse(result)

    @patch.object(ContentManager, '_load_stored_token')
    def test_preflight_auth_skipped_when_api_unreachable(self, mock_load):
        """Auth check is skipped when API is unreachable"""
        mock_cm = Mock()
        mock_cm.check_api_connectivity.return_value = (False, "Cannot connect")
        self.cli.content_manager = mock_cm

        result = self.cli._preflight_check(['auth'])
        self.assertFalse(result)
        # validate_token should not be called since API is down
        mock_cm.validate_token.assert_not_called()

    def test_preflight_data_pass(self):
        """Preflight data check passes with valid new_data.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.cli.config['paths']['local_downloads'] = temp_dir
            json_file = os.path.join(temp_dir, 'new_data.json')
            valid_data = {
                "lastModified": "01/01/2026",
                "videos": [],
                "tags": []
            }
            with open(json_file, 'w') as f:
                json.dump(valid_data, f)

            mock_cm = Mock()
            mock_cm.validate_json_data.return_value = []
            self.cli.content_manager = mock_cm

            result = self.cli._preflight_check(['data'])
            self.assertTrue(result)

    def test_preflight_data_fail_missing(self):
        """Preflight data check fails when new_data.json is missing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.cli.config['paths']['local_downloads'] = temp_dir
            result = self.cli._preflight_check(['data'])
            self.assertFalse(result)

    @patch('subprocess.run')
    def test_preflight_devices_pass(self, mock_run):
        """Preflight devices check passes when devices are connected"""
        # First call: adb version check, second: adb devices
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = """List of devices attached
MASTER123\tdevice product:phone model:SM device:beyond
SLAVE456\tdevice product:quest model:Quest device:hollywood
"""
        self.cli._ensure_managers_initialized()

        result = self.cli._preflight_check(['devices'])
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_preflight_devices_fail_disconnected(self, mock_run):
        """Preflight devices check fails when a device is missing"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = """List of devices attached
MASTER123\tdevice product:phone model:SM device:beyond
"""
        self.cli._ensure_managers_initialized()

        result = self.cli._preflight_check(['devices'])
        self.assertFalse(result)

    def test_preflight_devices_fail_none_configured(self):
        """Preflight devices check fails when no devices configured"""
        self.cli.config['devices'] = {'master_serial': '', 'slave_serial': ''}
        self.cli._ensure_managers_initialized()

        result = self.cli._preflight_check(['devices'])
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()