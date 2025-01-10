from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from pathlib import Path
import neuralspace as ns
from tempfile import NamedTemporaryFile
import asyncio
import json
import librosa
import soundfile as sf
import noisereduce as nr
import numpy as np
from pydantic import BaseModel
from typing import List, Dict, Optional
import openai

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://call-center-dashboard-n8z4y8vb2-anas-ahmeds-projects-c957fb83.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = "gpt-3.5-turbo"

NEURALSPACE_API_KEY = os.getenv('NEURALSPACE_API_KEY')
if not NEURALSPACE_API_KEY:
    raise ValueError("NEURALSPACE_API_KEY environment variable is not set")

vai = ns.VoiceAI(api_key=NEURALSPACE_API_KEY)

async def enhance_audio_file(input_path, output_path):
    """
    Enhance the audio quality of the input file
    """
    audio, sr = librosa.load(input_path, sr=None)
    
    noise_sample = audio[0:int(sr)]
    reduced_noise = nr.reduce_noise(
        y=audio,
        sr=sr,
        prop_decrease=0.75,
        n_std_thresh_stationary=1.5
    )
    
    speech_enhanced = librosa.effects.preemphasis(reduced_noise, coef=0.97)
    speech_enhanced = librosa.util.normalize(speech_enhanced)
    sf.write(output_path, speech_enhanced, sr)

@app.post("/api/transcribe-dummy")
async def transcribe_audio_dummy(file: UploadFile):
    """
    Dummy endpoint that returns mock transcription data from dummy.json for testing,
    formatted to match the structure of the /api/transcribe endpoint
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dummy_file_path = os.path.join(current_dir, "dummy.json")

    with open(dummy_file_path, 'r') as f:
        dummy_data = json.load(f)

    # Wrap the dummy data in the same format as the transcribe endpoint
    return {
        "segments": dummy_data
    }

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile, enhance_audio: bool = False):
    """
    Endpoint to transcribe audio files and return both full transcription and word timestamps
    """
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Supported formats: {', '.join(allowed_extensions)}"
        )

    try:
        with NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            
            input_file = temp_file.name
            
            if enhance_audio:
                enhanced_file = NamedTemporaryFile(delete=False, suffix='.wav')
                await enhance_audio_file(temp_file.name, enhanced_file.name)
                input_file = enhanced_file.name

            config = {
                'file_transcription': {
                    'language_id': 'ar-ir',
                    'mode': 'advanced',
                },
                "speaker_diarization": {
                    "mode": "speakers",
                    "num_speakers" : 2,
                },
                "sentiment_detect": True
            }
            job_id = vai.transcribe(file=input_file, config=config)
            result = vai.poll_until_complete(job_id)

            os.unlink(temp_file.name)
            if enhance_audio:
                os.unlink(enhanced_file.name)

            if result.get('success'):
                return {
                    "segments": result['data']['result']['transcription']['segments']
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Transcription failed"
                )

    except Exception as e:
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file.name)
            except:
                pass
        if enhance_audio and 'enhanced_file' in locals():
            try:
                os.unlink(enhanced_file.name)
            except:
                pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio file: {str(e)}"
        )

@app.get("/api/transcription/{job_id}")
async def get_transcription_status(job_id: str):
    """
    Endpoint to check the status of a transcription job
    """
    try:
        result = vai.get_job_status(job_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching job status: {str(e)}"
        )

class LabelDefinition(BaseModel):
    name: str
    description: str

class Segment(BaseModel):
    startTime: float
    endTime: float
    text: str
    speaker: str
    channel: int
    label: Optional[str] = None

class LabelingRequest(BaseModel):
    segments: List[Segment]
    possible_labels: List[LabelDefinition]

@app.post("/api/label-segments")
async def label_segments(request: LabelingRequest):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    label_descriptions = "\n".join([
        f"- {label.name}: {label.description}"
        for label in request.possible_labels
    ])

    segments = request.segments
    for i, segment in enumerate(segments):
        prompt = f"""
You are an AI assistant tasked with labeling a segment of a customer service conversation.
The possible labels and their descriptions are:

{label_descriptions}

Here's the segment:
[{segment.speaker}]: {segment.text}

