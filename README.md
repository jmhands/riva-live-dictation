# Real-time Voice Dictation with NVIDIA Riva

A real-time speech-to-text dictation app that types directly to your cursor using NVIDIA Riva NIM (locally hosted).

## ✨ NEW: Modern Version Available!

We now have a **modernized version** with significant UX improvements:

### 🎨 Modern UI Features (Phase 1)
- **System tray integration** - Minimal distraction, runs in background
- **Floating status widget** - Draggable, translucent, modern design
- **Visual status indicators** - Color-coded status dots and smart notifications
- **Auto-recovery** - Automatic reconnection to Riva when connection drops
- **Persistent configuration** - Settings saved between sessions
- **Improved error handling** - Better error messages and recovery

### 🚀 Quick Start (Modern Version)

```bash
# Install dependencies
pip install -r requirements.txt

# Test dependencies (recommended)
python test_modern_app.py

# Run modern version
python modern_dictation.py
```

**Usage:**
- App starts with system tray icon (green microphone)
- Floating widget appears in top-right corner (can be dragged)
- **F9**: Start/Stop recording
- Right-click tray icon for full menu
- Auto-reconnects to Riva if connection drops

---

## 📱 Original Version

The original version (`realtime_dictation.py`) is still available with the traditional window interface.

## Features

🎤 **Real-time transcription** - See words appear as you speak
⚡ **Auto-typing** - Text appears directly at your cursor position
🔒 **100% Local** - No cloud services, complete privacy
🎯 **System-wide** - Works in any application
⌨️ **Hotkey control** - F9 to start/stop dictation

## Demo

![Demo GIF placeholder - add your own demo]

## Requirements

- NVIDIA Riva NIM container running locally
- Python 3.8+
- Microphone

## Installation

### 1. Set up NVIDIA Riva NIM

```bash
# Pull and run the Riva container
docker run -it --rm \
   --runtime=nvidia \
   --gpus '"device=0"' \
   --shm-size=8GB \
   -e NGC_API_KEY=your_api_key \
   -e NIM_HTTP_API_PORT=9000 \
   -e NIM_GRPC_API_PORT=50051 \
   -p 9000:9000 \
   -p 50051:50051 \
   nvcr.io/nim/nvidia/parakeet-0-6b-ctc-en-us:latest
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Choose your version

**Modern Version (Recommended):**
```bash
python modern_dictation.py
```

**Original Version:**
```bash
python realtime_dictation.py
```

## Usage

1. **Start Riva NIM** container (see installation above)
2. **Run the dictation app** (modern or original version)
3. **Check "Auto-type to cursor"** (enabled by default)
4. **Click in any text field** (Notepad, browser, etc.)
5. **Press F9** to start real-time dictation
6. **Speak clearly** - words appear at your cursor!
7. **Press F9** to stop

### Hotkeys
- **F9**: Start/Stop dictation
- **ESC**: Exit app (modern version: only when widget visible)

## Troubleshooting

### Riva Connection Issues
```bash
# Test if Riva is running
curl http://localhost:9000/v1/health/ready
```

### Microphone Issues
- Check microphone permissions in Windows
- Use the "Test Microphone" button in the app
- Ensure your microphone is set as default input device

### Dependency Issues
```bash
# Test all dependencies (modern version)
python test_modern_app.py
```

### Modern App Specific
- **Can't see system tray icon?** Check your system tray settings
- **Widget won't show?** Right-click tray icon → "Show Widget"
- **Auto-reconnection not working?** Check Riva container status

## Technical Details

- Uses NVIDIA Riva's streaming ASR API for real-time transcription
- Requires `max_alternatives=3` in RecognitionConfig for proper results
- Streams audio in 16kHz mono PCM format
- Real-time typing uses interim and final results from Riva
- Modern version includes automatic error recovery and persistent config

## Resources

- **[NVIDIA Riva Python Clients](https://github.com/nvidia-riva/python-clients)** - Official Python client library for NVIDIA Riva
- **[Parakeet CTC ASR Model](https://build.nvidia.com/nvidia/parakeet-ctc-0_6b-asr)** - The ASR model used in this project
- **[NVIDIA Riva ASR NIM Documentation](https://docs.nvidia.com/nim/riva/asr/latest/index.html)** - Complete documentation for Riva ASR NIM

## License

MIT License - see LICENSE file

## Acknowledgments

- Built with [NVIDIA Riva](https://developer.nvidia.com/riva) speech AI platform
- Uses the [nvidia-riva-client](https://github.com/nvidia-riva/python-clients) Python library
- Powered by [NVIDIA Parakeet CTC ASR model](https://build.nvidia.com/nvidia/parakeet-ctc-0_6b-asr)