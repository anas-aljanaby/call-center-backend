from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

def get_openai_client():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )