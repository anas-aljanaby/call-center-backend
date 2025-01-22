# Call Center Backend

This is a FastAPI-based backend service for processing and analyzing call center audio files. It provides transcription, sentiment analysis, event detection, and conversation summarization capabilities.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/anas-aljanaby/call-center-backend.git
cd call-center-backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:
```
NEURALSPACE_API_KEY=your_neuralspace_api_key
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Running the Project

1. Start the server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. Upload audio file(s):
```bash
# Upload a single file
python src/upload_calls.py /path/to/audio/file.mp3 --agent-id "agent-uuid"

# Example:
python src/upload_calls.py short_sample.mp3 --agent-id "04669dbb-bd98-4fb7-869e-28abe559e803"
```
Note: The `agent-id` should correspond to a valid user ID from the profiles table.

3. Process the uploaded files:
```bash
python src/run_processor.py
```
This will process all uploaded files and populate the `call_analytics` table with:
- Summary
- Key moments
- Transcription