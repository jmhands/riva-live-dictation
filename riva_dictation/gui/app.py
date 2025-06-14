"""GUI application entry point (temporary shim).

This module will eventually contain the refactored GUI code. For now it simply
re-exports ``ModernDictationApp`` from the main app module so that other package modules can import it without changing functionality.
"""

from riva_dictation.app import ModernDictationApp

__all__ = ["ModernDictationApp"]