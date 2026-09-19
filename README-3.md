# screen_ai_tool

Press a hotkey, screenshot your screen, get a Gemini-powered answer displayed
directly on top of it — either as a single floating answer box, or as
per-region annotations drawn next to whatever they describe.

## Features

- **Box mode** — one rounded, semi-transparent answer box (position and
  color configurable), toggled on/off by the hotkey.
- **Annotate mode** — asks Gemini for labeled regions (tabs, code lines,
  images, UI elements) and draws each label directly over that region on a
  fullscreen, click-through transparent layer.
- **Multi-key + multi-model rotation** — add as many API keys and model
  names as you want; on a quota/rate-limit/model-not-found error it
  automatically retries the next combination.
- **Control panel GUI** (`control_panel.py`) — Tkinter app for editing keys,
  models, prompts, hotkey, fonts, colors, and layout without touching JSON
  by hand. Save & Run launches the overlay directly.
- **Per-run metrics** — capture time, API time, total round-trip time, and
  token usage logged to `metrics.csv`.

## Getting an API key (free)

1. Go to **[aistudio.google.com](https://aistudio.google.com/)** and sign in
   with any Google account.
2. Click **"Get API key"** (top left or in the menu) → **"Create API key."**
3. Copy the key it generates — starts with `AIzaSy` or `AQ.`.
4. Keep this tab open if you want more than one key (see "multiple keys"
   below) — each click of "Create API key" makes a new one.

This is separate from a paid Gemini *app* subscription (Google One AI
Premium, etc.) — that doesn't give you API access. The API key above has its
own free tier with daily/per-minute limits.

**Heads up on quota:** Gemini's free tier is scoped **per Google Cloud
project**, not per key. If you generate several keys from the same Google
account without creating separate projects, they usually share one quota
pool — adding keys won't raise your limit in that case. Keys from genuinely
different Google accounts (or different projects under Cloud Console) get
separate pools.

## Setup

1. **Install Python 3.10+** from [python.org](https://python.org/downloads)
   if you don't have it. On the installer's first screen, check
   **"Add python.exe to PATH"** before clicking Install.

2. **Install dependencies** — open a terminal in this folder and run:
   ```
   python -m pip install --user -r requirements.txt
   ```
   (Use `py` instead of `python` if Windows says `python` isn't recognized.)

3. **Set up your config** — either:
   - Run `python control_panel.py`, paste your key(s) into the "API Keys &
     Models" tab, hit **Save**. This creates `config.json` for you.
   - Or manually: `cp config.example.json config.json`, then open
     `config.json` and replace `YOUR_GEMINI_API_KEY_HERE` with your real key.

4. **Run it:**
   ```
   python control_panel.py
   ```
   then **Save & Run** — or, if `config.json` is already set up, run
   `python screen_ai.py` directly.

5. Press your configured hotkey (backtick `` ` `` by default) over any
   screen content.

### Adding multiple keys

In the control panel's "API Keys & Models" tab, click **"+ Add key"** for
each additional key — no limit. `screen_ai.py` rotates through all of them
(and every model listed) automatically when one hits a quota or
rate-limit error.


## Notes / limitations

- Windows only right now — the click-through overlay and rounded-corner
  rendering both rely on Win32-specific tricks (`ctypes.windll`,
  `-transparentcolor`). Linux/macOS would need a different overlay
  implementation.
- Gemini's free tier quota is scoped **per project, per model** — not per
  API key. If all your keys come from the same Google Cloud project, adding
  more keys won't actually raise your quota; you need either separate
  projects/accounts or a billing-enabled project.
- Annotate mode's bounding-box accuracy depends on the model and how dense
  the screen content is — expect some drift on cluttered screens.

## Security

`config.json` is git-ignored on purpose — it holds your real API key(s).
Never commit it. If you ever accidentally do, treat those keys as
compromised and regenerate them at aistudio.google.com immediately;
removing the file in a later commit does not remove it from git history.

## License

MIT — see [LICENSE](LICENSE).
