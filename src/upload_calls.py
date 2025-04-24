from services.call_recording_uploader import CallRecordingUploader
from services.document_uploader import DocumentUploader
from services.agent_manager import AgentManager
import argparse
from pathlib import Path
from pydub import AudioSegment
import pydub.silence
import io
import tempfile
import logging
from typing import Dict, List, Optional, Tuple, Union, Set
from dataclasses import dataclass
from enum import Enum, auto

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File type definitions
class FileType(Enum):
    AUDIO = auto()
    DOCUMENT = auto()
    UNSUPPORTED = auto()

# Constants
AUDIO_EXTENSIONS: Set[str] = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}
SUPPORTED_DOCUMENT_EXTENSIONS: Set[str] = {'.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx', '.xls', '.ppt', '.pptx', '.json', '.md'}
IGNORED_FILES: Set[str] = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitkeep'}

# Result types
@dataclass
class ProcessResult:
    """Result of processing a file"""
    success: bool
    message: str
    file_path: Path
    duration: Optional[float] = None
    reduction_percentage: Optional[float] = None

def get_file_type(file_path: Path) -> FileType:
    """
    Determine the type of file based on its extension
    
    Args:
        file_path: Path to the file
        
    Returns:
        FileType enum indicating the type of file
    """
    suffix = file_path.suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return FileType.AUDIO
    elif suffix in SUPPORTED_DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT
    else:
        return FileType.UNSUPPORTED

