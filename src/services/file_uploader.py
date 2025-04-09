from supabase import create_client, Client
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv
import mimetypes
import librosa
import random
from pydub import AudioSegment
import pytz

load_dotenv()

class FileUploader:
    def __init__(self, organization_id: str = None, agent_id: str = None, bucket_name: str = 'documents'):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.bucket_name = bucket_name
        self.organization_id = organization_id
        self.agent_id = agent_id
        self.ensure_bucket_exists()

    def ensure_bucket_exists(self):
        """Ensure the storage bucket exists and has public access"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == self.bucket_name for bucket in buckets)
            
            if not bucket_exists:
                # Create bucket with public access
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={
                        'public': True  # This makes the bucket public
                    }
                )
                print(f"Created public bucket: {self.bucket_name}")
        except Exception as e:
            print(f"Error ensuring bucket exists: {str(e)}")
            raise
    
    def get_random_agent(self) -> str:
        """Get a random agent ID for the user"""
        try:
            response = self.supabase.table('agents') \
                .select('id') \
                .eq('organization_id', self.organization_id) \
                .execute()
            
            if not response.data:
                raise ValueError(f"No agents found for organization_id: {self.organization_id}")
            
            return random.choice(response.data)['id']
        except Exception as e:
            print(f"Error getting random agent: {str(e)}")
            raise

    def upload_file(self, file_path: Path, original_filename: str = None) -> Dict:
        """Upload a single file to Supabase storage"""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine if this is an audio file (call recording)
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        is_audio = file_path.suffix.lower() in audio_extensions
        
        # Set the appropriate bucket for the file type
        if is_audio and self.organization_id:
            # For call recordings, use the call-recordings bucket
            original_bucket = self.bucket_name
            self.bucket_name = 'call-recordings'
            self.ensure_bucket_exists()
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = original_filename or file_path.name
        unique_filename = f"{filename}_{timestamp}"
        
        # Upload file to storage
        with open(file_path, 'rb') as f:
            self.supabase.storage.from_(self.bucket_name).upload(
                unique_filename,
                f.read(),
                {'content-type': mimetypes.guess_type(file_path)[0]}
            )
        
        # Get the public URL instead of a signed URL
        file_url = self.supabase.storage.from_(self.bucket_name).get_public_url(unique_filename)

        # For audio files, handle as call recording if organization_id is provided
        if is_audio and self.organization_id and self.agent_id:
            result = self._handle_call_recording(file_path, file_url)
            
            # Restore original bucket name if it was changed
            if 'original_bucket' in locals():
                self.bucket_name = original_bucket
                
            return result
        
        # For non-audio files or when org_id is not provided
        if 'original_bucket' in locals():
            self.bucket_name = original_bucket
            
        return {
            'success': True,
            'file_url': file_url
        }

    def _handle_call_recording(self, file_path: Path, file_url: str) -> dict:
        """Handle the specific case of uploading call recordings"""
        try:
            # Get audio duration
            audio = AudioSegment.from_file(file_path)
            duration = int(len(audio) / 1000)  # Convert milliseconds to seconds
            
            # Get current time for start time
            now = datetime.now(pytz.UTC)
            started_at = now
            ended_at = started_at + timedelta(seconds=duration)
            
            # Randomly select resolution status
            resolution_status = random.choice(['resolved', 'pending'])
            
            # Extract storage path from URL - modified for public URLs
            # The format will be different from signed URLs
            storage_path = f"{self.bucket_name}/{file_url.split('/')[-1]}"
            
            # Create call record
            call_data = {
                'organization_id': self.organization_id,
                'agent_id': self.agent_id,
                'recording_url': file_url,
                'storage_path': storage_path,  # Store the path separately
                'duration': duration,
                'started_at': started_at.isoformat(),
                'ended_at': ended_at.isoformat(),
                'resolution_status': resolution_status,
                'processed': False
            }
            
            response = self.supabase.table('calls').insert(call_data).execute()
            
            return {
                'success': True,
                'call_id': response.data[0]['id'] if response.data else None,
                'file_url': file_url
            }
        except Exception as e:
            print(f"Error handling call recording {file_path.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_directory(self, directory_path: str) -> List[Dict]:
        """Upload all audio files in a directory"""
        path = Path(directory_path)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        # Define supported audio extensions
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        
        results = []
        # Use glob with a tuple of extensions
        for file_path in path.glob('*.*'):
            if file_path.suffix.lower() in audio_extensions:
                try:
                    result = self.upload_file(file_path)
                    results.append(result)
                except Exception as e:
                    print(f"Error uploading {file_path}: {str(e)}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'file_path': str(file_path)
                    })
        
        return results 