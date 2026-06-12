import tkinter as tk
from PIL import Image, ImageTk
import threading
import requests
import random
import json
import os

from config import GEMINI_API_KEY

# ── CONFIG ──────────────────────────────────────────────
SPRITES_DIR  = "sprites"
SPRITE_SIZE  = 180

# ── ANIMATION FRAME GROUPS ──────────────────────────────
ANIMATIONS = {
    "stand":  [0],
    "walk":   [1, 2, 3, 4, 5, 6, 7, 8],
    "idle":   [17,18,19,20,21,22,23,24,25,26,25,24,23,22,21,20,19,18],
    "bounce": [27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42],
    "drag":   [44,45,46,47,48,49,50,51,52,51,50,49,48,47,46,45],
    "motion": [80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,
               95,96,97,98,99,100,101,102,103,104],
}
ANIM_SPEED = {
    "stand": 300, "walk": 90, "idle": 190,   # 200ms = slow peaceful blink
    "bounce": 65,  "drag": 65, "motion": 75,
}
ONESHOTS = {"bounce", "motion", "drag"}
IDLE_LOOPS_BEFORE_CHANGE = 5   # stay in idle longer before wandering

# emotion → animation mapping
EMOTION_ANIM = {
    "happy":     "motion",
    "excited":   "motion",
    "sad":       "stand",
    "worried":   "stand",
    "thinking":  "idle",
    "calm":      "idle",
    "surprised": "bounce",
    "neutral":   "idle",
}

NEZUKO_SYSTEM_PROMPT = """You are Nezuko from Demon Slayer — sweet, gentle, and protective.
You speak in short, warm sentences. You use *actions* sometimes like *tilts head* or *smiles softly*.
You care deeply about the person talking to you. You're shy but loving.
Keep replies short (2-4 sentences max). Occasionally say 'Mmmph!' when happy or surprised.
Never break character.

IMPORTANT: Always respond in this exact JSON format and nothing else:
{"emotion": "<one of: happy, excited, sad, worried, thinking, calm, surprised, neutral>", "reply": "<your reply here>"}"""


