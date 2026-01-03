#!/usr/bin/env python3
"""
Live audio translation: English to Polish
Captures system audio, transcribes it, translates to Polish, and plays Polish audio.
"""
import os
import sys
import json
import queue
import threading
import tempfile
import subprocess
import time
import pyaudio
import audioop
from vosk import Model, KaldiRecognizer
from deep_translator import GoogleTranslator
from gtts import gTTS
import pygame

# Configuration
MODEL_PATH = "vosk-model-en-us-0.22"
VOSK_RATE = 16000  # Vosk model sample rate (capture directly at this rate)
CHUNK_SIZE = 4096  # Chunk size in samples
TARGET_LANGUAGE = "pl"  # Polish
SHOW_PARTIAL_RESULTS = False  # Show intermediate recognition results
BREAK_SECONDS = 60.0  # break

# Global queues for async processing
translation_queue = queue.Queue()
audio_playback_queue = queue.Queue()

# Control flags
running = True
playback_end_time = 0  # Timestamp when Polish audio finished playing


def get_pulseaudio_monitor():
    """
    Get PulseAudio monitor source name using pactl.
    """
    try:
        result = subprocess.run(['pactl', 'list', 'sources', 'short'],
                              capture_output=True, text=True, check=True)

        # Find monitor sources
        monitors = []
        for line in result.stdout.strip().split('\n'):
            if '.monitor' in line or 'monitor' in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    source_name = parts[1]
                    # Status is the last field (RUNNING, SUSPENDED, etc.)
                    status = parts[-1] if len(parts) > 4 else ''
                    monitors.append((source_name, status))

        if monitors:
            print("\nFound PulseAudio monitor sources:")
            for i, (monitor, status) in enumerate(monitors):
                status_indicator = "●" if status == "RUNNING" else "○"
                print(f"  {i}: {status_indicator} {monitor}")

            print("\nRecommended: Use the one that's RUNNING (●)")
            print("For Easy Effects users: Choose 'easyeffects_sink.monitor'")
            print("\nEnter number to select, or press Enter for auto-select:")
            choice = input("Selection: ").strip()

            if choice.isdigit():
                idx = int(choice)
                if 0 <= idx < len(monitors):
                    return monitors[idx][0]

            # Auto-select: prefer easyeffects_sink.monitor if RUNNING, else first RUNNING, else first
            for monitor, status in monitors:
                if 'easyeffects_sink.monitor' in monitor and status == "RUNNING":
                    print(f"Auto-selected: {monitor} (Easy Effects)")
                    return monitor

            for monitor, status in monitors:
                if status == "RUNNING":
                    print(f"Auto-selected: {monitor}")
                    return monitor

            return monitors[0][0]

        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def find_system_audio_device(p):
    """
    Find the PulseAudio monitor device (system audio output).
    """
    # First, try to find PulseAudio monitor using pactl
    pa_monitor = get_pulseaudio_monitor()
    if pa_monitor:
        print(f"\nUsing PulseAudio monitor: {pa_monitor}")
        print("This will capture all system audio output.")
        return pa_monitor  # Return the source name, not index

    # Fallback: show PyAudio devices
    print("\nAvailable PyAudio devices:")
    monitor_device = None
    valid_devices = []

    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                valid_devices.append(i)
                print(f"{i}: {info['name']} (inputs: {info['maxInputChannels']})")

                # Look for pulse or monitor devices
                if 'pulse' in info['name'].lower() or 'monitor' in info['name'].lower():
                    if monitor_device is None:
                        monitor_device = i
                        print(f"  → Potential system audio device")
        except Exception:
            continue

    if monitor_device is None and valid_devices:
        print(f"\nNo monitor device found. Valid device indices: {valid_devices}")
        print("Please enter a device index:")
        choice = input("Device index: ").strip()
        if choice and choice.isdigit():
            idx = int(choice)
            if idx in valid_devices:
                monitor_device = idx
            else:
                print(f"Error: Device {idx} is not valid or has no input channels")
                return None

    return monitor_device


