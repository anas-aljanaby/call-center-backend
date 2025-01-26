from services.agent_manager import AgentManager
from services.file_uploader import FileUploader
from services.call_processor import CallProcessor
import argparse
import asyncio
from pathlib import Path
import random

async def main():
    parser = argparse.ArgumentParser(description='Setup organization and process calls')
    parser.add_argument('org_id', help='Organization ID')
    parser.add_argument('calls_path', help='Path to call recording file or directory')
    args = parser.parse_args()
    
    path = Path(args.calls_path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return

    # Create or get existing agents
    agent_manager = AgentManager(args.org_id)
    existing_agents = agent_manager.get_existing_agents()
    
    agents = []
    if existing_agents:
        print(f"Found {len(existing_agents)} existing agents")
        agents = existing_agents
    
    # Create additional agents if needed
    for i in range(max(0, 3 - len(agents))):
        result = agent_manager.create_agent(
            f"agent{i+1}@example.com",
            f"Agent {i+1}"
        )
        if result['success']:
            print(f"Created new agent: {result['agent']['full_name']}")
            agents.append(result['agent'])
    
    if not agents:
        print("Error: No agents available")
        return
        
    # Upload calls
    if path.is_file():
        # Choose random agent for the file
        agent = random.choice(agents)
        uploader = FileUploader(args.org_id, agent['id'])
        result = uploader.upload_file(path)
        print(f"Upload for {agent['full_name']}: {'✓' if result['success'] else '✗'} {path.name}")
    else:
        # Upload directory contents, distributing among agents
        for file_path in path.glob('*.mp3'):
            agent = random.choice(agents)
            uploader = FileUploader(args.org_id, agent['id'])
            result = uploader.upload_file(file_path)
            print(f"Upload for {agent['full_name']}: {'✓' if result['success'] else '✗'} {file_path.name}")
    
    # Process all calls
    processor = CallProcessor(args.org_id)
    results = await processor.process_all_calls()
    print("\nProcessing Results:")
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"{status} Call {result['call_id']}")

if __name__ == "__main__":
    asyncio.run(main())