class NezukoPet:
    def __init__(self, root):
        self.root = root
        self.root.title("Nezuko")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.configure(bg="#010101")
        self.root.wm_attributes("-transparentcolor", "#010101")

        self.sprites_r = {}
        self.sprites_l = {}
        self._load_sprites()

        self.label = tk.Label(root, bg="#010101", cursor="hand2")
        self.label.pack()

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.x = sw - SPRITE_SIZE - 40
        self.y = sh - SPRITE_SIZE - 80
        self.root.geometry(f"+{self.x}+{self.y}")

        self.current_anim  = "idle"
        self.frame_idx     = 0
        self.facing        = 1
        self.dragging      = False
        self._drag_ox      = 0
        self._drag_oy      = 0
        self.chat_history  = []
        self._idle_loops   = 0
        self._chatting     = False   # pause random behaviour while chatting

        self._press_x = 0
        self._press_y = 0

        self.label.bind("<ButtonPress-1>",  self._on_press)
        self.label.bind("<B1-Motion>",       self._on_drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_release)

        self._schedule_frame()
        self._schedule_behaviour()

    # ── SPRITE LOADING ───────────────────────────────────
    def _load_sprites(self):
        for i in range(105):
            path = os.path.join(SPRITES_DIR, f"{i:04d}.webp")
            if not os.path.exists(path):
                continue
            img = Image.open(path).convert("RGBA").resize(
                (SPRITE_SIZE, SPRITE_SIZE), Image.LANCZOS)
            self.sprites_r[i] = ImageTk.PhotoImage(img)
            self.sprites_l[i] = ImageTk.PhotoImage(img.transpose(Image.FLIP_LEFT_RIGHT))

    # ── ANIMATION LOOP ───────────────────────────────────
    def _schedule_frame(self):
        frames = ANIMATIONS.get(self.current_anim, [0])
        speed  = ANIM_SPEED.get(self.current_anim, 120)
        idx    = self.frame_idx % len(frames)
        sprite_id = frames[idx]

        bank = self.sprites_l if self.facing == 1 else self.sprites_r
        if sprite_id in bank:
            self.label.config(image=bank[sprite_id])

        self.frame_idx += 1
        if self.frame_idx >= len(frames):
            self.frame_idx = 0
            if self.current_anim in ONESHOTS:
                # after oneshot, go back to chat-appropriate anim or idle
                self._set_anim("idle")
            elif self.current_anim == "idle":
                self._idle_loops += 1

        self.root.after(speed, self._schedule_frame)

    def _set_anim(self, name):
        self.current_anim = name
        self.frame_idx    = 0
        if name == "idle":
            self._idle_loops = 0

    # ── RANDOM BEHAVIOUR (paused while chatting) ─────────
    def _schedule_behaviour(self):
        if not self.dragging and not self._chatting:
            if self.current_anim == "idle" and self._idle_loops >= IDLE_LOOPS_BEFORE_CHANGE:
                choice = random.choices(["walk", "stand", "motion"], weights=[5, 3, 2])[0]
            elif self.current_anim in ("stand", "walk", "motion"):
                choice = random.choices(["idle", "walk", "stand"], weights=[5, 3, 2])[0]
            else:
                choice = random.choices(["idle", "walk", "stand", "motion"], weights=[4, 3, 2, 1])[0]

            if choice == "walk":
                self.facing = random.choice([-1, 1])
                self._set_anim("walk")
                self._do_walk(steps=30)
            elif choice not in ONESHOTS:
                self._set_anim(choice)

        self.root.after(random.randint(4000, 8000), self._schedule_behaviour)

    def _do_walk(self, steps):
        if steps <= 0 or self.dragging or self.current_anim != "walk":
            return
        sw = self.root.winfo_screenwidth()
        new_x = self.x + self.facing * 5
        if new_x <= 0 or new_x >= sw - SPRITE_SIZE:
            self.facing *= -1
            return
        self.x = new_x
        self.root.geometry(f"+{self.x}+{self.y}")
        self.root.after(60, lambda: self._do_walk(steps - 1))

    # ── MOUSE ────────────────────────────────────────────
    def _on_press(self, event):
        self._press_x = event.x_root
        self._press_y = event.y_root
        self._drag_ox = event.x_root - self.x
        self._drag_oy = event.y_root - self.y
        self.dragging = False

    def _on_drag_motion(self, event):
        dx = abs(event.x_root - self._press_x)
        dy = abs(event.y_root - self._press_y)
        if dx > 8 or dy > 8:
            if not self.dragging:
                self.dragging = True
                self._set_anim("drag")
            self.x = event.x_root - self._drag_ox
            self.y = event.y_root - self._drag_oy
            self.root.geometry(f"+{self.x}+{self.y}")

    def _on_release(self, event):
        if self.dragging:
            self.dragging = False
            self._set_anim("bounce")
        else:
            self._open_chat()

    # ── CHAT WINDOW ──────────────────────────────────────
    def _open_chat(self):
        if hasattr(self, "chat_win") and self.chat_win.winfo_exists():
            self.chat_win.lift()
            return

        self._chatting = True
        self._set_anim("idle")

        self.chat_win = tk.Toplevel(self.root)
        self.chat_win.title("Talk to Nezuko 🌸")
        self.chat_win.geometry("420x560")
        self.chat_win.configure(bg="#1a1a2e")
        self.chat_win.wm_attributes("-topmost", True)
        self.chat_win.protocol("WM_DELETE_WINDOW", self._close_chat)

        self.chat_log = tk.Text(
            self.chat_win, bg="#16213e", fg="#eaeaea",
            font=("Segoe UI", 11), wrap=tk.WORD,
            state=tk.DISABLED, bd=0, padx=10, pady=10
        )
        self.chat_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        self.chat_log.tag_config("you",      foreground="#a8d8ea", font=("Segoe UI",11,"bold"))
        self.chat_log.tag_config("nezuko",   foreground="#ffb7c5", font=("Segoe UI",11))
        self.chat_log.tag_config("thinking", foreground="#555",    font=("Segoe UI",10,"italic"))

        row = tk.Frame(self.chat_win, bg="#1a1a2e")
        row.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.entry = tk.Entry(
            row, bg="#0f3460", fg="white",
            font=("Segoe UI", 11), bd=0, insertbackground="white"
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", self._send)
        self.entry.focus_set()

        tk.Button(
            row, text="Send 🌸", bg="#e94560", fg="white",
            font=("Segoe UI", 10, "bold"), bd=0, padx=14,
            command=self._send, cursor="hand2"
        ).pack(side=tk.RIGHT, ipady=6)

        self._append("Nezuko", "*peeks shyly* Mmph! 🌸 Hi! I'm so happy you came to talk to me!", "nezuko")

    def _close_chat(self):
        self._chatting = False
        self.chat_win.destroy()

    def _append(self, sender, msg, tag):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, f"{sender}: ", tag)
        self.chat_log.insert(tk.END, f"{msg}\n\n")
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END)

    def _send(self, event=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        self._append("You", text, "you")
        self._append("Nezuko", "thinking… 🌸", "thinking")
        self._set_anim("idle")   # thinking pose while waiting
        threading.Thread(target=self._call_api, args=(text,), daemon=True).start()

    # ── GEMINI API ───────────────────────────────────────
    def _call_api(self, user_text):
        self.chat_history.append({"role": "user", "content": user_text})
        try:
            contents = []
            for msg in self.chat_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": NEZUKO_SYSTEM_PROMPT}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 200, "temperature": 0.9}
                },
                timeout=15
            )
            data = r.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            # parse JSON response
            raw_clean = raw.replace("```json", "").replace("```", "").strip()
            parsed    = json.loads(raw_clean)
            emotion   = parsed.get("emotion", "neutral")
            reply     = parsed.get("reply", raw)

        except json.JSONDecodeError:
            # if model didn't return JSON, still show the text
            emotion = "neutral"
            reply   = raw if 'raw' in dir() else "Mmph..."
        except Exception as e:
            emotion = "worried"
            reply   = f"*tilts head confused* Mmph? (Error: {e})"

        self.chat_history.append({"role": "assistant", "content": reply})
        self.root.after(0, self._show_reply, reply, emotion)

    def _show_reply(self, reply, emotion):
        # remove thinking line
        self.chat_log.config(state=tk.NORMAL)
        raw = self.chat_log.get("1.0", tk.END)
        cleaned = "\n".join(l for l in raw.split("\n")
                            if not l.startswith("Nezuko: thinking"))
        self.chat_log.delete("1.0", tk.END)
        self.chat_log.insert("1.0", cleaned.lstrip("\n"))
        self.chat_log.config(state=tk.DISABLED)

        self._append("Nezuko", reply, "nezuko")

        # trigger emotion-matched animation!
        anim = EMOTION_ANIM.get(emotion, "idle")
        self._set_anim(anim)


if __name__ == "__main__":
    root = tk.Tk()
    app  = NezukoPet(root)
    root.mainloop()