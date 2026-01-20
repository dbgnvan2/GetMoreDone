#!/usr/bin/env python3
"""
Quick audio test script to verify pygame can play sound.
"""
import sys
import pygame
from pathlib import Path

print("=" * 60)
print("AUDIO TEST SCRIPT")
print("=" * 60)

# Initialize pygame mixer
try:
    pygame.mixer.init(44100, -16, 2, 512)
    print(f"✓ Pygame mixer initialized successfully")
    print(f"  Settings: {pygame.mixer.get_init()}")
except Exception as e:
    print(f"✗ Failed to initialize pygame mixer: {e}")
    sys.exit(1)

# Get music folder from settings
try:
    from src.getmoredone.app_settings import AppSettings
    settings = AppSettings.load()
    music_folder = settings.music_folder
    volume = settings.music_volume

    if not music_folder:
        print("\n✗ No music folder configured")
        print("  Please set music folder in Settings > Timer & Audio")
        sys.exit(1)

    print(f"\n✓ Music folder: {music_folder}")
    print(f"✓ Volume setting: {int(volume * 100)}%")

except Exception as e:
    print(f"\n✗ Failed to load settings: {e}")
    sys.exit(1)

# Find music files
music_folder_path = Path(music_folder)
if not music_folder_path.exists():
    print(f"\n✗ Music folder does not exist: {music_folder}")
    sys.exit(1)

audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'}
music_files = [
    f for f in music_folder_path.iterdir()
    if f.is_file() and f.suffix.lower() in audio_extensions
]

if not music_files:
    print(f"\n✗ No music files found in: {music_folder}")
    print(f"  Looking for: {', '.join(audio_extensions)}")
    sys.exit(1)

print(f"✓ Found {len(music_files)} music file(s)")

# Try to play a file
test_file = music_files[0]
print(f"\nAttempting to play: {test_file.name}")

try:
    pygame.mixer.music.load(str(test_file))
    pygame.mixer.music.set_volume(volume)
    pygame.mixer.music.play()

    print(f"✓ Music is playing at {int(volume * 100)}% volume")
    print("\n" + "=" * 60)
    print("If you hear music, your audio is working correctly!")
    print("The music will play for 5 seconds...")
    print("=" * 60)

    import time
    time.sleep(5)

    pygame.mixer.music.stop()
    print("\n✓ Test complete!")

except Exception as e:
    print(f"\n✗ Failed to play music: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
