"""
main.py — API FastAPI para teste no Render gratuito.
Inclui:
- autenticação/licença
- análise inicial dos Excel
- processamento principal no servidor
- redistribuição entre segmentos no servidor
"""

import os
import io
import json
import zipfile
import tempfile
import traceback
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse

from leitor_civil import ConfigLeitura, ler_multiplos_arquivos
from detector_trechos import detectar_trechos
from distribuidor2 import distribuir
from gerador_excel import gerar_excel
from projeto_json import (
    salvar_projeto,
    _dict_to_mapeamento,
    _dict_to_params,
    _dict_to_config_dist,
)

try:
    from restricoes_ramo import dict_to_restricoes
except Exception:
    dict_to_restricoes = None


app = FastAPI(title="Pensare Terraplenagem API")


BANCO_DE_USUARIOS = {
    "albertojunior22@gmail.com": ["Pensare123", "ativo", "2027-06-20", 1],
    "cliente_teste@gmail.com": ["Mudar123", "ativo", "2027-12-31", 1],
}


@app.get("/")
def health_check():
    return {"status": "gerenciador_online"}


@app.post("/login")
@app.post("/login/")
async def login_cliente(request: Request):
    try:
        dados = await request.json()
        email = dados.get("email", "").lower().strip()
        senha = dados.get("senha", "")

        if email not in BANCO_DE_USUARIOS:
            return {"status": "erro", "mensagem": "E-mail nao cadastrado."}

        senha_salva, status, expiracao, primeiro_acesso = BANCO_DE_USUARIOS[email]

        if status == "bloqueado":
            return {"status": "erro", "mensagem": "Acesso suspenso pelo administrador."}

        data_exp = datetime.strptime(expiracao, "%Y-%m-%d")
        if datetime.now() > data_exp:
            return {"status": "erro", "mensagem": f"Assinatura vencida em {expiracao}."}

        if senha != senha_salva:
            return {"status": "erro", "mensagem": "Senha incorreta."}

        if primeiro_acesso == 1:
            return {
                "status": "primeiro_acesso",
                "mensagem": "Altere sua senha provisoria de primeiro acesso.",
            }

        return {"status": "sucesso", "mensagem": "Acesso liberado!"}

    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}


@app.post("/alterar-senha")
@app.post("/alterar-senha/")
async def alterar_senha(request: Request):
    try:
        dados = await request.json()
        email = dados.get("email", "").lower().strip()
        senha_antiga = dados.get("senha_antiga", "")
        senha_nova = dados.get("senha_nova", "")

        if email not in BANCO_DE_USUARIOS or BANCO_DE_USUARIOS[email][0] != senha_antiga:
            return {"status": "erro", "mensagem": "Senha antiga incorreta."}

        BANCO_DE_USUARIOS[email][0] = senha_nova
        BANCO_DE_USUARIOS[email][3] = 0

        return {"status": "sucesso", "mensagem": "Senha atualizada com sucesso!"}

    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}


def _config_leitura_from_dict(d: dict) -> ConfigLeitura:
    return ConfigLeitura(
        unidade=d.get("unidade", "estaca"),
        em_distancia=bool(d.get("em_distancia", False)),
        dist_estaca=float(d.get("dist_estaca", 20.0)),
        dist_max_bloco=float(d.get("dist_max_bloco", 20.0)),
        fatores_hom=d.get("fatores_hom", {}) or {},
    )


def _salvar_uploads(tmpdir: str, files, arquivos_meta):
    arquivos = []

    for idx, up in enumerate(files):
        meta = arquivos_meta[idx] if idx < len(arquivos_meta) else {}
        nome = meta.get("nome") or up.filename or f"arquivo_{idx}.xlsx"
        tipo = int(meta.get("tipo", 1))

        caminho = os.path.join(tmpdir, os.path.basename(nome))

        with open(caminho, "wb") as f:
            f.write(up.file.read())

        arquivos.append({
            "caminho": caminho,
            "tipo": tipo,
            "nome_original": nome,
        })

    return arquivos


def _erro_json(status_code: int, e: Exception):
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "erro",
            "mensagem": str(e),
            "traceback": traceback.format_exc(),
        },
    )


