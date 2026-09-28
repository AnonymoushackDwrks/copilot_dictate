Here is a highly detailed, professional prompt designed for an AI or software developer to build this application. It fully describes your concept, architecture, and exact features.
------------------------------
## 📝 Software Specification & System Prompt
Project Goal:
Create a lightweight, background Windows voice-typing application that functions similarly to Microsoft Voice Typing but introduces user-controlled operational modes via keyboard inputs and an on-screen visual overlay interface.
------------------------------
## 1. Core Architecture
The system consists of two tightly coupled layers:

* Frontend Controller (Keyboard & UI System): Handles custom macro bindings, window creation, visual tracking timers, and blocking keyboard hooks.
* Backend Processor (Audio & AI API Core): Interacts with audio hardware, initializes connection pipelines with the Gemini 3.5 Transcribe Live model using an explicit API key, and processes voice data streams.

------------------------------
## 2. Workflow Logic & Sequential Execution Tree

   1. Activation Phase (The Toggle Hook):
   * Monitor system inputs globally. When the user presses the combined shortcut Copilot + H, intercept the keystroke and launch a centered modal menu.
   2. Selection Phase (Interactive Filter Gate):
   * Display a centered, transparent menu overlay with the prompt options.
      * Strict Input Validation Rule: Put the application into a blocking capture loop.
      * If the user presses any key other than 1 or 2, do nothing—keep waiting for valid input.
         * If the user presses 1 or 2, register the choice, immediately destroy the selection menu overlay, and proceed to the designated processing mode.
      3. Execution Phase (Recording & Feedback):
   * Instantly display a small, semi-transparent visual timestamp timer clock running in the corner of the desktop screen (tracking runtime in MM:SS format).
      * Launch the audio collection processor in the background depending on the chosen mode.
   
------------------------------
## 3. Operation Processing Modes

* Mode 1: Dynamic Live Transcription
* Open a real-time, low-latency audio capture stream through the microphone.
   * Pipe chunks of the audio dynamically to the Gemini 3.5 Transcribe Live API.
   * As text fragments return from the server, inject the text payload directly into the active text cursor position in real-time while the user is actively speaking.
* Mode 2: Closed Batch Processing (Clipboard Paste)
* Silently capture and accumulate all microphone audio input locally while the session is running.
   * Keep track of the time on the overlay, but do not output text to the screen yet.
   * When the user stops the session, compress and send the completed audio payload directly to the API in one request.
   * Extract the finished text transcript and dump it directly into the Windows system Clipboard (Ctrl + V cache).

------------------------------
## 4. Termination & Teardown

* The Escape Mechanism: Pressing the Esc key acts as a master global fail-safe.
* Upon termination: Kill background audio stream tasks, stop API connection threads, dump the final clipboard payload (if Mode 2 was active), and cleanly remove all overlay visual tracking windows from the screen.

------------------------------
Would you like me to refine this prompt further by adding specific design specs (like exact font types, hex color codes, or width/height values for the overlay boxes)?

