# NVIDIA Riva Live Dictation

🎤 **Real-time voice dictation powered by NVIDIA Riva** - Professional-grade speech-to-text that types directly to your cursor with enterprise-level features and cross-platform support.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![NVIDIA Riva](https://img.shields.io/badge/NVIDIA-Riva-green.svg)](https://developer.nvidia.com/riva)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Key Features

🎯 **Real-time Streaming Recognition** - See words appear as you speak with ultra-low latency
⚡ **Auto-typing** - Text appears directly at your cursor position in any application
🌐 **Remote & Local Endpoints** - Connect to local Riva servers or remote cloud deployments
🔧 **Port Remapping** - Configure custom ports for ASR and health check services
🖥️ **Cross-Platform** - Works on Windows, Linux, and macOS
📱 **Dual Interface** - Full GUI with system tray OR headless CLI mode
🔒 **Enterprise Ready** - SSL/TLS support, advanced ASR settings, health monitoring
🎚️ **Professional ASR** - FLAC encoding, speech contexts, endpointing, quality controls

## 🚀 Quick Start

### GUI Mode (Default)
```bash
# Install and run with system tray interface
pip install -r requirements.txt
python -m riva_dictation
```

### CLI Mode (Headless)
```bash
# Run without GUI - perfect for servers and remote sessions
python -m riva_dictation --no-gui
```

### Remote Endpoint
```bash
# Connect to remote Riva server with custom ports
python -m riva_dictation --no-gui \
  --endpoint my-riva-server.com \
  --asr-port 50052 \
  --health-port 8080 \
  --ssl
```

**Usage:** Press **F9** to start/stop recording in any mode!

---

## 📋 Table of Contents

- [Installation](#installation)
- [Usage Modes](#usage-modes)
- [Endpoint Configuration](#endpoint-configuration)
- [Advanced Features](#advanced-features)
- [CLI Reference](#cli-reference)
- [Cross-Platform Support](#cross-platform-support)
- [Troubleshooting](#troubleshooting)
- [API Documentation](#api-documentation)

## 🛠️ Installation

### Prerequisites
- **Python 3.8+**
- **NVIDIA Riva server** (local or remote)
- **Microphone access**

### 1. Clone and Install
```bash
git clone https://github.com/your-repo/riva-live-dictation.git
cd riva-live-dictation
pip install -r requirements.txt
```

### 2. Set up NVIDIA Riva (Local)
```bash
# Pull and run Riva NIM container
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

### 3. Test Installation
```bash
# List available microphones
python -m riva_dictation --list-mics

# Test local connection
python -m riva_dictation --no-gui
```

## 🎮 Usage Modes

### GUI Mode with System Tray
```bash
python -m riva_dictation
```
- **System tray integration** - Minimal distraction, runs in background
- **Floating status widget** - Draggable, translucent interface
- **Settings dialog** - Full configuration through GUI
- **Microphone selection** - Visual device picker

### CLI Mode (Headless)
```bash
python -m riva_dictation --no-gui
```
- **No GUI dependencies** - Perfect for servers and containers
- **Console status updates** - All feedback through terminal
- **SSH-friendly** - Works over remote connections
- **Automation ready** - Scriptable and configurable

## 🌐 Endpoint Configuration

### Local Endpoint (Default)
```bash
# Uses localhost:50051 automatically
python -m riva_dictation --no-gui
```

### Remote Endpoint with Port Remapping
```bash
# Custom ASR and health check ports
python -m riva_dictation --no-gui \
  --endpoint riva-cluster.company.com \
  --asr-port 50052 \
  --health-port 8080
```

### SSL/TLS Secure Connection
```bash
# Encrypted connection to cloud Riva service
python -m riva_dictation --no-gui \
  --endpoint secure-riva.example.com \
  --ssl \
  --asr-port 443
```

### Configuration Persistence
Settings are automatically saved to `~/.riva_dictation_config.json`:
```json
{
  "endpoint_type": "custom",
  "custom_endpoint": "my-server.com",
  "custom_asr_port": 50052,
  "custom_health_port": 8080,
  "use_separate_health_port": true,
  "use_ssl": true
}
```

## 🎚️ Advanced Features

### Professional ASR Quality Settings
- **FLAC Audio Encoding** - 50% bandwidth reduction vs LINEAR_PCM
- **Max Alternatives** - Up to 5 recognition hypotheses
- **Profanity Filter** - Content filtering options
- **Verbatim Transcripts** - Raw vs normalized text output
- **Model Selection** - Choose specific ASR models
- **Speech Contexts** - Boost recognition of specific terms
- **Endpointing Configuration** - Voice activity detection tuning

### Audio Configuration
```bash
# List and select specific microphone
python -m riva_dictation --list-mics
python -m riva_dictation --no-gui --mic-device 1
```

### Health Monitoring
- **gRPC Health Checks** - Service availability monitoring
- **HTTP Fallback** - Alternative health check methods
- **Connection Recovery** - Automatic reconnection on failures
- **Status Reporting** - Real-time connection status

## 📖 CLI Reference

### Basic Commands
```bash
# Show help
python -m riva_dictation --help

# List microphones
python -m riva_dictation --list-mics

# GUI mode (default)
python -m riva_dictation

# CLI mode
python -m riva_dictation --no-gui
```

### Endpoint Options
```bash
--endpoint HOSTNAME        # Remote server hostname/IP
--asr-port PORT           # ASR service port (default: 50051)
--health-port PORT        # Health check port (optional)
--ssl                     # Enable SSL/TLS encryption
```

### Audio Options
```bash
--mic-device INDEX        # Microphone device index
--list-mics              # Show available microphones
```

### Complete Example
```bash
python -m riva_dictation --no-gui \
  --endpoint my-riva-cluster.com \
  --asr-port 50052 \
  --health-port 8080 \
  --ssl \
  --mic-device 1
```

## 🌍 Cross-Platform Support

### Windows ✅
- **Full GUI support** - System tray, floating widgets
- **Audio device management** - Complete microphone control
- **Hotkey integration** - Global F9 hotkey support

### Linux ✅
- **CLI mode recommended** - Perfect for headless servers
- **GUI mode available** - With proper dependencies
- **Container friendly** - Docker and Kubernetes ready

### macOS ✅
- **CLI mode fully supported** - No system tray dependencies
- **GUI mode compatible** - With permission grants
- **SSH session ready** - Remote development support

### Docker/Container Deployment
```dockerfile
FROM python:3.9-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "-m", "riva_dictation", "--no-gui", "--endpoint", "riva-server"]
```

## 🔧 Troubleshooting

### Connection Issues

If you encounter connection errors like "http1.x server" or "StatusCode.UNAVAILABLE", use the built-in diagnostics:

```bash
python -m riva_dictation --diagnose
```

This will test:
- Network connectivity to the server
- Whether the server responds to HTTP (indicating it's not a gRPC server)
- gRPC connection attempts with and without SSL

### Common Issues and Solutions

#### "Trying to connect an http1.x server (HTTP status 400)"
This error means the server is responding with HTTP instead of gRPC protocol.

**Solutions:**
1. Verify you're connecting to the correct port for the Riva ASR service
2. Check if SSL is required: `python -m riva_dictation --endpoint your-server --ssl`
3. Confirm the server is actually running Riva ASR service, not a web server
4. Contact your server administrator for the correct gRPC endpoint

#### "StatusCode.UNAVAILABLE"
This indicates the server is not reachable or not running.

**Solutions:**
1. Check if the server is running
2. Verify the server address and port are correct
3. Test network connectivity
4. Check firewall settings

#### "Health check protos not available"
This is a warning that can be safely ignored. The application will continue without health checks.

### Configuration

The application stores configuration in `~/.riva_dictation_config.json`. You can edit this file directly or use the GUI settings dialog.

Key configuration options:
- `endpoint_type`: "local" or "custom"
- `custom_endpoint`: Your server hostname/IP
- `custom_asr_port`: gRPC port for ASR service (default: 50051)
- `use_ssl`: Enable SSL/TLS encryption
- `auto_retry_ssl`: Automatically try SSL if initial connection fails

## 📚 API Documentation

### Supported Riva Features
Based on [NVIDIA NIM Riva ASR API](https://docs.nvidia.com/nim/riva/asr/latest/index.html):

- **Streaming Recognition** - Real-time audio processing
- **Automatic Punctuation** - Proper sentence formatting
- **Word Time Offsets** - Precise timing information
- **Multiple Audio Encodings** - LINEAR_PCM, FLAC support
- **Language Models** - Parakeet 0.6B CTC English model
- **Speech Contexts** - Domain-specific vocabulary boosting

### Configuration Options
```python
# Example RecognitionConfig
{
    "encoding": "FLAC",                    # Audio encoding
    "sample_rate_hertz": 16000,           # Audio sample rate
    "language_code": "en-US",             # Language
    "max_alternatives": 3,                # Recognition hypotheses
    "enable_automatic_punctuation": True, # Sentence formatting
    "profanity_filter": False,            # Content filtering
    "verbatim_transcripts": False,        # Text normalization
    "speech_contexts": [                  # Vocabulary boosting
        {"phrases": ["technical terms"], "boost": 10.0}
    ]
}
```

## 🏗️ Architecture

### Modular Design
```
riva_dictation/
├── app.py              # Main application logic
├── config.py           # Configuration management
├── cli.py              # Command-line interface
├── gui/
│   ├── widgets.py      # GUI components
│   └── indicators.py   # Visual indicators
└── __main__.py         # Entry point
```

### Key Components
- **ModernDictationApp** - Core application class
- **Config** - Persistent configuration management
- **StatusWidget** - Floating GUI status display
- **CursorIndicator** - Visual recording indicator
- **CLI Interface** - Command-line argument processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest

# Run tests
pytest

# Run with development settings
python -m riva_dictation --no-gui
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[NVIDIA Riva](https://developer.nvidia.com/riva)** - Enterprise speech AI platform
- **[NVIDIA NIM](https://build.nvidia.com/)** - Inference microservices platform
- **[Parakeet CTC ASR](https://build.nvidia.com/nvidia/parakeet-ctc-0_6b-asr)** - State-of-the-art ASR model
- **[NVIDIA Riva Python Client](https://github.com/nvidia-riva/python-clients)** - Official Python SDK

## 📞 Support

- **Documentation**: [NVIDIA Riva ASR NIM Docs](https://docs.nvidia.com/nim/riva/asr/latest/index.html)
- **Issues**: GitHub Issues for bug reports and feature requests
- **Community**: NVIDIA Developer Forums for general discussion

---

**Built with ❤️ using NVIDIA Riva - Professional speech AI for real-world applications**