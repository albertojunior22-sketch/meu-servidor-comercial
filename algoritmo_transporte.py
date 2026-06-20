"""
algoritmo_transporte.py
-----------------------
Implementa o problema de transporte para otimização da distribuição
de terraplenagem.

Método:
1. Solução inicial pelo Método do Custo Mínimo
2. Otimização pelo método Stepping-Stone (MODI)

Aplicação:
- Linhas (oferta) = trechos de corte + empréstimos fictícios
- Colunas (demanda) = trechos de aterro + bota foros fictícios
- Custo = DMT entre origem e destino
- Custo infinito = célula proibida pelas regras de categoria
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

INFINITO = 1e9   # custo para células proibidas
EPSILON  = 1e-6  # tolerância numérica


# ---------------------------------------------------------------------------
# Estrutura da matriz de transporte
# ---------------------------------------------------------------------------

@dataclass
class Celula:
    """Representa uma célula da matriz de transporte."""
    i:       int
    j:       int
    custo:   float
    qtd:     float = 0.0
    basica:  bool  = False


@dataclass
class ResultadoTransporte:
    """Resultado da otimização."""
    alocacoes:   List[Tuple[int, int, float]]
    custo_total: float
    iteracoes:   int


# ---------------------------------------------------------------------------
# Método do Custo Mínimo (solução inicial)
# ---------------------------------------------------------------------------

def solucao_custo_minimo(custos: List[List[float]],
                          ofertas: List[float],
                          demandas: List[float]) -> List[List[float]]:
    """
    Gera solução inicial pelo Método do Custo Mínimo.
    Aloca na célula de menor custo disponível primeiro.
    """
    m = len(ofertas)
    n = len(demandas)

    of  = ofertas[:]
    dem = demandas[:]
    aloc = [[0.0] * n for _ in range(m)]

    celulas = [
        (custos[i][j], i, j)
        for i in range(m)
        for j in range(n)
        if custos[i][j] < INFINITO
    ]
    celulas.sort()

    linhas_esgotadas  = set()
    colunas_esgotadas = set()

    for _, i, j in celulas:
        if i in linhas_esgotadas or j in colunas_esgotadas:
            continue
        if of[i] <= EPSILON or dem[j] <= EPSILON:
            continue

        qtd = min(of[i], dem[j])
        aloc[i][j] = qtd
        of[i]  = round(of[i]  - qtd, 6)
        dem[j] = round(dem[j] - qtd, 6)

        if of[i] <= EPSILON:
            linhas_esgotadas.add(i)
        if dem[j] <= EPSILON:
            colunas_esgotadas.add(j)

        if len(linhas_esgotadas) == m or len(colunas_esgotadas) == n:
            break

    return aloc


# ---------------------------------------------------------------------------
# Método MODI / Stepping-Stone
# ---------------------------------------------------------------------------

def encontrar_ciclo(aloc: List[List[float]],
                    i_entrada: int,
                    j_entrada: int) -> Optional[List[Tuple[int, int]]]:
    """
    Encontra o ciclo fechado para a variável não básica (i_entrada, j_entrada).

    Usa pilha explícita (iterativo) — sem recursão profunda.
    Pré-computa índices de básicas por linha e por coluna para busca O(1).
    Movimentos alternam horizontal → vertical → horizontal → ...

    REGRA DE FECHAMENTO:
    O ciclo fecha no movimento VERTICAL quando chegamos à linha i_entrada
    na coluna j_entrada — mesmo que (i_entrada, j_entrada) não seja básica
    (ela é justamente a variável não básica que está entrando na base).
    """
    # Pré-computar básicas por linha e por coluna
    basicas_por_linha: Dict[int, List[int]] = {}
    basicas_por_col:   Dict[int, List[int]] = {}
    for i, row in enumerate(aloc):
        for j, v in enumerate(row):
            if v > EPSILON:
                basicas_por_linha.setdefault(i, []).append(j)
                basicas_por_col.setdefault(j,  []).append(i)

    # Pilha: (caminho como tupla, próximo_movimento_é_horizontal)
    # Primeiro movimento a partir da célula de entrada: HORIZONTAL
    pilha: List[Tuple[tuple, bool]] = [(((i_entrada, j_entrada),), True)]

    while pilha:
        caminho, horizontal = pilha.pop()
        i_cur, j_cur = caminho[-1]
        visitados = set(caminho)

        if horizontal:
            # Mover na mesma linha i_cur para uma coluna de célula básica
            for j_viz in basicas_por_linha.get(i_cur, []):
                if j_viz == j_cur:
                    continue
                nova = (i_cur, j_viz)
                if nova in visitados:
                    continue
                pilha.append((caminho + (nova,), False))

        else:
            # Fechar ciclo: movimento vertical na coluna j_entrada
            # chega em i_entrada — a célula de entrada não é básica,
            # mas é o ponto de fechamento do ciclo
            if j_cur == j_entrada and len(caminho) >= 3:
                return list(caminho)

            # Mover na mesma coluna j_cur para uma linha de célula básica
            for i_viz in basicas_por_col.get(j_cur, []):
                if i_viz == i_cur:
                    continue
                nova = (i_viz, j_cur)
                if nova in visitados:
                    continue
                pilha.append((caminho + (nova,), True))

    return None


def calcular_ui_vj(custos: List[List[float]],
                    aloc: List[List[float]]) -> Tuple[List[float], List[float]]:
    """Calcula multiplicadores u_i e v_j pelo método MODI."""
    m = len(aloc)
    n = len(aloc[0])

    u: List[Optional[float]] = [None] * m
    v: List[Optional[float]] = [None] * n
    u[0] = 0.0

    changed = True
    while changed:
        changed = False
        for i in range(m):
            for j in range(n):
                if aloc[i][j] > EPSILON and custos[i][j] < INFINITO:
                    if u[i] is not None and v[j] is None:
                        v[j] = custos[i][j] - u[i]
                        changed = True
                    elif v[j] is not None and u[i] is None:
                        u[i] = custos[i][j] - v[j]
                        changed = True

    u = [x if x is not None else 0.0 for x in u]
    v = [x if x is not None else 0.0 for x in v]
    return u, v


def stepping_stone(custos: List[List[float]],
                   aloc: List[List[float]],
                   max_iter: int = 1000) -> Tuple[List[List[float]], int]:
    """
    Otimiza a solução pelo método Stepping-Stone (MODI).

    CORREÇÃO DE PERFORMANCE:
    - Calcula todos os deltas PRIMEIRO e identifica a célula de menor delta.
    - Chama encontrar_ciclo UMA ÚNICA VEZ por iteração (para a melhor célula).
    - encontrar_ciclo usa pilha iterativa com índices pré-computados.

    Antes: encontrar_ciclo era chamado para CADA célula com delta negativo
    (recursão profunda × N células = exponencial em matrizes grandes).
    """
    m = len(aloc)
    n = len(aloc[0])
    iteracoes = 0

    for _ in range(max_iter):
        iteracoes += 1
        u, v = calcular_ui_vj(custos, aloc)

        # 1) Varrer todos os deltas — identificar apenas a melhor célula
        melhor_delta = -EPSILON
        melhor_ij    = None

        for i in range(m):
            for j in range(n):
                if aloc[i][j] <= EPSILON and custos[i][j] < INFINITO:
                    delta = custos[i][j] - u[i] - v[j]
                    if delta < melhor_delta:
                        melhor_delta = delta
                        melhor_ij    = (i, j)

        if melhor_ij is None:
            break  # solução ótima

        # 2) Encontrar ciclo UMA VEZ para a melhor célula
        ciclo = encontrar_ciclo(aloc, melhor_ij[0], melhor_ij[1])
        if ciclo is None:
            break  # degenerado — sem ciclo possível

        # 3) Aplicar realocação: pares recebem +, ímpares recebem -
        qtd_min = min(
            aloc[ciclo[k][0]][ciclo[k][1]]
            for k in range(1, len(ciclo), 2)
        )

        for k, (i, j) in enumerate(ciclo):
            if k % 2 == 0:
                aloc[i][j] = round(aloc[i][j] + qtd_min, 6)
            else:
                aloc[i][j] = round(aloc[i][j] - qtd_min, 6)
                if aloc[i][j] < EPSILON:
                    aloc[i][j] = 0.0

    return aloc, iteracoes


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def resolver_transporte(custos: List[List[float]],
                         ofertas: List[float],
                         demandas: List[float],
                         otimizar: bool = True,
                         custo_ficticio: float = 0.0) -> ResultadoTransporte:
    """
    Resolve o problema de transporte.

    custos:        matriz m×n. Use INFINITO para células proibidas.
    ofertas:       volumes disponíveis em cada origem.
    demandas:      volumes necessários em cada destino.
    otimizar:      True = aplica Stepping-Stone; False = só solução inicial.
    custo_ficticio: custo das linhas/colunas fictícias de equilíbrio.
    """
    m = len(ofertas)
    n = len(demandas)

    total_oferta  = sum(ofertas)
    total_demanda = sum(demandas)

    of_eq  = ofertas[:]
    dem_eq = demandas[:]

    if total_oferta > total_demanda + EPSILON:
        # Surplus: coluna fictícia de bota fora
        dem_eq.append(round(total_oferta - total_demanda, 6))
        for i in range(m):
            custos[i].append(custo_ficticio)
        n += 1

    elif total_demanda > total_oferta + EPSILON:
        # Déficit: linha fictícia de empréstimo
        of_eq.append(round(total_demanda - total_oferta, 6))
        custos.append([custo_ficticio] * n)
        m += 1

    aloc = solucao_custo_minimo(custos, of_eq, dem_eq)

    iteracoes = 0
    if otimizar:
        aloc, iteracoes = stepping_stone(custos, aloc)

    custo_total = sum(
        aloc[i][j] * custos[i][j]
        for i in range(len(aloc))
        for j in range(len(aloc[0]))
        if aloc[i][j] > EPSILON and custos[i][j] < INFINITO
    )

    alocacoes = [
        (i, j, aloc[i][j])
        for i in range(len(aloc))
        for j in range(len(aloc[0]))
        if aloc[i][j] > EPSILON
    ]

    return ResultadoTransporte(
        alocacoes=alocacoes,
        custo_total=round(custo_total, 4),
        iteracoes=iteracoes
    )


# ---------------------------------------------------------------------------
# Teste direto
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    custos = [
        [1.0, 3.0, 2.0],
        [2.0, 1.0, 4.0],
        [3.0, 2.0, 1.0],
    ]
    ofertas  = [100.0, 200.0, 150.0]
    demandas = [120.0, 180.0, 150.0]

    resultado = resolver_transporte(custos, ofertas, demandas, otimizar=True)

    print(f"Custo total: {resultado.custo_total:.4f} km·m³")
    print(f"Iterações:   {resultado.iteracoes}")
    print("\nAlocações:")
    for i, j, qtd in resultado.alocacoes:
        if i < 3 and j < 3:
            print(f"  C{i+1} → A{j+1}: {qtd:,.2f} m³  (DMT: {custos[i][j]:.3f} km)")