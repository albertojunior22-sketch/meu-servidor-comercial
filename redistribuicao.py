"""
redistribuicao.py (v2)
----------------------
Redistribuição de material entre segmentos usando Stepping-Stone global.

NOVIDADES v2:
- RelacaoSegmento: posicionamento físico real (extensão + deslocamento)
- Matriz global: BFs de TODOS os segmentos vs déficits de TODOS os segmentos
- Também analisa cortes com DMT alta que podem melhorar indo para outro segmento
- Filtro de material inservível (corte_somente_bf=True)
- Filtro de BF sem cadastro (sem posição definida = não entra na matriz)
- DMT calculada pela posição do CORTE ORIGINAL, não do BF
- Origem nas linhas = corte real (não o BF)
- BF reduz no segmento origem
- Flags corretas: vai_para e vem_do
- Versões automáticas ao salvar
"""

import json
import os
import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from algoritmo_transporte import resolver_transporte

INFINITO = 1_000_000_000.0
EPSILON  = 1e-6
DMT_MINIMA = 0.050


# ---------------------------------------------------------------------------
# Relação entre segmentos — v2
# ---------------------------------------------------------------------------

@dataclass
class RelacaoSegmento:
    """
    Posiciona dois segmentos no mesmo espaço físico para cálculo de DMT.

    A ordem (seg_a, seg_b) define quem vem primeiro fisicamente.
    seg_a vem antes de seg_b.

    extensao_a_m:   extensão total do segmento A em metros
    extensao_b_m:   extensão total do segmento B em metros
    deslocamento_m: deslocamento em metros entre o fim de A e o início de B.
                    0 = B começa exatamente onde A termina.
                    Positivo = há um gap entre eles.
                    Negativo = B começa antes do fim de A (sobreposição).
    afastamento_m:  distância lateral entre os eixos dos dois segmentos.
    usar_c1/c2/c3:  quais categorias de material são permitidas na redistribuição.
    """
    seg_a:          str
    seg_b:          str
    extensao_a_m:   float = 0.0
    extensao_b_m:   float = 0.0
    deslocamento_m: float = 0.0
    afastamento_m:  float = 0.0
    usar_c1:        bool  = True
    usar_c2:        bool  = False
    usar_c3:        bool  = False

    def calcular_dmt(self,
                     cmv_a: float, estaca_ini_a: float, deslocamento_ramo_a: float,
                     cmv_b: float, estaca_ini_b: float, deslocamento_ramo_b: float) -> float:
        """
        Calcula DMT entre um corte do seg_a e um aterro do seg_b usando
        posição física relativa.

        pos_fisica = cmv - estaca_ini_ramo + deslocamento_ramo
        Para passar de seg_a para seg_b:
          pos_fisica_b_no_sistema_a = pos_fisica_b + extensao_a + deslocamento
        """
        pos_a = cmv_a - estaca_ini_a + deslocamento_ramo_a
        pos_b = cmv_b - estaca_ini_b + deslocamento_ramo_b
        # Converter pos_b para o sistema de referência de A
        pos_b_no_sistema_a = pos_b + self.extensao_a_m + self.deslocamento_m
        dist = abs(pos_a - pos_b_no_sistema_a) / 1000.0
        af   = self.afastamento_m / 1000.0
        return max(round(dist + af, 6), DMT_MINIMA)

    def calcular_dmt_inv(self,
                         cmv_b: float, estaca_ini_b: float, deslocamento_ramo_b: float,
                         cmv_a: float, estaca_ini_a: float, deslocamento_ramo_a: float) -> float:
        """Direção inversa: seg_b → seg_a."""
        return self.calcular_dmt(cmv_a, estaca_ini_a, deslocamento_ramo_a,
                                  cmv_b, estaca_ini_b, deslocamento_ramo_b)


# ---------------------------------------------------------------------------
# Segmento para redistribuição
# ---------------------------------------------------------------------------

@dataclass
class SegmentoRedist:
    nome:          str
    caminho_json:  str
    dados_json:    dict = field(default_factory=dict)
    # BFs com cadastro de posição (candidatos à redistribuição)
    bota_foras:    List[dict] = field(default_factory=list)
    # BFs sem cadastro (ficam onde estão)
    bota_foras_sem_cadastro: List[dict] = field(default_factory=list)
    # Aterros com déficit
    deficits:      List[dict] = field(default_factory=list)
    # Cortes alocados em aterros (candidatos a melhorar DMT)
    cortes_em_aterro: List[dict] = field(default_factory=list)
    ramos:         List[str]  = field(default_factory=list)
    # Info de estaca_ini por ramo (para posição física — pistas paralelas)
    estaca_ini_por_ramo:    Dict[str, float] = field(default_factory=dict)
    deslocamento_por_ramo:  Dict[str, float] = field(default_factory=dict)
    # Posição de interseções no eixo de referência (para intersecao_marginal)
    # pos_relativa_por_ramo[ramo] = posição física da interseção no eixo principal
    pos_relativa_por_ramo:  Dict[str, float] = field(default_factory=dict)
    dmt_fixa_por_ramo:      Dict[str, float] = field(default_factory=dict)
    eixo_ref_por_ramo:      Dict[str, str]   = field(default_factory=dict)
    # Override de categorias aceitas por ramo (configurado na janela de redistribuição)
    # Ex: {'INT 05_Eixo 5400': {'aceita_c2': True, 'aceita_c3': True}}
    config_ramos: Dict[str, dict] = field(default_factory=dict)
    # BFs e AEs cadastrados na janela de redistribuição (por segmento)
    bota_foras_redist:  List = field(default_factory=list)
    emprestimos_redist: List = field(default_factory=list)
    # Dados brutos da tabela (listas de strings) para preservar entre aberturas
    _dados_bf: List = field(default_factory=list)
    _dados_ae: List = field(default_factory=list)


@dataclass
class LocalAuxiliarRedist:
    """BF ou AE cadastrado na janela de redistribuição."""
    nome:          str
    tipo:          str        # 'BF' ou 'AE'
    segmento:      str        # nome do segmento ao qual está associado
    eixo_ref:      str        # ramo de referência para calcular posição
    pos_relativa_m: float     # posição em relação ao início do eixo_ref
    afastamento_m:  float     # afastamento lateral em metros
    capacidade:    float      # volume disponível (BF) ou necessário (AE)
    fh:            float = 1.0
    cmv_label:     str   = "" # informativo — aparece na coluna CMv da planilha


