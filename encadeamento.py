"""
encadeamento.py (v2)
--------------------
Calcula DMT entre segmentos não conectados diretamente,
usando as relações cadastradas como grafo e encontrando
o caminho de menor DMT via Dijkstra.

PRINCÍPIO FUNDAMENTAL v2:
Cada salto do encadeamento propaga a POSIÇÃO FÍSICA REAL, não o CMv absoluto.
pos_fisica = cmv - estaca_ini + deslocamento

Isso garante que dois eixos com sistemas de estacagem diferentes mas mesma
posição física tenham DMT = só o afastamento lateral entre eles.

Só chamado quando usar_encadeamento=True na ConfigDistribuicao.
"""

import heapq
from typing import Dict, List, Optional, Tuple
from distribuidor2 import (
    RelacaoSegmentos, ConfigDistribuicao,
    calcular_dmt_relacao, _pos_fisica_a, _pos_fisica_b,
    DMT_MINIMA, INFINITO
)


def calcular_dmt_encadeada(
        cmv_orig: float,
        cmv_dest: float,
        ramo_orig: str,
        ramo_dest: str,
        config: ConfigDistribuicao) -> float:
    """
    Calcula DMT entre ramo_orig e ramo_dest usando encadeamento de relações.
    Propaga posição física real em cada salto.
    Retorna INFINITO se não encontrar caminho.
    """
    if ramo_orig == ramo_dest:
        dist = abs(cmv_dest - cmv_orig) / 1000.0
        return max(round(dist, 6), DMT_MINIMA)

    # Estado: (dmt_acumulada, ramo_atual, cmv_atual)
    # cmv_atual = CMv ABSOLUTO no ramo atual (para cálculo de DMT)
    fila: List[Tuple[float, str, float]] = [(0.0, ramo_orig, cmv_orig)]
    visitados: Dict[str, float] = {}

    while fila:
        dmt_acum, ramo_atual, cmv_atual = heapq.heappop(fila)

        if ramo_atual == ramo_dest:
            return max(round(dmt_acum, 6), DMT_MINIMA)

        if ramo_atual in visitados and visitados[ramo_atual] <= dmt_acum:
            continue
        visitados[ramo_atual] = dmt_acum

        for rel in config.relacoes:
            # Relações com todos=True e ramos_todos preenchida
            if rel.todos and rel.ramos_todos:
                if rel.ramo_a == ramo_atual:
                    for ramo_int in rel.ramos_todos:
                        if ramo_int in visitados:
                            continue
                        cmv_viz = _estimar_cmv_entrada(cmv_atual, cmv_dest,
                                                        rel, 'a', ramo_dest, ramo_int)
                        dmt_tr = calcular_dmt_relacao(cmv_atual, cmv_viz, rel)
                        if dmt_tr < INFINITO:
                            heapq.heappush(fila, (dmt_acum + dmt_tr, ramo_int, cmv_viz))

                elif ramo_atual in rel.ramos_todos:
                    # Saindo de ramo da lista → eixo
                    if rel.ramo_a not in visitados:
                        rel_inv = _inverter_relacao(rel)
                        cmv_viz = _estimar_cmv_entrada(cmv_atual, cmv_dest,
                                                        rel_inv, 'a', ramo_dest, rel.ramo_a)
                        dmt_tr = calcular_dmt_relacao(cmv_atual, cmv_viz, rel_inv)
                        if dmt_tr < INFINITO:
                            heapq.heappush(fila, (dmt_acum + dmt_tr, rel.ramo_a, cmv_viz))
                    # Entre ramos da mesma lista: dmt_fixa
                    for ramo_int in rel.ramos_todos:
                        if ramo_int == ramo_atual or ramo_int in visitados:
                            continue
                        dmt_tr = max(rel.dmt_fixa_km, DMT_MINIMA)
                        heapq.heappush(fila, (dmt_acum + dmt_tr, ramo_int, cmv_dest))
                continue

            # Relações simples
            vizinho = None
            cmv_vizinho = None
            dmt_trecho = None

            if rel.ramo_a == ramo_atual:
                vizinho = rel.ramo_b
                cmv_vizinho = _estimar_cmv_entrada(cmv_atual, cmv_dest,
                                                    rel, 'a', ramo_dest, vizinho)
                dmt_trecho = calcular_dmt_relacao(cmv_atual, cmv_vizinho, rel)

            elif rel.ramo_b == ramo_atual:
                vizinho = rel.ramo_a
                rel_inv = _inverter_relacao(rel)
                cmv_vizinho = _estimar_cmv_entrada(cmv_atual, cmv_dest,
                                                    rel_inv, 'a', ramo_dest, vizinho)
                dmt_trecho = calcular_dmt_relacao(cmv_atual, cmv_vizinho, rel_inv)

            if vizinho is None or dmt_trecho is None or dmt_trecho >= INFINITO:
                continue

            nova_dmt = dmt_acum + dmt_trecho
            if vizinho in visitados and visitados[vizinho] <= nova_dmt:
                continue
            heapq.heappush(fila, (nova_dmt, vizinho, cmv_vizinho))

    return INFINITO


