# Jupyter Watchdog

**Jupyter Watchdog** is an IPython/Jupyter extension that monitors your cell executions and notifies you when long-running tasks complete.

## Features

- **Browser & Desktop Notifications**: Native notifications that work even if your browser is in the background.
- **Audio Feedback**: A subtle "beep" sound plays upon completion, using Web Audio API.
- **Auto-Watchdog**: Automatically monitor *all* cells and alert you only if they run longer than a specific threshold (e.g., 60 seconds).
- **Discord Integration**: Optionally send notifications to a Discord channel.

## Installation & Loading

Since this is a standalone Python file extension, ensure `jupyter_watchdog.py` is in your Python path or in the same directory as your notebook.

Load the extension in your Jupyter Notebook/Lab:

```python
%load_ext jupyter_watchdog
```

## Usage

### 1. Manual Notification (`%%notify`)
Use the `%%notify` cell magic to explicitly monitor a specific cell.

```python
%%notify
import time
time.sleep(5)
```
*Triggers a notification immediately after the cell finishes.*

**Modes:**
- `%%notify` or `%%notify system`: Standard browser notification + Audio.
- `%%notify discord`: Force a Discord notification (if configured) + Browser.

---

### 2. Auto-Watchdog (`%watchdog_auto`)
Set a threshold (in seconds) to automatically monitor all running cells.

```python
%watchdog_auto 10
```
*If ANY cell runs longer than 10 seconds, you will get a notification. Short cells are ignored.*

To disable:
```python
%watchdog_auto 0
```

---

### 3. Discord Configuration (`%watchdog_setup`)
To receive notifications on Discord (e.g., on your phone), you need a [Discord Webhook URL](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).

**Option A: Setup via Magic (Session only)**
```python
%watchdog_setup https://discord.com/api/webhooks/...
```

**Option B: Environment Variable (Permanent)**
Set the `JUPYTER_WATCHDOG_WEBHOOK` environment variable before launching Jupyter.

---

## Privacy & Safety
- **No data export**: Your code and results stay local. Only the completion status and duration are sent to Discord (if configured).
- **Safe HTML/JS**: Uses `json.dumps` for safe JavaScript injection.
- **Non-blocking**: Discord requests run in a background thread with strict timeouts, so your notebook **never** freezes.
