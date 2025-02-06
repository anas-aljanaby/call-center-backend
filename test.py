from openai import OpenAI

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key="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",
)

# turn on streaming
completion = client.chat.completions.create(
  model="deepseek/deepseek-r1:free",
  messages=[
    {
      "role": "user",
      "content": "What is the meaning of life?, in one sentence."
    }
  ],
)
print(completion)
print("--------------------------------")
print(completion.choices[0].message.content)