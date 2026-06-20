import uvicorn
from fastapi import FastAPI, Request
import os
import base64
import json

from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
from detector_trechos import detectar_trechos, ParametrosDistribuicao
from distribuidor2 import distribuir, ConfigDistribuicao
from gerador_excel import gerar_excel
from projeto_json import salvar_projeto

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "online"}

@app.post("/processar-projeto")
async def processar_projeto_nuvem(request: Request):
    try:
        # Recebe o pacote como texto JSON simples e limpo da internet
        dados_recebidos = await request.json()
        dados = dados_recebidos["config"]
        
        caminho_excel = "resultado_temporario.xlsx"
        caminho_json = "resultado_temporario.json"
        nome_projeto = dados.get("nome", "Distribuicao")

        # Reconstrói os arquivos Excel originais a partir do texto criptografado enviado pelo .exe
        caminhos_locais_servidor = []
        for i, arquivo_txt in enumerate(dados_recebidos.get("arquivos_base64", [])):
            caminho_salvar = f"entrada_{i}.xlsx"
            conteudo_binario = base64.b64decode(arquivo_txt)
            with open(caminho_salvar, "wb") as f:
                f.write(conteudo_binario)
            caminhos_locais_servidor.append(caminho_salvar)

        config_leitura = ConfigLeitura(
            unidade=dados.get("unidade", "estaca"),
            em_distancia=dados.get("em_distancia", False),
            dist_estaca=dados.get("dist_estaca", 20.0),
            fatores_hom=dados.get("fatores_hom", {})
        )
        
        projeto = ler_multiplos_arquivos(caminhos_locais_servidor, config_leitura)
        
        # [SUA LÓGICA DE CÁLCULO REAIS DE ENGENHARIA]
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
        
        gerar_excel(resultado_final, resultados, caminho_excel, nome_projeto, fatores_hom=dados.get("fatores_hom", {}))
        salvar_projeto(caminho_json, nome_projeto, caminhos_locais_servidor, config_leitura, dados.get("mapeamento"), _params, config_dist, resultados, resultado_final)

        with open(caminho_excel, "rb") as f_excel:
            excel_base64 = base64.b64encode(f_excel.read()).decode('utf-8')
        with open(caminho_json, "r", encoding="utf-8") as f_json:
            json_dados_puros = json.load(f_json)

        # Limpa o lixo
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
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
