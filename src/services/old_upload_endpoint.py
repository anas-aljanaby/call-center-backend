@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    metadata: str = Form(...)
):
    """Upload a document file to storage and process it"""
    try:
        # Parse metadata
        metadata_dict = json.loads(metadata)
        metadata_obj = DocumentMetadata(**metadata_dict)
        
        # Initialize services
        file_uploader = FileUploader(
            user_id=user_id,
            bucket_name='docs'
        )
        
        # Upload file and get URL
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            # Upload to storage
            result = file_uploader.upload_file(Path(temp_file.name))
            if not result['success']:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload file: {result.get('error', 'Unknown error')}"
                )
            
            # Update metadata with file URL
            metadata_obj.source_url = result['file_url']
            metadata_obj.file_size = len(content)
            metadata_obj.last_updated = datetime.now(pytz.UTC)
            
            # Process document
            processor = DocumentProcessor()
            chunks = await processor.process_document(temp_file.name, metadata_obj)
            
            # Get embeddings for chunks
            embeddings = []
            for chunk in chunks:
                response = processor.openai_client.embeddings.create(
                    input=chunk.content,
                    model="text-embedding-ada-002"
                )
                embeddings.append(response.data[0].embedding)
            
            # Store in vector database
            vector_store = VectorStore()
            await vector_store.store_document(chunks, embeddings, metadata_obj)
            
            return {
                "success": True,
                "message": "Document uploaded and processed successfully",
                "file_url": result['file_url']
            }
            
    except Exception as e:
        print(f"Error in upload_document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading document: {str(e)}"
        )
    finally:
        # Clean up temp file
        if 'temp_file' in locals():
            os.unlink(temp_file.name)
