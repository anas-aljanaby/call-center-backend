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
        
    def ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_exists = any(b['name'] == self.bucket_name for b in buckets)
            
            if not bucket_exists:
                self.supabase.storage.create_bucket(self.bucket_name, {'public': False})
                print(f"Created bucket: {self.bucket_name}")
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
            
            # Get the private URL
            file_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                unique_filename,
                60 * 60 * 24  # 24 hour expiry
            )['signedURL']

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
        """Upload all audio files from a directory"""
        try:
            # Ensure bucket exists
            self.ensure_bucket_exists()
            
            directory = Path(directory_path)
            if not directory.exists():
                raise NotADirectoryError(f"Directory not found: {directory}")
            
            # Supported audio extensions
            audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
            
            # Find all audio files
            audio_files = [
                f for f in directory.rglob("*")
                if f.suffix.lower() in audio_extensions
            ]
            
            results = []
            current_time = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            for file_path in audio_files:
                # Randomly select an hour for the call
                hour_offset = random.randint(0, 23)
                call_time = current_time - timedelta(hours=hour_offset)
                
                # Ensure only 3-5 calls per hour
                if len([r for r in results if r['success'] and r['db_record']['started_at'].startswith(call_time.strftime("%Y-%m-%dT%H"))]) >= 5:
                    continue
                
                # Upload file
                result = self.upload_file(file_path)
                if result['success']:
                    # Update the call's start and end times
                    duration = result['db_record']['duration']
                    result['db_record']['started_at'] = (call_time - timedelta(seconds=duration)).isoformat()
                    result['db_record']['ended_at'] = call_time.isoformat()
                    
                    # Update the database entry with new times
                    self.supabase.table('calls').update({
                        'started_at': result['db_record']['started_at'],
                        'ended_at': result['db_record']['ended_at']
                    }).eq('id', result['db_record']['id']).execute()
                
                results.append(result)
                
                # Print status
                status = "✓" if result['success'] else "✗"
                print(f"{status} {file_path.name}")
            
            return results
            
        except Exception as e:
            print(f"Error processing directory {directory_path}: {str(e)}")
            return [] 