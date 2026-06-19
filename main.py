import uvicorn
from fastapi import FastAPI, Request
import os
import base64
import json

# Importações dos seus 13 arquivos originais de engenharia
from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
from detector_trechos import detectar_trechos, ParametrosDistribuicao
from distribuidor2 import distribuir, ConfigDistribuicao
from gerador_excel import gerar_excel
from projeto_json import salvar_projeto

app = FastAPI()

@app.post("/processar-projeto")
async def processar_projeto_nuvem(request: Request):
    try:
        # Recebe qualquer JSON bruto enviado pelo seu .exe sem travar na validação
        dados = await request.json()
        
        # Definição dos caminhos temporários dentro do servidor nuvem
        caminho_excel = "resultado_temporario.xlsx"
        caminho_json = "resultado_temporario.json"
        nome_projeto = dados.get("nome", "Distribuicao")

        # 1. RECONSTRÓI AS CONFIGURAÇÕES DE LEITURA REPASSADAS PELO .EXE
        config_leitura = ConfigLeitura(
            unidade=dados.get("unidade", "estaca"),
            em_distancia=dados.get("em_distancia", False),
            dist_estaca=dados.get("dist_estaca", 20.0),
            fatores_hom=dados.get("fatores_hom", {})
        )
        
        # 2. SEUS ALGORITMOS REAIS EXECUTAM EM SIGILO NA NUVEM RENDER
        projeto = ler_multiplos_arquivos(dados.get("arquivos", []), config_leitura)
        
        resultados = []
        _params = dados.get("params", {})
        
        # Executa a detecção de trechos por ramo em ambiente web seguro
        for ramo in projeto.ramos:
            p_obj = ParametrosDistribuicao(
                usar_corte3_interno=_params.get("usar_corte3_interno", False),
                aceita_corte3_externo=_params.get("aceita_corte3_externo", False),
                usar_corte2_interno=_params.get("usar_corte2_interno", False),
                aceita_corte2_externo=_params.get("aceita_corte2_externo", False),
                vol_min_aterro_c3=float(_params.get("vol_min_aterro_c3", 500)),
                pct_max_c3=float(_params.get("pct_max_c3", 50))
            )
            res = detectar_trechos(ramo, dados.get("mapeamento"), p_obj, unidade=dados.get("unidade", "estaca"))
            resultados.append(res)
            
        # Executa a distribuição matemática do Stepping-Stone na nuvem
        config_dist_enviada = dados.get("config_dist", {})
        config_dist = ConfigDistribuicao(
            tipo_projeto=dados.get("tipo_projeto", "segmento"),
            usar_dmt_maxima=config_dist_enviada.get("usar_dmt_maxima", False),
            dmt_maxima_km=config_dist_enviada.get("dmt_maxima_km", 999.0),
            dmt_cl=config_dist_enviada.get("dmt_cl", 0.05),
            estrategia=config_dist_enviada.get("estrategia", "usar_tudo"),
            relacoes=[], 
            bota_foras=dados.get("bota_foras", []),
            emprestimos=dados.get("emprestimos", [])
        )
        
        resultado_final = distribuir(resultados, dados.get("mapeamento"), _params, config_dist)
        
        # 3. GERA OS ARQUIVOS DE SAÍDA DENTRO DO SERVIDOR
        gerar_excel(resultado_final, resultados, caminho_excel, nome_projeto, fatores_hom=dados.get("fatores_hom", {}))
        salvar_projeto(caminho_json, nome_projeto, dados.get("arquivos", []), config_leitura, dados.get("mapeamento"), _params, config_dist, resultados, resultado_final)

        # 4. TRANSFORMA OS ARQUIVOS GERADOS EM TEXTO COMPATÍVEL COM A INTERNET
        with open(caminho_excel, "rb") as f_excel:
            excel_base64 = base64.b64encode(f_excel.read()).decode('utf-8')
            
        with open(caminho_json, "r", encoding="utf-8") as f_json:
            json_dados_puros = json.load(f_json)

        # Apaga os arquivos temporários criados no servidor
        if os.path.exists(caminho_excel): os.remove(caminho_excel)
        if os.path.exists(caminho_json): os.remove(caminho_json)

        # 5. RETORNA OS DOIS ARQUIVOS PRONTOS VIA REQUISIÇÃO
        return {
            "status": "sucesso",
            "json_final": json_dados_puros,
            "excel_base64": excel_base64
        }
        
    except Exception as e:
        return {"status": "erro", "detalhes": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
