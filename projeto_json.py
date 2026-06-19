"""
projeto_json.py (v2)
--------------------
Serialização/deserialização do projeto de terraplenagem.

NOVIDADES v2:
- Versões automáticas (_v1, _v2, ...) ao salvar
- JSON armazena APENAS entradas — resultados sempre recalculados
- Conversão automática de relações v1.0 → v2.0
- Validação de integridade ao carregar
- campo material_inservivel em LinhaQDM
- LocalAuxiliar com eixo_ref e pos_relativa_m
"""

import json
import os
from datetime import datetime
from typing import List

VERSAO = "2.0"
VERSAO_LEGADA = "1.0"

# Imports internos
from leitor_civil import ConfigLeitura
from detector_trechos import (
    Trecho, ResultadoDeteccao,
    MapeamentoMateriais, ParametrosDistribuicao
)
from distribuidor2 import (
    RelacaoSegmentos, LocalAuxiliar,
    ConfigDistribuicao, LinhaQDM, ResultadoDistribuicao
)


# ---------------------------------------------------------------------------
# Serialização (objeto → dict)
# ---------------------------------------------------------------------------

def _config_leitura_to_dict(c: ConfigLeitura) -> dict:
    return {
        "unidade":        c.unidade,
        "em_distancia":   c.em_distancia,
        "dist_estaca":    c.dist_estaca,
        "dist_max_bloco": c.dist_max_bloco,
        "fatores_hom":    c.fatores_hom,
    }


def _mapeamento_to_dict(m: MapeamentoMateriais) -> dict:
    return {
        "corte1":    m.corte1, "corte2": m.corte2, "corte3": m.corte3,
        "aterro_ca": m.aterro_ca, "aterro_cf": m.aterro_cf,
        "ignorar":   m.ignorar,
        "prefixo_c1": m.prefixo_c1, "prefixo_c2": m.prefixo_c2,
        "prefixo_c3": m.prefixo_c3, "prefixo_ca": m.prefixo_ca,
        "prefixo_cf": m.prefixo_cf, "prefixo_cl": m.prefixo_cl,
        "prefixo_bf": m.prefixo_bf, "prefixo_ae": m.prefixo_ae,
    }


def _params_to_dict(p) -> dict:
    if isinstance(p, dict):
        return {ramo: _params_single_to_dict(v) for ramo, v in p.items()}
    return _params_single_to_dict(p)


def _params_single_to_dict(p: ParametrosDistribuicao) -> dict:
    return {
        "usar_corte3_interno":   p.usar_corte3_interno,
        "usar_corte2_interno":   p.usar_corte2_interno,
        "aceita_corte3_externo": p.aceita_corte3_externo,
        "aceita_corte2_externo": p.aceita_corte2_externo,
        "vol_min_aterro_c3":     p.vol_min_aterro_c3,
        "pct_max_c3":            p.pct_max_c3,
    }


def _local_aux_to_dict(l: LocalAuxiliar) -> dict:
    return {
        "nome":           l.nome,
        "tipo":           l.tipo,
        "capacidade":     l.capacidade,
        "fh":             l.fh,
        "eixo_ref":       l.eixo_ref,
        "pos_relativa_m": l.pos_relativa_m,
        "afastamento":    l.afastamento,
        "estaca_m":       l.estaca_m,   # compatibilidade v1.0
        "cmv_label":      l.cmv_label,  # informativo
    }


