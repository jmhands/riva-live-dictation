#!/usr/bin/env python3
"""
Simple Dictation App using Local Riva NIM (gRPC)
- Press F9 to start/stop recording
- Transcribed text is automatically typed into the active window
- Uses your local Riva NIM gRPC endpoint at localhost:50051
"""

import pyaudio
import wave
import tempfile
import threading
import time
from pynput import keyboard
from pynput.keyboard import Key, Listener
import pyautogui
import tkinter as tk
from tkinter import messagebox
import sys
import os
import numpy as np

# Riva client imports
try:
    import riva.client
    from riva.client import RecognitionConfig
    import riva.client.proto.riva_audio_pb2 as riva_audio_pb2
except ImportError:
    print("❌ nvidia-riva-client not installed!")
    print("Install with: pip install nvidia-riva-client")
    sys.exit(1)

class DictationApp:
    def __init__(self):
        self.recording = False
        self.audio_frames = []
        self.audio = None
        self.stream = None

        # Audio settings - Riva prefers 16kHz mono
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000

        # Riva gRPC settings
        self.riva_server = "localhost:50051"
        self.language_code = "en-US"

        # Initialize PyAudio and find default input device
        self.audio = pyaudio.PyAudio()
        self.setup_microphone()

        # Initialize Riva client
        self.setup_riva_client()

        # Setup GUI
        self.setup_gui()

        # Setup hotkey listener
        self.setup_hotkeys()

    def setup_microphone(self):
        """Setup and verify microphone"""
        try:
            # Get default input device
            default_device_info = self.audio.get_default_input_device_info()
            self.input_device_index = default_device_info['index']

            print(f"🎤 Using microphone: {default_device_info['name']}")
            print(f"   Device index: {self.input_device_index}")
            print(f"   Max input channels: {default_device_info['maxInputChannels']}")
            print(f"   Default sample rate: {default_device_info['defaultSampleRate']}")

            # Test if we can open the device
            test_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )
            test_stream.close()
            print("✅ Microphone test successful")

        except Exception as e:
            print(f"❌ Microphone setup failed: {e}")
            print("\n📱 Available input devices:")
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    print(f"   {i}: {info['name']} (channels: {info['maxInputChannels']})")
            self.input_device_index = None

    def setup_riva_client(self):
        """Initialize Riva ASR client"""
        try:
            # Create Riva ASR service
            auth = riva.client.Auth(uri=self.riva_server, use_ssl=False)
            self.riva_asr = riva.client.ASRService(auth)
            print(f"✅ Connected to Riva server at {self.riva_server}")
        except Exception as e:
            print(f"❌ Failed to connect to Riva: {e}")
            self.riva_asr = None

    def setup_gui(self):
        """Create simple status window"""
        self.root = tk.Tk()
        self.root.title("Local Dictation (Riva)")
        self.root.geometry("300x200")
        self.root.attributes('-topmost', True)

        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Press F9 to start dictation\nReady",
            font=("Arial", 12),
            fg="green"
        )
        self.status_label.pack(pady=20)

        # Instructions
        instructions = tk.Label(
            self.root,
            text="F9: Start/Stop Recording\nESC: Exit App\nUsing Riva gRPC at :50051",
            font=("Arial", 9),
            fg="gray"
        )
        instructions.pack(pady=10)

        # Test connection button
        test_btn = tk.Button(
            self.root,
            text="Test Riva Connection",
            command=self.test_connection
        )
        test_btn.pack(pady=2)

        # Microphone test button
        mic_test_btn = tk.Button(
            self.root,
            text="Test Microphone",
            command=self.test_microphone
        )
        mic_test_btn.pack(pady=2)

    def setup_hotkeys(self):
        """Setup global hotkey listener"""
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.toggle_recording()
                elif key == keyboard.Key.esc:
                    self.quit_app()
            except AttributeError:
                pass

        # Start hotkey listener in background
        self.listener = Listener(on_press=on_press)
        self.listener.start()

    def test_connection(self):
        """Test connection to Riva"""
        if self.riva_asr is None:
            messagebox.showerror("Connection Test", "❌ Riva client not initialized")
            print("❌ Riva client not initialized")
            return

        try:
            # Create a simple test audio (1 second of silence)
            test_audio = np.zeros(self.rate, dtype=np.int16)
            audio_bytes = test_audio.tobytes()

            # Create recognition config with proper encoding
            config = RecognitionConfig(
                language_code=self.language_code,
                enable_automatic_punctuation=True,
                sample_rate_hertz=self.rate,
                encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                max_alternatives=3  # This is the key fix!
            )

            print(f"Testing with config: encoding={config.encoding}, sample_rate={config.sample_rate_hertz}")
            print(f"Audio bytes length: {len(audio_bytes)}")

            # Test transcription
            response = self.riva_asr.offline_recognize(audio_bytes, config)
            print("✅ Connection test successful!")

            messagebox.showinfo("Connection Test", "✅ Riva connection successful!\n(Silence detected - ready for real audio)")

        except Exception as e:
            error_msg = f"❌ Riva test failed: {str(e)}"
            print(f"\n{error_msg}")  # Print to console for copying
            import traceback
            traceback.print_exc()  # Full traceback to console
            messagebox.showerror("Connection Test", error_msg)

    def test_microphone(self):
        """Test microphone recording"""
        if self.input_device_index is None:
            messagebox.showerror("Microphone Test", "❌ No microphone available")
            return

        try:
            print("🎤 Testing microphone for 3 seconds...")
            messagebox.showinfo("Microphone Test", "Recording for 3 seconds...\nSpeak now!")

            # Record for 3 seconds
            frames = []
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            for _ in range(0, int(self.rate / self.chunk * 3)):  # 3 seconds
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

            stream.close()

            # Analyze the recorded audio
            audio_data = b''.join(frames)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            max_amplitude = np.max(np.abs(audio_array))
            rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))

            print(f"📊 Microphone test results:")
            print(f"   Max amplitude: {max_amplitude}")
            print(f"   RMS level: {rms:.1f}")

            if max_amplitude > 1000:
                result_msg = f"✅ Microphone working well!\nMax amplitude: {max_amplitude}\nRMS: {rms:.1f}"
                print("✅ Good audio levels detected")
            elif max_amplitude > 100:
                result_msg = f"⚠️ Microphone working but quiet\nMax amplitude: {max_amplitude}\nRMS: {rms:.1f}\n\nTry speaking louder or moving closer"
                print("⚠️ Audio levels are low")
            else:
                result_msg = f"❌ Very quiet or no audio detected\nMax amplitude: {max_amplitude}\nRMS: {rms:.1f}\n\nCheck microphone settings"
                print("❌ Very low audio levels")

            messagebox.showinfo("Microphone Test", result_msg)

        except Exception as e:
            error_msg = f"❌ Microphone test failed: {str(e)}"
            print(error_msg)
            messagebox.showerror("Microphone Test", error_msg)

    def toggle_recording(self):
        """Start or stop recording"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording"""
        if self.riva_asr is None:
            self.status_label.config(text="❌ Riva not connected", fg="red")
            return

        if self.input_device_index is None:
            self.status_label.config(text="❌ No microphone available", fg="red")
            return

        try:
            self.recording = True
            self.audio_frames = []

            # Update GUI
            self.status_label.config(text="🔴 Recording...\nPress F9 to stop", fg="red")
            self.root.update()

            # Start recording stream with specific device
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            print(f"🎤 Started recording from device {self.input_device_index}")

            # Record in background thread
            self.record_thread = threading.Thread(target=self._record_audio)
            self.record_thread.start()

        except Exception as e:
            error_msg = f"❌ Recording failed: {str(e)}"
            print(error_msg)
            self.status_label.config(text=error_msg, fg="red")
            self.recording = False

    def _record_audio(self):
        """Record audio in background thread"""
        while self.recording:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.audio_frames.append(data)
            except Exception as e:
                print(f"Recording error: {e}")
                break

    def stop_recording(self):
        """Stop recording and transcribe"""
        if not self.recording:
            return

        self.recording = False

        # Update GUI
        self.status_label.config(text="⏳ Processing...", fg="orange")
        self.root.update()

        try:
            # Stop stream
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

            # Wait for recording thread to finish
            if hasattr(self, 'record_thread'):
                self.record_thread.join(timeout=1)

            # Process audio in background
            threading.Thread(target=self._process_audio).start()

        except Exception as e:
            self.status_label.config(text=f"❌ Stop failed:\n{str(e)}", fg="red")

    def _process_audio(self):
        """Process recorded audio and transcribe with Riva"""
        try:
            if not self.audio_frames:
                self.status_label.config(text="No audio recorded\nReady", fg="green")
                return

            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name

                # Write WAV file
                wf = wave.open(temp_filename, 'wb')
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self.audio_frames))
                wf.close()

            # Transcribe with Riva
            transcription = self._transcribe_with_riva(temp_filename)

            # Clean up temp file
            os.unlink(temp_filename)

            if transcription:
                # Type the transcription
                self._type_text(transcription)
                preview = transcription[:30] + "..." if len(transcription) > 30 else transcription
                self.status_label.config(text=f"✅ Typed: {preview}\nReady", fg="green")
            else:
                self.status_label.config(text="❌ No transcription\nReady", fg="orange")

        except Exception as e:
            self.status_label.config(text=f"❌ Process failed:\n{str(e)[:50]}...\nReady", fg="red")

    def _transcribe_with_riva(self, audio_file):
        """Transcribe audio using Riva gRPC client"""
        try:
            # Read raw audio data from WAV file (skip headers)
            with wave.open(audio_file, 'rb') as wav_file:
                # Get audio parameters
                sample_rate = wav_file.getframerate()
                n_frames = wav_file.getnframes()

                # Read raw audio frames (this excludes WAV headers)
                raw_audio_bytes = wav_file.readframes(n_frames)

                print(f"Audio file: {sample_rate}Hz, {n_frames} frames, {len(raw_audio_bytes)} bytes")

                # Calculate duration and check audio level
                duration = n_frames / sample_rate
                audio_array = np.frombuffer(raw_audio_bytes, dtype=np.int16)
                max_amplitude = np.max(np.abs(audio_array))
                rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))

                print(f"Duration: {duration:.2f}s, Max amplitude: {max_amplitude}, RMS: {rms:.1f}")

                if max_amplitude < 100:
                    print("⚠️  WARNING: Audio seems very quiet (max amplitude < 100)")
                if duration < 0.5:
                    print("⚠️  WARNING: Audio is very short (< 0.5 seconds)")

            # Create recognition config with proper encoding
            config = RecognitionConfig(
                language_code=self.language_code,
                enable_automatic_punctuation=True,
                sample_rate_hertz=sample_rate,  # Use actual sample rate from file
                encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                max_alternatives=3  # This is the key fix!
            )

            print(f"Transcribing with config: encoding={config.encoding}, sample_rate={config.sample_rate_hertz}")

            # Perform offline recognition
            response = self.riva_asr.offline_recognize(raw_audio_bytes, config)

            print(f"Response received: {len(response.results) if hasattr(response, 'results') else 0} results")

            # Extract transcription from response
            if hasattr(response, 'results') and len(response.results) > 0:
                print(f"Processing {len(response.results)} results:")

                # Check all results, not just the first one
                for i, result in enumerate(response.results):
                    print(f"  Result {i}: {len(result.alternatives)} alternatives")

                    if len(result.alternatives) > 0:
                        transcript = result.alternatives[0].transcript
                        confidence = result.alternatives[0].confidence if hasattr(result.alternatives[0], 'confidence') else 'N/A'
                        print(f"  Result {i} transcript: '{transcript}' (confidence: {confidence})")

                        # Return the first non-empty transcript
                        if transcript.strip():
                            print(f"✅ Using transcript from result {i}: '{transcript}'")
                            return transcript.strip()

                print("❌ No non-empty transcripts found in any result")
                return None
            else:
                print("No transcription results - possible causes:")
                print("  • Audio too quiet or silent")
                print("  • Speech not clear enough")
                print("  • Recording too short")
                print("  • Background noise too high")
                return None

        except Exception as e:
            print(f"Riva transcription error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _type_text(self, text):
        """Type text into active window"""
        if text:
            # Small delay to ensure window focus
            time.sleep(0.1)
            pyautogui.typewrite(text)

    def quit_app(self):
        """Clean shutdown"""
        self.recording = False

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
        try:
            print("Local Dictation App (Riva gRPC) Started")
            print("Press F9 to start/stop recording")
            print("Press ESC to quit")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()

if __name__ == "__main__":
    # Check dependencies
    missing_deps = []
    try:
        import pyaudio
    except ImportError:
        missing_deps.append("pyaudio")

    try:
        import pynput
    except ImportError:
        missing_deps.append("pynput")

    try:
        import pyautogui
    except ImportError:
        missing_deps.append("pyautogui")

    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")

    try:
        import riva.client
    except ImportError:
        missing_deps.append("nvidia-riva-client")

    if missing_deps:
        print(f"Missing dependencies: {', '.join(missing_deps)}")
        print("\nInstall with:")
        print("pip install pyaudio pynput pyautogui numpy nvidia-riva-client")
        sys.exit(1)

    app = DictationApp()
    app.run()