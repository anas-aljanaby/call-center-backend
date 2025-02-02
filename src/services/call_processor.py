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
        self.api_url = "http://localhost:8000"
        self.bucket_name = 'call-recordings'
        
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
            # Download using the public URL directly
            response = requests.get(recording_url)
            response.raise_for_status()
            files = {
                'file': ('audio.wav', response.content, 'audio/wav')
            }
            
            # Step 1: Transcribe
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
            transcription_data = transcription_response.json()
            
            # Step 2: Get events analysis
            events_response = requests.post(
                f"{self.api_url}/api/analyze-events",
                json={
                    'segments': transcription_data['segments'],
                    'settings': {"aiModel": "gpt-4o"}
                }
            )
            events_data = events_response.json()
            
            # Step 3: Get conversation summary
            summary_response = requests.post(
                f"{self.api_url}/api/summarize-conversation",
                json={
                    'segments': transcription_data['segments'],
                    'settings': {"aiModel": "gpt-4o"}
                }
            )
            summary_data = summary_response.json()
            
            # Step 4: Get additional analytics
            details_response = requests.post(
                f"{self.api_url}/api/analyze-call-details",
                json={
                    'segments': transcription_data['segments'],
                    'settings': {"aiModel": "gpt-4o"}
                }
            )
            details_data = details_response.json()
            
            # Update call_analytics table
            analytics_data = {
                'call_id': call_id,
                'sentiment_score': details_data['sentiment_score'],
                'transcription': transcription_data['segments'],
                'transcript_highlights': events_data['key_events'],
                'topics': details_data['topics'],
                'flags': details_data['flags'],
                'call_type': details_data['call_type'],
                'summary': summary_data['summary']
            }
            
            self.supabase.table('call_analytics').insert(analytics_data).execute()
            
            # Mark call as processed
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