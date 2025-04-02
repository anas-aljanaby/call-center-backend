from pydantic import BaseModel
from typing import Optional


class ProcessingSettings(BaseModel):
    # AI Model Settings for different endpoints
    summaryModel: str = 'o3-mini'
    eventsModel: str = 'gpt-4o'
    labelsModel: str = 'o3-mini'
    detailsModel: str = 'o3-mini'
    checklistModel: str = 'o3-mini'
    
    # Transcription Settings
    transcriptionModel: str = 'real'
    languageId: str = 'ar-ir'
    sentimentDetect: bool = True

class TranscriptionRequest(BaseModel):
    settings: ProcessingSettings

class ConversationRequest(BaseModel):
    segments: list
    settings: ProcessingSettings 