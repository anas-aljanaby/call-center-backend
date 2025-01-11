from pydantic import BaseModel
from typing import Optional

class ProcessingSettings(BaseModel):
    # AI Model Settings
    aiModel: str = 'gpt-3.5-turbo'
    
    # Transcription Settings
    transcriptionModel: str = 'real'
    languageId: str = 'ar-ir'
    sentimentDetect: bool = True

class TranscriptionRequest(BaseModel):
    settings: ProcessingSettings

class ConversationRequest(BaseModel):
    segments: list
    settings: ProcessingSettings 