@app.post("/analisar-arquivos")
async def analisar_arquivos(
    payload: str = Form(...),
    files: list[UploadFile] = File(...),
):
    try:
        dados = json.loads(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            arquivos = _salvar_uploads(tmpdir, files, dados.get("arquivos", []))
            config = _config_leitura_from_dict(dados.get("config_leitura", {}))
            projeto = ler_multiplos_arquivos(arquivos, config)

            mats = set()
            for ramo in projeto.ramos:
                mats.update(ramo.materiais)

            return {
                "status": "sucesso",
                "materiais": sorted(mats),
                "ramos": list(dict.fromkeys(r.nome for r in projeto.ramos)),
            }

    except Exception as e:
        return _erro_json(500, e)


@app.post("/processar-distribuicao")
async def processar_distribuicao(
    payload: str = Form(...),
    files: list[UploadFile] = File(...),
):
    try:
        dados = json.loads(payload)

        nome_saida = dados.get("nome_saida") or dados.get("nome") or "resultado"
        nome_saida = os.path.splitext(os.path.basename(nome_saida))[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            arquivos = _salvar_uploads(tmpdir, files, dados.get("arquivos", []))

            config_leitura = _config_leitura_from_dict(dados.get("config_leitura", {}))
            mapeamento = _dict_to_mapeamento(dados["mapeamento"])
            params = _dict_to_params(dados["params"])
            config_dist = _dict_to_config_dist(dados["config_dist"])

            config_restricoes = None
            if dados.get("restricoes") and dict_to_restricoes:
                config_restricoes = dict_to_restricoes(dados.get("restricoes"))

            projeto = ler_multiplos_arquivos(arquivos, config_leitura)

            resultados = []
            for ramo in projeto.ramos:
                p = params.get(ramo.nome, list(params.values())[0]) if isinstance(params, dict) else params
                res = detectar_trechos(
                    ramo,
                    mapeamento,
                    p,
                    unidade=config_leitura.unidade,
                    restricoes=config_restricoes,
                )
                resultados.append(res)

            resultado = distribuir(
                resultados,
                mapeamento,
                params,
                config_dist,
                restricoes=config_restricoes,
            )

            caminho_excel = os.path.join(tmpdir, f"{nome_saida}.xlsx")
            caminho_json = os.path.join(tmpdir, f"{nome_saida}.json")

            gerar_excel(
                resultado,
                resultados,
                caminho_excel,
                nome_saida,
                fatores_hom=config_leitura.fatores_hom,
                mapeamento=mapeamento,
                projeto=projeto,
                restricoes=config_restricoes,
            )

            arquivos_json = []
            for meta, arq in zip(dados.get("arquivos", []), arquivos):
                arquivos_json.append({
                    "caminho": meta.get("caminho", meta.get("nome", arq["nome_original"])),
                    "tipo": arq["tipo"],
                })

            salvar_projeto(
                caminho_json,
                nome_saida,
                arquivos_json,
                config_leitura,
                mapeamento,
                params,
                config_dist,
                resultados,
                resultado,
                caminho_excel=f"{nome_saida}.xlsx",
                config_restricoes=config_restricoes,
                criar_versao=False,
            )

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.write(caminho_excel, arcname=f"{nome_saida}.xlsx")
                z.write(caminho_json, arcname=f"{nome_saida}.json")

            zip_buffer.seek(0)

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={nome_saida}.zip"},
            )

    except Exception as e:
        return _erro_json(500, e)


@app.post("/redistribuir-segmentos")
async def redistribuir_segmentos(
    payload: str = Form(...),
    files: list[UploadFile] = File(...),
):
    try:
        from redistribuicao import (
            carregar_segmento,
            RelacaoSegmento,
            redistribuir,
            gerar_excel_redistribuido,
            salvar_json_redistribuido,
            salvar_sessao,
        )

        dados = json.loads(payload)

        nome_saida = dados.get("nome_saida") or "redistribuicao_segmentos"
        nome_saida = os.path.splitext(os.path.basename(nome_saida))[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            pasta_saida = os.path.join(tmpdir, nome_saida)
            os.makedirs(pasta_saida, exist_ok=True)

            caminhos_json = []

            for idx, up in enumerate(files):
                nome = up.filename or f"segmento_{idx + 1}.json"
                caminho = os.path.join(tmpdir, os.path.basename(nome))

                with open(caminho, "wb") as f:
                    f.write(up.file.read())

                caminhos_json.append(caminho)

            segmentos = [carregar_segmento(c) for c in caminhos_json]

            relacoes = []
            for r in dados.get("relacoes", []):
                relacoes.append(RelacaoSegmento(
                    seg_a=r.get("seg_a", ""),
                    seg_b=r.get("seg_b", ""),
                    extensao_a_m=float(r.get("extensao_a_m", 0) or 0),
                    extensao_b_m=float(r.get("extensao_b_m", 0) or 0),
                    deslocamento_m=float(r.get("deslocamento_m", 0) or 0),
                    afastamento_m=float(r.get("afastamento_m", 0) or 0),
                    usar_c1=bool(r.get("usar_c1", True)),
                    usar_c2=bool(r.get("usar_c2", False)),
                    usar_c3=bool(r.get("usar_c3", False)),
                ))

            resultado = redistribuir(segmentos, relacoes)

            arquivos_gerados = []
            bfae_sessao = dados.get("bfae", []) or []

            bfs_ext = []

            for s in segmentos:
                for bf_r in getattr(s, "bota_foras_redist", []):
                    bfs_ext.append({
                        "tipo": "BF",
                        "label_bf": bf_r.nome,
                        "cmv_label": bf_r.cmv_label,
                        "cmv_m": bf_r.pos_relativa_m,
                        "ramo": bf_r.eixo_ref,
                        "segmento": s.nome,
                        "afastamento_m": bf_r.afastamento_m,
                    })

                for ae_r in getattr(s, "emprestimos_redist", []):
                    bfs_ext.append({
                        "tipo": "AE",
                        "label_bf": ae_r.nome,
                        "cmv_label": ae_r.cmv_label,
                        "cmv_m": ae_r.pos_relativa_m,
                        "ramo": ae_r.eixo_ref,
                        "segmento": s.nome,
                        "afastamento_m": ae_r.afastamento_m,
                    })

            for seg in segmentos:
                linhas = resultado.get(seg.nome, [])
                nome_base = seg.nome.replace(" ", "_").replace("/", "_")

                excel_out = os.path.join(pasta_saida, f"{nome_base}_redistribuido.xlsx")
                json_out = os.path.join(pasta_saida, f"{nome_base}_redistribuido.json")

                gerar_excel_redistribuido(
                    seg,
                    linhas,
                    excel_out,
                    bfs_externos=bfs_ext,
                    relacoes=relacoes,
                )

                json_salvo = salvar_json_redistribuido(seg, linhas, json_out)

                if os.path.exists(excel_out):
                    arquivos_gerados.append(excel_out)
                else:
                    print(f"AVISO: Excel redistribuído não encontrado para {seg.nome}: {excel_out}")

                if json_salvo and os.path.exists(json_salvo):
                    arquivos_gerados.append(json_salvo)
                elif os.path.exists(json_out):
                    arquivos_gerados.append(json_out)
                else:
                    print(f"AVISO: JSON redistribuído não encontrado para {seg.nome}: {json_out}")

            sessao_out = os.path.join(pasta_saida, "sessao_redistribuicao.json")

            salvar_sessao(
                segmentos,
                dados.get("relacoes", []),
                pasta_saida,
                sessao_out,
                bfae=bfae_sessao,
            )

            if os.path.exists(sessao_out):
                arquivos_gerados.append(sessao_out)
            else:
                print(f"AVISO: sessão não encontrada: {sessao_out}")

            if not arquivos_gerados:
                raise RuntimeError("Nenhum arquivo foi gerado pela redistribuição.")

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for arq in arquivos_gerados:
                    if os.path.exists(arq):
                        z.write(arq, arcname=os.path.basename(arq))
                    else:
                        print(f"AVISO: arquivo não encontrado no ZIP: {arq}")

            zip_buffer.seek(0)

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={nome_saida}.zip"},
            )

    except Exception as e:
        return _erro_json(500, e)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
