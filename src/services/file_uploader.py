from supabase import create_client, Client
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import mimetypes

load_dotenv()

class FileUploader:
    def __init__(self, agent_id: str = None):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.bucket_name = 'call-recordings'
        self.agent_id = agent_id
        
    def ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            # List buckets to check if ours exists
            buckets = self.supabase.storage.list_buckets()
            bucket_exists = any(b['name'] == self.bucket_name for b in buckets)
            
            if not bucket_exists:
                self.supabase.storage.create_bucket(self.bucket_name, {'public': False})
                print(f"Created bucket: {self.bucket_name}")
        except Exception as e:
            print(f"Error ensuring bucket exists: {str(e)}")
            raise
    
    def upload_file(self, file_path: Path) -> Dict:
        """Upload a single file to Supabase storage and create database entry"""
        try:
            # Ensure file exists
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Generate a unique filename
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
            
            # Create database entry with agent_id
            db_entry = {
                'recording_url': file_url,
                'original_filename': file_path.name,
                'processed': False,
                'created_at': datetime.now().isoformat()
            }
            
            # Add agent_id if provided
            if self.agent_id:
                db_entry['agent_id'] = self.agent_id
            
            # Insert into database
            response = self.supabase.table('calls').insert(db_entry).execute()
            
            return {
                'success': True,
                'file_url': file_url,
                'db_record': response.data[0] if response.data else None
            }
            
        except Exception as e:
            print(f"Error uploading file {file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'file_path': str(file_path)
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
            for file_path in audio_files:
                result = self.upload_file(file_path)
                results.append(result)
                
                # Print status
                status = "✓" if result['success'] else "✗"
                print(f"{status} {file_path.name}")
            
            return results
            
        except Exception as e:
            print(f"Error processing directory {directory_path}: {str(e)}")
            return [] 