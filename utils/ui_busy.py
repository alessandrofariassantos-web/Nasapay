# utils/ui_busy.py
import tkinter as tk
from threading import Thread
import os
try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None  # opcional

class BusyOverlay:
    def __init__(self, parent, texto="Processando..."):
        self.parent = parent.winfo_toplevel()
        self.top = tk.Toplevel(self.parent)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)

        frm = tk.Frame(self.top, bg="#fff", bd=1, relief="solid"); frm.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frm, width=260, height=90, bd=0, highlightthickness=0, bg="#fff")
        self.canvas.pack(padx=18, pady=(16, 8))
        self._draw_logo()
        self.arc = self.canvas.create_arc(205, 22, 245, 62, start=0, extent=60, style="arc", width=3, outline="#2b6cb0")
        tk.Label(frm, text=texto, bg="#fff", fg="#333", font=("Segoe UI", 10)).pack(padx=18, pady=(0, 16))

        self.parent.update_idletasks()
        w = 300; h = 150
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - w)//2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - h)//2
        self.top.geometry(f"{w}x{h}+{max(x,0)}+{max(y,0)}")
        self._alive = True; self._angle = 0
        self._tick()

    def _draw_logo(self):
        path = r"C:\nasapay\logo_nasapay.png"
        if Image and ImageTk and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                prop = min(260/img.width, 90/img.height) * 0.9
                img = img.resize((int(img.width*prop), int(img.height*prop)))
                self._logo = ImageTk.PhotoImage(img)
                self.canvas.create_image(12, 45, image=self._logo, anchor="w")
                return
            except Exception:
                pass
        self.canvas.create_text(16, 45, text="nasapay", anchor="w", font=("Segoe UI", 26, "bold"), fill="#2b6cb0")

    def _tick(self):
        if not self._alive: return
        self._angle = (self._angle + 12) % 360
        self.canvas.itemconfigure(self.arc, start=self._angle)
        self.top.after(50, self._tick)

    def close(self):
        self._alive = False
        try: self.top.destroy()
        except Exception: pass

def run_with_busy(parent, text, func, on_done=None):
    """Executa func() em thread com overlay; chama on_done(result, error) no main thread."""
    ov = BusyOverlay(parent, text); parent.update_idletasks()
    def worker():
        res, err = None, None
        try: res = func()
        except Exception as e: err = e
        finally:
            def finish():
                try: ov.close()
                finally:
                    if callable(on_done): on_done(res, err)
            parent.after(0, finish)
    Thread(target=worker, daemon=True).start()