def carregar_segmento(caminho_json: str) -> SegmentoRedist:
    """
    Carrega um JSON de distribuição e extrai BFs, déficits e cortes.

    Regras:
    - BF com cadastro de posição → candidato à redistribuição
    - BF sem cadastro (pos_relativa=0 e estaca_m=0) → fica onde está
    - Material inservível (material_inservivel=True) → nunca redistribui
    - Déficit = linha com label_origem=AE* e dmt_total=0
    """
    with open(caminho_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    nome = dados.get('nome', os.path.basename(caminho_json))
    seg  = SegmentoRedist(nome=nome, caminho_json=caminho_json, dados_json=dados)
    seg.ramos = list(dict.fromkeys(r['nome'] for r in dados.get('ramos', [])))

    # Extrair posição física de cada ramo usando as relações do config_dist
    # Para pistas_paralelas: usa estaca_ini_a_m e estaca_ini_b_m
    # Para intersecao_marginal: ramo_a é o eixo (pos_relativa_m é sua posição no eixo)
    #   → ramos da interseção têm pos_relativa_m como referência no eixo principal
    # Isso permite calcular a posição física correta de qualquer ramo no sistema global

    # Primeiro: popular eixos principais (pistas_paralelas)
    for rel in dados.get('config_dist', {}).get('relacoes', []):
        tipo = rel.get('tipo', '')
        if tipo == 'pistas_paralelas':
            ra = rel.get('ramo_a', '')
            rb = rel.get('ramo_b', '')
            if ra:
                seg.estaca_ini_por_ramo[ra]   = rel.get('estaca_ini_a_m', 0.0)
                seg.deslocamento_por_ramo[ra] = rel.get('deslocamento_a_m', 0.0)
            if rb:
                seg.estaca_ini_por_ramo[rb]   = rel.get('estaca_ini_b_m', 0.0)
                seg.deslocamento_por_ramo[rb] = rel.get('deslocamento_b_m', 0.0)

    # Segundo: popular interseções/marginais usando pos_relativa_m
    # Para intersecao_marginal: ramo_b (e ramos_todos) têm posição fisica = pos_relativa_m
    # A posição do ramo de interseção no sistema do segmento = pos_relativa_m
    # (medida no eixo de referência ramo_a, que tem ei conhecido)
    # O _get_estaca_info retornará (0.0, 0.0) para esses ramos — correto,
    # pois o cmv deles é medido desde o zero do próprio ramo (interseção)
    # e a posição global é calculada via pos_relativa_m da relação
    # 
    # Precisamos guardar pos_relativa_m por ramo para usar no cálculo de DMT
    for rel in dados.get('config_dist', {}).get('relacoes', []):
        tipo = rel.get('tipo', '')
        if tipo == 'intersecao_marginal':
            pos_rel = rel.get('pos_relativa_m', 0.0)
            dmt_fixa = rel.get('dmt_fixa_km', 0.0)
            # eixo de referência (ramo_a): ei_a_m é sua estaca_ini no eixo
            ra = rel.get('ramo_a', '')
            ei_eixo = rel.get('estaca_ini_a_m', 0.0)
            # Guardar pos_relativa para cada ramo da interseção
            # usando um prefixo especial para distinguir de estaca_ini
            ramos_int = [rel.get('ramo_b', '')] if not rel.get('todos') else rel.get('ramos_todos', [])
            for ramo_int in ramos_int:
                if ramo_int:
                    # pos_relativa_m = posição no eixo principal onde a interseção ocorre
                    # ei_eixo = estaca_ini do eixo (geralmente 0 para interseções)
                    # pos_fisica_intersecao = pos_relativa_m - ei_eixo
                    seg.estaca_ini_por_ramo[ramo_int]   = 0.0   # cmv do ramo é local
                    seg.deslocamento_por_ramo[ramo_int] = 0.0
                    # Guardar pos_relativa no eixo para usar no encadeamento
                    if not hasattr(seg, 'pos_relativa_por_ramo'):
                        seg.pos_relativa_por_ramo = {}
                        seg.dmt_fixa_por_ramo = {}
                        seg.eixo_ref_por_ramo = {}
                    seg.pos_relativa_por_ramo[ramo_int] = pos_rel - ei_eixo
                    seg.dmt_fixa_por_ramo[ramo_int]     = dmt_fixa
                    seg.eixo_ref_por_ramo[ramo_int]     = ra

    for ramo_data in dados.get('ramos', []):
        ramo_nome = ramo_data['nome']
        for linha in ramo_data.get('linhas_qdm', []):
            vol = linha.get('vol_total', 0)
            if vol <= EPSILON:
                continue

            inservivel = linha.get('material_inservivel', False)

            # --- BF ---
            if linha['tipo_destino'] == 'BF':
                if inservivel:
                    continue  # material inservível nunca redistribui

                # Posição = CMv do CORTE ORIGINAL (sempre disponível)
                cmv_m = _label_para_metros(linha['cmv_origem'], dados)
                label_bf = linha['label_destino']

                bf_info = {
                    'label_corte':        linha['label_origem'],
                    'estaca_ini_origem':  linha.get('estaca_ini_origem', ''),
                    'cmv_label':          linha['cmv_origem'],
                    'estaca_fin_origem':  linha.get('estaca_fin_origem', ''),
                    'cmv_m':              cmv_m,  # posição do corte original
                    'label_bf':           label_bf,
                    'vol_disponivel':     vol,
                    'vol_original':       vol,
                    'vol_c1':             linha.get('vol_c1', 0),
                    'vol_c2':             linha.get('vol_c2', 0),
                    'vol_c3':             linha.get('vol_c3', 0),
                    'ramo':               ramo_nome,
                    'tem_cadastro':       True,  # sempre entra na redistribuição
                }
                # Todo BF entra — posição é a do corte original
                seg.bota_foras.append(bf_info)

            # --- Déficit (AE sem DMT) ---
            elif (linha['label_origem'].startswith('AE') and
                  linha.get('dmt_total', 0) == 0.0):
                cmv_m = _label_para_metros(linha['cmv_destino'], dados)
                # Buscar restrições de categoria deste ramo
                aceita_c1 = True; aceita_c2 = True; aceita_c3 = True
                prio = False
                for r in dados.get('restricoes', {}).get('restricoes', []):
                    if r['ramo'] == ramo_nome:
                        aceita_c1 = r.get('aterro_aceita_c1', True)
                        aceita_c2 = r.get('aterro_aceita_c2', True)
                        aceita_c3 = r.get('aterro_aceita_c3', True)
                        prio      = r.get('prioridade_c3_c2_c1', False)
                        break
                seg.deficits.append({
                    'label_aterro':       linha['label_destino'],
                    'estaca_ini_destino': linha.get('estaca_ini_destino', ''),
                    'cmv_label':          linha['cmv_destino'],
                    'estaca_fin_destino': linha.get('estaca_fin_destino', ''),
                    'cmv_m':              cmv_m,
                    'categoria':          linha['tipo_destino'],
                    'ramo':               ramo_nome,
                    'label_ae':           linha['label_origem'],
                    'vol_deficit':        vol,
                    'vol_original':       vol,
                    'aceita_c1':          aceita_c1,
                    'aceita_c2':          aceita_c2,
                    'aceita_c3':          aceita_c3,
                    'prioridade_c3_c2_c1': prio,
                    '_aceita_c2_orig':    aceita_c2,  # guardar original para override
                    '_aceita_c3_orig':    aceita_c3,
                })

    vol_bf  = sum(b['vol_disponivel'] for b in seg.bota_foras)
    vol_bfs = sum(b['vol_disponivel'] for b in seg.bota_foras_sem_cadastro)
    vol_ae  = sum(d['vol_deficit']    for d in seg.deficits)
    print(f"Segmento '{nome}':")
    print(f"  BF com cadastro:  {len(seg.bota_foras)} ({vol_bf:,.0f} m³)")
    print(f"  BF sem cadastro:  {len(seg.bota_foras_sem_cadastro)} ({vol_bfs:,.0f} m³) — fixos")
    print(f"  Déficits:         {len(seg.deficits)} ({vol_ae:,.0f} m³)")
    return seg


def _label_para_metros(label: str, dados: dict) -> float:
    try:
        unidade     = dados.get('config_leitura', {}).get('unidade', 'estaca')
        dist_estaca = dados.get('config_leitura', {}).get('dist_estaca', 20.0)
        label = str(label).replace(',', '.')
        if '+' in label:
            partes  = label.replace('K', '').split('+')
            inteiro = float(partes[0])
            decimal = float(partes[1]) if len(partes) > 1 else 0.0
            if unidade == 'estaca':
                return inteiro * dist_estaca + decimal * dist_estaca / 100
            else:
                return inteiro * 1000 + decimal
        return float(label)
    except Exception:
        return 0.0


def _get_estaca_info(ramo: str, seg: SegmentoRedist) -> Tuple[float, float]:
    """Retorna (estaca_ini, deslocamento) do ramo no segmento."""
    return (
        seg.estaca_ini_por_ramo.get(ramo, 0.0),
        seg.deslocamento_por_ramo.get(ramo, 0.0),
    )


# ---------------------------------------------------------------------------
# Redistribuição principal
# ---------------------------------------------------------------------------

def redistribuir(
        segmentos: List[SegmentoRedist],
        relacoes:  List[RelacaoSegmento]
) -> Dict[str, List[dict]]:
    """
    Redistribuição global usando Stepping-Stone.

    Matriz:
    - Origens: BFs com cadastro de TODOS os segmentos
    - Destinos: déficits de TODOS os segmentos
    - Custo: DMT do CORTE ORIGINAL até o aterro (posição física relativa)
    - BFs sem cadastro: não entram na matriz
    - Material inservível: filtrado no carregar_segmento
    """
    # Coletar BFs com cadastro de todos os segmentos
    todos_bfs = []
    for seg in segmentos:
        for bf in seg.bota_foras:
            todos_bfs.append({**bf, 'segmento': seg.nome, '_seg': seg})

    # Coletar déficits de todos os segmentos
    todos_def = []
    for seg in segmentos:
        for d in seg.deficits:
            todos_def.append({**d, 'segmento': seg.nome, '_seg': seg})

    if not todos_bfs and not todos_def:
        print("Nada a redistribuir (sem BF cadastrado ou sem déficit).")
        return {seg.nome: [] for seg in segmentos}

    # Coletar AEs da redistribuição — entram como ORIGENS (fornecem material)
    todos_aes_redist = []
    for seg in segmentos:
        for ae in seg.emprestimos_redist:
            todos_aes_redist.append({
                'label_ae':       ae.nome,
                'cmv_label':      str(ae.pos_relativa_m),
                'cmv_m':          ae.pos_relativa_m,  # posição física direta
                'ramo':           ae.eixo_ref,
                'vol_disponivel': ae.capacidade * (1.0 / ae.fh if ae.fh > 0 else 1.0),  # Fh aplicado
                'vol_original':   ae.capacidade * (1.0 / ae.fh if ae.fh > 0 else 1.0),
                'segmento':       seg.nome,
                '_seg':           seg,
                '_ae_redist':     True,
            })

    # Coletar BFs da redistribuição — entram como DESTINOS (recebem material)
    todos_bfs_redist = []
    for seg in segmentos:
        for bf_r in seg.bota_foras_redist:
            todos_bfs_redist.append({
                'label_bf':       bf_r.nome,
                'cmv_label':      str(bf_r.pos_relativa_m),
                'cmv_m':          bf_r.pos_relativa_m,  # posição física direta
                'ramo':           bf_r.eixo_ref,
                'vol_disponivel': bf_r.capacidade,
                'vol_original':   bf_r.capacidade,
                'segmento':       seg.nome,
                '_seg':           seg,
                '_bf_redist':     True,
            })

    print(f"\n--- Redistribuição Global ---")
    print(f"  BF cortes:   {len(todos_bfs)} ({sum(b['vol_disponivel'] for b in todos_bfs):,.0f} m³)")
    print(f"  BF externos: {len(todos_bfs_redist)} ({sum(b['vol_disponivel'] for b in todos_bfs_redist):,.0f} m³)")
    print(f"  AE externos: {len(todos_aes_redist)} ({sum(a['vol_disponivel'] for a in todos_aes_redist):,.0f} m³)")
    print(f"  Déficits:    {len(todos_def)} ({sum(d['vol_deficit'] for d in todos_def):,.0f} m³)")

    linhas_por_seg: Dict[str, List[dict]] = {seg.nome: [] for seg in segmentos}

    # Mapa de segmentos para acesso rápido
    segmentos_map = {seg.nome: seg for seg in segmentos}

    def _pos_fisica(item, seg_obj):
        """Retorna posição física do item em metros no sistema do segmento.
        
        Para BF/AE externos (LocalAuxiliarRedist): usa pos_relativa_m diretamente.
        Para interseções/marginais: usa pos_relativa_por_ramo (posição no eixo principal).
        Para pistas paralelas: usa cmv_m - estaca_ini + deslocamento.
        """
        if item.get('_bf_redist') or item.get('_ae_redist'):
            return item['cmv_m']  # pos_relativa_m já é posição física no segmento

        ramo = item['ramo']

        # Interseção/marginal: posição física = pos_relativa no eixo principal
        if ramo in seg_obj.pos_relativa_por_ramo:
            return seg_obj.pos_relativa_por_ramo[ramo]

        # Pista paralela: posição física = cmv - estaca_ini + deslocamento
        ei, desloc = _get_estaca_info(ramo, seg_obj)
        return item['cmv_m'] - ei + desloc

    def _dmt_fixa_ramo(ramo, seg_obj):
        """Retorna dmt_fixa (afastamento lateral) do ramo em km."""
        return seg_obj.dmt_fixa_por_ramo.get(ramo, 0.0)

    def _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos, permitir_mesmo_seg=False):
        """Calcula DMT entre BF (corte original) e déficit usando encadeamento."""
        seg_orig_obj = bf['_seg']
        seg_dest_obj = deficit['_seg']

        # dmt_fixa dos ramos (afastamento lateral de interseções)
        dmt_fixa_orig = _dmt_fixa_ramo(bf['ramo'], seg_orig_obj)
        dmt_fixa_dest = _dmt_fixa_ramo(deficit['ramo'], seg_dest_obj)
        dmt_fixa = max(dmt_fixa_orig, dmt_fixa_dest)

        if bf['segmento'] == deficit['segmento']:
            if not permitir_mesmo_seg:
                return INFINITO
            pos_bf  = _pos_fisica(bf,      seg_orig_obj)
            pos_def = _pos_fisica(deficit, seg_dest_obj)
            dmt = max(round(abs(pos_bf - pos_def) / 1000.0 + dmt_fixa, 6), DMT_MINIMA)
            return dmt

        ei_orig, desloc_orig = _get_estaca_info(bf['ramo'], seg_orig_obj) \
                               if bf['ramo'] not in seg_orig_obj.pos_relativa_por_ramo else (0.0, 0.0)
        ei_dest, desloc_dest = _get_estaca_info(deficit['ramo'], seg_dest_obj) \
                               if deficit['ramo'] not in seg_dest_obj.pos_relativa_por_ramo else (0.0, 0.0)

        # Para interseções: usar pos_relativa como cmv efetivo no encadeamento
        cmv_orig = seg_orig_obj.pos_relativa_por_ramo.get(bf['ramo'], bf['cmv_m'] - ei_orig + desloc_orig)
        cmv_dest = seg_dest_obj.pos_relativa_por_ramo.get(deficit['ramo'], deficit['cmv_m'] - ei_dest + desloc_dest)

        dmt_var = _calcular_dmt_encadeada(
            bf['segmento'], cmv_orig, 0.0, 0.0,
            deficit['segmento'], cmv_dest, 0.0, 0.0,
            relacoes, segmentos_map)
        if dmt_var >= INFINITO:
            return INFINITO
        return max(round(dmt_var + dmt_fixa, 6), DMT_MINIMA)

    def _calcular_dmt_ae_deficit(ae, deficit, relacoes):
        """Calcula DMT entre AE externo e déficit usando encadeamento."""
        seg_dest_obj = deficit['_seg']
        dmt_fixa_dest = _dmt_fixa_ramo(deficit['ramo'], seg_dest_obj)
        # Déficit: usar pos_relativa se interseção, senão cmv com ei
        cmv_dest = seg_dest_obj.pos_relativa_por_ramo.get(
            deficit['ramo'],
            deficit['cmv_m'] - _get_estaca_info(deficit['ramo'], seg_dest_obj)[0])
        dmt_var = _calcular_dmt_encadeada(
            ae['segmento'], ae['cmv_m'], 0.0, 0.0,
            deficit['segmento'], cmv_dest, 0.0, 0.0,
            relacoes, segmentos_map)
        if dmt_var >= INFINITO:
            return INFINITO
        return max(round(dmt_var + dmt_fixa_dest, 6), DMT_MINIMA)

    def _calcular_dmt_bf_bfredist(bf, bf_redist, relacoes):
        """Calcula DMT entre corte original e BF externo de destino."""
        seg_orig_obj = bf['_seg']
        dmt_fixa_orig = _dmt_fixa_ramo(bf['ramo'], seg_orig_obj)
        cmv_orig = seg_orig_obj.pos_relativa_por_ramo.get(
            bf['ramo'],
            bf['cmv_m'] - _get_estaca_info(bf['ramo'], seg_orig_obj)[0])
        dmt_var = _calcular_dmt_encadeada(
            bf['segmento'], cmv_orig, 0.0, 0.0,
            bf_redist['segmento'], bf_redist['cmv_m'], 0.0, 0.0,
            relacoes, segmentos_map)
        if dmt_var >= INFINITO:
            return INFINITO
        return max(round(dmt_var + dmt_fixa_orig, 6), DMT_MINIMA)

    def _cat_permitida(bf, deficit, relacoes):
        """Verifica se a categoria do BF é permitida para este déficit."""
        cat = _categoria_bf(bf)
        # Verificar restrição do aterro
        if cat == 'C3' and not deficit.get('aceita_c3', True): return False
        if cat == 'C2' and not deficit.get('aceita_c2', True): return False
        if cat == 'C1' and not deficit.get('aceita_c1', True): return False
        # Verificar materiais permitidos em alguma relação no caminho
        # Usa a primeira relação direta encontrada; para encadeado, usa qualquer caminho
        rel = _buscar_relacao_segmento(bf['segmento'], deficit['segmento'], relacoes)
        if rel is not None:
            if cat == 'C3' and not rel.usar_c3: return False
            if cat == 'C2' and not rel.usar_c2: return False
            if cat == 'C1' and not rel.usar_c1: return False
        else:
            # Sem relação direta — verificar se há caminho encadeado
            # Nesse caso, verificar os materiais nas relações do caminho
            # Simplificação: se há caminho (DMT < INFINITO), permite
            pass
        return True

    # Aplicar config_ramos (override de aceita_c2/c3 por ramo para redistribuição)
    # Para ramos normais: override via config_ramos
    # Para ramos prioritários: as categorias marcadas na relação (usar_c1/c2/c3)
    #   sobrepõem o aceita_c1/c2 do JSON original
    usar_c1_global = any(r.usar_c1 for r in relacoes)
    usar_c2_global = any(r.usar_c2 for r in relacoes)
    usar_c3_global = any(r.usar_c3 for r in relacoes)

    for deficit in todos_def:
        seg = deficit['_seg']
        cfg_ramo = seg.config_ramos.get(deficit['ramo'], {})
        if deficit.get('prioridade_c3_c2_c1', False):
            # Prioritários: override pelas categorias marcadas na redistribuição
            if usar_c1_global: deficit['aceita_c1'] = True
            if usar_c2_global: deficit['aceita_c2'] = True
            if usar_c3_global: deficit['aceita_c3'] = True
        else:
            # Normais: override via config_ramos
            if cfg_ramo.get('aceita_c2'): deficit['aceita_c2'] = True
            if cfg_ramo.get('aceita_c3'): deficit['aceita_c3'] = True

    # Separar déficits com e sem prioridade
    defs_prio   = [d for d in todos_def if d.get('prioridade_c3_c2_c1', False)]
    defs_normal = [d for d in todos_def if not d.get('prioridade_c3_c2_c1', False)]

    CUSTO_FICTICIO = 9999.0  # custo alto para forçar alocação real

    # --- FASE 1: Stepping-Stone por categoria para déficits com prioridade ---
    # Roda C3 global → C2 global → C1 global
    # BFs do próprio segmento ENTRAM na matriz (menor DMT vence)
    # Déficits normais ficam fora até a FASE 2
    if defs_prio:
        print(f"\n--- FASE 1: Stepping-Stone prioritário C3→C2→C1 ({len(defs_prio)} déficits) ---")
        for cats in ['C3', 'C2', 'C1']:
            bfs_cat = [b for b in todos_bfs
                       if _categoria_bf(b) == cats and b['vol_disponivel'] > EPSILON]
            defs_cat = [d for d in defs_prio
                        if d['vol_deficit'] > EPSILON and d.get(f'aceita_{cats.lower()}', True)]
            if not bfs_cat or not defs_cat:
                continue

            print(f"  Rodada {cats}: {len(bfs_cat)} BFs × {len(defs_cat)} déficits")
            m1 = len(bfs_cat); n1 = len(defs_cat)
            custos1 = [[INFINITO] * n1 for _ in range(m1)]

            for i, bf in enumerate(bfs_cat):
                for j, deficit in enumerate(defs_cat):
                    if bf['segmento'] == deficit['segmento']:
                        # BF do mesmo segmento: DMT interna
                        dmt = _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos, permitir_mesmo_seg=True)
                        custos1[i][j] = dmt
                    else:
                        # BF de outro segmento: verificar categoria permitida e encadeamento
                        rel = _buscar_relacao_segmento(bf['segmento'], deficit['segmento'], relacoes)
                        if rel is not None:
                            if cats == 'C3' and not rel.usar_c3: continue
                            if cats == 'C2' and not rel.usar_c2: continue
                            if cats == 'C1' and not rel.usar_c1: continue
                        dmt = _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos)
                        if dmt < INFINITO:
                            custos1[i][j] = dmt

            idx_val1 = [i for i in range(m1) if any(custos1[i][j] < INFINITO for j in range(n1))]
            if not idx_val1:
                continue

            idx_map1    = {novo: orig for novo, orig in enumerate(idx_val1)}
            custos_r1   = [custos1[i] for i in idx_val1]
            ofertas1    = [bfs_cat[i]['vol_disponivel'] for i in idx_val1]
            demandas1   = [d['vol_deficit'] for d in defs_cat]

            res1 = resolver_transporte(custos_r1, ofertas1, demandas1,
                                       otimizar=True, custo_ficticio=CUSTO_FICTICIO)
            print(f"    Iterações: {res1.iteracoes} | Custo: {res1.custo_total:,.2f} km·m³")

            n_r1 = len(idx_val1)
            for i, j, vol in res1.alocacoes:
                if vol <= EPSILON or i >= n_r1 or j >= n1: continue
                bf      = bfs_cat[idx_map1[i]]
                deficit = defs_cat[j]
                mesmo_seg = bf['segmento'] == deficit['segmento']
                dmt = _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos,
                                               permitir_mesmo_seg=mesmo_seg)
                if dmt >= INFINITO: continue
                vol = round(min(vol, bf['vol_disponivel']), 4)
                if vol <= EPSILON: continue
                bf['vol_disponivel']   = round(bf['vol_disponivel']   - vol, 4)
                deficit['vol_deficit'] = round(deficit['vol_deficit'] - vol, 4)
                fator  = vol / bf['vol_original'] if bf['vol_original'] > EPSILON else 0
                vol_c1 = round(bf['vol_c1'] * fator, 4)
                vol_c2 = round(bf['vol_c2'] * fator, 4)
                vol_c3 = round(bf['vol_c3'] * fator, 4)
                print(f"    {cats} {bf['label_corte']} ({bf['segmento']}) → "
                      f"{deficit['label_aterro']} ({deficit['segmento']}) "
                      f"vol={vol:,.0f} m³ dmt={dmt:.3f}km"
                      f"{' [próprio seg]' if mesmo_seg else ''}")
                if mesmo_seg:
                    # Alocação interna: não gera linha de redistribuição
                    # Apenas reduz o BF e o déficit — o déficit será zerado
                    # Registrar como alocação interna simples
                    _registrar_alocacao_interna(linhas_por_seg, bf, deficit,
                                                vol, vol_c1, vol_c2, vol_c3, dmt)
                else:
                    _registrar_alocacao(linhas_por_seg, bf, deficit,
                                        vol, vol_c1, vol_c2, vol_c3, dmt)

    # --- FASE 2: Stepping-Stone global para déficits normais (sem prioridade) ---
    # Inclui também déficits prioritários que ainda têm saldo após FASE 1
    defs_fase2 = [d for d in todos_def if d['vol_deficit'] > EPSILON]
    bfs_restantes = [b for b in todos_bfs if b['vol_disponivel'] > EPSILON]

    if bfs_restantes and defs_fase2:
        print(f"\n--- FASE 2: Stepping-Stone global ({len(bfs_restantes)} BFs × {len(defs_fase2)} déficits) ---")
        m2 = len(bfs_restantes); n2 = len(defs_fase2)
        custos2 = [[INFINITO] * n2 for _ in range(m2)]

        for i, bf in enumerate(bfs_restantes):
            for j, deficit in enumerate(defs_fase2):
                if bf['segmento'] == deficit['segmento']: continue
                if not _cat_permitida(bf, deficit, relacoes): continue
                dmt = _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos)
                custos2[i][j] = dmt

        idx_val2 = [i for i in range(m2) if any(custos2[i][j] < INFINITO for j in range(n2))]
        if idx_val2:
            idx_map2    = {novo: orig for novo, orig in enumerate(idx_val2)}
            custos_r2   = [custos2[i] for i in idx_val2]
            ofertas2    = [bfs_restantes[i]['vol_disponivel'] for i in idx_val2]
            demandas2   = [d['vol_deficit'] for d in defs_fase2]

            res2 = resolver_transporte(custos_r2, ofertas2, demandas2,
                                       otimizar=True, custo_ficticio=CUSTO_FICTICIO)
            print(f"  Iterações: {res2.iteracoes} | Custo: {res2.custo_total:,.2f} km·m³")

            n_r2 = len(idx_val2)
            for i, j, vol in res2.alocacoes:
                if vol <= EPSILON or i >= n_r2 or j >= n2: continue
                bf      = bfs_restantes[idx_map2[i]]
                deficit = defs_fase2[j]
                if bf['segmento'] == deficit['segmento']: continue
                dmt = _calcular_dmt_bf_deficit(bf, deficit, relacoes, segmentos)
                if dmt >= INFINITO: continue
                vol = round(min(vol, bf['vol_disponivel']), 4)
                if vol <= EPSILON: continue
                bf['vol_disponivel']   = round(bf['vol_disponivel']   - vol, 4)
                deficit['vol_deficit'] = round(deficit['vol_deficit'] - vol, 4)
                fator  = vol / bf['vol_original'] if bf['vol_original'] > EPSILON else 0
                vol_c1 = round(bf['vol_c1'] * fator, 4)
                vol_c2 = round(bf['vol_c2'] * fator, 4)
                vol_c3 = round(bf['vol_c3'] * fator, 4)
                print(f"  {bf['label_corte']} ({bf['segmento']}) → "
                      f"{deficit['label_aterro']} ({deficit['segmento']}) "
                      f"vol={vol:,.0f} m³ dmt={dmt:.3f}km")
                _registrar_alocacao(linhas_por_seg, bf, deficit, vol, vol_c1, vol_c2, vol_c3, dmt)
    # --- FASE 3: AEs externos → déficits restantes; cortes restantes → BFs externos ---
    defs_restantes = [d for d in todos_def if d['vol_deficit'] > EPSILON]
    bfs_restantes3 = [b for b in todos_bfs if b['vol_disponivel'] > EPSILON]

    if todos_aes_redist and defs_restantes:
        print(f"\n--- FASE 3a: AEs externos ({len(todos_aes_redist)}) → déficits ({len(defs_restantes)}) ---")
        ma = len(todos_aes_redist); na = len(defs_restantes)
        custos_a = [[INFINITO] * na for _ in range(ma)]
        for i, ae in enumerate(todos_aes_redist):
            for j, deficit in enumerate(defs_restantes):
                if not deficit.get('aceita_c1', True): continue  # AE externo é C1 por padrão
                dmt = _calcular_dmt_ae_deficit(ae, deficit, relacoes)
                if dmt < INFINITO:
                    custos_a[i][j] = dmt
        idx_va = [i for i in range(ma) if any(custos_a[i][j] < INFINITO for j in range(na))]
        if idx_va:
            res_a = resolver_transporte(
                [custos_a[i] for i in idx_va],
                [todos_aes_redist[i]['vol_disponivel'] for i in idx_va],
                [d['vol_deficit'] for d in defs_restantes],
                otimizar=True, custo_ficticio=CUSTO_FICTICIO)
            print(f"  Iterações: {res_a.iteracoes} | Custo: {res_a.custo_total:,.2f} km·m³")
            for i, j, vol in res_a.alocacoes:
                if vol <= EPSILON or i >= len(idx_va) or j >= na: continue
                ae      = todos_aes_redist[idx_va[i]]
                deficit = defs_restantes[j]
                dmt = _calcular_dmt_ae_deficit(ae, deficit, relacoes)
                if dmt >= INFINITO: continue
                vol = round(min(vol, ae['vol_disponivel']), 4)
                if vol <= EPSILON: continue
                ae['vol_disponivel']   = round(ae['vol_disponivel']   - vol, 4)
                deficit['vol_deficit'] = round(deficit['vol_deficit'] - vol, 4)
                print(f"  AE {ae['label_ae']} ({ae['segmento']}) → "
                      f"{deficit['label_aterro']} ({deficit['segmento']}) "
                      f"vol={vol:,.0f} m³ dmt={dmt:.3f}km")
                # Registrar: AE externo → déficit
                seg_dest = deficit['segmento']
                linhas_por_seg[seg_dest].append({
                    'label_origem':       ae['label_ae'],
                    'estaca_ini_origem':  '',
                    'cmv_origem':         ae['cmv_label'],
                    'estaca_fin_origem':  '',
                    'vol_c1': vol, 'vol_c2': 0.0, 'vol_c3': 0.0,
                    'vol_total': vol,
                    'dmt_total': dmt, 'dmt_fixa': 0.0, 'dmt_var': round(dmt, 6),
                    'label_destino':      deficit['label_aterro'],
                    'estaca_ini_destino': deficit.get('estaca_ini_destino', ''),
                    'cmv_destino':        deficit['cmv_label'],
                    'estaca_fin_destino': deficit.get('estaca_fin_destino', ''),
                    'tipo_destino':       deficit['categoria'],
                    'ramo_origem':        ae['ramo'],
                    'ramo_destino':       deficit['ramo'],
                    'obs':                f"AE externo {ae['segmento']}",
                    'flag_nao_soma_corte':  0,
                    'flag_nao_soma_aterro': 0,
                    'vol_ca': vol if deficit['categoria'] == 'CA' else 0.0,
                    'vol_cf': vol if deficit['categoria'] == 'CF' else 0.0,
                    'redistribuido': True,
                    'material_inservivel': False,
                    '_ae_label': deficit['label_ae'],
                    '_ae_ramo':  deficit['ramo'],
                    '_ae_vol_red':  vol,
                    '_ae_vol_orig': deficit['vol_original'],
                })

    if todos_bfs_redist and bfs_restantes3:
        print(f"\n--- FASE 3b: cortes restantes → BFs externos ({len(todos_bfs_redist)}) ---")
        mb = len(bfs_restantes3); nb = len(todos_bfs_redist)
        custos_b = [[INFINITO] * nb for _ in range(mb)]
        for i, bf in enumerate(bfs_restantes3):
            for k, bf_r in enumerate(todos_bfs_redist):
                if bf_r['vol_disponivel'] <= EPSILON: continue
                dmt = _calcular_dmt_bf_bfredist(bf, bf_r, relacoes)
                if dmt < INFINITO:
                    custos_b[i][k] = dmt
        idx_vb = [i for i in range(mb) if any(custos_b[i][k] < INFINITO for k in range(nb))]
        if idx_vb:
            res_b = resolver_transporte(
                [custos_b[i] for i in idx_vb],
                [bfs_restantes3[i]['vol_disponivel'] for i in idx_vb],
                [b['vol_disponivel'] for b in todos_bfs_redist],
                otimizar=True, custo_ficticio=CUSTO_FICTICIO)
            for i, k, vol in res_b.alocacoes:
                if vol <= EPSILON or i >= len(idx_vb) or k >= nb: continue
                bf    = bfs_restantes3[idx_vb[i]]
                bf_r  = todos_bfs_redist[k]
                dmt   = _calcular_dmt_bf_bfredist(bf, bf_r, relacoes)
                if dmt >= INFINITO: continue
                vol = round(min(vol, bf['vol_disponivel']), 4)
                if vol <= EPSILON: continue
                bf['vol_disponivel']   = round(bf['vol_disponivel']   - vol, 4)
                bf_r['vol_disponivel'] = round(bf_r['vol_disponivel'] - vol, 4)
                fator  = vol / bf['vol_original'] if bf['vol_original'] > EPSILON else 0
                vol_c1 = round(bf['vol_c1'] * fator, 4)
                vol_c2 = round(bf['vol_c2'] * fator, 4)
                vol_c3 = round(bf['vol_c3'] * fator, 4)
                print(f"  {bf['label_corte']} ({bf['segmento']}) → "
                      f"BF {bf_r['label_bf']} ({bf_r['segmento']}) "
                      f"vol={vol:,.0f} m³ dmt={dmt:.3f}km")
                # Registrar: corte → BF externo (origem paga, destino recebe)
                seg_orig = bf['segmento']
                linhas_por_seg[seg_orig].append({
                    'label_origem':       bf['label_corte'],
                    'estaca_ini_origem':  bf.get('estaca_ini_origem', ''),
                    'cmv_origem':         bf['cmv_label'],
                    'estaca_fin_origem':  bf.get('estaca_fin_origem', ''),
                    'vol_c1': vol_c1, 'vol_c2': vol_c2, 'vol_c3': vol_c3,
                    'vol_total': vol,
                    'dmt_total': dmt, 'dmt_fixa': 0.0, 'dmt_var': round(dmt, 6),
                    'label_destino':      bf_r['label_bf'],
                    'estaca_ini_destino': '',
                    'cmv_destino':        bf_r['cmv_label'],
                    'estaca_fin_destino': '',
                    'tipo_destino':       'BF',
                    'ramo_origem':        bf['ramo'],
                    'ramo_destino':       bf['ramo'],   # fica na aba do corte original
                    'obs':                f"vai para BF externo {bf_r['segmento']}",
                    'flag_nao_soma_corte':  0,
                    'flag_nao_soma_aterro': 0,
                    'vol_ca': 0.0, 'vol_cf': 0.0,
                    'redistribuido': True,
                    'material_inservivel': False,
                    '_bf_label':    bf['label_bf'],
                    '_bf_ramo':     bf['ramo'],
                    '_bf_vol_red':  vol,
                    '_bf_vol_orig': bf['vol_original'],
                })

    return linhas_por_seg


