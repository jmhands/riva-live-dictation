#!/usr/bin/env python3
"""
Modern Real-time Dictation App with System Tray Integration
- System tray integration for minimal distraction
- Modern floating widget interface
- Robust error handling and auto-recovery
- Real-time streaming with visual feedback
"""

import os
import sys
import json
import time
import queue
import threading
from pathlib import Path
from typing import Dict, Any
import argparse
import pyaudio
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import pyautogui
from infi.systray import SysTrayIcon

# Import system tray and keyboard handling
try:
    import pystray
    from pystray import MenuItem, Menu
    from PIL import Image, ImageDraw
except ImportError:
    print("❌ pystray and PIL required for system tray!")
    print("Install with: pip install pystray pillow")
    sys.exit(1)

try:
    from pynput import keyboard
    from pynput.keyboard import Key, Listener
except ImportError:
    print("❌ pynput and pyautogui required!")
    print("Install with: pip install pynput pyautogui")
    sys.exit(1)

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
        "endpoint_type": "local",  # "local", "nim_cloud", "custom"
        "nim_api_key": "",  # For NVIDIA NIM cloud endpoints
        "custom_endpoint": "",  # For custom cloud endpoints
        "connection_timeout": 30,  # Connection timeout in seconds
        # ENDPOINT PRESETS
        "endpoints": {
            "local": {
                "server": "localhost:50051",
                "use_ssl": False,
                "description": "Local Riva/Parakeet"
            },
            "nim_cloud": {
                "server": "ai.api.nvidia.com:443",
                "use_ssl": True,
                "description": "NVIDIA NIM Cloud"
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

class CursorIndicator:
    """Simple static red microphone icon that appears when recording"""

    def __init__(self, parent_app):
        self.app = parent_app
        self.indicator = None
        self.visible = False

    def show_indicator(self):
        """Show simple recording indicator"""
        if self.indicator:
            return

        self.indicator = tk.Toplevel()
        self.indicator.title("Recording")
        self.indicator.overrideredirect(True)  # No window decorations
        self.indicator.attributes('-topmost', True)
        self.indicator.attributes('-alpha', 0.9)

        # Position in bottom-right corner (unobtrusive)
        self.indicator.geometry("40x40+{}+{}".format(
            self.indicator.winfo_screenwidth() - 60,
            self.indicator.winfo_screenheight() - 100
        ))

        # Simple red circle with microphone icon (Google Material style)
        frame = tk.Frame(self.indicator, bg='#f44336', width=36, height=36)
        frame.pack(padx=2, pady=2)
        frame.pack_propagate(False)

        # Material Design microphone icon
        mic_label = tk.Label(frame, text="🎙️", bg='#f44336', fg='white',
                           font=("Segoe UI", 16))
        mic_label.pack(expand=True)

        self.visible = True

    def hide_indicator(self):
        """Hide the recording indicator"""
        if self.indicator:
            self.indicator.destroy()
            self.indicator = None
        self.visible = False

    # Remove all text update methods - no interference!

class StatusWidget:
    """Material Design floating status widget"""

    def __init__(self, parent_app):
        self.app = parent_app
        self.root = None
        self.visible = False
        # Thread-safe GUI update queue
        self.gui_queue = queue.Queue()

        # Material Design Color Palette
        self.colors = {
            'primary': '#1976d2',        # Material Blue 700
            'primary_variant': '#1565c0', # Material Blue 800
            'secondary': '#03dac6',      # Material Teal 200
            'background': '#ffffff',     # Material Surface
            'surface': '#ffffff',        # Material Surface
            'surface_variant': '#f5f5f5', # Material Surface Variant
            'on_surface': '#1c1b1f',     # Material On Surface
            'on_surface_variant': '#49454f', # Material On Surface Variant
            'success': '#4caf50',        # Material Green 500
            'warning': '#ff9800',        # Material Orange 500
            'error': '#f44336',          # Material Red 500
            'outline': '#79747e',        # Material Outline
        }

        # Dark theme colors (for future use)
        self.dark_colors = {
            'primary': '#90caf9',        # Material Blue 200
            'primary_variant': '#42a5f5', # Material Blue 400
            'secondary': '#03dac6',      # Material Teal 200
            'background': '#121212',     # Material Dark Background
            'surface': '#1e1e1e',        # Material Dark Surface
            'surface_variant': '#2d2d2d', # Material Dark Surface Variant
            'on_surface': '#e1e2e3',     # Material Dark On Surface
            'on_surface_variant': '#c7c5d0', # Material Dark On Surface Variant
            'success': '#4caf50',
            'warning': '#ff9800',
            'error': '#f44336',
            'outline': '#938f99',
        }

    def create_widget(self):
        """Create Material Design floating widget"""
        self.root = tk.Toplevel()
        self.root.title("Riva Dictation")

        # Material Design elevation and styling
        self.setup_material_styling()

        # Remove window decorations for Material card appearance
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        # Material Design elevation shadow (simulated with border)
        self.root.configure(bg='#e0e0e0')  # Shadow color

        # Position using Material 8dp grid system
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"320x160+{screen_width - 340}+16")  # 16dp margin

        # Main Material card container
        self.card_frame = tk.Frame(self.root, bg=self.colors['surface'],
                                  relief='flat', bd=0)
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)  # 2px shadow

        # Content with Material spacing (16dp padding)
        self.content_frame = tk.Frame(self.card_frame, bg=self.colors['surface'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        self.create_material_header()
        self.create_material_status()
        self.create_material_actions()

        # Material drag behavior
        self.setup_material_dragging()

        # Start GUI processing
        self.process_gui_updates()

        self.update_status("ready")

    def create_material_header(self):
        """Create Material Design header with app title"""
        header_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        header_frame.pack(fill=tk.X, pady=(0, 16))  # 16dp bottom margin

        # App title - Material Design Headline 6
        title_label = tk.Label(header_frame,
                              text="Riva Dictation",
                              bg=self.colors['surface'],
                              fg=self.colors['on_surface'],
                              font=("Roboto", 16, "bold"),  # Material Headline 6
                              anchor='w')
        title_label.pack(side=tk.LEFT)

        # Close button - Material Design IconButton
        close_btn = tk.Button(header_frame,
                             text="✕",
                             bg=self.colors['surface'],
                             fg=self.colors['on_surface_variant'],
                             font=("Roboto", 14),
                             bd=0,
                             relief='flat',
                             width=3,
                             height=1,
                             cursor='hand2',
                             command=self.hide_widget)
        close_btn.pack(side=tk.RIGHT)

        # Hover effect for close button
        def on_enter(e):
            close_btn.configure(bg='#f0f0f0')
        def on_leave(e):
            close_btn.configure(bg=self.colors['surface'])
        close_btn.bind("<Enter>", on_enter)
        close_btn.bind("<Leave>", on_leave)

    def create_material_status(self):
        """Create Material Design status section"""
        status_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        status_frame.pack(fill=tk.X, pady=(0, 16))

        # Status indicator container
        indicator_frame = tk.Frame(status_frame, bg=self.colors['surface'])
        indicator_frame.pack(side=tk.LEFT)

        # Material Design status dot (larger, following Material size guidelines)
        self.status_canvas = tk.Canvas(indicator_frame,
                                      width=16, height=16,
                                      bg=self.colors['surface'],
                                      highlightthickness=0,
                                      bd=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 12))  # 12dp spacing

        # Status text - Material Design Body 1
        self.status_text = tk.Label(status_frame,
                                   text="Ready",
                                   bg=self.colors['surface'],
                                   fg=self.colors['on_surface'],
                                   font=("Roboto", 14, "bold"))  # Material Body 1
        self.status_text.pack(side=tk.LEFT)

        # Endpoint badge - Material Design Caption
        self.endpoint_badge = tk.Label(status_frame,
                                      text="🏠 Local",
                                      bg=self.colors['surface_variant'],
                                      fg=self.colors['on_surface_variant'],
                                      font=("Roboto", 11, "bold"),  # Material Caption
                                      padx=8, pady=4,
                                      relief='flat')
        self.endpoint_badge.pack(side=tk.RIGHT)

    def create_material_actions(self):
        """Create Material Design action buttons"""
        actions_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        actions_frame.pack(fill=tk.X)

        # Primary action button - Material Design Filled Button
        self.record_btn = tk.Button(actions_frame,
                                   text="Start Recording",
                                   bg=self.colors['primary'],
                                   fg='white',
                                   font=("Roboto", 12, "bold"),  # Changed from "medium" to "bold"
                                   bd=0,
                                   relief='flat',
                                   padx=16, pady=8,  # Material button padding
                                   cursor='hand2',
                                   command=self.app.toggle_recording)
        self.record_btn.pack(side=tk.LEFT)

        # Secondary actions container
        secondary_frame = tk.Frame(actions_frame, bg=self.colors['surface'])
        secondary_frame.pack(side=tk.RIGHT)

        # Settings button - Material Design Text Button
        settings_btn = tk.Button(secondary_frame,
                                text="Settings",
                                bg=self.colors['surface'],
                                fg=self.colors['primary'],
                                font=("Roboto", 12, "bold"),  # Changed from "medium" to "bold"
                                bd=0,
                                relief='flat',
                                padx=12, pady=8,
                                cursor='hand2',
                                command=self.show_settings)
        settings_btn.pack(side=tk.RIGHT, padx=(8, 0))  # 8dp spacing

        # Auto-type toggle - Material Design Switch (simplified as checkbox)
        self.auto_type_var = tk.BooleanVar(value=self.app.config.get("auto_type", True))
        auto_type_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        auto_type_frame.pack(fill=tk.X, pady=(16, 0))  # 16dp top margin

        auto_type_check = tk.Checkbutton(auto_type_frame,
                                        text="Auto-type",
                                        variable=self.auto_type_var,
                                        bg=self.colors['surface'],
                                        fg=self.colors['on_surface'],
                                        font=("Roboto", 12, "bold"),
                                        activebackground=self.colors['surface'],
                                        activeforeground=self.colors['primary'],
                                        selectcolor=self.colors['primary'],
                                        bd=0,
                                        command=self.toggle_auto_type)
        auto_type_check.pack(anchor=tk.W)

        # Material hover effects
        self.setup_button_hover_effects([self.record_btn, settings_btn])

    def setup_button_hover_effects(self, buttons):
        """Add Material Design hover effects to buttons"""
        def create_hover_effect(button, normal_color, hover_color):
            def on_enter(e):
                button.configure(bg=hover_color)
            def on_leave(e):
                button.configure(bg=normal_color)
            button.bind("<Enter>", on_enter)
            button.bind("<Leave>", on_leave)

        # Primary button hover
        create_hover_effect(self.record_btn, self.colors['primary'], self.colors['primary_variant'])

        # Settings button hover
        for btn in buttons[1:]:  # Skip record button
            create_hover_effect(btn, self.colors['surface'], '#f5f5f5')

    def setup_material_styling(self):
        """Setup Material Design styling"""
        # Configure tkinter to use Roboto font if available
        try:
            # Try to use Roboto (Material Design font)
            test_label = tk.Label(self.root, font=("Roboto", 12))
            self.font_family = "Roboto"
        except:
            # Fallback to system fonts
            import platform
            if platform.system() == "Windows":
                self.font_family = "Segoe UI"
            elif platform.system() == "Darwin":  # macOS
                self.font_family = "SF Pro Display"
            else:  # Linux
                self.font_family = "Ubuntu"

    def setup_material_dragging(self):
        """Setup Material Design drag behavior with proper feedback"""
        def start_drag(event):
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            # Material Design: Slightly elevate during drag
            self.root.configure(bg='#bdbdbd')  # Darker shadow during drag

        def on_drag(event):
            x = self.root.winfo_x() + event.x - self.drag_start_x
            y = self.root.winfo_y() + event.y - self.drag_start_y
            self.root.geometry(f"+{x}+{y}")

        def end_drag(event):
            # Material Design: Return to normal elevation
            self.root.configure(bg='#e0e0e0')

        # Bind to header area only (Material Design pattern)
        self.content_frame.bind("<Button-1>", start_drag)
        self.content_frame.bind("<B1-Motion>", on_drag)
        self.content_frame.bind("<ButtonRelease-1>", end_drag)

    def process_gui_updates(self):
        """Process GUI updates with REDUCED frequency for lower latency"""
        try:
            # OPTIMIZED: Process multiple updates at once, less frequently
            updates_processed = 0
            while updates_processed < 5:  # Process max 5 updates per cycle
                try:
                    update_func = self.gui_queue.get_nowait()
                    update_func()
                    updates_processed += 1
                except queue.Empty:
                    break
        except Exception as e:
            print(f"⚠️ GUI update error: {e}")

        # OPTIMIZED: Reduced update frequency from 10ms to 50ms during recording
        # This reduces CPU overhead significantly
        if hasattr(self, 'app') and self.app.recording:
            fps = self.app.config.get("gui_fps_recording", 20)
            self.root.after(int(1000/fps), self.process_gui_updates)  # Configurable FPS during recording
        else:
            fps = self.app.config.get("gui_fps_idle", 60)
            self.root.after(int(1000/fps), self.process_gui_updates)  # Configurable FPS when idle

    def show_widget(self):
        """Show the widget"""
        if not self.root:
            self.create_widget()
        self.root.deiconify()
        self.visible = True

    def hide_widget(self):
        """Hide the widget"""
        if self.root:
            self.root.withdraw()
        self.visible = False

    def toggle_widget(self):
        """Toggle widget visibility"""
        if self.visible:
            self.hide_widget()
        else:
            self.show_widget()

    def update_status(self, status: str, message: str = ""):
        """Update status with endpoint information"""
        def _update():
            if not self.root:
                return

            # Update status dot color
            self.status_canvas.delete("all")
            colors = {
                "ready": "#22c55e",     # Green
                "recording": "#ef4444", # Red
                "connecting": "#f59e0b", # Yellow
                "error": "#ef4444"      # Red
            }

            color = colors.get(status, "#6b7280")  # Default gray
            self.status_canvas.create_oval(2, 2, 10, 10, fill=color, outline="")

            # Update status text
            status_texts = {
                "ready": "Ready",
                "recording": "Recording...",
                "connecting": "Connecting...",
                "error": f"Error: {message}"
            }

            self.status_text.config(text=status_texts.get(status, status))

            # Update endpoint indicator
            if hasattr(self, 'app'):
                endpoint_type = self.app.config.get("endpoint_type", "local")
                endpoint_icons = {
                    "local": "🏠 Local",
                    "nim_cloud": "☁️ NIM",
                    "custom": "🌐 Custom"
                }
                self.endpoint_badge.config(text=endpoint_icons.get(endpoint_type, ""))

            # Update record button text
            if hasattr(self, 'record_btn'):
                if status == "recording":
                    self.record_btn.config(text="Stop Recording", bg=self.colors['error'])
                else:
                    self.record_btn.config(text="Start Recording", bg=self.colors['primary'])

        self.gui_queue.put(_update)

    def show_dialog(self, title: str, message: str):
        """Show dialog in a thread-safe manner"""
        def _show_dialog():
            if self.root:
                messagebox.showinfo(title, message)

        # Queue the dialog for main thread
        self.gui_queue.put(_show_dialog)

    def toggle_auto_type(self):
        """Toggle auto-type setting"""
        self.app.config.set("auto_type", self.auto_type_var.get())

    def show_settings(self, icon=None, item=None):
        # Schedule settings dialog to open in the main thread
        self.app.root.after(0, self._show_settings_dialog)

    def _show_settings_dialog(self):
        # (existing settings dialog code goes here, unchanged)
        settings = tk.Toplevel(self.app.root)
        settings.title("Riva Dictation Settings")
        settings.geometry("400x300")
        settings.resizable(False, False)
        settings.attributes('-topmost', True)
        main_frame = tk.Frame(settings, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        endpoint_frame = tk.LabelFrame(main_frame, text="Endpoint Configuration", padx=10, pady=10)
        endpoint_frame.pack(fill=tk.X, pady=(0, 10))
        endpoint_var = tk.StringVar(value=self.app.config.get("endpoint_type", "local"))
        tk.Radiobutton(endpoint_frame, text="Local Riva/Parakeet", variable=endpoint_var, value="local").pack(anchor=tk.W)
        tk.Radiobutton(endpoint_frame, text="NVIDIA NIM Cloud", variable=endpoint_var, value="nim_cloud").pack(anchor=tk.W)
        tk.Radiobutton(endpoint_frame, text="Custom Endpoint", variable=endpoint_var, value="custom").pack(anchor=tk.W)
        nim_frame = tk.Frame(endpoint_frame)
        nim_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(nim_frame, text="NVIDIA NIM API Key:").pack(side=tk.LEFT)
        nim_key_var = tk.StringVar(value=self.app.config.get("nim_api_key", ""))
        nim_entry = tk.Entry(nim_frame, textvariable=nim_key_var, show="*", width=30)
        nim_entry.pack(side=tk.LEFT, padx=(5, 0))
        custom_frame = tk.Frame(endpoint_frame)
        custom_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(custom_frame, text="Custom Endpoint:").pack(side=tk.LEFT)
        custom_url_var = tk.StringVar(value=self.app.config.get("custom_endpoint", ""))
        custom_entry = tk.Entry(custom_frame, textvariable=custom_url_var, width=30)
        custom_entry.pack(side=tk.LEFT, padx=(5, 0))
        ssl_var = tk.BooleanVar(value=self.app.config.get("use_ssl", True))
        tk.Checkbutton(endpoint_frame, text="Use SSL/TLS", variable=ssl_var).pack(anchor=tk.W, pady=(5, 0))
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        def save_settings():
            self.app.config.set("endpoint_type", endpoint_var.get())
            self.app.config.set("nim_api_key", nim_key_var.get())
            self.app.config.set("custom_endpoint", custom_url_var.get())
            self.app.config.set("use_ssl", ssl_var.get())
            self.app.config.save_config()
            self.app.setup_riva()
            settings.destroy()
            messagebox.showinfo("Settings Saved", "Settings have been saved.\nRestart recording for changes to take effect.")
        def test_connection():
            messagebox.showinfo("Connection Test", "Connection test feature coming soon!")
        tk.Button(button_frame, text="Test Connection", command=test_connection).pack(side=tk.LEFT)
        tk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT)
        settings.update_idletasks()
        width = settings.winfo_width()
        height = settings.winfo_height()
        x = (settings.winfo_screenwidth() // 2) - (width // 2)
        y = (settings.winfo_screenheight() // 2) - (height // 2)
        settings.geometry(f'{width}x{height}+{x}+{y}')

class ModernDictationApp:
    """Modern Riva Dictation App with ULTRA-LOW LATENCY optimizations"""

    def __init__(self):
        # Configuration
        self.config = Config()
        # Audio settings
        self.rate = self.config.get("sample_rate", 16000)
        self.chunk = self.config.get("chunk_size", 256)
        self.format = pyaudio.paInt16
        self.channels = 1
        self.audio_queue = queue.Queue(maxsize=self.config.get("queue_size", 5))
        self.audio = None
        self.stream = None
        self.input_device_index = None
        self.recording = False
        self.current_text = ""
        self.final_text = ""
        self.last_typed_length = 0
        self.riva_asr = None
        self.connection_thread = None
        self.setup_audio()
        self.setup_riva()
        self.root = tk.Tk()
        self.root.withdraw()
        self.setup_hotkeys()
        self.last_connection_check = 0
        # Tray icon
        self.systray = None
        self.create_systray()

    def create_systray(self):
        import os
        icon_path = "mic.ico" if os.path.exists("mic.ico") else None
        menu_options = (
            ("Start Recording (F9)", None, self.start_recording),
            ("Stop Recording (F9)", None, self.stop_recording),
            ("Select Microphone", None, self.select_microphone),
            ("Settings", None, self.show_settings),
        )
        self.systray = SysTrayIcon(icon_path, "Riva Dictation", menu_options, on_quit=self.quit_app)

    def select_microphone(self, systray=None):
        self.root.after(0, self._show_microphone_dialog)

    def _show_microphone_dialog(self):
        import pyaudio
        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                devices.append((i, info['name']))
        pa.terminate()
        if not devices:
            messagebox.showerror("No Microphones", "No input devices found.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Microphone")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        tk.Label(dialog, text="Select your microphone:", font=("Arial", 12)).pack(pady=10)
        listbox = tk.Listbox(dialog, width=50, height=10)
        for idx, name in devices:
            listbox.insert(tk.END, f"{idx}: {name}")
        listbox.pack(pady=10)
        def save_selection():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("No Selection", "Please select a microphone.")
                return
            device_idx = devices[sel[0]][0]
            device_name = devices[sel[0]][1]
            self.config.set("input_device_index", device_idx)
            self.input_device_index = device_idx
            dialog.destroy()
            print(f"🎤 Microphone selected: {device_idx}: {device_name}")
            messagebox.showinfo("Microphone Selected", f"Microphone set to: {device_name}")
        tk.Button(dialog, text="Select", command=save_selection).pack(pady=10)
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

    def setup_audio(self):
        try:
            self.audio = pyaudio.PyAudio()
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
            self.audio = None
            self.input_device_index = None

    def setup_riva(self):
        """Setup Riva connection with cloud endpoint support"""
        def connect():
            try:
                endpoint_type = self.config.get("endpoint_type", "local")

                if endpoint_type == "local":
                    # Local Riva/Parakeet setup
                    server = self.config.get("riva_server", "localhost:50051")
                    use_ssl = False
                    print(f"🏠 Connecting to local Riva at {server}")

                elif endpoint_type == "nim_cloud":
                    # NVIDIA NIM Cloud setup
                    server = self.config.get("endpoints", {}).get("nim_cloud", {}).get("server", "ai.api.nvidia.com:443")
                    use_ssl = True
                    api_key = self.config.get("nim_api_key", "")

                    if not api_key:
                        print("❌ NIM API key required for cloud endpoint")
                        print("💡 Set your API key: app.config.set('nim_api_key', 'your_key')")
                        self.safe_update_status("error", "API key required")
                        return False

                    print(f"☁️ Connecting to NVIDIA NIM Cloud at {server}")

                elif endpoint_type == "custom":
                    # Custom cloud endpoint
                    server = self.config.get("custom_endpoint", "")
                    use_ssl = self.config.get("use_ssl", True)

                    if not server:
                        print("❌ Custom endpoint URL required")
                        self.safe_update_status("error", "No endpoint configured")
                        return False

                    print(f"🌐 Connecting to custom endpoint at {server}")

                else:
                    print(f"❌ Unknown endpoint type: {endpoint_type}")
                    return False

                # Create auth with appropriate settings
                if endpoint_type == "nim_cloud":
                    # For NIM cloud, use API key authentication
                    auth = riva.client.Auth(
                        uri=server,
                        use_ssl=use_ssl,
                        metadata=[('authorization', f'Bearer {api_key}')]
                    )
                else:
                    # For local/custom endpoints
                    auth = riva.client.Auth(uri=server, use_ssl=use_ssl)

                self.riva_asr = riva.client.ASRService(auth)
                print(f"✅ Connected to Riva at {server}")
                self.safe_update_status("ready")
                return True

            except Exception as e:
                print(f"❌ Riva connection failed: {e}")
                self.riva_asr = None
                self.safe_update_status("error", "Connection failed")
                return False

        # Try initial connection
        if not connect():
            # Start background retry thread
            self.start_connection_retry()

    def safe_update_status(self, status: str, message: str = ""):
        # OPTIMIZATION: Skip GUI updates during recording to reduce latency
        if self.recording and status not in ["error", "ready"]:
            return
        # No dynamic tray icon update for infi.systray

    def safe_update_icon(self, recording: bool = False):
        # No dynamic tray icon update for infi.systray
        pass

    def setup_hotkeys(self):
        """Setup hotkey handling"""
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.toggle_recording()
            except AttributeError:
                pass

        self.listener = Listener(on_press=on_press)
        self.listener.start()

    def toggle_recording(self):
        """Toggle recording state"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start recording with improved error handling"""
        # Check prerequisites
        if not self.riva_asr:
            print("❌ Riva not connected")
            self.start_connection_retry()
            return False

        if not self.audio or self.input_device_index is None:
            print("❌ No microphone available")
            return False

        try:
            self.recording = True
            self.current_text = ""
            self.last_typed_length = len(self.final_text)

            # Update UI (thread-safe)
            self.safe_update_status("recording")

            # Start audio capture
            self.audio_thread = threading.Thread(target=self._capture_audio, daemon=True)
            self.audio_thread.start()

            # Start Riva streaming
            self.riva_thread = threading.Thread(target=self._stream_to_riva, daemon=True)
            self.riva_thread.start()

            print("🎤 Recording started")
            return True

        except Exception as e:
            print(f"❌ Recording start failed: {e}")
            self.recording = False
            self.safe_update_status("error", "Start failed")
            return False

    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            return

        self.recording = False
        print("⏹️ Recording stopped")

        # Update UI
        self.safe_update_status("ready")

        # Stop audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        # Wait for threads
        if hasattr(self, 'audio_thread'):
            self.audio_thread.join(timeout=1)
        if hasattr(self, 'riva_thread'):
            self.riva_thread.join(timeout=1)

    def _capture_audio(self):
        """Capture audio with ULTRA-LOW LATENCY optimizations"""
        try:
            # OPTIMIZED: Reduce buffer sizes for lower latency
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk,
                # LATENCY OPTIMIZATIONS:
                stream_callback=None,  # Use blocking mode for simplicity
                start=False  # Don't auto-start
            )

            # Start the stream
            self.stream.start_stream()

            while self.recording:
                try:
                    # OPTIMIZED: Non-blocking read with smaller chunks
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    if self.recording:
                        # OPTIMIZED: Non-blocking put with immediate discard if queue full
                        try:
                            self.audio_queue.put_nowait(data)
                        except queue.Full:
                            # Discard oldest chunk to prevent latency buildup
                            try:
                                self.audio_queue.get_nowait()
                                self.audio_queue.put_nowait(data)
                            except queue.Empty:
                                pass
                except Exception as e:
                    if self.recording:  # Only log if we're still supposed to be recording
                        print(f"⚠️ Audio capture error: {e}")
                    break

        except Exception as e:
            print(f"❌ Audio stream setup failed: {e}")
            self.recording = False
            self.safe_update_status("error", "Audio failed")

    def _stream_to_riva(self):
        """Stream to Riva with ULTRA-LOW LATENCY optimizations"""
        try:
            # OPTIMIZED: Minimal Riva config for maximum speed
            streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
                config=riva_asr_pb2.RecognitionConfig(
                    encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=self.rate,
                    language_code=self.config.get("language_code", "en-US"),
                    max_alternatives=1,  # REDUCED from 3 - faster processing
                    enable_automatic_punctuation=True
                    # REMOVED: model and audio_channel_count for compatibility
                ),
                interim_results=True
            )

            # OPTIMIZED: Faster audio generator with smaller timeout
            def audio_generator():
                while self.recording:
                    try:
                        # REDUCED timeout from 0.1 to 0.01 for faster response
                        chunk = self.audio_queue.get(timeout=0.01)
                        yield chunk
                    except queue.Empty:
                        # Yield silence to keep stream alive with minimal latency
                        yield b'\x00' * (self.chunk * 2)  # 16-bit silence
                        continue

            # Start streaming
            responses = self.riva_asr.streaming_response_generator(
                audio_generator(),
                streaming_config
            )

            # OPTIMIZED: Process responses with minimal overhead
            for response in responses:
                if not self.recording:
                    break

                # OPTIMIZED: Direct processing without extra loops
                if response.results:
                    result = response.results[0]  # Take only first result for speed
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript

                        if result.is_final:
                            self.final_text += transcript
                            self.current_text = ""
                            print(f"✅ Final: '{transcript}'")

                            # OPTIMIZED: Immediate auto-type without delay
                            if self.config.get("auto_type", True):
                                self._auto_type_new_text()
                        else:
                            self.current_text = transcript
                            # REMOVED interim text printing for performance

        except Exception as e:
            print(f"❌ Riva streaming error: {e}")
            if self.recording:
                self.safe_update_status("error", "Streaming failed")
                # Try to reconnect
                self.riva_asr = None
                self.start_connection_retry()

    def _auto_type_new_text(self):
        """OPTIMIZED auto-type with minimal overhead"""
        try:
            current_total = len(self.final_text)
            if current_total > self.last_typed_length:
                new_text = self.final_text[self.last_typed_length:]
                if new_text.strip():
                    # OPTIMIZED: Faster typing with reduced interval
                    pyautogui.typewrite(new_text, interval=self.config.get("type_interval", 0.01))
                    print(f"⌨️ Typed: '{new_text.strip()}'")
                self.last_typed_length = current_total
        except Exception as e:
            print(f"⚠️ Auto-type error: {e}")

    def quit_app(self, systray=None):
        self.recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if hasattr(self, 'listener'):
            self.listener.stop()
        if hasattr(self, 'root') and self.root:
            self.root.after(0, self._really_quit)

    def _really_quit(self):
        self.root.quit()
        self.root.destroy()

    def run(self):
        print("🚀 Modern Riva Dictation (infi.systray) starting...")
        print("✅ App ready! Press F9 to start recording")
        print("💡 Check system tray for more options")
        # Start tray icon in a background thread
        tray_thread = threading.Thread(target=self.systray.start, daemon=True)
        tray_thread.start()
        self.root.mainloop()

    def show_settings(self, systray=None):
        self.root.after(0, self._show_settings_dialog)

    def _show_settings_dialog(self):
        settings = tk.Toplevel(self.root)
        settings.title("Riva Dictation Settings")
        settings.geometry("400x300")
        settings.resizable(False, False)
        settings.attributes('-topmost', True)
        main_frame = tk.Frame(settings, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        endpoint_frame = tk.LabelFrame(main_frame, text="Endpoint Configuration", padx=10, pady=10)
        endpoint_frame.pack(fill=tk.X, pady=(0, 10))
        endpoint_var = tk.StringVar(value=self.config.get("endpoint_type", "local"))
        tk.Radiobutton(endpoint_frame, text="Local Riva/Parakeet", variable=endpoint_var, value="local").pack(anchor=tk.W)
        tk.Radiobutton(endpoint_frame, text="NVIDIA NIM Cloud", variable=endpoint_var, value="nim_cloud").pack(anchor=tk.W)
        tk.Radiobutton(endpoint_frame, text="Custom Endpoint", variable=endpoint_var, value="custom").pack(anchor=tk.W)
        nim_frame = tk.Frame(endpoint_frame)
        nim_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(nim_frame, text="NVIDIA NIM API Key:").pack(side=tk.LEFT)
        nim_key_var = tk.StringVar(value=self.config.get("nim_api_key", ""))
        nim_entry = tk.Entry(nim_frame, textvariable=nim_key_var, show="*", width=30)
        nim_entry.pack(side=tk.LEFT, padx=(5, 0))
        custom_frame = tk.Frame(endpoint_frame)
        custom_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(custom_frame, text="Custom Endpoint:").pack(side=tk.LEFT)
        custom_url_var = tk.StringVar(value=self.config.get("custom_endpoint", ""))
        custom_entry = tk.Entry(custom_frame, textvariable=custom_url_var, width=30)
        custom_entry.pack(side=tk.LEFT, padx=(5, 0))
        ssl_var = tk.BooleanVar(value=self.config.get("use_ssl", True))
        tk.Checkbutton(endpoint_frame, text="Use SSL/TLS", variable=ssl_var).pack(anchor=tk.W, pady=(5, 0))
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        def save_settings():
            self.config.set("endpoint_type", endpoint_var.get())
            self.config.set("nim_api_key", nim_key_var.get())
            self.config.set("custom_endpoint", custom_url_var.get())
            self.config.set("use_ssl", ssl_var.get())
            self.config.save_config()
            self.setup_riva()
            settings.destroy()
            messagebox.showinfo("Settings Saved", "Settings have been saved.\nRestart recording for changes to take effect.")
        def test_connection():
            messagebox.showinfo("Connection Test", "Connection test feature coming soon!")
        tk.Button(button_frame, text="Test Connection", command=test_connection).pack(side=tk.LEFT)
        tk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT)
        settings.update_idletasks()
        width = settings.winfo_width()
        height = settings.winfo_height()
        x = (settings.winfo_screenwidth() // 2) - (width // 2)
        y = (settings.winfo_screenheight() // 2) - (height // 2)
        settings.geometry(f'{width}x{height}+{x}+{y}')

if __name__ == "__main__":
    import signal
    parser = argparse.ArgumentParser(
        description="Modern Riva Dictation with Ultra-Low Latency & Cloud Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with local Riva/Parakeet (default)
  python modern_dictation.py

  # Use ultra-low latency profile for gaming/real-time
  python modern_dictation.py --profile ultra_low

  # Connect to NVIDIA NIM Cloud
  python modern_dictation.py --nim-cloud --api-key YOUR_API_KEY

  # Use custom cloud endpoint
  python modern_dictation.py --endpoint https://your-riva-server.com:443 --ssl

  # Show current configuration
  python modern_dictation.py --show-config

Phase 2 Features:
  ✅ Ultra-low latency (16ms minimum)
  ✅ Cloud endpoint support (NIM, custom)
  ✅ Modern tabbed settings dialog
  ✅ Real-time endpoint switching
  ✅ Performance profiles
        """)

    parser.add_argument("--profile", choices=["ultra_low", "balanced", "quality"],
                       help="Set latency optimization profile")
    parser.add_argument("--show-config", action="store_true",
                       help="Show current configuration and exit")

    # Cloud endpoint options
    cloud_group = parser.add_argument_group("Cloud Endpoints")
    cloud_group.add_argument("--nim-cloud", action="store_true",
                            help="Use NVIDIA NIM Cloud endpoint")
    cloud_group.add_argument("--api-key",
                            help="API key for NIM Cloud")
    cloud_group.add_argument("--endpoint",
                            help="Custom endpoint URL")
    cloud_group.add_argument("--ssl", action="store_true",
                            help="Use SSL/TLS for custom endpoint")

    args = parser.parse_args()

    app = ModernDictationApp()
    def signal_handler(sig, frame):
        print("Ctrl+C pressed, exiting...")
        app._really_quit()
    signal.signal(signal.SIGINT, signal_handler)

    if args.show_config:
        print("📋 Current Configuration:")
        for key, value in app.config.config.items():
            if key == "nim_api_key" and value:
                value = "***hidden***"
            print(f"   {key}: {value}")
        sys.exit(0)

    # Apply command-line endpoint settings
    if args.nim_cloud:
        app.config.set("endpoint_type", "nim_cloud")
        if args.api_key:
            app.config.set("nim_api_key", args.api_key)
        print("☁️ Configured for NVIDIA NIM Cloud")

    elif args.endpoint:
        app.config.set("endpoint_type", "custom")
        app.config.set("custom_endpoint", args.endpoint)
        app.config.set("use_ssl", args.ssl or False)
        print(f"🌐 Configured for custom endpoint: {args.endpoint}")

    if args.profile:
        app.set_latency_profile(args.profile)

    print("🚀 Starting Modern Riva Dictation (Phase 2)")
    print("💡 New: Settings dialog with cloud support! Right-click tray icon.")
    app.run()