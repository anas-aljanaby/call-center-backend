import argparse
from pathlib import Path
from pydub import AudioSegment
import pydub.silence
import os

def remove_silence(audio_path: Path, min_silence_len: int = 500, silence_thresh: int = -40) -> Path:
    """
    Remove silences from an audio file
    
    Args:
        audio_path: Path to the audio file
        min_silence_len: Minimum length of silence to remove (in ms)
        silence_thresh: Threshold for silence detection (in dB)
        
    Returns:
        Path to the processed audio file
    """
    try:
        # Load audio file
        audio = AudioSegment.from_file(audio_path)
        
        # Get original duration
        original_duration = len(audio) / 1000  # in seconds
        
        # Split on silence
        audio_chunks = pydub.silence.split_on_silence(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh
        )
        
        if not audio_chunks:
            print(f"No audio chunks found in {audio_path}. Returning original file.")
            return audio_path
            
        # Join chunks with a short silence between them
        short_silence = AudioSegment.silent(duration=200)  # 200ms silence
        processed_audio = audio_chunks[0]
        
        for chunk in audio_chunks[1:]:
            processed_audio += short_silence + chunk
        
        # Create output filename
        output_filename = f"{audio_path.stem}_no_silence"
        
        # Try to export with original format first
        try:
            output_path = Path.cwd() / f"{output_filename}{audio_path.suffix}"
            processed_audio.export(
                output_path, 
                format=audio_path.suffix.replace('.', '')
            )
        except Exception as e:
            # If original format fails, try MP3 as a fallback
            print(f"Failed to export in original format: {str(e)}")
            print("Trying to export as MP3 instead...")
            output_path = Path.cwd() / f"{output_filename}.mp3"
            processed_audio.export(output_path, format="mp3")
        
        # Get new duration
        new_duration = len(processed_audio) / 1000  # in seconds
        
        # Calculate reduction percentage
        reduction = (original_duration - new_duration) / original_duration * 100
        
        print(f"Removed silence from {audio_path.name}")
        print(f"Original duration: {original_duration:.2f}s")
        print(f"New duration: {new_duration:.2f}s")
        print(f"Reduction: {reduction:.2f}%")
        print(f"Saved to: {output_path}")
        
        return output_path
            
    except Exception as e:
        print(f"Error removing silence from {audio_path}: {str(e)}")
        return audio_path  # Return original file if processing fails

def main():
    parser = argparse.ArgumentParser(description='Remove silence from audio files')
    parser.add_argument('file_path', help='Path to the audio file')
    parser.add_argument('--min-silence', type=int, default=500, 
                        help='Minimum length of silence to remove (in ms)')
    parser.add_argument('--silence-thresh', type=int, default=-40, 
                        help='Threshold for silence detection (in dB)')
    parser.add_argument('--output-format', 
                        help='Force output format (mp3, wav, etc.)')
    args = parser.parse_args()
    
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return
    
    remove_silence(file_path, args.min_silence, args.silence_thresh)

if __name__ == "__main__":
    main() 