def _estimar_cmv_entrada(cmv_orig: float, cmv_dest_final: float,
                          rel: RelacaoSegmentos, lado: str,
                          ramo_dest_final: str, ramo_vizinho: str) -> float:
    """
    Estima o CMv de entrada no ramo vizinho preservando a posição física.

    PRINCÍPIO: converter posição física do ramo atual para CMv absoluto
    equivalente no ramo vizinho.

    pos_fisica = cmv - estaca_ini + deslocamento  (invariante entre eixos)
    cmv_vizinho = pos_fisica + estaca_ini_vizinho - deslocamento_vizinho
    """
    if ramo_vizinho == ramo_dest_final:
        return cmv_dest_final

    if rel.tipo == 'pistas_paralelas':
        if lado == 'a':
            # Saindo do eixo A → entrar no eixo B na mesma posição física
            pos_fisica = _pos_fisica_a(cmv_orig, rel)
            # CMv no eixo B = pos_fisica - deslocamento_b + estaca_ini_b
            cmv_b = pos_fisica - rel.deslocamento_b_m + rel.estaca_ini_b_m
            return max(cmv_b, rel.estaca_ini_b_m)
        else:
            # Saindo do eixo B → entrar no eixo A na mesma posição física
            pos_fisica = _pos_fisica_b(cmv_orig, rel)
            cmv_a = pos_fisica - rel.deslocamento_a_m + rel.estaca_ini_a_m
            return max(cmv_a, rel.estaca_ini_a_m)

    elif rel.tipo == 'intersecao_marginal':
        if lado == 'a':
            # Saindo do eixo (ramo_a) → entrar na interseção
            # A interseção não tem CMv linear — usar pos_relativa como referência
            return rel.pos_relativa_m + rel.estaca_ini_a_m
        else:
            # Saindo da interseção → entrar no eixo
            # CMv no eixo = estaca_ini_a + pos_relativa
            return rel.estaca_ini_a_m + rel.pos_relativa_m

    elif rel.tipo == 'intersecao_marginal_inv':
        # Saindo da interseção (ramo_a) → entrando no eixo (ramo_b)
        # CMv de entrada no eixo = estaca_ini_b + pos_relativa (ponto de conexão)
        return rel.estaca_ini_b_m + rel.pos_relativa_m

    # --- compatibilidade v1.0 ---
    elif rel.tipo == 'estaca':
        if lado == 'a':
            pos_a = cmv_orig - rel.estaca_ini_a_m
            if rel.pista_antes == 'a':
                pos_b = pos_a - rel.dist_inicio_m
            else:
                pos_b = pos_a + rel.dist_inicio_m
            return rel.estaca_ini_b_m + max(pos_b, 0)
        else:
            pos_b = cmv_orig - rel.estaca_ini_b_m
            if rel.pista_antes == 'a':
                pos_a = pos_b + rel.dist_inicio_m
            else:
                pos_a = pos_b - rel.dist_inicio_m
            return rel.estaca_ini_a_m + max(pos_a, 0)

    elif rel.tipo == 'distancia':
        if lado == 'a':
            return cmv_orig + rel.dist_fixa_m
        else:
            return cmv_orig - rel.dist_fixa_m

    elif rel.tipo == 'fixa':
        return cmv_orig

    elif rel.tipo == 'intersecao_interna':
        # Ponto de passagem = estaca central (ref_a_m) no eixo
        # Na inversão: manter ref_a_m original (não trocar com ref_b_m=0)
        return rel.ref_a_m

    elif rel.tipo == 'intersecao_externa':
        if lado == 'a':
            return rel.ref_b_m if rel.ref_b_m > 0 else rel.ref_a_m
        else:
            return rel.ref_a_m

    return cmv_orig