def _relacao_to_dict(r: RelacaoSegmentos) -> dict:
    return {
        "ramo_a":            r.ramo_a,
        "ramo_b":            r.ramo_b,
        "tipo":              r.tipo,
        # pistas_paralelas
        "estaca_ini_a_m":    r.estaca_ini_a_m,
        "estaca_ini_b_m":    r.estaca_ini_b_m,
        "deslocamento_a_m":  r.deslocamento_a_m,
        "deslocamento_b_m":  r.deslocamento_b_m,
        "afastamento_m":     r.afastamento_m,
        # intersecao_marginal
        "pos_relativa_m":    r.pos_relativa_m,
        "dmt_fixa_km":       r.dmt_fixa_km,
        # compartilhados
        "pistas_paralelas":  r.pistas_paralelas,
        "usar_rodada_interna": r.usar_rodada_interna,
        "todos":             r.todos,
        "ramos_todos":       r.ramos_todos,
        # legados v1.0 (preservados para compatibilidade)
        "dist_inicio_m":     r.dist_inicio_m,
        "pista_antes":       r.pista_antes,
        "dist_estaca_m":     r.dist_estaca_m,
        "dist_fixa_m":       r.dist_fixa_m,
        "ref_a_m":           r.ref_a_m,
        "ref_b_m":           r.ref_b_m,
        "dist_refs_m":       r.dist_refs_m,
    }


def _config_dist_to_dict(c: ConfigDistribuicao) -> dict:
    return {
        "tipo_projeto":            c.tipo_projeto,
        "usar_dmt_maxima":         c.usar_dmt_maxima,
        "dmt_maxima_km":           c.dmt_maxima_km,
        "dmt_cl":                  c.dmt_cl,
        "emprestimo_mais_proximo": c.emprestimo_mais_proximo,
        "estrategia":              c.estrategia,
        "usar_encadeamento":       c.usar_encadeamento,
        "relacoes":                [_relacao_to_dict(r) for r in c.relacoes],
        "dmt_entre_ramos":         c.dmt_entre_ramos,
    }


def _trecho_to_dict(t: Trecho) -> dict:
    return {
        "tipo": t.tipo, "ramo": t.ramo, "numero": t.numero,
        "prefixo": t.prefixo, "categoria": t.categoria,
        "estaca_ini": t.estaca_ini, "estaca_fin": t.estaca_fin,
        "estaca_ini_m": t.estaca_ini_m, "estaca_fin_m": t.estaca_fin_m,
        "extensao": t.extensao, "cmv": t.cmv, "cmv_label": t.cmv_label,
        "vol_total_hom": t.vol_total_hom,
        "vol_total_geo": t.volumes_geo.get("total", t.vol_total_hom),
        "aceita_c3": t.aceita_c3, "vol_max_c3": t.vol_max_c3,
        "vol_disponivel": t.vol_disponivel,
    }


def _linha_qdm_to_dict(l: LinhaQDM) -> dict:
    return {
        "label_origem":       l.label_origem,
        "estaca_ini_origem":  l.estaca_ini_origem,
        "cmv_origem":         l.cmv_origem,
        "estaca_fin_origem":  l.estaca_fin_origem,
        "vol_c1":             l.vol_c1,
        "vol_c2":             l.vol_c2,
        "vol_c3":             l.vol_c3,
        "vol_total":          l.vol_total,
        "dmt_fixa":           l.dmt_fixa,
        "dmt_var":            l.dmt_var,
        "dmt_total":          l.dmt_total,
        "label_destino":      l.label_destino,
        "estaca_ini_destino": l.estaca_ini_destino,
        "cmv_destino":        l.cmv_destino,
        "estaca_fin_destino": l.estaca_fin_destino,
        "tipo_destino":       l.tipo_destino,
        "ramo_origem":        l.ramo_origem,
        "ramo_destino":       l.ramo_destino,
        "obs":                l.obs,
        "flag_nao_soma_corte":  getattr(l, "flag_nao_soma_corte",  0),
        "flag_nao_soma_aterro": getattr(l, "flag_nao_soma_aterro", 0),
        "vol_ca":             getattr(l, "vol_ca", 0.0),
        "vol_cf":             getattr(l, "vol_cf", 0.0),
        "material_inservivel": getattr(l, "material_inservivel", False),
    }


# ---------------------------------------------------------------------------
# Conversão v1.0 → v2.0
# ---------------------------------------------------------------------------

