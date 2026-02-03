# Audio Troubleshooting Guide

## Problem: Music shows as "playing" but I only hear clicks or silence

### Cause
You're likely using **M4A, AAC, WMA, or FLAC** files, which pygame doesn't support well on macOS.

### Solution: Convert to MP3

#### Option 1: Automated Conversion (Recommended)

1. Install ffmpeg (if not already installed):
   ```bash
   brew install ffmpeg
   ```

2. Run the converter script:
   ```bash
   cd ~/ProjectsLocal/Projects/GetMoreDone
   source venv/bin/activate
   python3 convert_music_to_mp3.py
   ```

This will convert all M4A/AAC/WMA/FLAC files in your music folder to MP3.

#### Option 2: Manual Conversion

Use any audio converter to convert your files to MP3:
- **macOS**: Use iTunes/Music app → File → Convert → Create MP3 Version
- **Online**: Use cloudconvert.com or similar
- **Command line**:
  ```bash
  ffmpeg -i input.m4a -codec:a libmp3lame -q:a 2 output.mp3
  ```

### Supported Formats

✅ **Well-supported** (use these):
- MP3 (.mp3)
- WAV (.wav)
- OGG (.ogg)

⚠️ **Problematic** (may not work):
- M4A (.m4a)
- AAC (.aac)
- WMA (.wma)
- FLAC (.flac)

## Other Common Issues

### No audio device found
If you see ALSA errors or "no audio device" errors, check:
1. System Preferences → Sound → Output - ensure correct device is selected
2. Make sure system volume is not muted
3. Try unplugging/replugging headphones or speakers

### Volume too low
1. Open the app
2. Go to **Settings → Timer & Audio**
3. Set **Music Volume** to **100%**
4. Also check system volume

### Test Your Audio

Run the test script to diagnose issues:
```bash
python3 test_audio.py
```

This will tell you exactly what's wrong with your audio setup.

## Still Having Issues?

Check the console output when starting a timer. The app now provides detailed error messages:
- `[ERROR] Music file loaded but won't play` → File format not supported
- `[WARNING] Selected .m4a file` → Convert to MP3
- `[DEBUG] Pygame mixer initialized` → Audio system is working

If you see these messages, convert your files to MP3 format.
