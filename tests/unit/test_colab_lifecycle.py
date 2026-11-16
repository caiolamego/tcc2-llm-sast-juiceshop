"""Ciclo do notebook com servidor/túnel simulados, sem GPU ou rede."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def sources():
    doc=json.loads((Path(__file__).resolve().parents[2]/'notebooks/qwen_colab_api.ipynb').read_text())
    return [''.join(c['source']) for c in doc['cells'] if c['cell_type']=='code']


def stop_source():
    return next(s for s in sources() if 'active_thread = globals().get' in s)


class ColabLifecycleTests(unittest.TestCase):
    def test_started_verdadeiro_com_thread_morta_nao_bloqueia(self):
        for source in sources():
            if 'server_thread.is_alive()' not in source or 'SERVER_SOURCE' in source:continue
            tree=ast.parse(source)
            guards=[n for n in tree.body if isinstance(n,ast.If) and 'server_thread' in ast.unparse(n.test)]
            if not guards:continue
            guard=ast.Module(body=[guards[0]],type_ignores=[])
            ns={'server':SimpleNamespace(started=True),'server_thread':SimpleNamespace(is_alive=lambda:False)}
            exec(compile(guard,'guard','exec'),ns)
            ns['server_thread']=SimpleNamespace(is_alive=lambda:True)
            with self.assertRaises(RuntimeError):exec(compile(guard,'guard','exec'),ns)

    def test_parada_confirmada_limpa_referencias_preserva_modelo_e_repete(self):
        model=object();server=SimpleNamespace(started=True,should_exit=False)
        thread=Mock();thread.is_alive.return_value=False
        ngrok=Mock()
        ns={'model':model,'server':server,'server_thread':thread,'tunnel':SimpleNamespace(public_url='fixture'),
            'BASE_URL':'fixture','ngrok':ngrok,'print':Mock()}
        exec(stop_source(),ns)
        self.assertTrue(server.should_exit);thread.join.assert_called_once_with(timeout=30)
        self.assertNotIn('server',ns);self.assertNotIn('server_thread',ns);self.assertNotIn('tunnel',ns)
        self.assertIs(ns['model'],model)
        exec(stop_source(),ns)

    def test_thread_viva_nao_declara_encerramento(self):
        thread=Mock();thread.is_alive.return_value=True
        ns={'server':SimpleNamespace(should_exit=False),'server_thread':thread,'print':Mock()}
        with self.assertRaisesRegex(RuntimeError,'ainda encerrando'):exec(stop_source(),ns)
        self.assertIn('server_thread',ns)

    def test_falha_tunel_nao_impede_pedido_parada(self):
        ngrok=Mock();ngrok.disconnect.side_effect=RuntimeError('fixture')
        server=SimpleNamespace(should_exit=False);thread=Mock();thread.is_alive.return_value=False
        ns={'server':server,'server_thread':thread,'ngrok':ngrok,'tunnel':SimpleNamespace(public_url='fixture'),'print':Mock()}
        with self.assertRaisesRegex(RuntimeError,'túnel não foi confirmado'):exec(stop_source(),ns)
        self.assertTrue(server.should_exit);thread.join.assert_called_once()

    def test_geracao_ativa_impede_reinicio(self):
        ns={'generation_lock':SimpleNamespace(locked=lambda:True),'print':Mock()}
        with self.assertRaisesRegex(RuntimeError,'geração ainda'):exec(stop_source(),ns)


if __name__=='__main__':unittest.main()
