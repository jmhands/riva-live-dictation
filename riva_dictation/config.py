"""
Configuration management for Riva Dictation
"""

import json
from pathlib import Path
from typing import Dict, Any

class Config:
    """Configuration management with persistence"""

    DEFAULT_CONFIG = {
        "riva_server": "localhost:50051",
        "language_code": "en-US",
        "sample_rate": 16000,
        "auto_type": True,
        "show_widget": True,
        "hotkey": "f9",
        "theme": "dark",
        # LATENCY OPTIMIZATION PROFILES - ULTRA_LOW AS DEFAULT
        "latency_profile": "ultra_low",  # Set to ultra_low for maximum speed
        "chunk_size": 256,  # Ultra-low latency chunk size
        "queue_size": 5,   # Minimal queue for lowest latency
        "type_interval": 0.005,  # Ultra-fast typing
        "gui_fps_recording": 10,  # Minimal GUI updates during recording
        "gui_fps_idle": 30,  # Reduced idle updates for performance
        # CLOUD/ENDPOINT CONFIGURATION
        "use_ssl": False,  # Enable for cloud endpoints
        "endpoint_type": "local",  # "local", "custom"
        "custom_endpoint": "",  # For custom cloud endpoints
        "custom_asr_port": 50051,  # Custom ASR service port
        "custom_health_port": 8000,  # Custom health check port (if different from ASR)
        "use_separate_health_port": False,  # Enable separate health check port
        "connection_timeout": 30,  # Connection timeout in seconds
        "grpc_options": {},  # Additional gRPC channel options
        "auto_retry_ssl": True,  # Automatically try SSL if initial connection fails
        "connection_protocol": "grpc",  # "grpc", "grpc-web" (for HTTP proxies)
        "validate_streaming": True,  # Validate streaming capability during connection
        # ASR QUALITY SETTINGS
        "audio_encoding": "LINEAR_PCM",  # "LINEAR_PCM", "FLAC" (FLAC recommended for bandwidth)
        "max_alternatives": 1,  # Number of recognition hypotheses (1-5)
        "profanity_filter": False,  # Enable profanity filtering
        "verbatim_transcripts": False,  # True = exactly what was said, False = normalized text
        "model_name": "",  # Specific model to use (empty = auto-select)
        # SPEECH CONTEXT (for better recognition of specific terms)
        "speech_contexts": [],  # List of {"phrases": [...], "boost": float}
        # ENDPOINTING CONFIG (voice activity detection)
        "enable_endpointing": False,  # Enable custom endpointing
        "start_history_ms": 200,  # Start detection window (ms)
        "start_threshold": 0.3,  # Start detection threshold (0.0-1.0)
        "stop_history_ms": 800,  # Stop detection window (ms)
        "stop_threshold": 0.3,  # Stop detection threshold (0.0-1.0)
        # ENDPOINT PRESETS
        "endpoints": {
            "local": {
                "server": "localhost:50051",
                "use_ssl": False,
                "description": "Local Riva/Parakeet"
            }
        }
    }

    def __init__(self):
        self.config_file = Path.home() / ".riva_dictation_config.json"
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    config = self.DEFAULT_CONFIG.copy()
                    config.update(loaded)
                    return config
        except Exception as e:
            print(f"⚠️ Config load failed, using defaults: {e}")

        return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        """Save current configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"⚠️ Config save failed: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()