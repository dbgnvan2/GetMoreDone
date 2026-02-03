#!/usr/bin/env python3
"""
Convert M4A/AAC music files to MP3 for better pygame compatibility.
Requires ffmpeg to be installed: brew install ffmpeg
"""
import sys
import subprocess
from pathlib import Path

def check_ffmpeg():
    """Check if ffmpeg is installed."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def convert_to_mp3(input_file: Path, output_file: Path = None):
    """Convert audio file to MP3."""
    if output_file is None:
        output_file = input_file.with_suffix('.mp3')

    # Skip if already MP3 or output already exists
    if input_file.suffix.lower() == '.mp3':
        print(f"⊘ Skipping {input_file.name} (already MP3)")
        return True

    if output_file.exists():
        print(f"⊘ Skipping {input_file.name} (MP3 already exists)")
        return True

    print(f"Converting {input_file.name} → {output_file.name}...", end=' ')

    try:
        # Convert with good quality settings
        subprocess.run([
            'ffmpeg', '-i', str(input_file),
            '-codec:a', 'libmp3lame',
            '-q:a', '2',  # High quality (0-9, lower is better)
            '-y',  # Overwrite
            str(output_file)
        ], capture_output=True, check=True)
        print("✓")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("MUSIC CONVERTER - Convert M4A/AAC to MP3 for pygame")
    print("=" * 60)

    # Check for ffmpeg
    if not check_ffmpeg():
        print("\n✗ ffmpeg is not installed!")
        print("  Install it with: brew install ffmpeg")
        print("  Or download from: https://ffmpeg.org/download.html")
        sys.exit(1)

    print("✓ ffmpeg is installed\n")

    # Get music folder from settings
    try:
        from src.getmoredone.app_settings import AppSettings
        settings = AppSettings.load()
        music_folder = settings.music_folder

        if not music_folder:
            print("✗ No music folder configured")
            print("  Please set music folder in Settings > Timer & Audio")
            sys.exit(1)

        print(f"Music folder: {music_folder}\n")
    except Exception as e:
        print(f"✗ Failed to load settings: {e}")
        sys.exit(1)

    # Find files to convert
    music_folder_path = Path(music_folder)
    if not music_folder_path.exists():
        print(f"✗ Music folder does not exist: {music_folder}")
        sys.exit(1)

    convertible_formats = {'.m4a', '.aac', '.wma', '.flac'}
    files_to_convert = [
        f for f in music_folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in convertible_formats
    ]

    if not files_to_convert:
        print("✓ No files need conversion (no M4A/AAC/WMA/FLAC files found)")
        sys.exit(0)

    print(f"Found {len(files_to_convert)} file(s) to convert:\n")

    # Convert each file
    success_count = 0
    for file in files_to_convert:
        if convert_to_mp3(file):
            success_count += 1

    print(f"\n{'=' * 60}")
    print(f"✓ Converted {success_count}/{len(files_to_convert)} files successfully")
    print(f"{'=' * 60}")
    print("\nYou can now use the MP3 files for timer music playback!")
    print("The original files are kept - you can delete them if desired.")

if __name__ == '__main__':
    main()
