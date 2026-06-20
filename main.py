import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime

app = FastAPI()

# ---------------------------------------------------------------------------
# SUA LISTA DE CLIENTES COMERCIAIS ESTÁVEL (Modifique aqui para controlar os acessos)
# ---------------------------------------------------------------------------
# Formato: "e-mail": ["senha", "status", "data_expiracao", primeiro_acesso]
# primeiro_acesso: 1 (obriga a mudar a senha) | 0 (já mudou, acesso normal)
BANCO_DE_USUARIOS = {
    "albertojunior22@gmail.com": ["Pensare123", "ativo", "2027-06-20", 1],
    "cliente_teste@gmail.com":   ["Mudar123", "ativo", "2027-12-31", 1],
}

@app.get("/")
def health_check():
    return {"status": "gerenciador_online"}

# 1. ROTA DE LOGIN E VALIDAÇÃO DE ASSINATURA
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
            return {"status": "primeiro_acesso", "mensagem": "Altere sua senha provisoria de primeiro acesso."}

        return {"status": "sucesso", "mensagem": "Acesso liberado!"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

# 2. ROTA PARA ATUALIZAR A SENHA PROVISÓRIA DO CLIENTE
@app.post("/alterar-senha/")
async def alterar_senha(request: Request):
    try:
        dados = await request.json()
        email = dados.get("email", "").lower().strip()
        senha_antiga = dados.get("senha_antiga", "")
        senha_nova = dados.get("senha_nova", "")
        
        if email not in BANCO_DE_USUARIOS or BANCO_DE_USUARIOS[email][0] != senha_antiga:
            return {"status": "erro", "mensagem": "Senha antiga incorreta."}

        # Atualiza a senha na memória do servidor
        BANCO_DE_USUARIOS[email][0] = senha_nova
        BANCO_DE_USUARIOS[email][3] = 0 # Define primeiro_acesso como 0
        
        return {"status": "sucesso", "mensagem": "Senha atualizada com sucesso!"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    # Força o servidor a rodar direto como texto do módulo principal
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
