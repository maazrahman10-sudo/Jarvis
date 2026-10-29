# JARVIS

A lightweight personal assistant for Windows 10, with a quiet charcoal-and-cyan interface inspired by the supplied design. Runs in your browser with a Python backend; no large local language model, GPU runtime, Electron, Node, or frontend build is required.

**Implemented:** streamed Gemini chat; Stop generation; local conversation history, rename/delete and new conversation; push-to-talk; system speech and optional Fish Audio speech; approved app/website launching; encoded web searches; local tasks and notes; real CPU/memory readings; persistent settings. Chat and desktop actions are deliberately separate: use the visible action controls, rather than expecting the model to operate your PC from natural language.

**Verified in the build environment:** 16 backend tests, 5 stubbed voice lifecycle tests, and the Chromium browser smoke flow pass.

**Validation limits:** automated backend tests and Chromium UI checks can run on Linux. Real cloud responses require your credentials and internet access. Windows app launches, real microphones, Windows voices and Fish playback require the manual checks below. Official documentation requests were blocked by the build environment's proxy; the REST adapters need live account verification before relying on them. No live cloud or Windows compatibility claim is made from mocked tests.

## Windows setup (beginner friendly)

1. Install **64-bit Python 3.12** from [python.org](https://www.python.org/downloads/windows/). Enable the Python launcher in the installer. Windows 10 and your 16 GB RAM are sufficient; your RX 580 is not used.
2. Download/clone this repository and extract it to a folder you can write to. Avoid a public/shared folder. Open `setup_windows.bat`. It creates `.venv`, installs the compatible dependency versions in `requirements.txt`, copies `.env.example` to `.env` **only if `.env` does not already exist**, and runs the backend tests. Internet access is needed for installation.
3. Right-click `.env` and open it with Notepad. Obtain your own Gemini API key through [Google AI Studio](https://aistudio.google.com/). Set `GEMINI_API_KEY` and `GEMINI_MODEL` to a model ID available to your account. A model is intentionally not hardcoded because model availability changes. Do not include `models/` in the ID. Save the file.
4. Optional Fish Audio: set `FISH_API_KEY` to your **replacement** key, and optionally `FISH_REFERENCE_ID` to a voice you are authorized to use. `FISH_MODEL` is optional; when set it is sent as the model header. Never paste API keys into chat or commit `.env`. Revoke any key already shared in chat.
5. Double-click `launch_windows.bat`. Keep its console window open. The app opens in your default browser at the local address displayed by the launcher. Use **Windows Edge** for the best chance of browser speech-recognition support. No firewall exception or network sharing is needed. Do not change the server bind address to `0.0.0.0`.
6. Open Settings. Choose your display name, Gemini model, speech provider, voice and speech rate. Click **Save settings**. Settings never accept API keys. Restart the launcher after changing `.env`; ordinary settings apply immediately.
7. Press Ctrl+C in the launcher console to stop JARVIS. Launching again reuses an existing healthy JARVIS instance instead of starting another server.

Local tasks, notes, settings, and completed conversations live in `~/.jarvis/jarvis.sqlite3` (typically `C:\Users\YourName\.jarvis\jarvis.sqlite3`). Set `JARVIS_DATA_DIR` in `.env` to change this directory. Back up the directory only after stopping JARVIS. Data is local **plaintext**, protected by your Windows account permissions, not encrypted. Secure your account and backups. The session token rotates on restart; reload existing tabs afterward.

## Talking to JARVIS

- **Type:** enter a message and press Enter or the arrow button. The first exchange creates a conversation after it finishes successfully. Errors and stopped partial exchanges are not written to history. Context is bounded to the most recent 40 messages.
- **Push-to-talk:** hold the microphone button while speaking and release to finish. Keyboard users can focus it with Tab and hold Space or Enter. Review the transcript in the input, then press Enter to send. There is a 30-second cap. Recognition stops on window blur, hidden tabs and release; no continuous wake-word listener runs.
- **Voice privacy:** recognition uses the browser's implementation and may send audio to its speech service. It usually requires internet access and may be unsupported even when the microphone works. JARVIS never writes audio files. The transcript stays in the input until sent; history settings apply after sending.
- **Speech:** system voices use the asynchronous browser/OS speech service and need no API key. Prefer a voice marked **on device** for offline output. Online system voices may send response text to their provider. Speech is serialized and can be stopped. Starting recognition cancels speech; starting speech aborts recognition to avoid self-transcription.
- **Fish Audio:** choose Fish Audio in Settings after configuring its backend key. Response text is sent to Fish Audio; fees and voice permissions depend on your account. Fish output is fetched as bounded MP3 data and is not saved to disk. System voices remain available if the cloud service fails; the app does not silently switch providers.
- **Devices:** the selected microphone is used for the local input-level test. Browser SpeechRecognition does **not** support choosing a microphone; set its default input in Windows. Fish Audio can select a speaker if the browser supports `HTMLMediaElement.setSinkId`; system voices use the OS default output. Speech-rate control applies to system voices.
- **Stop:** the Stop control cancels generation, speech synthesis, or listening. A canceled cloud request may still incur provider usage. Click New to start a separate conversation. The rail's conversation icon opens saved history; rename/delete controls appear for each item. Collapse/Expand hides/shows the current exchange.

“LOCAL ONLINE” means the local backend is responding. It does not mean Gemini or Fish Audio has authenticated or is reachable; their availability is checked when requested. Error/disconnected visuals reflect application state. CPU and memory figures come from the PC running the backend, never generated values. Respecting reduced motion disables visual animation.

## Local tools

- **Open apps → Manage shortcuts:** add a name and a full local `.exe` path, e.g. `C:\Windows\System32\notepad.exe`. Save settings, then click that app in Open apps. No command-line arguments, scripts, network paths, path traversal, shell expressions or model-generated commands are accepted. A launch result reports process creation, not proof a window is visible.
- Add approved HTTPS websites in Settings. Open them from Apps & the web. Browser acceptance does not prove a page loaded.
- Web search opens an encoded Google search URL in your default Windows browser. JARVIS does not retrieve current results and must not claim it did.
- Create, complete/reopen or delete tasks in My tasks. Deletion requires in-app confirmation. Notes supports creating and retrieving local text notes; no external file writes occur.
- Apps & the web → Show local time uses the backend PC's timezone. Settings can disable future saved chat history or delete all stored conversations with confirmation. Turning history off does not delete existing records. Tasks and notes are not included in chat automatically.

Shutdown/restart, arbitrary commands, purchases, message sending, autonomous model actions and wake-word recording are intentionally not implemented. The tool registry validates action names and arguments; model output never enters it automatically. Local app approval is a deliberate permission to execute that binary; approve only software you trust.

## Microphone and speech tests on Windows

1. Start JARVIS in Edge. Windows Settings → Privacy → Microphone: allow microphone access and desktop/browser access. In Edge's address bar, allow microphone use for this local site.
2. Settings → Voice & audio → select a microphone → **Test microphone**. Speak: the meter should move. It stops after 10 seconds. **Stop audio** ends it early. This test stays local and does not feed a speaker.
3. Set your chosen input as the default in Windows Settings → System → Sound. Return Home, hold the mic, say “Hello JARVIS,” release. The transcript should appear in the input. Review it, then send. If recognition fails, type instead.
4. Settings → enable spoken responses → choose an on-device system voice → **Test speech**. Repeat it three times to check engine lifecycle. Stop audio should interrupt it immediately. Try a different voice and rate, then Save settings.
5. For Fish Audio, configure the replacement key, restart, choose Fish Audio and Test speech. Check that the desired authorized voice plays and Stop audio interrupts it. Select an alternate output if listed. Account/model compatibility needs this live check.
6. Confirm the mic does not transcribe speech playback: start Test speech, then hold the mic. Playback must stop first. Start speech while an input test is running only after ending the test.
7. Add Notepad as an approved app and launch it. Verify Windows opens it. Test an invalid executable path: a failure must be reported. Test an approved site and an encoded search such as `C++ & Python`.
8. Send two Gemini messages. Confirm the second uses context, Stop cancels a long response, New resets context, and completed history survives restarting. With a deliberately invalid key/model, verify a clear error instead of a success. Restore the correct configuration afterward.

## Troubleshooting: receives messages but does not speak

- Open Settings and enable spoken responses. Select the intended provider and Save settings. Click Test speech; a typed message must finish successfully before automatic speech begins.
- Check Windows volume, mute, default output, Bluetooth/headphone connection, browser tab mute and Windows app volume. System speech uses the Windows output, even if a Fish speaker is selected.
- Choose a different installed **on-device** voice and test again. Edge may need a user interaction before audio playback; click Test speech. Install a voice through Windows Settings → Time & Language → Speech if none are available. No voice files are downloaded by JARVIS.
- If Fish fails, inspect the visible error. Verify a replacement `FISH_API_KEY` is set in `.env`, restart, check account credit and voice reference permissions. Do not use the Gemini key for Fish. Leave `FISH_MODEL` empty unless your account's API documentation requires a specific model header.
- Stop other playback, press Stop audio, then retry. Reload the tab if the browser speech service stalled. Repeated tests should stay audible; the app uses one serialized speech queue and cancels it before microphone recognition.
- Mic test succeeds but recognition fails: input-level capture and recognition are different browser APIs. Check the Windows default mic, browser compatibility and internet connection. Use text as a fallback.
- “Local session expired”: reload after server restart. “DISCONNECTED”: ensure the launcher is still running. Port 8765 in use: close the conflicting program. Do not bind to your LAN as a workaround.
- Invalid Gemini key/model, rate limits and timeouts have distinct messages. A configured key indicator is not an authentication test. If internet access is restricted, allow HTTPS destinations `generativelanguage.googleapis.com` and optionally `api.fish.audio`, plus the browser's own speech service (browser-dependent).

## Development and verification

```text
backend/
  app.py               HTTP API, local security, stream lifecycle, static serving
  models.py            strict validated request schemas
  store.py             SQLite transactions and persistence
  actions.py           explicit approved action registry
  providers/base.py    AI provider interface and safe errors
  providers/gemini.py  Gemini REST streaming adapter
  providers/speech.py  Fish Audio REST speech adapter
frontend/
  index.html           accessible app shell and SVG symbols
  styles.css           responsive reference-inspired design
  app.js               UI, settings, tasks, history, actual activity state
  api.js               memory-only local authentication and NDJSON streaming
  voice.js             serialized system/Fish playback, push-to-talk and device tests
scripts/launch.py       loopback server/browser launcher
tests/test_jarvis.py    backend tests with deterministic provider transports
tests/browser_smoke.py optional Chromium UI check
tests/voice.test.mjs    optional dependency-free Node voice lifecycle tests
```

The frontend uses browser ES modules instead of React/TypeScript: the build machine could not reach the package registry, so a zero-build client made the complete interface runnable and verifiable without installing frontend packages. It can be replaced independently through the API. The Python FastAPI architecture and provider abstraction follow the requested separation. No desktop wrapper is required; this keeps memory usage lower.

On Linux/macOS for backend/UI development (Windows desktop actions return an explicit unsupported error):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Copy .env.example to .env if it does not exist; add credentials privately.
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/launch.py
```

On Windows tests can also be run with `.venv\Scripts\python.exe -m unittest discover -s tests -v`. The suite uses Python unittest, not pytest. Installed FastAPI/Starlette may emit an httpx TestClient deprecation warning; tests currently execute successfully with the pinned HTTP client.

The optional voice lifecycle checks run with `node --test tests/voice.test.mjs` (Node 20+; Node is only needed for this developer test). They test repeated playback, disabled speech, push-to-talk, self-transcription prevention and Stop using stubbed browser audio services. They do not validate real devices.

The optional browser smoke test requires Playwright and Chromium and is **not** part of installation. Start a server against an expendable test data directory, then run the script; it creates a note and modifies settings. It verifies real API task persistence, delete cancellation/confirmation, notes, settings, missing-key UI errors, fixture-based streamed rendering, mobile overflow and JS console errors. Set Chromium's executable path for your OS in the test harness if rerunning outside Linux. It is not a live cloud test.

Only one response generates at a time. Each Gemini request has connect/read timeouts and a two-minute total cap. Only selected transient HTTP statuses are retried once, before streaming any text. Fish requests have timeouts and a response-size cap with no automatic billing retries. Stored completed conversations are local; provider retention is governed by your provider account policies.

The local API binds to loopback port 8765, enforces Host and Origin checks, rejects cross-site browser requests, and requires a memory-only session bearer token for data/actions. Static resources are same-origin with a restrictive content-security policy. This protects against ordinary cross-site browser requests, not malware or another process already running as your Windows user. Access logging is disabled. Do not publish this API to the internet or LAN.

### Official reference links and unverified items

- [Gemini streaming generateContent REST](https://ai.google.dev/api/generate-content) — configurable model ID, `streamGenerateContent`, SSE and `x-goog-api-key`.
- [Fish Audio text-to-speech](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech) — backend REST adapter at `https://api.fish.audio/v1/tts`; confirm current model/voice requirements against your account before live use.
- [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/).
- [Browser SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition), [SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis), [setSinkId](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/setSinkId).

These official pages could not be retrieved during implementation because the environment proxy returned 403. No fixed cloud model was selected. Dependency compatibility was checked using the installed versions and executed tests, rather than claiming online documentation verification. Verify live services and Windows audio before daily use. No API key from the conversation has been saved in this project.
