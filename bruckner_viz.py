"""
bruckner_viz.py
---------------
Visualização do Diagrama de Massas (Curva de Brückner) integrada ao
programa de distribuição de terraplenagem.

Três pontos de entrada:
  - abrir_pre_distribuicao(resultados, config_dist, master)
  - abrir_pos_distribuicao(caminho_json, master)
  - abrir_pos_redistribuicao(caminho_json, master)

Requer: tkinterweb  (pip install tkinterweb)
"""

import json
import os
import tkinter as tk
from tkinter import messagebox

# ---------------------------------------------------------------------------
# Constantes visuais (mesmas da interface.py)
# ---------------------------------------------------------------------------
COR_BG     = "#1E2330"
COR_PAINEL = "#252B3B"
COR_BORDA  = "#3A4460"
COR_ACCENT = "#4A9EFF"
COR_TEXTO  = "#E8EAF0"


# ---------------------------------------------------------------------------
# Build da Curva de Brückner (monotônica, por breakpoints de posição física)
# ---------------------------------------------------------------------------

def _build_bruckner(ramo: dict) -> list:
    """
    Para um ramo do JSON, constrói a curva de Brückner correta:
    - Discretiza o eixo pelos breakpoints reais (estaca_ini e estaca_fin)
    - Acumula massa proporcionalmente à densidade volumétrica em cada fatia
    - Resultado: X estritamente crescente, nunca recua
    - Inclui referências ao QDM (origens/destinos) para o tooltip
    """
    trechos = [t for t in ramo.get('trechos', [])
               if t['tipo'] in ('CORTE', 'C. LATERAL', 'ATERRO')]
    if not trechos:
        return []

    # Índices QDM: label → lista de fluxos
    qdm_orig, qdm_dest = {}, {}
    for l in ramo.get('linhas_qdm', []):
        k = l['label_origem']
        if k not in qdm_orig:
            qdm_orig[k] = []
        qdm_orig[k].append({
            'dest': l['label_destino'],
            'vol':  round(l['vol_total']),
            'dmt':  round(l['dmt_total'], 3),
            'r':    l.get('ramo_destino', '')
        })
        k2 = l['label_destino']
        if k2 not in qdm_dest:
            qdm_dest[k2] = []
        qdm_dest[k2].append({
            'orig': l['label_origem'],
            'vol':  round(l['vol_total']),
            'dmt':  round(l['dmt_total'], 3)
        })

    # Densidade volumétrica por trecho (m³/m), negativa para aterro
    for t in trechos:
        ext = max(t['estaca_fin_m'] - t['estaca_ini_m'], 0.01)
        sinal = -1 if t['tipo'] == 'ATERRO' else 1
        t['_dens'] = sinal * t['vol_total_hom'] / ext

    # Breakpoints = union de todos estaca_ini e estaca_fin
    breaks = sorted(set(
        [t['estaca_ini_m'] for t in trechos] +
        [t['estaca_fin_m'] for t in trechos]
    ))

    pontos = []
    massa = 0.0

    for i in range(len(breaks) - 1):
        x0, x1 = breaks[i], breaks[i + 1]
        dx = x1 - x0
        if dx <= 0:
            continue

        # Ponto no início do intervalo (antes da variação)
        pontos.append({'x': round(x0, 1), 'y': round(massa),
                       'l': '', 'p': '', 'v': 0})

        # Acumula contribuição de todos os trechos que cobrem esta fatia
        delta = sum(
            t['_dens'] * dx
            for t in trechos
            if t['estaca_ini_m'] <= x0 and t['estaca_fin_m'] >= x1
        )
        massa += delta

        # Ponto no fim do intervalo: associa ao trecho que termina aqui
        t_fim = next((t for t in trechos
                      if abs(t['estaca_fin_m'] - x1) < 0.1), None)
        if t_fim:
            label = f"{t_fim['prefixo']}{t_fim['numero']}"
            p = {
                'x': round(x1, 1),
                'y': round(massa),
                'l': label,
                'p': t_fim['prefixo'].rstrip('-'),
                'v': round(t_fim['vol_total_hom']),
            }
            if label in qdm_orig:
                p['s'] = qdm_orig[label]
            if label in qdm_dest:
                p['e'] = qdm_dest[label]
            pontos.append(p)
        else:
            pontos.append({'x': round(x1, 1), 'y': round(massa),
                           'l': '', 'p': '', 'v': 0})

    # Remove pontos com X consecutivo idêntico
    result = [pontos[0]] if pontos else []
    for p in pontos[1:]:
        if p['x'] != result[-1]['x']:
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Resumo por ramo (corte, aterro, balanço, BF para remoção)
# ---------------------------------------------------------------------------

