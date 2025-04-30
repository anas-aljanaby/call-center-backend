from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta
import random
import pytz
from pydub import AudioSegment
from .base_file_uploader import BaseFileUploader


class CallRecordingUploader(BaseFileUploader):
    def __init__(self, organization_id: str = None, agent_id: str = None):
        super().__init__(bucket_name='call-recordings')
        self.organization_id = organization_id
        self.agent_id = agent_id

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

    def upload_call_recording(self, file_path: Path, original_filename: str = None) -> Dict:
        """Upload a call recording and create call metadata"""
        if not self.organization_id:
            raise ValueError("organization_id is required for call recordings")

        # Check if file is an audio file
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        if file_path.suffix.lower() not in audio_extensions:
            raise ValueError(f"File must be an audio file. Supported formats: {audio_extensions}")

        # Upload the file
        upload_result = self.upload_file(file_path, original_filename)
        if not upload_result['success']:
            return upload_result

        # Process call metadata
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
            
            # Extract storage path from URL
            storage_path = f"{self.bucket_name}/{upload_result['file_url'].split('/')[-1]}"
            
            # Create call record
            call_data = {
                'organization_id': self.organization_id,
                'agent_id': self.agent_id or self.get_random_agent(),
                'recording_url': upload_result['file_url'],
                'storage_path': storage_path,
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
                'file_url': upload_result['file_url']
            }
        except Exception as e:
            print(f"Error handling call recording {file_path.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def upload_directory(self, directory_path: str) -> List[Dict]:
        """Upload all audio files in a directory as call recordings"""
        path = Path(directory_path)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        # Define supported audio extensions
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        
        results = []
        for file_path in path.glob('*.*'):
            if file_path.suffix.lower() in audio_extensions:
                try:
                    result = self.upload_call_recording(file_path)
                    results.append(result)
                except Exception as e:
                    print(f"Error uploading {file_path}: {str(e)}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'file_path': str(file_path)
                    })
        
        return results 