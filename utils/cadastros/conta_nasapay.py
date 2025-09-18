# utils/cadastros/conta_nasapay.py
import tkinter as tk
from tkinter import ttk, messagebox
import re

def _digits(s, limit=None):
    s = re.sub(r"\D", "", s or "")
    return s[:limit] if limit else s

def _bind_digits(entry: ttk.Entry, var: tk.StringVar, limit: int):
    """Permite só dígitos até `limit`, mantendo posição do cursor."""
    guard = {"on": False}
    def on_key(_=None):
        if guard["on"]:
            return
        guard["on"] = True
        try:
            s = var.get()
            idx = entry.index("insert")
            before = sum(1 for ch in s[:idx] if ch.isdigit())
            raw = _digits(s, limit)
            if raw != s:
                var.set(raw)
                cnt = 0; new_idx = 0
                for i, ch in enumerate(var.get()):
                    if ch.isdigit():
                        cnt += 1
                    new_idx = i + 1
                    if cnt >= before:
                        break
                entry.icursor(new_idx)
        finally:
            guard["on"] = False
    entry.bind("<KeyRelease>", on_key)

def _pad_zeros_on_blur(entry: ttk.Entry, var: tk.StringVar, width: int):
    def on_blur(_=None):
        d = _digits(var.get(), width)
        var.set(d.zfill(width) if d else "")
    entry.bind("<FocusOut>", on_blur)

def build_aba_conta(parent, state):
    frm = ttk.Frame(parent)
    frm.columnconfigure(1, weight=1)

    def _linha(r, label, var, width):
        ttk.Label(frm, text=label, width=24, anchor="e").grid(row=r, column=0, padx=6, pady=4, sticky="e")
        e = ttk.Entry(frm, textvariable=var, width=width)
        e.grid(row=r, column=1, padx=6, pady=4, sticky="w")
        return e

    v_ag = state.var("agencia")
    e_ag = _linha(0, "Agência", v_ag, 10)
    _bind_digits(e_ag, v_ag, 4)
    _pad_zeros_on_blur(e_ag, v_ag, 4)

    v_cc = state.var("conta")
    e_cc = _linha(1, "Conta", v_cc, 12)
    _bind_digits(e_cc, v_cc, 7)
    _pad_zeros_on_blur(e_cc, v_cc, 7)

    v_dv = state.var("digito")
    e_dv = _linha(2, "Dígito", v_dv, 4)
    _bind_digits(e_dv, v_dv, 1)

    v_cart = state.var("carteira")
    e_cart = _linha(3, "Carteira", v_cart, 6)
    _bind_digits(e_cart, v_cart, 2)
    _pad_zeros_on_blur(e_cart, v_cart, 2)

    v_ced = state.var("codigo_cedente")
    e_ced = _linha(4, "Código do Cedente", v_ced, 12)
    _bind_digits(e_ced, v_ced, 7)
    def _ced_blur(_=None):
        d = _digits(v_ced.get(), 7)
        v_ced.set(d)
        if d and len(d) != 7:
            messagebox.showwarning("Código do Cedente", "Preencha exatamente 7 números.", parent=frm.winfo_toplevel())
            e_ced.after(1, lambda: (e_ced.focus_set(), e_ced.icursor("end")))
    e_ced.bind("<FocusOut>", _ced_blur)

    return frm

def build_aba_nasapay(parent, state):
    # Mantém compatibilidade com o nome esperado
    return build_aba_conta(parent, state)
