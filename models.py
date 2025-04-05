from pydantic import BaseModel
from typing import Optional


class ProcessingSettings(BaseModel):
    # AI Model Settings for different endpoints
    summaryModel: str = 'gpt-4o'
    eventsModel: str = 'gpt-4o'
    labelsModel: str = 'gpt-4o'
    detailsModel: str = 'gpt-4o'
    checklistModel: str = 'gpt-4o'
    
    # Transcription Settings
    transcriptionModel: str = 'real'
    languageId: str = 'ar-ir'
    sentimentDetect: bool = True

class TranscriptionRequest(BaseModel):
    settings: ProcessingSettings

class ConversationRequest(BaseModel):
    segments: list
    settings: ProcessingSettings 