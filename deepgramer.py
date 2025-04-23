from deepgram import Deepgram
import asyncio
import os

# Set your API key here
DEEPGRAM_API_KEY = "9f32058791d9c4f2456893d7c612ddabffad8dea"

# Async function to handle transcription
async def transcribe():
    dg_client = Deepgram(DEEPGRAM_API_KEY)

    with open("porcupine_testing.wav", "rb") as audio:
        source = {
            "buffer": audio,
            "mimetype": "audio/wav"
        }

        response = await dg_client.transcription.prerecorded(
            source,
            {"punctuate": True, "language": "en"}
        )

        print(response["results"]["channels"][0]["alternatives"][0]["transcript"])

# Run the async function
asyncio.run(transcribe())