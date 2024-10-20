from typing import Union
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
import requests
from typing import Dict, Any
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import base64
import json
import azure.cognitiveservices.speech as speechsdk
import config

import os
import io

from setup import prepared_text_llama_response

sys_prompt = '''You're Chatterbot, a friendly AI English tutor for Indian learners. Use simple words, short responses (max 15 words per question), and a light Indian accent. Start with basic questions about favorite colors, foods, and hometown. If the student converses well, ask about family and friends.

Key points:
1. Use relatable Indian examples and gentle humor
2. Subtly correct mistakes in verb tenses, pronouns, articles, and word order
3. Be patient and encouraging
4. Keep conversations natural while providing quick English tips
5. Adapt your style to the user's responses and English level

If unsure, admit it.

Example:
Bot: "Namaste! What's your plan for today?"
User: "I go to market for vegetables."
Bot: "Nice! Shopping for veggies? Quick tip: Try 'I'm going to the market.' Which sabzi is your favorite?'''

global messages
messages = [{"role": "system", "content": sys_prompt}]

app = FastAPI()

# Add CORS middleware to allow smartphone requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (you can restrict to specific origins)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")



# Azure Speech configurations
speech_config = speechsdk.SpeechConfig(subscription=config.AZURE_SPEECH_KEY, region=config.AZURE_SPEECH_REGION)
speech_config.speech_recognition_language = "en-US"
speech_config.speech_synthesis_voice_name = "en-IN-NeerjaNeural"

class Query(BaseModel):
    prompt: str = "who are you?"
#     prompt: str = """You're Chatterbot, a friendly AI Spoken English tutor for Indian learners. Use simple words, short responses (max 15 words per question), and a light Indian accent. Start with basic questions about favorite colors, foods, and hometown.

# Key points:
# 1. Use relatable Indian examples and gentle humor
# 2. Subtly correct mistakes in verb tenses, pronouns, articles, and word order
# 3. Be patient and encouraging
# 4. Keep conversations natural while providing quick English tips
# 5. Adapt your style to the user's responses and English level
# 6. Ignore spelling mistakes and case mistakes

# If unsure, admit it.

# Example:
# Bot: "Hi! What's your plan for today?"
# User: "I go to market for vegetables."
# Bot: "Nice! Shopping for veggies? Quick tip: Try 'I'm going to the market.' Which sabzi is your favorite?"""
    model: str = "hf.co/Sravana/llama_chatterbot_2:Q5_K_M"  

@app.get("/cool")
def read_root():
    return {"Hello": "World"}

# Serve the main HTML file
@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

@app.post("/generate")
async def generate_text1(query: Query):
    try:
        global messages
        # print(len(messages))
        # retain always pre 3 chat conv
        if len(messages) > 6:
            messages = [messages[0]] + messages[-3:]
        message = query.prompt
        messages.append({
            "role": "user",
            "content": message
        })

        raw_prompt = prepared_text_llama_response(messages)

        
        messages.append({
            "role": "assistant",
            "content": "Hello World"
        })
        return {"generated_text": message}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Ollama: {str(e)}")


@app.post("/generate1")
async def generate_text(query: Query):
    try:
        global messages
        # print(len(messages))
        # retain always pre 3 chat conv
        if len(messages) > 5:
            messages = [messages[0]] + messages[-3:]
        message = query.prompt
        messages.append({
            "role": "user",
            "content": message
        })

        raw_prompt = prepared_text_llama_response(messages)

        api_endpoint = "http://127.0.0.1:11434/api/generate"
        response = requests.post(

            # "http://localhost:11434/api/generate",
            api_endpoint,
            # json={"model": query.model, "prompt": query.prompt, "stream": False}
            json={"model": query.model, "prompt": raw_prompt, "stream": False, "raw": True}
        )
        response.raise_for_status()
        messages.append({
            "role": "assistant",
            "content": response.json()["response"]
        })
        return {"generated_text": response.json()["response"]}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Ollama: {str(e)}")


# =========================== NEW EXP ======================= #
from time import sleep

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            pass
            data = await websocket.receive_text()
            
            audio_data = base64.b64decode(data)

            text = await speech_to_text(audio_data)
            print("tex:.....", text)
            
            # Send interim audio immediately
            # interim_audio = await get_random_interim_audio()
            # await websocket.send_text(json.dumps({
            #     "type": "interim",
            #     "audio": base64.b64encode(interim_audio).decode('utf-8')
            # }))
            
            # response_text = await process_text(text)
        
            response_text = await generate_text(Query(prompt=text))
            response_text = response_text['generated_text']
            
            audio_response = await text_to_speech(response_text)
            await websocket.send_text(json.dumps({
                "text": response_text,
                "audio": base64.b64encode(audio_response).decode('utf-8')
            }))

        except Exception as e:
            print(f"Error: {str(e)}")
            error_message = "Sorry, there was an error processing your request."
            error_audio = await text_to_speech(error_message)
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": error_message,
                "audio": base64.b64encode(error_audio).decode('utf-8')
            }))


async def process_text(text):
    # Here you would send the text to your LLM and get a response
    # This is a placeholder implementation
    return f"I heard: {text}. How can I help you improve your English?"


# List of short audio files for interim responses
INTERIM_AUDIO_FILES = [
    "alright.mp3",
    "gotitthinking.mp3",
    "interestingquestion.mp3",
    "justasecond.mp3",
    "letmethink.mp3"
]
import random
async def get_random_interim_audio():
    """Get a random interim audio file content."""
    filename = random.choice(INTERIM_AUDIO_FILES)
    with open(filename, "rb") as f:
        return f.read()

from deepgram import Deepgram
dg_client = Deepgram(config.DEEPGRAM_API_KEY)
async def speech_to_text(audio_data):
    try:
        source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
        options = {
            'punctuate': True,
            'model': 'nova-2-general',# 'general',
            'language': 'en-IN'
        }

        response = await dg_client.transcription.prerecorded(source, options)
        
        # Extract the transcript from the response
        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
        
        return transcript

    except Exception as e:
        print(f"Error in speech_to_text: {e}")
        return "Error occurred during transcription"

async def text_to_speech(text):
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = speech_synthesizer.speak_text_async(text).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # def save_raw_audio(audio_data, filename):
        #     with open(filename, 'wb') as file:
        #         file.write(audio_data)
        # # Usage
        # save_raw_audio(result.audio_data, 'interestingquestion.mp3')

        return result.audio_data
    elif result.reason == speechsdk.ResultReason.Canceled:
        return b""  # Return empty bytes if synthesis was canceled

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0", port=8000 
    uvicorn.run(app, port=8000)


