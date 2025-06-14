"""
Tests for Riva Dictation UI components
"""

import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from riva_dictation.gui.widgets import StatusWidget, CursorIndicator
from riva_dictation.app import ModernDictationApp

class TestStatusWidget(unittest.TestCase):
    """Test cases for StatusWidget"""

    def setUp(self):
        """Set up test environment"""
        # Create mock app
        self.app = MagicMock(spec=ModernDictationApp)
        self.app.config = MagicMock()
        self.app.config.get.return_value = True  # show_widget

        # Create widget
        self.widget = StatusWidget(self.app)
        self.widget.create_widget()

        # Process any pending GUI updates
        self.widget.root.update()

    def tearDown(self):
        """Clean up test environment"""
        if self.widget.root:
            self.widget.root.destroy()

    def test_init(self):
        """Test widget initialization"""
        self.assertIsNotNone(self.widget)
        self.assertIsNotNone(self.widget.root)
        self.assertIsNotNone(self.widget.status_label)
        self.assertIsNotNone(self.widget.message_label)

    def test_create_widget(self):
        """Test widget creation"""
        self.assertIsNotNone(self.widget.root)
        self.assertIsNotNone(self.widget.status_label)
        self.assertIsNotNone(self.widget.message_label)
        self.assertIsNotNone(self.widget.record_button)
        self.assertIsNotNone(self.widget.settings_button)

    def test_show_hide_widget(self):
        """Test widget visibility"""
        # Hide widget
        self.widget.hide_widget()
        self.assertFalse(self.widget.visible)

        # Show widget
        self.widget.show_widget()
        self.assertTrue(self.widget.visible)

    def test_process_gui_updates(self):
        """Test GUI update processing"""
        # Add test update to queue
        self.widget.gui_queue.put({
            'type': 'status',
            'status': 'Test Status',
            'message': 'Test Message'
        })

        # Process updates
        self.widget.process_gui_updates()

        # Verify labels were updated
        self.assertEqual(self.widget.status_label.cget("text"), "Test Status")
        self.assertEqual(self.widget.message_label.cget("text"), "Test Message")

    def test_update_status(self):
        """Test status update functionality"""
        # Update status
        self.widget.update_status("Test Status", "Test Message")

        # Process any pending GUI updates
        self.widget.root.update()

        # Verify labels were updated
        self.assertEqual(self.widget.status_label.cget("text"), "Test Status")
        self.assertEqual(self.widget.message_label.cget("text"), "Test Message")

class TestCursorIndicator(unittest.TestCase):
    """Test cases for CursorIndicator"""

    def setUp(self):
        """Set up test environment"""
        # Create mock app
        self.app = MagicMock(spec=ModernDictationApp)

        # Create indicator
        self.indicator = CursorIndicator(self.app)

    def tearDown(self):
        """Clean up test environment"""
        if self.indicator.indicator:
            self.indicator.indicator.destroy()

    def test_init(self):
        """Test indicator initialization"""
        self.assertIsNotNone(self.indicator)
        self.assertIsNone(self.indicator.indicator)
        self.assertFalse(self.indicator.visible)

    def test_show_hide_indicator(self):
        """Test indicator visibility"""
        # Show indicator
        self.indicator.show_indicator()
        self.assertTrue(self.indicator.visible)
        self.assertIsNotNone(self.indicator.indicator)

        # Hide indicator
        self.indicator.hide_indicator()
        self.assertFalse(self.indicator.visible)
        self.assertIsNone(self.indicator.indicator)

if __name__ == '__main__':
    unittest.main()