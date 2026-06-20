import uvicorn
from fastapi import FastAPI, Form, File, UploadFile
from typing import List
import os
import base64
import json

from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
from detector_trechos import detectar_trechos, ParametrosDistribuicao
from distribuidor2 import distribuir, ConfigDistribuicao
from gerador_excel import gerar_excel
from projeto_json import salvar_projeto

app = FastAPI()

@app.post("/processar-projeto")
async def processar_projeto_nuvem(config: str = Form(...), files: List[UploadFile] = File(...)):
    try:
        # Converte o texto das configurações de volta para dicionário
        dados = json.loads(config)
        
        caminho_excel = "resultado_temporario.xlsx"
        caminho_json = "resultado_temporario.json"
        nome_projeto = dados.get("nome", "Distribuicao")

        # Salva temporariamente os arquivos enviados pelo cliente no disco do servidor
        caminhos_locais_servidor = []
        for file in files:
            caminho_salvar = file.filename
            conteudo = await file.read()
            with open(caminho_salvar, "wb") as f:
                f.write(conteudo)
            caminhos_locais_servidor.append(caminho_salvar)

        # 1. Configura a leitura usando os arquivos reais que agora estão no servidor
        config_leitura = ConfigLeitura(
            unidade=dados.get("unidade", "estaca"),
            em_distancia=dados.get("em_distancia", False),
            dist_estaca=dados.get("dist_estaca", 20.0),
            fatores_hom=dados.get("fatores_hom", {})
        )
        
        # Passa a lista de arquivos salvos no servidor para o seu script calcular
        projeto = ler_multiplos_arquivos(caminhos_locais_servidor, config_leitura)
        
        # [SUA LÓGICA ORIGINAL DE ENGENHARIA DE DETECÇÃO E STEPPING-STONE]
        resultados = []
        _params = dados.get("params", {})
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
            
        config_dist = ConfigDistribuicao(
            tipo_projeto=dados.get("tipo_projeto", "segmento"),
            usar_dmt_maxima=False, dmt_maxima_km=999.0, dmt_cl=0.05,
            estrategia="usar_tudo", relacoes=[], bota_foras=[], emprestimos=[]
        )
        resultado_final = distribuir(resultados, dados.get("mapeamento"), _params, config_dist)
        
        # Gera os arquivos finais
        gerar_excel(resultado_final, resultados, caminho_excel, nome_projeto, fatores_hom=dados.get("fatores_hom", {}))
        salvar_projeto(caminho_json, nome_projeto, caminhos_locais_servidor, config_leitura, dados.get("mapeamento"), _params, config_dist, resultados, resultado_final)

        # Transforma em texto para a transmissão
        with open(caminho_excel, "rb") as f_excel:
            excel_base64 = base64.b64encode(f_excel.read()).decode('utf-8')
        with open(caminho_json, "r", encoding="utf-8") as f_json:
            json_dados_puros = json.load(f_json)

        # Limpa os arquivos temporários do servidor
        if os.path.exists(caminho_excel): os.remove(caminho_excel)
        if os.path.exists(caminho_json): os.remove(caminho_json)
        for arq in caminhos_locais_servidor:
            if os.path.exists(arq): os.remove(arq)

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
