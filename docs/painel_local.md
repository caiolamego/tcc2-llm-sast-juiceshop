# Painel local do pipeline

Na raiz do repositório, execute:

```bash
python painel.py
```

Abra http://127.0.0.1:8765. O script usa automaticamente a `.venv` existente.
Não há instalação de pacotes de frontend nem etapa de build. O servidor usa a
biblioteca padrão do Python e atende somente em `127.0.0.1`.

## Iniciar e acompanhar

1. Confira os casos, as estratégias e K apresentados. São lidos de
   [`config/execucao.yaml`](../config/execucao.yaml), também usado por `executar.py`.
2. Escolha **Real**, **Preflight** ou **Dry-run** e clique em **Iniciar pipeline**.
   Real usa o cliente LLM existente, seu cache e os limites acumulados do `.env`.
   O painel não altera esses limites e não envia a chave ao navegador.
3. Acompanhe o status, o tempo da sessão e o log. O polling acontece a cada 1,5 s.
4. Cada tentativa concluída aparece na tabela com issue, arquivo, estratégia,
   resultado e tempos. Os registros são atualizados ao fim da tentativa;
   uma linha ainda ausente não significa tempo zero.

O painel chama os mesmos comandos montados por `executar.montar_comandos`, mantendo
os gates, contratos, regras, estratégias e critérios do orquestrador. A seleção de
modo na página vale para a nova execução, sem modificar o YAML. As métricas são
consolidadas após término normal do pipeline. “Processo finalizado” indica o término
dos comandos, não a correção de todas as issues; confira as classificações e os logs.

## Encerrar

**Encerrar após tentativa atual** cria um pedido cooperativo de parada. A preparação
em curso ou a tentativa atual termina; o orquestrador não inicia outra tentativa e
devolve a worktree pelo fluxo normal de restauração. Uma chamada de API já enviada
pode ser cobrada. O painel permanece em “Aguardando parada” até o processo terminar.
Se a consolidação já estiver em curso, ela termina antes de encerrar.

O painel não mata processos à força. Uma etapa travada pode atrasar a parada até seu
timeout. `Ctrl+C` no terminal do servidor solicita a mesma parada e aguarda o término.
Fechar a aba do navegador mantém o servidor e a execução ativos; reabra a página
para acompanhar. O painel controla somente a execução iniciada por ele; não inicia,
encerra ou retoma execuções de outro terminal. Evite usar simultaneamente o terminal
e o painel sobre as mesmas worktrees.

Na parada pelo usuário ou em uma falha, os artefatos parciais são preservados e não
há consolidação automática. A retomada e a consolidação parcial continuam disponíveis
pelas interfaces completas do pipeline e de métricas. Após reiniciar o servidor,
execuções com contrato aparecem no seletor de histórico; o acompanhamento ao vivo
pertence à sessão atual do servidor.

## Tempos e resultados

Nas execuções com contrato 3.0, a configuração efetiva mostra política de validação,
cache e repetição de API. A tabela distingue cache da LLM de reuso SAST/funcional.
Passe o mouse sobre o resultado para consultar política, origem e etapas; sobre um
tempo reutilizado para consultar a duração original. O valor principal é o trabalho
gasto agora, não o custo histórico da evidência. Etapas dispensadas não são testes
aprovados. O exemplo `config/execucao_otimizada.exemplo.yaml` mantém K=1 e inicia em
preflight; o YAML padrão não foi alterado.

| Coluna | Medição |
|---|---|
| LLM | Latência registrada pelo cliente, incluindo a política existente de cache |
| SAST | Tempo registrado da reanálise estática |
| Validação | Tempo registrado da validação funcional |
| Total | `duracao_total_s`, medido com relógio monotônico para novas tentativas |
| Total com `≈` | Soma LLM + SAST + validação dos registros antigos; só aparece se as três etapas estiverem disponíveis |

O total novo começa antes de `tentativa()` e termina quando ela retorna. Inclui a
preparação interna, geração, aplicação e medições, mas não a fila para obter worktree,
a preparação global, a gravação final do registro ou a restauração ao devolver o pool.
Os registros novos também recebem `inicio_tentativa` e `fim_tentativa` em UTC.
Registros antigos permanecem intactos. Ausências aparecem como `—`; R/M indeterminados
aparecem como `?`. A coluna F mostra `F_criterio` quando esse campo existe.

No contrato 3.0, o total também inclui a restauração explícita feita após a medição
e antes de registrar a tentativa. A restauração adicional ao devolver o pool e a
persistência final continuam fora desse cronômetro. O replay mede ainda o tempo até
obter a worktree limpa (incluindo a preparação inicial do pool) e a restauração de
cada patch, em campos próprios. Somente esperas efetivamente instrumentadas são
apresentadas como medições.

O cronômetro da sessão é independente: inclui preparação e consolidação. Tempos de
tentativas paralelas não devem ser somados como tempo de parede. A tabela mostra
tentativas e não calcula novamente as populações científicas das métricas. Preflight
gera prompts e não corresponde a tentativas de correção.

## Arquivos e opções

- `painel.py`: inicialização e seleção da `.venv`.
- `src/pipeline/painel/`: servidor HTTP, controle de execução e leitura dos registros.
- `frontend/painel/`: interface sem dependências externas.
- `outputs/painel/`: logs completos e estado final das sessões iniciadas pelo painel.
- `.cache/painel/`: pedidos de parada e lock de instância; dados locais ignorados pelo Git.
- A pasta configurada em `saida_base`: artefatos do pipeline e diretório irmão `_METRICAS`.

```bash
python painel.py --porta 8766
python painel.py --config /caminho/execucao.yaml
```

Os resultados configurados devem estar dentro de `outputs/`. Cada início cria um
identificador novo. Apenas uma execução pode ficar ativa no painel; um lock impede
duas instâncias do servidor. As operações de controle exigem token de sessão e
origem local. A interface não fornece acesso livre a arquivos ou comandos shell.

## Verificação

Os testes de `tests/unit/test_painel.py` usam processos sintéticos e fixtures:
leitura dos tempos, ausência de valores, rejeição de caminhos externos e symlinks,
parada cooperativa, restauração pelo fluxo do pool, exclusão de execução concorrente,
falha de processo, consolidação e proteção das operações HTTP. Não chamam LLM,
Semgrep nem testes funcionais do Juice Shop.
