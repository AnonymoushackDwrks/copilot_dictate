; ============================================================
; Voice Typing Launcher — AutoHotkey v2
; Catches:
;  • Copilot key (#+F23, #F23)
;  • Microsoft / Office key (^!+# / Ctrl+Alt+Shift+Win)
;  • Universal backup (^+h / Ctrl+Shift+H)
; ============================================================
#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent(true)

global ScriptDir := A_ScriptDir
global PythonApp := ScriptDir "\voice_typing_app.py"
global PythonExe := "C:\Users\Dwaragesh k\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
global PythonExeFallback := "C:\Users\Dwaragesh k\AppData\Local\Python\bin\pythonw.exe"

; ── Copilot key hardware combinations ─────────────────────
#+F23:: LaunchVoiceApp()   ; Win+Shift+F23 (Copilot key)
#F23::  LaunchVoiceApp()   ; Win+F23

; ── Microsoft / Office dedicated key ──────────────────────
^!+#::  LaunchVoiceApp()   ; Ctrl+Alt+Shift+Win (MS Office key)

; ── Universal keyboard shortcut ───────────────────────────
^+h::   LaunchVoiceApp()   ; Ctrl+Shift+H backup

LaunchVoiceApp() {
    global ScriptDir, PythonApp, PythonExe, PythonExeFallback
    exe := FileExist(PythonExe) ? PythonExe : PythonExeFallback
    try {
        Run('"' exe '" "' PythonApp '"', ScriptDir)
    } catch as err {
        MsgBox("Failed to launch Voice Typing:`n" err.Message, "Voice Typing Error", "Icon!")
    }
}