def transcribe_audio(model_path, device_spec):
    """
    Capture and transcribe audio from system output using parec.
    device_spec is a PulseAudio source name (string)
    """
    global running

    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        print("Please run setup_model.py first")
        sys.exit(1)

    print("Loading Vosk model...")
    model = Model(model_path)
    recognizer = KaldiRecognizer(model, VOSK_RATE)
    recognizer.SetWords(True)

    print(f"\nStarting audio capture from {device_spec}...")
    print(f"Capturing at {VOSK_RATE}Hz (no resampling needed)")

    # Start parec subprocess to capture audio
    try:
        proc = subprocess.Popen([
            'parec',
            f'--device={device_spec}',
            '--channels=1',
            f'--rate={VOSK_RATE}',
            '--format=s16le',
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error starting parec: {e}")
        sys.exit(1)

    print("Listening to system audio... (Press Ctrl+C to stop)")
    print("Play some English speech to test (YouTube, podcast, etc.)")
    print("")

    # Calculate chunk size in bytes (2 bytes per sample for s16le)
    chunk_bytes = CHUNK_SIZE * 2

    # Track partial results for continuous output
    last_partial = ""
    last_partial_time = time.time()
    partial_timeout = 1.0  # Send partial after 1 second of no change
    sent_words_count = 0  # Track how many words we've already sent from current partial
    is_listening = True  # Track whether we're currently listening

    try:
        while running:
            # Read audio data from parec
            data = proc.stdout.read(chunk_bytes)

            if not data:
                break

            # Skip transcription if Polish audio is still playing or just finished
            if time.time() < playback_end_time:
                if is_listening:
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"\n[{timestamp}] Stopped listening (break time)")
                    is_listening = False

                # Don't feed audio to recognizer during break - just discard it
                continue
            elif not is_listening:
                # Just resumed after break - reset recognizer to clear any accumulated state
                timestamp = time.strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Started listening...")
                is_listening = True
                # Reset recognizer to clear accumulated audio
                recognizer = KaldiRecognizer(model, VOSK_RATE)
                recognizer.SetWords(True)
                last_partial = ""
                sent_words_count = 0
                continue  # Skip this first chunk after resuming

            # Check for final result
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get('text', '').strip()
                last_partial = ""  # Reset partial tracking
                sent_words_count = 0  # Reset sent words counter

                if text:
                    # Split into 12-word chunks
                    words = text.split()
                    chunk_size = 12
                    for i in range(0, len(words), chunk_size):
                        chunk = ' '.join(words[i:i + chunk_size])
                        if chunk:
                            timestamp = time.strftime("%H:%M:%S")
                            print(f"\n[{timestamp}] [EN] {chunk}")
                            translation_queue.put(chunk)
                            # Wait for translation and audio playback to complete
                            translation_queue.join()
                            audio_playback_queue.join()
            else:
                # Check partial results for continuous output
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get('partial', '').strip()

                if partial_text and partial_text != last_partial:
                    # Partial result changed, update tracking
                    last_partial = partial_text
                    last_partial_time = time.time()

                    # Check if we have enough NEW words to send (beyond what we've already sent)
                    words = partial_text.split()
                    unsent_words = words[sent_words_count:]

                    if len(unsent_words) >= 12:
                        # Send only the next 12 words
                        chunk = ' '.join(unsent_words[:12])
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"\n[{timestamp}] [EN] {chunk}")
                        translation_queue.put(chunk)
                        translation_queue.join()
                        # Wait for audio to finish playing before continuing
                        audio_playback_queue.join()
                        # Update sent counter
                        sent_words_count += 12

                # Removed stable partial sending - only send when we have 12 words

    except KeyboardInterrupt:
        print("\n\nStopping...")
        running = False

    finally:
        proc.terminate()
        proc.wait()


def translate_worker():
    """
    Worker thread to translate text to Polish.
    """
    global running
    translator = GoogleTranslator(source='en', target=TARGET_LANGUAGE)

    while running or not translation_queue.empty():
        try:
            text = translation_queue.get(timeout=1)

            try:
                translated = translator.translate(text)
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] [PL] {translated}")
                audio_playback_queue.put(translated)
            except Exception as e:
                print(f"Translation error: {e}")

            translation_queue.task_done()

        except queue.Empty:
            continue


def get_sink_inputs(sink_name):
    """Get all sink-input IDs for a given sink."""
    try:
        # Get the sink ID
        result = subprocess.run(['pactl', 'list', 'sinks', 'short'],
                              capture_output=True, text=True, check=True)
        sink_id = None
        for line in result.stdout.split('\n'):
            if sink_name in line:
                sink_id = line.split()[0]
                break

        if not sink_id:
            return []

        # Get sink inputs for this sink
        result = subprocess.run(['pactl', 'list', 'sink-inputs', 'short'],
                              capture_output=True, text=True, check=True)
        sink_inputs = []
        for line in result.stdout.split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == sink_id:
                    sink_inputs.append(parts[0])

        return sink_inputs
    except:
        return []


