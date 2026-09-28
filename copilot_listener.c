#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <stdio.h>
#include <stdbool.h>
#include <time.h>

/*
 * ============================================================================
 * Copilot Key Native KB-Sized Listener
 * ============================================================================
 * Super-lightweight Win32 daemon (< 25 KB compiled binary, ~800 KB RAM, 0% CPU).
 * Uses dual-layer detection:
 *   1. RegisterHotKey (OS-level reliable hotkeys for Win+Shift+F23, Ctrl+Shift+H, etc.)
 *   2. Low-Level Keyboard Hook (intercepts raw physical scan codes & suppresses default Copilot)
 *
 * When detected:
 *   - If voice_typing_app.py is NOT running:
 *       -> Launches pythonw.exe voice_typing_app.py silently.
 *   - If voice_typing_app.py IS running:
 *       -> Passes key through so the running Python session receives it
 *          to stop/disable recording and exit.
 * ============================================================================
 */

#define PYTHONW_PATH L"C:\\Users\\Dwaragesh k\\AppData\\Local\\Python\\pythoncore-3.14-64\\pythonw.exe"
#define SCRIPT_PATH  L"d:\\v2c\\voice_typing_app.py"
#define APP_MUTEX_NAME L"Global\\VoiceTypingSessionMutex"
#define LISTENER_MUTEX_NAME L"Global\\CopilotListenerSingletonMutex"
#define LOG_FILE "d:\\v2c\\listener.log"

#ifndef MOD_NOREPEAT
#define MOD_NOREPEAT 0x4000
#endif

static HHOOK g_hHook = NULL;
static ULONGLONG g_lastTriggerTime = 0;

static void LogMsg(const char *msg) {
    FILE *f = fopen(LOG_FILE, "a");
    if (f) {
        time_t t = time(NULL);
        struct tm *tm_info = localtime(&t);
        char buf[32];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", tm_info);
        fprintf(f, "%s | %s\n", buf, msg);
        fclose(f);
    }
}

/* Check if the Voice Typing Python session is actively running */
static bool IsVoiceAppRunning(void) {
    HANDLE hMutex = OpenMutexW(SYNCHRONIZE, FALSE, APP_MUTEX_NAME);
    if (hMutex != NULL) {
        CloseHandle(hMutex);
        return true;
    }
    return false;
}

/* Launch voice_typing_app.py silently via pythonw.exe */
static void LaunchVoiceApp(void) {
    LogMsg("Launching voice_typing_app.py session via pythonw...");

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    ZeroMemory(&pi, sizeof(pi));

    WCHAR cmdLine[1024];
    wsprintfW(cmdLine, L"\"%s\" \"%s\"", PYTHONW_PATH, SCRIPT_PATH);

    if (CreateProcessW(
            NULL,
            cmdLine,
            NULL,
            NULL,
            FALSE,
            0,
            NULL,
            L"d:\\v2c",
            &si,
            &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        LogMsg("voice_typing_app.py process created successfully.");
    } else {
        char errBuf[64];
        snprintf(errBuf, sizeof(errBuf), "Failed to launch voice_typing_app. Error: %lu", GetLastError());
        LogMsg(errBuf);
    }
}

static void HandleTrigger(const char *source) {
    char buf[128];
    snprintf(buf, sizeof(buf), "Trigger received from: %s", source);
    LogMsg(buf);

    if (IsVoiceAppRunning()) {
        LogMsg("Voice app is already running -> ignoring trigger in listener.");
        return;
    }

    ULONGLONG now = GetTickCount64();
    if (now - g_lastTriggerTime >= 800) {
        g_lastTriggerTime = now;
        LaunchVoiceApp();
    } else {
        LogMsg("Debounced rapid trigger.");
    }
}

/* Low-level keyboard hook callback */
static LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode == HC_ACTION && (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN)) {
        KBDLLHOOKSTRUCT *p = (KBDLLHOOKSTRUCT *)lParam;
        bool isTrigger = false;
        bool suppressKey = false;
        const char *triggerType = "";

        /* 1. Check for physical Copilot key: VK_F23 (0x86) or VK_F24 (0x87) */
        if (p->vkCode == 0x86) {
            isTrigger = true;
            suppressKey = true;
            triggerType = "Hook: Copilot Key (VK_F23)";
        } else if (p->vkCode == 0x87) {
            isTrigger = true;
            suppressKey = true;
            triggerType = "Hook: Copilot Alt (VK_F24)";
        }
        /* 2. Check for Office / MS key: VK_F21 (0x84) */
        else if (p->vkCode == 0x84) {
            isTrigger = true;
            suppressKey = true;
            triggerType = "Hook: MS Office Key (VK_F21)";
        }

        if (isTrigger) {
            if (IsVoiceAppRunning()) {
                /* Let running Python session receive it to stop recording */
                return CallNextHookEx(g_hHook, nCode, wParam, lParam);
            }

            HandleTrigger(triggerType);

            if (suppressKey) {
                return 1; /* Eat the key so Windows Copilot app does NOT open */
            }
        }
    }

    return CallNextHookEx(g_hHook, nCode, wParam, lParam);
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    /* Prevent multiple instances of the listener */
    HANDLE hSingle = CreateMutexW(NULL, TRUE, LISTENER_MUTEX_NAME);
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        if (hSingle) CloseHandle(hSingle);
        return 0;
    }

    LogMsg("Copilot Listener started. Dual-layer engine (RegisterHotKey + LowLevelHook).");

    /* 1. Register OS Hotkeys */
    RegisterHotKey(NULL, 1, MOD_WIN | MOD_SHIFT | MOD_NOREPEAT, 0x86);  /* Win + Shift + F23 */
    RegisterHotKey(NULL, 2, MOD_WIN | MOD_NOREPEAT, 0x86);              /* Win + F23 */
    RegisterHotKey(NULL, 3, MOD_NOREPEAT, 0x86);                        /* Raw F23 */
    RegisterHotKey(NULL, 4, MOD_NOREPEAT, 0x84);                        /* MS Office Key F21 */
    RegisterHotKey(NULL, 5, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 'H'); /* Ctrl + Shift + H */

    /* 2. Install Low-Level Keyboard Hook for raw hardware events & key suppression */
    g_hHook = SetWindowsHookExW(WH_KEYBOARD_LL, LowLevelKeyboardProc, GetModuleHandleW(NULL), 0);
    if (!g_hHook) {
        LogMsg("Warning: Could not install WH_KEYBOARD_LL hook; RegisterHotKey remains active.");
    } else {
        LogMsg("WH_KEYBOARD_LL hook active.");
    }

    /* Standard message loop — sleeps in OS wait state, 0.00% CPU */
    MSG msg;
    BOOL bRet;
    while ((bRet = GetMessageW(&msg, NULL, 0, 0)) != 0) {
        if (bRet == -1) {
            LogMsg("GetMessage error occurred.");
            break;
        }

        if (msg.message == WM_HOTKEY) {
            int hotkeyId = (int)msg.wParam;
            char srcBuf[64];
            snprintf(srcBuf, sizeof(srcBuf), "OS WM_HOTKEY (id=%d)", hotkeyId);
            HandleTrigger(srcBuf);
        }

        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    LogMsg("Copilot Listener exiting.");

    /* Unregister hotkeys */
    for (int i = 1; i <= 5; i++) {
        UnregisterHotKey(NULL, i);
    }

    /* Unhook on exit */
    if (g_hHook) {
        UnhookWindowsHookEx(g_hHook);
    }

    if (hSingle) {
        ReleaseMutex(hSingle);
        CloseHandle(hSingle);
    }

    return 0;
}