def _converter_relacao_v1_para_v2(d: dict) -> dict:
    """
    Converte relação do formato v1.0 para v2.0.
    Preserva campos legados para não perder informação.
    """
    tipo_v1 = d.get("tipo", "fixa")

    # Mapear tipos v1 → v2
    mapa_tipos = {
        "estaca":              "pistas_paralelas",
        "distancia":           "pistas_paralelas",
        "intersecao_interna":  "intersecao_marginal",
        "intersecao_externa":  "intersecao_marginal",
        "fixa":                "intersecao_marginal",
        # v2 (já corretos)
        "pistas_paralelas":    "pistas_paralelas",
        "intersecao_marginal": "intersecao_marginal",
    }

    tipo_v2 = mapa_tipos.get(tipo_v1, tipo_v1)
    d_novo = dict(d)
    d_novo["tipo"] = tipo_v2

    # Migrar campos específicos
    if tipo_v1 == "estaca":
        # estaca_ini_a_m e estaca_ini_b_m já existem
        # dist_inicio_m → deslocamento entre eixos
        d_novo.setdefault("deslocamento_a_m", 0.0)
        d_novo.setdefault("deslocamento_b_m", d.get("dist_inicio_m", 0.0))

    elif tipo_v1 == "distancia":
        # dist_fixa_m → deslocamento entre inícios
        d_novo.setdefault("deslocamento_a_m", 0.0)
        d_novo.setdefault("deslocamento_b_m", d.get("dist_fixa_m", 0.0))

    elif tipo_v1 in ("intersecao_interna",):
        # ref_a_m → pos_relativa_m
        d_novo.setdefault("pos_relativa_m", d.get("ref_a_m", 0.0))

    elif tipo_v1 == "intersecao_externa":
        # ref_a_m → pos_relativa_m (ponto de conexão no eixo A)
        d_novo.setdefault("pos_relativa_m", d.get("ref_a_m", 0.0))

    elif tipo_v1 == "fixa":
        # dmt_fixa_km já existe
        d_novo.setdefault("pos_relativa_m", 0.0)

    # Garantir campos novos com defaults
    d_novo.setdefault("deslocamento_a_m", 0.0)
    d_novo.setdefault("deslocamento_b_m", 0.0)
    d_novo.setdefault("pos_relativa_m", 0.0)
    d_novo.setdefault("usar_rodada_interna", d.get("pistas_paralelas", False))

    return d_novo


def _converter_local_aux_v1_para_v2(d: dict) -> dict:
    """Converte BF/AE v1.0 → v2.0."""
    d_novo = dict(d)
    # estaca_m → pos_relativa_m (mantém estaca_m para compatibilidade)
    if "estaca_m" in d and "pos_relativa_m" not in d:
        d_novo["pos_relativa_m"] = d["estaca_m"]
    d_novo.setdefault("eixo_ref", "")
    d_novo.setdefault("pos_relativa_m", 0.0)
    return d_novo


# ---------------------------------------------------------------------------
# Deserialização (dict → objeto)
# ---------------------------------------------------------------------------

def _dict_to_config_leitura(d: dict) -> ConfigLeitura:
    return ConfigLeitura(
        unidade        = d.get("unidade",        "estaca"),
        em_distancia   = d.get("em_distancia",   False),
        dist_estaca    = d.get("dist_estaca",     20.0),
        dist_max_bloco = d.get("dist_max_bloco",  20.0),
        fatores_hom    = d.get("fatores_hom",     {})
    )


def _dict_to_mapeamento(d: dict) -> MapeamentoMateriais:
    return MapeamentoMateriais(
        corte1    = d.get("corte1", []),
        corte2    = d.get("corte2", []),
        corte3    = d.get("corte3", []),
        aterro_ca = d.get("aterro_ca", []),
        aterro_cf = d.get("aterro_cf", []),
        ignorar   = d.get("ignorar", []),
        prefixo_c1 = d.get("prefixo_c1", "C-"),
        prefixo_c2 = d.get("prefixo_c2", "C2-"),
        prefixo_c3 = d.get("prefixo_c3", "C3-"),
        prefixo_ca = d.get("prefixo_ca", "CA-"),
        prefixo_cf = d.get("prefixo_cf", "CF-"),
        prefixo_cl = d.get("prefixo_cl", "CL-"),
        prefixo_bf = d.get("prefixo_bf", "BF-"),
        prefixo_ae = d.get("prefixo_ae", "AE-"),
    )


