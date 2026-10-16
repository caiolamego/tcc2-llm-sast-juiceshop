"""A entrada curta delega a execução sem acessar API, SAST ou worktrees."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import executar
import yaml


class EntradaCurtaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(executar, "RAIZ", self.raiz).start()
        self.config = {"modo": "real", "casos": ["AMPa", "AMPb"],
                       "estrategias": ["P1", "P2", "P3", "P4"], "k": 1,
                       "catalogo": "catalogo.json", "perfil_sast": "perfil.json",
                       "baseline_testes": "baseline.json", "semgrep_bin": "semgrep",
                       "saida_base": "outputs"}
        for campo in ("catalogo", "perfil_sast", "baseline_testes", "semgrep_bin"):
            (self.raiz / self.config[campo]).touch()
        self.arquivo = self.raiz / "config.yaml"
        self.gravar()

    def gravar(self):
        self.arquivo.write_text(yaml.safe_dump(self.config), encoding="utf-8")

    def executar_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return executar.main(["--config", str(self.arquivo), *args])

    def test_real_delega_e_consolida_na_mesma_execucao(self):
        with patch.object(executar.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(self.executar_main(), 0)
        self.assertEqual(run.call_count, 2)
        pipeline, metricas = [call.args[0] for call in run.call_args_list]
        self.assertEqual(pipeline[pipeline.index("--casos") + 1], "AMPa,AMPb")
        self.assertEqual(pipeline[pipeline.index("--execucao") + 1], metricas[metricas.index("--execucao") + 1])
        self.assertNotIn("--dry-run", pipeline)
        self.assertNotIn("--pular-checagem-ambiente", pipeline)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["cwd"], self.raiz)

    def test_falha_do_pipeline_preserva_codigo_e_nao_consolida(self):
        with patch.object(executar.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)) as run:
            self.assertEqual(self.executar_main(), 7)
        self.assertEqual(run.call_count, 1)

    def test_preview_nao_executa_nem_cria_saida(self):
        with patch.object(executar.subprocess, "run", side_effect=AssertionError("subprocesso inesperado")):
            self.assertEqual(self.executar_main("--mostrar-comando"), 0)
        self.assertFalse((self.raiz / "outputs").exists())

    def test_modos_delegam_flags_corretas(self):
        for modo, flag in (("preflight", "--somente-preflight"), ("dry-run", "--dry-run")):
            with self.subTest(modo=modo), patch.object(executar.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(self.executar_main("--modo", modo), 0)
                self.assertIn(flag, run.call_args_list[0].args[0])

    def test_config_invalida_falha_antes_de_executar(self):
        for campo, valor in (("casos", []), ("casos", ["AMPa", "AMPa"]),
                             ("k", True), ("estrategias", ["P1L"]),
                             ("catalogo", "ausente.json")):
            with self.subTest(campo=campo, valor=valor):
                original = self.config[campo]
                self.config[campo] = valor
                self.gravar()
                with patch.object(executar.subprocess, "run", side_effect=AssertionError("subprocesso inesperado")):
                    self.assertEqual(self.executar_main(), 1)
                self.config[campo] = original

    def test_caminhos_resolvidos_pela_raiz(self):
        config = executar.carregar_config(self.arquivo)
        self.assertEqual(config["catalogo"], self.raiz / "catalogo.json")
        self.assertEqual(config["saida_base"], self.raiz / "outputs")

    def test_selecao_da_venv_preserva_argumentos(self):
        python = self.raiz / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.touch()
        with patch.object(executar.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(self.executar_main("--modo", "preflight", "--mostrar-comando"), 0)
        comando = run.call_args.args[0]
        self.assertEqual(comando[0], str(python))
        self.assertEqual(comando[comando.index("--config") + 1], str(self.arquivo))
        self.assertIn("--mostrar-comando", comando)
        self.assertEqual(comando[comando.index("--modo") + 1], "preflight")

    def test_politica_opcional_propaga_sem_alterar_yaml_antigo(self):
        mapa=self.raiz/'mapa.yaml';mapa.write_text('fixture')
        self.config.update(politica_validacao='otimizada_v1',mapa_testes='mapa.yaml',
                           cache_validacao='leitura-escrita',repeticao_api='seletiva-experimental')
        self.gravar()
        with patch.object(executar.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertEqual(self.executar_main(),0)
        cmd=run.call_args_list[0].args[0]
        self.assertEqual(cmd[cmd.index('--mapa-testes')+1],str(mapa))
        self.assertEqual(cmd[cmd.index('--politica-validacao')+1],'otimizada_v1')
        self.assertIn('--cache-validacao',cmd)


if __name__ == "__main__":
    unittest.main()
