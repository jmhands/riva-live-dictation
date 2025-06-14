"""
UI Components for Riva Dictation
"""

import tkinter as tk
from tkinter import ttk
import queue
from typing import Optional

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

        self.indicator = tk.Toplevel(self.app.root)
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

        # Dark theme colors
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

    def initialize(self):
        """Initialize the widget and show it"""
        self.create_widget()
        self.show_widget()
        return self.root

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

    def create_material_header(self):
        """Create Material Design header with title and close button"""
        header_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        header_frame.pack(fill=tk.X, pady=(0, 16))

        # Title with Material typography
        title_label = tk.Label(header_frame, text="Riva Dictation",
                             font=("Segoe UI", 16, "bold"),
                             bg=self.colors['surface'],
                             fg=self.colors['on_surface'])
        title_label.pack(side=tk.LEFT)

        # Close button with hover effect
        close_button = tk.Label(header_frame, text="×", font=("Segoe UI", 20),
                              bg=self.colors['surface'],
                              fg=self.colors['on_surface_variant'],
                              cursor="hand2")
        close_button.pack(side=tk.RIGHT)
        close_button.bind("<Button-1>", lambda e: self.hide_widget())

        # Add hover effects
        def on_enter(e):
            close_button.configure(fg=self.colors['error'])
        def on_leave(e):
            close_button.configure(fg=self.colors['on_surface_variant'])

        close_button.bind("<Enter>", on_enter)
        close_button.bind("<Leave>", on_leave)

    def create_material_status(self):
        """Create Material Design status section"""
        status_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        status_frame.pack(fill=tk.X, pady=(0, 16))

        # Status label with Material typography
        self.status_label = tk.Label(status_frame, text="Ready",
                                   font=("Segoe UI", 14),
                                   bg=self.colors['surface'],
                                   fg=self.colors['on_surface'])
        self.status_label.pack(side=tk.LEFT)

        # Status message with Material typography
        self.message_label = tk.Label(status_frame, text="",
                                    font=("Segoe UI", 12),
                                    bg=self.colors['surface'],
                                    fg=self.colors['on_surface_variant'])
        self.message_label.pack(side=tk.LEFT, padx=(8, 0))

    def create_material_actions(self):
        """Create Material Design action buttons"""
        actions_frame = tk.Frame(self.content_frame, bg=self.colors['surface'])
        actions_frame.pack(fill=tk.X)

        # Action buttons with Material styling
        self.record_button = tk.Button(actions_frame, text="Start Recording",
                                     font=("Segoe UI", 12),
                                     bg=self.colors['primary'],
                                     fg='white',
                                     relief='flat',
                                     cursor="hand2",
                                     command=self.app.toggle_recording)
        self.record_button.pack(side=tk.LEFT, padx=(0, 8))

        self.settings_button = tk.Button(actions_frame, text="Settings",
                                       font=("Segoe UI", 12),
                                       bg=self.colors['surface_variant'],
                                       fg=self.colors['on_surface_variant'],
                                       relief='flat',
                                       cursor="hand2",
                                       command=lambda: self.app.show_settings())
        self.settings_button.pack(side=tk.LEFT)

        # Add hover effects
        self.setup_button_hover_effects([self.record_button, self.settings_button])

    def setup_button_hover_effects(self, buttons):
        """Setup Material Design hover effects for buttons"""
        def create_hover_effect(button, normal_color, hover_color):
            def on_enter(e):
                button.configure(bg=hover_color)
            def on_leave(e):
                button.configure(bg=normal_color)
            button.bind("<Enter>", on_enter)
            button.bind("<Leave>", on_leave)

        # Apply hover effects
        create_hover_effect(self.record_button,
                          self.colors['primary'],
                          self.colors['primary_variant'])
        create_hover_effect(self.settings_button,
                          self.colors['surface_variant'],
                          self.colors['outline'])

    def setup_material_styling(self):
        """Setup Material Design styling"""
        style = ttk.Style()
        style.configure("Material.TButton",
                       font=("Segoe UI", 12),
                       padding=8)

    def setup_material_dragging(self):
        """Setup Material Design drag behavior"""
        def start_drag(event):
            self.root._drag_start_x = event.x
            self.root._drag_start_y = event.y

        def on_drag(event):
            x = self.root.winfo_x() - (self.root._drag_start_x - event.x)
            y = self.root.winfo_y() - (self.root._drag_start_y - event.y)
            self.root.geometry(f"+{x}+{y}")

        def end_drag(event):
            # Material Design: Return to normal elevation
            pass

        self.card_frame.bind("<Button-1>", start_drag)
        self.card_frame.bind("<B1-Motion>", on_drag)
        self.card_frame.bind("<ButtonRelease-1>", end_drag)

    def process_gui_updates(self):
        """Process pending GUI updates from the queue"""
        try:
            while True:
                update = self.gui_queue.get_nowait()
                if update['type'] == 'status':
                    self.status_label.configure(text=update['status'])
                    self.message_label.configure(text=update.get('message', ''))
                elif update['type'] == 'recording':
                    self.record_button.configure(
                        text="Stop Recording" if update['recording'] else "Start Recording",
                        bg=self.colors['error'] if update['recording'] else self.colors['primary']
                    )
                self.gui_queue.task_done()
        except queue.Empty:
            pass

        # Schedule next update
        if self.visible:
            self.root.after(50, self.process_gui_updates)

    def show_widget(self):
        """Show the status widget"""
        if not self.root:
            self.create_widget()
        self.root.deiconify()
        self.visible = True
        self.process_gui_updates()

    def hide_widget(self):
        """Hide the status widget"""
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
        """Update status and message (thread-safe)"""
        def _update():
            self.status_label.configure(text=status)
            self.message_label.configure(text=message)

        if self.root:
            self.root.after(0, _update)

    def show_dialog(self, title: str, message: str):
        """Show a Material Design dialog"""
        def _show_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("400x200")
            dialog.transient(self.root)
            dialog.grab_set()

            # Material Design dialog content
            content = tk.Frame(dialog, padx=24, pady=24)
            content.pack(fill=tk.BOTH, expand=True)

            # Message
            message_label = tk.Label(content, text=message,
                                   font=("Segoe UI", 12),
                                   wraplength=350)
            message_label.pack(fill=tk.X, pady=(0, 24))

            # OK button
            ok_button = tk.Button(content, text="OK",
                                font=("Segoe UI", 12),
                                bg=self.colors['primary'],
                                fg='white',
                                relief='flat',
                                command=dialog.destroy)
            ok_button.pack(side=tk.RIGHT)

        if self.root:
            self.root.after(0, _show_dialog)