def _dict_to_params(d: dict):
    if not d:
        return ParametrosDistribuicao()
    primeiro = list(d.values())[0]
    if isinstance(primeiro, dict):
        return {ramo: _dict_to_single_params(v) for ramo, v in d.items()}
    return _dict_to_single_params(d)


def _dict_to_single_params(d: dict) -> ParametrosDistribuicao:
    return ParametrosDistribuicao(
        usar_corte3_interno   = d.get("usar_corte3_interno", d.get("usar_corte3", False)),
        usar_corte2_interno   = d.get("usar_corte2_interno", d.get("usar_corte2", False)),
        aceita_corte3_externo = d.get("aceita_corte3_externo", True),
        aceita_corte2_externo = d.get("aceita_corte2_externo", True),
        vol_min_aterro_c3     = d.get("vol_min_aterro_c3", 500.0),
        pct_max_c3            = d.get("pct_max_c3", 50.0),
    )


def _dict_to_local_aux(d: dict) -> LocalAuxiliar:
    d = _converter_local_aux_v1_para_v2(d)
    return LocalAuxiliar(
        nome           = d["nome"],
        tipo           = d["tipo"],
        capacidade     = d.get("capacidade", 0.0),
        fh             = d.get("fh", 1.25),
        eixo_ref       = d.get("eixo_ref", ""),
        pos_relativa_m = d.get("pos_relativa_m", 0.0),
        afastamento    = d.get("afastamento", 0.0),
        estaca_m       = d.get("estaca_m", 0.0),
        cmv_label      = d.get("cmv_label", ""),
    )


def _dict_to_relacao(d: dict) -> RelacaoSegmentos:
    d = _converter_relacao_v1_para_v2(d)
    return RelacaoSegmentos(
        ramo_a            = d["ramo_a"],
        ramo_b            = d["ramo_b"],
        tipo              = d["tipo"],
        estaca_ini_a_m    = d.get("estaca_ini_a_m",   0.0),
        estaca_ini_b_m    = d.get("estaca_ini_b_m",   0.0),
        deslocamento_a_m  = d.get("deslocamento_a_m", 0.0),
        deslocamento_b_m  = d.get("deslocamento_b_m", 0.0),
        afastamento_m     = d.get("afastamento_m",    0.0),
        pos_relativa_m    = d.get("pos_relativa_m",   0.0),
        dmt_fixa_km       = d.get("dmt_fixa_km",      0.0),
        pistas_paralelas  = d.get("pistas_paralelas", False),
        usar_rodada_interna = d.get("usar_rodada_interna", False),
        todos             = d.get("todos",            False),
        ramos_todos       = d.get("ramos_todos",      []),
        # legados v1.0
        dist_inicio_m     = d.get("dist_inicio_m",   0.0),
        pista_antes       = d.get("pista_antes",      "a"),
        dist_estaca_m     = d.get("dist_estaca_m",    20.0),
        dist_fixa_m       = d.get("dist_fixa_m",      0.0),
        ref_a_m           = d.get("ref_a_m",          0.0),
        ref_b_m           = d.get("ref_b_m",          0.0),
        dist_refs_m       = d.get("dist_refs_m",      0.0),
    )


def _dict_to_config_dist(d: dict) -> ConfigDistribuicao:
    return ConfigDistribuicao(
        tipo_projeto            = d.get("tipo_projeto", "segmento"),
        usar_dmt_maxima         = d.get("usar_dmt_maxima", False),
        dmt_maxima_km           = d.get("dmt_maxima_km", 999.0),
        dmt_cl                  = d.get("dmt_cl", 0.050),
        emprestimo_mais_proximo = d.get("emprestimo_mais_proximo", True),
        estrategia              = d.get("estrategia", "usar_tudo"),
        usar_encadeamento       = d.get("usar_encadeamento", False),
        relacoes = [_dict_to_relacao(r) for r in d.get("relacoes", [])],
        dmt_entre_ramos         = d.get("dmt_entre_ramos", {}),
        bota_foras  = [],
        emprestimos = [],
    )


