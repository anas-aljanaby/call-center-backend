from elevenlabs import ElevenLabs
from typing import List, Dict, Any
import os
from tempfile import NamedTemporaryFile

class ElevenLabsTranscriptionService:
    def __init__(self, api_key=None):
        """Initialize the ElevenLabs transcription service."""
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        self.client = ElevenLabs(api_key=self.api_key)
    
    def transcribe(self, file_path: str, language_code: str = 'en', num_speakers: int = 2) -> List[Dict[str, Any]]:
        """
        Transcribe an audio file using ElevenLabs and format the response.
        
        Args:
            file_path: Path to the audio file
            language_code: Language code (e.g., 'en', 'ara')
            num_speakers: Expected number of speakers
            
        Returns:
            List of segments in the format:
            [
                {
                    "startTime": float,
                    "endTime": float,
                    "text": str,
                    "speaker": str,
                },
                ...
            ]
        """
        try:
            with open(file_path, 'rb') as audio_file:
                response = self.client.speech_to_text.convert(
                    model_id='scribe_v1',
                    file=audio_file,
                    language_code=language_code,
                    num_speakers=num_speakers,
                    diarize=True,
                )
            
            # Process the response to create segments
            segments = self._process_response(response)
            
            return segments
            
        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")
    
    def transcribe_from_bytes(self, audio_bytes: bytes, language_code: str = 'en', num_speakers: int = 2) -> List[Dict[str, Any]]:
        """
        Transcribe audio from bytes using ElevenLabs and format the response.
        
        Args:
            audio_bytes: Audio file as bytes
            language_code: Language code (e.g., 'en', 'ara')
            num_speakers: Expected number of speakers
            
        Returns:
            List of segments in the format specified in transcribe method
        """
        with NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        try:
            result = self.transcribe(temp_file_path, language_code, num_speakers)
            return result
        finally:
            os.unlink(temp_file_path)
    
    def _process_response(self, response):
        """
        Process the ElevenLabs response to create segments in the desired format.
        
        Args:
            response: ElevenLabs API response
            
        Returns:
            List of segments in the desired format
        """
        # Filter out spacing segments
        words = [word for word in response.words if word.type != 'spacing']
        
        if not words:
            return []
        
        # Initialize the first segment
        segments = []
        current_segment = {
            "startTime": words[0].start,
            "endTime": words[0].end,
            "text": words[0].text,
            "speaker": words[0].speaker_id
        }
        
        # Process remaining words
        for word in words[1:]:
            # If the speaker is the same, extend the current segment
            if word.speaker_id == current_segment["speaker"]:
                current_segment["text"] += " " + word.text
                current_segment["endTime"] = word.end
            else:
                # Finalize the current segment and start a new one
                segments.append(current_segment)
                current_segment = {
                    "startTime": word.start,
                    "endTime": word.end,
                    "text": word.text,
                    "speaker": word.speaker_id
                }
        
        # Add the last segment
        segments.append(current_segment)
        
        # Clean up the segments
        for segment in segments:
            # Format speaker to match your expected format
            segment["speaker"] = segment["speaker"].replace("speaker_", "Speaker ")
            
            # Clean up text (remove extra spaces, etc.)
            segment["text"] = segment["text"].strip()
        
        return segments