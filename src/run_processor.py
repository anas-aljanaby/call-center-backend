import asyncio
import argparse
from services.call_processor import CallProcessor
import os
from pathlib import Path

async def main():
    parser = argparse.ArgumentParser(description='Process call center recordings')
    parser.add_argument('--skip-transcription', action='store_true', 
                      help='Skip transcription and use existing transcription data')
    parser.add_argument('--stats', action='store_true',
                      help='Collect and display detailed processing statistics')
    parser.add_argument('--limit', type=int, 
                      help='Limit the number of calls to process')
    parser.add_argument('--call-id', type=str,
                      help='Process a specific call by ID')
    args = parser.parse_args()
    
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    processor = CallProcessor(skip_transcription=args.skip_transcription, collect_stats=args.stats)
    
    if args.call_id:
        # Process a single call by ID
        processor.file_logger.info(f"Processing single call with ID: {args.call_id}")
        call_info = await processor.fetch_call_by_id(args.call_id)
        
        if not call_info:
            print(f"[red]Error: Call with ID {args.call_id} not found[/red]")
            return
            
        result = await processor.process_call(
            call_info['id'],
            call_info['recording_url'],
            call_info['organization_id']
        )
        
        # Display stats for the single call if requested
        if args.stats and result['success']:
            processor._display_single_call_stats(result)
    else:
        # Process multiple calls
        await processor.process_all_calls(limit=args.limit)

if __name__ == "__main__":
    asyncio.run(main()) 