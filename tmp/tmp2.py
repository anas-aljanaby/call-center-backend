from elevenlabs import ElevenLabs

client = ElevenLabs(api_key="")


res = client.speech_to_text.convert(
	model_id='scribe_v1',
	file=open('/Users/anes/Downloads/rg-601-07809992555-20241102-234828-1730580508.524.wav', 'rb'),
    language_code='ara',
	num_speakers=2,
	diarize=True,
)

print(res)
