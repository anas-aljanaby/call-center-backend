from typing import List, Dict
import openai
import os
from src.services.vector_store import VectorStore

class RAGService:
    def __init__(self):
        self.vector_store = VectorStore()
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
    async def get_answer(self, question: str, max_chunks: int = 5) -> Dict:
        # Get relevant chunks
        chunks = await self.vector_store.search_similar_chunks(
            query=question,
            match_count=max_chunks
        )
        
        # Format context from chunks
        context = "\n\n".join([
            f"Source: {chunk['source']}, Page: {chunk['page_number']}\n{chunk['content']}"
            for chunk in chunks
        ])
        
        print(context)
        # Generate answer using context
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the user's question. If you cannot find the answer in the context, say so."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ]
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        
        return {
            "answer": response.choices[0].message.content,
            "sources": [
                {
                    "content": chunk['content'],
                    "source": chunk['source'],
                    "page": chunk['page_number'],
                    "similarity": chunk['similarity']
                }
                for chunk in chunks
            ]
        } 