"""
=============================================================================
🎙 Voice Typing Application — All-in-One Python Edition
=============================================================================
Combines hotkey detection, translucent GUI overlays, and Gemini AI voice
transcription into a SINGLE Python file.

Hotkeys to launch:
  • Copilot Key (Win+Shift+F23 / Win+F23 / F23)
  • Ctrl+Shift+H (Universal fallback)

Modes:
  • Mode 1: Live Transcription (streams audio, types real-time at cursor)
  • Mode 2: Clipboard Paste (records batch audio, transcribes, copies to clipboard)
  • Esc: Cancel menu or stop active recording
=============================================================================
"""

import sys
import os
import time
import io
import wave
import base64
import threading
import asyncio
import traceback
import tkinter as tk
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
from google import genai
from google.genai import types

# =============================================================================
# Configuration & Logging
# =============================================================================
API_KEY = "YOUR API KEY"
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_app.log")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 100
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

def log(msg):
    """Write timestamped logs to file and console."""
    try:
        import datetime
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {msg}"
        print(line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# Initialize Gemini Client
client = None
try:
    client = genai.Client(api_key=API_KEY)
    log("Gemini Client initialized successfully.")
except Exception as e:
    log(f"Failed to initialize Gemini Client: {e}")

# =============================================================================
# State Management
# =============================================================================
class AppState:
    def __init__(self):
        self.root = None
        self.menu_window = None
        self.timer_window = None
        self.timer_label = None
        self.timer_running = False
        self.record_start_time = 0
        self.is_recording = False
        self.current_mode = None
        self.stop_event = threading.Event()
        self.last_trigger_time = 0
        self.cleanup_menu_fn = None

state = AppState()

# =============================================================================
# UI Components (Tkinter Overlays)
# =============================================================================
def get_screen_geometry(root):
    """Return width and height of the screen."""
    return root.winfo_screenwidth(), root.winfo_screenheight()

def show_mode_menu():
    """Display centered translucent mode selection popup."""
    now = time.time()
    if now - state.last_trigger_time < 0.35:
        return
    state.last_trigger_time = now

    if state.is_recording:
        log("Already recording, ignoring menu request.")
        return

    if state.menu_window and state.menu_window.winfo_exists():
        log("Menu already open.")
        return

    log("Opening Mode Selection Menu...")

    menu = tk.Toplevel(state.root)
    state.menu_window = menu
    menu.title("Voice Typing Mode")
    menu.overrideredirect(True)
    menu.attributes("-topmost", True)
    try:
        menu.attributes("-alpha", 0.92)
    except Exception:
        pass

    # Styling dimensions
    width, height = 370, 150
    screen_w, screen_h = get_screen_geometry(state.root)
    pos_x = (screen_w - width) // 2
    pos_y = (screen_h - height) // 2
    menu.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    menu.configure(bg="#111111")

    # Outer border frame
    border_frame = tk.Frame(menu, bg="#2a2a2a", bd=1)
    border_frame.pack(fill="both", expand=True, padx=2, pady=2)
    inner_frame = tk.Frame(border_frame, bg="#111111", padx=22, pady=16)
    inner_frame.pack(fill="both", expand=True)

    # Title & Options
    lbl_title = tk.Label(
        inner_frame,
        text="🎙  Voice Typing Mode",
        font=("Segoe UI", 14, "bold"),
        fg="#FFFFFF",
        bg="#111111",
        anchor="w"
    )
    lbl_title.pack(fill="x", pady=(0, 10))

    lbl_opt1 = tk.Label(
        inner_frame,
        text="Press 1  →  Live Typing (real-time)",
        font=("Segoe UI", 11),
        fg="#D6D6D6",
        bg="#111111",
        anchor="w"
    )
    lbl_opt1.pack(fill="x", pady=2)

    lbl_opt2 = tk.Label(
        inner_frame,
        text="Press 2  →  Clipboard Paste (batch)",
        font=("Segoe UI", 11),
        fg="#D6D6D6",
        bg="#111111",
        anchor="w"
    )
    lbl_opt2.pack(fill="x", pady=2)

    lbl_cancel = tk.Label(
        inner_frame,
        text="Press Copilot key to cancel",
        font=("Segoe UI", 9),
        fg="#7E7E7E",
        bg="#111111",
        anchor="w"
    )
    lbl_cancel.pack(fill="x", pady=(8, 0))

    # Mode selection hook
    def choose_mode(mode_val):
        cleanup_menu(cancel_session=False)
        if mode_val in ("1", "2"):
            log(f"Selected Mode: {mode_val}")
            start_recording_session(mode_val)

    def cleanup_menu(cancel_session=False):
        try:
            keyboard.unhook(menu_hook)
        except Exception:
            pass
        if state.menu_window and state.menu_window.winfo_exists():
            state.menu_window.destroy()
        state.menu_window = None
        state.cleanup_menu_fn = None
        if cancel_session and not state.is_recording:
            log("Menu cancelled without mode selection — exiting session.")
            state.root.after(100, state.root.destroy)

    state.cleanup_menu_fn = cleanup_menu

    # Capture global key presses while menu is active (only 1 or 2)
    def on_global_key(event):
        if event.event_type != keyboard.KEY_DOWN:
            return
        if event.name == "1":
            state.root.after(0, lambda: choose_mode("1"))
        elif event.name == "2":
            state.root.after(0, lambda: choose_mode("2"))

    menu_hook = keyboard.hook(on_global_key)

    # Auto-cancel and exit after 10 seconds of inactivity
    state.root.after(10000, lambda: cleanup_menu(cancel_session=True) if state.menu_window == menu else None)

def show_timer_overlay():
    """Display recording timer at top-right of the primary screen."""
    if state.timer_window and state.timer_window.winfo_exists():
        return

    overlay = tk.Toplevel(state.root)
    state.timer_window = overlay
    overlay.title("Recording Timer")
    overlay.overrideredirect(True)
    overlay.attributes("-topmost", True)
    try:
        overlay.attributes("-alpha", 0.88)
    except Exception:
        pass

    width, height = 180, 42
    screen_w, _ = get_screen_geometry(state.root)
    pos_x = screen_w - width - 25
    pos_y = 35
    overlay.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    overlay.configure(bg="#1a1a1a")

    border_frame = tk.Frame(overlay, bg="#333333", bd=1)
    border_frame.pack(fill="both", expand=True, padx=1, pady=1)

    lbl = tk.Label(
        border_frame,
        text="⏺ REC  00:00",
        font=("Segoe UI", 12, "bold"),
        fg="#FF4444",
        bg="#1a1a1a"
    )
    lbl.pack(fill="both", expand=True)
    state.timer_label = lbl

    state.record_start_time = time.time()
    state.timer_running = True
    update_timer_tick()

def update_timer_tick():
    """Update elapsed time on the timer overlay every 500ms."""
    if not state.timer_running or not state.timer_window or not state.timer_window.winfo_exists():
        return

    elapsed = int(time.time() - state.record_start_time)
    mins = elapsed // 60
    secs = elapsed % 60
    if state.timer_label and state.timer_label.winfo_exists():
        state.timer_label.config(text=f"⏺ REC  {mins:02d}:{secs:02d}", fg="#FF4444")
    
    state.root.after(500, update_timer_tick)

def update_timer_status(text, color="#FFCC00"):
    """Update overlay text status (e.g., Transcribing or Copied)."""
    state.timer_running = False
    if state.timer_label and state.timer_label.winfo_exists():
        state.timer_label.config(text=text, fg=color, font=("Segoe UI", 10, "bold"))

def close_timer_overlay():
    """Destroy the timer overlay."""
    state.timer_running = False
    if state.timer_window and state.timer_window.winfo_exists():
        state.timer_window.destroy()
    state.timer_window = None
    state.timer_label = None

# =============================================================================
# Audio Collection & Transcription Logic
# =============================================================================
def run_mode_1_live():
    """Mode 1: Live transcription using Gemini Live API (types as you speak)."""
    log("Mode 1 (Live) started.")

    async def live_worker():
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        try:
            async with client.aio.live.connect(
                model="gemini-3.5-transcribe-live",
                config=config,
            ) as session:
                log("Live session connected to gemini-3.5-transcribe-live!")

                loop = asyncio.get_running_loop()
                audio_queue = asyncio.Queue()

                def audio_callback(indata, frames, time_info, status):
                    if not state.stop_event.is_set():
                        loop.call_soon_threadsafe(audio_queue.put_nowait, indata.copy().tobytes())

                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    callback=audio_callback,
                    blocksize=CHUNK_SAMPLES,
                )

                async def send_audio():
                    with stream:
                        log("Continuous microphone stream active.")
                        while not state.stop_event.is_set():
                            try:
                                chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.2)
                                await session.send_realtime_input(
                                    media=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                                )
                            except asyncio.TimeoutError:
                                continue
                            except Exception as ex:
                                if not state.stop_event.is_set():
                                    log(f"Error sending audio chunk: {ex}")
                                break
                    try:
                        await session.close()
                    except Exception:
                        pass

                async def receive_text():
                    last_typed = ""
                    try:
                        while not state.stop_event.is_set():
                            async for response in session.receive():
                                if state.stop_event.is_set():
                                    break
                                sc = getattr(response, "server_content", None)
                                if not sc:
                                    continue

                                # 1. Extract live interim or final transcription
                                new_text = ""
                                is_final = False
                                if sc.input_transcription and sc.input_transcription.text:
                                    new_text = sc.input_transcription.text.strip()
                                    is_final = True
                                elif sc.interim_input_transcription and sc.interim_input_transcription.text:
                                    new_text = sc.interim_input_transcription.text.strip()

                                if new_text:
                                    log(f"Live speech detected: {new_text}")
                                    # Delta typing: find common prefix between last_typed and new_text
                                    k = 0
                                    while k < len(last_typed) and k < len(new_text) and last_typed[k] == new_text[k]:
                                        k += 1
                                    backspaces = len(last_typed) - k
                                    to_type = new_text[k:]

                                    if backspaces > 0:
                                        for _ in range(backspaces):
                                            keyboard.send("backspace")
                                    if to_type:
                                        keyboard.write(to_type)
                                    last_typed = new_text

                                # If speech turn completed or finalized, add trailing space and reset buffer
                                if is_final or getattr(sc, "turn_complete", False):
                                    if last_typed:
                                        keyboard.write(" ")
                                        last_typed = ""

                    except Exception as ex:
                        if not state.stop_event.is_set():
                            log(f"receive_text error: {ex}")

                await asyncio.gather(send_audio(), receive_text())
        except Exception as e:
            log(f"Live connect session error: {e}")

    try:
        asyncio.run(live_worker())
    except Exception as e:
        log(f"Error running live loop: {e}")
    finally:
        state.is_recording = False
        state.root.after(0, close_timer_overlay)
        log("Mode 1 (Live) ended.")
        # Auto-exit Python session after live transcription finishes
        state.root.after(400, state.root.destroy)