def _registrar_alocacao_interna(linhas_por_seg, bf, deficit, vol, vol_c1, vol_c2, vol_c3, dmt):
    """Registra alocação interna (mesmo segmento) — BF reduzido, déficit zerado.
    Gera uma linha no segmento mostrando que o corte foi desviado do BF para o aterro."""
    seg_nome = bf['segmento']
    linhas_por_seg[seg_nome].append({
        'label_origem':       bf['label_corte'],
        'estaca_ini_origem':  bf.get('estaca_ini_origem', ''),
        'cmv_origem':         bf['cmv_label'],
        'estaca_fin_origem':  bf.get('estaca_fin_origem', ''),
        'vol_c1': vol_c1, 'vol_c2': vol_c2, 'vol_c3': vol_c3,
        'vol_total': vol,
        'dmt_total': dmt, 'dmt_fixa': 0.0, 'dmt_var': round(dmt, 6),
        'label_destino':      deficit['label_aterro'],
        'estaca_ini_destino': deficit.get('estaca_ini_destino', ''),
        'cmv_destino':        deficit['cmv_label'],
        'estaca_fin_destino': deficit.get('estaca_fin_destino', ''),
        'tipo_destino':       deficit['categoria'],
        'ramo_origem':        bf['ramo'],
        'ramo_destino':       deficit['ramo'],
        'obs':                f"redistribuição interna - BF→aterro prioritário",
        'flag_nao_soma_corte':  0,
        'flag_nao_soma_aterro': 0,
        'vol_ca': vol if deficit['categoria'] == 'CA' else 0.0,
        'vol_cf': vol if deficit['categoria'] == 'CF' else 0.0,
        'redistribuido': True,
        'material_inservivel': False,
        '_bf_label':    bf['label_bf'],
        '_bf_ramo':     bf['ramo'],
        '_bf_vol_red':  vol,
        '_bf_vol_orig': bf['vol_original'],
        '_ae_label':    deficit['label_ae'],
        '_ae_ramo':     deficit['ramo'],
        '_ae_vol_red':  vol,
        '_ae_vol_orig': deficit['vol_original'],
    })


