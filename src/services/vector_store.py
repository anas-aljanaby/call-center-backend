from supabase import create_client
import os
from typing import List, Dict
from src.models.document_models import DocumentChunk, DocumentMetadata
import openai

class VectorStore:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    async def store_document(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
        metadata: DocumentMetadata
    ):
        # Get UTC timestamp string
        last_updated = metadata.get_utc_timestamp()
        
        # First store document metadata
        doc_response = self.supabase.table('documents').insert({
            'title': metadata.title,
            'file_type': metadata.file_type,
            'total_pages': metadata.total_pages,
            'file_size': metadata.file_size,
            'source_url': metadata.source_url,
            'category': metadata.category,
            'summary': metadata.summary,
            'tags': metadata.tags,
            'helpful_rating': metadata.helpful_rating,
            'use_count': metadata.use_count,
            'last_updated': last_updated,
            'ai_suggestion': metadata.ai_suggestion
        }).execute()
        
        document_id = doc_response.data[0]['id']

        # Store chunks with embeddings
        chunks_data = []
        for chunk, embedding in zip(chunks, embeddings):
            chunks_data.append({
                'document_id': document_id,
                'content': chunk.content,
                'embedding': embedding,
                'page_number': chunk.page_number,
                'chunk_number': chunk.chunk_number
            })
        
        self.supabase.table('document_chunks').insert(chunks_data).execute()

    async def search_similar_chunks(
        self,
        query: str,
        match_threshold: float = 0.1,
        match_count: int = 3
    ) -> List[Dict]:
        try:
            # Create embedding for the query
            response = self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-ada-002"  # Match the model used in storage
            )
            query_embedding = response.data[0].embedding

            # Debug print
            print(f"Generated query embedding of length: {len(query_embedding)}")

            # Search for similar chunks using the match_chunks function
            result = self.supabase.rpc(
                'match_chunks',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': match_threshold,
                    'match_count': match_count
                }
            ).execute()

            # Debug print
            print(f"RPC result: {result.data}")

            # Join with documents table to get source information
            chunks = result.data
            if chunks:
                # Get document information for the chunks
                doc_ids = list(set(chunk['document_id'] for chunk in chunks))
                docs = self.supabase.table('documents').select('*').in_('id', doc_ids).execute()
                doc_map = {doc['id']: doc for doc in docs.data}
                
                # Add source information to chunks
                for chunk in chunks:
                    doc = doc_map.get(chunk['document_id'])
                    if doc:
                        chunk['source'] = doc['title']
                        chunk['similarity'] = chunk.get('similarity', 0.0)
                        print(f"Found chunk from document: {doc['title']}")  # Debug print
                
                print(f"Found {len(chunks)} relevant chunks")
                return chunks

            print("No matching chunks found")
            return []
            
        except Exception as e:
            print(f"Error in search_similar_chunks: {str(e)}")
            return [] 