def get_firefox_sink_inputs():
    """Get only Firefox sink-input IDs (for selective ducking)."""
    try:
        result = subprocess.run(['pactl', 'list', 'sink-inputs'],
                              capture_output=True, text=True, check=True)

        firefox_inputs = []
        current_id = None
        current_name = None

        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('Sink Input #'):
                # Save previous entry if it was Firefox
                if current_id and current_name and 'firefox' in current_name.lower():
                    firefox_inputs.append(current_id)
                # Start new entry
                current_id = line.split('#')[1]
                current_name = None
            elif 'application.name = ' in line:
                current_name = line.split('=')[1].strip().strip('"')

        # Don't forget the last entry
        if current_id and current_name and 'firefox' in current_name.lower():
            firefox_inputs.append(current_id)

        return firefox_inputs
    except:
        return []


def get_sink_input_volume(sink_input):
    """Get the current volume of a sink input."""
    try:
        result = subprocess.run(['pactl', 'list', 'sink-inputs'],
                              capture_output=True, text=True, check=True)

        in_target_input = False
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith(f'Sink Input #{sink_input}'):
                in_target_input = True
            elif line.startswith('Sink Input #'):
                in_target_input = False
            elif in_target_input and 'Volume:' in line:
                # Extract the percentage value (e.g., "Volume: front-left: 65536 / 100% / 0.00 dB")
                parts = line.split('/')
                if len(parts) >= 2:
                    percent = parts[1].strip().rstrip('%')
                    return percent + '%'
        return '100%'  # Default if we can't find it
    except:
        return '100%'


def audio_playback_worker():
    """
    Worker thread to convert translated text to speech and play it.
    Measures audio duration to prevent capturing our own output.
    Ducks (lowers) only Firefox audio during Polish playback, keeping game audio at full volume.
    """
    global running, playback_end_time
    # Play to Easy Effects sink (where headphones are)
    playback_sink = "easyeffects_sink"
    duck_volume = "30%"  # Lower background audio to 30%

    while running or not audio_playback_queue.empty():
        try:
            text = audio_playback_queue.get(timeout=1)

            try:
                # Create temporary file for audio
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                    temp_file = fp.name

                # Generate speech
                tts = gTTS(text=text, lang=TARGET_LANGUAGE)
                tts.save(temp_file)

                # Get audio duration using ffprobe
                try:
                    result = subprocess.run([
                        'ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                        temp_file
                    ], capture_output=True, text=True, check=True)
                    audio_duration = float(result.stdout.strip())
                except:
                    # Fallback: estimate based on text length (~15 chars per second)
                    audio_duration = len(text) / 15.0

                # Get Firefox sink inputs only (for selective ducking)
                firefox_inputs = get_firefox_sink_inputs()

                # Store original volumes before ducking
                original_volumes = {}
                for sink_input in firefox_inputs:
                    original_volumes[sink_input] = get_sink_input_volume(sink_input)

                # Duck (lower) only Firefox audio, keep game audio at full volume
                for sink_input in firefox_inputs:
                    subprocess.run(['pactl', 'set-sink-input-volume', sink_input, duck_volume],
                                 stderr=subprocess.DEVNULL)

                # Set the end time BEFORE starting playback
                # This prevents transcription during playback + 20 sec break
                playback_end_time = time.time() + audio_duration + BREAK_SECONDS

                # Play audio using paplay (blocking - waits until done)
                subprocess.run([
                    'paplay',
                    f'--device={playback_sink}',
                    temp_file
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Restore Firefox audio to original volumes
                for sink_input in firefox_inputs:
                    original_volume = original_volumes.get(sink_input, '100%')
                    subprocess.run(['pactl', 'set-sink-input-volume', sink_input, original_volume],
                                 stderr=subprocess.DEVNULL)

                # Clean up
                os.unlink(temp_file)

            except Exception as e:
                print(f"Audio playback error: {e}")

            audio_playback_queue.task_done()

        except queue.Empty:
            continue


def main():
    """
    Main function to coordinate all threads.
    """
    global running

    # Get PulseAudio monitor source
    device_spec = get_pulseaudio_monitor()

    if device_spec is None:
        print("No audio device selected. Exiting.")
        sys.exit(1)

    print(f"\nUsing PulseAudio source: {device_spec}")

    # Start worker threads
    translator_thread = threading.Thread(target=translate_worker, daemon=True)
    playback_thread = threading.Thread(target=audio_playback_worker, daemon=True)

    translator_thread.start()
    playback_thread.start()

    # Start transcription (runs in main thread)
    try:
        transcribe_audio(MODEL_PATH, device_spec)
    except KeyboardInterrupt:
        print("\nShutting down...")
        running = False

    # Wait for queues to empty
    print("Waiting for remaining translations...")
    translation_queue.join()
    audio_playback_queue.join()

    # Wait for threads to finish
    translator_thread.join(timeout=5)
    playback_thread.join(timeout=5)

    print("Done!")


if __name__ == "__main__":
    main()