def _registrar_alocacao(linhas_por_seg, bf, deficit, vol, vol_c1, vol_c2, vol_c3, dmt):
    """Registra uma alocação nas linhas de ambos os segmentos."""
    # Linha no segmento ORIGEM
    linhas_por_seg[bf['segmento']].append({
        'label_origem':       bf['label_corte'],
        'estaca_ini_origem':  bf['estaca_ini_origem'],
        'cmv_origem':         bf['cmv_label'],
        'estaca_fin_origem':  bf['estaca_fin_origem'],
        'vol_c1': vol_c1, 'vol_c2': vol_c2, 'vol_c3': vol_c3,
        'vol_total': vol,
        'dmt_total': dmt, 'dmt_fixa': 0.0, 'dmt_var': round(dmt, 6),
        'label_destino':      deficit['label_aterro'],
        'estaca_ini_destino': deficit['estaca_ini_destino'],
        'cmv_destino':        deficit['cmv_label'],
        'estaca_fin_destino': deficit['estaca_fin_destino'],
        'tipo_destino':       deficit['categoria'],
        'ramo_origem':        bf['ramo'],
        'ramo_destino':       bf['ramo'],   # fica na aba do corte original
        'obs':                f"vai para {deficit['segmento']} - {deficit['ramo']}",
        'flag_nao_soma_corte':  0,
        'flag_nao_soma_aterro': 1,
        'vol_ca': vol if deficit['categoria'] == 'CA' else 0.0,
        'vol_cf': vol if deficit['categoria'] == 'CF' else 0.0,
        'redistribuido': True,
        'material_inservivel': False,
        '_bf_label':    bf['label_bf'],
        '_bf_ramo':     bf['ramo'],
        '_bf_vol_red':  vol,
        '_bf_vol_orig': bf['vol_original'],
    })
    # Linha no segmento DESTINO
    linhas_por_seg[deficit['segmento']].append({
        'label_origem':       bf['label_corte'],
        'estaca_ini_origem':  bf['estaca_ini_origem'],
        'cmv_origem':         bf['cmv_label'],
        'estaca_fin_origem':  bf['estaca_fin_origem'],
        'vol_c1': vol_c1, 'vol_c2': vol_c2, 'vol_c3': vol_c3,
        'vol_total': vol,
        'dmt_total': dmt, 'dmt_fixa': 0.0, 'dmt_var': round(dmt, 6),
        'label_destino':      deficit['label_aterro'],
        'estaca_ini_destino': deficit['estaca_ini_destino'],
        'cmv_destino':        deficit['cmv_label'],
        'estaca_fin_destino': deficit['estaca_fin_destino'],
        'tipo_destino':       deficit['categoria'],
        'ramo_origem':        bf['ramo'],
        'ramo_destino':       deficit['ramo'],
        'obs':                f"vem do {bf['segmento']} - {bf['ramo']}",
        'flag_nao_soma_corte':  1,
        'flag_nao_soma_aterro': 0,
        'vol_ca': vol if deficit['categoria'] == 'CA' else 0.0,
        'vol_cf': vol if deficit['categoria'] == 'CF' else 0.0,
        'redistribuido': True,
        'material_inservivel': False,
        '_ae_label':    deficit['label_ae'],
        '_ae_ramo':     deficit['ramo'],
        '_ae_vol_red':  vol,
        '_ae_vol_orig': deficit['vol_original'],
    })



