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
    last_updated: Optional[datetime] = None

    def get_utc_timestamp(self) -> Optional[str]:
        """Convert last_updated to UTC timezone string"""
        if self.last_updated:
            if self.last_updated.tzinfo is None:
                # If no timezone set, assume UTC
                utc_dt = pytz.UTC.localize(self.last_updated)
            else:
                # Convert to UTC if it has a different timezone
                utc_dt = self.last_updated.astimezone(pytz.UTC)
            return utc_dt.isoformat()
        return None 