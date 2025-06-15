import argparse
import sys


def main() -> None:
    """Command-line entry point for Riva Dictation."""
    parser = argparse.ArgumentParser(
        prog="riva-dictation",
        description="Real-time voice dictation powered by NVIDIA Riva",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run without the floating widget (transcription only)",
    )

    # Endpoint configuration
    parser.add_argument(
        "--endpoint",
        type=str,
        help="Custom endpoint hostname or IP (e.g., my-server.com or 192.168.1.100)",
    )
    parser.add_argument(
        "--asr-port",
        type=int,
        default=50051,
        help="ASR service port (default: 50051)",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        help="Health check port (if different from ASR port)",
    )
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Use SSL/TLS for connection",
    )

    # Audio configuration
    parser.add_argument(
        "--mic-device",
        type=int,
        help="Microphone device index (use --list-mics to see available devices)",
    )
    parser.add_argument(
        "--list-mics",
        action="store_true",
        help="List available microphone devices and exit",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run connection diagnostics and exit",
    )

    args = parser.parse_args()

    # Handle diagnostics
    if args.diagnose:
        try:
            from riva_dictation.app import ModernDictationApp
            from riva_dictation.config import Config

            config = Config()

            # Apply CLI configuration overrides for diagnostics
            if args.endpoint:
                config.set("endpoint_type", "custom")
                config.set("custom_endpoint", args.endpoint)
                config.set("custom_asr_port", args.asr_port)
                config.set("use_ssl", args.ssl)
                server = f"{args.endpoint}:{args.asr_port}"
            else:
                endpoint_type = config.get("endpoint_type")
                if endpoint_type == "custom":
                    custom_endpoint = config.get("custom_endpoint")
                    custom_asr_port = config.get("custom_asr_port", 50051)
                    if custom_endpoint:
                        if ':' in custom_endpoint:
                            server = custom_endpoint
                        else:
                            server = f"{custom_endpoint}:{custom_asr_port}"
                    else:
                        server = f"localhost:{custom_asr_port}"
                else:
                    endpoint = config.get("endpoints", {}).get(endpoint_type, {})
                    server = endpoint.get("server", "localhost:50051")

            # Create a temporary app instance for diagnostics
            app = ModernDictationApp(headless=True)
            app.diagnose_connection(server, test_ssl=True)
            return

        except Exception as e:
            print(f"❌ Error running diagnostics: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Handle list microphones
    if args.list_mics:
        try:
            import pyaudio
            audio = pyaudio.PyAudio()
            print("🎤 Available Microphone Devices:")
            print("=" * 50)
            device_count = audio.get_device_count()
            for i in range(device_count):
                info = audio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    print(f"  {i}: {info['name']} ({info['maxInputChannels']} channels)")
            audio.terminate()
            return
        except Exception as e:
            print(f"❌ Error listing microphones: {e}", file=sys.stderr)
            sys.exit(1)

    # Lazy import so that CLI is fast and dependencies are loaded only when needed.
    try:
        from riva_dictation.app import ModernDictationApp
        from riva_dictation.config import Config
    except ModuleNotFoundError as e:
        print(f"❌ Riva Dictation app not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error importing Riva Dictation app: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Apply CLI configuration overrides
    config = Config()

    # Configure endpoint
    if args.endpoint:
        print(f"🔗 Using custom endpoint: {args.endpoint}")
        config.set("endpoint_type", "custom")
        config.set("custom_endpoint", args.endpoint)
        config.set("custom_asr_port", args.asr_port)
        if args.health_port:
            config.set("use_separate_health_port", True)
            config.set("custom_health_port", args.health_port)
            print(f"🏥 Health check port: {args.health_port}")
        config.set("use_ssl", args.ssl)
        if args.ssl:
            print("🔒 SSL enabled")
        print(f"🎯 ASR port: {args.asr_port}")
    else:
        print("🏠 Using local endpoint (localhost:50051)")
        config.set("endpoint_type", "local")

    # Configure microphone
    if args.mic_device is not None:
        config.set("input_device_index", args.mic_device)
        print(f"🎤 Using microphone device: {args.mic_device}")

    app = ModernDictationApp(headless=args.no_gui)
    app.run()


if __name__ == "__main__":
    main()