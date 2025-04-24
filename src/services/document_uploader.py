from pathlib import Path
from typing import Dict, List
from .base_file_uploader import BaseFileUploader

class DocumentUploader(BaseFileUploader):
    def __init__(self):
        super().__init__(bucket_name='documents')

    def upload_document(self, file_path: Path, original_filename: str = None) -> Dict:
        """Upload a document file to the documents bucket"""
        return self.upload_file(file_path, original_filename)

    def upload_directory(self, directory_path: str) -> List[Dict]:
        """Upload all files in a directory"""
        path = Path(directory_path)
        if not path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        results = []
        for file_path in path.glob('*.*'):
            try:
                result = self.upload_document(file_path)
                results.append(result)
            except Exception as e:
                print(f"Error uploading {file_path}: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'file_path': str(file_path)
                })
        
        return results 