def run_mode_2_batch():
    """Mode 2: Batch recording, sends audio to gemini-3.5-transcribe via Interactions API."""
    log("Mode 2 (Batch) started. Recording until Esc...")

    frames = []

    def audio_callback(indata, frame_count, time_info, status):
        if status:
            log(f"Audio status: {status}")
        frames.append(indata.copy())

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=audio_callback,
            blocksize=CHUNK_SAMPLES,
        ):
            while not state.stop_event.is_set():
                time.sleep(0.05)
    except Exception as e:
        log(f"Error in batch audio stream: {e}")

    log(f"Mode 2: Captured {len(frames)} audio blocks.")

    # Show transcribing state on overlay
    state.root.after(0, lambda: update_timer_status("⏳ Transcribing...", "#FFCC00"))

    if not frames:
        log("No audio recorded.")
        state.root.after(1000, close_timer_overlay)
        state.is_recording = False
        return

    # Convert audio frames to in-memory WAV
    try:
        raw_pcm = np.concatenate(frames).tobytes()
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(raw_pcm)
        wav_bytes = wav_io.getvalue()

        # Send to gemini-3.5-transcribe via the Interactions API
        transcription = ""
        try:
            log("Transcribing with gemini-3.5-transcribe via Interactions API...")
            b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
            interaction = client.interactions.create(
                model="gemini-3.5-transcribe",
                input=[
                    {"type": "audio", "data": b64_audio, "mime_type": "audio/wav"}
                ],
            )
            transcription = (getattr(interaction, "output_text", None) or "").strip()
            log(f"Interactions API transcription: {transcription[:120]}...")
        except Exception as api_err:
            log(f"gemini-3.5-transcribe Interactions API failed: {api_err}")
            # Fallback to gemini-2.5-flash
            try:
                log("Falling back to gemini-2.5-flash generate_content...")
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        "Transcribe the following audio accurately. Output ONLY the transcription text, nothing else.",
                        types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                    ],
                )
                transcription = (resp.text or "").strip()
            except Exception as fb_err:
                log(f"Fallback model failed: {fb_err}")

        if transcription:
            pyperclip.copy(transcription)
            log(f"Transcribed and copied to clipboard: {transcription[:120]}...")
            state.root.after(0, lambda: update_timer_status("✓ Copied to clipboard!", "#00FF88"))
        else:
            log("No transcription text returned.")
            state.root.after(0, lambda: update_timer_status("⚠ No speech detected", "#FF8888"))

    except Exception as e:
        log(f"Batch transcription error: {e}")
        log(traceback.format_exc())
        state.root.after(0, lambda: update_timer_status("⚠ Error transcribing", "#FF4444"))

    # Graceful delay before closing overlay
    time.sleep(1.5)
    state.is_recording = False
    state.root.after(0, close_timer_overlay)
    log("Mode 2 (Batch) completed.")
    # Auto-exit Python session after batch transcription finishes
    state.root.after(400, state.root.destroy)

