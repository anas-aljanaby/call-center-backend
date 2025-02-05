from services.file_uploader import FileUploader
from services.agent_manager import AgentManager
import argparse
from pathlib import Path


audio_extensions = {'.mp3', '.wav', '.m4a', '.ogg'}

def main():
    parser = argparse.ArgumentParser(description='Upload audio files to Supabase')
    parser.add_argument('path', help='Path to file or directory to upload')
    parser.add_argument('--org-id', help='ID of the organization', required=True)
    parser.add_argument('--agent-id', help='ID of the agent (optional)')
    args = parser.parse_args()
    
    # Initialize agent manager to handle agent selection
    agent_manager = AgentManager(args.org_id)
    
    # If no agent specified, get a random one from the organization
    agent_id = args.agent_id
    if not agent_id:
        try:
            agent = agent_manager.get_random_agent()
            agent_id = agent['id']
            print(f"Selected agent: {agent['full_name']}")
        except ValueError as e:
            print(f"Error: {str(e)}")
            return

    # Initialize uploader with organization context
    uploader = FileUploader(organization_id=args.org_id, agent_id=agent_id)
    path = Path(args.path)
    
    if path.is_file():
        result = uploader.upload_file(path)
        status = "✓" if result['success'] else "✗"
        print(f"{status} {path.name}")
    elif path.is_dir():
        results = []
        for file_path in path.glob('*.*'):
            if file_path.suffix.lower() in audio_extensions:
                # For directories, optionally get a new random agent for each file
                if not args.agent_id:
                    agent = agent_manager.get_random_agent()
                uploader.agent_id = agent['id']
                print(f"Selected agent for {file_path.name}: {agent['full_name']}")
            
            result = uploader.upload_file(file_path)
            results.append(result)
            status = "✓" if result['success'] else "✗"
            print(f"{status} {file_path.name}")
        
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