def _categoria_bf(bf: dict) -> str:
    if bf.get('vol_c3', 0) > EPSILON: return 'C3'
    if bf.get('vol_c2', 0) > EPSILON: return 'C2'
    return 'C1'


def _buscar_relacao_segmento(
        seg_a: str, seg_b: str,
        relacoes: List[RelacaoSegmento]
) -> Optional[RelacaoSegmento]:
    """Busca relação direta entre dois segmentos (em qualquer direção)."""
    for rel in relacoes:
        if (rel.seg_a == seg_a and rel.seg_b == seg_b) or \
           (rel.seg_a == seg_b and rel.seg_b == seg_a):
            return rel
    return None


def _calcular_dmt_encadeada(
        seg_orig: str, cmv_orig: float, ei_orig: float, desloc_orig: float,
        seg_dest: str, cmv_dest: float, ei_dest: float, desloc_dest: float,
        relacoes: List[RelacaoSegmento],
        segmentos_map: Dict[str, 'SegmentoRedist']
) -> float:
    """
    Calcula DMT entre dois segmentos quaisquer usando Dijkstra sobre as relações.

    Converte posições físicas para um sistema de referência global único,
    somando as extensões e deslocamentos ao longo do caminho.

    Retorna INFINITO se não houver caminho.
    """
    if seg_orig == seg_dest:
        return INFINITO

    # Construir grafo: nó = segmento, aresta = relação com offset acumulado
    # Para cada nó visitado, guardamos o offset acumulado em relação ao seg_orig
    # offset = deslocamento físico do início de seg_orig até o início do nó atual
    import heapq

    # offset[seg] = metros do início de seg_orig até o início de seg
    # ou seja: pos_global = pos_fisica_local + offset[seg]
    INF = INFINITO

    # Dijkstra — mas aqui não é custo mínimo, é encontrar o offset de cada segmento
    # Usamos BFS simples (grafo pequeno, poucas relações)
    # offset[seg] = posição global do início de seg em relação ao início de seg_orig
    offsets: Dict[str, float] = {seg_orig: 0.0}
    visitados = set()
    fila = [(0.0, seg_orig)]  # (offset, seg)

    while fila:
        off_atual, seg_atual = heapq.heappop(fila)
        if seg_atual in visitados:
            continue
        visitados.add(seg_atual)

        for rel in relacoes:
            # Aresta A→B: offset_B = offset_A + extensao_A + deslocamento
            if rel.seg_a == seg_atual and rel.seg_b not in visitados:
                off_b = off_atual + rel.extensao_a_m + rel.deslocamento_m
                if rel.seg_b not in offsets or off_b < offsets[rel.seg_b]:
                    offsets[rel.seg_b] = off_b
                    heapq.heappush(fila, (off_b, rel.seg_b))
            # Aresta B→A (inversa): offset_A = offset_B - extensao_A - deslocamento
            elif rel.seg_b == seg_atual and rel.seg_a not in visitados:
                off_a = off_atual - rel.extensao_a_m - rel.deslocamento_m
                if rel.seg_a not in offsets or off_a < offsets[rel.seg_a]:
                    offsets[rel.seg_a] = off_a
                    heapq.heappush(fila, (off_a, rel.seg_a))

    if seg_dest not in offsets:
        return INFINITO  # sem caminho

    # Posição global do corte (seg_orig)
    pos_global_orig = (cmv_orig - ei_orig + desloc_orig) + offsets[seg_orig]
    # Posição global do aterro (seg_dest)
    pos_global_dest = (cmv_dest - ei_dest + desloc_dest) + offsets[seg_dest]

    # Afastamento lateral: somar afastamentos ao longo do caminho
    # Para simplificar, usar o afastamento da relação direta se existir,
    # senão somar afastamentos das relações no caminho
    af_km = _afastamento_no_caminho(seg_orig, seg_dest, relacoes, offsets) / 1000.0

    dist = abs(pos_global_orig - pos_global_dest) / 1000.0
    return max(round(dist + af_km, 6), DMT_MINIMA)


