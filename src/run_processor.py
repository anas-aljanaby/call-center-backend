import asyncio
import argparse
from services.call_processor import CallProcessor

async def main():
    parser = argparse.ArgumentParser(description='Process call center recordings')
    parser.add_argument('--skip-transcription', action='store_true', 
                      help='Skip transcription and use existing transcription data')
    args = parser.parse_args()
    
    processor = CallProcessor(skip_transcription=args.skip_transcription)
    results = await processor.process_all_calls()
    
    # Print results
    print("\nProcessing Results:")
    for result in results:
        status = "✓ Success" if result['success'] else "✗ Failed"
        print(f"Call {result['call_id']}: {status}")

if __name__ == "__main__":
    asyncio.run(main()) 