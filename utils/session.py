# utils/session.py
# Mantém o contexto da empresa atual durante a execução.

_current_empresa_id: int | None = None

def set_empresa_id(empresa_id: int | None) -> None:
    global _current_empresa_id
    _current_empresa_id = int(empresa_id) if empresa_id is not None else None

def get_empresa_id() -> int | None:
    return _current_empresa_id

def require_empresa_id() -> int:
    if _current_empresa_id is None:
        raise RuntimeError("Empresa não selecionada")
    return _current_empresa_id

# Compatibilidade: permitir session.empresa_id e session.empresa_id()
class _EmpresaIdProxy:
    def __call__(self):
        return get_empresa_id()
    def __int__(self):
        return int(get_empresa_id() or 0)
    def __repr__(self):
        v = get_empresa_id()
        return f"<empresa_id {v!r}>"
    def __str__(self):
        v = get_empresa_id()
        return "" if v is None else str(v)

# uso:
empresa_id = _EmpresaIdProxy()
