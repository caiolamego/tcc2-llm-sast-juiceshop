"""Revisoes aditivas e explicitas de associacoes; nunca modifica scans arquivados."""
from copy import deepcopy


def aplicar_revisoes(alertas: list[dict], revisoes: list[dict], chaves: set[str]) -> list[dict]:
    por_id = {a["id"]: a for a in alertas}
    usados = set()
    historico = []
    for revisao in revisoes:
        identidade = revisao["alerta_id"]
        if identidade in usados or identidade not in por_id:
            raise ValueError(f"Revisao duplicada ou alerta ausente: {identidade}")
        usados.add(identidade)
        alerta = por_id[identidade]
        anterior = deepcopy(alerta["triagem"])
        if alerta["scan"] == "baseline":
            raise ValueError("Revisao nao pode alterar o baseline")
        if anterior != revisao["triagem_anterior"] or anterior["status"] != "confirmado":
            raise ValueError(f"Triagem anterior divergente ou nao confirmada: {identidade}")
        novos = revisao["desafios_adicionais"]
        if (not novos or len(novos) != len(set(novos)) or not set(novos) <= chaves
                or set(novos) & set(anterior["desafios_confirmados"])):
            raise ValueError(f"Associacoes adicionais invalidas: {identidade}")
        if not revisao.get("motivo", "").strip():
            raise ValueError(f"Revisao sem justificativa: {identidade}")
        posterior = deepcopy(anterior)
        posterior["desafios_confirmados"] += novos
        posterior["sem_marcador"] = True
        posterior["motivo"] += "\nRevisao: " + revisao["motivo"]
        alerta["triagem"] = posterior
        historico.append({"alerta_id": identidade, "triagem_anterior": anterior,
                          "triagem_posterior": deepcopy(posterior),
                          "desafios_adicionais": novos, "motivo": revisao["motivo"]})
    return historico
