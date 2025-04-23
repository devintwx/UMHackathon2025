from flask import Flask, render_template, jsonify
import pvporcupine
import pyaudio
import struct
import wave
import pvcobra
from openai import OpenAI
import threading
from collections import deque
import time
import pyttsx3


app = Flask(__name__)

# Configuration
ACCESS_KEY = "qX3DhITQvxftyPTIxLxpiTXFD9yRzJ64d0bAJsTUlUxxeMWV8mnrFg=="
KEYWORD_PATH = "hey_grab_ppn.ppn"
AUDIO_FILENAME = "porcupine_testing.wav"
OPENAI_KEY = "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"

# Global variables
is_listening = True
audio_stream = None
pa = None
porcupine = None
cobra = None
client = None
transcript = ""
keyword_detected = False
transcript_history = deque(maxlen=50)
is_recording = False
has_new_transcript = False  # Add this new flag

def initialize_audio():
    global client, cobra, porcupine, pa
    try:
        client = OpenAI(api_key=OPENAI_KEY)
        cobra = pvcobra.create(access_key=ACCESS_KEY)
        porcupine = pvporcupine.create(
            access_key=ACCESS_KEY,
            keyword_paths=[KEYWORD_PATH]
        )
        pa = pyaudio.PyAudio()
        start_listening_thread()
        return True
    except Exception as e:
        print(f"Initialization error: {str(e)}")
        return False
    
def text_to_speech(text):
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"TTS error: {str(e)}")       

def start_listening_thread():
    global is_listening, audio_stream
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
    threading.Thread(target=listen_loop, daemon=True).start()

# Modify the transcribe_audio function
def transcribe_audio():
    global transcript, transcript_history, is_recording, has_new_transcript
    try:
        with open(AUDIO_FILENAME, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                prompt="This audio should be transcribed in English only. If other languages are detected, ignore them and transcribe only the English portions."
            )
            transcript = result.text
            transcript_history.append(transcript)
            has_new_transcript = True
            is_recording = False
            
            # Check if transcript contains "say hi"
            if "say hi" in transcript.lower():
                text_to_speech("Hello all the judges, good evening")
            
            return True
    except Exception as e:
        transcript = f"Error: {str(e)}"
        transcript_history.append(transcript)
        is_recording = False
        return False
    
def listen_loop():
    global is_listening, keyword_detected, is_recording
    
    while is_listening:
        try:
            pcm_b = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm_b)
            
            result = porcupine.process(pcm)
            if result >= 0 and not is_recording:
                keyword_detected = True
                is_recording = True
                # Add a small delay to prevent immediate re-triggering
                time.sleep(0.5)
                record_audio()
        except Exception as e:
            print(f"Listening error: {str(e)}")
            break

def record_audio():
    global transcript, keyword_detected, is_recording
    frames = []
    sample_rate = porcupine.sample_rate
    frames_per_buffer = porcupine.frame_length
    
    # Calculate exact number of frames for 2 seconds
    max_recording_frames = int(2 * sample_rate / frames_per_buffer)
    frames_recorded = 0
    
    print(f"Starting recording for {max_recording_frames} frames")  # Debug log
    
    # Get current time for timeout
    start_time = time.time()
    timeout = 2.0  # 2 seconds
    
    # Include the wake word in the recording
    pcm_b = audio_stream.read(frames_per_buffer, exception_on_overflow=False)
    frames.append(pcm_b)
    frames_recorded += 1
    
    while is_listening and is_recording and (time.time() - start_time) < timeout:
        try:
            pcm_b = audio_stream.read(frames_per_buffer, exception_on_overflow=False)
            frames.append(pcm_b)
            frames_recorded += 1
        except Exception as e:
            print(f"Recording error: {str(e)}")
            break
    
    print(f"Recorded {frames_recorded} frames")  # Debug log
    
    if not is_listening or not is_recording:
        print("Recording stopped early")
        return
    
    try:
        print("Saving recording...")  # Debug log
        wf = wave.open(AUDIO_FILENAME, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        print("Starting transcription...")  # Debug log
        transcribe_audio()
    except Exception as e:
        transcript = f"Recording error: {str(e)}"
        transcript_history.append(transcript)
        print(f"Error in recording: {str(e)}")  # Debug log
    finally:
        is_recording = False
        print("Recording completed")  # Debug log

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def get_status():
    global keyword_detected, transcript, is_recording, has_new_transcript
    response = {
        "keyword_detected": keyword_detected,
        "is_recording": is_recording,
        "transcript": transcript if has_new_transcript else "",
        "has_new_transcript": has_new_transcript
    }
    keyword_detected = False  # Reset after reading
    has_new_transcript = False  # Reset after reading
    return jsonify(response)

@app.route('/history', methods=['GET'])
def get_history():
    global transcript_history
    return jsonify(list(transcript_history))

def cleanup():
    global porcupine, cobra, pa, audio_stream
    if audio_stream:
        audio_stream.close()
    if porcupine:
        porcupine.delete()
    if cobra:
        cobra.delete()
    if pa:
        pa.terminate()

if __name__ == '__main__':
    if initialize_audio():
        try:
            app.run(debug=True, port=5000)
        finally:
            cleanup()
    else:
        print("Failed to initialize audio components")