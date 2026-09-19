import csv
import ctypes
import io
import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from datetime import datetime

from pynput import keyboard
import mss
from PIL import Image
import google.generativeai as genai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
METRICS_PATH = os.path.join(BASE_DIR, "metrics.csv")
TRANSPARENT_KEY = "#fe01fe"

ANNOTATE_PROMPT = (
    "Look at this screen. Identify the important regions (tabs, images, code lines, "
    "text blocks, buttons, panels). For EACH region return a short explanation of what "
    "it is or what it does.\n"
    "Return ONLY a JSON array, no markdown fences, no preamble. Each element:\n"
    '{"box_2d": [ymin, xmin, ymax, xmax], "label": "short explanation"}\n'
    "Coordinates are normalized 0-1000 relative to the image (y first, then x). "
    "Keep each label under 90 characters. Return at most 14 elements. "
    "No LaTeX or markdown in labels."
)

PALETTE = ["#ff6b6b", "#4ecdc4", "#ffe66d", "#a06cd5", "#59d102",
           "#ff9f1c", "#2ec4b6", "#e71d36", "#7bdff2", "#f4978e",
           "#b892ff", "#80ed99", "#ffd6a5", "#9bf6ff"]

DEFAULTS = {
    "hotkey": "`",
    "gemini_api_key": "",
    "gemini_api_keys": [],
    "model_name": "gemini-3.6-flash",
    "model_names": [],
    "prompt": "Answer what's on screen concisely.",
    "mode": "box",
    "annotate_prompt": ANNOTATE_PROMPT,
    "annotate_font_size": 10,
    "position": "bottom-center",
    "margin": 60,
    "max_width": 700,
    "font_family": "Segoe UI",
    "font_size": 12,
    "bg_color": "#111111",
    "text_color": "#ffffff",
    "alpha": 0.92,
    "corner_radius": 18
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULTS, f, indent=2)
        return dict(DEFAULTS)
    with open(CONFIG_PATH) as f:
        user_cfg = json.load(f)
    cfg = dict(DEFAULTS)
    cfg.update(user_cfg)
    return cfg


CFG = load_config()


def get_keys(cfg):
    keys = [k.strip() for k in cfg.get("gemini_api_keys", [])
            if k and k.strip() and not k.strip().startswith("PASTE_")]
    single = (cfg.get("gemini_api_key") or "").strip()
    if single and single not in keys and single != "YOUR_API_KEY_HERE":
        keys.append(single)
    return keys


def get_models(cfg):
    models = [m.strip() for m in cfg.get("model_names", []) if m and m.strip()]
    if not models and cfg.get("model_name"):
        models = [cfg["model_name"]]
    return models


KEYS = get_keys(CFG)
MODELS = get_models(CFG)
if not KEYS:
    raise SystemExit("No API keys in config.json. Run control_panel.py to add some.")
if not MODELS:
    raise SystemExit("No model in config.json. Run control_panel.py to set one.")

current_key_idx = 0
current_model_idx = 0


def configure_model():
    genai.configure(api_key=KEYS[current_key_idx])
    return genai.GenerativeModel(MODELS[current_model_idx])


model = configure_model()

root = tk.Tk()
root.withdraw()
overlay_win = None
ui_queue = queue.Queue()

STATE_IDLE, STATE_BUSY, STATE_SHOWING = "idle", "busy", "showing"
state = STATE_IDLE
state_lock = threading.Lock()


def resolve_hotkey(name):
    name = name.lower()
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unsupported hotkey in config.json: {name}")


HOTKEY = resolve_hotkey(CFG["hotkey"])


def make_click_through(win):
    """Let mouse clicks pass through the overlay to whatever is underneath."""
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, cur | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    except Exception as e:
        print(f"[overlay] click-through unavailable: {e}")


