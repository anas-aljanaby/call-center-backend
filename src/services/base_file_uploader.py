from supabase import create_client, Client
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv
import mimetypes
from datetime import datetime

load_dotenv()

class BaseFileUploader:
    def __init__(self, bucket_name: str = 'documents'):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.bucket_name = bucket_name
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

    def upload_file(self, file_path: Path, original_filename: str = None) -> Dict:
        """Upload a single file to Supabase storage"""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
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
        
        # Get the public URL
        file_url = self.supabase.storage.from_(self.bucket_name).get_public_url(unique_filename)
        
        return {
            'success': True,
            'file_url': file_url
        } 