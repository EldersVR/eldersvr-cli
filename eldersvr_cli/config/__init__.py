"""
Configuration utilities for EldersVR CLI
"""

import json
import os
from typing import Dict, Any, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file or return default"""
    
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
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    # Return default configuration
    return get_default_config()


def get_default_config() -> Dict[str, Any]:
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


def save_config(config: Dict[str, Any], config_path: str = './eldersvr_config.json') -> bool:
    """Save configuration to file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return True
    except (IOError, TypeError):
        return False


__all__ = ['load_config', 'get_default_config', 'save_config']