Determine if this segment should have any of the defined labels. If the segment doesn't match any label criteria, respond with null.
Be very conservative in your labeling. Don't assign any label unless it's very clear that this segment matches the label criteria.
Provide the response as a single JSON object with format: {{"label": "label_name"}} or {{"label": null}}
Only respond with the JSON object, no additional text.
"""
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a conversation analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )

            label_json = response.choices[0].message.content
            label_json = label_json.strip('`').replace('```json\n', '').replace('\n```', '').replace("json", "")
            label_data = json.loads(label_json)
            
            segment_dict = segment.dict()
            segment_dict["label"] = label_data["label"]
            segments[i] = Segment(**segment_dict)

        except json.JSONDecodeError as e:
            print(f"Error parsing OpenAI response for segment {i}: {str(e)}")
            segments[i].label = None
        except Exception as e:
            print(f"Error processing segment {i}: {str(e)}")
            segments[i].label = None

    return {
        "segments": [segment.dict() for segment in segments]
    }

class TranscriptSegment(BaseModel):
    startTime: float
    endTime: float
    text: str
    speaker: Optional[str] = None
    channel: Optional[int] = None
    sentiment: str = "neutral"  # Optional with default value

class ChecklistRequest(BaseModel):
    segments: List[TranscriptSegment]
    checklist: List[str]

@app.post("/api/analyze-checklist")
async def analyze_checklist(request: ChecklistRequest):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Prepare the segments text with numbers
    numbered_segments = "\n".join([
        f"{i+1}. {segment.text}"
        for i, segment in enumerate(request.segments)
    ])
    
    # Prepare the checklist items
    checklist_items = "\n".join([
        f"- {item}" for item in request.checklist
    ])
    
    prompt = f"""
    Given these conversation segments:
    {numbered_segments}
    
    And this checklist:
    {checklist_items}
    
    For each segment number, determine if it fulfills any of the checklist items.
    Only match segments that clearly fulfill the checklist item.
    Respond in JSON format like this:
    {{
        "matches": [
            {{"segment": 1, "checklist_item": "Greet Customer"}},
            {{"segment": 3, "checklist_item": "Gather Relevant Information"}}
        ]
    }}
    Only include segments that match a checklist item.
    Respond with only the JSON object, no additional text or formatting.
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a conversation analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Clean and parse the response
        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"Failed to parse response: {response_text}")
            result = {"matches": []}
        
        # Preserve existing segment data while adding checklist items
        segments = request.segments
        segment_matches = {match["segment"]: match["checklist_item"] 
                         for match in result.get("matches", [])}
        
        for i, segment in enumerate(segments):
            segment_dict = segment.dict()
            segment_dict["checklist_item"] = segment_matches.get(i + 1)
            segments[i] = TranscriptSegment(**segment_dict)
        
        return {
            "segments": [segment.dict() for segment in segments]
        }
        
    except Exception as e:
        print(f"Error in analyze_checklist: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing segments: {str(e)}"
        )

class ConversationSegment(BaseModel):
    startTime: float
    endTime: float
    text: str
    speaker: str
    channel: int

class ConversationRequest(BaseModel):
    segments: List[ConversationSegment]

@app.post("/api/analyze-events")
async def analyze_events(request: ConversationRequest):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Prepare the conversation flow
    conversation = "\n".join([
        f"[{segment.speaker}]: {segment.text}"
        for segment in request.segments
    ])
    
    prompt = """
    Analyze this customer service conversation and identify key events that occurred.
    Focus on important actions, requests, or decisions made during the conversation.
    
    For each event:
    1. Clearly indicate who took the action (Agent or Customer)
    2. Describe the specific event or action
    3. Include any relevant details or outcomes
    
    Format your response as a JSON array of events like this:
    {
        "events": [
            "Customer explained they were charged incorrectly and requested a refund",
            "Agent verified the transaction details in the system",
            "Agent approved a refund of 50 AED"
        ]
    }
    
    Do not include any other text or formatting in your response. Do not include the speaker name in the event description. 
    Just provide the event description as in the example.
    Conversation:
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a conversation analysis assistant specialized in Arabic customer service interactions."},
                {"role": "user", "content": prompt + conversation}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Clean and parse the response
        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(response_text)
            key_events = result.get("events", [])
        except json.JSONDecodeError:
            print(f"Failed to parse response: {response_text}")
            key_events = []
        
        return {
            "segments": [segment.dict() for segment in request.segments],
            "key_events": key_events
        }
        
    except Exception as e:
        print(f"Error in analyze_events: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing conversation events: {str(e)}"
        )

class SummaryRequest(BaseModel):
    segments: List[TranscriptSegment]

@app.post("/api/summarize-conversation")
async def summarize_conversation(request: SummaryRequest):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Prepare the conversation flow
    conversation = "\n".join([
        f"[{segment.speaker}]: {segment.text}"
        for segment in request.segments
    ])
    
    prompt = """
    Please provide a concise, single-paragraph summary of this customer service conversation in Arabic.
    Include the main purpose of the call, key points discussed, and any resolutions reached.
    Respond with a JSON object containing only a "summary" field with the paragraph.

    Conversation:
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a conversation analysis assistant specialized in Arabic customer service interactions."},
                {"role": "user", "content": prompt + conversation}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Clean and parse the response
        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(response_text)
            summary = result.get("summary", "")
        except json.JSONDecodeError:
            print(f"Failed to parse response: {response_text}")
            summary = ""
        
        return {
            "segments": [segment.dict() for segment in request.segments],
            "summary": summary
        }
        
    except Exception as e:
        print(f"Error in summarize_conversation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error summarizing conversation: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
