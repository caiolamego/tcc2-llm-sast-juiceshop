const $ = id => document.getElementById(id);
let token = '', configured = false, busy = false;
const duration = value => value == null ? '—' : value < 60 ? `${value.toFixed(2)} s` : `${Math.floor(value / 60)}m ${(value % 60).toFixed(1)}s`;
const bit = value => value == null ? '?' : String(Number(value));
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Painel-Token': token}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.erro || `HTTP ${response.status}`);
  return data;
}
function cell(row, text) { const td = document.createElement('td'); td.textContent = text; row.append(td); return td; }
function render(data) {
  const current = data.atual;
  $('connection').textContent = 'Local · conectado';
  $('start').disabled = data.ativo || busy;
  $('stop').disabled = !data.ativo || current?.status === 'parando' || busy;
  $('mode').disabled = data.ativo || busy;
  if (!configured) { $('mode').value = data.config.modo; configured = true; }
  $('config').textContent = `Casos: ${data.config.casos.join(', ')} · Estratégias: ${data.config.estrategias.join(' → ')} · K=${data.config.k} · ${data.config.politica_validacao} · Cache de validação: ${data.config.cache_validacao} · Repetição API: ${data.config.repeticao_api}`;
  const labels = {executando: 'Executando', parando: 'Aguardando parada', finalizada: 'Processo finalizado', interrompida: 'Interrompida', falhou: 'Falhou'};
  $('status').textContent = current ? `${labels[current.status] || current.status} · ${current.etapa}` : 'Aguardando';
  $('elapsed').textContent = current ? duration(current.decorrido_s) : '—';
  $('count').textContent = data.tentativas.length;
  $('run').textContent = $('history').value || current?.execucao || 'Selecione uma execução anterior ou inicie uma nova.';
  if (current?.erro) $('error').textContent = current.erro;
  const rows = data.tentativas.map(attempt => {
    const tr = document.createElement('tr');
    const first = cell(tr, attempt.caso || '—'); const file = document.createElement('small'); file.textContent = attempt.arquivo || '—'; first.append(file);
    const strategy = cell(tr, attempt.estrategia?.split('_')[0] || '—');
    strategy.title = attempt.estrategia || '';
    const hits = Object.entries(attempt.cache_validacao || {}).filter(([,v])=>v.hit).map(([k])=>k);
    const result = cell(tr, `${attempt.classificacao || '—'}${attempt.cache ? ' · cache LLM' : ''}${hits.length ? ' · reuso '+hits.join('/') : ''}`);
    const reasons = (attempt.motivos_indeterminacao || []).map(r => typeof r === 'string' ? r : `${r.campo}: ${r.descricao}`);
    if (reasons.length) { const detail = document.createElement('small'); detail.textContent = reasons.join(' '); result.append(detail); }
    else if (attempt.classificacao === 'indeterminada_sast') { const detail = document.createElement('small'); detail.textContent = 'Consulte a comparação arquivada para esta execução.'; result.append(detail); }
    if (attempt.cobertura_detalhada) {
      const detail=document.createElement('small');
      const scope=attempt.cobertura_detalhada;
      detail.textContent=`Cobertura: ${(scope.dominios||[]).join(', ') || 'insuficiente'} · ${(scope.grupos||[]).length} grupos executados${scope.motivos?.length ? ' · '+scope.motivos.join('; ') : ''}`;
      result.append(detail);
    }
    result.title = JSON.stringify({comparador:attempt.versao_comparador,motivos:attempt.motivos_indeterminacao,contexto:attempt.falhas_contexto_sast,politica:attempt.politica_validacao,cache:attempt.cache_validacao,etapas:attempt.etapas_validacao,cobertura:attempt.cobertura_detalhada ? {dominios:attempt.cobertura_detalhada.dominios,baseline:attempt.cobertura_detalhada.baseline_sha256,suficiente:attempt.cobertura_detalhada.suficiente,selecionados:attempt.cobertura_detalhada.grupos_selecionados,compilacoes:attempt.cobertura_detalhada.compilacoes,grupos:attempt.cobertura_detalhada.grupos.map(g=>({grupo:g.grupo,esperados:g.esperados?.length,executados:g.executados?.length,ignorados:g.testes?.filter(t=>t.estado==='ignorado').length}))} : null},null,2);
    for (const key of ['llm', 'sast', 'validacao']) {
      const td=cell(tr, duration(attempt.tempos[key]));
      const origem=attempt.cache_validacao?.[key==='validacao'?'funcional':key];
      if(origem?.hit) td.title=`Tempo gasto agora. Evidência original: ${duration(origem.duracao_original_s)}`;
    }
    cell(tr, `${attempt.total_estimado && attempt.tempos.total != null ? '≈ ' : ''}${duration(attempt.tempos.total)}`);
    cell(tr, [attempt.R, attempt.F, attempt.M].map(bit).join(' / '));
    return tr;
  });
  $('attempts').replaceChildren(...rows);
  $('empty').hidden = rows.length > 0;
  $('warnings').textContent = data.avisos.join(' ');
  if (!$('history').value) {
    $('log').textContent = data.log || 'Aguardando mensagens do pipeline…';
    if ($('follow').checked) $('log').scrollTop = $('log').scrollHeight;
  } else $('log').textContent = 'O log ao vivo pertence à execução atual. Escolha “Execução atual” para acompanhar.';
}
async function refresh() {
  try { render(await api(`/api/status?selecao=${encodeURIComponent($('history').value)}`)); }
  catch (error) { $('connection').textContent = 'Sem conexão'; $('error').textContent = error.message; $('start').disabled = true; $('stop').disabled = true; }
}
async function history() {
  const previous = $('history').value;
  const data = await api('/api/historico');
  const options = [new Option('Execução atual', ''), ...data.execucoes.map(r => new Option(`${r.execucao} · ${r.modo || 'histórico'}`, r.caminho))];
  $('history').replaceChildren(...options); $('history').value = previous;
}
async function action(path, body) {
  busy = true; $('start').disabled = true; $('stop').disabled = true; $('error').textContent = '';
  try { await api(path, body); if (path.endsWith('iniciar')) $('history').value = ''; }
  catch (error) { $('error').textContent = error.message; }
  finally { busy = false; await refresh(); }
}
$('start').onclick = () => action('/api/iniciar', {modo: $('mode').value});
$('stop').onclick = () => action('/api/parar', {});
$('history').onchange = refresh;
async function init() {
  try { token = (await api('/api/token')).token; await history(); await refresh(); }
  catch (error) { $('error').textContent = error.message; }
  setInterval(refresh, 1500); setInterval(() => history().catch(() => {}), 10000);
}
init();
