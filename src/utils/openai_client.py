from openai import OpenAI

def get_openai_client():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="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",
    )