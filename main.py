import uvicorn
from fastapi import FastAPI, Request
import os
import sqlite3
from datetime import datetime

app = FastAPI()
DB_FILE = "usuarios.db"

# ---------------------------------------------------------------------------
# CRIAÇÃO AUTOMÁTICA DO BANCO DE DADOS EM ARQUIVO (Não some se o Render reiniciar)
# ---------------------------------------------------------------------------
def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            email TEXT PRIMARY KEY,
            senha TEXT,
            status TEXT,
            expiracao TEXT,
            primeiro_acesso INTEGER
        )
    """)
    # --- CADASTRE OS SEUS CLIENTES AQUI (Use sempre letras minúsculas no e-mail) ---
    # Formato: ("e-mail", "senha_provisoria", "status", "ano-mes-dia", primeiro_acesso)
    # primeiro_acesso = 1 significa que ele SERÁ OBRIGADO a mudar a senha ao logar
    clientes_iniciais = [
        ("alberto@pensare.com.br", "Pensare123", "ativo", "2027-06-20", 1),
        ("cliente_teste@gmail.com", "Mudar123", "ativo", "2027-12-31", 1),
    ]
    for cliente in clientes_iniciais:
        cursor.execute("INSERT OR IGNORE INTO usuarios VALUES (?, ?, ?, ?, ?)", cliente)
    conn.commit()
    conn.close()

inicializar_banco()

@app.get("/")
def health_check():
    return {"status": "gerenciador_online"}

# 1. ROTA DE LOGIN E VALIDAÇÃO DE ASSINATURA
@app.post("/login")
async def login_cliente(request: Request):
    try:
        dados = await request.json()
        email = dados.get("email", "").lower().strip()
        senha = dados.get("senha", "")
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT senha, status, expiracao, primeiro_acesso FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()
        conn.close()

        if not usuario:
            return {"status": "erro", "mensagem": "E-mail nao cadastrado."}

        senha_salva, status, expiracao, primeiro_acesso = usuario

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
@app.post("/alterar-senha")
async def alterar_senha(request: Request):
    try:
        dados = await request.json()
        email = dados.get("email", "").lower().strip()
        senha_antiga = dados.get("senha_antiga", "")
        senha_nova = dados.get("senha_nova", "")
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT senha FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()

        if not usuario or usuario[0] != senha_antiga:
            conn.close()
            return {"status": "erro", "mensagem": "Senha antiga incorreta."}

        cursor.execute("UPDATE usuarios SET senha = ?, primeiro_acesso = 0 WHERE email = ?", (senha_nova, email))
        conn.commit()
        conn.close()
        return {"status": "sucesso", "mensagem": "Senha atualizada com sucesso!"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