def remove_silence(audio_path: Path, min_silence_len: int = 500, silence_thresh: int = -40, verbose: bool = False) -> Tuple[bytes, str, float, float]:
    """
    Remove silences from an audio file
    
    Args:
        audio_path: Path to the audio file
        min_silence_len: Minimum length of silence to remove (in ms)
        silence_thresh: Threshold for silence detection (in dB)
        verbose: Whether to print verbose output
        
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
            logger.info(f"No audio chunks found in {audio_path}. Returning original file.")
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
            logger.info(f"Removed silence from {audio_path.name}")
            logger.info(f"Original duration: {original_duration:.2f}s")
            logger.info(f"New duration: {new_duration:.2f}s")
            logger.info(f"Reduction: {reduction:.2f}%")
        
        # Export to bytes buffer
        audio_format = audio_path.suffix.replace('.', '')
        buffer = io.BytesIO()
        
        try:
            processed_audio.export(buffer, format=audio_format)
        except Exception as e:
            logger.warning(f"Failed to export in original format: {str(e)}")
            logger.info("Trying to export as MP3 instead...")
            audio_format = 'mp3'
            buffer = io.BytesIO()
            processed_audio.export(buffer, format='mp3')
        
        buffer.seek(0)
        return buffer.read(), audio_format, original_duration, new_duration
            
    except Exception as e:
        logger.error(f"Error removing silence from {audio_path}: {str(e)}")
        # Return original file as bytes
        with open(audio_path, 'rb') as f:
            return f.read(), audio_path.suffix.replace('.', ''), 0, 0

class FileProcessor:
    """Class to handle file processing and uploading"""
    
    def __init__(self, org_id: str, agent_id: Optional[str] = None, verbose: bool = False):
        """
        Initialize the file processor
        
        Args:
            org_id: Organization ID
            agent_id: Optional agent ID
            verbose: Whether to print verbose output
        """
        self.org_id = org_id
        self.agent_id = agent_id
        self.verbose = verbose
        self.agent_manager = AgentManager(org_id)
        self.call_uploader = CallRecordingUploader(organization_id=org_id, agent_id=agent_id)
        self.document_uploader = DocumentUploader()
        
    def get_agent_id(self) -> str:
        """
        Get an agent ID, either the one provided or a random one
        
        Returns:
            Agent ID
        """
        if self.agent_id:
            return self.agent_id
            
        try:
            agent = self.agent_manager.get_random_agent()
            if self.verbose:
                logger.info(f"Selected agent: {agent['full_name']}")
            return agent['id']
        except ValueError as e:
            logger.error(f"Error selecting agent: {str(e)}")
            raise
    
    def process_audio_file(self, file_path: Path, args: argparse.Namespace) -> Optional[ProcessResult]:
        """
        Process an audio file
        
        Args:
            file_path: Path to the audio file
            args: Command line arguments
            
        Returns:
            ProcessResult or None if processing failed
        """
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
                logger.info(f"Skipping {file_path.name}: Duration ({new_duration:.2f}s) is below minimum threshold ({args.min_duration}s)")
                return ProcessResult(
                    success=False, 
                    message=f'Duration below minimum threshold of {args.min_duration}s',
                    file_path=file_path,
                    duration=new_duration
                )
            
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
                        logger.info(f"Skipping {file_path.name}: Duration ({duration:.2f}s) is below minimum threshold ({args.min_duration}s)")
                        return ProcessResult(
                            success=False, 
                            message=f'Duration below minimum threshold of {args.min_duration}s',
                            file_path=file_path,
                            duration=duration
                        )
                except Exception as e:
                    logger.error(f"Error checking audio duration for {file_path}: {str(e)}")
            
        # Upload the file using CallRecordingUploader
        result = self.call_uploader.upload_call_recording(temp_path, original_filename=file_path.name)
        
        # Clean up temporary file if it was created
        if not args.skip_silence_removal and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete temporary file {temp_path}: {e}")
                
        return ProcessResult(
            success=result['success'],
            message=result.get('message', ''),
            file_path=file_path,
            duration=new_duration if not args.skip_silence_removal else None,
            reduction_percentage=((orig_duration - new_duration) / orig_duration * 100) if not args.skip_silence_removal else None
        )
    
    def process_document_file(self, file_path: Path) -> ProcessResult:
        """
        Process a document file
        
        Args:
            file_path: Path to the document file
            
        Returns:
            ProcessResult
        """
        # Upload using DocumentUploader
        result = self.document_uploader.upload_document(file_path)
        
        return ProcessResult(
            success=result['success'],
            message=result.get('message', ''),
            file_path=file_path
        )
    
    def process_file(self, file_path: Path, args: argparse.Namespace) -> Optional[ProcessResult]:
        """
        Process a single file
        
        Args:
            file_path: Path to the file
            args: Command line arguments
            
        Returns:
            ProcessResult or None if file was skipped
        """
        # Skip system files and unsupported files
        if file_path.name in IGNORED_FILES or file_path.suffix.lower() in IGNORED_FILES:
            logger.info(f"Skipping unsupported file: {file_path.name}")
            return None
        
        file_type = get_file_type(file_path)
        
        if file_type == FileType.AUDIO:
            return self.process_audio_file(file_path, args)
        elif file_type == FileType.DOCUMENT:
            return self.process_document_file(file_path)
        else:
            logger.info(f"Skipping file with unsupported extension: {file_path.name}")
            return None
    
    def process_directory(self, dir_path: Path, args: argparse.Namespace, recursive: bool = False) -> List[ProcessResult]:
        """
        Process all files in a directory
        
        Args:
            dir_path: Path to the directory
            args: Command line arguments
            recursive: Whether to process subdirectories recursively
            
        Returns:
            List of ProcessResult objects
        """
        results = []
        
        # Process all files in the current directory
        for file_path in dir_path.glob('*.*'):
            if file_path.is_file():
                result = self.process_file(file_path, args)
                if result:
                    results.append(result)
        
        # If recursive, process all subdirectories
        if recursive:
            for subdir in dir_path.iterdir():
                if subdir.is_dir():
                    logger.info(f"\nProcessing subdirectory: {subdir.name}")
                    subdir_results = self.process_directory(subdir, args, recursive)
                    results.extend(subdir_results)
        
        return results

def main():
    """Main entry point for the script"""
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
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Initialize file processor
    processor = FileProcessor(args.org_id, args.agent_id, args.verbose)
    
    path = Path(args.path)
    
    if path.is_file():
        result = processor.process_file(path, args)
        if result:
            status = "✓" if result.success else "✗"
            logger.info(f"{status} {path.name}")
    elif path.is_dir():
        results = processor.process_directory(path, args, recursive=args.recursive)
        
        # Print summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"\nUpload Summary:")
        logger.info(f"✓ Successful: {successful}")
        logger.info(f"✗ Failed: {failed}")
    else:
        logger.error(f"Error: Path does not exist: {path}")

if __name__ == "__main__":
    main() 