import requests
import json
from pathlib import Path
import time

def test_all_endpoints():
    # Setup paths
    current_dir = Path(__file__).parent
    input_file = current_dir / "inputs" / "sample_audio.wav"
    output_dir = current_dir / "outputs"
    final_output_file = output_dir / "final_analysis.json"

    # Create outputs directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure input file exists
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    try:
        # Step 1: Transcribe audio
        print("\n1. Transcribing audio...")
        files = {
            'file': ('sample_audio.wav', open(input_file, 'rb'), 'audio/wav')
        }
        response = requests.post(
            'http://localhost:8000/api/transcribe',
            files=files
        )
        response.raise_for_status()
        transcription = response.json()
        print("✓ Transcription completed")

        # Step 2: Label segments
        print("\n2. Labeling segments...")
        label_payload = {
            "segments": transcription["segments"],
            "possible_labels": [
                {
                    "name": "greeting",
                    "description": "Agent or customer greeting each other"
                },
                {
                    "name": "problem_statement",
                    "description": "Customer explaining their issue or reason for calling"
                },
                {
                    "name": "verification",
                    "description": "Agent verifying customer information or transaction details"
                },
                {
                    "name": "solution",
                    "description": "Agent providing a solution or taking action to resolve the issue"
                },
                {
                    "name": "farewell",
                    "description": "Agent or customer saying goodbye"
                }
            ]
        }
        response = requests.post(
            'http://localhost:8000/api/label-segments',
            json=label_payload
        )
        response.raise_for_status()
        labeled_segments = response.json()
        print("✓ Segment labeling completed")

        # Step 3: Analyze checklist
        print("\n3. Analyzing checklist...")
        checklist_payload = {
            "segments": labeled_segments["segments"],
            "checklist": [
                "Greet the customer appropriately",
                "Verify customer identity",
                "Listen to and understand customer's issue",
                "Ask clarifying questions",
                "Provide clear solution or next steps",
                "Confirm customer's understanding",
                "Thank the customer",
                "Professional closing"
            ]
        }
        response = requests.post(
            'http://localhost:8000/api/analyze-checklist',
            json=checklist_payload
        )
        response.raise_for_status()
        checklist_analysis = response.json()
        print("✓ Checklist analysis completed")

        # Step 4: Analyze events
        print("\n4. Analyzing events...")
        events_payload = {
            "segments": checklist_analysis["segments"]
        }
        response = requests.post(
            'http://localhost:8000/api/analyze-events',
            json=events_payload
        )
        response.raise_for_status()
        events_analysis = response.json()
        print("✓ Events analysis completed")

        # Step 5: Generate summary
        print("\n5. Generating summary...")
        summary_payload = {
            "segments": events_analysis["segments"]
        }
        response = requests.post(
            'http://localhost:8000/api/summarize-conversation',
            json=summary_payload
        )
        response.raise_for_status()
        final_result = response.json()
        print("✓ Summary generation completed")

        # Combine all results into final output
        final_output = {
            "segments": final_result["segments"],
            "key_events": events_analysis["key_events"],
            "summary": final_result["summary"]
        }

        # Save the final result
        with open(final_output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
            
        print(f"\n✓ All analyses completed successfully. Final results saved to: {final_output_file}")
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Close the file if it was opened
        if 'files' in locals():
            files['file'][1].close()

if __name__ == "__main__":
    test_all_endpoints()