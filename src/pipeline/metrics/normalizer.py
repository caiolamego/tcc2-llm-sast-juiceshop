"""Normalização compatível das três definições de F, sem escrita nas fontes."""
from pipeline.validation.conjunto_d import classificar
DEFS = ("sem_separacao", "marcador", "criterio")
ORDEM_TIERS = ["T0", "T2", "T3", "T4"]

def normalizar(l: dict) -> dict:
    """Garante F_<def>, classificacao_<def>, testes_falhos_d_<def> e incompleto_<def>."""
    l = dict(l)
    l.setdefault("condicao", "desenho")
    if "F_criterio" in l:
        for d in DEFS:
            l[f"incompleto_{d}"] = l.get(f"classificacao_{d}") in ("indeterminada_sast", "indeterminada_funcional")
        l.setdefault("testes_falhos_d_sem_separacao", [])
        return l
    # Linha antiga: reclassificacao a posteriori.
    l["F_sem_separacao"] = l["F"]
    l["testes_falhos_d_sem_separacao"] = []
    l["incompleto_sem_separacao"] = False
    c = classificar(l.get("testes_falhos_novos") or [])
    for d in ("marcador", "criterio"):
        l[f"testes_falhos_d_{d}"] = c[f"d_{d}"]
        if l["status_aplicacao"] != "aplicado":
            l[f"F_{d}"] = None
            l[f"incompleto_{d}"] = False
            continue
        tf = l.get("tier_falha")
        so_d = bool(l.get("testes_falhos_novos")) and not c[f"f_{d}"]
        if tf is None:
            l[f"F_{d}"], l[f"incompleto_{d}"] = 1, False
        elif so_d:
            # A camada que reprovou so tinha testes de D; se havia camadas
            # depois dela, elas nao rodaram.
            ultima = "T4"
            l[f"F_{d}"] = 1 if tf == ultima else None
            l[f"incompleto_{d}"] = tf != ultima
        else:
            l[f"F_{d}"], l[f"incompleto_{d}"] = 0, False
    for d in DEFS:
        f = l[f"F_{d}"]
        if l["status_aplicacao"] != "aplicado":
            l[f"classificacao_{d}"] = l["classificacao_final"]
        elif f is None:
            l[f"classificacao_{d}"] = "indeterminada"
        else:
            l[f"classificacao_{d}"] = ("aceita" if l["R"] and f and l["M"] else f"rejeitada:R{l['R']}F{f}M{l['M']}")
    return l



def normalizar_atual(original, caso, estrategia):
    """Enriquece uma cópia; inferências históricas ficam explicitamente marcadas."""
    import copy
    import re
    row = normalizar(copy.deepcopy(original))
    row['original'] = copy.deepcopy(original)
    row['classificacao_original'] = original.get('classificacao_final')
    row['estrategia_curta'] = estrategia
    row['inferencias_historicas'] = 'F_criterio' not in original
    for key in ('severidade', 'categoria_rag', 'classificacao_auditoria', 'owasp_2025', 'check_id'):
        row[key] = caso.get(key)
    from pipeline.metrics import exigir
    ids = caso.get('cwe_ids')
    if ids is None:
        values = caso.get('cwe') or []
        if isinstance(values,str):values=[values]
        exigir(isinstance(values,list),'Metadados CWE inválidos')
        ids = [m.group(0) for value in values
               if isinstance(value, str) and (m := re.match(r'CWE-\d+\b', value))]
    exigir(isinstance(ids,list) and all(isinstance(i,str) and re.fullmatch(r'CWE-\d+',i) for i in ids),'IDs CWE inválidos')
    row['cwe_ids'] = sorted(set(ids))
    row['condicao'] = 'diagnostico' if estrategia == 'P1L' else 'desenho'
    row['dry_run'] = bool(original.get('dry_run') or original.get('modelo') == 'dry-run')
    row['pos_aceite'] = False
    return row