def start_recording_session(mode):
    """Launch recording thread."""
    state.is_recording = True
    state.current_mode = mode
    state.stop_event.clear()

    # Show overlay timer
    show_timer_overlay()

    # Launch selected mode in worker thread
    target_fn = run_mode_1_live if mode == "1" else run_mode_2_batch
    worker_thread = threading.Thread(target=target_fn, daemon=True)
    worker_thread.start()

# =============================================================================
# Global Hotkey Dispatcher (Copilot Key & Fallbacks)
# =============================================================================
def on_hotkey_trigger(source="hotkey"):
    """Triggered by Copilot key or Ctrl+Shift+H."""
    if not state.root:
        return

    now = time.time()
    if now - state.last_trigger_time < 0.35:
        return
    state.last_trigger_time = now

    log(f"=== Trigger received from: {source} ===")

    # 1. If currently recording: pressing Copilot DISABLES / STOPS recording!
    if state.is_recording:
        log("Copilot key pressed while recording — disabling/stopping recording session.")
        state.stop_event.set()
        return

    # 2. If mode menu is open: pressing Copilot CANCELS / CLOSES the menu and exits!
    if state.menu_window and state.menu_window.winfo_exists():
        log("Copilot key pressed while menu open — closing mode menu and exiting session.")
        if state.cleanup_menu_fn:
            state.root.after(0, lambda: state.cleanup_menu_fn(cancel_session=True))
        return

    # 3. If idle: pressing Copilot OPENS the mode selection menu!
    state.root.after(0, show_mode_menu)

