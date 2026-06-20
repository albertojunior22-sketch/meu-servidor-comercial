import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
import os
import sqlite3
from datetime import datetime

app = FastAPI()
DB_FILE = "usuarios.db"

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO AUTOMÁTICA DO BANCO DE DADOS NA NUVEM
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
    # --- CADASTRE SEUS CLIENTES AQUI (Exemplos iniciais) ---
    # Formato: (e-mail, senha_provisoria, status, data_expiracao, primeiro_acesso)
    # primeiro_acesso = 1 significa que ele PRECISA trocar a senha ao logar.
    clientes_iniciais = [
        ("engenheiro1@email.com", "Pensare123", "ativo", "2027-06-20", 1),
        ("cliente2@empresa.com.br", "Mudar123", "ativo", "2027-12-31", 1),
        ("usuario_atrasado@gmail.com", "Senha999", "bloqueado", "2026-05-01", 0)
    ]
    for cliente in clientes_iniciais:
        cursor.execute("INSERT OR IGNORE INTO usuarios VALUES (?, ?, ?, ?, ?)", cliente)
    conn.commit()
    conn.close()

inicializar_banco()

# Modelos de dados para a internet
class LoginData(BaseModel):
    email: str
    senha: str

class NovaSenhaData(BaseModel):
    email: str
    senha_antiga: str
    senha_nova: str

@app.get("/")
def health_check():
    return {"status": "gerenciador_de_usuarios_online"}

# 1. ROTA DE LOGIN E VALIDAÇÃO DE PRAZO
@app.post("/login")
async def login_cliente(dados: LoginData):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT senha, status, expiracao, primeiro_acesso FROM usuarios WHERE email = ?", (dados.email.lower().strip(),))
    usuario = cursor.fetchone()
    conn.close()

    if not usuario:
        return {"status": "erro", "mensagem": "E-mail não cadastrado."}

    senha_salva, status, expiracao, primeiro_acesso = usuario

    # Verifica bloqueio manual do administrador
    if status == "bloqueado":
        return {"status": "erro", "mensagem": "Acesso suspenso pelo administrador."}

    # Verifica data de expiração da assinatura anual
    data_exp = datetime.strptime(expiracao, "%Y-%m-%d")
    if datetime.now() > data_exp:
        return {"status": "erro", "mensagem": f"Sua assinatura anual venceu em {expiracao}."}

    # Verifica se a senha está correta
    if dados.senha != senha_salva:
        return {"status": "erro", "mensagem": "Senha incorreta."}

    # Se for o primeiro acesso, avisa o .exe para abrir a tela de trocar senha
    if primeiro_acesso == 1:
        return {"status": "primeiro_acesso", "mensagem": "Por segurança, altere sua senha provisória."}

    return {"status": "sucesso", "mensagem": "Acesso liberado!"}

# 2. ROTA PARA TROCAR A SENHA PROVISÓRIA
@app.post("/alterar-senha")
async def alterar_senha(dados: NovaSenhaData):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT senha FROM usuarios WHERE email = ?", (dados.email.lower().strip(),))
    usuario = cursor.fetchone()

    if not usuario or usuario[0] != dados.senha_antiga:
        conn.close()
        return {"status": "erro", "mensagem": "Senha antiga incorreta."}

    # Atualiza para a nova senha e desmarca o primeiro acesso
    cursor.execute("UPDATE usuarios SET senha = ?, primeiro_acesso = 0 WHERE email = ?", (dados.senha_nova, dados.email.lower().strip()))
    conn.commit()
    conn.close()
    return {"status": "sucesso", "mensagem": "Senha atualizada com sucesso!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
