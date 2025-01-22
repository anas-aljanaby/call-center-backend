from supabase import create_client, Client
import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

class CallProcessor:
    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.api_url = "http://localhost:8000"  # Update with your actual API URL
        self.bucket_name = 'call-recordings'  # Make sure this matches FileUploader
        
    def fetch_unprocessed_calls(self):
        """Fetch all unprocessed calls from the calls table"""
        response = self.supabase.table('calls') \
            .select('id, recording_url') \
            .eq('processed', False) \
            .execute()
        
        return response.data
    
    async def process_call(self, call_id: str, recording_url: str):
        """Process a single call"""
        try:
            # Extract file path from the URL - handle both signed and unsigned URLs
            file_path = recording_url.split('/')[-1]  # Get the last part of the URL
            if '?' in file_path:  # Remove query parameters if present
                file_path = file_path.split('?')[0]
            
            print(f"Attempting to access file: {file_path}")
            
            # Get a fresh signed URL
            try:
                signed_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                    path=file_path,
                    expires_in=3600  # 1 hour expiry
                )
                download_url = signed_url['signedURL']
            except Exception as e:
                print(f"Error creating signed URL: {str(e)}")
                return {'success': False, 'call_id': call_id}
            
            # Download the recording using signed URL
            print(f"Downloading from signed URL...")
            response = requests.get(download_url)
            response.raise_for_status()
            print(f"Response: {response}")

            # Prepare the file for transcription
            files = {
                'file': ('audio.wav', response.content, 'audio/wav')
            }
            
            # Prepare transcription settings
            settings = {
                "transcriptionModel": "real",
                "languageId": "ar-ir",
                "sentimentDetect": True
            }
            
            # Send to transcription endpoint
            transcription_response = requests.post(
                f"{self.api_url}/api/transcribe",
                files=files,
                data={'settings': json.dumps(settings)}
            )
            transcription_response.raise_for_status()
            transcription_data = transcription_response.json()
            
            print(f"Call ID: {call_id}")
            print(f"Transcription data: {transcription_data}")
            
            # Get events analysis
            events_settings = {
                "aiModel": "gpt-3.5-turbo"
            }
            
            events_response = requests.post(
                f"{self.api_url}/api/analyze-events",
                json={
                    'segments': transcription_data['segments'],
                    'settings': events_settings
                }
            )
            events_response.raise_for_status()
            events_data = events_response.json()
            
            # Get conversation summary
            summary_response = requests.post(
                f"{self.api_url}/api/summarize-conversation",
                json={
                    'segments': transcription_data['segments'],
                    'settings': events_settings  # Reuse the same settings
                }
            )
            summary_response.raise_for_status()
            summary_data = summary_response.json()
            
            # Update call_analytics table with transcription, events, and summary
            self.supabase.table('call_analytics').insert({
                'call_id': call_id,
                'transcription': transcription_data['segments'],
                'events': events_data['key_events'],
                'summary': summary_data['summary']
            }).execute()
            
            # Mark call as processed
            self.supabase.table('calls') \
                .update({'processed': True}) \
                .eq('id', call_id) \
                .execute()
                
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading recording: {str(e)}")
            print(f"Status code: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
            return False
        except Exception as e:
            print(f"Error processing call {call_id}: {str(e)}")
            return False
    
    async def process_all_calls(self):
        """Process all unprocessed calls"""
        unprocessed_calls = self.fetch_unprocessed_calls()
        results = []
        
        for call in unprocessed_calls:
            success = await self.process_call(call['id'], call['recording_url'])
            results.append({
                'call_id': call['id'],
                'success': success
            })
        
        return results 