def setup_global_hotkeys():
    """Register all variations of Copilot key and Ctrl+Shift+H."""
    log("Registering hotkeys...")

    # Primary hotkeys with suppression to block Windows Copilot / MS Office from opening
    hotkeys = [
        ("windows+shift+f23", True),        # Standard Copilot key shortcut (suppressed)
        ("ctrl+alt+shift+windows", True),   # Microsoft / Office dedicated key (suppressed)
        ("windows+f23", True),              # Alternate Copilot key combo (suppressed)
        ("f23", True),                      # Direct Copilot hardware key (suppressed)
        ("ctrl+shift+h", False),            # Universal reliable shortcut
    ]

    for hk, sup in hotkeys:
        try:
            keyboard.add_hotkey(hk, lambda name=hk: on_hotkey_trigger(name), suppress=sup)
            log(f"Registered hotkey: {hk} (suppress={sup})")
        except Exception:
            try:
                keyboard.add_hotkey(hk, lambda name=hk: on_hotkey_trigger(name))
                log(f"Registered hotkey fallback: {hk}")
            except Exception as e2:
                log(f"Could not register {hk}: {e2}")

    # Fallback raw key interceptor for Copilot scan codes
    def on_raw_key(event):
        if event.event_type == keyboard.KEY_DOWN:
            # Key names or scan codes sent by Copilot hardware keys
            if event.name in ("f23", "f24", "copilot") or getattr(event, "scan_code", None) in (134, 110, 107):
                log(f"Raw Copilot key detected: name='{event.name}', scan_code={event.scan_code}, vk={getattr(event, 'vk', None)}")
                on_hotkey_trigger(f"raw_key({event.name})")

    try:
        keyboard.hook(on_raw_key)
        log("Registered raw key listener for Copilot hardware events.")
    except Exception as e:
        log(f"Could not register raw key listener: {e}")

# =============================================================================
# Application Entry Point
# =============================================================================
def main():
    log("=" * 60)
    log("🎙 Voice Typing Application (Single-Session Python Mode)")
    log("=" * 60)

    # Acquire session mutex to notify the C listener that Python is running
    import ctypes
    kernel32 = ctypes.windll.kernel32
    MUTEX_NAME = "Global\\VoiceTypingSessionMutex"
    h_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log("Another instance of voice_typing_app.py is already active. Exiting.")
        if h_mutex:
            kernel32.CloseHandle(h_mutex)
        return

    # Initialize Tkinter root (hidden coordinator)
    root = tk.Tk()
    root.withdraw()
    state.root = root

    # Verify audio input device
    try:
        dev = sd.query_devices(kind="input")
        log(f"Microphone detected: {dev['name']}")
    except Exception as e:
        log(f"WARNING: Audio device check: {e}")

    # Register hotkeys
    setup_global_hotkeys()

    print("\n" + "=" * 60)
    print(" Voice Typing is running!")
    print(" • Press 1 for Live Typing (types as you speak).")
    print(" • Press 2 for Clipboard Paste (batch transcription).")
    print(" • Press Copilot Key again while recording to stop.")
    print("=" * 60 + "\n")

    # Instantly open the mode selection menu on launch
    root.after(150, show_mode_menu)

    # Run Tkinter main event loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        log("Application stopped by user.")
    finally:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if h_mutex:
            try:
                kernel32.CloseHandle(h_mutex)
            except Exception:
                pass
        log("Voice Typing session exited.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "w", encoding="utf-8") as cf:
                cf.write(err_msg)
        except Exception:
            pass
        log(f"CRASH: {exc}")