def _resumo_ramo(ramo: dict) -> dict:
    nome   = ramo['nome']
    trechos = ramo.get('trechos', [])
    corte  = sum(t['vol_total_hom'] for t in trechos
                 if t['tipo'] in ('CORTE', 'C. LATERAL'))
    aterro = sum(t['vol_total_hom'] for t in trechos
                 if t['tipo'] == 'ATERRO')
    bf     = sum(l['vol_total'] for l in ramo.get('linhas_qdm', [])
                 if 'BF' in l.get('label_destino', ''))

    if   'PISTA DIREITA'  in nome: cat = 'pd'
    elif 'PISTA ESQUERDA' in nome: cat = 'pe'
    elif 'REMOÇÃO' in nome or 'REMOÇÃ' in nome: cat = 'rm'
    elif 'MARGINAL' in nome: cat = 'marg'
    elif 'EIXO' in nome or 'VIADUTO' in nome: cat = 'eixo'
    elif 'INT' in nome: cat = 'int'
    else: cat = 'outro'

    return {
        'nome': nome, 'cat': cat,
        'corte':  round(corte),
        'aterro': round(aterro),
        'bf':     round(bf),
    }


# ---------------------------------------------------------------------------
# Preparação dos dados do JSON para o HTML
# ---------------------------------------------------------------------------

def _dados_do_json(dados: dict, modo: str) -> dict:
    """
    Extrai do JSON do projeto:
    - ramos paralelos (pistas + remoção)
    - ramos de interseção/marginais
    - resumo por ramo
    - interseções do config_dist para as linhas verticais

    modo: 'pre' | 'pos' | 'pos_redist'
    """
    ramos = dados.get('ramos', [])

    # Identificar categorias
    paralelos = []     # pd, pe, rm
    intersecoes_ramos = []  # marg, eixo, int

    for ramo in ramos:
        nome = ramo['nome']
        if any(k in nome for k in ('PISTA DIREITA', 'PISTA ESQUERDA',
                                    'REMOÇÃO', 'REMOÇÃ')):
            paralelos.append(ramo)
        else:
            intersecoes_ramos.append(ramo)

    # Build das curvas apenas para ramos paralelos
    curvas = {}
    for ramo in paralelos:
        curvas[ramo['nome']] = _build_bruckner(ramo)

    # Resumos de todos os ramos
    resumos = [_resumo_ramo(r) for r in ramos]

    # Linhas de interseção do config_dist (posição no eixo principal)
    ints_viz = []
    config_dist = dados.get('config_dist', {})
    relacoes = config_dist.get('relacoes', []) if isinstance(config_dist, dict) \
               else getattr(config_dist, 'relacoes', [])

    for rel in relacoes:
        rd = rel if isinstance(rel, dict) else vars(rel)
        tipo = rd.get('tipo', '')
        if tipo == 'intersecao_marginal':
            pos = rd.get('pos_relativa_m', 0)
            ramo_b = rd.get('ramo_b', '')
            ramos_todos = rd.get('ramos_todos') or []
            nomes_int = ramos_todos if ramos_todos else ([ramo_b] if ramo_b else [])
            cat = ('eixo'  if any('EIXO' in n or 'VIADUTO' in n for n in nomes_int)
                   else 'int' if any('INT' in n for n in nomes_int)
                   else 'marg')
            nome_curto = '; '.join(n.replace('MARGINAL ','MARG. ')
                                    .replace('EIXO PI ','PI ')
                                    .replace('EIXO VIADUTO ','VIAD. ')
                                    .replace(' CRZ ', ' CRZ ')
                                    for n in nomes_int[:2])
            if nome_curto and pos:
                ints_viz.append({'pos': pos, 'nome': nome_curto, 'cat': cat})

    # Deduplicar interseções por posição
    vistas = set()
    ints_unicas = []
    for iv in ints_viz:
        k = round(iv['pos'])
        if k not in vistas:
            vistas.add(k)
            ints_unicas.append(iv)

    return {
        'modo':    modo,
        'nome':    dados.get('nome', 'Projeto'),
        'curvas':  curvas,
        'resumos': resumos,
        'ints':    ints_unicas,
    }


