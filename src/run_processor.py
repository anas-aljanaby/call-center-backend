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
    args = parser.parse_args()
    
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    processor = CallProcessor(skip_transcription=args.skip_transcription, collect_stats=args.stats)
    results = await processor.process_all_calls(limit=args.limit)
    
if __name__ == "__main__":
    asyncio.run(main()) 