import keyboard
import time
import os

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key_detected.log")

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("Listening for key presses... Press the key now!\n")

def on_event(event):
    if event.event_type == "down":
        line = f"KEY: name='{event.name}' | scan_code={event.scan_code} | vk={getattr(event, 'vk', None)}\n"
        print(line, end="")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)

hook = keyboard.hook(on_event)

try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    keyboard.unhook(hook)
