#!/usr/bin/env python3
"""
Mac Parakeet-MLX Native Dictation App

Native macOS application using PyObjC and Cocoa for speech-to-text dictation.
Uses parakeet-mlx for real-time transcription.

Requirements:
- parakeet-mlx
- sounddevice  
- pyobjc (already installed)

Usage:
    python mac_parakeet_native.py
"""

import sys
import threading
import time
import queue
import subprocess
import numpy as np
from typing import Optional

try:
    import sounddevice as sd
    from parakeet_mlx import from_pretrained
    import mlx.core as mx  # Add MLX import
    
    # Native Mac UI imports
    import objc
    from Foundation import *
    from AppKit import *
    from PyObjCTools import AppHelper
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install required packages:")
    print("pip install parakeet-mlx sounddevice")
    sys.exit(1)


class SimpleAudioCapture:
    """Simple real-time audio capture using sounddevice."""
    
    def __init__(self, sample_rate: int = 16000, block_size: int = 1024):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stream = None
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback function for audio stream."""
        if status:
            print(f"Audio callback status: {status}")
        self.audio_queue.put(indata.copy())
    
    def start_recording(self):
        """Start recording audio from microphone."""
        if self.is_recording:
            return
        
        try:
            default_input = sd.query_devices(kind='input')
            print(f"Using default input device: {default_input['name']}")
            
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                blocksize=self.block_size,
                callback=self._audio_callback
            )
            
            self.stream.start()
            self.is_recording = True
            print("Started recording...")
            
        except Exception as e:
            print(f"Error starting audio recording: {e}")
            raise
    
    def stop_recording(self):
        """Stop recording audio."""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        print("Stopped recording...")
    
    def get_audio_chunk(self) -> Optional[np.ndarray]:
        """Get the next audio chunk from the queue."""
        try:
            chunk = self.audio_queue.get_nowait()
            if chunk.ndim > 1:
                chunk = chunk.flatten()
            return chunk
        except queue.Empty:
            return None


class ParakeetDictationApp(NSObject):
    """Native Mac application for Parakeet-MLX dictation."""
    
    def init(self):
        self = objc.super(ParakeetDictationApp, self).init()
        if self is None:
            return None
        
        # App state
        self.model = None
        self.audio_capture = None
        self.transcription_thread = None
        self.is_transcribing = False
        self.sample_rate = 16000
        
        # UI elements
        self.window = None
        self.text_view = None
        self.status_label = None
        self.start_button = None
        self.stop_button = None
        
        return self
    
    def applicationDidFinishLaunching_(self, notification):
        """Called when the application finishes launching."""
        print("Loading Parakeet-MLX model...")
        
        # Load model in background
        model_thread = threading.Thread(target=self.load_model, daemon=True)
        model_thread.start()
        
        # Create UI
        self.create_ui()
    
    def load_model(self):
        """Load the parakeet-mlx model."""
        try:
            self.model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2")
            print("Model loaded successfully!")
            
            # Update UI on main thread
            def update_ui():
                self.status_label.setStringValue_("Ready")
                self.status_label.setTextColor_(NSColor.systemGreenColor())
                self.start_button.setEnabled_(True)
            
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "updateUI:", update_ui, False)
                
        except Exception as e:
            print(f"Error loading model: {e}")
            
            def show_error():
                alert = NSAlert.alloc().init()
                alert.setMessageText_("Model Loading Error")
                alert.setInformativeText_(f"Failed to load model: {e}")
                alert.setAlertStyle_(NSCriticalAlertStyle)
                alert.runModal()
            
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "showError:", show_error, False)
    
    def updateUI_(self, update_func):
        """Helper to update UI on main thread."""
        update_func()
    
    def showError_(self, error_func):
        """Helper to show error on main thread."""
        error_func()
    
    def create_ui(self):
        """Create the native Mac UI."""
        # Create window
        frame = NSMakeRect(100, 100, 600, 500)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered,
            False
        )
        
        self.window.setTitle_("Parakeet-MLX Live Dictation")
        self.window.setDelegate_(self)
        
        # Create content view
        content_view = NSView.alloc().initWithFrame_(frame)
        self.window.setContentView_(content_view)
        
        # Title label
        title_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 450, 560, 30))
        title_label.setStringValue_("🎤 Parakeet-MLX Live Dictation")
        title_label.setBezeled_(False)
        title_label.setDrawsBackground_(False)
        title_label.setEditable_(False)
        title_label.setSelectable_(False)
        title_label.setFont_(NSFont.boldSystemFontOfSize_(18))
        title_label.setAlignment_(NSTextAlignmentCenter)
        content_view.addSubview_(title_label)
        
        # Status label
        self.status_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 410, 560, 20))
        self.status_label.setStringValue_("Loading model...")
        self.status_label.setBezeled_(False)
        self.status_label.setDrawsBackground_(False)
        self.status_label.setEditable_(False)
        self.status_label.setSelectable_(False)
        self.status_label.setFont_(NSFont.systemFontOfSize_(14))
        self.status_label.setAlignment_(NSTextAlignmentCenter)
        self.status_label.setTextColor_(NSColor.systemOrangeColor())
        content_view.addSubview_(self.status_label)
        
        # Control buttons
        button_y = 370
        button_width = 140
        button_height = 32
        button_spacing = 20
        
        # Start button
        self.start_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(120, button_y, button_width, button_height))
        self.start_button.setTitle_("🎤 Start Dictation")
        self.start_button.setBezelStyle_(NSRoundedBezelStyle)
        self.start_button.setTarget_(self)
        self.start_button.setAction_("startDictation:")
        self.start_button.setEnabled_(False)  # Disabled until model loads
        content_view.addSubview_(self.start_button)
        
        # Stop button
        self.stop_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(120 + button_width + button_spacing, button_y, button_width, button_height))
        self.stop_button.setTitle_("⏹ Stop Dictation")
        self.stop_button.setBezelStyle_(NSRoundedBezelStyle)
        self.stop_button.setTarget_(self)
        self.stop_button.setAction_("stopDictation:")
        self.stop_button.setEnabled_(False)
        content_view.addSubview_(self.stop_button)
        
        # Clear button
        clear_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(240, button_y - 40, 120, button_height))
        clear_button.setTitle_("🗑 Clear Text")
        clear_button.setBezelStyle_(NSRoundedBezelStyle)
        clear_button.setTarget_(self)
        clear_button.setAction_("clearText:")
        content_view.addSubview_(clear_button)
        
        # Text view for transcription
        scroll_view = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, 20, 560, 300))
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutohidesScrollers_(True)
        scroll_view.setBorderType_(NSBezelBorder)
        
        self.text_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 560, 300))
        self.text_view.setEditable_(True)
        self.text_view.setSelectable_(True)
        self.text_view.setFont_(NSFont.systemFontOfSize_(14))
        self.text_view.setString_("Transcribed text will appear here...")
        
        scroll_view.setDocumentView_(self.text_view)
        content_view.addSubview_(scroll_view)
        
        # Show window
        self.window.makeKeyAndOrderFront_(None)
        self.window.center()
    
    def startDictation_(self, sender):
        """Start dictation."""
        if self.is_transcribing or not self.model:
            return
        
        try:
            # Initialize audio capture
            self.audio_capture = SimpleAudioCapture(sample_rate=self.sample_rate)
            self.audio_capture.start_recording()
            
            # Start transcription
            self.is_transcribing = True
            self.transcription_thread = threading.Thread(target=self.transcription_worker, daemon=True)
            self.transcription_thread.start()
            
            # Update UI
            self.status_label.setStringValue_("🔴 Recording...")
            self.status_label.setTextColor_(NSColor.systemRedColor())
            self.start_button.setEnabled_(False)
            self.stop_button.setEnabled_(True)
            
            print("Started live dictation")
            
        except Exception as e:
            print(f"Error starting dictation: {e}")
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Error Starting Dictation")
            alert.setInformativeText_(str(e))
            alert.setAlertStyle_(NSCriticalAlertStyle)
            alert.runModal()
    
    def stopDictation_(self, sender):
        """Stop dictation."""
        if not self.is_transcribing:
            return
        
        # Stop transcription
        self.is_transcribing = False
        
        # Stop audio capture
        if self.audio_capture:
            self.audio_capture.stop_recording()
            self.audio_capture = None
        
        # Wait for transcription thread to finish
        if self.transcription_thread and self.transcription_thread.is_alive():
            self.transcription_thread.join(timeout=2.0)
        
        # Update UI
        self.status_label.setStringValue_("✅ Ready")
        self.status_label.setTextColor_(NSColor.systemGreenColor())
        self.start_button.setEnabled_(True)
        self.stop_button.setEnabled_(False)
        
        print("Stopped live dictation")
    
    def clearText_(self, sender):
        """Clear the transcription text."""
        self.text_view.setString_("")
    
    def transcription_worker(self):
        """Worker thread for real-time transcription."""
        try:
            # Balanced context for good performance and accuracy
            with self.model.transcribe_stream(context_size=(192, 192)) as transcriber:
                audio_buffer = []  # Use list for accumulating samples
                buffer_duration = 0.3  # Balanced buffer for good latency
                buffer_samples = int(self.sample_rate * buffer_duration)
                min_buffer_samples = int(self.sample_rate * 0.2)  # Process at 200ms intervals
                last_text = ""
                last_auto_typed_text = ""  # Track what we've already auto-typed
                
                while self.is_transcribing:
                    chunk = self.audio_capture.get_audio_chunk()
                    
                    if chunk is not None:
                        # Convert chunk to list and extend buffer
                        if isinstance(chunk, np.ndarray):
                            audio_buffer.extend(chunk.flatten().tolist())
                        else:
                            audio_buffer.extend(np.array(chunk).flatten().tolist())
                        
                        # Process when we have enough audio
                        if len(audio_buffer) >= min_buffer_samples:
                            # Use appropriate chunk size
                            process_samples = min(len(audio_buffer), buffer_samples)
                            buffer_data = audio_buffer[:process_samples]
                            
                            # Ensure we have enough data for the model
                            if len(buffer_data) >= min_buffer_samples:
                                mlx_array = mx.array(buffer_data, dtype=mx.float32)
                                
                                # Send audio to transcriber
                                transcriber.add_audio(mlx_array)
                                
                                # Get result
                                result = transcriber.result
                                current_text = result.text.strip()
                                
                                # Only update if text actually changed and is meaningful
                                if (current_text and 
                                    current_text != last_text and 
                                    len(current_text) > len(last_text) * 0.7):  # Avoid glitchy partial updates
                                    
                                    self.update_transcription_display(current_text)
                                    
                                    # Smart auto-typing: only type new parts
                                    if len(current_text) > len(last_auto_typed_text):
                                        # Find the new part that hasn't been typed yet
                                        if current_text.startswith(last_auto_typed_text):
                                            new_part = current_text[len(last_auto_typed_text):]
                                            if new_part.strip():  # Only type if there's meaningful new content
                                                self.auto_type_text_smart(new_part)
                                                last_auto_typed_text = current_text
                                    
                                    last_text = current_text
                                
                                # Keep reasonable overlap for context
                                overlap_samples = min_buffer_samples // 4  # Smaller overlap to reduce duplicates
                                audio_buffer = audio_buffer[process_samples - overlap_samples:]
                    else:
                        time.sleep(0.01)  # Reasonable sleep time
                        
        except Exception as e:
            print(f"Error in transcription worker: {e}")
            import traceback
            traceback.print_exc()
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "stopDictation:", None, False)
    
    def update_transcription_display(self, text):
        """Update the transcription display."""
        def update():
            self.text_view.setString_(text)
            # Scroll to bottom
            self.text_view.scrollRangeToVisible_(NSMakeRange(len(text), 0))
        
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "updateUI:", update, False)
    
    def auto_type_text_smart(self, new_text):
        """Smart auto-type that only types new text parts."""
        try:
            if new_text and new_text.strip():
                # Clean up the text to avoid weird characters
                clean_text = new_text.strip()
                
                # Escape special characters for AppleScript
                escaped_text = clean_text.replace('"', '\\"').replace('\\', '\\\\')
                script = f'tell application "System Events" to keystroke "{escaped_text}"'
                subprocess.run(['osascript', '-e', script], check=False)
        except Exception as e:
            print(f"Error in smart auto-type: {e}")
    
    def auto_type_text(self, current_text, last_text):
        """Legacy auto-type method - keeping for compatibility."""
        # This method is now replaced by auto_type_text_smart
        pass
    
    def windowWillClose_(self, notification):
        """Called when window is about to close."""
        self.stopDictation_(None)
        NSApp.terminate_(None)


def main():
    """Main entry point."""
    print("=" * 50)
    print("Mac Parakeet-MLX Native Dictation")
    print("=" * 50)
    
    # Create application
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    
    # Create app delegate
    delegate = ParakeetDictationApp.alloc().init()
    app.setDelegate_(delegate)
    
    # Run the app
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main() 