def _afastamento_no_caminho(
        seg_orig: str, seg_dest: str,
        relacoes: List[RelacaoSegmento],
        offsets: Dict[str, float]
) -> float:
    """Retorna o afastamento lateral acumulado no caminho seg_orig→seg_dest."""
    # Relação direta
    for rel in relacoes:
        if (rel.seg_a == seg_orig and rel.seg_b == seg_dest) or \
           (rel.seg_a == seg_dest and rel.seg_b == seg_orig):
            return rel.afastamento_m
    # Sem relação direta: retornar 0 (afastamento lateral não acumula em encadeamento)
    return 0.0


# ---------------------------------------------------------------------------
# Gerar Excel redistribuído
# ---------------------------------------------------------------------------

def gerar_excel_redistribuido(
        segmento: SegmentoRedist,
        linhas_novas: List[dict],
        caminho_saida: str,
        bfs_externos: List = None,
        relacoes: List = None):

    from gerador_excel import gerar_excel
    from projeto_json import _dict_to_linha_qdm, _dict_to_trecho
    from distribuidor2 import LinhaQDM, ResultadoDistribuicao
    from detector_trechos import ResultadoDeteccao

    dados = segmento.dados_json

    # Montar mapa {(ramo, label_corte): cmv_m_metros} dos trechos
    # CL que virou C (inservível): guardar também com prefixo C-
    mapa_cmv = {}
    mapa_cmv_por_numero = {}  # fallback: {(ramo, str(numero)): cmv_m}
    for ramo_d in dados.get('ramos', []):
        ramo_nome = ramo_d['nome']
        for t in ramo_d.get('trechos', []):
            prefixo = t.get('prefixo', '')
            numero  = t.get('numero', '')
            label   = f"{prefixo}{numero}"
            try:
                cmv_val = float(t.get('cmv', 0.0))
                mapa_cmv[(ramo_nome, label)] = cmv_val
                # Fallback por número (ex: CL-1 e C-1 têm mesmo número 1)
                chave_num = (ramo_nome, str(numero))
                if chave_num not in mapa_cmv_por_numero:
                    mapa_cmv_por_numero[chave_num] = cmv_val
                # CL → registrar também como C- (inservível muda prefixo)
                if prefixo == 'CL-':
                    mapa_cmv[(ramo_nome, f"C-{numero}")] = cmv_val
            except (ValueError, TypeError):
                pass

    # Calcular reduções por BF e AE
    redu_bf = {}
    redu_ae = {}
    for ln in linhas_novas:
        if '_bf_label' in ln:
            k = (ln['label_origem'], ln['_bf_label'])
            redu_bf[k] = redu_bf.get(k, 0) + ln['_bf_vol_red']
        if '_ae_label' in ln:
            k = (ln['_ae_label'], ln['_ae_ramo'])
            redu_ae[k] = redu_ae.get(k, 0) + ln['_ae_vol_red']

    bfs_ext = bfs_externos or []

    def _cmv_m_corte(ramo_nome: str, label_origem: str) -> float:
        """Retorna posição física do corte no sistema do segmento."""
        # Para interseções: usar pos_relativa (já é posição no eixo principal)
        if hasattr(segmento, 'pos_relativa_por_ramo') and ramo_nome in segmento.pos_relativa_por_ramo:
            return segmento.pos_relativa_por_ramo[ramo_nome]
        # Buscar cmv pelo label exato
        cmv_abs = mapa_cmv.get((ramo_nome, label_origem), None)
        # Fallback: buscar pelo número (ex: "C-1" → número "1" → acha "CL-1")
        if cmv_abs is None:
            import re
            m = re.search(r'\d+$', label_origem)
            if m:
                cmv_abs = mapa_cmv_por_numero.get((ramo_nome, m.group()), None)
        if cmv_abs is None:
            cmv_abs = 0.0
        # Para pistas paralelas: cmv - estaca_ini
        ei = segmento.estaca_ini_por_ramo.get(ramo_nome, 0.0)
        return cmv_abs - ei

    def _dmt_bf_externo(pos_corte_m: float, ramo_corte: str, bf_ext: dict) -> float:
        """Calcula DMT entre corte e BF externo usando encadeamento."""
        seg_orig = segmento.nome
        seg_dest = bf_ext['segmento']
        dmt_fixa = 0.0
        if hasattr(segmento, 'dmt_fixa_por_ramo'):
            dmt_fixa = segmento.dmt_fixa_por_ramo.get(ramo_corte, 0.0)
        if seg_orig == seg_dest:
            return max(abs(pos_corte_m - bf_ext['cmv_m']) / 1000.0 + dmt_fixa, DMT_MINIMA)
        if relacoes:
            dmt_var = _calcular_dmt_encadeada(
                seg_orig, pos_corte_m, 0.0, 0.0,
                seg_dest, bf_ext['cmv_m'], 0.0, 0.0,
                relacoes, {})
            if dmt_var < INFINITO:
                return max(dmt_var + dmt_fixa, DMT_MINIMA)
        return INFINITO

    todas_linhas = []
    for ramo in dados.get('ramos', []):
        for ld in ramo.get('linhas_qdm', []):
            linha = _dict_to_linha_qdm(ld)

            # Reduzir BF pelo corte correspondente — nunca reduzir inservíveis
            if linha.tipo_destino == 'BF' and not linha.material_inservivel:
                k = (linha.label_origem, linha.label_destino)
                reduzido = redu_bf.get(k, 0)
                if reduzido > EPSILON:
                    novo_vol = max(linha.vol_total - reduzido, 0)
                    if novo_vol <= EPSILON:
                        continue  # BF totalmente usado — remover linha
                    fator = novo_vol / linha.vol_total
                    linha.vol_total = round(novo_vol, 4)
                    linha.vol_c1    = round(linha.vol_c1 * fator, 4)
                    linha.vol_c2    = round(linha.vol_c2 * fator, 4)
                    linha.vol_c3    = round(linha.vol_c3 * fator, 4)

            # Material inservível → redirecionar para BF externo mais próximo se houver
            if linha.tipo_destino == 'BF' and linha.material_inservivel and bfs_ext:
                ramo_nome = linha.ramo_origem
                pos_corte = _cmv_m_corte(ramo_nome, linha.label_origem)
                # dmt_fixa do ramo de origem (afastamento lateral da interseção/marginal)
                dmt_fixa_orig = segmento.dmt_fixa_por_ramo.get(ramo_nome, 0.0) \
                                if hasattr(segmento, 'dmt_fixa_por_ramo') else 0.0
                bf_prox = None; dmt_min_var = INFINITO
                for bf_e in bfs_ext:
                    if bf_e.get('tipo') != 'BF': continue
                    # _dmt_bf_externo já inclui dmt_fixa_orig internamente
                    # Calcular só a dmt_var para separar depois
                    seg_dest = bf_e['segmento']
                    if segmento.nome == seg_dest:
                        dmt_var_e = max(abs(pos_corte - bf_e['cmv_m']) / 1000.0, DMT_MINIMA)
                    elif relacoes:
                        dmt_var_e = _calcular_dmt_encadeada(
                            segmento.nome, pos_corte, 0.0, 0.0,
                            seg_dest, bf_e['cmv_m'], 0.0, 0.0,
                            relacoes, {})
                    else:
                        dmt_var_e = INFINITO
                    if dmt_var_e < dmt_min_var:
                        dmt_min_var = dmt_var_e; bf_prox = bf_e
                if bf_prox is not None and dmt_min_var < INFINITO:
                    # dmt_fixa = só o afastamento do BF (o que o usuário informou)
                    af_bf_km = bf_prox.get('afastamento_m', 0.0) / 1000.0
                    # dmt_fixa da interseção de origem → soma na dmt_var
                    linha.label_destino      = bf_prox['label_bf']
                    linha.cmv_destino        = bf_prox.get('cmv_label', '')
                    linha.estaca_ini_destino = ''
                    linha.dmt_var            = round(dmt_min_var + dmt_fixa_orig, 6)
                    linha.dmt_fixa           = round(af_bf_km, 6)
                    linha.dmt_total          = round(dmt_min_var + dmt_fixa_orig + af_bf_km, 6)

            # Substituir AE fictício pelo AE cadastrado mais próximo (se houver)
            if linha.label_origem.startswith('AE') and linha.dmt_total == 0.0:
                k = (linha.label_origem, linha.ramo_destino)
                reduzido = redu_ae.get(k, 0)
                if reduzido > EPSILON:
                    novo_vol = max(linha.vol_total - reduzido, 0)
                    if novo_vol <= EPSILON:
                        continue
                    linha.vol_total = round(novo_vol, 4)
                # Substituir pelo AE cadastrado mais próximo
                if bfs_ext:
                    aes_cad = [b for b in bfs_ext if b.get('tipo') == 'AE']
                    if aes_cad:
                        cmv_dest = _cmv_m_corte(linha.ramo_destino, linha.label_destino)
                        ae_prox = None; dmt_min_ae = INFINITO
                        for ae_e in aes_cad:
                            dmt_ae = _dmt_bf_externo(ae_e['cmv_m'], ae_e.get('ramo',''),
                                                      {'segmento': segmento.nome,
                                                       'cmv_m': cmv_dest})
                            if dmt_ae < dmt_min_ae:
                                dmt_min_ae = dmt_ae; ae_prox = ae_e
                        if ae_prox and dmt_min_ae < INFINITO:
                            # dmt_fixa = só o afastamento do AE (o que o usuário informou)
                            af_ae_km = ae_prox.get('afastamento_m', 0.0) / 1000.0
                            # dmt_fixa da interseção de destino → soma na dmt_var
                            dmt_fixa_dest = 0.0
                            if hasattr(segmento, 'dmt_fixa_por_ramo'):
                                dmt_fixa_dest = segmento.dmt_fixa_por_ramo.get(
                                    linha.ramo_destino, 0.0)
                            linha.label_origem = ae_prox['label_bf']
                            linha.cmv_origem   = ae_prox.get('cmv_label', '')
                            linha.dmt_var      = round(dmt_min_ae + dmt_fixa_dest, 6)
                            linha.dmt_fixa     = round(af_ae_km, 6)
                            linha.dmt_total    = round(dmt_min_ae + dmt_fixa_dest + af_ae_km, 6)

            todas_linhas.append(linha)

    # Adicionar linhas redistribuídas
    for ld in linhas_novas:
        ld_limpo = {k: v for k, v in ld.items() if not k.startswith('_')}
        linha = LinhaQDM(
            label_origem        = ld_limpo['label_origem'],
            estaca_ini_origem   = ld_limpo.get('estaca_ini_origem', ''),
            cmv_origem          = ld_limpo['cmv_origem'],
            estaca_fin_origem   = ld_limpo.get('estaca_fin_origem', ''),
            vol_c1              = ld_limpo.get('vol_c1', 0),
            vol_c2              = ld_limpo.get('vol_c2', 0),
            vol_c3              = ld_limpo.get('vol_c3', 0),
            vol_total           = ld_limpo['vol_total'],
            dmt_fixa            = ld_limpo.get('dmt_fixa', 0.0),
            dmt_var             = ld_limpo.get('dmt_var', 0.0),
            dmt_total           = ld_limpo['dmt_total'],
            label_destino       = ld_limpo['label_destino'],
            estaca_ini_destino  = ld_limpo.get('estaca_ini_destino', ''),
            cmv_destino         = ld_limpo['cmv_destino'],
            estaca_fin_destino  = ld_limpo.get('estaca_fin_destino', ''),
            tipo_destino        = ld_limpo['tipo_destino'],
            ramo_origem         = ld_limpo['ramo_origem'],
            ramo_destino        = ld_limpo['ramo_destino'],
            obs                 = ld_limpo.get('obs', ''),
            flag_nao_soma_corte  = ld_limpo.get('flag_nao_soma_corte', 0),
            flag_nao_soma_aterro = ld_limpo.get('flag_nao_soma_aterro', 0),
            material_inservivel  = ld_limpo.get('material_inservivel', False),
        )
        todas_linhas.append(linha)

    resultado = ResultadoDistribuicao(
        linhas_qdm  = todas_linhas,
        custo_total = sum(l.dmt_total * l.vol_total
                          for l in todas_linhas
                          if l.tipo_destino not in ('CL', 'BF')),
        iteracoes   = 0,
    )

    resultados_deteccao = []
    for ramo in dados.get('ramos', []):
        res = ResultadoDeteccao(ramo=ramo['nome'])
        res.trechos = [_dict_to_trecho(t) for t in ramo.get('trechos', [])]
        resultados_deteccao.append(res)

    nome = dados.get('nome', segmento.nome) + '_redistribuido'

    from detector_trechos import MapeamentoMateriais
    mapa_dados = dados.get('mapeamento', {})
    mapeamento_obj = MapeamentoMateriais(
        corte1    = mapa_dados.get('corte1', []),
        corte2    = mapa_dados.get('corte2', []),
        corte3    = mapa_dados.get('corte3', []),
        aterro_ca = mapa_dados.get('aterro_ca', []),
        aterro_cf = mapa_dados.get('aterro_cf', []),
        ignorar   = mapa_dados.get('ignorar', []),
        prefixo_c1 = mapa_dados.get('prefixo_c1', 'C-'),
        prefixo_c2 = mapa_dados.get('prefixo_c2', 'C2-'),
        prefixo_c3 = mapa_dados.get('prefixo_c3', 'C3-'),
        prefixo_ca = mapa_dados.get('prefixo_ca', 'CA-'),
        prefixo_cf = mapa_dados.get('prefixo_cf', 'CF-'),
        prefixo_cl = mapa_dados.get('prefixo_cl', 'CL-'),
        prefixo_bf = mapa_dados.get('prefixo_bf', 'BF-'),
        prefixo_ae = mapa_dados.get('prefixo_ae', 'AE-'),
    )
    fatores_hom = dados.get('config_leitura', {}).get('fatores_hom', {})

    projeto = None
    try:
        from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
        import string, re as _re

        def _resolver_caminho(caminho_orig: str) -> str:
            """Tenta encontrar o arquivo trocando letra de drive se necessário."""
            if os.path.exists(caminho_orig):
                return caminho_orig
            # Trocar letra do drive (Windows: D:\ → E:\, C:\ etc)
            if len(caminho_orig) >= 2 and caminho_orig[1] == ':':
                resto = caminho_orig[2:]
                for letra in string.ascii_uppercase:
                    tentativa = letra + ':' + resto
                    if os.path.exists(tentativa):
                        return tentativa
            # Buscar pelo nome do arquivo na pasta do JSON
            nome_arq = os.path.basename(caminho_orig)
            pasta_json = os.path.dirname(segmento.caminho_json)
            for raiz, dirs, arqs in os.walk(pasta_json):
                if nome_arq in arqs:
                    return os.path.join(raiz, nome_arq)
            return caminho_orig

        arquivos_orig = dados.get('arquivos', [])
        arquivos = []
        for a in arquivos_orig:
            caminho_resolvido = _resolver_caminho(a['caminho'])
            arquivos.append({**a, 'caminho': caminho_resolvido})

        cl_dados = dados.get('config_leitura', {})
        if arquivos and all(os.path.exists(a['caminho']) for a in arquivos):
            config_leitura = ConfigLeitura(
                unidade      = cl_dados.get('unidade', 'estaca'),
                em_distancia = cl_dados.get('em_distancia', False),
                dist_estaca  = cl_dados.get('dist_estaca', 20.0),
                fatores_hom  = fatores_hom,
            )
            projeto = ler_multiplos_arquivos(arquivos, config_leitura)
    except Exception as ex:
        print(f"  Aviso: não foi possível reler arquivos originais: {ex}")

    gerar_excel(resultado, resultados_deteccao, caminho_saida, nome,
                fatores_hom=fatores_hom,
                mapeamento=mapeamento_obj,
                projeto=projeto)
    print(f"  Excel salvo: {caminho_saida}")


