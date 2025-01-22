import asyncio
from services.call_processor import CallProcessor

async def main():
    processor = CallProcessor()
    results = await processor.process_all_calls()
    
    # Print results
    print("\nProcessing Results:")
    for result in results:
        status = "✓ Success" if result['success'] else "✗ Failed"
        print(f"Call {result['call_id']}: {status}")

if __name__ == "__main__":
    asyncio.run(main()) 