def _inverter_relacao(rel: RelacaoSegmentos) -> RelacaoSegmentos:
    """
    Inverte a direção de uma RelacaoSegmentos para cálculo B→A.

    REGRA CRÍTICA:
    - pistas_paralelas: troca A↔B (estaca_ini, deslocamento)
    - intersecao_marginal: troca A↔B mas mantém pos_relativa_m e dmt_fixa
    - intersecao_interna: MANTÉM ref_a_m (não troca com ref_b_m=0)
    - intersecao_externa: troca ref_a_m ↔ ref_b_m normalmente
    """
    if rel.tipo == 'pistas_paralelas':
        return RelacaoSegmentos(
            ramo_a=rel.ramo_b,
            ramo_b=rel.ramo_a,
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
        # Na inversao interseção→eixo, usar tipo especial 'intersecao_marginal_inv'
        # que trata o CMv do ramo_a como local (interseção) e ramo_b como eixo
        return RelacaoSegmentos(
            ramo_a=rel.ramo_b,
            ramo_b=rel.ramo_a,
            tipo='intersecao_marginal_inv',
            estaca_ini_a_m=rel.estaca_ini_b_m,   # estaca_ini da intersecao (geralmente 0)
            estaca_ini_b_m=rel.estaca_ini_a_m,   # estaca_ini do eixo original
            pos_relativa_m=rel.pos_relativa_m,
            dmt_fixa_km=rel.dmt_fixa_km,
            todos=rel.todos,
            ramos_todos=rel.ramos_todos,
        )

    # --- compatibilidade v1.0 ---
    elif rel.tipo == 'intersecao_interna':
        # CRÍTICO: manter ref_a_m original — não trocar com ref_b_m=0
        return RelacaoSegmentos(
            ramo_a=rel.ramo_b,
            ramo_b=rel.ramo_a,
            tipo=rel.tipo,
            dmt_fixa_km=rel.dmt_fixa_km,
            ref_a_m=rel.ref_a_m,   # MANTÉM o original
            ref_b_m=rel.ref_b_m,
            dist_refs_m=rel.dist_refs_m,
        )

    elif rel.tipo == 'intersecao_externa':
        return RelacaoSegmentos(
            ramo_a=rel.ramo_b,
            ramo_b=rel.ramo_a,
            tipo=rel.tipo,
            dmt_fixa_km=rel.dmt_fixa_km,
            ref_a_m=rel.ref_b_m,   # troca normalmente
            ref_b_m=rel.ref_a_m,
            dist_refs_m=rel.dist_refs_m,
        )

    # Outros tipos (fixa, estaca, distancia)
    return RelacaoSegmentos(
        ramo_a=rel.ramo_b,
        ramo_b=rel.ramo_a,
        tipo=rel.tipo,
        dmt_fixa_km=rel.dmt_fixa_km,
        estaca_ini_a_m=rel.estaca_ini_b_m,
        estaca_ini_b_m=rel.estaca_ini_a_m,
        dist_inicio_m=rel.dist_inicio_m,
        pista_antes='b' if rel.pista_antes == 'a' else 'a',
        afastamento_m=rel.afastamento_m,
        dist_estaca_m=rel.dist_estaca_m,
        dist_fixa_m=rel.dist_fixa_m,
        pistas_paralelas=rel.pistas_paralelas,
        ref_a_m=rel.ref_b_m,
        ref_b_m=rel.ref_a_m,
        dist_refs_m=rel.dist_refs_m,
    )
