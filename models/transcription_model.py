import neuralspace as ns
from typing import Dict, Any
import os
from tempfile import NamedTemporaryFile

class TranscriptionModel:
    def __init__(self):
        self.api_key = os.getenv('NEURALSPACE_API_KEY', 'your_api_key_here')
        self.vai = ns.VoiceAI(api_key=self.api_key)
        
    def transcribe(self, file_content: bytes) -> Dict[str, Any]:
        with NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            config = {
                'file_transcription': {
                    'language_id': 'en',
                    'mode': 'advanced',
                }
            }
            
            job_id = self.vai.transcribe(file=temp_file_path, config=config)
            result = self.vai.poll_until_complete(job_id)
            
            if result.get('success'):
                transcription_data = result['data']['result']['transcription']['channels']['0']
                return {
                    'full_text': transcription_data['transcript'],
                    'timestamps': transcription_data['timestamps']
                }
            else:
                raise Exception("Transcription failed")
                
        finally:
            os.unlink(temp_file_path) 