#!/usr/bin/env python3
"""
Real-time Streaming Dictation App using Riva
- Press F9 to start/stop streaming recognition
- See words appear in real-time as you speak
- Uses Riva's streaming API for immediate results
"""

import pyaudio
import threading
import time
import queue
from pynput import keyboard
from pynput.keyboard import Key, Listener
import pyautogui
import tkinter as tk
from tkinter import messagebox, scrolledtext
import sys
import numpy as np

# Riva client imports
try:
    import riva.client
    from riva.client import RecognitionConfig
    import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
    import riva.client.proto.riva_audio_pb2 as riva_audio_pb2
except ImportError:
    print("❌ nvidia-riva-client not installed!")
    print("Install with: pip install nvidia-riva-client")
    sys.exit(1)

class RealtimeDictationApp:
    def __init__(self):
        self.streaming = False
        self.audio_queue = queue.Queue()
        self.audio = None
        self.stream = None

        # Audio settings
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000

        # Riva settings
        self.riva_server = "localhost:50051"
        self.language_code = "en-US"

        # Text accumulation
        self.current_text = ""
        self.final_text = ""
        self.last_typed_length = 0  # Track what we've already typed

        # Initialize components
        self.audio = pyaudio.PyAudio()
        self.setup_microphone()
        self.setup_riva_client()
        self.setup_gui()
        self.setup_hotkeys()

    def setup_microphone(self):
        """Setup microphone"""
        try:
            default_device_info = self.audio.get_default_input_device_info()
            self.input_device_index = default_device_info['index']
            print(f"🎤 Using: {default_device_info['name']}")
        except Exception as e:
            print(f"❌ Microphone setup failed: {e}")
            self.input_device_index = None

    def setup_riva_client(self):
        """Initialize Riva client"""
        try:
            auth = riva.client.Auth(uri=self.riva_server, use_ssl=False)
            self.riva_asr = riva.client.ASRService(auth)
            print(f"✅ Connected to Riva at {self.riva_server}")
        except Exception as e:
            print(f"❌ Riva connection failed: {e}")
            self.riva_asr = None

    def setup_gui(self):
        """Create GUI with real-time text display"""
        self.root = tk.Tk()
        self.root.title("Real-time Dictation")
        self.root.geometry("600x400")
        self.root.attributes('-topmost', True)

        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Press F9 to start real-time dictation\nReady",
            font=("Arial", 12),
            fg="green"
        )
        self.status_label.pack(pady=10)

        # Real-time text display
        self.text_display = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            width=70,
            height=15,
            font=("Arial", 11)
        )
        self.text_display.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Control buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        self.start_btn = tk.Button(
            button_frame,
            text="Start Streaming (F9)",
            command=self.toggle_streaming,
            bg="lightgreen"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Control buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        self.start_btn = tk.Button(
            button_frame,
            text="Start Streaming (F9)",
            command=self.toggle_streaming,
            bg="lightgreen"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Auto-type toggle
        self.auto_type_var = tk.BooleanVar(value=True)
        self.auto_type_check = tk.Checkbutton(
            button_frame,
            text="Auto-type to cursor",
            variable=self.auto_type_var,
            font=("Arial", 10)
        )
        self.auto_type_check.pack(side=tk.LEFT, padx=5)

        self.clear_btn = tk.Button(
            button_frame,
            text="Clear Text",
            command=self.clear_text
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        self.type_btn = tk.Button(
            button_frame,
            text="Type All Text",
            command=self.type_all_text
        )
        self.type_btn.pack(side=tk.LEFT, padx=5)

        # Instructions
        instructions = tk.Label(
            self.root,
            text="F9: Start/Stop • ESC: Exit • Real-time streaming recognition",
            font=("Arial", 9),
            fg="gray"
        )
        instructions.pack(pady=5)

    def setup_hotkeys(self):
        """Setup hotkeys"""
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.toggle_streaming()
                elif key == keyboard.Key.esc:
                    self.quit_app()
            except AttributeError:
                pass

        self.listener = Listener(on_press=on_press)
        self.listener.start()

    def toggle_streaming(self):
        """Start or stop streaming"""
        if not self.streaming:
            self.start_streaming()
        else:
            self.stop_streaming()

    def start_streaming(self):
        """Start real-time streaming recognition"""
        if self.riva_asr is None:
            messagebox.showerror("Error", "Riva not connected")
            return

        if self.input_device_index is None:
            messagebox.showerror("Error", "No microphone available")
            return

        try:
            self.streaming = True
            self.current_text = ""

            # Update GUI
            self.status_label.config(text="🔴 STREAMING - Speaking in real-time...\nPress F9 to stop", fg="red")
            self.start_btn.config(text="Stop Streaming (F9)", bg="lightcoral")
            self.root.update()

            # Start audio capture thread
            self.audio_thread = threading.Thread(target=self._capture_audio)
            self.audio_thread.start()

            # Start Riva streaming thread
            self.riva_thread = threading.Thread(target=self._stream_to_riva)
            self.riva_thread.start()

            print("🎤 Started real-time streaming")

        except Exception as e:
            print(f"❌ Streaming start failed: {e}")
            self.streaming = False

    def stop_streaming(self):
        """Stop streaming"""
        self.streaming = False

        # Update GUI
        self.status_label.config(text="⏹️ Stopping stream...", fg="orange")
        self.root.update()

        # Stop audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        # Wait for threads
        if hasattr(self, 'audio_thread'):
            self.audio_thread.join(timeout=2)
        if hasattr(self, 'riva_thread'):
            self.riva_thread.join(timeout=2)

        # Update GUI
        self.status_label.config(text="Ready for next session\nPress F9 to start", fg="green")
        self.start_btn.config(text="Start Streaming (F9)", bg="lightgreen")

        print("⏹️ Stopped streaming")

    def _capture_audio(self):
        """Capture audio in background thread"""
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            while self.streaming:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                if self.streaming:  # Check again in case we stopped
                    self.audio_queue.put(data)

        except Exception as e:
            print(f"Audio capture error: {e}")

    def _stream_to_riva(self):
        """Stream audio to Riva for real-time recognition"""
        try:
            # Create streaming config
            streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                config=riva_asr_pb2.RecognitionConfig(
                    encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=self.rate,
                    language_code=self.language_code,
                    max_alternatives=3,
                    enable_automatic_punctuation=True
                ),
                interim_results=True  # Get partial results as we speak
            )

            # Create audio chunk generator
            def audio_generator():
                while self.streaming:
                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                        yield chunk
                    except queue.Empty:
                        continue

            # Start streaming recognition
            responses = self.riva_asr.streaming_response_generator(
                audio_generator(),
                streaming_config
            )

            # Process responses
            for response in responses:
                if not self.streaming:
                    break

                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript

                        if result.is_final:
                            # Final result - add to permanent text
                            self.final_text += transcript + " "
                            self.current_text = ""
                            print(f"✅ Final: '{transcript}'")

                            # Auto-type final text if enabled
                            if self.auto_type_var.get():
                                self._auto_type_new_text()
                        else:
                            # Interim result - show temporarily
                            self.current_text = transcript
                            print(f"⏳ Interim: '{transcript}'")

                        # Update display
                        self._update_display()

        except Exception as e:
            print(f"Riva streaming error: {e}")

    def _auto_type_new_text(self):
        """Auto-type only the new text that was just finalized"""
        try:
            # Get the total text length we should have typed
            current_total = len(self.final_text)

            # Calculate what's new since last typing
            if current_total > self.last_typed_length:
                new_text = self.final_text[self.last_typed_length:]

                # Type the new text to active window
                if new_text.strip():
                    pyautogui.typewrite(new_text)
                    print(f"⌨️ Auto-typed: '{new_text.strip()}'")

                # Update our tracking
                self.last_typed_length = current_total

        except Exception as e:
            print(f"Auto-type error: {e}")

    def _update_display(self):
        """Update the text display"""
        try:
            # Combine final and current text
            display_text = self.final_text + self.current_text

            # Update text widget
            self.text_display.delete(1.0, tk.END)
            self.text_display.insert(1.0, display_text)

            # Auto-scroll to end
            self.text_display.see(tk.END)

        except Exception as e:
            print(f"Display update error: {e}")

    def clear_text(self):
        """Clear all text"""
        self.final_text = ""
        self.current_text = ""
        self.last_typed_length = 0
        self.text_display.delete(1.0, tk.END)

    def type_all_text(self):
        """Type all accumulated text to active window"""
        full_text = (self.final_text + self.current_text).strip()
        if full_text:
            # Small delay then type
            time.sleep(0.1)
            pyautogui.typewrite(full_text)
            print(f"⌨️ Typed all text: '{full_text[:50]}...'")

    def start_streaming(self):
        """Start real-time streaming recognition"""
        if self.riva_asr is None:
            messagebox.showerror("Error", "Riva not connected")
            return

        if self.input_device_index is None:
            messagebox.showerror("Error", "No microphone available")
            return

        try:
            self.streaming = True
            self.current_text = ""
            self.last_typed_length = len(self.final_text)  # Reset typing tracker

            # Update GUI
            status_text = "🔴 STREAMING - Speaking in real-time..."
            if self.auto_type_var.get():
                status_text += "\n✍️ Auto-typing to cursor position"
            else:
                status_text += "\n📝 Text shown here only"
            status_text += "\nPress F9 to stop"

            self.status_label.config(text=status_text, fg="red")
            self.start_btn.config(text="Stop Streaming (F9)", bg="lightcoral")
            self.root.update()

            # Start audio capture thread
            self.audio_thread = threading.Thread(target=self._capture_audio)
            self.audio_thread.start()

            # Start Riva streaming thread
            self.riva_thread = threading.Thread(target=self._stream_to_riva)
            self.riva_thread.start()

            print("🎤 Started real-time streaming")
            if self.auto_type_var.get():
                print("✍️ Auto-typing enabled - text will appear at cursor")

        except Exception as e:
            print(f"❌ Streaming start failed: {e}")
            self.streaming = False

    def quit_app(self):
        """Clean shutdown"""
        self.streaming = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio:
            self.audio.terminate()

        if hasattr(self, 'listener'):
            self.listener.stop()

        self.root.quit()
        sys.exit(0)

    def run(self):
        """Start the application"""
        print("Real-time Dictation App Started")
        print("Press F9 to start/stop streaming")
        print("Words will appear in real-time as you speak!")
        self.root.mainloop()

if __name__ == "__main__":
    app = RealtimeDictationApp()
    app.run()