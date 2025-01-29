from typing import List, Optional
import fitz  # PyMuPDF
from pathlib import Path
import tiktoken
import openai
from src.models.document_models import DocumentChunk
import os

class DocumentProcessor:
    def __init__(self):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = 500
        self.chunk_overlap = 50
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def extract_text_from_pdf(self, file_path: str) -> List[tuple[str, int]]:
        doc = fitz.open(file_path)
        text_pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text_pages.append((page.get_text(), page_num + 1))
        return text_pages

    def create_chunks(self, text: str, source: str, page_number: Optional[int] = None) -> List[DocumentChunk]:
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), self.chunk_size - self.chunk_overlap):
            chunk_tokens = tokens[i:i + self.chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(
                DocumentChunk(
                    content=chunk_text,
                    source=source,
                    page_number=page_number,
                    chunk_number=len(chunks) + 1
                )
            )
        return chunks

    async def create_embeddings(self, chunks: List[DocumentChunk]) -> List[List[float]]:
        embeddings = []
        for chunk in chunks:
            response = self.openai_client.embeddings.create(
                input=chunk.content,
                model="text-embedding-3-small"
            )
            embeddings.append(response.data[0].embedding)
        return embeddings 