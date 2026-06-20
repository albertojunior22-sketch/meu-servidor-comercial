"""
distribuidor2.py (v5)
---------------------
Distribuição de terraplenagem usando matriz única global de transporte.

NOVIDADES v5:
- Dois tipos de relação: 'pistas_paralelas' e 'intersecao_marginal'
- Posição física real: pos = cmv - estaca_ini + deslocamento
- LocalAuxiliar com eixo_ref e pos_relativa_m
- LinhaQDM com material_inservivel
- Compatibilidade total com JSONs v1.0 (conversão automática)

Estratégias:
- "usar_tudo": Stepping-Stone sempre. AE só no déficit. BF só na sobra.
- "otimizar":  Tudo em uma única rodada.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from detector_trechos import (
    Trecho, TipoTrecho, ResultadoDeteccao,
    MapeamentoMateriais, ParametrosDistribuicao
)
from algoritmo_transporte import resolver_transporte, INFINITO, EPSILON

DMT_MINIMA      = 0.050
PENALIDADE_C2CF = 0.001
PENALIDADE_BF   = 500.0   # garante aterros antes de BF quando só BF cadastrado
LIMIAR_VOL      = 0.01   # volumes abaixo disso sao residuos numericos


# ---------------------------------------------------------------------------
# Relação entre segmentos — v5
# ---------------------------------------------------------------------------

@dataclass
class RelacaoSegmentos:
    """
    Define a relação geométrica entre dois ramos para cálculo de DMT.

    Tipos:
    - 'pistas_paralelas': dois eixos paralelos com sistemas de estacagem
      possivelmente diferentes. Usa posição física relativa.
      pos_fisica = cmv - estaca_ini + deslocamento
      DMT = |pos_a - pos_b| / 1000 + afastamento / 1000

    - 'intersecao_marginal': interseção ou marginal conectada a um eixo
      de referência em uma posição relativa conhecida.
      DMT = |cmv_eixo - estaca_ini_eixo + deslocamento_eixo - pos_relativa| / 1000 + dmt_fixa

    Compatibilidade v1.0: tipos antigos (estaca, distancia, intersecao_interna,
    intersecao_externa, fixa) são convertidos automaticamente na carga do JSON.
    """
    ramo_a:           str
    ramo_b:           str
    tipo:             str    # 'pistas_paralelas' | 'intersecao_marginal'

    # --- pistas_paralelas ---
    estaca_ini_a_m:   float = 0.0   # CMv absoluto do início do eixo A
    estaca_ini_b_m:   float = 0.0   # CMv absoluto do início do eixo B
    deslocamento_a_m: float = 0.0   # deslocamento físico do eixo A (pode ser negativo)
    deslocamento_b_m: float = 0.0   # deslocamento físico do eixo B (pode ser negativo)
    afastamento_m:    float = 0.0   # distância lateral entre os dois eixos

    # --- intersecao_marginal ---
    # ramo_a = eixo de referência (pista principal)
    # ramo_b = interseção / marginal
    pos_relativa_m:   float = 0.0   # posição relativa da interseção no eixo A (pode ser negativa)
    dmt_fixa_km:      float = 0.0   # afastamento lateral em km

    # --- compartilhados ---
    pistas_paralelas: bool  = False  # True → entra na rodada interna conjunta
    todos:            bool  = False  # True → relação vale para ramos_todos
    ramos_todos:      List[str] = field(default_factory=list)
    usar_rodada_interna: bool = False  # alias de pistas_paralelas para interface

    # --- campos legados v1.0 (mantidos para compatibilidade) ---
    dist_inicio_m:    float = 0.0
    pista_antes:      str   = "a"
    dist_estaca_m:    float = 20.0
    dist_fixa_m:      float = 0.0
    ref_a_m:          float = 0.0
    ref_b_m:          float = 0.0
    dist_refs_m:      float = 0.0


def _pos_fisica_a(cmv_a: float, rel: RelacaoSegmentos) -> float:
    """Posição física do ponto no eixo A."""
    return cmv_a - rel.estaca_ini_a_m + rel.deslocamento_a_m


def _pos_fisica_b(cmv_b: float, rel: RelacaoSegmentos) -> float:
    """Posição física do ponto no eixo B."""
    return cmv_b - rel.estaca_ini_b_m + rel.deslocamento_b_m


def calcular_dmt_relacao(cmv_a: float, cmv_b: float,
                          rel: RelacaoSegmentos) -> float:
    """
    Calcula DMT entre dois pontos usando a relação geométrica definida.
    cmv_a = CMv do ponto no ramo_a (absoluto, em metros)
    cmv_b = CMv do ponto no ramo_b (absoluto, em metros)
    """
    if rel.tipo == 'pistas_paralelas':
        pos_a = _pos_fisica_a(cmv_a, rel)
        pos_b = _pos_fisica_b(cmv_b, rel)
        dist  = abs(pos_a - pos_b) / 1000.0
        af    = rel.afastamento_m / 1000.0
        # Quando afastamento definido, respeitar valor real (pode ser < DMT_MINIMA)
        valor = round(dist + af, 6)
        return max(valor, af) if af > 0 else max(valor, DMT_MINIMA)

    elif rel.tipo == 'intersecao_marginal':
        # ramo_a = eixo de referência
        # pos_relativa_m = posição física da interseção no eixo de referência
        pos_eixo = _pos_fisica_a(cmv_a, rel)
        dist = abs(pos_eixo - rel.pos_relativa_m) / 1000.0
        return max(round(dist + rel.dmt_fixa_km, 6), DMT_MINIMA)

    # --- compatibilidade v1.0 ---
    elif rel.tipo == 'fixa':
        return max(rel.dmt_fixa_km, DMT_MINIMA)

    elif rel.tipo == 'estaca':
        if rel.pista_antes == 'a':
            pos_a = cmv_a - rel.estaca_ini_a_m
            pos_b = (cmv_b - rel.estaca_ini_b_m) + rel.dist_inicio_m
        else:
            pos_a = (cmv_a - rel.estaca_ini_a_m) + rel.dist_inicio_m
            pos_b = cmv_b - rel.estaca_ini_b_m
        dist = abs(pos_a - pos_b) / 1000.0
        af   = rel.afastamento_m / 1000.0
        valor = round(dist + af, 6)
        return max(valor, af) if af > 0 else max(valor, DMT_MINIMA)

    elif rel.tipo == 'distancia':
        dist_fixa = rel.dist_fixa_m / 1000.0
        dist_est  = abs(cmv_a - cmv_b) / 1000.0
        return max(round(dist_fixa + dist_est, 6), DMT_MINIMA)

    elif rel.tipo == 'intersecao_interna':
        dist_a = abs(cmv_a - rel.ref_a_m) / 1000.0
        dist_b = abs(cmv_b - rel.ref_a_m) / 1000.0
        return max(round(dist_a + dist_b + rel.dmt_fixa_km, 6), DMT_MINIMA)

    elif rel.tipo == 'intersecao_externa':
        dist_a = abs(cmv_a - rel.ref_a_m) / 1000.0
        dist_b = abs(cmv_b - rel.ref_b_m) / 1000.0
        return max(round(dist_a + rel.dist_refs_m / 1000.0 + dist_b + rel.dmt_fixa_km, 6), DMT_MINIMA)

    elif rel.tipo == 'intersecao_marginal_inv':
        # Direcao invertida: interseção (ramo_a) → eixo (ramo_b)
        # cmv_a = CMv local da interseção (medido desde o início da interseção)
        # cmv_b = CMv do eixo (absoluto)
        # estaca_ini_b_m = estaca_ini do eixo (ramo_b)
        # pos_relativa_m = posição de conexão no eixo
        dist_local = abs(cmv_a) / 1000.0   # distância no interior da interseção
        dist_eixo  = abs(cmv_b - (rel.estaca_ini_b_m + rel.pos_relativa_m)) / 1000.0
        return max(round(dist_local + rel.dmt_fixa_km + dist_eixo, 6), DMT_MINIMA)

    return DMT_MINIMA


# ---------------------------------------------------------------------------
# LocalAuxiliar — BF e AE
# ---------------------------------------------------------------------------

@dataclass
class LocalAuxiliar:
    """
    BF ou AE com posicionamento físico.

    pos_relativa_m: posição relativa em relação ao início do eixo de referência.
                    Pode ser negativa (antes do início do eixo).
    eixo_ref:       nome do ramo de referência. Vazio = único eixo disponível.
    estaca_m:       CMv absoluto (mantido para compatibilidade v1.0).
    """
    nome:           str
    tipo:           str        # "BF" ou "AE"
    capacidade:     float = 0.0
    fh:             float = 1.25
    # v5: posicionamento por eixo de referência
    eixo_ref:       str   = ""
    pos_relativa_m: float = 0.0
    afastamento:    float = 0.0
    # v1.0: compatibilidade
    estaca_m:       float = 0.0
    # informativo: aparece na coluna CMv da planilha (coluna C para AE, Q para BF)
    cmv_label:      str   = ""

    @property
    def valido(self) -> bool:
        return bool(self.nome.strip()) and self.capacidade > 0

    @property
    def capacidade_hom(self) -> float:
        if self.tipo == "AE":
            return self.capacidade / self.fh
        return self.capacidade

    def vol_geo_corte(self, vol_hom: float, fh_corte: float) -> float:
        return vol_hom * fh_corte

    def dmt_para(self, cmv: float,
                 config: 'ConfigDistribuicao' = None,
                 ramo_corte: str = "") -> float:
        """
        Calcula DMT do corte/aterro até este BF/AE.

        Se eixo_ref está definido e config fornecido, usa encadeamento
        para calcular a posição física correta.
        Caso contrário, usa estaca_m (modo compatibilidade v1.0).
        """
        if self.eixo_ref and config is not None:
            # Buscar relação do eixo_ref para obter estaca_ini
            estaca_ini = _get_estaca_ini_ramo(self.eixo_ref, config)
            # pos_fisica_bf = pos_relativa_m (já relativa ao zero do eixo)
            # pos_fisica_corte = cmv - estaca_ini_ramo_corte + deslocamento
            # Se ramo_corte == eixo_ref: distância direta
            if ramo_corte == self.eixo_ref:
                estaca_ini_corte = _get_estaca_ini_ramo(ramo_corte, config)
                deslocamento = _get_deslocamento_ramo(ramo_corte, config)
                pos_corte = cmv - estaca_ini_corte + deslocamento
                dist = abs(pos_corte - self.pos_relativa_m) / 1000.0
            else:
                # Encadeamento: usar calcular_dmt com ramo_corte → eixo_ref → BF
                # Por simplicidade: usar encadeamento via calcular_dmt
                # O BF é tratado como um ponto no eixo_ref na pos_relativa_m
                cmv_bf_equiv = estaca_ini + self.pos_relativa_m
                dmt_encadeada = calcular_dmt(cmv, cmv_bf_equiv, config,
                                              ramo_corte, self.eixo_ref,
                                              permitir_cruzamento=True)
                return max(round(dmt_encadeada + self.afastamento / 1000.0, 6), DMT_MINIMA)
            af = self.afastamento / 1000.0
            return max(round(dist + af, 6), DMT_MINIMA)

        # Modo compatibilidade v1.0: usa estaca_m absoluta
        ref = self.estaca_m if self.estaca_m > 0 else (
            self.pos_relativa_m if self.pos_relativa_m > 0 else 0.0)
        dist = abs(ref - cmv) / 1000.0
        af   = self.afastamento / 1000.0
        return max(round(dist + af, 6), DMT_MINIMA)


def _get_estaca_ini_ramo(ramo: str, config: 'ConfigDistribuicao') -> float:
    """Retorna estaca_ini_m do eixo de referência nas relações."""
    for rel in config.relacoes:
        if rel.tipo == 'pistas_paralelas':
            if rel.ramo_a == ramo:
                return rel.estaca_ini_a_m
            if rel.ramo_b == ramo:
                return rel.estaca_ini_b_m
    return 0.0


def _get_deslocamento_ramo(ramo: str, config: 'ConfigDistribuicao') -> float:
    """Retorna deslocamento do eixo de referência nas relações."""
    for rel in config.relacoes:
        if rel.tipo == 'pistas_paralelas':
            if rel.ramo_a == ramo:
                return rel.deslocamento_a_m
            if rel.ramo_b == ramo:
                return rel.deslocamento_b_m
    return 0.0


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class ConfigDistribuicao:
    tipo_projeto:            str   = "intersecao"
    usar_dmt_maxima:         bool  = False
    dmt_maxima_km:           float = 999.0
    dmt_cl:                  float = 0.050
    emprestimo_mais_proximo: bool  = True
    estrategia:              str   = "usar_tudo"
    relacoes:                List[RelacaoSegmentos] = field(default_factory=list)
    bota_foras:              List[LocalAuxiliar] = field(default_factory=list)
    emprestimos:             List[LocalAuxiliar] = field(default_factory=list)
    dmt_entre_ramos:         Dict[str, Dict[str, float]] = field(default_factory=dict)
    usar_encadeamento:       bool  = False


@dataclass
class LinhaQDM:
    label_origem:       str
    estaca_ini_origem:  str
    cmv_origem:         str
    estaca_fin_origem:  str
    vol_c1:             float = 0.0
    vol_c2:             float = 0.0
    vol_c3:             float = 0.0
    vol_total:          float = 0.0
    dmt_fixa:           float = DMT_MINIMA
    dmt_var:            float = 0.0
    dmt_total:          float = 0.0
    label_destino:      str   = ""
    estaca_ini_destino: str   = ""
    cmv_destino:        str   = ""
    estaca_fin_destino: str   = ""
    tipo_destino:       str   = ""
    ramo_origem:        str   = ""
    ramo_destino:       str   = ""
    obs:                str   = ""
    flag_nao_soma_corte:    int   = 0
    flag_nao_soma_aterro:   int   = 0
    vol_ca:                 float = 0.0
    vol_cf:                 float = 0.0
    material_inservivel:    bool  = False   # True → não entra na redistribuição


@dataclass
class ResultadoDistribuicao:
    linhas_qdm:  List[LinhaQDM] = field(default_factory=list)
    alertas:     List[str]      = field(default_factory=list)
    custo_total: float          = 0.0
    iteracoes:   int            = 0


# ---------------------------------------------------------------------------
# DMT helpers
# ---------------------------------------------------------------------------

def _buscar_relacao(ramo_a: str, ramo_b: str,
                    config: ConfigDistribuicao) -> Optional[RelacaoSegmentos]:
    """
    Busca relação direta entre dois ramos.
    Para intersecao_marginal: ramo_a é sempre o eixo de referência.
    """
    for rel in config.relacoes:
        if rel.todos:
            continue

        if rel.tipo == 'pistas_paralelas':
            if rel.ramo_a == ramo_a and rel.ramo_b == ramo_b:
                return rel
            if rel.ramo_a == ramo_b and rel.ramo_b == ramo_a:
                # Inverter pistas paralelas: trocar A e B
                return RelacaoSegmentos(
                    ramo_a=ramo_a, ramo_b=ramo_b,
                    tipo='pistas_paralelas',
                    estaca_ini_a_m=rel.estaca_ini_b_m,
                    estaca_ini_b_m=rel.estaca_ini_a_m,
                    deslocamento_a_m=rel.deslocamento_b_m,
                    deslocamento_b_m=rel.deslocamento_a_m,
                    afastamento_m=rel.afastamento_m,
                    pistas_paralelas=rel.pistas_paralelas,
                    todos=rel.todos,
                    ramos_todos=rel.ramos_todos,
                )

        elif rel.tipo == 'intersecao_marginal':
            # ramo_a = eixo, ramo_b = interseção
            if rel.ramo_a == ramo_a and rel.ramo_b == ramo_b:
                return rel
            # Direção inversa: interseção → eixo (invertemos internamente)
            if rel.ramo_a == ramo_b and rel.ramo_b == ramo_a:
                return RelacaoSegmentos(
                    ramo_a=ramo_a, ramo_b=ramo_b,
                    tipo='intersecao_marginal',
                    estaca_ini_a_m=rel.estaca_ini_b_m,
                    deslocamento_a_m=rel.deslocamento_b_m,
                    pos_relativa_m=rel.pos_relativa_m,
                    dmt_fixa_km=rel.dmt_fixa_km,
                    todos=rel.todos,
                    ramos_todos=rel.ramos_todos,
                )

        # --- compatibilidade v1.0 ---
        else:
            if rel.ramo_a == ramo_a and rel.ramo_b == ramo_b:
                return rel
            if rel.ramo_a == ramo_b and rel.ramo_b == ramo_a:
                if rel.tipo == 'estaca':
                    return RelacaoSegmentos(
                        ramo_a=ramo_a, ramo_b=ramo_b, tipo=rel.tipo,
                        estaca_ini_a_m=rel.estaca_ini_b_m,
                        estaca_ini_b_m=rel.estaca_ini_a_m,
                        dist_inicio_m=rel.dist_inicio_m,
                        pista_antes='b' if rel.pista_antes == 'a' else 'a',
                        afastamento_m=rel.afastamento_m,
                        dist_estaca_m=rel.dist_estaca_m,
                        pistas_paralelas=rel.pistas_paralelas,
                    )
                if rel.tipo == 'intersecao_externa':
                    return RelacaoSegmentos(
                        ramo_a=ramo_a, ramo_b=ramo_b, tipo=rel.tipo,
                        ref_a_m=rel.ref_b_m, ref_b_m=rel.ref_a_m,
                        dist_refs_m=rel.dist_refs_m,
                        dmt_fixa_km=rel.dmt_fixa_km,
                    )
                import dataclasses
                return dataclasses.replace(rel, ramo_a=ramo_a, ramo_b=ramo_b)
    return None


def _buscar_relacao_fallback(config: ConfigDistribuicao,
                              ramo_orig: str = "",
                              ramo_dest: str = "") -> Optional[RelacaoSegmentos]:
    """Retorna relação fallback (todos=True) para o par de ramos."""
    fallback_geral = None
    for rel in config.relacoes:
        if not rel.todos:
            continue
        if not rel.ramos_todos:
            if fallback_geral is None:
                fallback_geral = rel
        else:
            if ramo_orig in rel.ramos_todos or ramo_dest in rel.ramos_todos:
                return rel
    return fallback_geral


def _calcular_dmt_fallback(cmv_orig: float, cmv_dest: float,
                            ramo_orig: str,
                            rel: RelacaoSegmentos) -> float:
    """Calcula DMT usando relação fallback (todos=True)."""
    if rel.tipo == 'intersecao_marginal':
        if ramo_orig == rel.ramo_a:
            pos_eixo = _pos_fisica_a(cmv_orig, rel)
            dist = abs(pos_eixo - rel.pos_relativa_m) / 1000.0
            return max(round(dist + rel.dmt_fixa_km, 6), DMT_MINIMA)
        else:
            return max(rel.dmt_fixa_km, DMT_MINIMA)

    elif rel.tipo == 'intersecao_interna':
        if ramo_orig == rel.ramo_a:
            dist = abs(cmv_orig - rel.ref_a_m) / 1000.0
            return max(round(dist + rel.dmt_fixa_km, 6), DMT_MINIMA)
        else:
            return max(rel.dmt_fixa_km, DMT_MINIMA)

    elif rel.tipo == 'intersecao_externa':
        if ramo_orig == rel.ramo_a:
            dist = abs(cmv_orig - rel.ref_a_m) / 1000.0
            return max(round(dist + rel.dist_refs_m / 1000.0 + rel.dmt_fixa_km, 6), DMT_MINIMA)
        else:
            return max(rel.dmt_fixa_km, DMT_MINIMA)

    else:
        return calcular_dmt_relacao(cmv_orig, cmv_dest, rel)


def calcular_dmt(cmv_orig: float, cmv_dest: float,
                 config: ConfigDistribuicao,
                 ramo_orig: str, ramo_dest: str,
                 permitir_cruzamento: bool = True) -> float:
    if ramo_orig == ramo_dest:
        dist = abs(cmv_dest - cmv_orig) / 1000.0
        return max(round(dist, 6), DMT_MINIMA)
    if not permitir_cruzamento:
        return INFINITO
    rel = _buscar_relacao(ramo_orig, ramo_dest, config)
    if rel:
        return calcular_dmt_relacao(cmv_orig, cmv_dest, rel)
    # Legado
    dmt = config.dmt_entre_ramos.get(ramo_orig, {}).get(ramo_dest, 0.0)
    if dmt == 0:
        dmt = config.dmt_entre_ramos.get(ramo_dest, {}).get(ramo_orig, 0.0)
    if dmt > 0:
        return max(dmt, DMT_MINIMA)
    # Encadeamento
    if config.usar_encadeamento:
        from encadeamento import calcular_dmt_encadeada
        dmt_enc = calcular_dmt_encadeada(cmv_orig, cmv_dest, ramo_orig, ramo_dest, config)
        if dmt_enc < INFINITO:
            return dmt_enc
        rel_fallback = _buscar_relacao_fallback(config, ramo_orig, ramo_dest)
        if rel_fallback:
            return _calcular_dmt_fallback(cmv_orig, cmv_dest, ramo_orig, rel_fallback)
    return INFINITO


def dmt_ok(dmt: float, config: ConfigDistribuicao) -> bool:
    return not (config.usar_dmt_maxima and dmt > config.dmt_maxima_km)


# ---------------------------------------------------------------------------
# Criadores de linha QDM
# ---------------------------------------------------------------------------

def _cat_corte(corte: Trecho) -> str:
    return corte.categoria


def linha_corte_aterro(corte: Trecho, aterro: Trecho,
                       vol: float, config: ConfigDistribuicao,
                       inservivel: bool = False) -> 'LinhaQDM | List[LinhaQDM]':
    dmt  = calcular_dmt(corte.cmv, aterro.cmv, config, corte.ramo, aterro.ramo)
    cat  = _cat_corte(corte)
    entre_ramos = corte.ramo != aterro.ramo

    obs_origem  = f"vai para {aterro.ramo}" if entre_ramos else ""
    obs_destino = f"vem do {corte.ramo}"   if entre_ramos else ""

    def _make_linha(obs_val, flag_corte, flag_aterro):
        return LinhaQDM(
            label_origem=corte.label, estaca_ini_origem=corte.estaca_ini,
            cmv_origem=corte.cmv_label, estaca_fin_origem=corte.estaca_fin,
            vol_c1=vol if cat=="C1" else 0.0,
            vol_c2=vol if cat=="C2" else 0.0,
            vol_c3=vol if cat=="C3" else 0.0,
            vol_total=round(vol, 4),
            dmt_fixa=0.0, dmt_var=round(dmt, 6), dmt_total=dmt,
            label_destino=aterro.label, estaca_ini_destino=aterro.estaca_ini,
            cmv_destino=aterro.cmv_label, estaca_fin_destino=aterro.estaca_fin,
            tipo_destino=aterro.categoria,
            ramo_origem=corte.ramo, ramo_destino=aterro.ramo,
            obs=obs_val,
            flag_nao_soma_corte=flag_corte,
            flag_nao_soma_aterro=flag_aterro,
            material_inservivel=inservivel,
        )

    if entre_ramos:
        l_orig = _make_linha(obs_origem, flag_corte=0, flag_aterro=1)
        l_dest = _make_linha(obs_destino, flag_corte=1, flag_aterro=0)
        return [l_orig, l_dest]
    else:
        return _make_linha("", flag_corte=0, flag_aterro=0)


def linha_cl(cl: Trecho, config: ConfigDistribuicao) -> LinhaQDM:
    return LinhaQDM(
        label_origem=cl.label, estaca_ini_origem=cl.estaca_ini,
        cmv_origem=cl.cmv_label, estaca_fin_origem=cl.estaca_fin,
        vol_c1=cl.vol_total_hom, vol_total=cl.vol_total_hom,
        dmt_fixa=config.dmt_cl, dmt_var=0.0, dmt_total=config.dmt_cl,
        label_destino=cl.label, estaca_ini_destino=cl.estaca_ini,
        cmv_destino=cl.cmv_label, estaca_fin_destino=cl.estaca_fin,
        tipo_destino="CL", ramo_origem=cl.ramo, ramo_destino=cl.ramo,
        obs="", flag_nao_soma_corte=0, flag_nao_soma_aterro=0
    )


def linha_bota_fora(corte: Trecho, vol: float,
                    bf: Optional[LocalAuxiliar],
                    prefixo_bf: str, num: int,
                    inservivel: bool = False,
                    config: ConfigDistribuicao = None) -> LinhaQDM:
    cat = _cat_corte(corte)
    if bf and bf.valido:
        dmt_t = bf.dmt_para(corte.cmv, config, corte.ramo)
        dmt_f = 0.0
        dmt_v = round(dmt_t, 6)
        label_bf = bf.nome          # nome real do BF vai para label_destino
    else:
        dmt_t = dmt_f = dmt_v = 0.0
        label_bf = f"{prefixo_bf}{num}"  # sem BF cadastrado: usa sequencial
    return LinhaQDM(
        label_origem=corte.label, estaca_ini_origem=corte.estaca_ini,
        cmv_origem=corte.cmv_label, estaca_fin_origem=corte.estaca_fin,
        vol_c1=vol if cat=="C1" else 0.0,
        vol_c2=vol if cat=="C2" else 0.0,
        vol_c3=vol if cat=="C3" else 0.0,
        vol_total=round(vol, 4),
        dmt_fixa=dmt_f, dmt_var=dmt_v, dmt_total=dmt_t,
        label_destino=label_bf,
        estaca_ini_destino="", cmv_destino=bf.cmv_label if bf and bf.valido else "", estaca_fin_destino="",
        tipo_destino="BF", ramo_origem=corte.ramo, ramo_destino="",
        obs="", flag_nao_soma_corte=0, flag_nao_soma_aterro=0,
        material_inservivel=inservivel,
    )


def linha_emprestimo(aterro: Trecho, vol: float,
                     ae: Optional[LocalAuxiliar],
                     prefixo_ae: str, num: int,
                     config: ConfigDistribuicao = None) -> LinhaQDM:
    if ae and ae.valido:
        dmt_t = ae.dmt_para(aterro.cmv, config, aterro.ramo)
        dmt_f = 0.0
        dmt_v = round(dmt_t, 6)
        label_ae = ae.nome          # nome real do AE vai para label_origem
    else:
        dmt_t = dmt_f = dmt_v = 0.0
        label_ae = f"{prefixo_ae}{num}"  # sem AE cadastrado: usa sequencial
    return LinhaQDM(
        label_origem=label_ae, estaca_ini_origem="",
        cmv_origem=ae.cmv_label if ae and ae.valido else "", estaca_fin_origem="",
        vol_total=round(vol, 4),
        dmt_fixa=dmt_f, dmt_var=dmt_v, dmt_total=dmt_t,
        label_destino=aterro.label, estaca_ini_destino=aterro.estaca_ini,
        cmv_destino=aterro.cmv_label, estaca_fin_destino=aterro.estaca_fin,
        tipo_destino=aterro.categoria,
        ramo_origem="", ramo_destino=aterro.ramo,
        obs="", flag_nao_soma_corte=0, flag_nao_soma_aterro=0
    )



def _consolidar_linhas(linhas):
    """
    Consolida residuos numericos do Stepping-Stone.
    vol < LIMIAR_VOL: soma na linha principal do mesmo par ou descarta.
    CLs e BFs nunca sao filtrados.
    """
    resultado = []
    principais = {}

    for l in linhas:
        if l.tipo_destino in ('CL', 'BF'):
            resultado.append(l)
            continue
        if l.vol_total >= LIMIAR_VOL:
            chave = (l.label_origem, l.label_destino,
                     l.ramo_origem, l.ramo_destino, l.flag_nao_soma_corte)
            if chave not in principais:
                principais[chave] = l
                resultado.append(l)
            else:
                principais[chave].vol_total = round(principais[chave].vol_total + l.vol_total, 4)
                principais[chave].vol_c1    = round(principais[chave].vol_c1    + l.vol_c1,    4)
                principais[chave].vol_c2    = round(principais[chave].vol_c2    + l.vol_c2,    4)
                principais[chave].vol_c3    = round(principais[chave].vol_c3    + l.vol_c3,    4)

    n_somados = 0
    n_descartados = 0
    for l in linhas:
        if l.tipo_destino in ('CL', 'BF') or l.vol_total >= LIMIAR_VOL:
            continue
        chave = (l.label_origem, l.label_destino,
                 l.ramo_origem, l.ramo_destino, l.flag_nao_soma_corte)
        if chave in principais:
            principais[chave].vol_total = round(principais[chave].vol_total + l.vol_total, 4)
            principais[chave].vol_c1    = round(principais[chave].vol_c1    + l.vol_c1,    4)
            principais[chave].vol_c2    = round(principais[chave].vol_c2    + l.vol_c2,    4)
            principais[chave].vol_c3    = round(principais[chave].vol_c3    + l.vol_c3,    4)
            n_somados += 1
        else:
            n_descartados += 1

    if n_somados + n_descartados > 0:
        print(f"  Consolidacao: {n_somados} residuos somados + "
              f"{n_descartados} descartados (vol < {LIMIAR_VOL} m3)")
    return resultado

# ---------------------------------------------------------------------------
# Matriz única global de transporte (sem mudança na lógica)
# ---------------------------------------------------------------------------

def montar_e_resolver_matriz(
        cortes_c3: List[Trecho],
        cortes_c2: List[Trecho],
        cortes_c1: List[Trecho],
        aterros_ca: List[Trecho],
        aterros_cf: List[Trecho],
        params: ParametrosDistribuicao,
        config: ConfigDistribuicao,
        mapeamento: MapeamentoMateriais,
        incluir_ae: bool = False,
        incluir_bf: bool = False,
        permitir_cruzamento: bool = True,
        restricoes=None) -> Tuple[List[LinhaQDM], int]:

    linhas: List[LinhaQDM] = []

    origens: List[Trecho] = []
    origens += [c for c in cortes_c3 if c.vol_disponivel > EPSILON and not getattr(c, '_somente_bf', False)]
    origens += [c for c in cortes_c2 if c.vol_disponivel > EPSILON and not getattr(c, '_somente_bf', False)]
    origens += [c for c in cortes_c1 if c.vol_disponivel > EPSILON and not getattr(c, '_somente_bf', False)]

    destinos_ca = [a for a in aterros_ca if a.vol_disponivel > EPSILON]
    destinos_cf = [a for a in aterros_cf if a.vol_disponivel > EPSILON]
    destinos    = destinos_ca + destinos_cf

    if not origens or not destinos:
        return [], 0

    aes_validos = [ae for ae in config.emprestimos if ae.valido] if incluir_ae else []
    bfs_validos = [bf for bf in config.bota_foras  if bf.valido] if incluir_bf else []

    n_ae  = len(aes_validos)
    n_bf  = len(bfs_validos)
    n_dest_real = len(destinos)

    m = len(origens) + n_ae
    n = n_dest_real + n_bf

    custos = [[INFINITO] * n for _ in range(m)]

    for i, corte in enumerate(origens):
        cat = corte.categoria
        for j, aterro in enumerate(destinos):
            # Verificar restrição de categoria do aterro via restricoes
            if restricoes is not None:
                if not restricoes.aterro_aceita(aterro.ramo, cat):
                    continue
            else:
                # Fallback: usar flags _aceita_cX se existirem
                if hasattr(aterro, '_aceita_c1'):
                    if cat == 'C1' and not aterro._aceita_c1: continue
                    if cat == 'C2' and not aterro._aceita_c2: continue
                    if cat == 'C3' and not aterro._aceita_c3: continue

            dmt = calcular_dmt(corte.cmv, aterro.cmv, config,
                               corte.ramo, aterro.ramo,
                               permitir_cruzamento=permitir_cruzamento)
            if not dmt_ok(dmt, config):
                continue
            r_aterro = restricoes.get(aterro.ramo) if restricoes else None
            tem_restricao_aterro = (r_aterro is not None and r_aterro.corte_somente_bf)
            if cat == "C3":
                if aterro.categoria != "CA": continue
                if not tem_restricao_aterro and not aterro.aceita_c3: continue
                if not tem_restricao_aterro:
                    ja_recebeu = aterro.vol_total_hom - aterro.vol_disponivel
                    if ja_recebeu >= aterro.vol_max_c3: continue
                custos[i][j] = dmt
            elif cat == "C2":
                custos[i][j] = dmt if aterro.categoria == "CA" else dmt + PENALIDADE_C2CF
            elif cat == "C1":
                custos[i][j] = dmt

        for k, bf in enumerate(bfs_validos):
            dmt_bf = bf.dmt_para(corte.cmv, config, corte.ramo)
            # Se não há AE cadastrado, penalizar BF para garantir que
            # aterros sejam atendidos antes. Com AE cadastrado, BF entra
            # sem penalidade pois AE e BF otimizam juntos.
            inservivel_corte = getattr(corte, '_somente_bf', False)
            if not inservivel_corte and n_ae == 0:
                dmt_bf += PENALIDADE_BF
            custos[i][n_dest_real + k] = dmt_bf

    for k, ae in enumerate(aes_validos):
        idx = len(origens) + k
        for j, aterro in enumerate(destinos):
            custos[idx][j] = ae.dmt_para(aterro.cmv, config, aterro.ramo)
        for kb in range(n_bf):
            custos[idx][n_dest_real + kb] = 0.0

    ofertas  = [c.vol_disponivel for c in origens]
    ofertas += [ae.capacidade_hom for ae in aes_validos]
    demandas  = [a.vol_disponivel for a in destinos]
    demandas += [bf.capacidade    for bf in bfs_validos]

    resultado = resolver_transporte(custos, ofertas, demandas, otimizar=True)

    print(f"  Matriz {len(ofertas)}×{len(demandas)} | "
          f"AE={n_ae} BF={n_bf} | "
          f"Iterações: {resultado.iteracoes} | "
          f"Custo: {resultado.custo_total:,.2f} km·m³")

    num_bf = 1
    num_ae = 1

    for i, j, vol in resultado.alocacoes:
        if vol <= EPSILON:
            continue
        if j >= n_dest_real + n_bf:
            if i < len(origens) and incluir_bf:
                corte = origens[i]
                inservivel = getattr(corte, '_somente_bf', False)
                bf = min(bfs_validos, key=lambda b: b.dmt_para(corte.cmv, config, corte.ramo)) \
                     if bfs_validos else None
                linhas.append(linha_bota_fora(corte, vol, bf, mapeamento.prefixo_bf,
                                              num_bf, inservivel=inservivel, config=config))
                corte.vol_disponivel = round(corte.vol_disponivel - vol, 4)
                num_bf += 1
            continue
        if i >= len(origens) + n_ae:
            continue
        if n_ae > 0 and i >= len(origens):
            idx_ae = i - len(origens)
            if idx_ae < n_ae and j < n_dest_real:
                aterro = destinos[j]
                ae = aes_validos[idx_ae]
                linhas.append(linha_emprestimo(aterro, vol, ae, mapeamento.prefixo_ae,
                                               num_ae, config=config))
                aterro.vol_disponivel = round(aterro.vol_disponivel - vol, 4)
                num_ae += 1
            continue
        if n_bf > 0 and j >= n_dest_real:
            idx_bf = j - n_dest_real
            if idx_bf < n_bf and i < len(origens):
                corte = origens[i]
                inservivel = getattr(corte, '_somente_bf', False)
                bf = bfs_validos[idx_bf]
                linhas.append(linha_bota_fora(corte, vol, bf, mapeamento.prefixo_bf,
                                              num_bf, inservivel=inservivel, config=config))
                corte.vol_disponivel = round(corte.vol_disponivel - vol, 4)
                num_bf += 1
            continue
        if i < len(origens) and j < n_dest_real:
            corte  = origens[i]
            aterro = destinos[j]
            inservivel = getattr(corte, '_somente_bf', False)
            if corte.categoria == "C3":
                ja_recebeu = aterro.vol_total_hom - aterro.vol_disponivel
                espaco = max(0, aterro.vol_max_c3 - ja_recebeu)
                vol = min(vol, espaco)
            if vol <= EPSILON:
                continue
            resultado_linha = linha_corte_aterro(corte, aterro, vol, config,
                                                  inservivel=inservivel)
            if isinstance(resultado_linha, list):
                linhas.extend(resultado_linha)
            else:
                linhas.append(resultado_linha)
            corte.vol_disponivel  = round(corte.vol_disponivel - vol, 4)
            aterro.vol_disponivel = round(aterro.vol_disponivel - vol, 4)

    return linhas, resultado.iteracoes


# ---------------------------------------------------------------------------
# Função principal de distribuição (sem mudança na lógica de ETAPAs)
# ---------------------------------------------------------------------------

def distribuir(resultados: List[ResultadoDeteccao],
               mapeamento: MapeamentoMateriais,
               params: ParametrosDistribuicao,
               config: ConfigDistribuicao,
               restricoes=None) -> ResultadoDistribuicao:

    resultado  = ResultadoDistribuicao()
    linhas: List[LinhaQDM] = []
    total_iter = 0
    num_bf     = 1
    num_ae     = 1

    def get_params(ramo_nome):
        if isinstance(params, dict):
            return params.get(ramo_nome, list(params.values())[0])
        return params

    aes_validos = [ae for ae in config.emprestimos if ae.valido]
    bfs_validos = [bf for bf in config.bota_foras  if bf.valido]

    tem_ae  = bool(aes_validos)
    tem_bf  = bool(bfs_validos)
    otimizar = config.estrategia == "otimizar"

    # Relações com pistas paralelas — ramos que entram juntos na rodada interna
    pares_paralelos = set()
    for rel in config.relacoes:
        if rel.pistas_paralelas or rel.usar_rodada_interna:
            par = (min(rel.ramo_a, rel.ramo_b), max(rel.ramo_a, rel.ramo_b))
            pares_paralelos.add(par)

    cls_: List[Trecho] = []
    c3s:  List[Trecho] = []
    c2s:  List[Trecho] = []
    c1s:  List[Trecho] = []
    cas:  List[Trecho] = []
    cfs:  List[Trecho] = []

    for res in resultados:
        for t in res.trechos:
            if t.tipo == TipoTrecho.CL:        cls_.append(t)
            elif t.tipo == TipoTrecho.CORTE:
                if t.categoria == "C3":        c3s.append(t)
                elif t.categoria == "C2":      c2s.append(t)
                elif t.categoria == "C1":      c1s.append(t)
            elif t.tipo == TipoTrecho.ATERRO:
                if t.categoria == "CA":        cas.append(t)
                elif t.categoria == "CF":      cfs.append(t)

    # Aplicar restrições
    if restricoes is not None and restricoes.tem_restricoes():
        for t in c1s + c2s + c3s:
            if restricoes.corte_somente_bf(t.ramo):
                t._somente_bf = True
                t._material_inservivel = True  # flag para redistribuição
        for t in cas + cfs:
            r = restricoes.get(t.ramo)
            if r and not r.aterro_sem_restricao():
                t._aceita_c1 = r.aterro_aceita_c1
                t._aceita_c2 = r.aterro_aceita_c2
                t._aceita_c3 = r.aterro_aceita_c3
                t._usa_ae    = r.aterro_usa_ae
                t._ae_label  = r.ae_label


    for t in c3s + c2s + c1s + cas + cfs:
        t.vol_disponivel = t.vol_total_hom

    # ETAPA 0: Compensações Laterais
    print("\n--- Lançando Compensações Laterais ---")
    for cl in cls_:
        if (restricoes is not None and
                restricoes.tem_restricoes() and
                restricoes.corte_somente_bf(cl.ramo)):
            bf = min(bfs_validos, key=lambda b: b.dmt_para(cl.cmv, config, cl.ramo)) \
                 if bfs_validos else None
            label_c1 = f"{mapeamento.prefixo_c1}{num_bf}"
            dmt_t = bf.dmt_para(cl.cmv, config, cl.ramo) if bf and bf.valido else 0.0
            linhas.append(LinhaQDM(
                label_origem=label_c1,
                estaca_ini_origem=cl.estaca_ini,
                cmv_origem=cl.cmv_label,
                estaca_fin_origem=cl.estaca_fin,
                vol_c1=cl.vol_total_hom, vol_c2=0.0, vol_c3=0.0,
                vol_total=round(cl.vol_total_hom, 4),
                dmt_fixa=0.0, dmt_var=round(dmt_t, 6), dmt_total=dmt_t,
                label_destino=bf.nome if bf and bf.valido else f"{mapeamento.prefixo_bf}{num_bf}",
                estaca_ini_destino="",
                cmv_destino="", estaca_fin_destino="",
                tipo_destino="BF", ramo_origem=cl.ramo, ramo_destino="",
                obs="", flag_nao_soma_corte=0, flag_nao_soma_aterro=0,
                material_inservivel=True,
            ))
            num_bf += 1
        else:
            linhas.append(linha_cl(cl, config))
    total_cl = sum(cl.vol_total_hom for cl in cls_)
    print(f"  Total CL: {total_cl:,.2f} m³ ({len(cls_)} trechos)")

    # ETAPA 1: Distribuição interna
    print(f"\n--- Distribuição Interna ({config.estrategia}) ---")
    ramos_processados = set()

    for par in pares_paralelos:
        ramo_a, ramo_b = par
        ramos_processados.add(ramo_a)
        ramos_processados.add(ramo_b)
        p_a = get_params(ramo_a)
        c1_par = [c for c in c1s if c.ramo in (ramo_a, ramo_b) and c.vol_disponivel > EPSILON]
        c2_par = [c for c in c2s if c.ramo in (ramo_a, ramo_b) and c.vol_disponivel > EPSILON
                  and get_params(c.ramo).usar_corte2_interno]
        c3_par = [c for c in c3s if c.ramo in (ramo_a, ramo_b) and c.vol_disponivel > EPSILON
                  and get_params(c.ramo).usar_corte3_interno]
        ca_par = [a for a in cas if a.ramo in (ramo_a, ramo_b) and a.vol_disponivel > EPSILON]
        cf_par = [a for a in cfs if a.ramo in (ramo_a, ramo_b) and a.vol_disponivel > EPSILON]
        if not (c1_par or c2_par or c3_par) or not (ca_par or cf_par):
            continue
        print(f"  Par paralelo: {ramo_a} ↔ {ramo_b}")
        l, it = montar_e_resolver_matriz(c3_par, c2_par, c1_par, ca_par, cf_par,
                                          p_a, config, mapeamento,
                                          incluir_ae=tem_ae and otimizar,
                                          incluir_bf=tem_bf and otimizar,
                                          permitir_cruzamento=True,
                                          restricoes=restricoes)
        linhas += l
        total_iter += it

    ramos_com_corte = list(dict.fromkeys(t.ramo for t in c3s + c2s + c1s))
    for ramo in ramos_com_corte:
        if ramo in ramos_processados:
            continue
        p = get_params(ramo)
        c1_int = [c for c in c1s if c.ramo == ramo and c.vol_disponivel > EPSILON]
        c2_int = [c for c in c2s if c.ramo == ramo and c.vol_disponivel > EPSILON
                  and p.usar_corte2_interno]
        c3_int = [c for c in c3s if c.ramo == ramo and c.vol_disponivel > EPSILON
                  and p.usar_corte3_interno]
        ca_int = [a for a in cas if a.ramo == ramo and a.vol_disponivel > EPSILON]
        cf_int = [a for a in cfs if a.ramo == ramo and a.vol_disponivel > EPSILON]
        if not (c1_int or c2_int or c3_int) or not (ca_int or cf_int):
            continue
        print(f"  Ramo: {ramo}")
        l, it = montar_e_resolver_matriz(c3_int, c2_int, c1_int, ca_int, cf_int,
                                          p, config, mapeamento,
                                          incluir_ae=tem_ae and otimizar,
                                          incluir_bf=tem_bf and otimizar,
                                          permitir_cruzamento=False,
                                          restricoes=restricoes)
        linhas += l
        total_iter += it

    # ETAPA 2: Distribuição externa
    ca_def = [a for a in cas if a.vol_disponivel > EPSILON]
    cf_def = [a for a in cfs if a.vol_disponivel > EPSILON]
    c3_sob = [c for c in c3s if c.vol_disponivel > EPSILON]
    c2_sob = [c for c in c2s if c.vol_disponivel > EPSILON]
    c1_sob = [c for c in c1s if c.vol_disponivel > EPSILON]

    # Pré-alocação C3 exclusivo
    cas_so_c3 = [a for a in ca_def if (
        hasattr(a, '_aceita_c1') and not a._aceita_c1 and
        hasattr(a, '_aceita_c2') and not a._aceita_c2 and
        hasattr(a, '_aceita_c3') and a._aceita_c3)]
    if cas_so_c3 and c3_sob:
        print(f"\n--- Pré-alocação C3 exclusivo ({len(cas_so_c3)} aterros) ---")
        for aterro in cas_so_c3:
            cortes_ord = sorted([c for c in c3_sob if c.vol_disponivel > EPSILON],
                                 key=lambda c: calcular_dmt(c.cmv, aterro.cmv, config,
                                                             c.ramo, aterro.ramo, True))
            for corte in cortes_ord:
                if aterro.vol_disponivel <= EPSILON: break
                if corte.vol_disponivel <= EPSILON: continue
                dmt = calcular_dmt(corte.cmv, aterro.cmv, config, corte.ramo, aterro.ramo, True)
                if dmt >= INFINITO: continue
                vol = min(corte.vol_disponivel, aterro.vol_disponivel)
                lca = linha_corte_aterro(corte, aterro, vol, config)
                if isinstance(lca, list): linhas += lca
                else: linhas.append(lca)
                corte.vol_disponivel  = round(corte.vol_disponivel  - vol, 6)
                aterro.vol_disponivel = round(aterro.vol_disponivel - vol, 6)
        ca_def = [a for a in cas if a.vol_disponivel > EPSILON]
        cf_def = [a for a in cfs if a.vol_disponivel > EPSILON]
        c3_sob = [c for c in c3s if c.vol_disponivel > EPSILON]
        c2_sob = [c for c in c2s if c.vol_disponivel > EPSILON]
        c1_sob = [c for c in c1s if c.vol_disponivel > EPSILON]

    # Pré-alocação prioritária C3→C2→C1
    if restricoes is not None and restricoes.tem_restricoes():
        aterros_prio = [
            a for a in ca_def
            if (r := restricoes.get(a.ramo)) and getattr(r, 'prioridade_c3_c2_c1', False)
        ]
        if aterros_prio:
            print(f"\n--- Pré-alocação prioritária C3→C2→C1 ---")
            for cats, pool in [("C3", c3_sob), ("C2", c2_sob), ("C1", c1_sob)]:
                cortes_disp = [c for c in pool if c.vol_disponivel > EPSILON]
                if not cortes_disp: continue
                for aterro in aterros_prio:
                    if aterro.vol_disponivel <= EPSILON: continue
                    # Verificar se o aterro aceita esta categoria
                    # Usa restricoes diretamente — não depende de flags _aceita_cX
                    if not restricoes.aterro_aceita(aterro.ramo, cats):
                        continue
                    cortes_ord = sorted(cortes_disp,
                                        key=lambda c: calcular_dmt(c.cmv, aterro.cmv, config,
                                                                     c.ramo, aterro.ramo, True))
                    for corte in cortes_ord:
                        if aterro.vol_disponivel <= EPSILON: break
                        if corte.vol_disponivel <= EPSILON: continue
                        dmt = calcular_dmt(corte.cmv, aterro.cmv, config,
                                           corte.ramo, aterro.ramo, True)
                        if dmt >= INFINITO: continue
                        vol = min(corte.vol_disponivel, aterro.vol_disponivel)
                        lca = linha_corte_aterro(corte, aterro, vol, config)
                        if isinstance(lca, list): linhas += lca
                        else: linhas.append(lca)
                        corte.vol_disponivel  = round(corte.vol_disponivel  - vol, 6)
                        aterro.vol_disponivel = round(aterro.vol_disponivel - vol, 6)
                        print(f"  {cats} {corte.label} ({corte.ramo}) → "
                              f"{aterro.label} ({aterro.ramo}) "
                              f"vol={vol:,.2f} DMT={dmt:.4f}km")
            ca_def = [a for a in cas if a.vol_disponivel > EPSILON]
            cf_def = [a for a in cfs if a.vol_disponivel > EPSILON]
            c3_sob = [c for c in c3s if c.vol_disponivel > EPSILON]
            c2_sob = [c for c in c2s if c.vol_disponivel > EPSILON]
            c1_sob = [c for c in c1s if c.vol_disponivel > EPSILON]

    # Excluir da ETAPA 2 aterros com restricao de categoria (aceita_c1=False ou aceita_c2=False)
    # Esses aterros só recebem material via pré-alocação controlada
    # Se ainda têm déficit após a pré-alocação → vão para AE na ETAPA 3
    # Excluir da ETAPA 2 aterros com restrição de categoria
    # Usa restricoes diretamente — não depende de flags _aceita_cX
    def _tem_restricao_cat(aterro):
        if restricoes is None: return False
        r = restricoes.get(aterro.ramo)
        if r is None: return False
        return not r.aterro_sem_restricao()

    ca_def_ext = [a for a in ca_def if not _tem_restricao_cat(a)]
    cf_def_ext = cf_def  # CF sem restricao especial de categoria

    if (c3_sob or c2_sob or c1_sob) and (ca_def_ext or cf_def_ext):
        _p_ext = list(params.values())[0] if isinstance(params, dict) else params
        print(f"\n--- Distribuição Externa ({config.estrategia}) ---")
        l, it = montar_e_resolver_matriz(c3_sob, c2_sob, c1_sob, ca_def_ext, cf_def_ext,
                                          _p_ext, config, mapeamento,
                                          incluir_ae=tem_ae and otimizar,
                                          incluir_bf=tem_bf and otimizar,
                                          permitir_cruzamento=True,
                                          restricoes=restricoes)
        linhas += l
        total_iter += it

    # ETAPA 3: Déficit residual → AE
    ca_def2 = [a for a in cas if a.vol_disponivel > EPSILON]
    cf_def2 = [a for a in cfs if a.vol_disponivel > EPSILON]
    if ca_def2 or cf_def2:
        print(f"\n--- Déficit residual → Empréstimo ---")
        # Corte normal sobrando: só inservível pode ter sobrado legitimamente
        corte_normal_sobrando = any(
            c.vol_disponivel > EPSILON and not getattr(c, '_somente_bf', False)
            for c in c3s + c2s + c1s
        )
        for aterro in ca_def2 + cf_def2:
            if aterro.vol_disponivel <= EPSILON: continue
            vol = aterro.vol_disponivel
            ae = None
            if aes_validos:
                ae = min(aes_validos, key=lambda a: a.dmt_para(aterro.cmv, config, aterro.ramo))
            # Sem AE cadastrado e com corte normal sobrando: déficit ilegítimo
            # (corte deveria ter ido para o aterro — não cria fictício)
            if not ae and corte_normal_sobrando:
                resultado.alertas.append(
                    f"ATENÇÃO: {aterro.label} ({aterro.ramo}) "
                    f"falta {vol:,.2f} m³ — corte disponível não alcançou o aterro!")
                continue
            linhas.append(linha_emprestimo(aterro, vol, ae, mapeamento.prefixo_ae,
                                            num_ae, config=config))
            if not ae:
                resultado.alertas.append(
                    f"DÉFICIT: {aterro.label} ({aterro.ramo}) "
                    f"falta {vol:,.2f} m³ — sem material disponível!")
            num_ae += 1
            aterro.vol_disponivel = 0

    # ETAPA 4: Sobra de corte → BF
    cortes_sobra = [c for c in c3s + c2s + c1s if c.vol_disponivel > EPSILON]
    if cortes_sobra:
        print(f"\n--- Sobra de corte → Bota Fora ---")
        for corte in cortes_sobra:
            inservivel = getattr(corte, '_material_inservivel', False)
            bf = min(bfs_validos, key=lambda b: b.dmt_para(corte.cmv, config, corte.ramo)) \
                 if bfs_validos else None
            linhas.append(linha_bota_fora(corte, corte.vol_disponivel, bf,
                                           mapeamento.prefixo_bf, num_bf,
                                           inservivel=inservivel, config=config))
            num_bf += 1
            corte.vol_disponivel = 0

    # Consolidar residuos numericos do Stepping-Stone
    linhas = _consolidar_linhas(linhas)

    resultado.custo_total = round(sum(
        l.dmt_total * l.vol_total
        for l in linhas
        if l.tipo_destino not in ("CL", "BF")
    ), 2)
    resultado.iteracoes  = total_iter
    resultado.linhas_qdm = linhas
    return resultado


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def imprimir_distribuicao(resultado: ResultadoDistribuicao):
    print(f"\n{'='*80}")
    print("RESULTADO DA DISTRIBUIÇÃO — QDM")
    print(f"{'='*80}")
    print(f"Total de linhas: {len(resultado.linhas_qdm)}")
    print(f"Iterações totais: {resultado.iteracoes}")
    print(f"Custo total:      {resultado.custo_total:,.2f} km·m³\n")
    for l in resultado.linhas_qdm:
        print(f"  {l.label_origem:<8} {l.cmv_origem:<14} "
              f"{l.vol_total:>10,.2f} {l.dmt_total:>8.3f} "
              f"{l.label_destino:<8} {l.cmv_destino:<14} "
              f"{l.tipo_destino:>4} {l.flag_nao_soma_corte:>4}  {l.obs}")
    if resultado.alertas:
        print(f"\n{'!'*50}")
        for a in resultado.alertas:
            print(f"  {a}")