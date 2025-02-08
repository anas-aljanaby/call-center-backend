import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
response = openai.chat.completions.create(
    model="o3-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Can you explain the concept of quantum entanglement?"}
    ]
)

print(response.choices[0].message["content"])
