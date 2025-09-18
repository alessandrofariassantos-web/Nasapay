# === utils/boletos_bmp.py ===
from datetime import date, datetime

BANCO = "274"
MOEDA = "9"  # Real

def _limpa_valor_brl(valor_str: str) -> int:
    v = valor_str.replace(".", "").replace(",", ".")
    centavos = int(round(float(v) * 100))
    return max(0, centavos)

def fator_vencimento(dt_venc_str: str) -> str:
    d = datetime.strptime(dt_venc_str, "%d/%m/%Y").date()
    base_antiga = date(1997, 10, 7)
    base_nova   = date(2025, 2, 22)
    if d >= base_nova:
        fator = 1000 + (d - base_nova).days
    else:
        fator = (d - base_antiga).days
    return f"{fator:04d}"

def campo_livre(agencia: str, carteira: str, nosso_numero11: str, conta: str) -> str:
    ag = f"{int(agencia):04d}"
    cart = f"{int(carteira):02d}"
    nn = f"{int(nosso_numero11):011d}"
    cc = f"{int(conta):07d}"
    return f"{ag}{cart}{nn}{cc}0"  # 25 posições

def _mod10(num_str: str) -> str:
    soma, mult = 0, 2
    for ch in reversed(num_str):
        p = int(ch) * mult
        if p >= 10:
            p = (p // 10) + (p % 10)
        soma += p
        mult = 1 if mult == 2 else 2
    dv = (10 - (soma % 10)) % 10
    return str(dv)

def _mod11_barcode(num_str_43: str) -> str:
    pesos = [2,3,4,5,6,7,8,9]
    s, j = 0, 0
    for ch in reversed(num_str_43):
        s += int(ch) * pesos[j]
        j = (j + 1) % len(pesos)
    resto = s % 11
    dv = 11 - resto
    if dv in (0, 1) or dv > 9:
        dv = 1
    return str(dv)

def montar_codigo_barras(param, titulo) -> str:
    fator = fator_vencimento(titulo["vencimento"])
    valor = f"{_limpa_valor_brl(titulo['valor']):010d}"
    livre = campo_livre(param["agencia"], param["carteira"], titulo["nosso_numero"], param["conta"])
    base43 = BANCO + MOEDA + fator + valor + livre  # sem o DV geral
    dv = _mod11_barcode(base43)
    return BANCO + MOEDA + dv + fator + valor + livre  # 44 dígitos

def montar_linha_digitavel(codigo_barras_44: str) -> str:
    banco, moeda, dv_geral = codigo_barras_44[:3], codigo_barras_44[3], codigo_barras_44[4]
    fator, valor = codigo_barras_44[5:9], codigo_barras_44[9:19]
    livre = codigo_barras_44[19:44]  # 25
    c1_sem_dv = banco + moeda + livre[:5]
    c2_sem_dv =          livre[5:15]
    c3_sem_dv =          livre[15:25]
    c1 = f"{c1_sem_dv[:5]}.{c1_sem_dv[5:]}{_mod10(c1_sem_dv)}"
    c2 = f"{c2_sem_dv[:5]}.{c2_sem_dv[5:]}{_mod10(c2_sem_dv)}"
    c3 = f"{c3_sem_dv[:5]}.{c3_sem_dv[5:]}{_mod10(c3_sem_dv)}"
    c4 = dv_geral
    c5 = f"{fator}{valor}"
    return f"{c1} {c2} {c3} {c4} {c5}"

def dv_nosso_numero_base7(carteira: str, nosso_numero11: str) -> str:
    seq = f"{int(carteira):02d}{int(nosso_numero11):011d}"
    pesos = [2,3,4,5,6,7]
    s, j = 0, 0
    for ch in reversed(seq):
        s += int(ch) * pesos[j]
        j = (j + 1) % len(pesos)
    resto = s % 11
    if resto in (0, 1):
        return "0"
    return str(11 - resto)
