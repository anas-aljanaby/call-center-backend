import requests
import json
from pathlib import Path

def test_label_segments():
    # Setup paths
    current_dir = Path(__file__).parent
    input_file = current_dir / "outputs" / "transcription_result.json"
    output_dir = current_dir / "outputs"
    output_file = output_dir / "labeled_segments.json"

    # Create outputs directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure input file exists
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Read the transcription file
    with open(input_file, 'r', encoding='utf-8') as f:
        transcription_data = json.load(f)

    # Prepare the request payload
    payload = {
        "segments": transcription_data["segments"],
        # "possible_labels": [
        #     {
        #         "name": "greeting",
        #         "description": "Agent or customer greeting each other"
        #     },
        #     {
        #         "name": "problem_statement",
        #         "description": "Customer explaining their issue or reason for calling"
        #     },
        #     {
        #         "name": "verification",
        #         "description": "Agent verifying customer information or transaction details"
        #     },
        #     {
        #         "name": "solution",
        #         "description": "Agent providing a solution or taking action to resolve the issue"
        #     },
        #     {
        #         "name": "farewell",
        #         "description": "Agent or customer saying goodbye"
        #     }
         "possible_labels": [
            {
                "name": "greeting",
                "description": "Agent or customer greeting each other"
            },
            {
                "name": "Info Request",
                "description": "Customer asking for information or clarification"
            },
            {
                "name": "Verification",
                "description": "Agent verifying customer information or transaction details"
            },
            {
                "name": "Solution",
                "description": "Agent providing a solution or taking action to resolve the issue"
            },
            {
                "name": "Farewell",
                "description": "Agent or customer saying goodbye"
            }
        ]       # ]
    }

    try:
        # Make request to the endpoint
        response = requests.post(
            'http://localhost:8000/api/label-segments',
            json=payload
        )
        
        # Check if request was successful
        response.raise_for_status()
        
        # Get the JSON response
        result = response.json()
        
        # Save the result to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"Segment labeling completed successfully. Results saved to: {output_file}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_label_segments() 