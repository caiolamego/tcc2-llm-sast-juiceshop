"""Compara rodada 12 com snapshot 11, preservando historico."""
import json
from report_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada11/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada12/matriz_desafios.json"
ALVOS = {"emptyUserRegistration", "passwordRepeatChallenge", "zeroStarsChallenge"}
PERFIS = {"default", "custom-rules", *(f"rodada{i}" for i in range(2, 13))}


def comparar(antes, depois):
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico SSTI alterado")
    result = resumir(antes, depois, novo_scan="rodada12", perfis=PERFIS)
    result["candidatos_incluidos"] = sorted(ALVOS & set(result["novos_desafios_confirmados"]))
    result["meta_50_desafios_atingida"] = result["desafios_confirmados_depois"] >= 50
    result["limites"] = "Dois alertas novos cobrem tres desafios; nao equivalem a tres causas independentes. Mantida confirmacao condicional de JSONP da rodada 11. Selecao de correcao antiga nao atualizada."
    return result


if __name__ == "__main__":
    result = comparar(json.loads(OLD.read_text()), json.loads(NEW.read_text()))
    (NEW.parent / "resumo.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