def compute_position(w, h, sw, sh, position, margin):
    positions = {
        "bottom-center": ((sw - w) // 2, sh - h - margin),
        "top-center": ((sw - w) // 2, margin),
        "bottom-left": (margin, sh - h - margin),
        "bottom-right": (sw - w - margin, sh - h - margin),
        "top-left": (margin, margin),
        "top-right": (sw - w - margin, margin),
        "center": ((sw - w) // 2, (sh - h) // 2),
    }
    return positions.get(position, positions["bottom-center"])


def draw_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
              x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
              x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def show_box_overlay(text):
    global overlay_win
    if overlay_win is not None:
        overlay_win.destroy()

    overlay_win = tk.Toplevel(root)
    overlay_win.overrideredirect(True)
    overlay_win.attributes("-topmost", True)
    overlay_win.attributes("-transparentcolor", TRANSPARENT_KEY)
    overlay_win.attributes("-alpha", CFG["alpha"])
    overlay_win.configure(bg=TRANSPARENT_KEY)

    font = (CFG["font_family"], CFG["font_size"])
    pad_x, pad_y = 16, 10

    measure = tk.Label(overlay_win, text=text, font=font,
                       wraplength=CFG["max_width"], justify="left")
    measure.update_idletasks()
    tw, th = measure.winfo_reqwidth(), measure.winfo_reqheight()
    measure.destroy()

    w, h = tw + pad_x * 2, th + pad_y * 2

    canvas = tk.Canvas(overlay_win, width=w, height=h, bg=TRANSPARENT_KEY,
                       highlightthickness=0, bd=0)
    canvas.pack()
    draw_rounded_rect(canvas, 1, 1, w - 1, h - 1, CFG["corner_radius"],
                      fill=CFG["bg_color"], outline=CFG["bg_color"])
    canvas.create_text(w / 2, h / 2, text=text, fill=CFG["text_color"], font=font,
                       width=CFG["max_width"], justify="left")

    sw, sh = overlay_win.winfo_screenwidth(), overlay_win.winfo_screenheight()
    x, y = compute_position(w, h, sw, sh, CFG["position"], CFG["margin"])
    overlay_win.geometry(f"{w}x{h}+{x}+{y}")
    overlay_win.lift()
    overlay_win.update()
    make_click_through(overlay_win)
    print(f"[overlay] box at x={x} y={y} size={w}x{h}")


def show_annotations(items):
    """Fullscreen transparent layer: each label drawn over the region it describes."""
    global overlay_win
    if overlay_win is not None:
        overlay_win.destroy()

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    overlay_win = tk.Toplevel(root)
    overlay_win.overrideredirect(True)
    overlay_win.attributes("-topmost", True)
    overlay_win.attributes("-transparentcolor", TRANSPARENT_KEY)
    overlay_win.geometry(f"{sw}x{sh}+0+0")
    overlay_win.configure(bg=TRANSPARENT_KEY)

    canvas = tk.Canvas(overlay_win, width=sw, height=sh, bg=TRANSPARENT_KEY,
                       highlightthickness=0, bd=0)
    canvas.pack()

    font = (CFG["font_family"], CFG["annotate_font_size"])
    drawn = 0
    for i, item in enumerate(items):
        box = item.get("box_2d") or item.get("box") or []
        label = str(item.get("label", "")).strip()
        if len(box) != 4 or not label:
            continue
        ymin, xmin, ymax, xmax = box
        x1 = xmin / 1000.0 * sw
        y1 = ymin / 1000.0 * sh
        x2 = xmax / 1000.0 * sw
        y2 = ymax / 1000.0 * sh
        color = PALETTE[i % len(PALETTE)]

        canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)

        tx = min(max(x1 + 4, 4), sw - 8)
        ty = max(y1 - 6, 10)
        anchor = "sw"
        if ty <= 12:
            ty = y1 + 6
            anchor = "nw"

        tid = canvas.create_text(tx, ty, text=label, fill=color, font=font,
                                 anchor=anchor, width=360, justify="left")
        bx1, by1, bx2, by2 = canvas.bbox(tid)
        rid = canvas.create_rectangle(bx1 - 4, by1 - 2, bx2 + 4, by2 + 2,
                                      fill=CFG["bg_color"], outline=color)
        canvas.tag_raise(tid, rid)
        drawn += 1

    overlay_win.lift()
    overlay_win.update()
    make_click_through(overlay_win)
    print(f"[overlay] annotate: {drawn} region(s) drawn")


def hide_overlay():
    global overlay_win
    if overlay_win is not None:
        overlay_win.destroy()
        overlay_win = None
    print("[overlay] hidden")


def poll_queue():
    global state
    try:
        while True:
            action, payload = ui_queue.get_nowait()
            if action == "show_box":
                show_box_overlay(payload)
                state = STATE_SHOWING
            elif action == "show_annotate":
                show_annotations(payload)
                state = STATE_SHOWING
            elif action == "hide":
                hide_overlay()
    except queue.Empty:
        pass
    root.after(100, poll_queue)


def capture_screenshot():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def ask_ai(image_bytes, prompt):
    global current_key_idx, current_model_idx, model
    last_err = None
    for _ in range(len(KEYS) * len(MODELS)):
        try:
            response = model.generate_content([
                {"mime_type": "image/png", "data": image_bytes},
                prompt,
            ])
            return response.text.strip(), getattr(response, "usage_metadata", None)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if not any(s in msg for s in ["quota", "429", "resourceexhausted",
                                          "rate limit", "rate_limit", "404", "not found"]):
                break
            current_key_idx += 1
            if current_key_idx >= len(KEYS):
                current_key_idx = 0
                current_model_idx = (current_model_idx + 1) % len(MODELS)
            model = configure_model()
            print(f"[keys] retry key #{current_key_idx + 1}/{len(KEYS)} "
                  f"model {MODELS[current_model_idx]}")
    return f"Error: {last_err}", None


def parse_annotations(raw):
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?", "", txt).strip()
    txt = re.sub(r"```$", "", txt).strip()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", txt, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, list) else None


def log_metrics(capture_ms, api_ms, total_ms, usage, mode):
    is_new = not os.path.exists(METRICS_PATH)
    tok = lambda a: getattr(usage, a, "") if usage else ""
    with open(METRICS_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp", "mode", "capture_ms", "api_ms", "total_ms",
                        "prompt_tokens", "output_tokens", "total_tokens", "key_index"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), mode,
                    f"{capture_ms:.1f}", f"{api_ms:.1f}", f"{total_ms:.1f}",
                    tok("prompt_token_count"), tok("candidates_token_count"),
                    tok("total_token_count"), current_key_idx])
    print(f"[metrics] {mode} | capture {capture_ms:.0f}ms | api {api_ms:.0f}ms | "
          f"total {total_ms:.0f}ms | tokens {tok('total_token_count')} "
          f"| key #{current_key_idx + 1}")


