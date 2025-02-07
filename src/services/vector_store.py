from supabase import create_client
import os
from typing import List, Dict
from src.models.document_models import DocumentChunk, DocumentMetadata
from openai import OpenAI
import numpy as np

class VectorStore:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.openai_client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
        )

    async def store_document(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
        metadata: DocumentMetadata
    ):
        try:
            # Get UTC timestamp string
            updated_at = metadata.get_utc_timestamp()
            
            # Store document metadata
            doc_data = {
                'title': metadata.title,
                'file_type': metadata.file_type,
                'total_pages': metadata.total_pages or 0,
                'file_size': metadata.file_size,
                'source_url': metadata.source_url,
                'category': metadata.category,
                'summary': metadata.summary,
                'tags': metadata.tags,
                'helpful_rating': metadata.helpful_rating or 0,
                'use_count': metadata.use_count or 0,
                'updated_at': updated_at,
                'ai_suggestion': metadata.ai_suggestion
            }
            
            doc_response = self.supabase.table('documents').insert(doc_data).execute()
            document_id = doc_response.data[0]['id']

            # Store chunks with embeddings
            chunks_data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                embedding_array = np.array(embedding, dtype=np.float32)
                chunks_data.append({
                    'document_id': document_id,
                    'content': chunk.content,
                    'embedding': embedding_array.tolist(),
                    'page_number': chunk.page_number or 1,
                    'chunk_number': i + 1
                })
            
            # Insert chunks in batches
            batch_size = 5
            for i in range(0, len(chunks_data), batch_size):
                batch = chunks_data[i:i + batch_size]
                self.supabase.table('document_chunks').insert(batch).execute()
            
            return document_id
            
        except Exception as e:
            raise

    async def search_similar_chunks(
        self,
        query: str,
        match_threshold: float = 0.1,
        match_count: int = 3
    ) -> List[Dict]:
        try:
            response = self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding

            result = self.supabase.rpc(
                'match_document_chunks',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': match_threshold,
                    'match_count': match_count
                }
            ).execute()

            chunks = result.data
            if chunks:
                doc_ids = list(set(chunk['document_id'] for chunk in chunks))
                docs = self.supabase.table('documents').select('*').in_('id', doc_ids).execute()
                doc_map = {doc['id']: doc for doc in docs.data}
                
                for chunk in chunks:
                    doc = doc_map.get(chunk['document_id'])
                    if doc:
                        chunk['source'] = doc['title']
                        chunk['similarity'] = chunk.get('similarity', 0.0)
                
                return chunks
            
            return []
            
        except Exception as e:
            raise