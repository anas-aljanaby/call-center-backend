from services.file_uploader import FileUploader
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Upload audio files to Supabase')
    parser.add_argument('path', help='Path to file or directory to upload')
    parser.add_argument('--agent-id', help='ID of the agent (from profiles table)', required=True)
    args = parser.parse_args()
    
    uploader = FileUploader(agent_id=args.agent_id)
    path = Path(args.path)
    
    if path.is_file():
        result = uploader.upload_file(path)
        status = "✓" if result['success'] else "✗"
        print(f"{status} {path.name}")
    elif path.is_dir():
        results = uploader.upload_directory(str(path))
        
        # Print summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        print(f"\nUpload Summary:")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
    else:
        print(f"Error: Path does not exist: {path}")

if __name__ == "__main__":
    main() 