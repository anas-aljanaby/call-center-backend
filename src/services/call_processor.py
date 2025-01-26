from supabase import create_client, Client
import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

class CallProcessor:
    def __init__(self, organization_id: str):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.organization_id = organization_id
        self.api_url = "http://localhost:8000"  # Update with your actual API URL
        self.bucket_name = 'call-recordings'  # Make sure this matches FileUploader
        
    def fetch_unprocessed_calls(self):
        """Fetch all unprocessed calls from the calls table"""
        response = self.supabase.table('calls') \
            .select('id, recording_url') \
            .eq('organization_id', self.organization_id) \
            .eq('processed', False) \
            .execute()
        
        return response.data
    
    async def process_call(self, call_id: str, recording_url: str):
        """Process a single call"""
        try:
            # Extract file path from the URL
            file_path = recording_url.split('/')[-1]
            if '?' in file_path:
                file_path = file_path.split('?')[0]
            
            print(f"Attempting to access file: {file_path}")
            
            # Get a fresh signed URL
            try:
                signed_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                    path=file_path,
                    expires_in=3600
                )
                download_url = signed_url['signedURL']
            except Exception as e:
                print(f"Error creating signed URL: {str(e)}")
                return {'success': False, 'call_id': call_id}
            
            # Download the recording
            print(f"Downloading from signed URL...")
            response = requests.get(download_url)
            response.raise_for_status()
            print(f"Response: {response}")

            # Prepare the file for transcription
            files = {
                'file': ('audio.wav', response.content, 'audio/wav')
            }
            
            # Transcribe
            settings = {
                "transcriptionModel": "real",
                "languageId": "ar-ir",
                "sentimentDetect": False
            }
            
            transcription_response = requests.post(
                f"{self.api_url}/api/transcribe",
                files=files,
                data={'settings': json.dumps(settings)}
            )
            transcription_response.raise_for_status()
            transcription_data = transcription_response.json()
            
            print(f"Call ID: {call_id}")
            print(f"Transcription data: {transcription_data}")
            
            print(f"Segments being sent for analysis: {transcription_data['segments']}")
            
            # Get events analysis
            events_response = requests.post(
                f"{self.api_url}/api/analyze-events",
                json={
                    'segments': transcription_data['segments'],
                    'settings': {"aiModel": "gpt-4o"}
                }
            )
            events_response.raise_for_status()
            events_data = events_response.json()
            
            # Get conversation summary
            summary_response = requests.post(
                f"{self.api_url}/api/summarize-conversation",
                json={
                    'segments': transcription_data['segments'],
                    'settings': {"aiModel": "gpt-4o"}
                }
            )
            summary_response.raise_for_status()
            summary_data = summary_response.json()
            
            print(f"Summary data: {summary_data}")
            print("events data: ", events_data['key_events'])
            # Update call_analytics table with the new schema
            analytics_data = {
                'call_id': call_id,
                'transcription': transcription_data['segments'],
                'transcript_highlights': events_data['key_events'],
                'sentiment_analysis': {
                    'segments': [
                        {'text': s['text'], 'sentiment': s.get('sentiment', 'neutral')} 
                        for s in transcription_data['segments']
                    ]
                },
                'ai_insights': {
                    'summary': summary_data['summary']
                },
                'summary': summary_data['summary']
            }
            
            self.supabase.table('call_analytics').insert(analytics_data).execute()
            
            # Mark as processed
            self.supabase.table('calls') \
                .update({'processed': True}) \
                .eq('id', call_id) \
                .execute()
                
            return {
                'success': True,
                'call_id': call_id
            }
            
        except Exception as e:
            print(f"Error processing call {call_id}: {str(e)}")
            return {
                'success': False,
                'call_id': call_id,
                'error': str(e)
            }
    
    async def process_all_calls(self):
        """Process all unprocessed calls"""
        calls = self.fetch_unprocessed_calls()
        results = []
        
        for call in calls:
            result = await self.process_call(call['id'], call['recording_url'])
            results.append(result)
                
        return results 