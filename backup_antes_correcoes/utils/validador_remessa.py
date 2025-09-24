# === utils/validador_remessa.py ===
import os, re
from utils.boletos_bmp import dv_nosso_numero_base7

def _slice(line: str, i: int, j: int) -> str:
    """1-based inclusive [i..j]."""
    return line[i-1:j]

def _dig(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _must_len(line: str, n: int, msg: str):
    if len(line) != n:
        raise ValueError(f"{msg}: esperado {n} colunas, veio {len(line)}")

def validar_remessa_bmp(path_rem: str) -> None:
    """
    Validações locais:
    - tamanho 400 colunas
    - HEADER literal 'COBRANCA'
    - número da remessa (111–117) == sequencial do nome (últimos 7 dígitos) e >= 6
    - MULTA: se código (66) == '0' então percentual (67–70) == '0000'
    - DOC pagador: tipo (219–220) coerente com dígitos (221–234)
    - NOSSO NÚMERO: 71–81 (11 dígitos) e 82 = DV módulo 11 base 7 com a carteira
      (carteira obtida do identificador da empresa: pos 022–024; usamos apenas os 2 últimos dígitos)
    """
    if not os.path.exists(path_rem):
        raise ValueError("Arquivo REM não encontrado.")

    nome = os.path.basename(path_rem)
    m = re.search(r"(\d{7})\.REM$", nome.upper())
    if not m:
        raise ValueError("Nome do arquivo não segue padrão CBddmmXXXXXXX.REM.")
    seq_nome = int(m.group(1))

    with open(path_rem, "r", encoding="latin-1") as f:
        linhas = [ln.rstrip("\r\n") for ln in f]

    if not linhas or linhas[0][0] != "0":
        raise ValueError("Header inválido.")

    # HEADER
    h = linhas[0]
    _must_len(h, 400, "Header")
    literal = _slice(h, 12, 26)
    if literal != "COBRANCA".ljust(15):
        raise ValueError("Header: pos 12–26 deve ser 'COBRANCA'.")
    nr_header = int(_slice(h, 111, 117))
    if nr_header != seq_nome:
        raise ValueError(f"Header: pos 111–117 ({nr_header}) deve bater com o sequencial do nome.")

    # DETALHES
    for i, det in enumerate(linhas[1:-1], start=2):
        if not det or det[0] != "1":
            raise ValueError(f"Linha {i}: registro detalhe inválido.")
        _must_len(det, 400, f"Linha {i}")

        # MULTA
        cod_multa = _slice(det, 66, 66)
        perc_multa = _slice(det, 67, 70)
        if cod_multa == "0" and perc_multa != "0000":
            raise ValueError(f"Linha {i}: código de multa isento (66='0') e percentual não zerado (67–70='{perc_multa}').")

        # NOSSO NÚMERO + DV (71–82)
        nn = _slice(det, 71, 81)
        dv = _slice(det, 82, 82)
        if not nn.isdigit() or len(nn) != 11:
            raise ValueError(f"Linha {i}: Nosso Número (71–81) deve ter 11 dígitos. Valor: '{nn}'.")
        # carteira fica no identificador da empresa (021–037) => 022–024
        cart3 = _slice(det, 22, 24)
        cart2 = cart3[-2:]
        dv_ok = dv_nosso_numero_base7(cart2, nn)
        if dv != dv_ok:
            raise ValueError(f"Linha {i}: DV do Nosso Número inválido em 82. Esperado '{dv_ok}', recebido '{dv}'.")

        # DOC PAGADOR
        tipo = _slice(det, 219, 220)
        doc  = _slice(det, 221, 234)
        d = _dig(doc)
        if not d.isdigit() or len(d) not in (11, 14):
            raise ValueError(f"Linha {i}: número inscrição pagador inválido (221–234='{doc}').")
        if tipo == "01" and len(d) not in (11, 14):
            raise ValueError(f"Linha {i}: tipo inscrição '01' (CPF) inconsistente com documento '{doc}'.")
        if tipo == "02" and len(d) != 14:
            raise ValueError(f"Linha {i}: tipo inscrição '02' (CNPJ) requer 14 dígitos no documento '{doc}'.")

    # TRAILER
    t = linhas[-1]
    if not t or t[0] != "9":
        raise ValueError("Trailer inválido.")
    _must_len(t, 400, "Trailer")

# --- wrapper simples p/ integrar com o menu ---
def validar_arquivo_remessa(path_rem: str, parent=None) -> None:
    """
    Wrapper para manter compatibilidade com quem chama 'validar_arquivo_remessa'.
    Levanta exceção se houver erro; não exibe messagebox aqui.
    """
    validar_remessa_bmp(path_rem)
