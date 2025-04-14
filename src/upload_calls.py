from services.file_uploader import FileUploader
from services.agent_manager import AgentManager
import argparse
from pathlib import Path
from pydub import AudioSegment
import pydub.silence
import io
import tempfile


audio_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}
supported_document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx', '.xls', '.ppt', '.pptx', '.json', '.md'}
ignored_files = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitkeep'}

def remove_silence(audio_path: Path, min_silence_len: int = 500, silence_thresh: int = -40, verbose: bool = False) -> tuple:
    """
    Remove silences from an audio file
    
    Args:
        audio_path: Path to the audio file
        min_silence_len: Minimum length of silence to remove (in ms)
        silence_thresh: Threshold for silence detection (in dB)
        
    Returns:
        Tuple of (audio_bytes, format, original_duration, new_duration)
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
            # Return original file as bytes
            with open(audio_path, 'rb') as f:
                return f.read(), audio_path.suffix.replace('.', ''), original_duration, original_duration
            
        # Join chunks with a short silence between them
        short_silence = AudioSegment.silent(duration=200)  # 200ms silence
        processed_audio = audio_chunks[0]
        
        for chunk in audio_chunks[1:]:
            processed_audio += short_silence + chunk
        
        # Get new duration
        new_duration = len(processed_audio) / 1000  # in seconds
        
        # Calculate reduction percentage
        reduction = (original_duration - new_duration) / original_duration * 100
        
        if verbose:
            print(f"Removed silence from {audio_path.name}")
            print(f"Original duration: {original_duration:.2f}s")
            print(f"New duration: {new_duration:.2f}s")
            print(f"Reduction: {reduction:.2f}%")
        
        # Export to bytes buffer
        audio_format = audio_path.suffix.replace('.', '')
        buffer = io.BytesIO()
        
        try:
            processed_audio.export(buffer, format=audio_format)
        except Exception as e:
            print(f"Failed to export in original format: {str(e)}")
            print("Trying to export as MP3 instead...")
            audio_format = 'mp3'
            buffer = io.BytesIO()
            processed_audio.export(buffer, format='mp3')
        
        buffer.seek(0)
        return buffer.read(), audio_format, original_duration, new_duration
            
    except Exception as e:
        print(f"Error removing silence from {audio_path}: {str(e)}")
        # Return original file as bytes
        with open(audio_path, 'rb') as f:
            return f.read(), audio_path.suffix.replace('.', ''), 0, 0

def main():
    parser = argparse.ArgumentParser(description='Upload audio files to Supabase')
    parser.add_argument('path', help='Path to file or directory to upload')
    parser.add_argument('--org-id', help='ID of the organization', required=True)
    parser.add_argument('--agent-id', help='ID of the agent (optional)')
    parser.add_argument('--skip-silence-removal', action='store_true', 
                      help='Skip silence removal step')
    parser.add_argument('--min-silence-len', type=int, default=500,
                      help='Minimum length of silence to remove (in ms)')
    parser.add_argument('--silence-thresh', type=int, default=-40,
                      help='Threshold for silence detection (in dB)')
    parser.add_argument('--recursive', action='store_true',
                      help='Recursively process subdirectories')
    parser.add_argument('--verbose', action='store_true',
                      help='Verbose output')
    parser.add_argument('--min-duration', type=float, default=0,
                      help='Minimum audio duration in seconds (default: 0, no minimum)')
    args = parser.parse_args()
    
    # Initialize agent manager to handle agent selection
    agent_manager = AgentManager(args.org_id)
    
    # If no agent specified, get a random one from the organization
    agent_id = args.agent_id
    if not agent_id:
        try:
            agent = agent_manager.get_random_agent()
            agent_id = agent['id']
            if args.verbose:
                print(f"Initial agent selected: {agent['full_name']}")
                print("Note: A new random agent will be selected for each file in the directory")
        except ValueError as e:
            print(f"Error: {str(e)}")
            return

    path = Path(args.path)
    
    if path.is_file():
        process_file(path, args, agent_id, agent_manager)
    elif path.is_dir():
        results = process_directory(path, args, agent_id, agent_manager, recursive=args.recursive)
        
        # Print summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        print(f"\nUpload Summary:")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
    else:
        print(f"Error: Path does not exist: {path}")

def process_file(file_path, args, agent_id, agent_manager):
    """Process a single file"""
    # Skip system files and unsupported files
    if file_path.name in ignored_files or file_path.suffix.lower() in ignored_files:
        print(f"Skipping unsupported file: {file_path.name}")
        return None
    
    # For single file upload, determine bucket based on file type
    if file_path.suffix.lower() in audio_extensions:
        # Process audio file to remove silence if needed
        if not args.skip_silence_removal:
            audio_bytes, audio_format, orig_duration, new_duration = remove_silence(
                file_path, 
                min_silence_len=args.min_silence_len,
                silence_thresh=args.silence_thresh,
                verbose=args.verbose
            )
            
            # Skip short audio files if min_duration is set
            if args.min_duration > 0 and new_duration < args.min_duration:
                print(f"Skipping {file_path.name}: Duration ({new_duration:.2f}s) is below minimum threshold ({args.min_duration}s)")
                return {'success': False, 'message': f'Duration below minimum threshold of {args.min_duration}s'}
            
            # Create a temporary file with the processed audio
            with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = Path(temp_file.name)
        else:
            temp_path = file_path
            
            # If we're skipping silence removal, we need to check the duration manually
            if args.min_duration > 0:
                try:
                    audio = AudioSegment.from_file(file_path)
                    duration = len(audio) / 1000  # in seconds
                    if duration < args.min_duration:
                        print(f"Skipping {file_path.name}: Duration ({duration:.2f}s) is below minimum threshold ({args.min_duration}s)")
                        return {'success': False, 'message': f'Duration below minimum threshold of {args.min_duration}s'}
                except Exception as e:
                    print(f"Error checking audio duration for {file_path}: {str(e)}")
            
        # For audio files, use call-recordings bucket
        uploader = FileUploader(
            organization_id=args.org_id, 
            agent_id=agent_id,
            bucket_name='call-recordings'  # Explicitly set bucket for call recordings
        )
        
        # Upload the file
        result = uploader.upload_file(temp_path, original_filename=file_path.name)
        
        # Clean up temporary file if it was created
        if not args.skip_silence_removal and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                print(f"Warning: Could not delete temporary file {temp_path}: {e}")
    elif file_path.suffix.lower() in supported_document_extensions:
        # For supported document files, use documents bucket
        uploader = FileUploader(bucket_name='documents')
        result = uploader.upload_file(file_path)
    else:
        print(f"Skipping file with unsupported extension: {file_path.name}")
        return None
        
    status = "✓" if result['success'] else "✗"
    print(f"{status} {file_path.name}")
    return result

def process_directory(dir_path, args, agent_id, agent_manager, recursive=False):
    """Process all files in a directory"""
    results = []
    
    # Process all files in the current directory
    for file_path in dir_path.glob('*.*'):
        if file_path.is_file():
            # For each file, get a new random agent if no specific agent was provided
            current_agent_id = agent_id
            if not args.agent_id:
                agent = agent_manager.get_random_agent()
                current_agent_id = agent['id']
                if args.verbose:
                    print(f"Selected agent for {file_path.name}: {agent['full_name']}")
            
            result = process_file(file_path, args, current_agent_id, agent_manager)
            if result:
                results.append(result)
    
    # If recursive, process all subdirectories
    if recursive:
        for subdir in dir_path.iterdir():
            if subdir.is_dir():
                print(f"\nProcessing subdirectory: {subdir.name}")
                # For directories, optionally get a new random agent for each directory
                if not args.agent_id:
                    agent = agent_manager.get_random_agent()
                    subdir_agent_id = agent['id']
                else:
                    subdir_agent_id = agent_id
                
                subdir_results = process_directory(subdir, args, subdir_agent_id, agent_manager, recursive)
                results.extend(subdir_results)
    
    return results

if __name__ == "__main__":
    main() 