def _dict_to_trecho(d: dict) -> Trecho:
    t = Trecho(
        tipo      = d["tipo"],
        ramo      = d["ramo"],
        numero    = d["numero"],
        prefixo   = d["prefixo"],
        categoria = d.get("categoria", ""),
        estaca_ini = d.get("estaca_ini", ""),
        estaca_fin = d.get("estaca_fin", ""),
        estaca_ini_m = d.get("estaca_ini_m", 0.0),
        estaca_fin_m = d.get("estaca_fin_m", 0.0),
        extensao     = d.get("extensao", 0.0),
        cmv          = d.get("cmv", 0.0),
        cmv_label    = d.get("cmv_label", ""),
        vol_total_hom = d.get("vol_total_hom", 0.0),
        aceita_c3   = d.get("aceita_c3", True),
        vol_max_c3  = d.get("vol_max_c3", 0.0),
    )
    t.vol_disponivel = d.get("vol_disponivel", t.vol_total_hom)
    vg = d.get("vol_total_geo", t.vol_total_hom)
    t.volumes_geo = {"total": vg}
    return t


def _dict_to_linha_qdm(d: dict) -> LinhaQDM:
    return LinhaQDM(
        label_origem       = d.get("label_origem", ""),
        estaca_ini_origem  = d.get("estaca_ini_origem", ""),
        cmv_origem         = d.get("cmv_origem", ""),
        estaca_fin_origem  = d.get("estaca_fin_origem", ""),
        vol_c1             = d.get("vol_c1", 0.0),
        vol_c2             = d.get("vol_c2", 0.0),
        vol_c3             = d.get("vol_c3", 0.0),
        vol_total          = d.get("vol_total", 0.0),
        dmt_fixa           = d.get("dmt_fixa", 0.0),
        dmt_var            = d.get("dmt_var", 0.0),
        dmt_total          = d.get("dmt_total", 0.0),
        label_destino      = d.get("label_destino", ""),
        estaca_ini_destino = d.get("estaca_ini_destino", ""),
        cmv_destino        = d.get("cmv_destino", ""),
        estaca_fin_destino = d.get("estaca_fin_destino", ""),
        tipo_destino       = d.get("tipo_destino", ""),
        ramo_origem        = d.get("ramo_origem", ""),
        ramo_destino       = d.get("ramo_destino", ""),
        obs                = d.get("obs", ""),
        flag_nao_soma_corte  = d.get("flag_nao_soma_corte",  0),
        flag_nao_soma_aterro = d.get("flag_nao_soma_aterro", 0),
        vol_ca             = d.get("vol_ca", 0.0),
        vol_cf             = d.get("vol_cf", 0.0),
        material_inservivel = d.get("material_inservivel", False),
    )


# ---------------------------------------------------------------------------
# Versionamento automático
# ---------------------------------------------------------------------------

def _proximo_caminho_versao(caminho_base: str) -> str:
    """
    Gera o próximo caminho versionado.
    Ex: projeto.json → projeto_v1.json → projeto_v2.json
    """
    base, ext = os.path.splitext(caminho_base)
    # Remover versão existente se houver
    import re
    base_limpo = re.sub(r'_v\d+$', '', base)

    v = 1
    while True:
        candidato = f"{base_limpo}_v{v}{ext}"
        if not os.path.exists(candidato):
            return candidato
        v += 1


