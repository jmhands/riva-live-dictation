# Mac Parakeet-MLX Speech Transcription

A comprehensive macOS script for speech transcription using the parakeet-mlx library.

## Features

- **Real-time streaming transcription** with configurable context windows
- **Interactive file selection** from current directory
- **Progress tracking** with time stamps
- **Real-time simulation mode** for testing
- **Multiple audio format support** (WAV, MP3, M4A, FLAC, AAC, OGG)
- **Automatic transcription saving** to text files
- **Configurable processing speed**

## Installation

1. Install the required package:
```bash
pip install parakeet-mlx
```

2. Make the script executable:
```bash
chmod +x mac_parakeet_transcription.py
```

## Usage

### Basic Usage

```bash
# Interactive file selection
python mac_parakeet_transcription.py

# Transcribe a specific file
python mac_parakeet_transcription.py audio_file.wav

# Real-time simulation mode
python mac_parakeet_transcription.py audio_file.wav --realtime

# Faster processing (2x speed)
python mac_parakeet_transcription.py audio_file.wav --realtime --speed 2.0

# Use a different model
python mac_parakeet_transcription.py audio_file.wav --model "mlx-community/parakeet-tdt-0.6b-v2"
```

### Command Line Options

- `audio_file` (optional): Path to the audio file to transcribe
- `--realtime`: Enable real-time simulation mode
- `--speed FACTOR`: Speed factor for real-time simulation (default: 1.0)
- `--model MODEL_NAME`: Specify which model to use (default: mlx-community/parakeet-tdt-0.6b-v2)

## How It Works

1. **Model Loading**: Downloads and loads the specified parakeet-mlx model
2. **Audio Processing**: Loads audio file and processes it in configurable chunks
3. **Streaming Context**: Uses a streaming context with left and right context frames for better accuracy
4. **Real-time Display**: Shows progress and intermediate results as transcription proceeds
5. **Output**: Displays final transcription and saves to a text file

## Example Output

```
============================================================
Mac Parakeet-MLX Speech Transcription
============================================================
Loading model: mlx-community/parakeet-tdt-0.6b-v2
Model loaded successfully!
Loading audio file: example.wav
Audio loaded - Duration: 45.2s, Sample rate: 16000Hz
Starting transcription...

[ 11.1% |    5.0s] Hello, this is a test of the transcription system.
[ 22.2% |   10.0s] Hello, this is a test of the transcription system. We are speaking clearly.
[ 33.3% |   15.0s] Hello, this is a test of the transcription system. We are speaking clearly and slowly.
...

============================================================
FINAL TRANSCRIPTION:
============================================================
Hello, this is a test of the transcription system. We are speaking clearly and slowly to ensure accurate transcription results.
============================================================

Transcription saved to: example_transcription.txt
```

## Real-time Mode

The real-time simulation mode processes audio at the same rate as the original recording, making it useful for:

- Testing latency and responsiveness
- Simulating live transcription scenarios
- Demonstrating streaming capabilities

## Supported Audio Formats

- WAV (recommended for best quality)
- MP3
- M4A
- FLAC
- AAC
- OGG

## Technical Details

- **Context Size**: Uses (256, 256) frames for left and right context
- **Chunk Duration**: 1.0 seconds for normal mode, 0.5 seconds for real-time mode
- **Sample Rate**: Automatically uses the model's preprocessor configuration
- **Memory Management**: Efficient streaming approach to handle large audio files

## Error Handling

The script includes comprehensive error handling for:
- Missing audio files
- Unsupported audio formats
- Model loading failures
- Network connectivity issues
- Interrupted transcription (Ctrl+C)

## Performance Tips

1. **Use WAV files** for best performance and accuracy
2. **Ensure good audio quality** (clear speech, minimal background noise)
3. **Use appropriate chunk sizes** for your use case
4. **Consider your hardware** - larger models may require more memory

## Troubleshooting

### ImportError for parakeet_mlx
```bash
pip install parakeet-mlx
```

### Audio file not found
- Check the file path
- Ensure the file exists in the current directory
- Use absolute paths if needed

### Model loading issues
- Check internet connection for first-time downloads
- Verify model name spelling
- Try the default model first

## License

This script is provided as-is for educational and research purposes. Please refer to the parakeet-mlx license for model usage terms. 