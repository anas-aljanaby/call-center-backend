from pydantic import BaseModel
from typing import List, Optional

class DocumentChunk(BaseModel):
    content: str
    source: str
    page_number: Optional[int]
    chunk_number: int

class DocumentMetadata(BaseModel):
    title: str
    file_type: str
    total_pages: Optional[int]
    file_size: int
    source_url: str
    category: str 