def _validar_integridade(dados: dict) -> List[str]:
    """
    Valida integridade do JSON carregado.
    Retorna lista de problemas encontrados (vazia = tudo OK).
    """
    problemas = []

    # Verificar arquivos Excel
    for arq in dados.get("arquivos", []):
        caminho = arq.get("caminho", "")
        if caminho and not os.path.exists(caminho):
            problemas.append(f"Arquivo não encontrado: {caminho}")

    # Verificar ramos nas relações
    ramos_existentes = {r["nome"] for r in dados.get("ramos", [])}
    for rel in dados.get("config_dist", {}).get("relacoes", []):
        ra = rel.get("ramo_a", "")
        rb = rel.get("ramo_b", "")
        if ra and ra not in ramos_existentes:
            problemas.append(f"Relação referencia ramo inexistente: '{ra}'")
        if rb and rb not in ramos_existentes:
            problemas.append(f"Relação referencia ramo inexistente: '{rb}'")

    return problemas


# ---------------------------------------------------------------------------
# Salvar projeto
# ---------------------------------------------------------------------------

def salvar_projeto(
        caminho_json: str,
        nome_projeto: str,
        arquivos: List[dict],
        config_leitura: ConfigLeitura,
        mapeamento: MapeamentoMateriais,
        params,
        config_dist: ConfigDistribuicao,
        resultados_deteccao: List[ResultadoDeteccao],
        resultado_dist: ResultadoDistribuicao,
        caminho_excel: str = "",
        config_restricoes=None,
        criar_versao: bool = True) -> str:
    """
    Salva o projeto em JSON.
    Se criar_versao=True, cria novo arquivo versionado (_v1, _v2, ...).
    Retorna o caminho do arquivo salvo.
    """
    from restricoes_ramo import restricoes_to_dict as _restricoes_to_dict

    agora = datetime.now().isoformat(timespec="seconds")

    # Determinar caminho de saída
    if criar_versao:
        caminho_saida = _proximo_caminho_versao(caminho_json)
    else:
        caminho_saida = caminho_json

    # Preservar data_criacao
    data_criacao = agora
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                existente = json.load(f)
                data_criacao = existente.get("data_criacao", agora)
        except Exception:
            pass

    # Montar ramos com trechos e linhas QDM
    ramos_data = []
    for res in resultados_deteccao:
        linhas_ramo = [
            _linha_qdm_to_dict(l)
            for l in resultado_dist.linhas_qdm
            if (l.ramo_origem == res.ramo and l.flag_nao_soma_corte != 1)
            or (not l.ramo_origem and l.ramo_destino == res.ramo)
            or (l.ramo_destino == res.ramo and l.flag_nao_soma_corte == 1)
        ]
        ramos_data.append({
            "nome":             res.ramo,
            "data_atualizacao": agora,
            "trechos":          [_trecho_to_dict(t) for t in res.trechos],
            "linhas_qdm":       linhas_ramo,
        })

    projeto = {
        "versao":           VERSAO,
        "nome":             nome_projeto,
        "data_criacao":     data_criacao,
        "data_atualizacao": agora,
        "caminho_excel":    caminho_excel,
        "arquivos":         arquivos,
        "config_leitura":   _config_leitura_to_dict(config_leitura),
        "restricoes":       _restricoes_to_dict(config_restricoes) if config_restricoes else None,
        "mapeamento":       _mapeamento_to_dict(mapeamento),
        "params":           _params_to_dict(params),
        "config_dist":      _config_dist_to_dict(config_dist),
        "bota_foras":       [_local_aux_to_dict(b) for b in config_dist.bota_foras],
        "emprestimos":      [_local_aux_to_dict(e) for e in config_dist.emprestimos],
        "ramos":            ramos_data,
        "resultado": {
            "custo_total": resultado_dist.custo_total,
            "iteracoes":   resultado_dist.iteracoes,
            "alertas":     resultado_dist.alertas,
        }
    }

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(projeto, f, ensure_ascii=False, indent=2)

    print(f"Projeto salvo: {caminho_saida}")
    return caminho_saida


# ---------------------------------------------------------------------------
# Carregar projeto
# ---------------------------------------------------------------------------