# ---------------------------------------------------------------------------
# Salvar JSON redistribuído — com versão automática
# ---------------------------------------------------------------------------

def salvar_json_redistribuido(
        segmento: SegmentoRedist,
        linhas_novas: List[dict],
        caminho_json: str,
        criar_versao: bool = True):
    """
    Salva JSON redistribuído.
    Se criar_versao=True, gera nome versionado (_v1, _v2...).
    """
    import re

    if criar_versao:
        base, ext = os.path.splitext(caminho_json)
        base_limpo = re.sub(r'_v\d+$', '', base)
        base_limpo = re.sub(r'_redistribuido$', '', base_limpo)
        v = 1
        while True:
            candidato = f"{base_limpo}_redistribuido_v{v}{ext}"
            if not os.path.exists(candidato):
                caminho_saida = candidato
                break
            v += 1
    else:
        caminho_saida = caminho_json

    dados = copy.deepcopy(segmento.dados_json)
    dados['data_atualizacao'] = datetime.now().isoformat(timespec='seconds')
    dados['redistribuido'] = True
    dados['versao'] = '2.0'

    # Calcular reduções
    redu_bf = {}
    redu_ae = {}
    for ln in linhas_novas:
        if '_bf_label' in ln:
            k = (ln['label_origem'], ln['_bf_label'])
            redu_bf[k] = redu_bf.get(k, 0) + ln['_bf_vol_red']
        if '_ae_label' in ln:
            k = (ln['_ae_label'], ln['_ae_ramo'])
            redu_ae[k] = redu_ae.get(k, 0) + ln['_ae_vol_red']

    # Atualizar linhas existentes
    for ramo in dados['ramos']:
        linhas_atualizadas = []
        for ld in ramo['linhas_qdm']:
            if ld['tipo_destino'] == 'BF':
                k = (ld['label_origem'], ld['label_destino'])
                red = redu_bf.get(k, 0)
                if red > EPSILON:
                    novo = max(ld['vol_total'] - red, 0)
                    if novo <= EPSILON:
                        continue
                    fator = novo / ld['vol_total']
                    ld = dict(ld)
                    ld['vol_total'] = round(novo, 4)
                    ld['vol_c1']    = round(ld.get('vol_c1', 0) * fator, 4)
                    ld['vol_c2']    = round(ld.get('vol_c2', 0) * fator, 4)
                    ld['vol_c3']    = round(ld.get('vol_c3', 0) * fator, 4)

            if (ld['label_origem'].startswith('AE') and
                    ld.get('dmt_total', 0) == 0.0):
                k = (ld['label_origem'], ld['ramo_destino'])
                red = redu_ae.get(k, 0)
                if red > EPSILON:
                    novo = max(ld['vol_total'] - red, 0)
                    if novo <= EPSILON:
                        continue
                    ld = dict(ld)
                    ld['vol_total'] = round(novo, 4)

            linhas_atualizadas.append(ld)
        ramo['linhas_qdm'] = linhas_atualizadas

    # Adicionar linhas redistribuídas ao ramo correto
    for ln in linhas_novas:
        ld = {k: v for k, v in ln.items() if not k.startswith('_')}
        ramo_nome = ld['ramo_destino'] if ld.get('flag_nao_soma_corte') \
                    else ld['ramo_origem']
        for ramo in dados['ramos']:
            if ramo['nome'] == ramo_nome:
                ramo['linhas_qdm'].append(ld)
                break

    # Limpar alertas de déficits totalmente cobertos
    dados['resultado'] = dict(dados.get('resultado', {}))
    alertas_orig = dados['resultado'].get('alertas', [])
    if alertas_orig and redu_ae:
        aes_remanescentes = set()
        for ramo in dados['ramos']:
            for ld in ramo['linhas_qdm']:
                if (ld['label_origem'].startswith('AE') and
                        ld.get('dmt_total', 0) == 0.0):
                    aes_remanescentes.add((ld['label_origem'], ld['ramo_destino']))
        alertas_filtrados = [
            a for a in alertas_orig
            if not any(k not in aes_remanescentes
                       for k in redu_ae if k[1] in a)
        ]
        dados['resultado']['alertas'] = alertas_filtrados

    with open(caminho_saida, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"  JSON salvo: {caminho_saida}")
    return caminho_saida


