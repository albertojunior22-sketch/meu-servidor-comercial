"""
teste_relacoes.py
-----------------
Testes automáticos para validar o novo modelo de relações v2.0.

Cenários fictícios com resultados esperados calculados manualmente.
Execute antes de rodar com dados reais para garantir que o motor está correto.
"""

import sys
import math

# Importar os módulos novos
sys.path.insert(0, '.')

def _importar_v5():
    """Importa distribuidor2_v5 como distribuidor2 para os testes."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("distribuidor2", "distribuidor2_v5.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

d2 = _importar_v5()
RelacaoSegmentos   = d2.RelacaoSegmentos
ConfigDistribuicao = d2.ConfigDistribuicao
calcular_dmt_relacao = d2.calcular_dmt_relacao
calcular_dmt       = d2.calcular_dmt
INFINITO           = d2.INFINITO
DMT_MINIMA         = d2.DMT_MINIMA


def assert_aprox(valor, esperado, tolerancia=0.001, descricao=""):
    ok = abs(valor - esperado) <= tolerancia
    status = "✅" if ok else "❌"
    print(f"  {status} {descricao}: calculado={valor:.6f} esperado={esperado:.6f}")
    if not ok:
        print(f"     ERRO: diferença={abs(valor-esperado):.6f} > tolerância={tolerancia}")
    return ok


# ---------------------------------------------------------------------------
# CENÁRIO 1 — Pistas Paralelas simples
# ---------------------------------------------------------------------------

def teste_cenario_1():
    """
    Pista A: estaca_ini=116.000m, deslocamento=0
    Pista B: estaca_ini=56.000m,  deslocamento=0
    Afastamento=22m

    Cálculo manual (demonstração feita anteriormente):
    Estaca A: 5950+15,235 → cmv_a = 5950*20 + 15.235 = 119.015,235m
    Estaca B: 3150+14,020 → cmv_b = 3150*20 + 14.020 = 63.014,020m
    pos_a = 119.015,235 - 116.000 + 0 = 3.015,235m
    pos_b = 63.014,020  -  56.000 + 0 = 7.014,020m
    DMT = |3.015,235 - 7.014,020| / 1000 + 0.022
        = 3.998,785 / 1000 + 0.022
        = 3.999 + 0.022 = 4.021km
    """
    print("\n=== CENÁRIO 1 — Pistas Paralelas simples ===")

    rel = RelacaoSegmentos(
        ramo_a="PISTA_A", ramo_b="PISTA_B",
        tipo="pistas_paralelas",
        estaca_ini_a_m=116000.0,
        estaca_ini_b_m=56000.0,
        deslocamento_a_m=0.0,
        deslocamento_b_m=0.0,
        afastamento_m=22.0,
    )

    cmv_a = 5950 * 20 + 15.235   # = 119015.235m
    cmv_b = 3150 * 20 + 14.020   # = 63014.020m

    dmt = calcular_dmt_relacao(cmv_a, cmv_b, rel)
    ok1 = assert_aprox(dmt, 4.021, descricao="DMT A→B")

    # Simétrico: B→A deve dar mesmo resultado
    rel_inv = RelacaoSegmentos(
        ramo_a="PISTA_B", ramo_b="PISTA_A",
        tipo="pistas_paralelas",
        estaca_ini_a_m=56000.0,
        estaca_ini_b_m=116000.0,
        deslocamento_a_m=0.0,
        deslocamento_b_m=0.0,
        afastamento_m=22.0,
    )
    dmt_inv = calcular_dmt_relacao(cmv_b, cmv_a, rel_inv)
    ok2 = assert_aprox(dmt_inv, 4.021, descricao="DMT B→A (simétrico)")

    # Quando estão lado a lado (mesma posição relativa): DMT = só afastamento
    # pos_a = pos_b → cmv_a_equiv para b: 116000 + 7014 = 123014
    cmv_a_lado = 116000 + 7.014020 * 1000 / 1000   # = pos_fisica_b + estaca_ini_a = 56000 + 7014 + 60000?
    # Melhor: pista A na posição 7014.020m → cmv_a = 116000 + 7014.020 = 123014.020
    cmv_a_lado2 = 116000 + 7014.020
    dmt_lado = calcular_dmt_relacao(cmv_a_lado2, cmv_b, rel)
    ok3 = assert_aprox(dmt_lado, 0.022, tolerancia=0.001,
                        descricao="DMT lado a lado (deve = afastamento)")

    return ok1 and ok2 and ok3


# ---------------------------------------------------------------------------
# CENÁRIO 2 — Pistas Paralelas com deslocamento
# ---------------------------------------------------------------------------

def teste_cenario_2():
    """
    Pista A: estaca_ini=116.000m, deslocamento_a=0
    Pista B: estaca_ini=56.000m,  deslocamento_b=-2000m (B começa 2000m antes)
    Afastamento=22m

    Se A está na posição relativa 1000m:
      pos_a = cmv_a - 116000 + 0 = 1000 → cmv_a = 117000
    Se B está na posição relativa 1000m:
      pos_b = cmv_b - 56000 + (-2000) = 1000 → cmv_b = 59000

    DMT = |1000 - 1000| / 1000 + 0.022 = 0.022km ✅
    """
    print("\n=== CENÁRIO 2 — Pistas Paralelas com deslocamento ===")

    rel = RelacaoSegmentos(
        ramo_a="PISTA_A", ramo_b="PISTA_B",
        tipo="pistas_paralelas",
        estaca_ini_a_m=116000.0,
        estaca_ini_b_m=56000.0,
        deslocamento_a_m=0.0,
        deslocamento_b_m=-2000.0,  # B começa 2000m antes
        afastamento_m=22.0,
    )

    # Mesmo ponto físico: pos_a = pos_b = 1000m
    cmv_a = 117000.0   # 116000 + 1000
    cmv_b = 59000.0    # 56000 - 2000 + 1000 → cmv = 56000 + 3000 → 59000
    # Verificar: pos_b = 59000 - 56000 + (-2000) = 3000 - 2000 = 1000 ✅

    dmt_lado = calcular_dmt_relacao(cmv_a, cmv_b, rel)
    ok1 = assert_aprox(dmt_lado, 0.022, descricao="Mesmo ponto físico (deve = afastamento)")

    # 5km de diferença: pos_a=6000, pos_b=1000
    cmv_a2 = 122000.0   # pos_a = 6000
    dmt_5km = calcular_dmt_relacao(cmv_a2, cmv_b, rel)
    ok2 = assert_aprox(dmt_5km, 5.022, descricao="5km de distância + afastamento")

    return ok1 and ok2


# ---------------------------------------------------------------------------
# CENÁRIO 3 — Interseção/Marginal
# ---------------------------------------------------------------------------

def teste_cenario_3():
    """
    Eixo principal (Pista A): estaca_ini=116.000m, deslocamento=0
    Interseção conectada na posição relativa 1740m do eixo
    DMT fixa = 0.3km

    Quando pista está na estaca central (pos=1740m):
      cmv_pista = 116000 + 1740 = 117740
      DMT = |1740 - 1740| / 1000 + 0.3 = 0 + 0.3 = 0.3km

    Quando pista está 5km antes (pos=-3260m):
      cmv_pista = 116000 - 3260 = 112740
      pos_eixo = 112740 - 116000 = -3260
      DMT = |-3260 - 1740| / 1000 + 0.3 = 5.000 + 0.3 = 5.3km
    """
    print("\n=== CENÁRIO 3 — Interseção/Marginal ===")

    rel = RelacaoSegmentos(
        ramo_a="PISTA_A", ramo_b="INT_04",
        tipo="intersecao_marginal",
        estaca_ini_a_m=116000.0,
        deslocamento_a_m=0.0,
        pos_relativa_m=1740.0,
        dmt_fixa_km=0.3,
    )

    # Pista na estaca central
    cmv_pista_central = 117740.0
    cmv_int = 82000.0   # CMv da interseção (não usado no cálculo — ramo_a é o eixo)
    dmt_central = calcular_dmt_relacao(cmv_pista_central, cmv_int, rel)
    ok1 = assert_aprox(dmt_central, 0.3, descricao="Pista na estaca central (deve = dmt_fixa)")

    # Pista 5km antes da estaca central
    cmv_pista_antes = 112740.0   # pos = 112740 - 116000 = -3260
    dmt_antes = calcular_dmt_relacao(cmv_pista_antes, cmv_int, rel)
    ok2 = assert_aprox(dmt_antes, 5.3, descricao="Pista 5km antes da central")

    # Pista 2km depois da estaca central
    cmv_pista_depois = 119740.0   # pos = 119740 - 116000 = 3740
    # DMT = |3740 - 1740| / 1000 + 0.3 = 2.0 + 0.3 = 2.3km
    dmt_depois = calcular_dmt_relacao(cmv_pista_depois, cmv_int, rel)
    ok3 = assert_aprox(dmt_depois, 2.3, descricao="Pista 2km depois da central")

    return ok1 and ok2 and ok3


# ---------------------------------------------------------------------------
# CENÁRIO 4 — Encadeamento: Interseção → Pista A → Pista B
# ---------------------------------------------------------------------------

def teste_cenario_4():
    """
    Cenário do SEGA:
    Pista A (Dir): estaca_ini=116.000m, deslocamento=0
    Pista B (Esq): estaca_ini=56.000m,  deslocamento=0
    Afastamento Pista A ↔ Pista B = 22m

    Solo Mole: no eixo da Pista B, pos_relativa=5120m (estaca 3056+00 - 2800+00)
    Relação Pista B ↔ Solo Mole: tipo=pistas_paralelas, ini_a=56000, ini_b=56000, af=0

    Acesso (CRZ20): cmv local ≈ 316m
    Relação Pista A ↔ Acesso: intersecao_marginal, pos_relativa=4740m (120740-116000), dmt_fixa=0.5

    Encadeamento: Acesso → Pista A → Pista B → Solo Mole

    Passo 1: Acesso (cmv=316) → Pista A via intersecao_marginal
      pos_eixo = -(pos_relativa) pois o acesso está no "lado B"
      Na inversão: cmv_pista_equiv = 116000 + 4740 = 120740 (estaca central)
      dist_acesso = |316 - ... | hmm, nesse caso a inversão precisa do encadeamento

    Para o acesso, o cálculo correto é:
    - O acesso tem cmv local 316m
    - A relação diz que está na pos_relativa=4740m do eixo A
    - DMT = |cmv_eixo_A - (estaca_ini_A + pos_relativa)| / 1000 + dmt_fixa
    - Quando vai do Acesso para o eixo, o encadeamento usa a estaca central como ponto de passagem

    Vamos testar o resultado final esperado:
    Solo Mole CA-1 cmv ≈ 61120m (no sistema da Pista B)
    pos_fisica_solo = 61120 - 56000 = 5120m

    Pista A no ponto equivalente ao Solo Mole: cmv_A = 116000 + 5120 = 121120m
    DMT Pista A → Solo Mole = |5120 - 5120| / 1000 + 0 = 0km (no mesmo ponto)

    DMT Acesso → Pista A (via rel intersecao_marginal invertida):
    = |316 - 0| / 1000 + 0.5 = 0.316 + 0.5 = 0.816km

    Total encadeado: 0.816 + 0 = 0.816km
    """
    print("\n=== CENÁRIO 4 — Encadeamento Acesso → Pista A → Solo Mole ===")

    rel_pista_a_b = RelacaoSegmentos(
        ramo_a="PISTA_A", ramo_b="PISTA_B",
        tipo="pistas_paralelas",
        estaca_ini_a_m=116000.0, estaca_ini_b_m=56000.0,
        deslocamento_a_m=0.0, deslocamento_b_m=0.0,
        afastamento_m=22.0,
    )

    rel_pista_b_solo = RelacaoSegmentos(
        ramo_a="PISTA_B", ramo_b="SOLO_MOLE",
        tipo="pistas_paralelas",
        estaca_ini_a_m=56000.0, estaca_ini_b_m=56000.0,
        deslocamento_a_m=0.0, deslocamento_b_m=0.0,
        afastamento_m=0.0,
    )

    rel_acesso = RelacaoSegmentos(
        ramo_a="PISTA_A", ramo_b="ACESSO",
        tipo="intersecao_marginal",
        estaca_ini_a_m=116000.0, deslocamento_a_m=0.0,
        pos_relativa_m=4740.0,   # 120740 - 116000
        dmt_fixa_km=0.5,
    )

    config = ConfigDistribuicao(
        relacoes=[rel_pista_a_b, rel_pista_b_solo, rel_acesso],
        usar_encadeamento=True,
    )

    # Importar encadeamento
    import encadeamento_v2 as enc

    cmv_acesso = 316.745
    cmv_solo   = 61120.0   # Solo Mole no início, pos_relativa=5120 em relação ao zero

    dmt_enc = enc.calcular_dmt_encadeada(
        cmv_acesso, cmv_solo,
        "ACESSO", "SOLO_MOLE",
        config
    )
    # Esperado: ≈ 0.816km (acesso até pista) + pequena distância na pista até solo mole
    # A posição do acesso (4740m) e do solo mole (5120m) diferem 380m ao longo da pista
    # 380m / 1000 + 0 afastamento pista_b_solo + 22m pista_a_b
    # Total: 0.316 (acesso local) + 0.5 (dmt_fixa) + 0.380 (pista_a para pista_b_equiv) + 0.022
    # = 1.218km
    esperado = (316.745/1000 + 0.5) + (abs(4740 - 5120)/1000) + 0.022
    ok1 = assert_aprox(dmt_enc, esperado, tolerancia=0.01,
                        descricao=f"Encadeamento Acesso→SoloMole (esperado≈{esperado:.3f}km)")

    # Relação direta Pista A → Pista B na mesma posição física
    cmv_pista_a = 121120.0   # pos=5120m no eixo A
    cmv_pista_b = 61120.0    # pos=5120m no eixo B
    dmt_ab = calcular_dmt_relacao(cmv_pista_a, cmv_pista_b, rel_pista_a_b)
    ok2 = assert_aprox(dmt_ab, 0.022, descricao="Pista A ↔ Pista B mesma posição (deve = 22m)")

    return ok1 and ok2


# ---------------------------------------------------------------------------
# CENÁRIO 5 — Verificar compatibilidade v1.0 (tipos antigos)
# ---------------------------------------------------------------------------

def teste_cenario_5():
    """
    Verifica que tipos v1.0 (estaca, intersecao_interna) ainda calculam corretamente.
    Usa os valores do SEGB que estavam funcionando.
    """
    print("\n=== CENÁRIO 5 — Compatibilidade v1.0 (tipos antigos) ===")

    # SEGB: Pista Direita ↔ Pista Esquerda, tipo=estaca, ini_a=0, ini_b=0, af=22
    # (como estava nos JSONs antigos — zeros)
    rel_legada = RelacaoSegmentos(
        ramo_a="SEGB_DIR", ramo_b="SEGB_ESQ",
        tipo="estaca",
        estaca_ini_a_m=0.0, estaca_ini_b_m=0.0,
        dist_inicio_m=0.0, pista_antes="a",
        afastamento_m=22.0,
    )
    # Com zeros, DMT = |cmv_a - cmv_b| / 1000 + 0.022
    cmv_a = 5000.0
    cmv_b = 5000.0
    dmt_lado = calcular_dmt_relacao(cmv_a, cmv_b, rel_legada)
    ok1 = assert_aprox(dmt_lado, 0.022, descricao="v1.0 estaca: mesmo CMv (deve = af=22m)")

    cmv_b2 = 8000.0
    dmt_3km = calcular_dmt_relacao(cmv_a, cmv_b2, rel_legada)
    ok2 = assert_aprox(dmt_3km, 3.022, descricao="v1.0 estaca: 3km diferença + af=22m")

    # intersecao_interna v1.0
    rel_int = RelacaoSegmentos(
        ramo_a="PISTA_DIR", ramo_b="MARGINAL",
        tipo="intersecao_interna",
        ref_a_m=10000.0, dmt_fixa_km=0.3,
    )
    # Pista na estaca central, marginal no CMv 5000:
    # dist_a = |10000 - 10000| = 0, dist_b = |5000 - 10000| = 5km → total = 5.3km
    dmt_central = calcular_dmt_relacao(10000.0, 5000.0, rel_int)
    ok3 = assert_aprox(dmt_central, 5.3, descricao="v1.0 intersecao_interna: eixo na central + 5km dist marginal")

    # Pista 5km antes: dist_a=5, dist_b=5, total=10.3km
    dmt_5km = calcular_dmt_relacao(5000.0, 5000.0, rel_int)
    esperado = abs(5000 - 10000)/1000 + abs(5000 - 10000)/1000 + 0.3
    ok4 = assert_aprox(dmt_5km, esperado, descricao="v1.0 intersecao_interna: 5km da central em cada lado")

    return ok1 and ok2 and ok3 and ok4


# ---------------------------------------------------------------------------
# EXECUÇÃO DOS TESTES
# ---------------------------------------------------------------------------

def executar_todos():
    print("="*60)
    print("TESTES DO NOVO MODELO DE RELAÇÕES v2.0")
    print("="*60)

    resultados = {
        "Cenário 1 - Pistas Paralelas simples":           teste_cenario_1(),
        "Cenário 2 - Pistas Paralelas com deslocamento":  teste_cenario_2(),
        "Cenário 3 - Interseção/Marginal":                teste_cenario_3(),
        "Cenário 4 - Encadeamento completo":              teste_cenario_4(),
        "Cenário 5 - Compatibilidade v1.0":               teste_cenario_5(),
    }

    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    todos_ok = True
    for nome, ok in resultados.items():
        status = "✅ PASSOU" if ok else "❌ FALHOU"
        print(f"  {status} — {nome}")
        if not ok:
            todos_ok = False

    print()
    if todos_ok:
        print("✅ TODOS OS TESTES PASSARAM — pode usar com dados reais!")
    else:
        print("❌ ALGUNS TESTES FALHARAM — revisar antes de usar!")
    return todos_ok


if __name__ == "__main__":
    executar_todos()
