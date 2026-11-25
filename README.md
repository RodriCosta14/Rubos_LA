# Rubos LA (v5.2)

A local Windows desktop assistant built in Python, tailored for European Portuguese (PT-PT). It handles continuous voice calls, opens and closes apps/windows, analyzes screenshots, searches the web, manages a local schedule with voice reminders, and keeps a private vector memory (RAG).

## What you need

* **Windows 10 or 11 (64-bit):** The app hooks directly into the Windows Registry, PowerShell, UAC, and native audio APIs, so it won't run on Linux or macOS.
* **Python 3.10+:** When running the installer on Windows, make sure **Add Python to PATH** and **tcl/tk and IDLE** (needed for the `tkinter` UI) are checked.
* **Mic & Speakers:** Needed if you want to use the voice call mode and TTS responses.

## Setup

### 1. Python dependencies

Clone the repo, open a terminal in the project folder, and install the packages:

```bash
pip install requests SpeechRecognition sounddevice numpy edge-tts Pillow psutil ddgs
```

*(Note: `requests` is the only hard requirement for basic chat. The rest enable voice input/output, screen capture, system stats, and DuckDuckGo search—the app will still boot if some optional ones are missing.)*

### 2. Ollama (Local LLM)

Rubos will try to start `ollama serve` automatically in the background when you launch it, so just make sure [Ollama](https://ollama.com) is installed. Then pull the models you want to use:

```bash
# Main chat model (defaults to 'rubos-livre:latest' if you have a custom model, otherwise picks an installed one)
ollama pull dolphin-llama3

# Needed if you want to use Screen Capture or Attach Image
ollama pull minicpm-v

# Optional: better semantic search for local memory/files (falls back to a simple local vectorizer if missing)
ollama pull nomic-embed-text
```

### 3. Portuguese Voice (PT-PT)

You can switch between three voice engines in the sidebar. Set up whichever you prefer:

* **Piper (Offline - Recommended):** Grab `piper_windows_amd64.zip` from the Piper releases and extract it into `vozes_piper/` (or `vozes_piper/piper/`). Download `pt_PT-tugao-medium.onnx` and `pt_PT-tugao-medium.onnx.json` from `rhasspy/piper-voices` on Hugging Face and drop both into `vozes_piper/`.
* **Edge TTS (Online):** Works out of the box once `edge-tts` is installed via pip. Gives you the Duarte and Raquel PT-PT neural voices.
* **Windows Native (Offline fallback):** Go to **Windows Settings > Time & language > Language & region**, add **Portuguese (Portugal)**, and install its Text-to-speech pack.

## Running it

From the project folder, run:

```bash
python Rubos_3.py
```

The console window hides itself automatically and launches the GUI. On the first run, it creates a few folders and files in the root directory:

* `vozes_piper/` — put `piper.exe` and your `.onnx` voice models here.
* `scripts/` — drop custom `.py` scripts here to trigger them by voice or text (also supports optional `tocar_spotify.py`, `controlar_spotify.py`, and `ligar_discord.py`).
* `imagens_rubos/` — where web images get saved.
* `base_vetorial_rubos.json` & `agenda_rubos.json` — local JSON storage for your RAG memory and calendar events.
