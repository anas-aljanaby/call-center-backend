from pydantic import BaseModel
from typing import Optional

class ProcessingSettings(BaseModel):
    # AI Model Settings
    aiModel: str = 'deepseek/deepseek-r1:free'
    
    # Transcription Settings
    transcriptionModel: str = 'real'
    languageId: str = 'ar-ir'
    sentimentDetect: bool = True

class TranscriptionRequest(BaseModel):
    settings: ProcessingSettings

class ConversationRequest(BaseModel):
    segments: list
    settings: ProcessingSettings 