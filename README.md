# Live Audio Translation: English to Polish

This tool captures system audio (everything playing on your computer), transcribes it from English, translates to Polish, and plays the Polish audio with a few seconds delay. It also lowers system audio while playing. 

## Requirements

- Linux with PulseAudio/PipeWire
- Python 3.8+
- Internet connection (for translation and TTS)
- ffmpeg/ffprobe (for audio duration detection)

## Setup

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pyaudio portaudio19-dev ffmpeg
```

### 2. Create Virtual Environment and Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Download Vosk Model

Download the large, high-accuracy model (1.8GB):

```bash
python download_large_model.py
```

This downloads `vosk-model-en-us-0.22` which provides excellent transcription accuracy.

## Usage

### Run the Live Translator

```bash
source venv/bin/activate
python live_translate.py
```

The script will:
1. Show you all available PulseAudio monitor sources with status indicators (● = running, ○ = suspended)
2. Auto-select a running monitor (or let you choose manually)
3. Start listening to system audio
4. Display English transcription and Polish translation
5. Play Polish audio through your headphones/speakers

### Selecting the Right Audio Device

The script auto-detects running PulseAudio monitors. Common options:
- `easyeffects_sink.monitor` - If using Easy Effects (recommended)
- `alsa_output.pci-0000_00_1f.3.analog-stereo.monitor` - Built-in audio
- `alsa_output.usb-*.monitor` - USB audio interfaces

Press Enter to auto-select, or type a number to choose manually.

### Stopping

Press `Ctrl+C` to stop the translation.

## How It Works

1. **Audio Capture**: Uses `parec` to capture mono audio directly at 16kHz from PulseAudio monitor
2. **Speech Recognition**: Vosk large model (1.8GB) transcribes English audio to text offline
3. **Chunk Splitting**: Long transcriptions are split into 10-word chunks for faster feedback
4. **Translation**: Google Translate API translates English chunks to Polish (requires internet)
5. **Text-to-Speech**: gTTS generates Polish audio (requires internet)
6. **Audio Ducking**: English audio is lowered to 30% volume while Polish plays
7. **Playback**: Polish audio plays via `paplay`, then English audio returns to 100%
8. **Feedback Prevention**: Transcription is paused during Polish playback (duration-based) to prevent capturing translated output

## Key Features

### Audio Ducking
When Polish translation plays, the background English audio automatically lowers to 30% volume, then returns to 100% when finished. This makes the translation easy to hear without completely muting the source.

### Feedback Loop Prevention
The system measures each Polish audio clip's duration and pauses transcription for that duration + 1 second buffer. This ensures the Polish audio is never captured and re-translated, even when headphones play to the same sink being monitored.

### Smart Chunking
Long sentences are split into 10-word chunks, so you get shorter, more frequent Polish translations instead of waiting for entire paragraphs.

### Noise Filtering
Short transcriptions and background noise are filtered out to reduce unnecessary translations.

## Configuration

Edit `live_translate.py` to customize:

- **Line 24**: `TARGET_LANGUAGE = "pl"` - Change translation target language
- **Line 196**: `chunk_size = 10` - Adjust chunk size (5-15 words recommended)
- **Line 276**: `duck_volume = "30%"` - Adjust ducking level (20-50% recommended)
- **Line 22**: `VOSK_RATE = 16000` - Audio capture rate (matches Vosk model)
- **Line 21**: `MODEL_PATH` - Path to Vosk model

## Troubleshooting

### No audio device found
- Make sure PulseAudio/PipeWire is running: `pulseaudio --check` or `systemctl --user status pipewire`
- List devices: `pactl list sources short`
- Look for sources with `.monitor` in the name and `RUNNING` status

### "ALSA lib" warnings
These are harmless ALSA/PulseAudio compatibility warnings and can be ignored.

### No transcription appearing
- Make sure there's clear English speech playing (news, podcasts work best)
- Check your system volume
- Avoid music or fast speech - Vosk works best with clear, moderate-paced speech
- Try selecting a different audio monitor

### Polish audio creates feedback loop
The system should prevent this automatically. If it still occurs:
- Check that `playback_sink = "easyeffects_sink"` (line 273) matches where your headphones are connected
- The cooldown system should prevent re-capture, but you can increase the buffer on line 312

### Translation errors
- Check your internet connection (required for Google Translate and gTTS)
- Translation and TTS are online services

### Audio playback issues
- Make sure your speakers/headphones are working
- Check system audio isn't muted
- Verify ffprobe is installed: `ffprobe -version`

### Poor transcription quality
- Use clear, professional speech (news broadcasts, podcasts)
- Avoid background music or noise
- Don't play audio at 0.5x or 2x speed - use normal playback
- The large model is already quite accurate; poor results usually mean unclear source audio

## Performance Notes

- First transcription may be slow (model loading)
- Translation adds ~1-2 second latency
- Audio ducking happens in real-time (<100ms)
- Transcription is paused during Polish playback to avoid feedback

## Limitations

- Requires internet for translation and TTS (transcription is offline)
- Translation/TTS adds 1-3 second latency
- Works best with clear, moderate-paced speech
- Captures ALL system audio (music, notifications, etc.)
- Vosk model is English-only for transcription

## Credits

- **Vosk**: Offline speech recognition (https://alphacephei.com/vosk/)
- **deep-translator**: Translation API wrapper
- **gTTS**: Google Text-to-Speech
- **PulseAudio/PipeWire**: Audio capture via `parec`
- **ffmpeg**: Audio duration detection
