# utils/cadastros/cobranca.py
import tkinter as tk
from tkinter import ttk

# ------------------- opções de espécie -------------------
_ESPECIES_DEFAULT = [
    "01 - Cheque (CH)",
    "02 - Duplicata Mercantil (DM)",
    "03 - Duplicata Mercantil Indicação (DMI)",
    "04 - Duplicata de Serviço (DS)",
    "05 - Duplicata de Serviço Indicação (DSI)",
    "06 - Duplicata Rural (DR)",
    "07 - Letra de Câmbio (LC)",
    "08 - Nota de Crédito Comercial (NCC)",
    "09 - Nota de Crédito Exportação (NCE)",
    "10 - Nota de Crédito Industrial (NCI)",
    "11 - Nota de Crédito Rural (NCR)",
    "12 - Nota Promissória (NP)",
    "13 - Nota Promissória Rural (NPR)",
    "14 - Triplicata Mercantil (TM)",
    "15 - Triplicata de Serviço (TS)",
    "16 - Nota de Seguro (NS)",
    "17 - Recibo (RC)",
    "18 - Bloqueto (FAT)",
    "19 - Nota de Débito (ND)",
    "20 - Apólice de Seguro (AP)",
    "21 - Mensalidade Escolar (ME)",
    "22 - Parcela de Consórcio (PC)",
    "23 - Nota Fiscal (PF)",
    "24 - Documento de Dívida (DD)",
    "25 - Cédula de Produto Rural",
    "26 - Warrant",
    "27 - Dívida Ativa de Estado",
    "28 - Dívida Ativa de Município",
    "29 - Dívida Ativa da União",
    "30 - Encargos condominiais",
    "31 - Cartão de Crédito",
    "32 - Boleto proposta",
    "99 - Outros",
]
_DEFAULT_ESPECIE = "02 - Duplicata Mercantil (DM)"


def _get_especies(state) -> list[str]:
    """Tenta pegar via state.choices('especies'); se não existir, usa a lista padrão."""
    try:
        if hasattr(state, "choices"):
            lst = state.choices("especies")
            if isinstance(lst, (list, tuple)) and lst:
                return list(lst)
    except Exception:
        pass
    return _ESPECIES_DEFAULT


# ------------------- helpers: máscara de porcentagem -------------------
def _format_percent_from_raw(raw: str) -> str:
    if not raw:
        return "0,00"
    v = int(raw) / 100.0
    return f"{v:.2f}".replace(".", ",")


def _attach_percent_mask(entry: ttk.Entry, var: tk.StringVar):
    """
    Mantém um 'raw' de até 3 dígitos.
    Digite: 2 -> 0,02 | 20 -> 0,20 | 200 -> 2,00
    Backspace remove do final. Cursor sempre no fim.
    """
    digits = "".join(ch for ch in (var.get() or "") if ch.isdigit())
    entry._raw = "" if digits in ("", "0", "00", "000") else digits[:3]
    var.set(_format_percent_from_raw(entry._raw))

    def on_keypress(ev):
        if ev.keysym in (
            "Tab","ISO_Left_Tab","Left","Right","Up","Down","Home","End",
            "Shift_L","Shift_R","Control_L","Control_R"
        ):
            return
        if ev.keysym in ("BackSpace","Delete"):
            entry._raw = entry._raw[:-1]
            var.set(_format_percent_from_raw(entry._raw))
            entry.icursor("end")
            return "break"
        ch = ev.char
        if ch and ch.isdigit():
            if len(entry._raw) < 3:
                entry._raw += ch
                var.set(_format_percent_from_raw(entry._raw))
                entry.icursor("end")
            return "break"
        return "break"

    entry.bind("<KeyPress>", on_keypress)


# ------------------- UI -------------------
def build_aba_cobranca(nb, state):
    frm = ttk.Frame(nb)
    frm.columnconfigure(1, weight=1)

    def _linha(r, label, var, width=24):
        ttk.Label(frm, text=label, width=24, anchor="e").grid(
            row=r, column=0, padx=6, pady=4, sticky="e"
        )
        e = ttk.Entry(frm, textvariable=var, width=width)
        e.grid(row=r, column=1, padx=6, pady=4, sticky="w")
        return e

    # Espécie (combo)
    v_esp = state.var("especie")
    ttk.Label(frm, text="Espécie do Título", width=24, anchor="e").grid(
        row=0, column=0, padx=6, pady=4, sticky="e"
    )
    especies = _get_especies(state)
    cb = ttk.Combobox(
        frm, textvariable=v_esp, values=especies, width=40, state="readonly"
    )
    cb.grid(row=0, column=1, padx=6, pady=4, sticky="w")

    # define default se vier vazio
    if not (v_esp.get() or "").strip():
        v_esp.set(_DEFAULT_ESPECIE)
    # se o valor atual existir na lista, seleciona no combo
    try:
        idx = especies.index(v_esp.get())
        cb.current(idx)
    except ValueError:
        # se não estiver na lista (ex.: valor antigo), mantém no var e deixa combo sem seleção
        pass

    # Multa (%)
    v_multa = state.var("multa")
    e_multa = _linha(1, "Multa (%)", v_multa, width=12)
    _attach_percent_mask(e_multa, v_multa)

    # Juros (% a.d.)
    v_juros = state.var("juros")
    e_juros = _linha(2, "Juros (% a.d.)", v_juros, width=12)
    _attach_percent_mask(e_juros, v_juros)

    # Mensagens (força MAIÚSCULAS)
    def _bind_upper(e: ttk.Entry, v: tk.StringVar):
        guard = {"on": False}

        def on_key(_=None):
            if guard["on"]:
                return
            guard["on"] = True
            try:
                s = v.get()
                idx = e.index("insert")
                up = (s or "").upper()
                if up != s:
                    v.set(up)
                    e.icursor(min(idx, len(up)))
            finally:
                guard["on"] = False

        e.bind("<KeyRelease>", on_key)

    v_m1 = state.var("instrucao1")
    v_m2 = state.var("instrucao2")
    v_m3 = state.var("instrucao3")

    e_m1 = _linha(3, "Mensagem 1", v_m1, width=60); _bind_upper(e_m1, v_m1)
    e_m2 = _linha(4, "Mensagem 2", v_m2, width=60); _bind_upper(e_m2, v_m2)
    e_m3 = _linha(5, "Mensagem 3", v_m3, width=60); _bind_upper(e_m3, v_m3)

    return frm
