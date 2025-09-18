# utils/cadastros/empresa.py
import tkinter as tk
from tkinter import ttk, messagebox
import re

def _upper_text(s: str) -> str: return (s or "").upper()
def _lower_email(s: str) -> str: return (s or "").lower()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def _digits(s: str, limit: int) -> str: return re.sub(r"\D", "", s or "")[:limit]
def _uf_mask(s: str) -> str: return re.sub(r"[^A-Za-z]", "", s or "").upper()[:2]

def _mask_cnpj(s: str) -> str:
    d = _digits(s, 14)
    a,b,c,d1,e = d[:2], d[2:5], d[5:8], d[8:12], d[12:14]
    out = a
    if b:  out += "." + b
    if c:  out += "." + c
    if d1: out += "/" + d1
    if e:  out += "-" + e
    return out

def _mask_cep_oldstyle(s: str) -> str:
    d = _digits(s, 8)
    if len(d) <= 2: return d
    if len(d) <= 5: return f"{d[:2]}.{d[2:]}"
    return f"{d[:2]}.{d[2:5]}-{d[5:]}"

def _mask_tel_var(s: str) -> str:
    d = re.sub(r"\D", "", s or "")[:11]
    if   not d:          return ""
    if len(d) <= 2:      return f"({d}"
    if len(d) <= 6:      return f"({d[:2]}) {d[2:]}"
    if len(d) <= 10:     return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return                f"({d[:2]}) {d[2:7]}-{d[7:]}"

def _index_after_n_digits(text: str, n: int) -> int:
    count = 0
    for i,ch in enumerate(text):
        if ch.isdigit():
            count += 1
            if count == n:
                return i+1
    return len(text)

def _bind_mask_keep_caret(entry: ttk.Entry, var: tk.StringVar, formatter):
    guard = {"on": False}
    def on_keyrelease(_=None):
        if guard["on"]: return
        guard["on"] = True
        try:
            raw = var.get()
            idx = entry.index("insert")
            digits_before = sum(1 for ch in raw[:idx] if ch.isdigit())
            masked = formatter(raw)
            if masked != raw:
                var.set(masked)
                entry.icursor(_index_after_n_digits(masked, digits_before))
        finally:
            guard["on"] = False
    entry.bind("<KeyRelease>", on_keyrelease)

def _bind_simple_case(entry: ttk.Entry, var: tk.StringVar, transform):
    guard = {"on": False}
    def on_keyrelease(_=None):
        if guard["on"]: return
        guard["on"] = True
        try:
            s = var.get()
            idx = entry.index("insert")
            new = transform(s)
            if new != s:
                var.set(new)
                entry.icursor(min(idx, len(new)))
        finally:
            guard["on"] = False
    entry.bind("<KeyRelease>", on_keyrelease)

def _linha(frm, r, label, var, width=38):
    ttk.Label(frm, text=label, width=24, anchor="e").grid(row=r, column=0, padx=6, pady=4, sticky="e")
    ent = ttk.Entry(frm, textvariable=var, width=width)
    ent.grid(row=r, column=1, padx=6, pady=4, sticky="w")
    return ent

def build_aba_empresa(nb, state):
    frm = ttk.Frame(nb)
    frm.columnconfigure(1, weight=1)

    v_razao = state.var("razao_social")
    e_razao = _linha(frm, 0, "Razão Social", v_razao)
    _bind_simple_case(e_razao, v_razao, _upper_text)
    v_razao.set(_upper_text(v_razao.get()))

    v_cnpj = state.var("cnpj")
    e_cnpj = _linha(frm, 1, "CNPJ", v_cnpj)
    _bind_mask_keep_caret(e_cnpj, v_cnpj, _mask_cnpj)
    v_cnpj.set(_mask_cnpj(v_cnpj.get()))

    v_end = state.var("endereco")
    e_end = _linha(frm, 2, "Endereço", v_end, width=50)
    _bind_simple_case(e_end, v_end, _upper_text)
    v_end.set(_upper_text(v_end.get()))

    v_cid = state.var("cidade")
    e_cid = _linha(frm, 3, "Cidade", v_cid)
    _bind_simple_case(e_cid, v_cid, _upper_text)
    v_cid.set(_upper_text(v_cid.get()))

    v_uf = state.var("uf")
    e_uf = _linha(frm, 4, "UF", v_uf, width=6)
    _bind_simple_case(e_uf, v_uf, _uf_mask)
    v_uf.set(_uf_mask(v_uf.get()))

    v_cep = state.var("cep")
    e_cep = _linha(frm, 5, "CEP", v_cep)
    _bind_mask_keep_caret(e_cep, v_cep, _mask_cep_oldstyle)
    v_cep.set(_mask_cep_oldstyle(v_cep.get()))

    v_tel = state.var("telefone")
    e_tel = _linha(frm, 6, "Telefone", v_tel)
    _bind_mask_keep_caret(e_tel, v_tel, _mask_tel_var)
    v_tel.set(_mask_tel_var(v_tel.get()))

    v_email = state.var("email")
    e_email = _linha(frm, 7, "E-mail", v_email, width=40)
    _bind_simple_case(e_email, v_email, _lower_email)
    def _validate_email_on_blur(_=None):
        s = (v_email.get() or "").strip().lower()
        if s and not EMAIL_RE.match(s):
            messagebox.showwarning("E-mail", "Formato de e-mail aparentemente inválido.", parent=frm.winfo_toplevel())
            e_email.after(1, lambda: (e_email.focus_set(), e_email.icursor("end")))
    e_email.bind("<FocusOut>", _validate_email_on_blur)

    return frm
