"""
cliente_api.py
Cliente HTTP para enviar dados da interface local ao servidor FastAPI.
MVP: análise inicial dos Excels e processamento final da distribuição.
"""

import os
import io
import json
import zipfile
import requests

# Troque para a URL da sua API no Render/VPS.
BASE_URL = "https://pensare-api-teste.onrender.com"
URL_ANALISAR = f"{BASE_URL}/analisar-arquivos"
URL_PROCESSAR = f"{BASE_URL}/processar-distribuicao"


def _proximo_json_versionado(pasta: str, nome: str) -> str:
    """Retorna caminho local nome_v1.json, nome_v2.json... sem sobrescrever histórico."""
    base = os.path.splitext(nome)[0]
    i = 1
    while True:
        caminho = os.path.join(pasta, f"{base}_v{i}.json")
        if not os.path.exists(caminho):
            return caminho
        i += 1


def _abrir_arquivos_multipart(arquivos):
    """
    Monta lista multipart e mantém os handles abertos.
    Retorna (files, handles). Quem chamou deve fechar handles.
    """
    files = []
    handles = []
    for idx, arq in enumerate(arquivos):
        caminho = arq["caminho"]
        h = open(caminho, "rb")
        handles.append(h)
        files.append(("files", (os.path.basename(caminho), h, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")))
    return files, handles


def analisar_arquivos(arquivos, config_leitura: dict, timeout=180):
    """
    Envia os Excel ao servidor para leitura inicial.
    Retorna dict com materiais e ramos.
    """
    payload = {
        "arquivos": [{"nome": os.path.basename(a["caminho"]), "tipo": a["tipo"]} for a in arquivos],
        "config_leitura": config_leitura,
    }
    files, handles = _abrir_arquivos_multipart(arquivos)
    try:
        r = requests.post(URL_ANALISAR, data={"payload": json.dumps(payload, ensure_ascii=False)}, files=files, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"Servidor respondeu {r.status_code}: {r.text}")
        dados = r.json()
        if dados.get("status") != "sucesso":
            raise RuntimeError(dados.get("mensagem") or dados.get("detalhes") or "Erro desconhecido no servidor")
        return dados
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass


def processar_distribuicao(arquivos, config: dict, pasta_saida: str, nome_saida: str, timeout=600):
    """
    Envia Excel + configuração completa ao servidor.
    Recebe ZIP com XLSX e JSON e salva na pasta local do cliente.
    Retorna dict com caminhos salvos.
    """
    payload = dict(config)
    payload["arquivos"] = [{"nome": os.path.basename(a["caminho"]), "tipo": a["tipo"]} for a in arquivos]
    payload["nome_saida"] = nome_saida

    files, handles = _abrir_arquivos_multipart(arquivos)
    try:
        r = requests.post(URL_PROCESSAR, data={"payload": json.dumps(payload, ensure_ascii=False)}, files=files, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"Servidor respondeu {r.status_code}: {r.text}")

        content_type = r.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            dados = r.json()
            raise RuntimeError(dados.get("mensagem") or dados.get("detalhes") or str(dados))

        os.makedirs(pasta_saida, exist_ok=True)
        caminho_excel = os.path.join(pasta_saida, f"{nome_saida}.xlsx")
        caminho_json = _proximo_json_versionado(pasta_saida, nome_saida)

        with zipfile.ZipFile(io.BytesIO(r.content), "r") as z:
            xlsx_name = next((n for n in z.namelist() if n.lower().endswith(".xlsx")), None)
            json_name = next((n for n in z.namelist() if n.lower().endswith(".json")), None)
            if not xlsx_name or not json_name:
                raise RuntimeError("Resposta do servidor não contém XLSX e JSON.")
            with open(caminho_excel, "wb") as f:
                f.write(z.read(xlsx_name))
            with open(caminho_json, "wb") as f:
                f.write(z.read(json_name))

        return {"excel": caminho_excel, "json": caminho_json}
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass
