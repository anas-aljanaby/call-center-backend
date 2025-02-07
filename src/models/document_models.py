from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pytz

class DocumentChunk(BaseModel):
    content: str
    source: str
    page_number: Optional[int]
    chunk_number: int

class DocumentMetadata(BaseModel):
    title: str
    file_type: str
    total_pages: Optional[int] = None
    file_size: int
    source_url: Optional[str] = None
    category: str
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    helpful_rating: Optional[int] = None
    use_count: Optional[int] = 0
    ai_suggestion: Optional[str] = None
    updated_at: Optional[datetime] = None

    def get_utc_timestamp(self) -> Optional[str]:
        """Convert updated_at to UTC timezone string"""
        if self.updated_at:
            if self.updated_at.tzinfo is None:
                # If no timezone set, assume UTC
                utc_dt = pytz.UTC.localize(self.updated_at)
            else:
                # Convert to UTC if it has a different timezone
                utc_dt = self.updated_at.astimezone(pytz.UTC)
            return utc_dt.isoformat()
        return None 