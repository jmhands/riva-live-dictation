"""
Tests for Riva Dictation application
"""

import unittest
from unittest.mock import MagicMock, patch
import queue
import numpy as np
import pyaudio
import riva.client
from riva.client import RecognitionConfig
import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
import riva.client.proto.riva_audio_pb2 as riva_audio_pb2
import time

from riva_dictation.app import ModernDictationApp
from riva_dictation.config import Config

class TestModernDictationApp(unittest.TestCase):
    """Test cases for ModernDictationApp"""

    def setUp(self):
        """Set up test environment"""
        # Mock PyAudio
        self.pyaudio_patcher = patch('pyaudio.PyAudio')
        self.mock_pyaudio = self.pyaudio_patcher.start()
        self.mock_stream = MagicMock()
        self.mock_pyaudio.return_value.open.return_value = self.mock_stream

        # Mock Riva client and config
        self.riva_client_patcher = patch('riva.client.ASRService')
        self.mock_riva_client = self.riva_client_patcher.start()

        # Mock GUI components
        self.status_widget_patcher = patch('riva_dictation.gui.widgets.StatusWidget')
        self.cursor_indicator_patcher = patch('riva_dictation.gui.widgets.CursorIndicator')
        self.systray_patcher = patch('infi.systray.SysTrayIcon')
        self.keyboard_patcher = patch('pynput.keyboard.Listener')

        self.mock_status_widget = self.status_widget_patcher.start()
        self.mock_cursor_indicator = self.cursor_indicator_patcher.start()
        self.mock_systray = self.systray_patcher.start()
        self.mock_keyboard = self.keyboard_patcher.start()

        # Create app instance
        self.app = ModernDictationApp()

        # Mock Riva client instance
        self.app.riva_client = MagicMock()
        self.app.riva_client.StreamingRecognize.return_value = []

        # Create a test audio queue
        self.app.audio_queue = queue.Queue()

    def tearDown(self):
        """Clean up test environment"""
        self.pyaudio_patcher.stop()
        self.riva_client_patcher.stop()
        self.status_widget_patcher.stop()
        self.cursor_indicator_patcher.stop()
        self.systray_patcher.stop()
        self.keyboard_patcher.stop()
        if hasattr(self.app, 'systray'):
            self.app.systray.shutdown()

    def test_init(self):
        """Test app initialization"""
        self.assertIsNotNone(self.app)
        self.assertIsNotNone(self.app.config)
        self.assertIsNotNone(self.app.status_widget)
        self.assertIsNotNone(self.app.cursor_indicator)

    def test_config_persistence(self):
        """Test configuration persistence"""
        # Test setting and getting config values
        self.app.config.set("test_key", "test_value")
        self.assertEqual(self.app.config.get("test_key"), "test_value")

    def test_riva_streaming(self):
        """Test Riva streaming functionality"""
        # Mock Riva streaming response
        mock_response = MagicMock()
        mock_response.results = [MagicMock()]
        mock_response.results[0].is_final = True
        mock_response.results[0].alternatives = [MagicMock()]
        mock_response.results[0].alternatives[0].transcript = "Test transcript"

        self.app.riva_client.StreamingRecognize.return_value = [mock_response]

        # Start recording
        self.app.start_recording()
        time.sleep(0.1)  # Give threads time to start

        # Verify Riva client was called
        self.app.riva_client.StreamingRecognize.assert_called_once()

        # Stop recording
        self.app.stop_recording()

    def test_toggle_recording(self):
        """Test recording toggle functionality"""
        with patch.object(self.app, '_capture_audio', side_effect=lambda: time.sleep(0.2)), \
             patch.object(self.app, '_stream_to_riva', side_effect=lambda: time.sleep(0.2)):
            # Start recording
            self.app.toggle_recording()
            time.sleep(0.05)  # Give threads time to start

            self.assertTrue(self.app.recording)
            self.assertIsNotNone(self.app.audio_thread)
            self.assertIsNotNone(self.app.riva_thread)
            self.assertTrue(self.app.audio_thread.is_alive())
            self.assertTrue(self.app.riva_thread.is_alive())

            # Stop recording
            self.app.toggle_recording()
            time.sleep(0.05)  # Give threads time to stop

            self.assertFalse(self.app.recording)
            # Threads may have exited, so just check they exist
            self.assertIsNotNone(self.app.audio_thread)
            self.assertIsNotNone(self.app.riva_thread)

    def test_audio_callback(self):
        """Test audio callback functionality"""
        # Create test audio data
        test_data = np.random.rand(1024).astype(np.float32).tobytes()

        # Call audio callback
        result = self.app._audio_callback(test_data, 1024, None, None)

        # Verify result
        self.assertEqual(result[0], test_data)
        self.assertEqual(result[1], pyaudio.paContinue)

    def test_auto_type(self):
        """Test auto-type functionality"""
        # Enable auto-type
        self.app.config.set("auto_type", True)

        # Mock pyautogui.write
        with patch('pyautogui.write') as mock_write:
            # Test with text that needs space
            self.app._auto_type_new_text("Hello")
            mock_write.assert_called_with("Hello ", interval=self.app.config.get("type_interval"))

            # Test with text that already has space
            self.app._auto_type_new_text("Hello ")
            mock_write.assert_called_with("Hello ", interval=self.app.config.get("type_interval"))

            # Test with text that ends with punctuation
            self.app._auto_type_new_text("Hello!")
            mock_write.assert_called_with("Hello!", interval=self.app.config.get("type_interval"))

if __name__ == '__main__':
    unittest.main()