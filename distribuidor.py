"""
distribuidor.py
---------------
Algoritmo de distribuição de terraplenagem.

Ordem de distribuição:
1. CL lançada no QDM com DMT fixa configurável
2. Corte 3ª (se confirmado) → CA elegíveis internos primeiro, depois outros ramos
3. Corte 2ª (se confirmado) → CA internos, sobra → CF, depois outros ramos
4. Corte 1ª → CA e CF restantes internos, depois outros ramos
5. Déficit restante → Empréstimo
6. Sobra de corte → Bota fora

Regras:
- Distribuição INTERNA primeiro, excesso vai para outros ramos depois
- DMT calculada por CMv (mesmo ramo) ou valor configurado (entre ramos)
- DMT mínima: 0,050 km
- Bota fora: mais próximo disponível
- Empréstimo: mais próximo ou ordem cadastrada (config)
- flag_nao_soma=1 quando material cruza entre ramos
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from detector_trechos import (
    Trecho, TipoTrecho, ResultadoDeteccao,
    MapeamentoMateriais, ParametrosDistribuicao
)

DMT_MINIMA = 0.050  # km


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class LocalAuxiliar:
    """Bota fora ou jazida de empréstimo."""
    nome:        str
    estaca_m:    float   # posição no eixo em metros
    afastamento: float   # afastamento do eixo em metros
    tipo:        str     # "BF" ou "AE"

    def dmt_para(self, cmv_origem_m: float) -> float:
        dist = abs(self.estaca_m - cmv_origem_m) / 1000.0
        af   = self.afastamento / 1000.0
        return max(round(dist + af, 6), DMT_MINIMA)


@dataclass
class ConfigDistribuicao:
    """Configurações globais da distribuição."""
    tipo_projeto:            str   = "intersecao"  # 'segmento' ou 'intersecao'
    usar_dmt_maxima:         bool  = False
    dmt_maxima_km:           float = 999.0
    dmt_cl:                  float = 0.050   # DMT fixa da compensação lateral (km)
    emprestimo_mais_proximo: bool  = True
    dmt_entre_ramos:         Dict[str, Dict[str, float]] = field(default_factory=dict)
    bota_foras:              List[LocalAuxiliar] = field(default_factory=list)
    emprestimos:             List[LocalAuxiliar] = field(default_factory=list)


@dataclass
class LinhaQDM:
    """Linha do Quadro de Distribuição de Material."""
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
    tipo_destino:       str   = ""   # CA, CF, CL, BF, AE
    ramo_origem:        str   = ""
    ramo_destino:       str   = ""
    obs:                str   = ""
    flag_nao_soma:      int   = 0    # 1 = não soma no resumo do destino


@dataclass
class ResultadoDistribuicao:
    linhas_qdm: List[LinhaQDM] = field(default_factory=list)
    alertas:    List[str]      = field(default_factory=list)


# ---------------------------------------------------------------------------
# DMT helpers
# ---------------------------------------------------------------------------

def calcular_dmt(cmv_orig_m: float, cmv_dest_m: float,
                 config: ConfigDistribuicao,
                 ramo_orig: str, ramo_dest: str) -> float:
    if ramo_orig != ramo_dest:
        dmt = config.dmt_entre_ramos.get(ramo_orig, {}).get(ramo_dest, 0.0)
        if dmt == 0:
            dmt = config.dmt_entre_ramos.get(ramo_dest, {}).get(ramo_orig, 0.0)
        return max(dmt, DMT_MINIMA)
    dist = abs(cmv_dest_m - cmv_orig_m) / 1000.0
    return max(round(dist, 6), DMT_MINIMA)


def dmt_ok(dmt: float, config: ConfigDistribuicao) -> bool:
    if config.usar_dmt_maxima and dmt > config.dmt_maxima_km:
        return False
    return True


def bf_mais_proximo(cmv_m: float,
                    config: ConfigDistribuicao) -> Optional[LocalAuxiliar]:
    if not config.bota_foras:
        return None
    return min(config.bota_foras, key=lambda b: b.dmt_para(cmv_m))


def ae_para_aterro(cmv_m: float,
                   config: ConfigDistribuicao) -> Optional[LocalAuxiliar]:
    if not config.emprestimos:
        return None
    if config.emprestimo_mais_proximo:
        return min(config.emprestimos, key=lambda a: a.dmt_para(cmv_m))
    return config.emprestimos[0]


# ---------------------------------------------------------------------------
# Criadores de linha QDM
# ---------------------------------------------------------------------------

def linha_corte_aterro(corte: Trecho, aterro: Trecho,
                       vol: float, cat: str,
                       config: ConfigDistribuicao) -> LinhaQDM:
    dmt = calcular_dmt(corte.cmv, aterro.cmv, config,
                       corte.ramo, aterro.ramo)
    flag = 1 if corte.ramo != aterro.ramo else 0
    obs  = f"material vem do {corte.ramo}" if flag else ""
    return LinhaQDM(
        label_origem      = corte.label,
        estaca_ini_origem = corte.estaca_ini,
        cmv_origem        = corte.cmv_label,
        estaca_fin_origem = corte.estaca_fin,
        vol_c1    = vol if cat == "C1" else 0.0,
        vol_c2    = vol if cat == "C2" else 0.0,
        vol_c3    = vol if cat == "C3" else 0.0,
        vol_total = round(vol, 4),
        dmt_fixa  = DMT_MINIMA,
        dmt_var   = round(dmt - DMT_MINIMA, 6),
        dmt_total = dmt,
        label_destino      = aterro.label,
        estaca_ini_destino = aterro.estaca_ini,
        cmv_destino        = aterro.cmv_label,
        estaca_fin_destino = aterro.estaca_fin,
        tipo_destino  = aterro.categoria,
        ramo_origem   = corte.ramo,
        ramo_destino  = aterro.ramo,
        obs           = obs,
        flag_nao_soma = flag
    )


def linha_cl(cl: Trecho, config: ConfigDistribuicao) -> LinhaQDM:
    """Lança CL no QDM com DMT fixa configurada."""
    return LinhaQDM(
        label_origem      = cl.label,
        estaca_ini_origem = cl.estaca_ini,
        cmv_origem        = cl.cmv_label,
        estaca_fin_origem = cl.estaca_fin,
        vol_c1    = cl.vol_total_hom,
        vol_total = cl.vol_total_hom,
        dmt_fixa  = config.dmt_cl,
        dmt_var   = 0.0,
        dmt_total = config.dmt_cl,
        label_destino      = cl.label.replace("CL", "CA"),
        estaca_ini_destino = cl.estaca_ini,
        cmv_destino        = cl.cmv_label,
        estaca_fin_destino = cl.estaca_fin,
        tipo_destino  = "CL",
        ramo_origem   = cl.ramo,
        ramo_destino  = cl.ramo,
        obs           = "compensação lateral",
        flag_nao_soma = 0
    )


def linha_bota_fora(corte: Trecho, vol: float, cat: str,
                    bf: Optional[LocalAuxiliar],
                    prefixo_bf: str, num: int) -> LinhaQDM:
    dmt = bf.dmt_para(corte.cmv) if bf else 0.0
    return LinhaQDM(
        label_origem      = corte.label,
        estaca_ini_origem = corte.estaca_ini,
        cmv_origem        = corte.cmv_label,
        estaca_fin_origem = corte.estaca_fin,
        vol_c1    = vol if cat == "C1" else 0.0,
        vol_c2    = vol if cat == "C2" else 0.0,
        vol_c3    = vol if cat == "C3" else 0.0,
        vol_total = round(vol, 4),
        dmt_fixa  = DMT_MINIMA,
        dmt_var   = round(max(dmt - DMT_MINIMA, 0), 6),
        dmt_total = dmt,
        label_destino = f"{prefixo_bf}{num}",
        estaca_ini_destino = bf.nome if bf else "",
        tipo_destino  = "BF",
        ramo_origem   = corte.ramo,
        obs = bf.nome if bf else "sem bota fora cadastrado",
        flag_nao_soma = 0
    )


def linha_emprestimo(aterro: Trecho, vol: float,
                     ae: LocalAuxiliar,
                     prefixo_ae: str, num: int) -> LinhaQDM:
    dmt = ae.dmt_para(aterro.cmv)
    return LinhaQDM(
        label_origem      = f"{prefixo_ae}{num}",
        estaca_ini_origem = ae.nome,
        cmv_origem        = "",
        estaca_fin_origem = "",
        vol_total = round(vol, 4),
        dmt_fixa  = DMT_MINIMA,
        dmt_var   = round(max(dmt - DMT_MINIMA, 0), 6),
        dmt_total = dmt,
        label_destino      = aterro.label,
        estaca_ini_destino = aterro.estaca_ini,
        cmv_destino        = aterro.cmv_label,
        estaca_fin_destino = aterro.estaca_fin,
        tipo_destino  = aterro.categoria,
        ramo_destino  = aterro.ramo,
        obs = f"empréstimo: {ae.nome}",
        flag_nao_soma = 0
    )


# ---------------------------------------------------------------------------
# Distribuição por categoria — interno primeiro, depois externo
# ---------------------------------------------------------------------------

def distribuir_corte_para_aterros(
        cortes: List[Trecho],
        aterros: List[Trecho],
        cat: str,
        config: ConfigDistribuicao,
        apenas_interno: bool = True) -> List[LinhaQDM]:
    """
    Distribui uma lista de cortes para uma lista de aterros.
    apenas_interno=True: só distribui dentro do mesmo ramo.
    apenas_interno=False: distribui entre ramos diferentes.
    """
    linhas: List[LinhaQDM] = []

    for corte in cortes:
        if corte.vol_disponivel <= 0:
            continue

        # Filtrar aterros: interno ou externo conforme flag
        aterros_filtrados = [
            a for a in aterros
            if a.vol_disponivel > 0
            and (a.ramo == corte.ramo) == apenas_interno
        ]

        # Ordenar por DMT crescente
        aterros_ord = sorted(
            aterros_filtrados,
            key=lambda a: calcular_dmt(corte.cmv, a.cmv, config,
                                       corte.ramo, a.ramo)
        )

        for aterro in aterros_ord:
            if corte.vol_disponivel <= 0:
                break

            dmt = calcular_dmt(corte.cmv, aterro.cmv, config,
                               corte.ramo, aterro.ramo)
            if not dmt_ok(dmt, config):
                continue

            # Para C3: respeitar vol_max_c3
            if cat == "C3":
                ja_recebeu = aterro.vol_total_hom - aterro.vol_disponivel
                espaco_c3  = max(0, aterro.vol_max_c3 - ja_recebeu)
                vol = min(corte.vol_disponivel, espaco_c3, aterro.vol_disponivel)
            else:
                vol = min(corte.vol_disponivel, aterro.vol_disponivel)

            if vol <= 0:
                continue

            linhas.append(linha_corte_aterro(corte, aterro, vol, cat, config))
            corte.vol_disponivel  = round(corte.vol_disponivel - vol, 4)
            aterro.vol_disponivel = round(aterro.vol_disponivel - vol, 4)

    return linhas


# ---------------------------------------------------------------------------
# Função principal de distribuição
# ---------------------------------------------------------------------------

def distribuir(resultados: List[ResultadoDeteccao],
               mapeamento: MapeamentoMateriais,
               params: ParametrosDistribuicao,
               config: ConfigDistribuicao) -> ResultadoDistribuicao:

    resultado = ResultadoDistribuicao()
    linhas: List[LinhaQDM] = []

    # Coletar trechos de todos os ramos
    cls:    List[Trecho] = []
    c3s:    List[Trecho] = []
    c2s:    List[Trecho] = []
    c1s:    List[Trecho] = []
    cas:    List[Trecho] = []
    cfs:    List[Trecho] = []

    for res in resultados:
        for t in res.trechos:
            if t.tipo == TipoTrecho.CL:
                cls.append(t)
            elif t.tipo == TipoTrecho.CORTE:
                if t.categoria == "C3": c3s.append(t)
                elif t.categoria == "C2": c2s.append(t)
                elif t.categoria == "C1": c1s.append(t)
            elif t.tipo == TipoTrecho.ATERRO:
                if t.categoria == "CA": cas.append(t)
                elif t.categoria == "CF": cfs.append(t)

    # Inicializar volumes disponíveis
    for t in c3s + c2s + c1s + cas + cfs:
        t.vol_disponivel = t.vol_total_hom

    num_bf = 1
    num_ae = 1

    # ------------------------------------------------------------------
    # ETAPA 0: Lançar compensações laterais no QDM
    # ------------------------------------------------------------------
    print("\n--- Lançando Compensações Laterais ---")
    for cl in cls:
        linhas.append(linha_cl(cl, config))
        print(f"  {cl.label} → CL: {cl.vol_total_hom:,.2f} m³ "
              f"(DMT fixa: {config.dmt_cl:.3f} km)")

    # ------------------------------------------------------------------
    # ETAPA 1: Corte 3ª (se confirmado)
    # ------------------------------------------------------------------
    if params.usar_corte3 and c3s:
        ca_elegiveis = [ca for ca in cas if ca.aceita_c3]
        print("\n--- Distribuindo Corte 3ª ---")

        # Interno primeiro
        linhas += distribuir_corte_para_aterros(
            c3s, ca_elegiveis, "C3", config, apenas_interno=True)

        # Externo depois
        linhas += distribuir_corte_para_aterros(
            c3s, ca_elegiveis, "C3", config, apenas_interno=False)

        # Sobra → bota fora
        for corte in c3s:
            if corte.vol_disponivel > 0:
                bf = bf_mais_proximo(corte.cmv, config)
                linhas.append(linha_bota_fora(
                    corte, corte.vol_disponivel, "C3",
                    bf, mapeamento.prefixo_bf, num_bf))
                print(f"  {corte.label} → {mapeamento.prefixo_bf}{num_bf}: "
                      f"{corte.vol_disponivel:,.2f} m³ (sobra C3)")
                num_bf += 1
                corte.vol_disponivel = 0

    # ------------------------------------------------------------------
    # ETAPA 2: Corte 2ª (se confirmado)
    # ------------------------------------------------------------------
    if params.usar_corte2 and c2s:
        print("\n--- Distribuindo Corte 2ª ---")

        # Interno primeiro → CA
        linhas += distribuir_corte_para_aterros(
            c2s, cas, "C2", config, apenas_interno=True)
        # Interno → CF (sobra)
        linhas += distribuir_corte_para_aterros(
            c2s, cfs, "C2", config, apenas_interno=True)
        # Externo → CA
        linhas += distribuir_corte_para_aterros(
            c2s, cas, "C2", config, apenas_interno=False)
        # Externo → CF
        linhas += distribuir_corte_para_aterros(
            c2s, cfs, "C2", config, apenas_interno=False)

        # Sobra → bota fora
        for corte in c2s:
            if corte.vol_disponivel > 0:
                bf = bf_mais_proximo(corte.cmv, config)
                linhas.append(linha_bota_fora(
                    corte, corte.vol_disponivel, "C2",
                    bf, mapeamento.prefixo_bf, num_bf))
                print(f"  {corte.label} → {mapeamento.prefixo_bf}{num_bf}: "
                      f"{corte.vol_disponivel:,.2f} m³ (sobra C2)")
                num_bf += 1
                corte.vol_disponivel = 0

    # ------------------------------------------------------------------
    # ETAPA 3: Corte 1ª
    # ------------------------------------------------------------------
    if c1s:
        print("\n--- Distribuindo Corte 1ª ---")

        # Interno → CA
        linhas += distribuir_corte_para_aterros(
            c1s, cas, "C1", config, apenas_interno=True)
        # Interno → CF
        linhas += distribuir_corte_para_aterros(
            c1s, cfs, "C1", config, apenas_interno=True)
        # Externo → CA
        linhas += distribuir_corte_para_aterros(
            c1s, cas, "C1", config, apenas_interno=False)
        # Externo → CF
        linhas += distribuir_corte_para_aterros(
            c1s, cfs, "C1", config, apenas_interno=False)

        # Sobra → bota fora
        for corte in c1s:
            if corte.vol_disponivel > 0:
                bf = bf_mais_proximo(corte.cmv, config)
                linhas.append(linha_bota_fora(
                    corte, corte.vol_disponivel, "C1",
                    bf, mapeamento.prefixo_bf, num_bf))
                print(f"  {corte.label} → {mapeamento.prefixo_bf}{num_bf}: "
                      f"{corte.vol_disponivel:,.2f} m³ (sobra C1)")
                num_bf += 1
                corte.vol_disponivel = 0

    # ------------------------------------------------------------------
    # ETAPA 4: Déficit → Empréstimo
    # ------------------------------------------------------------------
    deficit = [t for t in cas + cfs if t.vol_disponivel > 0]
    if deficit:
        print("\n--- Suprindo déficit com Empréstimo ---")
        for aterro in deficit:
            if aterro.vol_disponivel <= 0:
                continue
            ae = ae_para_aterro(aterro.cmv, config)
            if ae:
                vol = aterro.vol_disponivel
                linhas.append(linha_emprestimo(
                    aterro, vol, ae,
                    mapeamento.prefixo_ae, num_ae))
                print(f"  {mapeamento.prefixo_ae}{num_ae} ({ae.nome}) → "
                      f"{aterro.label}: {vol:,.2f} m³")
                num_ae += 1
                aterro.vol_disponivel = 0
            else:
                resultado.alertas.append(
                    f"DÉFICIT: {aterro.label} ({aterro.ramo}) "
                    f"falta {aterro.vol_disponivel:,.2f} m³ "
                    f"— sem empréstimo cadastrado!")
                print(f"  ALERTA: {aterro.label} déficit de "
                      f"{aterro.vol_disponivel:,.2f} m³")

    resultado.linhas_qdm = linhas
    return resultado


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def imprimir_distribuicao(resultado: ResultadoDistribuicao):
    print(f"\n{'='*80}")
    print("RESULTADO DA DISTRIBUIÇÃO — QDM")
    print(f"{'='*80}")
    print(f"Total de linhas: {len(resultado.linhas_qdm)}\n")

    print(f"  {'Origem':<8} {'CMv Orig':<14} {'Vol(m³)':>10} "
          f"{'DMT(km)':>8} {'Destino':<8} {'CMv Dest':<14} "
          f"{'Tipo':>4} {'Flag':>4}  OBS")
    print(f"  {'-'*90}")

    for l in resultado.linhas_qdm:
        print(f"  {l.label_origem:<8} {l.cmv_origem:<14} "
              f"{l.vol_total:>10,.2f} {l.dmt_total:>8.3f} "
              f"{l.label_destino:<8} {l.cmv_destino:<14} "
              f"{l.tipo_destino:>4} {l.flag_nao_soma:>4}  {l.obs}")

    if resultado.alertas:
        print(f"\n{'!'*50}")
        for a in resultado.alertas:
            print(f"  {a}")

    # Totais
    total_c1 = sum(l.vol_c1 for l in resultado.linhas_qdm)
    total_c2 = sum(l.vol_c2 for l in resultado.linhas_qdm)
    total_c3 = sum(l.vol_c3 for l in resultado.linhas_qdm)
    total_bf = sum(l.vol_total for l in resultado.linhas_qdm if l.tipo_destino == "BF")
    total_ae = sum(l.vol_total for l in resultado.linhas_qdm if l.tipo_destino in ("CA","CF") and l.label_origem.startswith("AE"))
    total_cl = sum(l.vol_total for l in resultado.linhas_qdm if l.tipo_destino == "CL")

    print(f"\n  Resumo:")
    print(f"    Compensação lateral:  {total_cl:>12,.2f} m³")
    print(f"    Corte 1ª distribuído: {total_c1:>12,.2f} m³")
    print(f"    Corte 2ª distribuído: {total_c2:>12,.2f} m³")
    print(f"    Corte 3ª distribuído: {total_c3:>12,.2f} m³")
    print(f"    Bota fora:            {total_bf:>12,.2f} m³")
    print(f"    Empréstimo:           {total_ae:>12,.2f} m³")


# ---------------------------------------------------------------------------
# Execução direta para teste
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from leitor_civil import ler_multiplos_arquivos, ConfigLeitura
    from detector_trechos import detectar_trechos

    arquivo = r"E:\Dropbox\VisualStudio\PROGRAMA PARA DISTRIBUIÇÃO\DISTRIBUICAO\DISTRIBUICAO\SEGB_INT 03_Civil.xlsx"

    config_leitura = ConfigLeitura(
        unidade='estaca', em_distancia=False, dist_estaca=20.0)

    mapeamento = MapeamentoMateriais(
        corte1=['Corte1'], corte2=['Corte2'], corte3=['Corte3'],
        aterro_ca=['Aterro'], aterro_cf=['CF'],
        ignorar=['Limpeza', 'Solo Mole']
    )
    params = ParametrosDistribuicao(
        usar_corte3=False, usar_corte2=False,
        vol_min_aterro_c3=500.0, pct_max_c3=50.0
    )
    config = ConfigDistribuicao(
        tipo_projeto='intersecao',
        dmt_cl=0.050,
        usar_dmt_maxima=False,
        emprestimo_mais_proximo=True,
        dmt_entre_ramos={
            "INT 03 - RAMO 100": {"INT 03 - RAMO 300": 2.5}
        },
        bota_foras=[], emprestimos=[]
    )

    projeto = ler_multiplos_arquivos(
        [{"caminho": arquivo, "tipo": 1}], config_leitura)

    
    resultados = []
    for ramo in projeto.ramos:
        resultado = detectar_trechos(ramo, mapeamento, params, unidade="estaca")
        imprimir_trechos(resultado, params)
        resultados.append(resultado)