def pipeline():
    global state
    mode = CFG.get("mode", "box")
    prompt = CFG["annotate_prompt"] if mode == "annotate" else CFG["prompt"]

    t0 = time.perf_counter()
    img = capture_screenshot()
    t1 = time.perf_counter()
    answer, usage = ask_ai(img, prompt)
    t2 = time.perf_counter()

    log_metrics((t1 - t0) * 1000, (t2 - t1) * 1000, (t2 - t0) * 1000, usage, mode)

    if mode == "annotate" and not answer.startswith("Error:"):
        items = parse_annotations(answer)
        if items:
            ui_queue.put(("show_annotate", items))
            return
        print("[annotate] could not parse JSON, falling back to box")
    ui_queue.put(("show_box", answer))


def on_press(key):
    global state
    if key != HOTKEY:
        return
    with state_lock:
        if state == STATE_IDLE:
            state = STATE_BUSY
            threading.Thread(target=pipeline, daemon=True).start()
        elif state == STATE_SHOWING:
            state = STATE_IDLE
            ui_queue.put(("hide", None))


listener = keyboard.Listener(on_press=on_press)
listener.start()

print(f"Running | mode={CFG.get('mode')} | {len(KEYS)} key(s), {len(MODELS)} model(s)")
print(f"Press {CFG['hotkey']}: generate -> hide -> generate again")
print(f"Metrics -> {METRICS_PATH}")
root.after(100, poll_queue)
root.mainloop()