def _dados_do_resultados(resultados: list, config_dist) -> dict:
    """
    Para pré-distribuição: constrói curvas só com os trechos,
    sem linhas_qdm (ainda não distribuído).
    """
    ramos_fake = []
    for res in resultados:
        trechos_dict = []
        for t in res.trechos:
            trechos_dict.append({
                'tipo':          t.tipo,
                'prefixo':       t.prefixo,
                'numero':        t.numero,
                'vol_total_hom': t.vol_total_hom,
                'estaca_ini_m':  t.estaca_ini_m,
                'estaca_fin_m':  t.estaca_fin_m,
            })
        ramos_fake.append({'nome': res.ramo, 'trechos': trechos_dict, 'linhas_qdm': []})

    dados_fake = {
        'nome':       'Pré-distribuição',
        'ramos':      ramos_fake,
        'config_dist': config_dist if isinstance(config_dist, dict)
                       else {'relacoes': [vars(r) for r in getattr(config_dist, 'relacoes', [])]},
    }
    return _dados_do_json(dados_fake, 'pre')


# ---------------------------------------------------------------------------
# Geração do HTML completo
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Diagrama de Massas</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#1E2330;color:#E8EAF0;padding:0;overflow-x:hidden}
.topo{background:#252B3B;padding:8px 16px;border-bottom:1px solid #3A4460;display:flex;align-items:center;gap:12px}
.topo-titulo{font-size:13px;font-weight:600;color:#4A9EFF}
.topo-sub{font-size:11px;color:#8892A4}
.topo-modo{font-size:10px;background:#3A4460;color:#E8EAF0;padding:2px 8px;border-radius:10px}
.corpo{padding:10px 14px}
.stats{display:grid;gap:6px;margin-bottom:10px}
.stat{background:#252B3B;border-radius:6px;padding:6px 10px;border:.5px solid #3A4460}
.stat-nome{font-size:9.5px;color:#8892A4;font-weight:500;text-transform:uppercase;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stat-rows{display:grid;grid-template-columns:auto 1fr;gap:0px 6px;font-size:10.5px;line-height:1.7}
.sl{color:#8892A4}
.sv{text-align:right;font-variant-numeric:tabular-nums}
.sv-c{color:#4A9EFF}
.sv-a{color:#E74C3C}
.sv-p{color:#2ECC71;font-weight:600}
.sv-n{color:#E74C3C;font-weight:600}
.sv-bf{color:#F39C12}
.sv-sep{border-top:.5px solid #3A4460;grid-column:1/-1;margin:2px 0}
.ctrls{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px;align-items:center}
.btn{font-size:10.5px;padding:3px 10px;border-radius:20px;border:1.5px solid;cursor:pointer;transition:all .12s;background:transparent;white-space:nowrap;color:#E8EAF0}
.chart-w{position:relative;width:100%;height:360px}
.tt{position:absolute;background:#252B3B;border:.5px solid #3A4460;border-radius:7px;padding:8px 11px;font-size:10.5px;pointer-events:none;display:none;z-index:20;min-width:185px;max-width:255px;box-shadow:0 4px 16px rgba(0,0,0,.4)}
.tt-h{font-weight:600;font-size:11.5px;color:#E8EAF0;margin-bottom:4px;display:flex;align-items:center;gap:5px}
.tt-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.tt-r{color:#8892A4;line-height:1.6;margin-top:1px}
.tt-r b{color:#E8EAF0}
.tt-sep{border-top:.5px solid #3A4460;margin:4px 0}
.tt-fh{font-size:10px;font-weight:600;color:#E8EAF0;margin-bottom:2px}
.tt-f{font-size:10px;color:#8892A4;margin-top:1px}
.tt-f b{color:#E8EAF0}
.leg{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:10.5px;color:#8892A4;align-items:center}
.li{display:flex;align-items:center;gap:3px}
.ll{width:16px;height:3px;border-radius:2px;flex-shrink:0}
.sec{font-size:9.5px;font-weight:600;color:#8892A4;text-transform:uppercase;letter-spacing:.05em;margin:8px 0 4px;width:100%}
</style>
</head>
<body>
<div class="topo">
  <div class="topo-titulo">⬡ DIAGRAMA DE MASSAS — BRÜCKNER</div>
  <div class="topo-sub" id="proj-nome"></div>
  <div class="topo-modo" id="modo-badge"></div>
</div>
<div class="corpo">
  <div class="stats" id="stats"></div>
  <div class="ctrls" id="btns"></div>
  <div class="chart-w">
    <canvas id="cv" role="img" aria-label="Curva de Brückner"></canvas>
    <div class="tt" id="tt">
      <div class="tt-h"><div class="tt-dot" id="td"></div><span id="tl"></span></div>
      <div class="tt-r" id="tr1"></div>
      <div class="tt-r" id="tr2"></div>
      <div class="tt-r" id="tr3"></div>
      <div class="tt-r" id="tr4"></div>
      <div class="tt-sep" id="ts" style="display:none"></div>
      <div id="tf"></div>
    </div>
  </div>
  <div class="leg" id="leg"></div>
</div>

<script>
// ── DADOS INJETADOS PELO PYTHON ──────────────────────────────────────────
const DADOS = __DADOS_JSON__;
// ────────────────────────────────────────────────────────────────────────

// Cores por ramo e tipo de material
const CORES_RAMO = {
  pd: {CO:'#4A9EFF', CL:'#85B7EB', CA:'#0C447C', CF:'#042C53', C2:'#5B9FE0', C3:'#B5D4F4', '':'#4A9EFF'},
  pe: {CO:'#2ECC71', CL:'#5DCAA5', CA:'#085041', CF:'#04342C', C2:'#3DB88A', C3:'#9FE1CB', '':'#2ECC71'},
  rm: {CA:'#888780', CL:'#B4B2A9', CF:'#5F5E5A', C2:'#888780', C3:'#D3D1C7', '':'#888780'},
};
const INT_CORES = {marg:'#D85A30', eixo:'#7F77DD', int:'#2ECC71'};

function corTipo(cat, p) {
  const m = CORES_RAMO[cat] || CORES_RAMO.pd;
  if(!p) return m[''];
  if(p==='CA'||p==='CF') return m['CA'];
  if(p==='CL') return m['CL'];
  if(p==='C2') return m['C2'];
  if(p==='C3') return m['C3'];
  return m['CO'];
}

function catRamo(nome) {
  if(nome.includes('PISTA DIREITA'))  return 'pd';
  if(nome.includes('PISTA ESQUERDA')) return 'pe';
  if(nome.includes('REMO'))           return 'rm';
  return 'outro';
}

const fv = v => Math.round(v).toLocaleString('pt-BR');
const TIPO_NOME = {CO:'Corte', CL:'C. Lateral', CA:'Aterro', CF:'Aterro CF',
                   C2:'Corte C2', C3:'Corte C3', '':'—'};

// ── MODO ─────────────────────────────────────────────────────────────────
document.getElementById('proj-nome').textContent = DADOS.nome;
const modoTexto = {pre:'Pré-distribuição', pos:'Pós-distribuição',
                   pos_redist:'Pós-redistribuição'};
const modoBadge = document.getElementById('modo-badge');
modoBadge.textContent = modoTexto[DADOS.modo] || DADOS.modo;
modoBadge.style.background = DADOS.modo==='pre' ? '#3A4460'
                           : DADOS.modo==='pos' ? '#0C447C' : '#085041';

// ── PAINEL DE RESUMO ─────────────────────────────────────────────────────
const statsDiv = document.getElementById('stats');

// Detectar colunas: paralelas (pd/pe/rm) e se há interseções
const resumosParalelos = DADOS.resumos.filter(r => ['pd','pe','rm'].includes(r.cat));
const resumosInts = DADOS.resumos.filter(r => !['pd','pe','rm'].includes(r.cat));

// Grid adaptativo
const nPar = resumosParalelos.length;
const nInt = resumosInts.length;
const colsPar = Math.min(nPar, 3);
statsDiv.style.gridTemplateColumns = `repeat(${colsPar}, 1fr)`;

function mkCard(r) {
  const div = document.createElement('div');
  div.className = 'stat';
  const isRm = r.cat === 'rm';
  const corNome = r.cat==='pd' ? '#4A9EFF'
                : r.cat==='pe' ? '#2ECC71'
                : r.cat==='rm' ? '#888780'
                : r.cat==='marg' ? '#D85A30'
                : r.cat==='eixo' ? '#7F77DD'
                : r.cat==='int' ? '#2ECC71' : '#E8EAF0';
  const nomeCurto = r.nome.replace('SEGB ','').replace('MARGINAL ','MARG. ')
                          .replace('EIXO PI ','PI ').replace('EIXO VIADUTO ','VIAD. ')
                          .replace(' CRZ ',' CRZ ').replace(' E ',' e ');
  const bal = r.corte - r.aterro;
  if(isRm) {
    div.innerHTML = `
      <div class="stat-nome" style="color:${corNome}">${nomeCurto}</div>
      <div class="stat-rows">
        <span class="sl">Escav. → BF</span><span class="sv sv-bf">${fv(r.corte)} m³</span>
        <span class="sl">Aterro ext.</span><span class="sv sv-a">${fv(r.aterro)} m³</span>
        <div class="sv-sep"></div>
        <span class="sl" style="font-size:9px;color:#5F5E5A">Corte → BF, sem balanço</span><span class="sv" style="font-size:9px;color:#5F5E5A">—</span>
      </div>`;
  } else {
    div.innerHTML = `
      <div class="stat-nome" style="color:${corNome}">${nomeCurto}</div>
      <div class="stat-rows">
        <span class="sl">Corte</span><span class="sv sv-c">+${fv(r.corte)} m³</span>
        <span class="sl">Aterro</span><span class="sv sv-a">−${fv(r.aterro)} m³</span>
        <div class="sv-sep"></div>
        <span class="sl">Balanço</span>
        <span class="sv ${bal>=0?'sv-p':'sv-n'}">${bal>=0?'+':''}${fv(bal)} m³</span>
      </div>`;
  }
  return div;
}

resumosParalelos.forEach(r => statsDiv.appendChild(mkCard(r)));

// Interseções em linha separada se existirem
if(resumosInts.length > 0) {
  const secDiv = document.createElement('div');
  secDiv.className = 'sec';
  secDiv.textContent = 'Interseções / Marginais';
  secDiv.style.gridColumn = '1/-1';
  statsDiv.appendChild(secDiv);

  const nCols = Math.min(resumosInts.length, 4);
  const wrapInt = document.createElement('div');
  wrapInt.style.cssText = `grid-column:1/-1;display:grid;grid-template-columns:repeat(${nCols},1fr);gap:5px`;
  resumosInts.forEach(r => wrapInt.appendChild(mkCard(r)));
  statsDiv.appendChild(wrapInt);

  // Somatório geral (exceto remoção)
  const semRm = DADOS.resumos.filter(r => r.cat !== 'rm');
  const totCorte  = semRm.reduce((a,r) => a + r.corte,  0);
  const totAterro = semRm.reduce((a,r) => a + r.aterro, 0);
  const totBal    = totCorte - totAterro;
  const rmRes     = DADOS.resumos.find(r => r.cat === 'rm');

  const totWrap = document.createElement('div');
  totWrap.style.cssText = 'grid-column:1/-1;background:#252B3B;border-radius:6px;padding:7px 12px;border:.5px solid #3A4460';
  totWrap.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(${rmRes?4:3},1fr);gap:0">
      <div style="padding:3px 8px;border-right:.5px solid #3A4460">
        <div style="font-size:9.5px;color:#8892A4">Corte total</div>
        <div style="font-size:12px;font-weight:600;color:#4A9EFF">+${fv(totCorte)} m³</div>
      </div>
      <div style="padding:3px 8px;border-right:.5px solid #3A4460">
        <div style="font-size:9.5px;color:#8892A4">Aterro total</div>
        <div style="font-size:12px;font-weight:600;color:#E74C3C">−${fv(totAterro)} m³</div>
      </div>
      <div style="padding:3px 8px;${rmRes?'border-right:.5px solid #3A4460':''}">
        <div style="font-size:9.5px;color:#8892A4">Balanço geral</div>
        <div style="font-size:12px;font-weight:600;color:${totBal>=0?'#2ECC71':'#E74C3C'}">${totBal>=0?'+':''}${fv(totBal)} m³</div>
      </div>
      ${rmRes ? `<div style="padding:3px 8px">
        <div style="font-size:9.5px;color:#8892A4">Remoção → BF</div>
        <div style="font-size:12px;font-weight:600;color:#F39C12">${fv(rmRes.corte)} m³</div>
      </div>` : ''}
    </div>`;
  statsDiv.appendChild(totWrap);
}

// ── BOTÕES DE VISIBILIDADE ───────────────────────────────────────────────
const vis = {};
const btnsDiv = document.getElementById('btns');
const legDiv  = document.getElementById('leg');

// Monta lista de ramos para botões
const ramosVisiveis = Object.keys(DADOS.curvas);
ramosVisiveis.forEach(nome => { vis[nome] = true; });
vis['ints'] = true;

const COR_BTN = {
  pd: '#4A9EFF', pe: '#2ECC71', rm: '#888780', ints: '#D85A30'
};

function mkBtn(label, key, cor) {
  const b = document.createElement('button');
  b.className = 'btn';
  b.textContent = label;
  b.style.borderColor = cor;
  b.style.background  = cor;
  b.style.color = '#fff';
  b.addEventListener('click', () => {
    vis[key] = !vis[key];
    b.style.background = vis[key] ? cor : 'transparent';
    b.style.color = vis[key] ? '#fff' : cor;
    chart.update('none');
  });
  btnsDiv.appendChild(b);
}

ramosVisiveis.forEach(nome => {
  const cat = catRamo(nome);
  const cor = COR_BTN[cat] || '#8892A4';
  const label = nome.replace('SEGB ','').replace('REMOÇÃO','Remoção');
  mkBtn(label, nome, cor);
});
if(DADOS.ints.length > 0) {
  mkBtn('Interseções', 'ints', '#D85A30');
}

// ── LEGENDA ──────────────────────────────────────────────────────────────
const legItems = [
  {c:'#4A9EFF', l:'PD — Corte'}, {c:'#0C447C', l:'PD — Aterro'}, {c:'#85B7EB', l:'PD — C.Lateral'},
  {c:'#2ECC71', l:'PE — Corte'}, {c:'#085041', l:'PE — Aterro'}, {c:'#5DCAA5', l:'PE — C.Lateral'},
  {c:'#888780', l:'Remoção'},
];
legItems.forEach(({c, l}) => {
  const d = document.createElement('div'); d.className = 'li';
  d.innerHTML = `<div class="ll" style="background:${c}"></div>${l}`;
  legDiv.appendChild(d);
});

// ── CHART.JS ─────────────────────────────────────────────────────────────
const ctx = document.getElementById('cv').getContext('2d');

function buildDataset(nomRamo, dados) {
  const cat = catRamo(nomRamo);
  const isRm = cat === 'rm';
  const corBase = COR_BTN[cat] || '#8892A4';
  return {
    label: nomRamo,
    parsing: false,
    data: dados.map(p => ({...p, _r: cat})),
    borderColor: corBase,
    borderWidth: isRm ? 1.5 : 2.2,
    borderDash: isRm ? [3,3] : [],
    pointRadius: dados.map(p => p.l ? 3 : 0),
    pointBackgroundColor: dados.map(p => corTipo(cat, p.p)),
    pointHoverRadius: dados.map(p => p.l ? 7 : 0),
    tension: 0,
    fill: false,
    segment: {
      borderColor: ctx2 => {
        const p = dados[ctx2.p0DataIndex];
        return corTipo(cat, p ? p.p : '');
      }
    }
  };
}

const datasets = ramosVisiveis.map(nome => buildDataset(nome, DADOS.curvas[nome]));

const chart = new Chart(ctx, {
  type: 'line',
  data: { datasets },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'nearest', intersect: true },
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
    scales: {
      x: {
        type: 'linear',
        grid: { color: 'rgba(255,255,255,.06)' },
        ticks: {
          color: '#8892A4', font: { size: 10 },
          callback: v => v % 2000 === 0 ? (v/1000).toFixed(0) + 'km' : '',
          autoSkip: false, maxTicksLimit: 15
        },
        title: { display: true, text: 'Posição no eixo (m)', color: '#8892A4', font: { size: 10 } }
      },
      y: {
        grid: { color: 'rgba(255,255,255,.06)' },
        ticks: {
          color: '#8892A4', font: { size: 10 },
          callback: v => Math.abs(v) >= 1000 ? (v/1000).toFixed(0) + 'k' : v
        },
        title: { display: true, text: 'Vol. acumulado (m³)', color: '#8892A4', font: { size: 10 } }
      }
    },
    animation: { duration: 300 }
  },
  plugins: [
    {
      id: 'hidden',
      beforeDraw(ch) {
        ch.data.datasets.forEach((ds, i) => {
          ds.hidden = !vis[ramosVisiveis[i]];
        });
      }
    },
    {
      id: 'zero',
      beforeDraw(ch) {
        const y = ch.scales.y.getPixelForValue(0);
        const c = ch.ctx; c.save();
        c.strokeStyle = 'rgba(255,255,255,.15)';
        c.lineWidth = 1.5; c.setLineDash([6,4]);
        c.beginPath(); c.moveTo(ch.chartArea.left, y); c.lineTo(ch.chartArea.right, y); c.stroke();
        c.restore();
      }
    },
    {
      id: 'ints',
      afterDraw(ch) {
        if (!vis['ints'] || !DADOS.ints.length) return;
        const xs = ch.scales.x;
        const {top, bottom} = ch.chartArea;
        const c = ch.ctx; c.save();
        DADOS.ints.forEach(int => {
          const x = xs.getPixelForValue(int.pos);
          c.strokeStyle = INT_CORES[int.cat] || '#D85A30';
          c.lineWidth = 1.2; c.setLineDash([5,3]);
          c.beginPath(); c.moveTo(x, top+14); c.lineTo(x, bottom); c.stroke();
          c.fillStyle = INT_CORES[int.cat] || '#D85A30';
          c.font = '8px Segoe UI, sans-serif'; c.textAlign = 'center';
          c.fillText(int.nome, x, top + 10);
        });
        c.restore();
      }
    }
  ]
});

// ── TOOLTIP ──────────────────────────────────────────────────────────────
const tt  = document.getElementById('tt');
const cvEl = document.getElementById('cv');

function showTT(e, dot, head, rows, flows) {
  const rect = cvEl.getBoundingClientRect();
  document.getElementById('td').style.background = dot;
  document.getElementById('tl').textContent = head;
  ['tr1','tr2','tr3','tr4'].forEach((id, i) => {
    const el = document.getElementById(id);
    if(rows[i]) { el.innerHTML = rows[i]; el.style.display = ''; }
    else { el.textContent = ''; el.style.display = 'none'; }
  });
  const ts = document.getElementById('ts');
  const tf = document.getElementById('tf');
  if(flows) { ts.style.display = 'block'; tf.innerHTML = flows; }
  else       { ts.style.display = 'none';  tf.innerHTML = ''; }
  let lx = e.clientX - rect.left + 14;
  let ly = e.clientY - rect.top - 80;
  if(lx + 260 > rect.width) lx = e.clientX - rect.left - 260;
  tt.style.left = lx + 'px';
  tt.style.top  = Math.max(2, ly) + 'px';
  tt.style.display = 'block';
}

cvEl.addEventListener('mousemove', e => {
  const rect = cvEl.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const xs = chart.scales.x;

  // Hover sobre interseção
  if(vis['ints']) {
    for(const int of DADOS.ints) {
      const ix = xs.getPixelForValue(int.pos);
      if(Math.abs(mx - ix) < 10 && my < chart.chartArea.top + 30) {
        showTT(e, INT_CORES[int.cat]||'#D85A30', int.nome,
          [`Pos: ${(int.pos/1000).toFixed(2)} km`, '', '', ''], null);
        return;
      }
    }
  }

  // Hover sobre ponto da curva
  const pts = chart.getElementsAtEventForMode(e, 'nearest', {intersect:true, radius:8}, true);
  if(!pts.length) { tt.style.display = 'none'; return; }
  const {datasetIndex: di, index: idx} = pts[0];
  const p = chart.data.datasets[di].data[idx];
  if(!p || !p.l) { tt.style.display = 'none'; return; }

  const cat = p._r || catRamo(chart.data.datasets[di].label);
  const cor = corTipo(cat, p.p);
  const nomeRamo = chart.data.datasets[di].label
    .replace('SEGB ','').replace('REMOÇÃO','Remoção');
  const tipoNome = TIPO_NOME[p.p] || p.p || '—';
  const sinalVol = (p.p==='CA'||p.p==='CF') ? '−' : '+';

  const rows = [
    `Tipo: <b>${tipoNome}</b> (${p.p || '—'})`,
    `Pos: <b>${(p.x/1000).toFixed(3)} km</b>`,
    p.v ? `Vol. trecho: <b>${sinalVol}${fv(p.v)} m³</b>` : '',
    `Vol. acumulado: <b>${fv(p.y)} m³</b>`,
  ];

  let fl = '';
  if(p.s && p.s.length) {
    fl += `<div class="tt-fh">→ Destinos:</div>`;
    p.s.slice(0,5).forEach(f => {
      fl += `<div class="tt-f"><b>${f.dest||f.d}</b> — ${fv(f.vol||f.v)} m³ · ${(f.dmt||0).toFixed(3)} km</div>`;
    });
    if(p.s.length > 5) fl += `<div class="tt-f">+${p.s.length-5} mais…</div>`;
  }
  if(p.e && p.e.length) {
    fl += `<div class="tt-fh" style="margin-top:3px">← Origens:</div>`;
    p.e.slice(0,5).forEach(f => {
      fl += `<div class="tt-f"><b>${f.orig||f.o}</b> — ${fv(f.vol||f.v)} m³ · ${(f.dmt||0).toFixed(3)} km</div>`;
    });
    if(p.e.length > 5) fl += `<div class="tt-f">+${p.e.length-5} mais…</div>`;
  }

  showTT(e, cor, `${p.l} · ${nomeRamo}`, rows, fl || null);
});

cvEl.addEventListener('mouseleave', () => { tt.style.display = 'none'; });
</script>
</body>
</html>
"""


def _gerar_html(dados_viz: dict) -> str:
    """Gera o HTML completo com os dados embutidos como JSON."""
    dados_json = json.dumps(dados_viz, ensure_ascii=False, separators=(',', ':'))
    return _HTML_TEMPLATE.replace('__DADOS_JSON__', dados_json)


# ---------------------------------------------------------------------------
# Janela Tkinter com tkinterweb
# ---------------------------------------------------------------------------

class JanelaBruckner(tk.Toplevel):
    """
    Janela independente que exibe o Diagrama de Massas via tkinterweb.
    Pode ser aberta em qualquer ponto do programa passando dados_viz.
    """

    def __init__(self, master, dados_viz: dict, titulo: str = "Diagrama de Massas"):
        super().__init__(master)
        self.title(f"⬡ {titulo}")
        self.configure(bg=COR_BG)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = min(1200, sw - 60), min(860, sh - 60)
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(True, True)

        # Barra de topo
        tk.Frame(self, bg=COR_ACCENT, height=4).pack(fill="x")
        top = tk.Frame(self, bg=COR_PAINEL)
        top.pack(fill="x")
        tk.Label(top, text="⬡  TERRAPLENAGEM", font=("Segoe UI", 9, "bold"),
                 fg=COR_ACCENT, bg=COR_PAINEL).pack(side="left", padx=16, pady=8)
        tk.Label(top, text=titulo.upper(), font=("Segoe UI", 9, "bold"),
                 fg="#8892A4", bg=COR_PAINEL).pack(side="right", padx=16)
        tk.Frame(self, bg=COR_BORDA, height=1).pack(fill="x")

        # Tentar carregar tkinterweb
        # No Windows, tkinterweb não carrega scripts externos (CDN)
        # Por isso usamos o browser como padrão e tkinterweb apenas se
        # o HTML for auto-contido (sem CDN)
        self._fallback_browser(dados_viz, titulo)

    def _fallback_browser(self, dados_viz: dict, titulo: str):
        """Salva HTML temporário e abre no navegador padrão."""
        import tempfile
        import webbrowser

        html = _gerar_html(dados_viz)
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False,
            encoding='utf-8', prefix='bruckner_'
        )
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name.replace(os.sep, '/')}")

        # Fechar a janela Tk vazia — o browser é suficiente
        self.after(100, self.destroy)


# ---------------------------------------------------------------------------
# Funções públicas — pontos de entrada do programa
# ---------------------------------------------------------------------------

def abrir_pre_distribuicao(resultados: list, config_dist, master: tk.Misc):
    """
    Abre o Diagrama de Massas no estado pré-distribuição.

    Parâmetros:
        resultados:  lista de ResultadoDeteccao (saída de detectar_trechos)
        config_dist: ConfigDistribuicao (para as relações/interseções)
        master:      janela Tk pai
    """
    try:
        dados_viz = _dados_do_resultados(resultados, config_dist)
        JanelaBruckner(master, dados_viz,
                       titulo="Diagrama de Massas — Pré-distribuição")
    except Exception as ex:
        import traceback
        messagebox.showerror("Erro — Brückner",
                             f"{ex}\n\n{traceback.format_exc()}", parent=master)


def abrir_pos_distribuicao(caminho_json: str, master: tk.Misc):
    """
    Abre o Diagrama de Massas no estado pós-distribuição.

    Parâmetros:
        caminho_json: caminho para o JSON salvo pela Janela7Gerar
        master:       janela Tk pai
    """
    try:
        caminho_json = os.path.normpath(caminho_json)
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        dados_viz = _dados_do_json(dados, 'pos')
        JanelaBruckner(master, dados_viz,
                       titulo="Diagrama de Massas — Pós-distribuição")
    except Exception as ex:
        import traceback
        messagebox.showerror("Erro — Brückner",
                             f"{ex}\n\n{traceback.format_exc()}", parent=master)


def abrir_pos_redistribuicao(caminho_json: str, master: tk.Misc):
    """
    Abre o Diagrama de Massas no estado pós-redistribuição.

    Parâmetros:
        caminho_json: caminho para o JSON redistribuído
                      ({nome}_redistribuido.json)
        master:       janela Tk pai
    """
    try:
        caminho_json = os.path.normpath(caminho_json)
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        dados_viz = _dados_do_json(dados, 'pos_redist')
        JanelaBruckner(master, dados_viz,
                       titulo="Diagrama de Massas — Pós-redistribuição")
    except Exception as ex:
        import traceback
        messagebox.showerror("Erro — Brückner",
                             f"{ex}\n\n{traceback.format_exc()}", parent=master)