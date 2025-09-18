# utils/ui_envio/common.py
import tkinter as tk
from tkinter import ttk

def html_escape(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _add_page(container: ttk.Notebook, titulo_base: str):
    """Cria/seleciona uma aba (com registro para evitar duplicatas)."""
    titulo = (titulo_base[:20] if len(titulo_base)>20 else titulo_base.ljust(20, " "))
    if not hasattr(container, "_tab_registry"):
        container._tab_registry = {}
    if titulo_base in container._tab_registry:
        container.select(container._tab_registry[titulo_base])
        return container._tab_registry[titulo_base]
    page = ttk.Frame(container)
    container.add(page, text=titulo)
    container._tab_registry[titulo_base] = page
    container.select(page)

    def _close(*_):
        try:
            container.forget(page)
        finally:
            container._tab_registry.pop(titulo_base, None)
            try:
                container.after(0, lambda: container.event_generate("<<NotebookTabChanged>>"))
            except Exception:
                pass
    page._nasapay_close = _close
    return page

def _center_on_parent(top: tk.Toplevel, parent):
    """Centraliza qualquer popup/top-level no pai."""
    try:
        top.update_idletasks()
        if parent is None:
            parent = top.winfo_toplevel()
        px = parent.winfo_rootx(); py = parent.winfo_rooty()
        pw = parent.winfo_width(); ph = parent.winfo_height()
        tw = top.winfo_width(); th = top.winfo_height()
        x = px + (pw - tw)//2; y = py + (ph - th)//2
        top.geometry(f"+{max(0,x)}+{max(0,y)}")
        top.transient(parent); top.grab_set(); top.focus_force()
    except Exception:
        try: top.grab_set()
        except Exception: pass
