"""
Voice Transcriber — Gemini Live API
Mode 1: Real-time live transcription (types as you speak)
Mode 2: Batch recording, then paste transcription to clipboard
"""
import sys
import os
import asyncio
import traceback
import struct
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
from google import genai
from google.genai import types

# ============================================================
# Logging — write to a file next to the script for debugging
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v2c_python.log")

def log(msg):
    """Append a timestamped log message to the log file."""
    try:
        import datetime
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        pass

log("=" * 60)
log(f"Script started. Python: {sys.executable} v{sys.version}")
log(f"Arguments: {sys.argv}")

# ============================================================
# ⚠️  PASTE YOUR GEMINI API KEY BELOW
# ============================================================
API_KEY = "YOUR API KEY"
# ============================================================

if not API_KEY:
    log("ERROR: No API key set!")
    print("ERROR: No API key set! Open voice_transcriber.py and set API_KEY.")
    sys.exit(1)

try:
    client = genai.Client(api_key=API_KEY)
    log("Gemini client created successfully")
except Exception as e:
    log(f"ERROR creating Gemini client: {e}")
    sys.exit(1)

MODE = sys.argv[1] if len(sys.argv) > 1 else "1"
log(f"Mode: {MODE}")

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 100  # Send audio every 100ms
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

# Verify audio device is available
try:
    default_input = sd.query_devices(kind='input')
    log(f"Default input device: {default_input['name']}")
except Exception as e:
    log(f"ERROR: No audio input device found: {e}")
    sys.exit(1)


def record_audio_chunk():
    """Record a short chunk of audio and return as raw PCM16 bytes."""
    audio = sd.rec(CHUNK_SAMPLES, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    sd.wait()
    return audio.tobytes()


def stream_live():
    """Mode 1: Real-time transcription via Gemini Live API — types as you speak."""

    async def session_loop():
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
        )
        
        log("Connecting to Gemini Live API...")
        async with client.aio.live.connect(
            model="gemini-3.5-transcribe-live",
            config=config,
        ) as session:
            log("Live session connected!")
            print("Live session connected. Speak now... (press Esc to stop)")

            stop_event = asyncio.Event()

            async def send_audio():
                """Continuously capture and send audio chunks."""
                log("send_audio started")
                try:
                    while not stop_event.is_set():
                        # Check for Esc in a non-blocking way
                        if keyboard.is_pressed('esc'):
                            log("Esc detected in send_audio")
                            stop_event.set()
                            break
                        chunk = await asyncio.to_thread(record_audio_chunk)
                        await session.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                        )
                except Exception as e:
                    log(f"send_audio error: {e}")
                finally:
                    log("send_audio finished")
                    try:
                        await session.close()
                    except Exception:
                        pass

            async def receive_text():
                """Receive transcribed text and type it at cursor."""
                log("receive_text started")
                try:
                    async for response in session.receive():
                        if stop_event.is_set():
                            break
                        if response.server_content and response.server_content.model_turn:
                            for part in response.server_content.model_turn.parts:
                                if hasattr(part, 'text') and part.text:
                                    log(f"Received text: {part.text[:50]}...")
                                    keyboard.write(part.text)
                except Exception as e:
                    log(f"receive_text error: {e}")
                finally:
                    log("receive_text finished")

            # Run send and receive concurrently
            await asyncio.gather(send_audio(), receive_text())

    log("Starting Live Transcription (Mode 1)...")
    print("Starting Live Transcription (Mode 1)...")
    asyncio.run(session_loop())
    log("Live session ended.")
    print("Live session ended.")


def process_batch():
    """Mode 2: Record all audio, then transcribe and copy to clipboard."""
    log("Starting Batch Recording (Mode 2)...")
    print("Batch Recording (Mode 2)... Press Esc to finish and transcribe.")

    frames = []

    def audio_callback(indata, frame_count, time_info, status):
        """Callback for continuous recording."""
        if status:
            log(f"Audio callback status: {status}")
        frames.append(indata.copy())

    # Start continuous recording via callback
    log("Opening audio input stream...")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
        callback=audio_callback,
        blocksize=CHUNK_SAMPLES,
    ):
        log("Audio stream opened, recording... waiting for Esc")
        # Block until Esc is pressed
        keyboard.wait('esc')

    log(f"Recording stopped. Captured {len(frames)} frames.")
    print("Recording stopped. Transcribing...")

    if not frames:
        log("No audio recorded!")
        print("No audio recorded.")
        return

    # Combine all frames into one audio blob
    audio_data = np.concatenate(frames).tobytes()
    log(f"Audio data size: {len(audio_data)} bytes")

    # Send to Gemini for transcription
    try:
        log("Sending audio to Gemini API...")
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                "Transcribe the following audio accurately. Output ONLY the transcription text, nothing else.",
                types.Part.from_bytes(
                    data=audio_data,
                    mime_type='audio/pcm;rate=16000',
                )
            ]
        )

        transcription = response.text.strip()
        pyperclip.copy(transcription)
        log(f"Transcription copied to clipboard! ({len(transcription)} chars)")
        log(f"Transcription: {transcription[:200]}...")
        print(f"Transcription copied to clipboard! ({len(transcription)} chars)")
    except Exception as e:
        log(f"API Error: {e}")
        log(traceback.format_exc())
        print(f"API Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        if MODE == "1":
            stream_live()
        elif MODE == "2":
            process_batch()
        else:
            log(f"Unknown mode: {MODE}")
            print(f"Unknown mode: {MODE}")
    except KeyboardInterrupt:
        log("Interrupted by user")
        print("Interrupted.")
    except Exception as e:
        log(f"Fatal error: {e}")
        log(traceback.format_exc())
        print(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        log("Script exiting.")
