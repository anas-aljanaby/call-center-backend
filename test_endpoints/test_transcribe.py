import requests
import json
import os
from pathlib import Path

def test_transcribe_endpoint():
    # Setup paths
    current_dir = Path(__file__).parent
    input_file = current_dir / "inputs" / "short_sample.mp3"
    # input_file = "/Users/anes/Downloads/12.wav"
    output_dir = current_dir / "outputs"
    output_file = output_dir / "transcription_result.json"

    # Create outputs directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure input file exists
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Prepare the file for upload
    files = {
        'file': ('sample_audio.wav', open(input_file, 'rb'), 'audio/wav')
    }

    try:
        # Make request to the endpoint
        response = requests.post(
            'http://localhost:8000/api/transcribe',
            files=files
        )
        
        # Check if request was successful
        response.raise_for_status()
        
        # Get the JSON response
        result = response.json()
        
        # Save the result to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"Transcription completed successfully. Results saved to: {output_file}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Close the file
        files['file'][1].close()

if __name__ == "__main__":
    test_transcribe_endpoint() 