# ---------------------------------------------------------------------------
# Sessão de redistribuição
# ---------------------------------------------------------------------------

def salvar_sessao(segmentos: List[SegmentoRedist],
                  relacoes_dict: List[dict],
                  pasta_saida: str,
                  caminho_sessao: str,
                  bfae: List[dict] = None):
    sessao = {
        "versao": "2.0",
        "tipo":   "sessao_redistribuicao",
        "data":   datetime.now().isoformat(timespec='seconds'),
        "pasta_saida": pasta_saida,
        "segmentos": [
            {"nome": seg.nome, "caminho_json": seg.caminho_json,
             "config_ramos": seg.config_ramos,
             "dados_bf": getattr(seg, '_dados_bf', []),
             "dados_ae": getattr(seg, '_dados_ae', [])}
            for seg in segmentos
        ],
        "relacoes": relacoes_dict,
        "bfae":    bfae or [],
    }
    with open(caminho_sessao, 'w', encoding='utf-8') as f:
        json.dump(sessao, f, ensure_ascii=False, indent=2)
    print(f"  Sessão salva: {caminho_sessao}")


def carregar_sessao(caminho_sessao: str) -> dict:
    with open(caminho_sessao, 'r', encoding='utf-8') as f:
        sessao = json.load(f)
    if sessao.get('tipo') != 'sessao_redistribuicao':
        raise ValueError("Arquivo não é uma sessão de redistribuição válida.")
    return {
        "pasta_saida": sessao.get("pasta_saida", ""),
        "segmentos":   sessao.get("segmentos", []),
        "relacoes":    sessao.get("relacoes", []),
        "data":        sessao.get("data", ""),
        "versao":      sessao.get("versao", "1.0"),
    }