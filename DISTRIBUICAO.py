# DISTRIBUICAO.py
# As classes e funções do leitor estão em leitor_civil.py
# Este arquivo serve apenas para execução direta (testes)

from leitor_civil import *  # re-exporta tudo do leitor

if __name__ == "__main__":
    from leitor_civil import ler_multiplos_arquivos, ConfigLeitura, imprimir_resumo
    from detector_trechos import MapeamentoMateriais, ParametrosDistribuicao, detectar_trechos, imprimir_trechos
    from distribuidor2 import ConfigDistribuicao, distribuir, imprimir_distribuicao
    from gerador_excel import gerar_excel
    from projeto_json import salvar_projeto
    from interface import abrir_redistribuicao
    import os

    config = ConfigLeitura(
        unidade='estaca', em_distancia=False, dist_estaca=20.0,
        fatores_hom={"Corte1":1.00,"Corte2":1.15,"Corte3":0.90,"Aterro":1.25,"CF":1.25}
    )
    arquivos = [
        {"caminho": r"E:\Dropbox\VisualStudio\PROGRAMA PARA DISTRIBUIÇÃO\DISTRIBUICAO\DISTRIBUICAO\SEGB_INT 03_Civil.xlsx", "tipo": 1},
        {"caminho": r"E:\Dropbox\VisualStudio\PROGRAMA PARA DISTRIBUIÇÃO\DISTRIBUICAO\DISTRIBUICAO\SEGB_Civil.xlsx", "tipo": 1},
    ]
    mapeamento = MapeamentoMateriais(
        corte1=["Corte1"], corte2=["Corte2"], corte3=["Corte3"],
        aterro_ca=["Aterro"], aterro_cf=["CF"], ignorar=["Limpeza","Solo Mole"]
    )
    params = ParametrosDistribuicao(
        usar_corte3=False, usar_corte2=False,
        vol_min_aterro_c3=500.0, pct_max_c3=50.0
    )
    projeto = ler_multiplos_arquivos(arquivos, config)
    imprimir_resumo(projeto)

    config_dist = ConfigDistribuicao(
        tipo_projeto='intersecao', dmt_cl=0.050,
        usar_dmt_maxima=False, emprestimo_mais_proximo=True,
        dmt_entre_ramos={"INT 03 - RAMO 100": {"INT 03 - RAMO 300": 2.5}},
        bota_foras=[], emprestimos=[]
    )
    resultados = []
    for ramo in projeto.ramos:
        res = detectar_trechos(ramo, mapeamento, params, unidade="estaca")
        imprimir_trechos(res, params)
        resultados.append(res)

    resultado_dist = distribuir(resultados, mapeamento, params, config_dist)
    imprimir_distribuicao(resultado_dist)

    pasta = os.path.dirname(os.path.abspath(__file__))
    nome = input("Nome do arquivo de saída (sem extensão): ").strip()
    if not nome:
        nome = "Distribuicao"
    caminho_saida = os.path.join(pasta, f"{nome}.xlsx")
    gerar_excel(resultado_dist, resultados, caminho_saida, nome)

    json_path = os.path.join(pasta, f"{nome}.json")
    salvar_projeto(json_path, nome, arquivos, config, mapeamento, params,
                   config_dist, resultados, resultado_dist, caminho_excel=caminho_saida)

    abrir_redistribuicao()