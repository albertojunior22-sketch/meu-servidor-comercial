import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import os

app = FastAPI()

class DadosDoCliente(BaseModel):
    valores_originais: list

@app.post("/processar")
def minha_logica_secreta(dados: DadosDoCliente):
    resultado = [x * 1.5 for x in dados.valores_originais]
    return {"status": "sucesso", "resultado_calculado": resultado}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
