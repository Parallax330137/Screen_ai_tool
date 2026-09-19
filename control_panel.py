import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SCRIPT_PATH = os.path.join(BASE_DIR, "screen_ai.py")

DEFAULTS = {
    "hotkey": "`",
    "gemini_api_key": "",
    "gemini_api_keys": [],
    "model_name": "gemini-3.6-flash",
    "model_names": ["gemini-3.6-flash"],
    "prompt": "Answer what's on screen concisely.",
    "mode": "box",
    "annotate_prompt": "",
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

POSITIONS = ["bottom-center", "top-center", "bottom-left", "bottom-right",
             "top-left", "top-right", "center"]


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    with open(CONFIG_PATH) as f:
        cfg = dict(DEFAULTS)
        cfg.update(json.load(f))
        return cfg


class Panel:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        root.title("Screen AI - Control Panel")
        root.geometry("640x680")

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_keys = ttk.Frame(nb)
        self.tab_prompt = ttk.Frame(nb)
        self.tab_look = ttk.Frame(nb)
        nb.add(self.tab_keys, text="API Keys & Models")
        nb.add(self.tab_prompt, text="Prompt & Mode")
        nb.add(self.tab_look, text="Appearance")

        self.build_keys_tab()
        self.build_prompt_tab()
        self.build_look_tab()

        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="Save", command=self.save).pack(side="left")
        ttk.Button(bar, text="Save & Run", command=self.save_and_run).pack(side="left", padx=6)
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="left", padx=10)

    # ---------- keys tab ----------
    def build_keys_tab(self):
        f = self.tab_keys
        ttk.Label(f, text="API keys (one per row, add as many as you want):").pack(anchor="w", pady=(8, 2))

        wrap = ttk.Frame(f)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, height=230, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        self.keys_frame = ttk.Frame(canvas)
        self.keys_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.keys_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.key_rows = []
        existing = self.cfg.get("gemini_api_keys") or []
        if not existing and self.cfg.get("gemini_api_key"):
            existing = [self.cfg["gemini_api_key"]]
        for k in existing:
            self.add_key_row(k)
        if not existing:
            self.add_key_row("")

        ttk.Button(f, text="+ Add key", command=lambda: self.add_key_row("")).pack(anchor="w", pady=6)

        ttk.Separator(f).pack(fill="x", pady=8)
        ttk.Label(f, text="Models to try, in order (one per line):").pack(anchor="w")
        self.models_text = tk.Text(f, height=7, wrap="none")
        self.models_text.pack(fill="x", pady=4)
        models = self.cfg.get("model_names") or [self.cfg.get("model_name", "")]
        self.models_text.insert("1.0", "\n".join(m for m in models if m))

    def add_key_row(self, value):
        row = ttk.Frame(self.keys_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=f"{len(self.key_rows) + 1}.", width=3).pack(side="left")
        e = ttk.Entry(row, width=58)
        e.pack(side="left", padx=4)
        e.insert(0, value)
        ttk.Button(row, text="x", width=3,
                   command=lambda: self.remove_key_row(row, e)).pack(side="left")
        self.key_rows.append((row, e))

    def remove_key_row(self, row, entry):
        self.key_rows = [(r, e) for (r, e) in self.key_rows if e is not entry]
        row.destroy()
        for i, (r, _e) in enumerate(self.key_rows):
            r.winfo_children()[0].configure(text=f"{i + 1}.")

    # ---------- prompt tab ----------
    def build_prompt_tab(self):
        f = self.tab_prompt
        ttk.Label(f, text="Answer mode:").pack(anchor="w", pady=(8, 2))
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "box"))
        ttk.Radiobutton(f, text="Box  -  one answer box on screen",
                        variable=self.mode_var, value="box").pack(anchor="w")
        ttk.Radiobutton(f, text="Annotate  -  answers drawn next to what they describe",
                        variable=self.mode_var, value="annotate").pack(anchor="w")

        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Label(f, text="Prompt (box mode):").pack(anchor="w")
        self.prompt_text = tk.Text(f, height=7, wrap="word")
        self.prompt_text.pack(fill="x", pady=4)
        self.prompt_text.insert("1.0", self.cfg.get("prompt", ""))

        ttk.Label(f, text="Prompt (annotate mode) - must ask for JSON box_2d + label:").pack(anchor="w", pady=(8, 0))
        self.ann_prompt_text = tk.Text(f, height=10, wrap="word")
        self.ann_prompt_text.pack(fill="x", pady=4)
        self.ann_prompt_text.insert("1.0", self.cfg.get("annotate_prompt", ""))

    # ---------- appearance tab ----------
    def build_look_tab(self):
        f = self.tab_look
        grid = ttk.Frame(f)
        grid.pack(fill="x", pady=10)

        self.vars = {}

        def field(label, key, row, width=22):
            ttk.Label(grid, text=label).grid(row=row, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(self.cfg.get(key, "")))
            ttk.Entry(grid, textvariable=v, width=width).grid(row=row, column=1, sticky="w", padx=6)
            self.vars[key] = v

        field("Hotkey", "hotkey", 0)
        field("Font family", "font_family", 1)
        field("Font size (box)", "font_size", 2)
        field("Font size (annotate)", "annotate_font_size", 3)
        field("Max width (px)", "max_width", 4)
        field("Margin (px)", "margin", 5)
        field("Corner radius", "corner_radius", 6)
        field("Background color", "bg_color", 7)
        field("Text color", "text_color", 8)
        field("Opacity 0.1-1.0", "alpha", 9)

        ttk.Label(grid, text="Position").grid(row=10, column=0, sticky="w", pady=3)
        self.pos_var = tk.StringVar(value=self.cfg.get("position", "bottom-center"))
        ttk.Combobox(grid, textvariable=self.pos_var, values=POSITIONS,
                     state="readonly", width=20).grid(row=10, column=1, sticky="w", padx=6)

    # ---------- save ----------
    def collect(self):
        keys = [e.get().strip() for _r, e in self.key_rows if e.get().strip()]
        if not keys:
            raise ValueError("Add at least one API key.")
        models = [m.strip() for m in self.models_text.get("1.0", "end").splitlines() if m.strip()]
        if not models:
            raise ValueError("Add at least one model name.")

        cfg = dict(self.cfg)
        cfg["gemini_api_keys"] = keys
        cfg["gemini_api_key"] = keys[0]
        cfg["model_names"] = models
        cfg["model_name"] = models[0]
        cfg["mode"] = self.mode_var.get()
        cfg["prompt"] = self.prompt_text.get("1.0", "end").strip()
        cfg["annotate_prompt"] = self.ann_prompt_text.get("1.0", "end").strip()
        cfg["position"] = self.pos_var.get()

        ints = ["font_size", "annotate_font_size", "max_width", "margin", "corner_radius"]
        for k, v in self.vars.items():
            raw = v.get().strip()
            if k in ints:
                cfg[k] = int(float(raw))
            elif k == "alpha":
                cfg[k] = max(0.1, min(1.0, float(raw)))
            else:
                cfg[k] = raw
        return cfg

    def save(self):
        try:
            cfg = self.collect()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return False
        except Exception as e:
            messagebox.showerror("Invalid input", f"Check numeric fields: {e}")
            return False
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
        self.cfg = cfg
        self.status.configure(text=f"Saved - {len(cfg['gemini_api_keys'])} key(s)")
        return True

    def save_and_run(self):
        if not self.save():
            return
        if not os.path.exists(SCRIPT_PATH):
            messagebox.showerror("Not found", "screen_ai.py must be in the same folder.")
            return
        subprocess.Popen([sys.executable, SCRIPT_PATH], cwd=BASE_DIR)
        self.status.configure(text="Launched screen_ai.py")


if __name__ == "__main__":
    r = tk.Tk()
    Panel(r)
    r.mainloop()
