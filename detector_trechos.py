"""
detector_trechos.py
-------------------
Detecta trechos de corte, aterro e CL após desconto da compensação lateral.

Lógica:
1. CL = estacas onde Corte1 > 0 E CA > 0 simultaneamente
   - CL por estaca = min(Corte1, CA)
   - Corte1_liq = Corte1 - CL
   - CA_liq = CA - CL
2. Trechos definidos após desconto:
   - Corte1_liq > 0 → CORTE
   - CA_liq > 0    → ATERRO CA
   - CF separado e independente
   - Corte2, Corte3 → integrais, sem CL
3. Formato de estaca conforme unidade do projeto (km ou estaca de 20m)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from leitor_civil import DadosEstaca, DadosRamo, DadosProjeto


# ---------------------------------------------------------------------------
# Tipo de trecho
# ---------------------------------------------------------------------------

class TipoTrecho:
    CORTE  = "CORTE"
    ATERRO = "ATERRO"
    CL     = "C. LATERAL"


# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------

@dataclass
class ParametrosDistribuicao:
    """Parâmetros de distribuição por ramo."""
    usar_corte3_interno:   bool  = False
    usar_corte2_interno:   bool  = False
    aceita_corte3_externo: bool  = True
    aceita_corte2_externo: bool  = True
    vol_min_aterro_c3:     float = 500.0
    pct_max_c3:            float = 50.0

    @property
    def usar_corte3(self): return self.usar_corte3_interno
    @property
    def usar_corte2(self): return self.usar_corte2_interno


@dataclass
class MapeamentoMateriais:
    corte1:    List[str] = field(default_factory=list)
    corte2:    List[str] = field(default_factory=list)
    corte3:    List[str] = field(default_factory=list)
    aterro_ca: List[str] = field(default_factory=list)
    aterro_cf: List[str] = field(default_factory=list)
    ignorar:   List[str] = field(default_factory=list)
    prefixo_c1: str = "C-"
    prefixo_c2: str = "C2-"
    prefixo_c3: str = "C3-"
    prefixo_ca: str = "CA-"
    prefixo_cf: str = "CF-"
    prefixo_cl: str = "CL-"
    prefixo_bf: str = "BF-"
    prefixo_ae: str = "AE-"

    def todos_cortes(self):  return self.corte1 + self.corte2 + self.corte3
    def todos_aterros(self): return self.aterro_ca + self.aterro_cf


# ---------------------------------------------------------------------------
# Estrutura de trecho
# ---------------------------------------------------------------------------

@dataclass
class Trecho:
    tipo:       str
    ramo:       str
    numero:     int
    prefixo:    str
    categoria:  str
    estaca_ini:    str   = ""
    estaca_fin:    str   = ""
    estaca_ini_m:  float = 0.0
    estaca_fin_m:  float = 0.0
    extensao:      float = 0.0
    cmv:           float = 0.0
    cmv_label:     str   = ""
    volumes_geo:   Dict[str, float] = field(default_factory=dict)
    volumes_hom:   Dict[str, float] = field(default_factory=dict)
    vol_total_hom: float = 0.0
    aceita_c3:     bool  = False
    vol_max_c3:    float = 0.0
    vol_disponivel: float = 0.0
    estacas: List[DadosEstaca] = field(default_factory=list)

    @property
    def label(self): return f"{self.prefixo}{self.numero}"


@dataclass
class ResultadoDeteccao:
    ramo:    str
    trechos: List[Trecho] = field(default_factory=list)

    def cortes(self):       return [t for t in self.trechos if t.tipo == TipoTrecho.CORTE]
    def aterros_ca(self):   return [t for t in self.trechos if t.tipo == TipoTrecho.ATERRO and t.categoria == "CA"]
    def aterros_cf(self):   return [t for t in self.trechos if t.tipo == TipoTrecho.ATERRO and t.categoria == "CF"]
    def compensacoes(self): return [t for t in self.trechos if t.tipo == TipoTrecho.CL]


# ---------------------------------------------------------------------------
# Formatação de estaca
# ---------------------------------------------------------------------------

def metros_para_estaca(metros: float, unidade: str = "estaca") -> str:
    """
    Converte metros para formato de estaca conforme unidade do projeto.

    unidade='estaca': estacas de 20m
        ex: 2350m → estaca 117, resto 10m → '117+10,000'
        ex: 2385m → estaca 119, resto 5m  → '119+05,000'

    unidade='km':
        ex: 2350m → 2km + 350m → '2+350,000'
    """
    if unidade == "km":
        km    = int(metros // 1000)
        resto = metros % 1000
        return f"{km}+{resto:07.3f}".replace(".", ",")
    else:
        # estacas de 20m
        num_estaca = int(metros // 20)
        resto      = metros % 20
        return f"{num_estaca}+{resto:06.3f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Cálculo de CMv
# ---------------------------------------------------------------------------

def calcular_cmv(estacas: List[DadosEstaca],
                 vols_liq: Dict[str, float]) -> float:
    """
    CMv = Σ(estaca_m × vol_liq) / Σ(vol_liq)
    Recebe dicionário {estaca_label: vol_liquido}.
    """
    soma_vol = sum(vols_liq.values())
    if soma_vol == 0:
        if estacas:
            return (estacas[0].estaca_m + estacas[-1].estaca_m) / 2
        return 0.0
    soma_pos = sum(
        e.estaca_m * vols_liq.get(e.estaca, 0.0)
        for e in estacas
    )
    return soma_pos / soma_vol


# ---------------------------------------------------------------------------
# Função principal de detecção
# ---------------------------------------------------------------------------

def detectar_trechos(ramo: DadosRamo,
                     mapeamento: MapeamentoMateriais,
                     params: ParametrosDistribuicao,
                     unidade: str = "estaca",
                     restricoes=None) -> ResultadoDeteccao:
    """
    Detecta trechos após desconto da compensação lateral.
    restricoes: ConfigRestricoes | None
        Quando corte_somente_bf=True para o ramo, CA não desconta CL
        (o CL vai para BF, não compensa o aterro).
    """
    resultado = ResultadoDeteccao(ramo=ramo.nome)

    # Verificar se ramo tem corte_somente_bf — nesse caso CA não desconta CL
    ramo_somente_bf = (restricoes is not None and
                       restricoes.tem_restricoes() and
                       restricoes.corte_somente_bf(ramo.nome))

    if not ramo.estacas:
        return resultado

    # ------------------------------------------------------------------
    # Passo 1: calcular CL por estaca e volumes líquidos
    # ------------------------------------------------------------------
    # CL = min(Vh_Corte1, Vh_CA) quando ambos > 0
    # Corte1_liq = Corte1 - CL
    # CA_liq     = CA - CL

    vols_c1_liq:  Dict[str, float] = {}  # {estaca_label: vol}
    vols_ca_liq:  Dict[str, float] = {}
    vols_cl:      Dict[str, float] = {}
    vols_c2:      Dict[str, float] = {}
    vols_c3:      Dict[str, float] = {}
    vols_cf:      Dict[str, float] = {}

    # volumes geométricos por estaca (para tipo 2 — preserva vol_geo separado do hom)
    vols_c1_geo:  Dict[str, float] = {}
    vols_ca_geo:  Dict[str, float] = {}
    vols_c2_geo:  Dict[str, float] = {}
    vols_c3_geo:  Dict[str, float] = {}
    vols_cf_geo:  Dict[str, float] = {}
    vols_cl_geo:  Dict[str, float] = {}

    for e in ramo.estacas:
        vh_c1 = sum(e.volumes_h.get(m, 0.0) for m in mapeamento.corte1)
        vh_ca = sum(e.volumes_h.get(m, 0.0) for m in mapeamento.aterro_ca)
        vh_c2 = sum(e.volumes_h.get(m, 0.0) for m in mapeamento.corte2)
        vh_c3 = sum(e.volumes_h.get(m, 0.0) for m in mapeamento.corte3)
        vh_cf = sum(e.volumes_h.get(m, 0.0) for m in mapeamento.aterro_cf)

        # volumes geométricos (e.volumes — sem FH)
        vg_c1 = sum(e.volumes.get(m, 0.0) for m in mapeamento.corte1)
        vg_ca = sum(e.volumes.get(m, 0.0) for m in mapeamento.aterro_ca)
        vg_c2 = sum(e.volumes.get(m, 0.0) for m in mapeamento.corte2)
        vg_c3 = sum(e.volumes.get(m, 0.0) for m in mapeamento.corte3)
        vg_cf = sum(e.volumes.get(m, 0.0) for m in mapeamento.aterro_cf)

        # CL = min dos dois quando coexistem
        # Mínimo de 0.1 m³ — abaixo disso é ruído numérico, zera
        CL_MINIMO = 0.1
        cl_raw = min(vh_c1, vh_ca) if (vh_c1 > 0 and vh_ca > 0) else 0.0
        cl = cl_raw if cl_raw >= CL_MINIMO else 0.0

        # Corte líquido: vh_c1 - cl
        # Se c1_liq é muito pequeno MAS cl é real (>= 0.1), mantém o CL
        # Só zera c1_liq se for ruído (< 0.1 E cl_raw também era ruído)
        c1_liq = vh_c1 - cl
        if c1_liq < CL_MINIMO and cl_raw < CL_MINIMO:
            # Tudo é ruído — zera ambos
            c1_liq = 0.0
            cl = 0.0

        # vol_geo do CL proporcional ao FH de cada material
        # C1: cl_geo = cl * (vg_c1/vh_c1) — usa FH do corte
        # CA: cl_geo = cl * (vg_ca/vh_ca) — usa FH do aterro
        cl_geo_c1 = cl * (vg_c1 / vh_c1) if vh_c1 > 0 else cl
        cl_geo_ca = cl * (vg_ca / vh_ca) if vh_ca > 0 else cl

        vols_cl[e.estaca]     = round(cl, 6)
        vols_c1_liq[e.estaca] = round(c1_liq, 6)
        # Se ramo tem corte_somente_bf: CA não desconta CL (CL vai para BF)
        if ramo_somente_bf:
            vols_ca_liq[e.estaca] = round(vh_ca, 6)
        else:
            vols_ca_liq[e.estaca] = round(vh_ca - cl, 6)
        vols_c2[e.estaca]     = round(vh_c2, 6)
        vols_c3[e.estaca]     = round(vh_c3, 6)
        vols_cf[e.estaca]     = round(vh_cf, 6)

        # geométricos corrigidos
        vols_c1_geo[e.estaca] = round(vg_c1 - cl_geo_c1, 6)
        # Se ramo tem corte_somente_bf: CA geo não desconta CL (igual ao hom)
        if ramo_somente_bf:
            vols_ca_geo[e.estaca] = round(vg_ca, 6)
        else:
            vols_ca_geo[e.estaca] = round(vg_ca - cl_geo_ca, 6)
        vols_c2_geo[e.estaca] = round(vg_c2, 6)
        vols_c3_geo[e.estaca] = round(vg_c3, 6)
        vols_cf_geo[e.estaca] = round(vg_cf, 6)
        vols_cl_geo[e.estaca] = round(cl_geo_c1, 6)  # CL geo = CL × FH_C1

    # ------------------------------------------------------------------
    # Passo 2: detectar trechos contínuos por categoria
    # ------------------------------------------------------------------
    trechos: List[Trecho] = []

    def detectar_seq(vol_dict, tipo, prefixo, categoria,
                     aceita_c3_check=False, vol_dict_geo=None):
        """Detecta sequências contínuas com volume > 0."""
        nonlocal trechos
        numero = 0
        em_trecho = False
        est_trecho: List[DadosEstaca] = []

        for e in ramo.estacas:
            vol = vol_dict.get(e.estaca, 0.0)
            ativo = vol > 0

            if ativo and not em_trecho:
                em_trecho = True
                est_trecho = [e]
            elif ativo and em_trecho:
                est_trecho.append(e)
            elif not ativo and em_trecho:
                est_trecho.append(e)
                numero += 1
                t = _criar_trecho(ramo, tipo, prefixo, categoria,
                                  numero, est_trecho, vol_dict,
                                  params, unidade, aceita_c3_check,
                                  vol_dict_geo=vol_dict_geo)
                trechos.append(t)
                em_trecho = False
                est_trecho = []

        if em_trecho and est_trecho:
            numero += 1
            t = _criar_trecho(ramo, tipo, prefixo, categoria,
                              numero, est_trecho, vol_dict,
                              params, unidade, aceita_c3_check,
                              vol_dict_geo=vol_dict_geo)
            trechos.append(t)

    # Corte 1ª líquido
    detectar_seq(vols_c1_liq, TipoTrecho.CORTE, mapeamento.prefixo_c1, "C1",
                 vol_dict_geo=vols_c1_geo)

    # Corte 2ª
    detectar_seq(vols_c2, TipoTrecho.CORTE, mapeamento.prefixo_c2, "C2",
                 vol_dict_geo=vols_c2_geo)

    # Corte 3ª
    detectar_seq(vols_c3, TipoTrecho.CORTE, mapeamento.prefixo_c3, "C3",
                 vol_dict_geo=vols_c3_geo)

    # Aterro CA líquido
    # aceita_c3_check usa parâmetros do ramo — não hardcoded True
    # usar_corte3_interno=True → aceita C3 do próprio ramo
    # aceita_corte3_externo=True → aceita C3 de outros ramos
    # ambos False → não aceita C3 (default)
    _aceita_c3 = params.usar_corte3_interno or params.aceita_corte3_externo
    detectar_seq(vols_ca_liq, TipoTrecho.ATERRO, mapeamento.prefixo_ca, "CA",
                 aceita_c3_check=_aceita_c3, vol_dict_geo=vols_ca_geo)

    # Aterro CF (independente)
    detectar_seq(vols_cf, TipoTrecho.ATERRO, mapeamento.prefixo_cf, "CF",
                 vol_dict_geo=vols_cf_geo)

    # Compensação lateral — calculada em volumes hom, geo = hom
    detectar_seq(vols_cl, TipoTrecho.CL, mapeamento.prefixo_cl, "CL")

    # Ordenar por estaca inicial e categoria
    trechos.sort(key=lambda t: (t.estaca_ini_m, t.categoria))

    # Remover trechos com volume quase zero — mesclar no vizinho e renumerar
    trechos = _limpar_trechos(trechos)

    resultado.trechos = trechos
    return resultado


def _limpar_trechos(trechos: list, limiar: float = 0.01) -> list:
    """
    Remove trechos com vol_total_hom < limiar somando seu volume
    no vizinho do mesmo prefixo (tipo) mais próximo.
    Renumera sequencialmente cada grupo de prefixo ao final.

    Garante:
    - Sem trechos zerados no Excel/QDM
    - Numeração contínua (sem pulos)
    - Volume total conservado
    """
    if not trechos:
        return trechos

    trechos_ok = list(trechos)  # cópia para não modificar o original

    # Iterar enquanto houver trechos a eliminar
    alterou = True
    while alterou:
        alterou = False
        i = 0
        while i < len(trechos_ok):
            t = trechos_ok[i]
            if t.vol_total_hom < limiar:
                # Encontrar vizinho mais próximo do mesmo prefixo
                mesmo_tipo = [(j, trechos_ok[j])
                              for j in range(len(trechos_ok))
                              if j != i and trechos_ok[j].prefixo == t.prefixo
                              and trechos_ok[j].vol_total_hom >= limiar]

                if mesmo_tipo:
                    # Vizinho mais próximo por posição
                    j, viz = min(mesmo_tipo,
                                 key=lambda jt: abs(jt[1].estaca_ini_m - t.estaca_ini_m))
                    # Somar volume no vizinho
                    viz.vol_total_hom  = round(viz.vol_total_hom  + t.vol_total_hom,  4)
                    viz.vol_disponivel = round(viz.vol_disponivel + t.vol_total_hom,  4)
                    # Atualizar vol_max_c3 proporcionalmente se elegível
                    if viz.aceita_c3 and viz.vol_max_c3 > 0:
                        pass  # vol_max_c3 será recalculado na distribuição
                    # Remover trecho zerado
                    trechos_ok.pop(i)
                    alterou = True
                    # Não incrementar i — verificar mesmo índice novamente
                else:
                    # Sem vizinho do mesmo tipo — descartar silenciosamente
                    trechos_ok.pop(i)
                    alterou = True
            else:
                i += 1

    # Renumerar cada grupo de prefixo sequencialmente
    from collections import defaultdict
    contadores = defaultdict(int)
    for t in trechos_ok:
        contadores[t.prefixo] += 1
        t.numero = contadores[t.prefixo]

    return trechos_ok


def _criar_trecho(ramo: DadosRamo,
                  tipo: str, prefixo: str, categoria: str, numero: int,
                  estacas: List[DadosEstaca],
                  vol_dict: Dict[str, float],
                  params: ParametrosDistribuicao,
                  unidade: str,
                  aceita_c3_check: bool,
                  vol_dict_geo: Dict[str, float] = None) -> Trecho:
    """Cria um Trecho a partir de uma sequência de estacas."""
    e_ini = estacas[0]
    e_fin = estacas[-1]
    extensao = e_fin.estaca_m - e_ini.estaca_m

    # Volumes líquidos acumulados (homogeneizados)
    vol_total = sum(vol_dict.get(e.estaca, 0.0) for e in estacas)

    # Volume geométrico acumulado (sem FH) — só preenchido para tipo 2
    vol_total_geo = None
    if vol_dict_geo is not None:
        vol_total_geo = sum(vol_dict_geo.get(e.estaca, 0.0) for e in estacas)

    # CMv usando volumes líquidos
    vols_para_cmv = {e.estaca: vol_dict.get(e.estaca, 0.0) for e in estacas}
    cmv_m     = calcular_cmv(estacas, vols_para_cmv)
    cmv_label = metros_para_estaca(cmv_m, unidade)

    # Elegibilidade para C3 (só CA)
    aceita_c3  = False
    vol_max_c3 = 0.0
    if aceita_c3_check and tipo == TipoTrecho.ATERRO and categoria == "CA":
        if vol_total >= params.vol_min_aterro_c3:
            aceita_c3  = True
            vol_max_c3 = round(vol_total * params.pct_max_c3 / 100.0, 4)

    # volumes_geo: se tiver vol_geo separado usa ele, senão igual ao hom (tipo 1)
    vg = {"total": round(vol_total_geo, 4)} if vol_total_geo is not None else {}

    return Trecho(
        tipo=tipo, ramo=ramo.nome, numero=numero,
        prefixo=prefixo, categoria=categoria,
        estaca_ini   = metros_para_estaca(e_ini.estaca_m, unidade),
        estaca_fin   = metros_para_estaca(e_fin.estaca_m, unidade),
        estaca_ini_m = e_ini.estaca_m,
        estaca_fin_m = e_fin.estaca_m,
        extensao     = extensao,
        cmv          = cmv_m,
        cmv_label    = cmv_label,
        volumes_geo  = vg,
        volumes_hom  = {"total": round(vol_total, 4)},
        vol_total_hom= round(vol_total, 4),
        aceita_c3    = aceita_c3,
        vol_max_c3   = vol_max_c3,
        vol_disponivel = round(vol_total, 4),
        estacas      = estacas
    )


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def imprimir_trechos(resultado: ResultadoDeteccao,
                     params: ParametrosDistribuicao):
    print(f"\n{'='*72}")
    print(f"TRECHOS DETECTADOS — {resultado.ramo}")
    print(f"{'='*72}")
    print(f"Usar C3: {'Sim' if params.usar_corte3 else 'Não'} | "
          f"Usar C2: {'Sim' if params.usar_corte2 else 'Não'} | "
          f"Vol. mín. p/ C3: {params.vol_min_aterro_c3:,.0f} m³ | "
          f"% máx. C3: {params.pct_max_c3:.0f}%")
    print(f"Total de trechos: {len(resultado.trechos)}\n")

    for t in resultado.trechos:
        print(f"  {t.label:<8} | {t.tipo:<12} | "
              f"{t.estaca_ini} → {t.estaca_fin} "
              f"(ext: {t.extensao:.3f} m)")
        print(f"           CMv: {t.cmv_label:<15} | "
              f"Vol. Hom.: {t.vol_total_hom:>12,.2f} m³")

        if t.tipo == TipoTrecho.ATERRO and t.categoria == "CA":
            elegivel = "SIM" if t.aceita_c3 else f"NÃO (vol < {params.vol_min_aterro_c3:,.0f} m³)"
            print(f"           Elegível p/ C3: {elegivel}", end="")
            if t.aceita_c3:
                print(f" | Vol. máx. C3: {t.vol_max_c3:,.2f} m³", end="")
            print()
        print()