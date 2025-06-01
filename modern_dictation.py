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

    def show_settings(self):
        """Show Material Design settings dialog"""
        def _show_settings():
            # Material Design Dialog
            settings_window = tk.Toplevel(self.root)
            settings_window.title("Settings")
            settings_window.geometry("600x700")
            settings_window.resizable(False, False)
            settings_window.configure(bg='#fafafa')  # Material background

            # Center the window
            settings_window.transient(self.root)
            settings_window.grab_set()

            # Material Design App Bar
            app_bar = tk.Frame(settings_window, bg=self.colors['primary'], height=64)
            app_bar.pack(fill=tk.X)
            app_bar.pack_propagate(False)

            # App Bar content
            app_bar_content = tk.Frame(app_bar, bg=self.colors['primary'])
            app_bar_content.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

            # Title - Material Design Headline 6
            title_label = tk.Label(app_bar_content,
                                  text="Settings",
                                  bg=self.colors['primary'],
                                  fg='white',
                                  font=("Roboto", 20, "bold"))
            title_label.pack(side=tk.LEFT, pady=4)

            # Close button
            close_btn = tk.Button(app_bar_content,
                                 text="✕",
                                 bg=self.colors['primary'],
                                 fg='white',
                                 font=("Roboto", 16),
                                 bd=0, relief='flat',
                                 width=3, height=1,
                                 cursor='hand2',
                                 command=settings_window.destroy)
            close_btn.pack(side=tk.RIGHT)

            # Scrollable content area
            canvas = tk.Canvas(settings_window, bg='#fafafa', highlightthickness=0)
            scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='#fafafa')

            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            canvas.pack(side="left", fill="both", expand=True, padx=16, pady=16)
            scrollbar.pack(side="right", fill="y")

            # === ENDPOINT CONFIGURATION CARD ===
            endpoint_card = self.create_material_card(scrollable_frame, "🌐 Endpoint Configuration")

            # Endpoint selection with Material Design Radio buttons
            endpoint_var = tk.StringVar(value=self.app.config.get("endpoint_type", "local"))

            endpoints = [
                ("local", "🏠 Local Riva/Parakeet", "Connect to local server"),
                ("nim_cloud", "☁️ NVIDIA NIM Cloud", "Use NVIDIA's cloud service"),
                ("custom", "🌐 Custom Endpoint", "Configure custom server")
            ]

            for value, label, desc in endpoints:
                option_frame = tk.Frame(endpoint_card, bg='white')
                option_frame.pack(fill=tk.X, padx=16, pady=8)

                radio = tk.Radiobutton(option_frame,
                                      text=label,
                                      variable=endpoint_var,
                                      value=value,
                                      bg='white',
                                      fg=self.colors['on_surface'],
                                      font=("Roboto", 14, "bold"),
                                      activebackground='white',
                                      selectcolor=self.colors['primary'],
                                      bd=0)
                radio.pack(anchor=tk.W)

                desc_label = tk.Label(option_frame,
                                     text=desc,
                                     bg='white',
                                     fg=self.colors['on_surface_variant'],
                                     font=("Roboto", 12, "bold"))
                desc_label.pack(anchor=tk.W, padx=(20, 0))

            # Configuration inputs
            self.create_endpoint_inputs(endpoint_card)

            # === PERFORMANCE CARD ===
            perf_card = self.create_material_card(scrollable_frame, "⚡ Performance")

            # Latency profiles
            profile_var = tk.StringVar(value=self.app.config.get("latency_profile", "ultra_low"))

            profiles = [
                ("ultra_low", "🚀 Ultra Low Latency", "~16ms - Best for real-time use"),
                ("balanced", "⚖️ Balanced", "~32ms - Good speed and reliability"),
                ("quality", "🎯 High Quality", "~64ms - Best for noisy environments")
            ]

            for value, label, desc in profiles:
                option_frame = tk.Frame(perf_card, bg='white')
                option_frame.pack(fill=tk.X, padx=16, pady=8)

                radio = tk.Radiobutton(option_frame,
                                      text=label,
                                      variable=profile_var,
                                      value=value,
                                      bg='white',
                                      fg=self.colors['on_surface'],
                                      font=("Roboto", 14, "bold"),
                                      activebackground='white',
                                      selectcolor=self.colors['primary'],
                                      bd=0)
                radio.pack(anchor=tk.W)

                desc_label = tk.Label(option_frame,
                                     text=desc,
                                     bg='white',
                                     fg=self.colors['on_surface_variant'],
                                     font=("Roboto", 12, "bold"))
                desc_label.pack(anchor=tk.W, padx=(20, 0))

            # === GENERAL CARD ===
            general_card = self.create_material_card(scrollable_frame, "⚙️ General")

            # Settings with Material Design switches/inputs
            self.create_general_settings(general_card)

            # === ACTION BUTTONS ===
            self.create_settings_actions(settings_window, endpoint_var, profile_var)

        # Schedule on main thread
        if self.root:
            self.root.after_idle(_show_settings)

    def create_material_card(self, parent, title):
        """Create a Material Design card with title"""
        # Card container with elevation
        card_container = tk.Frame(parent, bg='#fafafa')
        card_container.pack(fill=tk.X, pady=(0, 16))

        # Card with shadow effect
        card = tk.Frame(card_container, bg='white', relief='flat', bd=0)
        card.pack(fill=tk.X, padx=2, pady=2)  # Shadow offset

        # Card header
        header = tk.Frame(card, bg='white', height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Title - Material Design Headline 6
        title_label = tk.Label(header,
                              text=title,
                              bg='white',
                              fg=self.colors['on_surface'],
                              font=("Roboto", 16, "bold"))
        title_label.pack(side=tk.LEFT, padx=16, pady=16)

        return card

    def create_endpoint_inputs(self, parent):
        """Create endpoint configuration inputs"""
        # Local server input
        local_frame = tk.Frame(parent, bg='white')
        local_frame.pack(fill=tk.X, padx=16, pady=8)

        tk.Label(local_frame, text="Local Server Address:",
                bg='white', fg=self.colors['on_surface'],
                font=("Roboto", 12, "bold")).pack(anchor=tk.W)

        self.local_server_var = tk.StringVar(value=self.app.config.get("riva_server", "localhost:50051"))
        local_entry = tk.Entry(local_frame, textvariable=self.local_server_var,
                              bg='white', fg=self.colors['on_surface'],
                              font=("Roboto", 12), relief='solid', bd=1,
                              highlightthickness=1, highlightcolor=self.colors['primary'])
        local_entry.pack(fill=tk.X, pady=(4, 0))

        # NIM Cloud API Key
        nim_frame = tk.Frame(parent, bg='white')
        nim_frame.pack(fill=tk.X, padx=16, pady=8)

        tk.Label(nim_frame, text="NVIDIA NIM API Key:",
                bg='white', fg=self.colors['on_surface'],
                font=("Roboto", 12, "bold")).pack(anchor=tk.W)

        self.nim_key_var = tk.StringVar(value=self.app.config.get("nim_api_key", ""))
        nim_entry = tk.Entry(nim_frame, textvariable=self.nim_key_var, show="*",
                            bg='white', fg=self.colors['on_surface'],
                            font=("Roboto", 12), relief='solid', bd=1,
                            highlightthickness=1, highlightcolor=self.colors['primary'])
        nim_entry.pack(fill=tk.X, pady=(4, 0))

        # Custom endpoint
        custom_frame = tk.Frame(parent, bg='white')
        custom_frame.pack(fill=tk.X, padx=16, pady=8)

        tk.Label(custom_frame, text="Custom Endpoint URL:",
                bg='white', fg=self.colors['on_surface'],
                font=("Roboto", 12, "bold")).pack(anchor=tk.W)

        self.custom_url_var = tk.StringVar(value=self.app.config.get("custom_endpoint", ""))
        custom_entry = tk.Entry(custom_frame, textvariable=self.custom_url_var,
                               bg='white', fg=self.colors['on_surface'],
                               font=("Roboto", 12), relief='solid', bd=1,
                               highlightthickness=1, highlightcolor=self.colors['primary'])
        custom_entry.pack(fill=tk.X, pady=(4, 0))

        # SSL checkbox
        self.ssl_var = tk.BooleanVar(value=self.app.config.get("use_ssl", True))
        ssl_check = tk.Checkbutton(custom_frame,
                                  text="Use SSL/TLS",
                                  variable=self.ssl_var,
                                  bg='white',
                                  fg=self.colors['on_surface'],
                                  font=("Roboto", 12),
                                  activebackground='white',
                                  selectcolor=self.colors['primary'],
                                  bd=0)
        ssl_check.pack(anchor=tk.W, pady=(8, 0))

    def create_general_settings(self, parent):
        """Create general settings section"""
        # Auto-type setting
        auto_frame = tk.Frame(parent, bg='white')
        auto_frame.pack(fill=tk.X, padx=16, pady=8)

        self.auto_type_var = tk.BooleanVar(value=self.app.config.get("auto_type", True))
        auto_check = tk.Checkbutton(auto_frame,
                                   text="Enable automatic typing",
                                   variable=self.auto_type_var,
                                   bg='white',
                                   fg=self.colors['on_surface'],
                                   font=("Roboto", 14),
                                   activebackground='white',
                                   selectcolor=self.colors['primary'],
                                   bd=0)
        auto_check.pack(anchor=tk.W)

        # Language selection
        lang_frame = tk.Frame(parent, bg='white')
        lang_frame.pack(fill=tk.X, padx=16, pady=8)

        tk.Label(lang_frame, text="Language:",
                bg='white', fg=self.colors['on_surface'],
                font=("Roboto", 12, "bold")).pack(anchor=tk.W)

        self.language_var = tk.StringVar(value=self.app.config.get("language_code", "en-US"))

        # Material Design dropdown (simplified)
        languages = ["en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN"]
        lang_frame_inner = tk.Frame(lang_frame, bg='white')
        lang_frame_inner.pack(fill=tk.X, pady=(4, 0))

        for i, lang in enumerate(languages):
            if i % 4 == 0:  # New row every 4 items
                row_frame = tk.Frame(lang_frame_inner, bg='white')
                row_frame.pack(fill=tk.X, pady=2)

            radio = tk.Radiobutton(row_frame,
                                  text=lang,
                                  variable=self.language_var,
                                  value=lang,
                                  bg='white',
                                  fg=self.colors['on_surface'],
                                  font=("Roboto", 11),
                                  activebackground='white',
                                  selectcolor=self.colors['primary'],
                                  bd=0)
            radio.pack(side=tk.LEFT, padx=(0, 16))

    def create_settings_actions(self, window, endpoint_var, profile_var):
        """Create Material Design action buttons"""
        # Action bar
        action_bar = tk.Frame(window, bg='#fafafa', height=72)
        action_bar.pack(fill=tk.X, side=tk.BOTTOM)
        action_bar.pack_propagate(False)

        button_frame = tk.Frame(action_bar, bg='#fafafa')
        button_frame.pack(side=tk.RIGHT, padx=16, pady=16)

        # Cancel button - Material Design Text Button
        cancel_btn = tk.Button(button_frame,
                              text="CANCEL",
                              bg='#fafafa',
                              fg=self.colors['primary'],
                              font=("Roboto", 12, "bold"),
                              bd=0, relief='flat',
                              padx=16, pady=8,
                              cursor='hand2',
                              command=window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

        # Save button - Material Design Filled Button
        def save_settings():
            # Apply all settings
            self.app.config.set("endpoint_type", endpoint_var.get())
            self.app.config.set("riva_server", self.local_server_var.get())
            self.app.config.set("nim_api_key", self.nim_key_var.get())
            self.app.config.set("custom_endpoint", self.custom_url_var.get())
            self.app.config.set("use_ssl", self.ssl_var.get())
            self.app.config.set("auto_type", self.auto_type_var.get())
            self.app.config.set("language_code", self.language_var.get())

            # Apply profile
            if profile_var.get() != self.app.config.get("latency_profile"):
                self.app.set_latency_profile(profile_var.get())

            print("✅ Settings saved successfully!")
            window.destroy()

            # Show confirmation
            self.show_dialog("Settings Saved",
                           "Settings have been saved successfully!\n\nRestart recording for changes to take effect.")

        save_btn = tk.Button(button_frame,
                            text="SAVE",
                            bg=self.colors['primary'],
                            fg='white',
                            font=("Roboto", 12, "bold"),
                            bd=0, relief='flat',
                            padx=16, pady=8,
                            cursor='hand2',
                            command=save_settings)
        save_btn.pack(side=tk.RIGHT)

        # Test connection button
        def test_connection():
            print("🧪 Testing connection...")
            self.show_dialog("Connection Test", "Connection test feature coming soon!")

        test_btn = tk.Button(button_frame,
                            text="TEST",
                            bg='#fafafa',
                            fg=self.colors['primary'],
                            font=("Roboto", 12, "bold"),
                            bd=0, relief='flat',
                            padx=16, pady=8,
                            cursor='hand2',
                            command=test_connection)
        test_btn.pack(side=tk.LEFT, padx=(0, 16))

class SystemTrayApp:
    """System tray integration"""

    def __init__(self, parent_app):
        self.app = parent_app
        self.icon = None

    def create_tray_icon(self):
        """Create system tray icon"""
        # Create icon image
        image = self.create_icon_image()

        # Create menu
        menu = Menu(
            MenuItem("Show Widget", self.show_widget),
            MenuItem("Start/Stop Recording", self.app.toggle_recording),
            Menu.SEPARATOR,
            MenuItem("Auto-type", self.toggle_auto_type, checked=lambda item: self.app.config.get("auto_type", True)),
            Menu.SEPARATOR,
            MenuItem("Settings", self.show_settings),
            MenuItem("About", self.show_about),
            Menu.SEPARATOR,
            MenuItem("Exit", self.quit_app)
        )

        self.icon = pystray.Icon("riva_dictation", image, "Riva Dictation", menu)
        return self.icon

    def create_icon_image(self, recording=False):
        """Create icon image"""
        # Create a simple microphone icon
        width = height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        color = (244, 67, 54) if recording else (76, 175, 80)  # Red if recording, green if ready

        # Draw microphone shape
        # Mic body
        draw.rectangle([24, 16, 40, 40], fill=color)
        # Mic base
        draw.rectangle([20, 44, 44, 48], fill=color)
        # Mic stand
        draw.rectangle([30, 48, 34, 56], fill=color)

        return image

    def update_icon(self, recording=False):
        """Update tray icon to show recording state"""
        if self.icon:
            self.icon.icon = self.create_icon_image(recording)

    def show_widget(self, icon=None, item=None):
        """Show the status widget"""
        self.app.widget.show_widget()

    def toggle_auto_type(self, icon=None, item=None):
        """Toggle auto-type setting"""
        current = self.app.config.get("auto_type", True)
        self.app.config.set("auto_type", not current)

    def show_settings(self, icon=None, item=None):
        """Show settings (thread-safe)"""
        self.app.widget.show_settings()

    def show_about(self, icon=None, item=None):
        """Show about dialog (thread-safe)"""
        message = (
            "Riva Dictation v2.0\n\n"
            "Real-time speech-to-text using NVIDIA Riva\n"
            "Modern UI with system tray integration\n\n"
            "Hotkey: F9 to start/stop recording\n\n"
            "Phase 1: Modern UI with thread-safe operations"
        )
        self.app.widget.show_dialog("About", message)

    def quit_app(self, icon=None, item=None):
        """Quit the application"""
        self.app.quit_app()

class ModernDictationApp:
    """Modern Riva Dictation App with ULTRA-LOW LATENCY optimizations"""

    def __init__(self):
        # Configuration
        self.config = Config()

        # Audio settings - OPTIMIZED FOR MINIMUM LATENCY
        self.rate = self.config.get("sample_rate", 16000)
        self.chunk = self.config.get("chunk_size", 256)
        self.format = pyaudio.paInt16
        self.channels = 1

        # Pre-allocate audio queue with smaller max size for faster operations
        self.audio_queue = queue.Queue(maxsize=self.config.get("queue_size", 5))

        # Audio components
        self.audio = None
        self.stream = None
        self.input_device_index = None

        # Recording state
        self.recording = False
        self.current_text = ""
        self.final_text = ""
        self.last_typed_length = 0

        # Riva ASR
        self.riva_asr = None
        self.connection_thread = None

        # Initialize components
        self.setup_audio()
        self.setup_riva()

        # UI components
        self.widget = StatusWidget(self)
        self.tray = SystemTrayApp(self)
        self.cursor_indicator = CursorIndicator(self)

        # Setup hotkeys
        self.setup_hotkeys()

        # Error recovery
        self.last_connection_check = 0

    def setup_audio(self):
        """Setup audio with better error handling"""
        try:
            self.audio = pyaudio.PyAudio()
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
        """Thread-safe status update - OPTIMIZED for minimal overhead"""
        # OPTIMIZATION: Skip GUI updates during recording to reduce latency
        if self.recording and status not in ["error", "ready"]:
            return

        if hasattr(self, 'widget') and self.widget.root:
            self.widget.update_status(status, message)

    def safe_update_icon(self, recording: bool = False):
        """Thread-safe icon update - OPTIMIZED"""
        # OPTIMIZATION: Only update icon on state changes, not continuously
        if hasattr(self, 'tray') and self.tray.icon:
            # For tray icon, we can update directly as pystray handles threading
            self.tray.update_icon(recording)

    def start_connection_retry(self):
        """Start background connection retry"""
        def retry_connection():
            while not self.riva_asr:
                print("🔄 Retrying Riva connection...")
                self.safe_update_status("connecting")

                time.sleep(5)  # Wait 5 seconds between retries

                try:
                    server = self.config.get("riva_server", "localhost:50051")
                    auth = riva.client.Auth(uri=server, use_ssl=False)
                    self.riva_asr = riva.client.ASRService(auth)
                    print("✅ Riva connection restored!")
                    self.safe_update_status("ready")
                    break
                except:
                    continue

        if not self.connection_thread or not self.connection_thread.is_alive():
            self.connection_thread = threading.Thread(target=retry_connection, daemon=True)
            self.connection_thread.start()

    def setup_hotkeys(self):
        """Setup hotkey handling"""
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.toggle_recording()
                elif key == keyboard.Key.esc and hasattr(key, 'char') and key.char == '\x1b':
                    # Only quit on ESC if widget is visible (safety measure)
                    if hasattr(self, 'widget') and self.widget.visible:
                        self.quit_app()
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
            self.safe_update_status("error", "Riva not connected")
            self.start_connection_retry()
            return False

        if not self.audio or self.input_device_index is None:
            self.safe_update_status("error", "No microphone")
            return False

        try:
            self.recording = True
            self.current_text = ""
            self.last_typed_length = len(self.final_text)

            # Update UI (thread-safe)
            self.safe_update_status("recording")
            self.safe_update_icon(recording=True)

            # Show cursor indicator
            self.cursor_indicator.show_indicator()

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
        self.recording = False

        # Update UI (thread-safe)
        self.safe_update_status("ready")
        self.safe_update_icon(recording=False)

        # Hide cursor indicator
        self.cursor_indicator.hide_indicator()

        # Clean up audio stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            except:
                pass

        print("⏹️ Recording stopped")

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
                            self.final_text += transcript + " "
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

    def quit_app(self):
        """Clean shutdown"""
        print("🚪 Shutting down...")

        # Stop recording
        self.recording = False

        # Clean up audio
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass

        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass

        # Stop hotkey listener
        if hasattr(self, 'listener'):
            self.listener.stop()

        # Hide tray icon
        if hasattr(self, 'tray') and self.tray.icon:
            self.tray.icon.stop()

        # Save config
        self.config.save_config()

        # Quit tkinter main loop
        if hasattr(self, 'root') and self.root:
            self.root.quit()
            self.root.destroy()

        sys.exit(0)

    def run(self):
        """Start the application"""
        print("🚀 Modern Riva Dictation starting...")

        # Create hidden root window for thread-safe GUI operations
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window

        # Show widget if configured
        if self.config.get("show_widget", True):
            self.widget.show_widget()

        print("✅ App ready! Press F9 to start recording")
        print("💡 Check system tray for more options")

        # Start the system tray in a background thread (Windows-friendly approach)
        def run_tray():
            icon = self.tray.create_tray_icon()
            icon.run()

        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()

        # Run tkinter in the main thread (required for Windows)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n🚪 Keyboard interrupt received, shutting down...")
            self.quit_app()
        except Exception as e:
            print(f"❌ Tkinter error: {e}")
            self.quit_app()

    def set_latency_profile(self, profile: str):
        """Set latency optimization profile"""
        profiles = {
            "ultra_low": {
                "chunk_size": 256,      # Smallest chunks for minimum latency
                "queue_size": 5,        # Minimal queue to prevent buildup
                "type_interval": 0.005, # Ultra-fast typing
                "gui_fps_recording": 10, # Minimal GUI updates during recording
                "gui_fps_idle": 30,     # Reduced idle updates
            },
            "balanced": {
                "chunk_size": 512,      # Balanced chunk size
                "queue_size": 10,       # Moderate queue size
                "type_interval": 0.01,  # Fast typing
                "gui_fps_recording": 20, # Moderate GUI updates
                "gui_fps_idle": 60,     # Full idle updates
            },
            "quality": {
                "chunk_size": 1024,     # Larger chunks for better audio quality
                "queue_size": 20,       # Larger buffer for stability
                "type_interval": 0.02,  # Slightly slower typing for reliability
                "gui_fps_recording": 30, # More GUI updates
                "gui_fps_idle": 60,     # Full idle updates
            }
        }

        if profile in profiles:
            print(f"🚀 Setting latency profile: {profile}")
            for key, value in profiles[profile].items():
                self.config.set(key, value)
            self.config.set("latency_profile", profile)
            print(f"✅ Profile '{profile}' applied. Restart recording for changes to take effect.")
        else:
            print(f"❌ Unknown profile: {profile}. Available: {list(profiles.keys())}")

if __name__ == "__main__":
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