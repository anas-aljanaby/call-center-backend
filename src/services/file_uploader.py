from supabase import create_client, Client
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv
import mimetypes
import librosa
import random

load_dotenv()

class FileUploader:
    def __init__(self, user_id: str, agent_id: str = None, bucket_name: str = 'call-recordings'):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.bucket_name = bucket_name
        self.user_id = user_id
        self.agent_id = agent_id
        self.ensure_bucket_exists()
        
    def ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == self.bucket_name for bucket in buckets)
            
            if not bucket_exists:
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={'public': True}  # Make bucket public
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
                .eq('user_id', self.user_id) \
                .execute()
            
            if not response.data:
                raise ValueError(f"No agents found for user_id: {self.user_id}")
            
            return random.choice(response.data)['id']
        except Exception as e:
            print(f"Error getting random agent: {str(e)}")
            raise

    def upload_file(self, file_path: Path) -> Dict:
        """Upload a single file to Supabase storage"""
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{file_path.name}"
            
            # Upload file to storage
            with open(file_path, 'rb') as f:
                self.supabase.storage.from_(self.bucket_name).upload(
                    unique_filename,
                    f.read(),
                    {'content-type': mimetypes.guess_type(file_path)[0]}
                )
            
            # Get the public URL
            file_url = self.supabase.storage.from_(self.bucket_name).get_public_url(unique_filename)

            # If it's an audio file, create a call entry
            if self.bucket_name == 'call-recordings':
                duration = int(librosa.get_duration(path=str(file_path)))
                now = datetime.now()
                
                # Get random agent if none specified
                agent_id = self.agent_id or self.get_random_agent()
                
                db_entry = {
                    'user_id': self.user_id,
                    'agent_id': agent_id,
                    'recording_url': file_url,
                    'duration': duration,
                    'started_at': (now - timedelta(seconds=duration)).isoformat(),
                    'ended_at': now.isoformat(),
                    'processed': False,
                    'resolution_status': 'pending'
                }
                response = self.supabase.table('calls').insert(db_entry).execute()
                return {
                    'success': True,
                    'file_url': file_url,
                    'db_record': response.data[0] if response.data else None
                }
            
            # For non-audio files
            return {
                'success': True,
                'file_url': file_url
            }
            
        except Exception as e:
            print(f"Error uploading file {file_path}: {str(e)}")
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