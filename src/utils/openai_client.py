from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

def get_openai_client(model: str = None):
    """
    Get an OpenAI client configured based on the model requested.
    
    Args:
        model: Optional model identifier. If starts with 'deepseek/', uses OpenRouter.
              Otherwise uses direct OpenAI API.
    
    Returns:
        OpenAI: Configured OpenAI client
    """
    if model and model.startswith('deepseek/'):
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    else:
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
        )