def carregar_projeto(caminho_json: str,
                     validar: bool = True,
                     alertar_versao: bool = True) -> dict:
    """
    Carrega JSON e reconstrói todos os objetos.
    Converte automaticamente v1.0 → v2.0.
    """
    if not os.path.exists(caminho_json):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_json}")

    with open(caminho_json, "r", encoding="utf-8") as f:
        dados = json.load(f)

    versao = dados.get("versao", "1.0")
    print(f"\nCarregando projeto: {dados.get('nome', '')}")
    print(f"  Versão JSON: {versao}")
    print(f"  Criado em:     {dados.get('data_criacao', '')}")
    print(f"  Atualizado em: {dados.get('data_atualizacao', '')}")

    if alertar_versao and versao == VERSAO_LEGADA:
        print(f"  ⚠️  JSON v1.0 detectado — convertendo para v2.0 automaticamente.")
        print(f"      Recomendado: salvar como nova versão após rodar.")

    # Validação de integridade
    if validar:
        problemas = _validar_integridade(dados)
        if problemas:
            print(f"\n  ⚠️  Problemas de integridade encontrados:")
            for p in problemas:
                print(f"    - {p}")

    config_leitura = _dict_to_config_leitura(dados["config_leitura"])
    mapeamento     = _dict_to_mapeamento(dados["mapeamento"])
    params         = _dict_to_params(dados["params"])
    config_dist    = _dict_to_config_dist(dados["config_dist"])

    config_dist.bota_foras  = [_dict_to_local_aux(b) for b in dados.get("bota_foras", [])]
    config_dist.emprestimos = [_dict_to_local_aux(e) for e in dados.get("emprestimos", [])]

    resultados_deteccao = []
    for ramo_data in dados.get("ramos", []):
        from detector_trechos import ResultadoDeteccao
        res = ResultadoDeteccao(ramo=ramo_data["nome"])
        res.trechos = [_dict_to_trecho(t) for t in ramo_data.get("trechos", [])]
        resultados_deteccao.append(res)
        print(f"  Ramo carregado: {res.ramo} ({len(res.trechos)} trechos)")

    todas_linhas = []
    for ramo_data in dados.get("ramos", []):
        for ld in ramo_data.get("linhas_qdm", []):
            todas_linhas.append(_dict_to_linha_qdm(ld))

    resultado_dist = ResultadoDistribuicao(
        linhas_qdm  = todas_linhas,
        custo_total = dados.get("resultado", {}).get("custo_total", 0.0),
        iteracoes   = dados.get("resultado", {}).get("iteracoes", 0),
        alertas     = dados.get("resultado", {}).get("alertas", []),
    )

    def _carregar_restricoes(d):
        if not d:
            return None
        from restricoes_ramo import dict_to_restricoes
        return dict_to_restricoes(d)

    # Resolver caminhos dos arquivos Excel:
    # Prioridade 1 — mesmo nome na pasta onde está o JSON
    # Prioridade 2 — caminho absoluto original
    pasta_json = os.path.dirname(os.path.abspath(caminho_json))
    arquivos_resolvidos = []
    for arq in dados.get("arquivos", []):
        caminho_orig = arq.get("caminho", "")
        nome_arq = os.path.basename(caminho_orig)
        candidato_local = os.path.join(pasta_json, nome_arq)
        if os.path.exists(candidato_local):
            arq_resolvido = dict(arq)
            arq_resolvido["caminho"] = candidato_local
        else:
            arq_resolvido = arq  # mantém original — erro será tratado normalmente
        arquivos_resolvidos.append(arq_resolvido)

    return {
        "versao":               versao,
        "nome":                 dados.get("nome", ""),
        "caminho_excel":        dados.get("caminho_excel", ""),
        "arquivos":             arquivos_resolvidos,
        "config_leitura":       config_leitura,
        "mapeamento":           mapeamento,
        "params":               params,
        "config_dist":          config_dist,
        "resultados_deteccao":  resultados_deteccao,
        "resultado_dist":       resultado_dist,
        "data_criacao":         dados.get("data_criacao", ""),
        "data_atualizacao":     dados.get("data_atualizacao", ""),
        "config_restricoes":    _carregar_restricoes(dados.get("restricoes")),
    }