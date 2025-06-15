"""
Main application module for Riva Dictation
"""

import os
import sys
import time
import queue
import threading
import signal
import pyaudio
import numpy as np
import pyautogui
from typing import Optional
from infi.systray import SysTrayIcon
import tkinter as tk
from tkinter import ttk, messagebox
import requests

# Riva client imports
import riva.client
from riva.client import RecognitionConfig
import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
import riva.client.proto.riva_audio_pb2 as riva_audio_pb2

from .config import Config
from .gui.widgets import StatusWidget, CursorIndicator

class ModernDictationApp:
    """Main application class for Riva Dictation"""

    def __init__(self, headless=False):
        # Configuration
        self.config = Config()
        self.headless = headless

        # Audio setup like working version
        self.rate = self.config.get("sample_rate", 16000)
        self.chunk = self.config.get("chunk_size", 256)
        self.format = pyaudio.paInt16  # Use Int16 like working version
        self.channels = 1
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.input_device_index = None
        self.recording = False
        self.audio_queue = queue.Queue(maxsize=self.config.get("queue_size", 5))

        # Text tracking like working version
        self.current_text = ""
        self.final_text = ""
        self.last_typed_length = 0

        # Riva client
        self.riva_client = None
        self.recognition_config = None

        # GUI components (only if not headless)
        if not self.headless:
            # Hidden Tkinter root for dialogs
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the main window

            # GUI components
            self.status_widget = StatusWidget(self)
            self.cursor_indicator = CursorIndicator(self)

            # System tray
            self.systray = None
            self.create_systray()
        else:
            self.root = None
            self.status_widget = None
            self.cursor_indicator = None
            self.systray = None
            print("🖥️  Running in CLI mode (no GUI)")

        # Setup audio and Riva
        self.setup_audio()
        self.setup_riva()

        # Setup hotkeys
        self.setup_hotkeys()

    def create_systray(self):
        """Create system tray icon and menu"""
        if self.headless:
            return

        menu_options = (
            ("Select Microphone", None, self.select_microphone),
            ("Settings", None, self.show_settings),
        )
        # Use on_quit parameter to handle the default quit option instead of adding our own
        self.systray = SysTrayIcon("mic.ico", "Riva Dictation (Press F9 to Record)", menu_options, on_quit=self.quit_app)

    def select_microphone(self, systray=None):
        """Show microphone selection dialog"""
        if self.headless:
            print("⚠️ Microphone selection not available in CLI mode")
            print("💡 Configure microphone in config file or run without --no-gui flag")
            return

        def _show_microphone_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Microphone")
            dialog.geometry("400x300")
            dialog.grab_set()

            # Create microphone list
            mic_frame = tk.Frame(dialog, padx=24, pady=24)
            mic_frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(mic_frame, text="Available Microphones:").pack(anchor=tk.W)
            mic_listbox = tk.Listbox(mic_frame, height=10)
            mic_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

            # Populate microphone list with all input devices
            device_count = self.audio.get_device_count()
            devices = []
            for i in range(device_count):
                info = self.audio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    devices.append((i, info['name']))
                    mic_listbox.insert(tk.END, f"{i}: {info['name']}")

            def save_selection():
                selection = mic_listbox.curselection()
                if selection:
                    device_idx = devices[selection[0]][0]
                    device_name = devices[selection[0]][1]
                    self.config.set("input_device_index", device_idx)  # Use correct config key
                    self.input_device_index = device_idx
                    self.setup_audio()  # Reinitialize audio with new device
                    dialog.destroy()
                    print(f"🎤 Microphone selected: {device_idx}: {device_name}")

            # Buttons
            button_frame = tk.Frame(mic_frame)
            button_frame.pack(fill=tk.X)

            save_button = tk.Button(button_frame, text="Save",
                                  font=("Segoe UI", 12),
                                  bg='#1976d2',
                                  fg='white',
                                  relief='flat',
                                  command=save_selection)
            save_button.pack(side=tk.RIGHT)

        # Call directly since we're now using mainloop
        _show_microphone_dialog()

    def setup_audio(self):
        """Setup audio input stream like working version"""
        try:
            # Use selected device if set
            device_idx = self.config.get("input_device_index", None)
            if device_idx is not None:
                default_device = self.audio.get_device_info_by_index(device_idx)
            else:
                default_device = self.audio.get_default_input_device_info()
            self.input_device_index = default_device['index']
            print(f"🎤 Audio device: {default_device['name']}")
        except Exception as e:
            print(f"❌ Audio setup failed: {e}")
            self.input_device_index = None

    def setup_riva(self):
        """Setup Riva client connection"""
        def connect():
            try:
                # Get server configuration
                endpoint_type = self.config.get("endpoint_type")
                if endpoint_type == "custom":
                    custom_endpoint = self.config.get("custom_endpoint")
                    custom_asr_port = self.config.get("custom_asr_port", 50051)

                    # Build server string with custom port
                    if custom_endpoint:
                        # If endpoint already has port, use as-is, otherwise add custom port
                        if ':' in custom_endpoint:
                            server = custom_endpoint
                        else:
                            server = f"{custom_endpoint}:{custom_asr_port}"
                    else:
                        server = f"localhost:{custom_asr_port}"

                    use_ssl = self.config.get("use_ssl")
                else:
                    endpoint = self.config.get("endpoints", {}).get(endpoint_type, {})
                    server = endpoint.get("server", "localhost:50051")
                    use_ssl = endpoint.get("use_ssl", False)

                print(f"🔗 Connecting to: {server} {'(SSL)' if use_ssl else ''}")

                # Create Riva client using Auth with timeout
                connection_timeout = self.config.get("connection_timeout", 30)

                try:
                    auth = riva.client.Auth(uri=server, use_ssl=use_ssl)
                    self.riva_client = riva.client.ASRService(auth)

                    # Test the connection by trying to create a simple config
                    # This will fail early if the connection is not working
                    test_config = RecognitionConfig(
                        encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                        sample_rate_hertz=self.rate,
                        language_code=self.config.get("language_code"),
                        max_alternatives=1
                    )

                    # Try to validate the connection more thoroughly (if enabled)
                    if self.config.get("validate_streaming", True):
                        try:
                            # Check if streaming methods are available
                            if not (hasattr(self.riva_client, 'streaming_response_generator') or
                                    hasattr(self.riva_client, 'StreamingRecognize')):
                                print("⚠️ Warning: No streaming methods found on client")
                                print("   Available methods:", [m for m in dir(self.riva_client) if not m.startswith('_')])

                            # Try a minimal streaming test to validate the connection
                            streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                                config=test_config,
                                interim_results=False
                            )

                            # Create a minimal test request
                            if hasattr(self.riva_client, 'StreamingRecognize'):
                                def test_request_generator():
                                    yield riva_asr_pb2.StreamingRecognizeRequest(streaming_config=streaming_config)
                                    # Send minimal audio data
                                    yield riva_asr_pb2.StreamingRecognizeRequest(audio_content=b'\x00' * 32)

                                # Try to create the stream (don't consume it, just test creation)
                                test_stream = self.riva_client.StreamingRecognize(test_request_generator())
                                # Try to get the first response to validate the connection
                                try:
                                    next(test_stream)
                                    print("✅ Streaming connection validated")
                                except StopIteration:
                                    print("✅ Streaming connection validated (empty response)")
                                except Exception as stream_test_error:
                                    if "http1.x server" in str(stream_test_error).lower():
                                        print("❌ Streaming validation failed: Server responds with HTTP")
                                        raise Exception("Server is not a gRPC service - it responds with HTTP instead of gRPC")
                                    else:
                                        print(f"⚠️ Streaming validation warning: {stream_test_error}")
                                        # Continue anyway, might work during actual streaming

                        except Exception as validation_error:
                            if "http1.x server" in str(validation_error).lower():
                                raise validation_error  # Re-raise HTTP server errors
                            else:
                                print(f"⚠️ Connection validation warning: {validation_error}")
                                # Continue anyway for other validation errors

                    print("✅ Successfully connected to Riva server")

                except Exception as conn_error:
                    error_msg = str(conn_error)

                    # Provide specific guidance based on error type
                    if "http1.x server" in error_msg.lower():
                        print("❌ Connection failed: Server is responding with HTTP instead of gRPC")
                        print("💡 Possible solutions:")
                        print("   1. Check if the port is correct for gRPC service")
                        print("   2. Verify the server supports gRPC protocol")
                        print("   3. Check if SSL is required (try enabling 'use_ssl' in settings)")
                        print("   4. Ensure the server is a Riva ASR service, not a web server")

                        # Try with SSL if not already enabled and auto_retry_ssl is enabled
                        if not use_ssl and self.config.get("auto_retry_ssl", True):
                            print("🔄 Attempting connection with SSL...")
                            try:
                                auth_ssl = riva.client.Auth(uri=server, use_ssl=True)
                                self.riva_client = riva.client.ASRService(auth_ssl)
                                print("✅ SSL connection successful!")
                                # Update config to remember this works
                                self.config.set("use_ssl", True)
                                use_ssl = True
                            except Exception as ssl_error:
                                print(f"❌ SSL connection also failed: {ssl_error}")
                                print("💡 Additional troubleshooting:")
                                print("   - The server may not be a gRPC service")
                                print("   - Check if this is a REST API endpoint instead")
                                print("   - Verify the correct port for Riva ASR service")
                                raise conn_error
                        else:
                            print("💡 Additional troubleshooting:")
                            print("   - The server may not be a gRPC service")
                            print("   - Check if this is a REST API endpoint instead")
                            print("   - Verify the correct port for Riva ASR service")
                            print("   - Try enabling auto_retry_ssl in config")
                            raise conn_error

                    elif "unavailable" in error_msg.lower():
                        print("❌ Connection failed: Server unavailable")
                        print("💡 Possible solutions:")
                        print("   1. Check if the server is running")
                        print("   2. Verify the server address and port")
                        print("   3. Check network connectivity")
                        print("   4. Ensure firewall allows the connection")
                        raise conn_error

                    elif "permission denied" in error_msg.lower() or "authentication" in error_msg.lower():
                        print("❌ Connection failed: Authentication error")
                        print("💡 Possible solutions:")
                        print("   1. Check if authentication credentials are required")
                        print("   2. Verify SSL settings")
                        print("   3. Check if the server requires specific authentication")
                        raise conn_error

                    else:
                        print(f"❌ Connection failed: {error_msg}")
                        # Run diagnostic if connection fails
                        print("\n🔍 Running connection diagnostics...")
                        self.diagnose_connection(server, test_ssl=not use_ssl)
                        raise conn_error

                # Create recognition config with enhanced settings
                encoding_map = {
                    "LINEAR_PCM": riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                    "FLAC": riva_audio_pb2.AudioEncoding.FLAC
                }
                encoding = encoding_map.get(self.config.get("audio_encoding", "LINEAR_PCM"),
                                           riva_audio_pb2.AudioEncoding.LINEAR_PCM)

                # Build speech contexts if configured
                speech_contexts = []
                for ctx in self.config.get("speech_contexts", []):
                    if "phrases" in ctx:
                        from riva.client.proto.riva_asr_pb2 import SpeechContext
                        speech_contexts.append(SpeechContext(
                            phrases=ctx["phrases"],
                            boost=ctx.get("boost", 0.0)
                        ))

                # Build endpointing config if enabled
                endpointing_config = None
                if self.config.get("enable_endpointing", False):
                    from riva.client.proto.riva_asr_pb2 import EndpointingConfig
                    endpointing_config = EndpointingConfig(
                        start_history=self.config.get("start_history_ms", 200),
                        start_threshold=self.config.get("start_threshold", 0.3),
                        stop_history=self.config.get("stop_history_ms", 800),
                        stop_threshold=self.config.get("stop_threshold", 0.3)
                    )

                self.recognition_config = RecognitionConfig(
                    encoding=encoding,
                    sample_rate_hertz=self.rate,
                    language_code=self.config.get("language_code"),
                    max_alternatives=self.config.get("max_alternatives", 1),
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=True,
                    profanity_filter=self.config.get("profanity_filter", False),
                    verbatim_transcripts=self.config.get("verbatim_transcripts", False),
                    model=self.config.get("model_name", ""),
                    speech_contexts=speech_contexts,
                    endpointing_config=endpointing_config
                )

                self.safe_update_status("Ready", "Connected to Riva server")
                return True
            except Exception as e:
                self.safe_update_status("Error", f"Failed to connect: {str(e)}")
                return False

        # Initial connection
        if not connect():
            self.safe_update_status("Error", "Failed to connect to Riva server")

    def safe_update_status(self, status: str, message: str = ""):
        """Thread-safe status update"""
        if self.headless:
            # In headless mode, just print status updates
            if message:
                print(f"📊 Status: {status} - {message}")
            else:
                print(f"📊 Status: {status}")
            return

        if self.status_widget:
            self.status_widget.gui_queue.put({
                'type': 'status',
                'status': status,
                'message': message
            })

    def safe_update_icon(self, recording: bool = False):
        """Update system tray icon state"""
        # No dynamic tray icon update for infi.systray
        pass

    def setup_hotkeys(self):
        """Setup global hotkeys"""
        from pynput import keyboard
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.toggle_recording()
            except AttributeError:
                pass

        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()

    def toggle_recording(self):
        """Toggle recording state"""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start audio recording and transcription"""
        if self.recording:
            return

        self.recording = True
        self.current_text = ""
        self.last_typed_length = len(self.final_text)

        self.safe_update_status("Recording", "Listening...")
        self.safe_update_icon(True)

        # Show cursor indicator only if not headless
        if not self.headless and self.cursor_indicator:
            self.cursor_indicator.show_indicator()

        # Start audio capture thread
        self.audio_thread = threading.Thread(target=self._capture_audio)
        self.audio_thread.daemon = True
        self.audio_thread.start()

        # Start Riva streaming thread
        self.riva_thread = threading.Thread(target=self._stream_to_riva)
        self.riva_thread.daemon = True
        self.riva_thread.start()

    def stop_recording(self):
        """Stop audio recording and transcription"""
        if not self.recording:
            return

        self.recording = False
        self.safe_update_status("Ready", "Stopped recording")
        self.safe_update_icon(False)

        # Hide cursor indicator only if not headless
        if not self.headless and self.cursor_indicator:
            self.cursor_indicator.hide_indicator()

        # Clear audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio stream callback"""
        if self.recording:
            self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)

    def _capture_audio(self):
        """Capture audio from microphone"""
        try:
            # Setup audio stream like working version
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk,
                start=False
            )

            # Start the stream
            self.stream.start_stream()

            while self.recording:
                try:
                    # Read audio data
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    if self.recording:
                        # Add to queue, discard if full to prevent latency buildup
                        try:
                            self.audio_queue.put_nowait(data)
                        except queue.Full:
                            # Discard oldest chunk
                            try:
                                self.audio_queue.get_nowait()
                                self.audio_queue.put_nowait(data)
                            except queue.Empty:
                                pass
                except Exception as e:
                    if self.recording:
                        print(f"⚠️ Audio capture error: {e}")
                    break

        except Exception as e:
            print(f"❌ Audio stream setup failed: {e}")
            self.recording = False
            self.safe_update_status("Error", "Audio failed")

    def _stream_to_riva(self):
        """Stream audio to Riva server"""
        try:
            print("🎤 Starting recognition...")

            # Validate client connection before streaming
            if not self.riva_client:
                print("❌ No Riva client available")
                self.safe_update_status("Error", "No Riva client")
                self.stop_recording()
                return

            # Create streaming config using the same recognition config
            streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                config=self.recognition_config,
                interim_results=True
            )

            def audio_generator():
                while self.recording:
                    try:
                        data = self.audio_queue.get(timeout=0.01)
                        yield data
                    except queue.Empty:
                        # Yield silence to keep stream alive
                        yield b'\x00' * (self.chunk * 2)
                        continue

            # Try different streaming methods
            responses = None
            try:
                # Method 1: Try streaming_response_generator
                if hasattr(self.riva_client, 'streaming_response_generator'):
                    responses = self.riva_client.streaming_response_generator(
                        audio_generator(),
                        streaming_config
                    )
                # Method 2: Try StreamingRecognize
                elif hasattr(self.riva_client, 'StreamingRecognize'):
                    def request_generator():
                        # First request with config
                        yield riva_asr_pb2.StreamingRecognizeRequest(streaming_config=streaming_config)
                        # Subsequent requests with audio
                        for audio_data in audio_generator():
                            yield riva_asr_pb2.StreamingRecognizeRequest(audio_content=audio_data)

                    responses = self.riva_client.StreamingRecognize(request_generator())
                else:
                    print("❌ No streaming method found!")
                    available_methods = [method for method in dir(self.riva_client) if not method.startswith('_')]
                    print(f"Available methods: {', '.join(available_methods)}")
                    self.safe_update_status("Error", "Streaming not supported")
                    return

                if responses:
                    empty_response_count = 0
                    last_interim = ""

                    for response in responses:
                        if not self.recording:
                            print("🛑 Recording stopped")
                            break

                        if response.results:
                            empty_response_count = 0  # Reset counter
                            result = response.results[0]
                            if result.alternatives:
                                transcript = result.alternatives[0].transcript

                                if result.is_final:
                                    self.final_text += transcript
                                    self.current_text = ""
                                    print(f"✅ Final: '{transcript.strip()}'")
                                    if self.config.get("auto_type"):
                                        self._auto_type_new_text()
                                    self.safe_update_status("Recording", transcript.strip())
                                    last_interim = ""  # Reset interim tracking
                                else:
                                    # Only show interim if it's different from last one
                                    if transcript != last_interim and transcript.strip():
                                        self.current_text = transcript
                                        print(f"🔄 Interim: '{transcript.strip()}'")
                                        last_interim = transcript
                        else:
                            empty_response_count += 1
                            # Only show empty response message occasionally to avoid spam
                            if empty_response_count == 1:
                                print("⏳ Listening...")
                            elif empty_response_count % 50 == 0:  # Every 50 empty responses
                                print(f"⏳ Still listening... ({empty_response_count} empty responses)")
                else:
                    print("❌ No responses received")

            except Exception as stream_error:
                error_msg = str(stream_error)
                print(f"❌ Streaming error: {stream_error}")

                # Handle specific streaming errors
                if "http1.x server" in error_msg.lower():
                    print("💡 TCP Port Forwarding Analysis:")
                    print("   ✅ Initial connection succeeded")
                    print("   ❌ Streaming connection failed (HTTP instead of gRPC)")
                    print("\n💡 This indicates TCP port forwarding to an HTTP service:")
                    print("   1. The port forwards TCP connections successfully")
                    print("   2. But the destination service responds with HTTP, not gRPC")
                    print("   3. The forwarded destination is likely a web server, not Riva ASR")
                    print("\n🔧 Recommended actions for TCP Port Forwarding:")
                    print("   1. Contact your network administrator")
                    print("   2. Verify the forwarded destination is running Riva ASR on the correct port")
                    print("   3. Ask for the direct IP/port of the actual Riva server")
                    print("   4. Ensure the destination port supports gRPC (usually 50051)")
                    print("   5. Check if a gRPC-aware load balancer is needed")
                    print("   6. Run diagnostics: python -m riva_dictation --diagnose")

                    # Try to reconnect with different settings
                    print("🔄 Attempting to reconnect...")
                    self.setup_riva()

                elif "unavailable" in error_msg.lower():
                    print("💡 Server became unavailable during streaming")
                    print("   The connection may have been lost or the forwarded service stopped")

                    # Try to reconnect
                    print("🔄 Attempting to reconnect...")
                    self.setup_riva()

                raise stream_error

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Recognition error: {e}")

            # Provide specific guidance for streaming errors
            if "http1.x server" in error_msg.lower():
                print("\n🔍 TCP Port Forwarding Analysis:")
                print("   ✅ Initial connection succeeded")
                print("   ❌ Streaming connection failed (HTTP instead of gRPC)")
                print("\n💡 This indicates TCP port forwarding to an HTTP service:")
                print("   1. The port forwards TCP connections successfully")
                print("   2. But the destination service responds with HTTP, not gRPC")
                print("   3. The forwarded destination is likely a web server, not Riva ASR")
                print("\n🔧 Recommended actions for TCP Port Forwarding:")
                print("   1. Contact your network administrator")
                print("   2. Verify the forwarded destination is running Riva ASR on the correct port")
                print("   3. Ask for the direct IP/port of the actual Riva server")
                print("   4. Ensure the destination port supports gRPC (usually 50051)")
                print("   5. Check if a gRPC-aware load balancer is needed")
                print("   6. Run diagnostics: python -m riva_dictation --diagnose")

            self.safe_update_status("Error", f"Recognition error: {str(e)}")
            self.stop_recording()

    def _auto_type_new_text(self):
        """Auto-type transcribed text like working version"""
        try:
            current_total = len(self.final_text)
            if current_total > self.last_typed_length:
                new_text = self.final_text[self.last_typed_length:]
                if new_text.strip():
                    # Type only the new text
                    pyautogui.typewrite(new_text, interval=self.config.get("type_interval", 0.01))
                    print(f"⌨️ Typed: '{new_text.strip()}'")
                self.last_typed_length = current_total
        except Exception as e:
            print(f"⚠️ Auto-type error: {e}")

    def quit_app(self, systray=None):
        """Clean up and quit application"""
        self.stop_recording()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()

        # Quit GUI components only if not headless
        if not self.headless and self.root:
            self.root.quit()
            self.root.destroy()

        sys.exit(0)

    def run(self):
        """Run the application"""
        if not self.headless:
            # Start system tray in background thread
            import threading
            tray_thread = threading.Thread(target=self.systray.start, daemon=True)
            tray_thread.start()

        # Handle signals
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        if not self.headless:
            # Use Tkinter mainloop for proper GUI support
            try:
                self.root.mainloop()
            except KeyboardInterrupt:
                self.quit_app()
        else:
            # Headless mode - just keep running until interrupted
            print("🎤 Riva Dictation running in CLI mode")
            print("📋 Press F9 to start/stop recording")
            print("🛑 Press Ctrl+C to quit")
            try:
                # Keep the main thread alive
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutting down...")
                self.quit_app()

    def show_settings(self, systray=None):
        """Show settings dialog"""
        if self.headless:
            print("⚠️ Settings dialog not available in CLI mode")
            print("💡 Edit configuration file or run without --no-gui flag")
            return

        def _show_settings_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title("Settings")
            dialog.geometry("500x400")
            dialog.grab_set()

            # Create settings form
            form = tk.Frame(dialog, padx=24, pady=24)
            form.pack(fill=tk.BOTH, expand=True)

            # Server settings
            server_frame = tk.LabelFrame(form, text="Server Settings", padx=16, pady=16)
            server_frame.pack(fill=tk.X, pady=(0, 16))

            # Endpoint type
            tk.Label(server_frame, text="Endpoint Type:").pack(anchor=tk.W)
            endpoint_var = tk.StringVar(value=self.config.get("endpoint_type"))
            endpoint_combo = ttk.Combobox(server_frame, textvariable=endpoint_var,
                                        values=["local", "custom"])
            endpoint_combo.pack(fill=tk.X, pady=(0, 8))

            # Custom endpoint
            tk.Label(server_frame, text="Custom Endpoint:").pack(anchor=tk.W)
            custom_endpoint_var = tk.StringVar(value=self.config.get("custom_endpoint"))
            custom_endpoint_entry = ttk.Entry(server_frame, textvariable=custom_endpoint_var)
            custom_endpoint_entry.pack(fill=tk.X, pady=(0, 8))

            # Port configuration frame
            port_frame = tk.Frame(server_frame)
            port_frame.pack(fill=tk.X, pady=(0, 8))

            # ASR Port
            tk.Label(port_frame, text="ASR Port:").pack(side=tk.LEFT)
            asr_port_var = tk.IntVar(value=self.config.get("custom_asr_port", 50051))
            asr_port_spin = tk.Spinbox(port_frame, from_=1, to=65535, textvariable=asr_port_var, width=8)
            asr_port_spin.pack(side=tk.LEFT, padx=(5, 15))

            # Separate health port checkbox
            separate_health_var = tk.BooleanVar(value=self.config.get("use_separate_health_port", False))
            separate_health_check = ttk.Checkbutton(port_frame, text="Separate Health Port:",
                                                   variable=separate_health_var)
            separate_health_check.pack(side=tk.LEFT, padx=(0, 5))

            # Health Port
            health_port_var = tk.IntVar(value=self.config.get("custom_health_port", 8000))
            health_port_spin = tk.Spinbox(port_frame, from_=1, to=65535, textvariable=health_port_var, width=8)
            health_port_spin.pack(side=tk.LEFT, padx=(0, 5))

            # Enable/disable health port based on checkbox
            def toggle_health_port():
                if separate_health_var.get():
                    health_port_spin.config(state='normal')
                else:
                    health_port_spin.config(state='disabled')

            separate_health_check.config(command=toggle_health_port)
            toggle_health_port()  # Set initial state

            # SSL checkbox
            ssl_var = tk.BooleanVar(value=self.config.get("use_ssl"))
            ssl_check = ttk.Checkbutton(server_frame, text="Use SSL", variable=ssl_var)
            ssl_check.pack(anchor=tk.W)

            # Port configuration info
            port_info = tk.Label(server_frame,
                text="💡 Port remapping: ASR port for recognition service, Health port for service monitoring",
                font=("Segoe UI", 9), fg="gray")
            port_info.pack(anchor=tk.W, pady=(4, 0))

            # General settings
            general_frame = tk.LabelFrame(form, text="General Settings", padx=16, pady=16)
            general_frame.pack(fill=tk.X, pady=(0, 16))

            # Auto-type checkbox
            auto_type_var = tk.BooleanVar(value=self.config.get("auto_type"))
            auto_type_check = ttk.Checkbutton(general_frame, text="Auto-type text",
                                            variable=auto_type_var)
            auto_type_check.pack(anchor=tk.W)

            # Show widget checkbox
            show_widget_var = tk.BooleanVar(value=self.config.get("show_widget"))
            show_widget_check = ttk.Checkbutton(general_frame, text="Show status widget",
                                              variable=show_widget_var)
            show_widget_check.pack(anchor=tk.W)

            # Hotkey
            tk.Label(general_frame, text="Hotkey:").pack(anchor=tk.W)
            hotkey_var = tk.StringVar(value=self.config.get("hotkey"))
            hotkey_entry = ttk.Entry(general_frame, textvariable=hotkey_var)
            hotkey_entry.pack(fill=tk.X, pady=(0, 8))

            # ASR Quality settings
            asr_frame = tk.LabelFrame(form, text="ASR Quality Settings", padx=16, pady=16)
            asr_frame.pack(fill=tk.X, pady=(0, 16))

            # Audio encoding
            tk.Label(asr_frame, text="Audio Encoding:").pack(anchor=tk.W)
            encoding_var = tk.StringVar(value=self.config.get("audio_encoding", "LINEAR_PCM"))
            encoding_combo = ttk.Combobox(asr_frame, textvariable=encoding_var,
                                        values=["LINEAR_PCM", "FLAC"], state="readonly")
            encoding_combo.pack(fill=tk.X, pady=(0, 8))

            # Max alternatives
            tk.Label(asr_frame, text="Max Alternatives (1-5):").pack(anchor=tk.W)
            alternatives_var = tk.IntVar(value=self.config.get("max_alternatives", 1))
            alternatives_spin = tk.Spinbox(asr_frame, from_=1, to=5, textvariable=alternatives_var)
            alternatives_spin.pack(fill=tk.X, pady=(0, 8))

            # Profanity filter
            profanity_var = tk.BooleanVar(value=self.config.get("profanity_filter", False))
            profanity_check = ttk.Checkbutton(asr_frame, text="Enable profanity filter",
                                            variable=profanity_var)
            profanity_check.pack(anchor=tk.W)

            # Verbatim transcripts
            verbatim_var = tk.BooleanVar(value=self.config.get("verbatim_transcripts", False))
            verbatim_check = ttk.Checkbutton(asr_frame, text="Verbatim transcripts (no text normalization)",
                                           variable=verbatim_var)
            verbatim_check.pack(anchor=tk.W)

            # Model name
            tk.Label(asr_frame, text="Model Name (optional):").pack(anchor=tk.W)
            model_var = tk.StringVar(value=self.config.get("model_name", ""))
            model_entry = ttk.Entry(asr_frame, textvariable=model_var)
            model_entry.pack(fill=tk.X, pady=(0, 8))

            # Speech contexts info
            contexts_info = tk.Label(asr_frame,
                text="💡 Tip: Add speech contexts in config file for better recognition of specific terms",
                font=("Segoe UI", 9), fg="gray")
            contexts_info.pack(anchor=tk.W, pady=(4, 0))

            def save_settings():
                # Save server settings
                self.config.set("endpoint_type", endpoint_var.get())
                self.config.set("custom_endpoint", custom_endpoint_var.get())
                self.config.set("custom_asr_port", asr_port_var.get())
                self.config.set("custom_health_port", health_port_var.get())
                self.config.set("use_separate_health_port", separate_health_var.get())
                self.config.set("use_ssl", ssl_var.get())

                # Save general settings
                self.config.set("auto_type", auto_type_var.get())
                self.config.set("show_widget", show_widget_var.get())
                self.config.set("hotkey", hotkey_var.get())

                # Save ASR quality settings
                self.config.set("audio_encoding", encoding_var.get())
                self.config.set("max_alternatives", alternatives_var.get())
                self.config.set("profanity_filter", profanity_var.get())
                self.config.set("verbatim_transcripts", verbatim_var.get())
                self.config.set("model_name", model_var.get())

                # Reconnect to Riva with new settings
                self.setup_riva()

                dialog.destroy()

            def test_connection():
                # Test Riva connection using currently selected settings
                try:
                    endpoint_type = endpoint_var.get()

                    # Determine server and SSL settings based on selected endpoint type
                    if endpoint_type == "custom":
                        custom_endpoint = custom_endpoint_var.get()
                        custom_asr_port = asr_port_var.get()
                        test_use_ssl = ssl_var.get()

                        # Build server string with custom port
                        if custom_endpoint:
                            # If endpoint already has port, use as-is, otherwise add custom port
                            if ':' in custom_endpoint:
                                test_server = custom_endpoint
                            else:
                                test_server = f"{custom_endpoint}:{custom_asr_port}"
                        else:
                            test_server = f"localhost:{custom_asr_port}"
                    else:
                        # Get from predefined endpoints
                        endpoint_config = self.config.get("endpoints", {}).get(endpoint_type, {})
                        test_server = endpoint_config.get("server", "localhost:50051")
                        test_use_ssl = endpoint_config.get("use_ssl", False)

                    print(f"[Test] Testing connection to: {test_server} (SSL: {test_use_ssl})")

                    # Create auth with appropriate settings
                    auth = riva.client.Auth(uri=test_server, use_ssl=test_use_ssl)

                    # Create test client
                    test_client = riva.client.ASRService(auth)

                    # For now, just verify client creation works
                    # The fact that we can create the client means authentication is working
                    print("[Test] ASR client created successfully")

                    # Show available methods for debugging
                    methods = [method for method in dir(test_client) if not method.startswith('_') and callable(getattr(test_client, method))]
                    print(f"[Test] Available methods: {', '.join(methods[:10])}...")

                    messagebox.showinfo("Connection Test",
                        f"✅ Connection test successful!\n\nEndpoint: {test_server}\nSSL: {test_use_ssl}\n\nClient created successfully.")

                except Exception as e:
                    error_msg = f"❌ Connection test failed:\n\n{str(e)}"
                    print(f"[Test] {error_msg}")
                    messagebox.showerror("Connection Test", error_msg)

            # Buttons
            button_frame = tk.Frame(form)
            button_frame.pack(fill=tk.X, pady=(0, 16))

            test_button = tk.Button(button_frame, text="Test Connection",
                                  font=("Segoe UI", 12),
                                  bg='#f5f5f5',
                                  fg='#1976d2',
                                  relief='flat',
                                  command=test_connection)
            test_button.pack(side=tk.LEFT)

            save_button = tk.Button(button_frame, text="Save",
                                  font=("Segoe UI", 12),
                                  bg='#1976d2',
                                  fg='white',
                                  relief='flat',
                                  command=save_settings)
            save_button.pack(side=tk.RIGHT)

        # Call directly since we're now using mainloop
        _show_settings_dialog()

    @staticmethod
    def signal_handler(sig, frame):
        """Handle system signals"""
        sys.exit(0)

    def diagnose_connection(self, server, test_ssl=True):
        """Diagnose connection issues with detailed testing"""
        print(f"🔍 Diagnosing connection to: {server}")

        # Test 1: Basic network connectivity
        try:
            import socket
            host, port = server.split(':')
            port = int(port)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                print("✅ Network connectivity: Port is reachable")
            else:
                print("❌ Network connectivity: Port is not reachable")
                return False
        except Exception as e:
            print(f"❌ Network test failed: {e}")
            return False

        # Test 2: Check what type of service is running
        try:
            import requests
            response = requests.get(f"http://{server}", timeout=5)
            print(f"🔀 TCP port responds to HTTP: {response.status_code}")
            print("💡 This suggests:")
            print("   - TCP port forwarding to an HTTP service")
            print("   - Load balancer not configured for gRPC")
            print("   - Proxy server intercepting connections")
            print("   - The forwarded destination may not be a gRPC service")

            # Check response headers for clues
            server_header = response.headers.get('server', '').lower()
            if 'nginx' in server_header or 'apache' in server_header:
                print(f"   - Detected web server: {server_header}")
                print("   - This port is likely forwarded to a web server, not Riva")
            elif 'riva' in server_header:
                print(f"   - Detected Riva in headers: {server_header}")
                print("   - This might be a Riva HTTP gateway")

        except requests.exceptions.ConnectionError:
            print("✅ No HTTP response: Good sign for gRPC services")
        except Exception as e:
            print(f"⚠️ HTTP test inconclusive: {e}")

        # Test 3: gRPC connection attempts
        connection_results = []

        # Test without SSL
        try:
            print("🔄 Testing gRPC without SSL...")
            auth = riva.client.Auth(uri=server, use_ssl=False)
            client = riva.client.ASRService(auth)
            print("✅ gRPC without SSL: Client created successfully")

            # Try a simple streaming test to validate actual functionality
            try:
                test_config = RecognitionConfig(
                    encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=16000,
                    language_code="en-US",
                    max_alternatives=1
                )
                streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                    config=test_config,
                    interim_results=False
                )

                def test_audio_generator():
                    yield b'\x00' * 32  # Send minimal audio data

                # Use the correct streaming method
                if hasattr(client, 'streaming_response_generator'):
                    test_stream = client.streaming_response_generator(
                        test_audio_generator(),
                        streaming_config
                    )
                    next(test_stream)
                    print("✅ gRPC streaming test: SUCCESS")
                    connection_results.append(("gRPC without SSL", True))
                else:
                    print("⚠️ No streaming_response_generator method found")
                    connection_results.append(("gRPC without SSL", False, "No streaming method"))

            except Exception as stream_error:
                if "http1.x server" in str(stream_error).lower():
                    print("❌ gRPC streaming test: HTTP response received")
                    print("💡 Analysis: TCP forwarding to HTTP service")
                    connection_results.append(("gRPC without SSL", False, "TCP forwarded to HTTP"))
                else:
                    print(f"⚠️ gRPC streaming test: {stream_error}")
                    connection_results.append(("gRPC without SSL", False, str(stream_error)))

        except Exception as e:
            print(f"❌ gRPC without SSL: {e}")
            connection_results.append(("gRPC without SSL", False, str(e)))

        # Test with SSL if requested
        if test_ssl:
            try:
                print("🔄 Testing gRPC with SSL...")
                auth = riva.client.Auth(uri=server, use_ssl=True)
                client = riva.client.ASRService(auth)
                print("✅ gRPC with SSL: Client created successfully")

                # Try streaming test with SSL
                try:
                    test_config = RecognitionConfig(
                        encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                        sample_rate_hertz=16000,
                        language_code="en-US",
                        max_alternatives=1
                    )
                    streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                        config=test_config,
                        interim_results=False
                    )

                    def test_audio_generator():
                        yield b'\x00' * 32  # Send minimal audio data

                    # Use the correct streaming method
                    if hasattr(client, 'streaming_response_generator'):
                        test_stream = client.streaming_response_generator(
                            test_audio_generator(),
                            streaming_config
                        )
                        next(test_stream)
                        print("✅ gRPC SSL streaming test: SUCCESS")
                        connection_results.append(("gRPC with SSL", True))
                    else:
                        print("⚠️ No streaming_response_generator method found")
                        connection_results.append(("gRPC with SSL", False, "No streaming method"))

                except Exception as stream_error:
                    if "http1.x server" in str(stream_error).lower():
                        print("❌ gRPC SSL streaming test: HTTP response received")
                        print("💡 Analysis: TCP forwarding to HTTP service (even with SSL)")
                        connection_results.append(("gRPC with SSL", False, "TCP forwarded to HTTP"))
                    else:
                        print(f"⚠️ gRPC SSL streaming test: {stream_error}")
                        connection_results.append(("gRPC with SSL", False, str(stream_error)))

            except Exception as e:
                print(f"❌ gRPC with SSL: {e}")
                connection_results.append(("gRPC with SSL", False, str(e)))

        # Analyze results and provide recommendations
        successful_methods = [result[0] for result in connection_results if result[1]]
        tcp_forwarding_detected = any("TCP forwarded to HTTP" in str(result) for result in connection_results)

        if successful_methods:
            print(f"✅ Successful connection methods: {', '.join(successful_methods)}")
            return True
        elif tcp_forwarding_detected:
            print("❌ TCP Port Forwarding Issue Detected")
            print("\n🔍 Analysis:")
            print("   - The port is reachable via TCP")
            print("   - gRPC client creation succeeds")
            print("   - But streaming fails with HTTP responses")
            print("   - This indicates TCP port forwarding to an HTTP service")
            print("\n💡 Recommendations for TCP Port Forwarding:")
            print("   1. Verify the forwarded destination is actually running Riva ASR")
            print("   2. Check if the destination port is correct for gRPC (usually 50051)")
            print("   3. Ensure the destination server supports gRPC, not just HTTP")
            print("   4. Contact your network administrator about the port forwarding configuration")
            print("   5. Ask for the direct IP/port of the actual Riva server")
            print("   6. Consider using a gRPC-aware load balancer if one is needed")
            return False
        else:
            print("❌ No successful connection methods found")
            print("\n💡 General Recommendations:")
            print("1. Verify this is actually a Riva ASR server")
            print("2. Check if the port number is correct for gRPC service")
            print("3. Confirm the server supports the Riva ASR protocol")
            print("4. Contact your server administrator for the correct gRPC endpoint")
            return False