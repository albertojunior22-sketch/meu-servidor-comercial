"""
interface.py — Interface gráfica para distribuição de terraplenagem.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

# ---------------------------------------------------------------------------
# Cores e fontes
# ---------------------------------------------------------------------------
COR_BG       = "#1E2330"
COR_PAINEL   = "#252B3B"
COR_CARD     = "#2D3446"
COR_BORDA    = "#3A4460"
COR_ACCENT   = "#4A9EFF"
COR_ACCENT2  = "#2ECC71"
COR_DANGER   = "#E74C3C"
COR_TEXTO    = "#E8EAF0"
COR_SUBTEXTO = "#8892A4"
COR_INPUT    = "#1A2030"
COR_BTN      = "#3A4460"
COR_BTN_HOV  = "#4A5470"

FONTE_SUB   = ("Segoe UI", 11, "bold")
FONTE_LABEL = ("Segoe UI", 10)
FONTE_SMALL = ("Segoe UI", 9)
FONTE_BTN   = ("Segoe UI", 10, "bold")
FONTE_MONO  = ("Consolas", 9)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

def styled_label(parent, text, fonte=FONTE_LABEL, cor=COR_TEXTO, bg=None, **kw):
    bg_cor = bg if bg else parent.cget("bg")
    return tk.Label(parent, text=text, font=fonte, fg=cor, bg=bg_cor, **kw)

def styled_entry(parent, var=None, width=20, **kw):
    return tk.Entry(parent, textvariable=var, width=width,
                    font=FONTE_LABEL, fg=COR_TEXTO, bg=COR_INPUT,
                    insertbackground=COR_TEXTO, relief="flat",
                    highlightthickness=1, highlightbackground=COR_BORDA,
                    highlightcolor=COR_ACCENT, **kw)

def styled_btn(parent, text, command, cor=COR_ACCENT, width=14, **kw):
    b = tk.Button(parent, text=text, command=command,
                  font=FONTE_BTN, fg="white", bg=cor,
                  activebackground=COR_BTN_HOV, activeforeground="white",
                  relief="flat", cursor="hand2", width=width, padx=8, pady=6, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=COR_BTN_HOV))
    b.bind("<Leave>", lambda e: b.config(bg=cor))
    return b

def styled_card(parent, **kw):
    return tk.Frame(parent, bg=COR_CARD, relief="flat",
                    highlightthickness=1, highlightbackground=COR_BORDA, **kw)

def styled_check(parent, text, var, **kw):
    return tk.Checkbutton(parent, text=text, variable=var,
                          font=FONTE_LABEL, fg=COR_TEXTO,
                          bg=parent.cget("bg"),
                          activebackground=parent.cget("bg"),
                          activeforeground=COR_ACCENT,
                          selectcolor=COR_INPUT, relief="flat", **kw)

def styled_combo(parent, var, values, width=20, **kw):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.TCombobox",
                    fieldbackground=COR_INPUT, background=COR_BTN,
                    foreground="#FFFFFF", selectbackground=COR_ACCENT,
                    selectforeground="#FFFFFF")
    style.map("Dark.TCombobox",
              fieldbackground=[("readonly", COR_INPUT)],
              foreground=[("readonly", "#FFFFFF")],
              selectbackground=[("readonly", COR_ACCENT)])
    return ttk.Combobox(parent, textvariable=var, values=values,
                        width=width, font=FONTE_LABEL,
                        style="Dark.TCombobox", state="readonly", **kw)

def add_tooltip(widget, text):
    tip = None
    def show(e):
        nonlocal tip
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, font=FONTE_SMALL,
                 fg="#1E2330", bg="#F0C040",
                 relief="flat", padx=6, pady=4).pack()
    def hide(e):
        nonlocal tip
        if tip:
            tip.destroy()
            tip = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


# ---------------------------------------------------------------------------
# Janela base
# ---------------------------------------------------------------------------

class JanelaBase(tk.Toplevel):
    def __init__(self, master, titulo, largura=820, altura=700):
        super().__init__(master)
        self.title(f"Distribuição de Terraplenagem — {titulo}")
        self.configure(bg=COR_BG)
        self.geometry(f"{largura}x{altura}")
        self.resizable(True, True)
        self.minsize(largura, altura)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{largura}x{altura}+{(sw-largura)//2}+{(sh-altura)//2}")
        self.grab_set()

        # Topo
        tk.Frame(self, bg=COR_ACCENT, height=4).pack(fill="x")
        top = tk.Frame(self, bg=COR_PAINEL)
        top.pack(fill="x")
        tk.Label(top, text="⬡  TERRAPLENAGEM", font=("Segoe UI",9,"bold"),
                 fg=COR_ACCENT, bg=COR_PAINEL).pack(side="left", padx=16, pady=8)
        tk.Label(top, text=titulo.upper(), font=("Segoe UI",9,"bold"),
                 fg=COR_SUBTEXTO, bg=COR_PAINEL).pack(side="right", padx=16)
        tk.Frame(self, bg=COR_BORDA, height=1).pack(fill="x")

        # Rodapé fixo
        self._frame_rodape = tk.Frame(self, bg=COR_PAINEL)
        self._frame_rodape.pack(fill="x", side="bottom")
        tk.Frame(self._frame_rodape, bg=COR_BORDA, height=1).pack(fill="x")
        self._inner_rodape = tk.Frame(self._frame_rodape, bg=COR_PAINEL)
        self._inner_rodape.pack(fill="x", padx=20, pady=10)

        # Canvas scrollável
        self._canvas = tk.Canvas(self, bg=COR_BG, highlightthickness=0)
        self._scroll = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)
        self.conteudo = tk.Frame(self._canvas, bg=COR_BG)
        self._cw = self._canvas.create_window((0,0), window=self.conteudo, anchor="nw")
        self.conteudo.bind("<Configure>",
                           lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._cw, width=e.width))
        self.bind_all("<MouseWheel>",
                      lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))

    def adicionar_botoes(self, btn_cancelar=None, btn_voltar=None,
                         btn_proximo=None, texto_proximo="Próximo →"):
        if btn_cancelar:
            styled_btn(self._inner_rodape, "✕ Cancelar", btn_cancelar,
                       cor=COR_DANGER, width=12).pack(side="left")
        if btn_voltar:
            styled_btn(self._inner_rodape, "← Voltar", btn_voltar,
                       cor=COR_BTN, width=12).pack(side="left", padx=(8,0))
        if btn_proximo:
            styled_btn(self._inner_rodape, texto_proximo, btn_proximo,
                       cor=COR_ACCENT, width=18).pack(side="right")


# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------

class EstadoProjeto:
    def __init__(self):
        self.nome              = ""
        self.arquivos          = []
        self.unidade           = "estaca"
        self.em_distancia      = False
        self.dist_estaca       = 20.0
        self.dist_max_bloco    = 20.0  # limiar para blocos separados
        self.fatores_hom       = {}
        self.mapeamento        = None
        self.params            = None
        self.config_dist       = None
        self.bota_foras        = []
        self.emprestimos       = []
        self.config_restricoes = None  # ConfigRestricoes | None
        self.materiais_encontrados = []
        self.ramos_nomes       = []
        self.caminho_json      = ""
        self.caminho_excel     = ""
        self._tipo_projeto     = "segmento"
        self._projeto_lido     = None


# ---------------------------------------------------------------------------
# Janela 1 — Projeto
# ---------------------------------------------------------------------------

class Janela1Projeto(JanelaBase):
    def __init__(self, master, estado, callback_proximo):
        super().__init__(master, "Projeto", 700, 560)
        self.estado = estado
        self.callback_proximo = callback_proximo
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_proximo=self._novo,
                              texto_proximo="Criar Novo Projeto →")

    def _construir(self):
        c = self.conteudo
        styled_label(c, "CONFIGURAÇÃO DO PROJETO",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)

        card = styled_card(c)
        card.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(card, text="📁  Novo Projeto", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(12,6))

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=4)
        styled_label(row, "Nome do Projeto:", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_nome = tk.StringVar(value=self.estado.nome)
        styled_entry(row, self.var_nome, width=35).pack(side="left")

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=4)
        styled_label(row, "Tipo:", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_tipo = tk.StringVar(value="segmento")
        for txt, val in [("Segmento único","segmento"),("Interseção / Múltiplos","intersecao")]:
            tk.Radiobutton(row, text=txt, variable=self.var_tipo, value=val,
                           font=FONTE_LABEL, fg=COR_TEXTO, bg=COR_CARD,
                           activebackground=COR_CARD, selectcolor=COR_INPUT
                           ).pack(side="left", padx=8)

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=4)
        styled_label(row, "Unidade:", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_unidade = tk.StringVar(value="estaca")
        for txt, val in [("Estaca (20m)","estaca"),("Km","km")]:
            tk.Radiobutton(row, text=txt, variable=self.var_unidade, value=val,
                           font=FONTE_LABEL, fg=COR_TEXTO, bg=COR_CARD,
                           activebackground=COR_CARD, selectcolor=COR_INPUT
                           ).pack(side="left", padx=8)

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=4)
        self.var_dist = tk.BooleanVar(value=False)
        styled_check(row, "Arquivo vem em distância (metros)", self.var_dist).pack(side="left")

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=(4,4))
        styled_label(row, "Distância entre estacas (m):", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_dist_estaca = tk.StringVar(value="20")
        styled_entry(row, self.var_dist_estaca, width=8).pack(side="left")
        styled_label(row, "(padrão: 20m)", cor=COR_SUBTEXTO, bg=COR_CARD).pack(side="left", padx=8)

        row = tk.Frame(card, bg=COR_CARD); row.pack(fill="x", padx=16, pady=(0,12))
        styled_label(row, "Dist. máxima entre blocos (m):", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_dist_max_bloco = tk.StringVar(value="20")
        styled_entry(row, self.var_dist_max_bloco, width=8).pack(side="left")
        styled_label(row, "Acima disso o volume entre estacas é zerado",
                     cor=COR_SUBTEXTO, bg=COR_CARD).pack(side="left", padx=8)

        card2 = styled_card(c)
        card2.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(card2, text="🔄  Carregar Projeto Existente",
                 font=FONTE_SUB, fg=COR_TEXTO, bg=COR_CARD
                 ).pack(anchor="w", padx=16, pady=(12,6))
        row = tk.Frame(card2, bg=COR_CARD); row.pack(fill="x", padx=16, pady=(0,12))
        styled_btn(row, "Selecionar JSON...", self._carregar,
                   cor=COR_BTN, width=18).pack(side="left")
        self.lbl_json = styled_label(row, "Nenhum arquivo selecionado", cor=COR_SUBTEXTO)
        self.lbl_json.pack(side="left", padx=12)

        card3 = styled_card(c)
        card3.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(card3, text="🔀  Redistribuição entre Segmentos",
                 font=FONTE_SUB, fg=COR_TEXTO, bg=COR_CARD
                 ).pack(anchor="w", padx=16, pady=(12,6))
        styled_label(card3,
                     "Redistribua material entre segmentos já distribuídos "
                     "usando os JSONs gerados.",
                     cor=COR_SUBTEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(0,4))
        row3 = tk.Frame(card3, bg=COR_CARD); row3.pack(fill="x", padx=16, pady=(0,12))
        styled_btn(row3, "Abrir Redistribuição →", self._abrir_redist,
                   cor="#F39C12", width=22).pack(side="left")

    def _novo(self):
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showwarning("Atenção", "Informe o nome do projeto.", parent=self)
            return
        self.estado.nome         = nome
        self.estado.unidade      = self.var_unidade.get()
        self.estado.em_distancia = self.var_dist.get()
        try:
            self.estado.dist_estaca = float(self.var_dist_estaca.get())
        except ValueError:
            self.estado.dist_estaca = 20.0
        try:
            self.estado.dist_max_bloco = float(self.var_dist_max_bloco.get())
        except ValueError:
            self.estado.dist_max_bloco = 20.0
        self.estado._tipo_projeto = self.var_tipo.get()
        self.destroy()
        self.callback_proximo(2)

    def _carregar(self):
        path = filedialog.askopenfilename(
            title="Selecionar projeto JSON",
            filetypes=[("JSON","*.json"),("Todos","*.*")], parent=self)
        if not path:
            return
        try:
            from projeto_json import carregar_projeto
            dados = carregar_projeto(path)
            self.estado.nome         = dados["nome"]
            self.estado.arquivos     = dados["arquivos"]
            self.estado.mapeamento   = dados["mapeamento"]
            self.estado.params       = dados["params"]
            self.estado.config_dist  = dados["config_dist"]
            self.estado.bota_foras   = dados["config_dist"].bota_foras
            self.estado.emprestimos  = dados["config_dist"].emprestimos
            self.estado.caminho_json = path
            self.estado.fatores_hom      = dados["config_leitura"].fatores_hom
            self.estado.dist_max_bloco   = dados["config_leitura"].dist_max_bloco
            self.estado.unidade          = dados["config_leitura"].unidade
            self.estado.em_distancia     = dados["config_leitura"].em_distancia
            self.estado.dist_estaca      = dados["config_leitura"].dist_estaca
            self.estado.config_restricoes= dados.get("config_restricoes", None)
            self.estado._resultado_carregado = dados
            # Restaurar ramos do JSON
            self.estado.ramos_nomes = list(dict.fromkeys(
                r["nome"] for r in dados.get("ramos", [])))
            self.estado._tipo_projeto = dados.get("config_dist", {}).tipo_projeto                 if hasattr(dados.get("config_dist"), "tipo_projeto")                 else "segmento"
            self.lbl_json.config(text=os.path.basename(path), fg=COR_ACCENT2)
            messagebox.showinfo("Projeto carregado",
                                f"Projeto '{dados['nome']}' carregado!\n"
                                f"Atualizado em: {dados['data_atualizacao']}", parent=self)
            self.destroy()
            self.callback_proximo(2)
        except Exception as ex:
            messagebox.showerror("Erro", str(ex), parent=self)

    def _abrir_redist(self):
        # JanelaRedistribuicao definida no final do arquivo
        # usar globals() para evitar problema de ordem de definição
        cls = globals().get("JanelaRedistribuicao")
        if cls is None:
            messagebox.showerror("Erro", "JanelaRedistribuicao não encontrada.", parent=self)
            return
        j = cls(self.master)
        j.protocol("WM_DELETE_WINDOW", j.destroy)

    def _cancelar(self):
        if messagebox.askokcancel("Sair", "Deseja sair?", parent=self):
            self.master.quit()


# ---------------------------------------------------------------------------
# Janela 2 — Arquivos
# ---------------------------------------------------------------------------

class Janela2Arquivos(JanelaBase):
    def __init__(self, master, estado, callback_proximo, callback_voltar):
        super().__init__(master, "Arquivos", 820, 580)
        self.estado = estado
        self.callback_proximo = callback_proximo
        self.callback_voltar  = callback_voltar
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._proximo)

    def _construir(self):
        c = self.conteudo
        styled_label(c, "SELEÇÃO DE ARQUIVOS EXCEL",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)

        card = styled_card(c)
        card.pack(fill="both", expand=True, padx=20, pady=(0,10))

        hdr = tk.Frame(card, bg=COR_BORDA); hdr.pack(fill="x", padx=2, pady=(2,0))
        for txt, w in [("Arquivo",40),("Tipo",24),("",5)]:
            tk.Label(hdr, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, width=w, anchor="w").pack(side="left", padx=4, pady=4)

        frame_sc = tk.Frame(card, bg=COR_CARD); frame_sc.pack(fill="both", expand=True, padx=2)
        cv = tk.Canvas(frame_sc, bg=COR_CARD, highlightthickness=0)
        sb = tk.Scrollbar(frame_sc, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self.frame_arqs = tk.Frame(cv, bg=COR_CARD)
        cv.create_window((0,0), window=self.frame_arqs, anchor="nw")
        self.frame_arqs.bind("<Configure>",
                             lambda e: cv.configure(scrollregion=cv.bbox("all")))

        btns = tk.Frame(card, bg=COR_CARD); btns.pack(fill="x", padx=12, pady=8)
        styled_btn(btns, "+ Civil 3D (Tipo 1)", lambda: self._adicionar(1),
                   cor=COR_ACCENT, width=18).pack(side="left", padx=(0,8))
        styled_btn(btns, "+ Só áreas (Tipo 2)", lambda: self._adicionar(2),
                   cor=COR_BTN, width=18).pack(side="left")

        for arq in self.estado.arquivos:
            self._add_linha(arq["caminho"], arq["tipo"])

    def _adicionar(self, tipo):
        paths = filedialog.askopenfilenames(
            title=f"Selecionar Excel Tipo {tipo}",
            filetypes=[("Excel","*.xlsx *.xls"),("Todos","*.*")], parent=self)
        for p in paths:
            if not any(a["caminho"]==p for a in self.estado.arquivos):
                self.estado.arquivos.append({"caminho":p,"tipo":tipo})
                self._add_linha(p, tipo)

    def _add_linha(self, caminho, tipo):
        row = tk.Frame(self.frame_arqs, bg=COR_CARD); row.pack(fill="x", padx=4, pady=2)
        tk.Label(row, text=os.path.basename(caminho), font=FONTE_MONO,
                 fg=COR_TEXTO, bg=COR_CARD, width=40, anchor="w").pack(side="left", padx=4)
        tk.Label(row, text="Civil 3D" if tipo==1 else "Só áreas",
                 font=FONTE_SMALL, fg=COR_ACCENT, bg=COR_CARD,
                 width=24, anchor="w").pack(side="left")
        def rem(c=caminho, r=row):
            self.estado.arquivos = [a for a in self.estado.arquivos if a["caminho"]!=c]
            r.destroy()
        tk.Button(row, text="✕", font=FONTE_SMALL, fg=COR_DANGER, bg=COR_CARD,
                  activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=rem).pack(side="left", padx=4)

    def _proximo(self):
        if not self.estado.arquivos:
            messagebox.showwarning("Atenção","Adicione pelo menos um arquivo.", parent=self)
            return
        try:
            from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
            config = ConfigLeitura(unidade=self.estado.unidade,
                                   em_distancia=self.estado.em_distancia,
                                   dist_estaca=self.estado.dist_estaca,
                                   dist_max_bloco=self.estado.dist_max_bloco)
            projeto = ler_multiplos_arquivos(self.estado.arquivos, config)
            mats = set()
            for ramo in projeto.ramos:
                mats.update(ramo.materiais)
            self.estado.materiais_encontrados = sorted(mats)
            self.estado.ramos_nomes = list(dict.fromkeys(r.nome for r in projeto.ramos))
            self.estado._projeto_lido = projeto
        except Exception as ex:
            messagebox.showerror("Erro ao ler arquivos", str(ex), parent=self)
            return
        self.destroy()
        self.callback_proximo(3)

    def _cancelar(self):
        if messagebox.askokcancel("Sair","Deseja sair?",parent=self):
            self.master.quit()


# ---------------------------------------------------------------------------
# Janela 3 — Materiais
# ---------------------------------------------------------------------------

CATEGORIAS = ["Corte 1ª","Corte 2ª","Corte 3ª","Aterro CA","Aterro CF","Ignorar"]
CAT_MAP    = {"Corte 1ª":"corte1","Corte 2ª":"corte2","Corte 3ª":"corte3",
              "Aterro CA":"aterro_ca","Aterro CF":"aterro_cf","Ignorar":"ignorar"}
CAT_AUTO   = {
    "corte1":    ["Corte1","CORTE1","Corte 1"],
    "corte2":    ["Corte2","CORTE2","Corte 2"],
    "corte3":    ["Corte3","CORTE3","Corte 3","rocha"],
    "aterro_ca": ["Aterro","ATERRO","Fill"],
    "aterro_cf": ["CF","cf","Camada Final"],
    "ignorar":   ["Limpeza","Solo Mole","Vegetal"],
}

def _sugerir_cat(mat):
    ml = mat.lower().replace(" ","").replace("_","")
    for cat_key, nomes in CAT_AUTO.items():
        for n in nomes:
            if n.lower().replace(" ","").replace("_","") in ml:
                return cat_key
    return "corte1"


class Janela3Materiais(JanelaBase):
    def __init__(self, master, estado, callback_proximo, callback_voltar):
        super().__init__(master, "Materiais", 820, 660)
        self.estado = estado
        self.callback_proximo = callback_proximo
        self.callback_voltar  = callback_voltar
        self.vars_cat  = {}
        self.vars_pref = {}
        self.vars_fh   = {}  # só para tipo 2
        self.tem_tipo2 = any(a.get("tipo") == 2 for a in estado.arquivos)
        self.mostrar_fh = True  # sempre mostra FH — necessário para gerador_excel
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._proximo)

    def _construir(self):
        c = self.conteudo
        styled_label(c, "MAPEAMENTO DE MATERIAIS",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)
        styled_label(c, "Associe cada material à sua categoria de terraplenagem.",
                     cor=COR_SUBTEXTO).pack(anchor="w", padx=20, pady=(0,8))

        card = styled_card(c); card.pack(fill="both", expand=True, padx=20, pady=(0,8))
        hdr = tk.Frame(card, bg=COR_BORDA); hdr.pack(fill="x", padx=2, pady=(2,0))
        cols = [("Material encontrado",25),("Categoria",22)]
        if self.mostrar_fh:
            cols.append(("FH",6))
        for txt, w in cols:
            tk.Label(hdr, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, width=w, anchor="w").pack(side="left", padx=8, pady=4)

        frame_sc = tk.Frame(card, bg=COR_CARD); frame_sc.pack(fill="both", expand=True, padx=2)
        cv = tk.Canvas(frame_sc, bg=COR_CARD, highlightthickness=0)
        sb = tk.Scrollbar(frame_sc, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self.frame_mats = tk.Frame(cv, bg=COR_CARD)
        cv.create_window((0,0), window=self.frame_mats, anchor="nw")
        self.frame_mats.bind("<Configure>",
                             lambda e: cv.configure(scrollregion=cv.bbox("all")))

        for mat in self.estado.materiais_encontrados:
            row = tk.Frame(self.frame_mats, bg=COR_CARD); row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=mat, font=FONTE_LABEL, fg=COR_TEXTO,
                     bg=COR_CARD, width=25, anchor="w").pack(side="left", padx=4)

            # Restaurar categoria do estado.mapeamento se já foi configurado
            cat_salva = None
            if self.estado.mapeamento:
                m = self.estado.mapeamento
                if mat in getattr(m, 'corte1',    []): cat_salva = "Corte 1ª"
                elif mat in getattr(m, 'corte2',  []): cat_salva = "Corte 2ª"
                elif mat in getattr(m, 'corte3',  []): cat_salva = "Corte 3ª"
                elif mat in getattr(m, 'aterro_ca',[]): cat_salva = "Aterro CA"
                elif mat in getattr(m, 'aterro_cf',[]): cat_salva = "Aterro CF"
                elif mat in getattr(m, 'ignorar', []): cat_salva = "Ignorar"
            if cat_salva is None:
                sug = _sugerir_cat(mat)
                cat_salva = next((k for k,v in CAT_MAP.items() if v==sug), "Corte 1ª")

            var = tk.StringVar(value=cat_salva)
            self.vars_cat[mat] = var
            styled_combo(row, var, CATEGORIAS, width=18).pack(side="left", padx=8)
            if self.mostrar_fh:
                fh_salvo = self.estado.fatores_hom.get(mat, 1.0) if self.estado.fatores_hom else 1.0
                var_fh = tk.StringVar(value=str(fh_salvo))
                self.vars_fh[mat] = var_fh
                styled_entry(row, var_fh, width=6).pack(side="left", padx=4)

        card2 = styled_card(c); card2.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(card2, text="Prefixos dos rótulos", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(8,4))
        grid = tk.Frame(card2, bg=COR_CARD); grid.pack(fill="x", padx=16, pady=(0,10))

        # Restaurar prefixos do estado.mapeamento se disponível
        m = self.estado.mapeamento
        prefixos = [
            ("C1:", getattr(m,'prefixo_c1','C-')  if m else "C-"),
            ("C2:", getattr(m,'prefixo_c2','C2-') if m else "C2-"),
            ("C3:", getattr(m,'prefixo_c3','C3-') if m else "C3-"),
            ("CA:", getattr(m,'prefixo_ca','CA-') if m else "CA-"),
            ("CF:", getattr(m,'prefixo_cf','CF-') if m else "CF-"),
            ("CL:", getattr(m,'prefixo_cl','CL-') if m else "CL-"),
            ("BF:", getattr(m,'prefixo_bf','BF-') if m else "BF-"),
            ("AE:", getattr(m,'prefixo_ae','AE-') if m else "AE-"),
        ]
        for i, (lbl, val) in enumerate(prefixos):
            f = tk.Frame(grid, bg=COR_CARD); f.grid(row=0, column=i, padx=6, pady=4)
            tk.Label(f, text=lbl, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_CARD, width=3).pack(side="left")
            v = tk.StringVar(value=val)
            self.vars_pref[lbl.replace(":","").strip()] = v
            styled_entry(f, v, width=5).pack(side="left")

    def _proximo(self):
        from detector_trechos import MapeamentoMateriais
        grupos = {k:[] for k in CAT_MAP.values()}
        for mat, var in self.vars_cat.items():
            grupos[CAT_MAP.get(var.get(),"ignorar")].append(mat)
        p = self.vars_pref
        self.estado.mapeamento = MapeamentoMateriais(
            corte1=grupos["corte1"], corte2=grupos["corte2"],
            corte3=grupos["corte3"], aterro_ca=grupos["aterro_ca"],
            aterro_cf=grupos["aterro_cf"], ignorar=grupos["ignorar"],
            prefixo_c1=p["C1"].get(), prefixo_c2=p["C2"].get(),
            prefixo_c3=p["C3"].get(), prefixo_ca=p["CA"].get(),
            prefixo_cf=p["CF"].get(), prefixo_cl=p["CL"].get(),
            prefixo_bf=p["BF"].get(), prefixo_ae=p["AE"].get())
        # Salvar FHs — para todos os tipos
        if self.mostrar_fh and self.vars_fh:
            fatores = {}
            for mat, var_fh in self.vars_fh.items():
                try:
                    fatores[mat] = float(var_fh.get())
                except ValueError:
                    fatores[mat] = 1.0
            self.estado.fatores_hom = fatores
        self.destroy()
        self.callback_proximo(4)

    def _cancelar(self):
        if messagebox.askokcancel("Sair","Deseja sair?",parent=self):
            self.master.quit()


# ---------------------------------------------------------------------------
# Janela 4 — Parâmetros
# ---------------------------------------------------------------------------

class Janela4Parametros(JanelaBase):
    def __init__(self, master, estado, callback_proximo, callback_voltar):
        super().__init__(master, "Parâmetros", 860, 720)
        self.estado = estado
        self.callback_proximo = callback_proximo
        self.callback_voltar  = callback_voltar
        self.relacoes_dados   = []
        self.params_por_ramo  = {}
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._proximo)

    def _construir(self):
        c = self.conteudo
        styled_label(c, "PARÂMETROS DE DISTRIBUIÇÃO",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)

        # Card materiais por segmento
        card1 = styled_card(c); card1.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(card1, text="Materiais por Segmento", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))
        styled_label(card1, "Configure o uso de C2 e C3 por segmento.",
                     cor=COR_SUBTEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(0,6))

        # Deduplica ramos
        vistos = set()
        ramos_unicos = []
        for r in self.estado.ramos_nomes:
            if r not in vistos:
                vistos.add(r)
                ramos_unicos.append(r)

        # Tabela com frames de largura fixa
        tbl_outer = tk.Frame(card1, bg=COR_BORDA)
        tbl_outer.pack(fill="x", padx=16, pady=(0,10))
        tbl = tk.Frame(tbl_outer, bg=COR_CARD)
        tbl.pack(fill="x", padx=1, pady=1)

        # Definição das colunas: (texto, largura_px)
        colunas = [
            ("Segmento",   180),
            ("C3 int.",     55),
            ("C3 ext.",     55),
            ("Vol.mín C3",  80),
            ("% máx C3",    65),
            ("C2 int.",     55),
            ("C2 ext.",     55),
        ]
        tips_col = [
            "",
            "Usa C3 internamente neste segmento",
            "Aceita receber C3 de outro segmento",
            "Volume mínimo do aterro para usar C3 (m³)",
            "% máximo do aterro que pode receber C3",
            "Usa C2 internamente neste segmento",
            "Aceita receber C2 de outro segmento",
        ]

        # Cabeçalho
        for col, ((txt, w), tip) in enumerate(zip(colunas, tips_col)):
            frm = tk.Frame(tbl, bg=COR_BORDA, width=w, height=30)
            frm.pack_propagate(False)
            frm.grid(row=0, column=col, padx=1, pady=(0,1), sticky="nsew")
            lbl = tk.Label(frm, text=txt, font=FONTE_SMALL,
                           fg="#FFFFFF", bg=COR_BORDA, anchor="center")
            lbl.pack(fill="both", expand=True)
            if tip:
                add_tooltip(lbl, tip)

        # Linhas de dados
        for row_idx, ramo in enumerate(ramos_unicos, start=1):
            bg = COR_CARD if row_idx % 2 == 1 else COR_PAINEL
            v_c3i  = tk.BooleanVar(value=False)
            v_c3e  = tk.BooleanVar(value=False)
            v_c2i  = tk.BooleanVar(value=False)
            v_c2e  = tk.BooleanVar(value=False)
            v_vmin = tk.StringVar(value="500")
            v_pct  = tk.StringVar(value="50")

            col_data = [
                ("label", ramo,  180, None,   ""),
                ("check", None,   55, v_c3i,  "Usa C3 internamente"),
                ("check", None,   55, v_c3e,  "Aceita C3 externo"),
                ("entry", None,   80, v_vmin, "Vol. mínimo aterro p/ C3 (m³)"),
                ("entry", None,   65, v_pct,  "% máx aterro p/ C3"),
                ("check", None,   55, v_c2i,  "Usa C2 internamente"),
                ("check", None,   55, v_c2e,  "Aceita C2 externo"),
            ]

            for col, (tipo, txt, w, var, tip) in enumerate(col_data):
                frm = tk.Frame(tbl, bg=bg, width=w, height=28)
                frm.pack_propagate(False)
                frm.grid(row=row_idx, column=col, padx=1, pady=1, sticky="nsew")
                if tipo == "label":
                    tk.Label(frm, text=txt, font=FONTE_SMALL,
                             fg=COR_TEXTO, bg=bg, anchor="w",
                             padx=6).pack(fill="both", expand=True)
                elif tipo == "check":
                    cb = tk.Checkbutton(frm, variable=var, bg=bg,
                                        activebackground=bg,
                                        selectcolor="#E74C3C", relief="flat")
                    cb.pack(expand=True)
                    if tip: add_tooltip(cb, tip)
                elif tipo == "entry":
                    e = styled_entry(frm, var, width=6)
                    e.pack(expand=True, pady=2)
                    if tip: add_tooltip(e, tip)

            # Pre-popular do estado carregado
            p = self.estado.params
            if isinstance(p, dict) and ramo in p:
                pr = p[ramo]
                v_c3i.set(pr.usar_corte3_interno)
                v_c3e.set(pr.aceita_corte3_externo)
                v_c2i.set(pr.usar_corte2_interno)
                v_c2e.set(pr.aceita_corte2_externo)
                v_vmin.set(str(pr.vol_min_aterro_c3))
                v_pct.set(str(pr.pct_max_c3))
            elif p and not isinstance(p, dict):
                v_c3i.set(p.usar_corte3_interno)
                v_c3e.set(p.aceita_corte3_externo)
                v_c2i.set(p.usar_corte2_interno)
                v_c2e.set(p.aceita_corte2_externo)
                v_vmin.set(str(p.vol_min_aterro_c3))
                v_pct.set(str(p.pct_max_c3))

            self.params_por_ramo[ramo] = {
                "c3i": v_c3i, "c3e": v_c3e,
                "c2i": v_c2i, "c2e": v_c2e,
                "vmin": v_vmin, "pct": v_pct
            }

        # Estratégia e DMT
        row = tk.Frame(card1, bg=COR_CARD); row.pack(fill="x", padx=16, pady=4)
        styled_label(row, "Estratégia:", bg=COR_CARD).pack(side="left", padx=(0,8))
        _estrategia = "usar_tudo"
        _dmt_cl = "0.050"
        if self.estado.config_dist:
            _estrategia = self.estado.config_dist.estrategia or "usar_tudo"
            _dmt_cl = str(self.estado.config_dist.dmt_cl)
        self.var_estrategia = tk.StringVar(value=_estrategia)
        for txt, val in [("Otimizar DMT (Stepping-Stone)","otimizar"),
                         ("Usar tudo (Custo Mínimo)","usar_tudo")]:
            tk.Radiobutton(row, text=txt, variable=self.var_estrategia, value=val,
                           font=FONTE_LABEL, fg="#FFFFFF", bg=COR_CARD,
                           activebackground=COR_CARD, activeforeground=COR_ACCENT,
                           selectcolor=COR_ACCENT).pack(side="left", padx=8)

        row = tk.Frame(card1, bg=COR_CARD); row.pack(fill="x", padx=16, pady=(4,12))
        styled_label(row, "DMT comp. lateral (km):", bg=COR_CARD).pack(side="left", padx=(0,6))
        self.var_dmt_cl = tk.StringVar(value=_dmt_cl)
        styled_entry(row, self.var_dmt_cl, width=8).pack(side="left", padx=(0,16))
        self.var_usa_dmt_max = tk.BooleanVar(value=False)
        styled_check(row, "DMT máxima (km):", self.var_usa_dmt_max,
                     command=self._toggle_dmt_max).pack(side="left", padx=(0,4))
        self.var_dmt_max = tk.StringVar(value="10.0")
        self.entry_dmt_max = styled_entry(row, self.var_dmt_max, width=8, state="disabled")
        self.entry_dmt_max.pack(side="left")

        # Encadeamento de relações
        row_enc = tk.Frame(card1, bg=COR_CARD); row_enc.pack(fill="x", padx=16, pady=(0,8))
        _usar_enc = False
        if self.estado.config_dist:
            _usar_enc = getattr(self.estado.config_dist, 'usar_encadeamento', False)
        self.var_encadeamento = tk.BooleanVar(value=_usar_enc)
        styled_check(row_enc, "Usar encadeamento de relações na rodada externa",
                     self.var_encadeamento).pack(side="left")

        # Relações entre segmentos
        if len(ramos_unicos) > 1:
            card2 = styled_card(c); card2.pack(fill="x", padx=20, pady=(0,8))
            tk.Label(card2, text="Relações entre Segmentos", font=FONTE_SUB,
                     fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))
            styled_label(card2, "Defina como calcular a DMT entre pares de segmentos.",
                         cor=COR_SUBTEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(0,4))
            btn_row = tk.Frame(card2, bg=COR_CARD); btn_row.pack(fill="x", padx=16, pady=(0,4))
            styled_btn(btn_row, "+ Adicionar Relação",
                       lambda: self._add_relacao(card2, ramos_unicos),
                       cor=COR_ACCENT2, width=18).pack(side="left")
            self.frame_rels = tk.Frame(card2, bg=COR_CARD)
            self.frame_rels.pack(fill="x", padx=16, pady=(0,8))

            # Pre-popular relações do estado carregado
            if self.estado.config_dist and self.estado.config_dist.relacoes:
                for rel in self.estado.config_dist.relacoes:
                    if rel.ramo_a in ramos_unicos and rel.ramo_b in ramos_unicos:
                        self._add_relacao_preenchida(card2, ramos_unicos, rel)
        else:
            self.frame_rels = None

    def _toggle_dmt_max(self):
        self.entry_dmt_max.config(
            state="normal" if self.var_usa_dmt_max.get() else "disabled")

    def _add_relacao(self, card_pai, ramos):
        """Adiciona nova relação em branco."""
        self._criar_linha_relacao(ramos, rel=None)

    def _add_relacao_preenchida(self, card_pai, ramos, rel):
        """Adiciona relação pre-preenchida a partir de RelacaoSegmentos."""
        self._criar_linha_relacao(ramos, rel=rel)

    def _criar_linha_relacao(self, ramos, rel=None):
        """
        Cria uma linha de relacao na lista.
        Tipos: 'pistas_paralelas' e 'intersecao_marginal'.
        Compatibilidade: tipos v1.0 convertidos automaticamente.
        """
        from distribuidor2 import RelacaoSegmentos

        # Mapear tipos v1.0 → v2.0 para pre-populacao
        _mapa_tipos = {
            'estaca':             'pistas_paralelas',
            'distancia':          'pistas_paralelas',
            'fixa':               'intersecao_marginal',
            'intersecao_interna': 'intersecao_marginal',
            'intersecao_externa': 'intersecao_marginal',
        }

        tipo_inicial = 'pistas_paralelas'
        if rel:
            tipo_inicial = _mapa_tipos.get(rel.tipo, rel.tipo)

        frame = tk.Frame(self.frame_rels, bg=COR_CARD,
                         highlightthickness=1, highlightbackground=COR_BORDA)
        frame.pack(fill="x", pady=3)

        # --- Linha 1: ramos A ↔ B + tipo + flags ---
        r1 = tk.Frame(frame, bg=COR_CARD)
        r1.pack(fill="x", padx=8, pady=(6,2))

        var_ramo_a = tk.StringVar(value=rel.ramo_a if rel else ramos[0])
        var_ramo_b = tk.StringVar(value=rel.ramo_b if rel else (ramos[1] if len(ramos)>1 else ramos[0]))
        var_tipo   = tk.StringVar(value=tipo_inicial)

        styled_label(r1, "A:", bg=COR_CARD).pack(side="left", padx=(0,4))
        cb_a = styled_combo(r1, var_ramo_a, ramos, width=20)
        cb_a.pack(side="left", padx=(0,8))
        add_tooltip(cb_a, "Ramo A da relação.\nPara Pistas Paralelas: qualquer dos dois eixos.\nPara Interseção/Marginal: SEMPRE o eixo principal (pista).")

        styled_label(r1, "↔  B:", bg=COR_CARD).pack(side="left", padx=(0,4))
        cb_b = styled_combo(r1, var_ramo_b, ramos, width=20)
        cb_b.pack(side="left", padx=(0,12))
        add_tooltip(cb_b, "Ramo B da relação.\nPara Pistas Paralelas: o outro eixo paralelo.\nPara Interseção/Marginal: a interseção ou marginal.")

        for txt, val, tip in [
            ("Pistas paralelas",    "pistas_paralelas",
             "Dois eixos paralelos com sistemas de estacagem diferentes.\n"
             "Usa posição física relativa para calcular DMT corretamente.\n"
             "Ex: Pista Direita ↔ Pista Esquerda"),
            ("Interseção/Marginal", "intersecao_marginal",
             "Interseção, marginal ou ramo conectado a um eixo principal.\n"
             "Ramo A = eixo principal. Ramo B = interseção/marginal.\n"
             "Informe a posição relativa da conexão no eixo principal.")
        ]:
            rb = tk.Radiobutton(r1, text=txt, variable=var_tipo, value=val,
                               font=FONTE_SMALL, fg="#FFFFFF", bg=COR_CARD,
                               activebackground=COR_CARD, activeforeground=COR_ACCENT,
                               selectcolor=COR_ACCENT,
                               command=lambda f=frame, vt=var_tipo: self._atualizar_params_rel(f, vt))
            rb.pack(side="left", padx=4)
            add_tooltip(rb, tip)

        # Checkbox: usar na rodada interna (pistas paralelas)
        var_interna = tk.BooleanVar(value=getattr(rel, 'pistas_paralelas', False) or
                                          getattr(rel, 'usar_rodada_interna', False) if rel else False)
        cb_int = tk.Checkbutton(r1, text="Usar na rodada interna",
                                variable=var_interna,
                                font=FONTE_SMALL, fg=COR_ACCENT2, bg=COR_CARD,
                                activebackground=COR_CARD, selectcolor="#E74C3C",
                                relief="flat")
        cb_int.pack(side="left", padx=(12,4))
        add_tooltip(cb_int,
                    "Marca os dois ramos para entrar juntos na rodada interna.\n"
                    "O Stepping-Stone decide se vale cruzar material entre eles.\n"
                    "Use para pistas realmente paralelas e próximas.")

        # Checkbox Todos + botão Ramos
        var_todos = tk.BooleanVar(value=rel.todos if rel else False)
        ramos_todos_vars = {r: tk.BooleanVar(value=r in (rel.ramos_todos if rel else []))
                            for r in ramos}

        def _abrir_janela_ramos(vt=var_todos, rtv=ramos_todos_vars, pai=self, _ramos=list(ramos)):
            win = tk.Toplevel(pai)
            win.title("Ramos desta relação")
            win.configure(bg=COR_BG)
            win.resizable(False, True)
            win.geometry("340x420")
            win.grab_set()
            tk.Label(win, text="Selecione os ramos que fazem parte desta relação:",
                     font=FONTE_LABEL, fg="#FFFFFF", bg=COR_BG,
                     wraplength=300, justify="left").pack(pady=(12,4), padx=16, anchor="w")
            tk.Label(win, text="Útil quando uma interseção tem vários subramos\n(ex: INT 04_Eixo 4100, 4200, 4300...).",
                     font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_BG,
                     wraplength=300, justify="left").pack(padx=16, anchor="w", pady=(0,6))
            btn_f = tk.Frame(win, bg=COR_BG); btn_f.pack(fill="x", padx=16, pady=(0,6))
            styled_btn(btn_f, "Marcar todos",    lambda: [v.set(True)  for v in rtv.values()], COR_ACCENT).pack(side="left", padx=(0,6))
            styled_btn(btn_f, "Desmarcar todos", lambda: [v.set(False) for v in rtv.values()], COR_CARD).pack(side="left")
            canvas = tk.Canvas(win, bg=COR_CARD, highlightthickness=0)
            scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y", padx=(0,8))
            canvas.pack(fill="both", expand=True, padx=16, pady=(0,8))
            inner = tk.Frame(canvas, bg=COR_CARD)
            canvas.create_window((0,0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            for ramo in _ramos:
                tk.Checkbutton(inner, text=ramo, variable=rtv[ramo],
                               font=FONTE_SMALL, fg="#CCCCCC", bg=COR_CARD,
                               activebackground=COR_CARD, selectcolor=COR_ACCENT,
                               relief="flat", anchor="w").pack(fill="x", padx=8, pady=2)
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            styled_btn(win, "OK", win.destroy, COR_ACCENT).pack(pady=(0,12))

        cb_todos = tk.Checkbutton(r1, text="Todos",
                                  variable=var_todos,
                                  font=FONTE_SMALL, fg=COR_ACCENT, bg=COR_CARD,
                                  activebackground=COR_CARD, selectcolor="#E74C3C",
                                  relief="flat",
                                  command=_abrir_janela_ramos)
        cb_todos.pack(side="left", padx=(8,2))
        add_tooltip(cb_todos,
                    "Marque para aplicar esta relação a múltiplos ramos.\n"
                    "Ao marcar, abre a lista de ramos para selecionar.\n"
                    "Ex: INT 04 tem subramos 4100, 4200, 4300, 4400, 4500.")

        tk.Button(r1, text="🔧 Ramos", font=FONTE_SMALL, fg=COR_ACCENT,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=_abrir_janela_ramos).pack(side="left", padx=(0,4))

        tk.Button(r1, text="✕ Remover", font=FONTE_SMALL, fg=COR_DANGER,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=lambda f=frame: (
                      f.destroy(),
                      [d for d in self.relacoes_dados if d.get("frame") == f and self.relacoes_dados.remove(d)])
                  ).pack(side="right", padx=4)

        # --- Linha 2: parâmetros dinâmicos ---
        r2 = tk.Frame(frame, bg=COR_CARD)
        r2.pack(fill="x", padx=8, pady=(2,6))

        # Variáveis dos parâmetros — pré-popular se rel fornecida
        def _fv(val, default="0"):
            return str(val) if val is not None else default

        # Pistas paralelas
        var_ini_a     = tk.StringVar(value=_fv(getattr(rel, 'estaca_ini_a_m',   None) or
                                               getattr(rel, 'ref_a_m', None)))
        var_ini_b     = tk.StringVar(value=_fv(getattr(rel, 'estaca_ini_b_m',   None) or
                                               getattr(rel, 'ref_b_m', None)))
        var_desloc_a  = tk.StringVar(value=_fv(getattr(rel, 'deslocamento_a_m', None)))
        var_desloc_b  = tk.StringVar(value=_fv(getattr(rel, 'deslocamento_b_m', None) or
                                               getattr(rel, 'dist_inicio_m', None)))
        var_afast     = tk.StringVar(value=_fv(getattr(rel, 'afastamento_m',    None)))
        # Intersecao/Marginal
        var_pos_rel   = tk.StringVar(value=_fv(getattr(rel, 'pos_relativa_m',   None) or
                                               getattr(rel, 'ref_a_m', None)))
        var_dmt_fixa  = tk.StringVar(value=_fv(getattr(rel, 'dmt_fixa_km',      None), "0.0"))

        vars_rel = {
            "frame": frame, "frame_params": r2,
            "ramo_a": var_ramo_a, "ramo_b": var_ramo_b, "tipo": var_tipo,
            "pistas_paralelas": var_interna,
            "todos": var_todos, "ramos_todos_vars": ramos_todos_vars,
            "estaca_ini_a":   var_ini_a,
            "estaca_ini_b":   var_ini_b,
            "deslocamento_a": var_desloc_a,
            "deslocamento_b": var_desloc_b,
            "afastamento":    var_afast,
            "pos_relativa":   var_pos_rel,
            "dmt_fixa":       var_dmt_fixa,
        }

        # Verificar duplicata
        par_novo = {var_ramo_a.get(), var_ramo_b.get()}
        if rel is None:  # só verificar em novas (não ao pre-popular)
            duplicata = any(
                {vr["ramo_a"].get(), vr["ramo_b"].get()} == par_novo
                for vr in self.relacoes_dados
            )
            if duplicata:
                frame.destroy()
                messagebox.showwarning("Atenção",
                                       "Já existe uma relação entre esses dois segmentos.\n"
                                       "Para a mesma interseção com DMTs diferentes, use o botão Ramos.",
                                       parent=self)
                return

        self.relacoes_dados.append(vars_rel)
        self._atualizar_params_rel(frame, var_tipo, vars_rel)

    def _atualizar_params_rel(self, frame, var_tipo, vars_rel=None):
        """Atualiza os campos de parâmetros conforme o tipo selecionado."""
        if vars_rel is None:
            for vr in self.relacoes_dados:
                if vr["frame"] == frame:
                    vars_rel = vr
                    break
        if not vars_rel:
            return

        r2 = vars_rel["frame_params"]
        for w in r2.winfo_children():
            w.destroy()

        tipo = var_tipo.get()

        if tipo == "pistas_paralelas":
            # Est.ini A | Desloc. A | Est.ini B | Desloc. B | Afastamento
            for lbl, key, tip in [
                ("Est.ini A (m):", "estaca_ini_a",
                 "CMv absoluto do início do eixo A (em metros).\n"
                 "Ex: Pista Direita começa na estaca 5800+00 → 5800 × 20 = 116.000m"),
                ("Desloc. A (m):", "deslocamento_a",
                 "Deslocamento físico do eixo A em relação ao ponto de referência.\n"
                 "0 = começa no ponto de referência. Negativo = começa antes."),
                ("Est.ini B (m):", "estaca_ini_b",
                 "CMv absoluto do início do eixo B (em metros).\n"
                 "Ex: Pista Esquerda começa na estaca 2800+00 → 2800 × 20 = 56.000m"),
                ("Desloc. B (m):", "deslocamento_b",
                 "Deslocamento físico do eixo B em relação ao ponto de referência.\n"
                 "0 = começa no mesmo lugar físico que A (quando deslocamento A também é 0)."),
                ("Afastamento (m):", "afastamento",
                 "Distância lateral entre os dois eixos em metros.\n"
                 "Ex: 22m entre Pista Direita e Pista Esquerda.\n"
                 "Esta distância é sempre somada à DMT calculada."),
            ]:
                lbl_w = styled_label(r2, lbl, bg=COR_CARD)
                lbl_w.pack(side="left", padx=(0,4))
                add_tooltip(lbl_w, tip)
                e = styled_entry(r2, vars_rel[key], width=9)
                e.pack(side="left", padx=(0,10))
                add_tooltip(e, tip)

        elif tipo == "intersecao_marginal":
            # Pos.relativa | DMT fixa
            for lbl, key, tip in [
                ("Pos. relativa (m):", "pos_relativa",
                 "Posição da interseção/marginal em relação ao início (zero) do eixo A.\n"
                 "Calculada como: CMv_conexão - Est.ini_A.\n"
                 "Pode ser negativa se a interseção estiver antes do início do eixo.\n"
                 "Ex: conexão no CMv 117.740m, Est.ini=116.000m → pos=1.740m"),
                ("DMT lateral (km):", "dmt_fixa",
                 "Distância lateral entre o eixo principal e a interseção/marginal.\n"
                 "Em quilômetros. Sempre somada à distância calculada no eixo.\n"
                 "Ex: 0.300km = 300m de afastamento lateral."),
            ]:
                lbl_w = styled_label(r2, lbl, bg=COR_CARD)
                lbl_w.pack(side="left", padx=(0,4))
                add_tooltip(lbl_w, tip)
                e = styled_entry(r2, vars_rel[key], width=10)
                e.pack(side="left", padx=(0,14))
                add_tooltip(e, tip)

    def _proximo(self):
        from detector_trechos import ParametrosDistribuicao
        from distribuidor2 import ConfigDistribuicao, RelacaoSegmentos

        # Coletar params por ramo
        params_dict = {}
        for ramo, vs in self.params_por_ramo.items():
            try:
                params_dict[ramo] = ParametrosDistribuicao(
                    usar_corte3_interno   = vs["c3i"].get(),
                    aceita_corte3_externo = vs["c3e"].get(),
                    usar_corte2_interno   = vs["c2i"].get(),
                    aceita_corte2_externo = vs["c2e"].get(),
                    vol_min_aterro_c3     = float(vs["vmin"].get()),
                    pct_max_c3            = float(vs["pct"].get()))
            except ValueError:
                messagebox.showwarning("Atenção", f"Verifique os valores de \'{ramo}\'.", parent=self)
                return
        self.estado.params = list(params_dict.values())[0] if len(params_dict)==1 else params_dict

        # Coletar relações
        relacoes = []
        for vr in self.relacoes_dados:
            tipo = vr["tipo"].get()
            ra, rb = vr["ramo_a"].get(), vr["ramo_b"].get()
            if ra == rb:
                messagebox.showwarning("Atenção", "Selecione segmentos diferentes.", parent=self)
                return
            try:
                _rt = vr.get("ramos_todos_vars", {})
                _ramos_todos = [r for r, v in _rt.items() if v.get()] if _rt else []

                if tipo == "pistas_paralelas":
                    rel = RelacaoSegmentos(
                        ramo_a=ra, ramo_b=rb,
                        tipo="pistas_paralelas",
                        estaca_ini_a_m   = float(vr["estaca_ini_a"].get()),
                        estaca_ini_b_m   = float(vr["estaca_ini_b"].get()),
                        deslocamento_a_m = float(vr["deslocamento_a"].get()),
                        deslocamento_b_m = float(vr["deslocamento_b"].get()),
                        afastamento_m    = float(vr["afastamento"].get()),
                        pistas_paralelas = vr.get("pistas_paralelas", tk.BooleanVar()).get(),
                        usar_rodada_interna = vr.get("pistas_paralelas", tk.BooleanVar()).get(),
                        todos            = vr.get("todos", tk.BooleanVar()).get(),
                        ramos_todos      = _ramos_todos,
                    )
                elif tipo == "intersecao_marginal":
                    rel = RelacaoSegmentos(
                        ramo_a=ra, ramo_b=rb,
                        tipo="intersecao_marginal",
                        estaca_ini_a_m = float(vr["estaca_ini_a"].get()) if vr.get("estaca_ini_a") else 0.0,
                        pos_relativa_m = float(vr["pos_relativa"].get()),
                        dmt_fixa_km    = float(vr["dmt_fixa"].get()),
                        todos          = vr.get("todos", tk.BooleanVar()).get(),
                        ramos_todos    = _ramos_todos,
                    )
                else:
                    continue
                relacoes.append(rel)
            except ValueError:
                messagebox.showwarning("Atenção", "Verifique os valores das relações.", parent=self)
                return

        self.estado.config_dist = ConfigDistribuicao(
            tipo_projeto            = self.estado._tipo_projeto,
            usar_dmt_maxima         = self.var_usa_dmt_max.get(),
            dmt_maxima_km           = float(self.var_dmt_max.get()) if self.var_usa_dmt_max.get() else 999.0,
            dmt_cl                  = float(self.var_dmt_cl.get()),
            emprestimo_mais_proximo = True,
            estrategia              = self.var_estrategia.get(),
            usar_encadeamento       = self.var_encadeamento.get(),
            relacoes                = relacoes,
            bota_foras              = self.estado.bota_foras,
            emprestimos             = self.estado.emprestimos)
        self.destroy()
        self.callback_proximo(5)

    def _cancelar(self):
        if messagebox.askokcancel("Sair","Deseja sair?",parent=self):
            self.master.quit()



# ---------------------------------------------------------------------------
# Janela 5 — Bota Fora e Empréstimos
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# JanelaTabelaBFAE — Grid editável tipo planilha para BF e AE
# ---------------------------------------------------------------------------

class JanelaTabelaBFAE(tk.Toplevel):
    """
    Janela de entrada em grid tipo planilha para BF ou AE.
    Suporta Ctrl+V para colar dados do Excel, listas suspensas nas
    colunas Segmento e Eixo ref., e edição célula a célula.
    """

    N_LINHAS_INICIAIS = 20

    def __init__(self, parent, tipo, colunas, listas_suspensas=None,
                 dados_iniciais=None, callback_ok=None, seg_ramos=None):
        """
        tipo: "BF" ou "AE"
        colunas: lista de nomes das colunas
        listas_suspensas: dict {nome_coluna: [opcoes]} para colunas com combo
        dados_iniciais: lista de listas com valores pré-preenchidos
        callback_ok: chamado com lista de listas ao confirmar
        seg_ramos: dict {segmento: [ramos]} para atualização dinâmica do Eixo ref.
        """
        super().__init__(parent)
        self.tipo            = tipo
        self.colunas         = colunas
        self.listas          = listas_suspensas or {}
        self.callback_ok     = callback_ok
        self._seg_ramos      = seg_ramos or {}  # disponível antes de criar linhas
        self.cells           = []
        self.widgets         = []

        cor_titulo = COR_DANGER if tipo == "BF" else COR_ACCENT2
        titulo_txt = f"🗑 Tabela de Bota Fora" if tipo == "BF" else f"⛏ Tabela de Empréstimos"

        self.title(titulo_txt)
        self.configure(bg=COR_BG)
        self.resizable(True, True)
        self.geometry("960x600")
        self.grab_set()

        # Instrução
        tk.Label(self, text=titulo_txt, font=FONTE_SUB,
                 fg=cor_titulo, bg=COR_BG).pack(anchor="w", padx=16, pady=(12,2))
        tk.Label(self,
                 text="Cole dados do Excel com Ctrl+V em qualquer célula.\n"
                      "Navegue com Tab/Shift+Tab e Enter. Segmento e Eixo ref. "
                      "têm lista suspensa mas também aceitam digitação.",
                 font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_BG,
                 justify="left").pack(anchor="w", padx=16, pady=(0,8))

        # Frame principal scrollável
        outer = tk.Frame(self, bg=COR_BG)
        outer.pack(fill="both", expand=True, padx=16, pady=(0,4))

        cv = tk.Canvas(outer, bg=COR_CARD, highlightthickness=0)
        sb_v = tk.Scrollbar(outer, orient="vertical",   command=cv.yview)
        sb_h = tk.Scrollbar(outer, orient="horizontal", command=cv.xview)
        cv.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        sb_v.pack(side="right",  fill="y")
        sb_h.pack(side="bottom", fill="x")
        cv.pack(fill="both", expand=True)

        self.grid_frame = tk.Frame(cv, bg=COR_CARD)
        self.cv_win = cv.create_window((0,0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>",
                             lambda e: cv.configure(scrollregion=cv.bbox("all")))
        self._cv = cv

        # Larguras das colunas
        self._larguras = self._calcular_larguras()

        # Cabeçalho
        hdr = tk.Frame(self.grid_frame, bg=COR_BORDA)
        hdr.grid(row=0, column=0, columnspan=len(self.colunas)+1, sticky="ew")
        tk.Label(hdr, text="#", font=FONTE_SMALL, fg=COR_SUBTEXTO,
                 bg=COR_BORDA, width=3, anchor="center").grid(row=0, column=0, padx=2, pady=3)
        for j, col in enumerate(self.colunas):
            tk.Label(hdr, text=col, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, width=self._larguras[j], anchor="w").grid(
                     row=0, column=j+1, padx=2, pady=3, sticky="w")

        # Criar linhas
        n = max(self.N_LINHAS_INICIAIS,
                len(dados_iniciais) + 5 if dados_iniciais else self.N_LINHAS_INICIAIS)
        for i in range(n):
            vals = dados_iniciais[i] if dados_iniciais and i < len(dados_iniciais) else None
            self._add_linha(i+1, vals)

        # Botões
        btn_frame = tk.Frame(self, bg=COR_BG)
        btn_frame.pack(fill="x", padx=16, pady=8)
        styled_btn(btn_frame, "+ 10 linhas", self._add_10_linhas,
                   COR_BTN, width=12).pack(side="left", padx=(0,6))
        styled_btn(btn_frame, "Limpar tudo", self._limpar,
                   COR_BTN, width=12).pack(side="left", padx=(0,20))
        styled_btn(btn_frame, "✓ Confirmar", self._confirmar,
                   COR_ACCENT, width=14).pack(side="right")
        styled_btn(btn_frame, "Cancelar", self.destroy,
                   COR_CARD, width=10).pack(side="right", padx=(0,8))

        # Bind Ctrl+V global na janela
        self.bind("<Control-v>", self._paste_global)
        self.bind("<Control-V>", self._paste_global)

    def _calcular_larguras(self):
        larguras_padrao = {
            "Nome":            12,
            "CMv":             10,
            "Segmento":        18,
            "Eixo ref.":       16,
            "Pos. rel. (m)":   12,
            "Afastamento (m)": 14,
            "Capacidade (m³)": 14,
            "Volume (m³)":     12,
            "Fh":              6,
        }
        return [larguras_padrao.get(c, 12) for c in self.colunas]

    def _add_linha(self, num, vals=None):
        i = len(self.cells)
        row_vars = []
        row_wgts = []

        # Número da linha
        tk.Label(self.grid_frame, text=str(num), font=FONTE_SMALL,
                 fg=COR_SUBTEXTO, bg=COR_CARD, width=3,
                 anchor="center").grid(row=i+1, column=0, padx=2, pady=1)

        # Índices das colunas Segmento e Eixo ref. nesta tabela
        idx_seg  = self.colunas.index("Segmento")  if "Segmento"  in self.colunas else -1
        idx_eixo = self.colunas.index("Eixo ref.") if "Eixo ref." in self.colunas else -1

        combo_eixo_ref = [None]  # referência mutável para o combo de eixo

        for j, col in enumerate(self.colunas):
            val = (vals[j] if vals and j < len(vals) else "") or ""
            v = tk.StringVar(value=val)
            row_vars.append(v)

            if col in self.listas and self.listas[col]:
                # Para Eixo ref.: usar ramos do segmento desta linha se disponível
                if col == "Eixo ref." and "Segmento" in self.colunas and self._seg_ramos:
                    idx_seg = self.colunas.index("Segmento")
                    seg_val = row_vars[idx_seg].get() if idx_seg < len(row_vars) else ""
                    opcoes  = self._seg_ramos.get(seg_val, self.listas[col])
                else:
                    opcoes = self.listas[col]
                w = ttk.Combobox(self.grid_frame, textvariable=v,
                                 values=opcoes,
                                 width=self._larguras[j],
                                 font=FONTE_SMALL)
                w.configure(style="Dark.TCombobox")
                if val in opcoes:
                    w.set(val)
                elif opcoes and not val:
                    w.set(opcoes[0])
                # Guardar referência ao combo de Eixo ref.
                if col == "Eixo ref.":
                    combo_eixo_ref[0] = w
            else:
                w = tk.Entry(self.grid_frame, textvariable=v,
                             font=FONTE_SMALL, fg=COR_TEXTO,
                             bg=COR_INPUT, relief="flat",
                             insertbackground=COR_TEXTO,
                             width=self._larguras[j])

            w.grid(row=i+1, column=j+1, padx=2, pady=1, sticky="ew")
            w.bind("<Tab>",       lambda e, r=i, c=j: self._nav(r, c, 0, 1))
            w.bind("<Shift-Tab>", lambda e, r=i, c=j: self._nav(r, c, 0, -1))
            w.bind("<Return>",    lambda e, r=i, c=j: self._nav(r, c, 1, 0))
            w.bind("<Down>",      lambda e, r=i, c=j: self._nav(r, c, 1, 0))
            w.bind("<Up>",        lambda e, r=i, c=j: self._nav(r, c, -1, 0))
            row_wgts.append(w)

        # Listener: quando Segmento muda, atualizar opções do Eixo ref.
        if idx_seg >= 0 and idx_eixo >= 0 and combo_eixo_ref[0] is not None:
            v_seg   = row_vars[idx_seg]
            v_eixo  = row_vars[idx_eixo]
            cb_eixo = combo_eixo_ref[0]
            seg_ramos = self._seg_ramos

            def _atualizar_eixo(*args, _v_seg=v_seg, _v_eixo=v_eixo,
                                _cb=cb_eixo, _sr=seg_ramos,
                                _fallback=self.listas.get("Eixo ref.", [])):
                seg_nome = _v_seg.get()
                eixos = _sr.get(seg_nome, _fallback)
                _cb['values'] = eixos
                if eixos and _v_eixo.get() not in eixos:
                    _v_eixo.set(eixos[0])

            v_seg.trace_add("write", _atualizar_eixo)
        elif idx_seg < 0 and idx_eixo >= 0 and combo_eixo_ref[0] is not None:
            # Sem coluna Segmento (distribuição): usar fallback direto dos ramos
            v_eixo  = row_vars[idx_eixo]
            cb_eixo = combo_eixo_ref[0]
            # Tentar pegar ramos do seg_ramos com chave vazia (distribuição)
            eixos_dist = self._seg_ramos.get("", self.listas.get("Eixo ref.", []))
            if eixos_dist:
                cb_eixo['values'] = eixos_dist
                if not v_eixo.get() or v_eixo.get() not in eixos_dist:
                    v_eixo.set(eixos_dist[0])

        self.cells.append(row_vars)
        self.widgets.append(row_wgts)

    def _nav(self, row, col, dr, dc):
        """Navega entre células."""
        nr, nc = row + dr, col + dc
        if nc < 0:
            nc = len(self.colunas) - 1
            nr -= 1
        elif nc >= len(self.colunas):
            nc = 0
            nr += 1
        if nr < 0: nr = 0
        if nr >= len(self.widgets): nr = len(self.widgets) - 1
        self.widgets[nr][nc].focus_set()
        if hasattr(self.widgets[nr][nc], 'select_range'):
            try: self.widgets[nr][nc].select_range(0, 'end')
            except: pass
        return "break"

    def _add_10_linhas(self):
        n = len(self.cells)
        for i in range(10):
            self._add_linha(n + i + 1)

    def _limpar(self):
        for row_vars in self.cells:
            for v in row_vars:
                v.set("")

    def _paste_global(self, event=None):
        """Cola dados do clipboard em formato tabular (TSV do Excel)."""
        try:
            txt = self.clipboard_get()
        except Exception:
            return "break"
        if not txt.strip():
            return "break"

        # Descobrir célula focada para saber onde começar a colar
        focused = self.focus_get()
        start_row, start_col = 0, 0
        for ri, row_wgts in enumerate(self.widgets):
            for ci, w in enumerate(row_wgts):
                if w == focused:
                    start_row, start_col = ri, ci
                    break

        linhas = [l for l in txt.split("\n") if l.strip()]
        for di, linha in enumerate(linhas):
            ri = start_row + di
            # Adicionar linhas se necessário
            while ri >= len(self.cells):
                self._add_linha(len(self.cells) + 1)
            campos = linha.rstrip("\r").split("\t")
            for dj, campo in enumerate(campos):
                ci = start_col + dj
                if ci < len(self.cells[ri]):
                    self.cells[ri][ci].set(campo.strip())
        return "break"

    def _confirmar(self):
        resultado = []
        for row_vars in self.cells:
            vals = [v.get().strip() for v in row_vars]
            # Pular linhas completamente vazias
            if any(v for v in vals):
                resultado.append(vals)
        if self.callback_ok:
            self.callback_ok(resultado)
        self.destroy()



class Janela5BFAuxiliar(JanelaBase):
    """Cadastro de Bota Fora e Empréstimos via tabela editável."""

    COLUNAS_BF = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Capacidade (m³)"]
    COLUNAS_AE = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Capacidade (m³)", "Fh"]

    def __init__(self, master, estado, callback_proximo, callback_voltar):
        super().__init__(master, "Bota Fora e Empréstimos", 860, 500)
        self.estado = estado
        self.callback_proximo = callback_proximo
        self.callback_voltar  = callback_voltar
        self.ramos = list(dict.fromkeys(self.estado.ramos_nomes)) if self.estado.ramos_nomes else []
        self.dados_bf = []  # lista de listas
        self.dados_ae = []
        # Pre-popular dos dados existentes
        for item in self.estado.bota_foras:
            eixo = getattr(item, "eixo_ref", "") or (self.ramos[0] if self.ramos else "")
            self.dados_bf.append([item.nome, item.cmv_label, eixo,
                                  str(item.pos_relativa_m), str(item.afastamento), str(item.capacidade)])
        for item in self.estado.emprestimos:
            eixo = getattr(item, "eixo_ref", "") or (self.ramos[0] if self.ramos else "")
            self.dados_ae.append([item.nome, item.cmv_label, eixo,
                                  str(item.pos_relativa_m), str(item.afastamento),
                                  str(item.capacidade), str(getattr(item, "fh", 1.25))])
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._proximo)

    def _construir(self):
        c = self.conteudo
        styled_label(c, "BOTA FORA E EMPRÉSTIMOS", FONTE_SUB, COR_ACCENT).pack(
            anchor="w", padx=20, pady=10)
        styled_label(c,
            "Clique nos botões abaixo para abrir a tabela de cada tipo.\n"
            "Na tabela você pode colar dados do Excel (Ctrl+V) ou editar célula a célula.",
            cor=COR_SUBTEXTO).pack(anchor="w", padx=20, pady=(0,12))

        paned = tk.Frame(c, bg=COR_BG); paned.pack(fill="x", padx=20, pady=(0,10))

        # Card BF
        card_bf = styled_card(paned)
        card_bf.pack(side="left", fill="x", expand=True, padx=(0,8))
        tk.Label(card_bf, text="🗑  Bota Fora", font=FONTE_SUB,
                 fg=COR_DANGER, bg=COR_CARD).pack(anchor="w", padx=16, pady=(12,4))
        self.lbl_bf = tk.Label(card_bf, text=self._resumo("BF"),
                               font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_CARD)
        self.lbl_bf.pack(anchor="w", padx=16, pady=(0,8))
        styled_btn(card_bf, "📋 Abrir tabela BF",
                   lambda: self._abrir_tabela("BF"),
                   COR_DANGER, width=20).pack(anchor="w", padx=16, pady=(0,16))

        # Card AE
        card_ae = styled_card(paned)
        card_ae.pack(side="left", fill="x", expand=True)
        tk.Label(card_ae, text="⛏  Empréstimos", font=FONTE_SUB,
                 fg=COR_ACCENT2, bg=COR_CARD).pack(anchor="w", padx=16, pady=(12,4))
        self.lbl_ae = tk.Label(card_ae, text=self._resumo("AE"),
                               font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_CARD)
        self.lbl_ae.pack(anchor="w", padx=16, pady=(0,8))
        styled_btn(card_ae, "📋 Abrir tabela AE",
                   lambda: self._abrir_tabela("AE"),
                   COR_ACCENT2, width=20).pack(anchor="w", padx=16, pady=(0,16))

    def _resumo(self, tipo):
        dados = self.dados_bf if tipo == "BF" else self.dados_ae
        n = sum(1 for r in dados if r and r[0].strip())
        return f"{n} item(s) cadastrado(s)" if n > 0 else "Nenhum item cadastrado"

    def _abrir_tabela(self, tipo):
        colunas = self.COLUNAS_BF if tipo == "BF" else self.COLUNAS_AE
        dados   = self.dados_bf   if tipo == "BF" else self.dados_ae
        listas  = {"Eixo ref.": self.ramos}
        # Na distribuição não há múltiplos segmentos — seg_ramos aponta para os ramos do projeto
        # A chave vazia ("") garante que linhas sem segmento usem os ramos do projeto
        seg_ramos_dist = {"": self.ramos}

        def _ok(resultado, t=tipo):
            if t == "BF":
                self.dados_bf = resultado
                self.lbl_bf.config(text=self._resumo("BF"))
            else:
                self.dados_ae = resultado
                self.lbl_ae.config(text=self._resumo("AE"))

        JanelaTabelaBFAE(self, tipo=tipo, colunas=colunas,
                         listas_suspensas=listas,
                         dados_iniciais=dados,
                         callback_ok=_ok,
                         seg_ramos=seg_ramos_dist)

    def _coletar(self, dados, colunas, tipo):
        from distribuidor2 import LocalAuxiliar
        resultado = []
        idx = {c: i for i, c in enumerate(colunas)}
        for row in dados:
            try:
                nome = row[idx["Nome"]].strip() if idx["Nome"] < len(row) else ""
                if not nome: continue
                cmv_lbl = row[idx["CMv"]].strip()      if "CMv"             in idx and idx["CMv"]             < len(row) else ""
                eixo    = row[idx["Eixo ref."]].strip() if "Eixo ref."       in idx and idx["Eixo ref."]       < len(row) else (self.ramos[0] if self.ramos else "")
                pos     = float(row[idx["Pos. rel. (m)"]].replace(",","."))  if idx.get("Pos. rel. (m)", 99) < len(row) else 0.0
                af      = float(row[idx["Afastamento (m)"]].replace(",",".")) if idx.get("Afastamento (m)", 99) < len(row) else 0.0
                cap     = float(row[idx["Capacidade (m³)"]].replace(",",".")) if idx.get("Capacidade (m³)", 99) < len(row) else 0.0
                fh      = float(row[idx["Fh"]].replace(",","."))              if "Fh" in idx and idx["Fh"] < len(row) and row[idx["Fh"]].strip() else 1.25
                resultado.append(LocalAuxiliar(
                    nome=nome, tipo=tipo, capacidade=cap, fh=fh,
                    eixo_ref=eixo, pos_relativa_m=pos, afastamento=af,
                    estaca_m=pos, cmv_label=cmv_lbl,
                ))
            except (ValueError, IndexError):
                pass
        return resultado

    def _proximo(self):
        self.estado.bota_foras  = self._coletar(self.dados_bf, self.COLUNAS_BF, "BF")
        self.estado.emprestimos = self._coletar(self.dados_ae, self.COLUNAS_AE, "AE")
        if self.estado.config_dist:
            self.estado.config_dist.bota_foras  = self.estado.bota_foras
            self.estado.config_dist.emprestimos = self.estado.emprestimos
        self.destroy()
        self.callback_proximo(6)

    def _cancelar(self):
        if messagebox.askokcancel("Sair", "Deseja sair?", parent=self):
            self.master.quit()


# ---------------------------------------------------------------------------
# Janela 6 — Gerar
# ---------------------------------------------------------------------------

class Janela6Restricoes(JanelaBase):
    """Janela de restrições por ramo — bloco independente."""

    def __init__(self, master, estado, callback_proximo, callback_voltar):
        super().__init__(master, "Restrições por Ramo", 900, 700)
        self.estado           = estado
        self.callback_proximo = callback_proximo
        self.callback_voltar  = callback_voltar
        self.vars_bf:   dict  = {}
        self.vars_c1:   dict  = {}
        self.vars_c2:   dict  = {}
        self.vars_c3:   dict  = {}
        self.vars_ae:   dict  = {}
        self.vars_aelbl:dict  = {}
        self.vars_prio: dict  = {}  # prioridade_c3_c2_c1
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._proximo)

    def _construir(self):
        c = self.conteudo
        styled_label(c, "RESTRIÇÕES POR RAMO",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=(10,2))
        styled_label(c,
                     "Configure restrições de corte e aterro por ramo. "
                     "Sem marcação = comportamento padrão.",
                     cor=COR_SUBTEXTO).pack(anchor="w", padx=20, pady=(0,8))

        # Pegar ramos do estado se disponíveis (mais rápido e confiável)
        ramos = []
        if hasattr(self.estado, 'ramos_nomes') and self.estado.ramos_nomes:
            ramos = self.estado.ramos_nomes
        else:
            # Tentar ler dos arquivos
            from DISTRIBUICAO import ConfigLeitura, ler_multiplos_arquivos
            try:
                config = ConfigLeitura(unidade=self.estado.unidade,
                                       em_distancia=self.estado.em_distancia,
                                       dist_estaca=self.estado.dist_estaca,
                                       dist_max_bloco=self.estado.dist_max_bloco,
                                       fatores_hom=self.estado.fatores_hom)
                proj = ler_multiplos_arquivos(self.estado.arquivos, config)
                ramos = [r.nome for r in proj.ramos]
            except Exception as ex:
                print(f"  Aviso Janela6: erro ao ler arquivos: {ex}")
                ramos = []

        # AEs disponíveis
        aes = [f'AE-{i+1}' for i, ae in enumerate(self.estado.emprestimos)
               if ae.valido] if self.estado.emprestimos else []

        # Restrições salvas
        from restricoes_ramo import ConfigRestricoes
        cfg_atual = getattr(self.estado, 'config_restricoes', None) or ConfigRestricoes()

        # Larguras fixas das colunas (em pixels)
        W_RAMO  = 220
        W_CHECK = 70
        W_AE    = 100

        # Container principal — ocupa espaço disponível deixando 50px para botões
        frame_main = tk.Frame(c, bg=COR_BG)
        frame_main.pack(fill="both", expand=True, padx=20, pady=(0,4))

        # Cabeçalho fixo
        hdr = tk.Frame(frame_main, bg=COR_BORDA)
        hdr.pack(fill="x", pady=(0,1))

        def hdr_label(parent, txt, w):
            tk.Label(parent, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, width=0, anchor="center",
                     wraplength=w-4).place(x=0, y=0)

        cols = [
            ("Ramo",         W_RAMO),
            ("Corte→BF",     W_CHECK),
            ("Aceita C1",    W_CHECK),
            ("C2",           W_CHECK),
            ("C3",           W_CHECK),
            ("Prio C3→C1",   W_CHECK),
            ("Usa AE",       W_CHECK),
            ("AE",           W_AE),
        ]
        x = 0
        for txt, w in cols:
            tk.Label(hdr, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, anchor="center",
                     width=w // 8).pack(side="left", padx=2, pady=4)

        # Área com scroll
        frame_sc = tk.Frame(frame_main, bg=COR_CARD)
        frame_sc.pack(fill="both", expand=True)

        cv = tk.Canvas(frame_sc, bg=COR_CARD, highlightthickness=0)
        sb = tk.Scrollbar(frame_sc, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(cv, bg=COR_CARD)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(win_id, width=e.width))

        # Scroll com mouse
        def _scroll(event):
            cv.yview_scroll(int(-1*(event.delta/120)), "units")
        cv.bind_all("<MouseWheel>", _scroll)

        if not ramos:
            styled_label(inner, "Nenhum ramo disponível.",
                         cor=COR_SUBTEXTO).pack(padx=16, pady=8)
            return

        for i, ramo in enumerate(ramos):
            r_atual = cfg_atual.get(ramo)
            bg = COR_CARD if i % 2 == 0 else COR_BORDA
            row = tk.Frame(inner, bg=bg)
            row.pack(fill="x", padx=0, pady=0)

            # Nome do ramo
            tk.Label(row, text=ramo, font=FONTE_SMALL, fg=COR_TEXTO,
                     bg=bg, anchor="w",
                     width=W_RAMO // 8).pack(side="left", padx=(8,4), pady=4)

            # Corte → somente BF — padrão DESMARCADO
            var_bf = tk.BooleanVar(value=r_atual.corte_somente_bf if r_atual else False)
            self.vars_bf[ramo] = var_bf
            tk.Checkbutton(row, variable=var_bf, bg=bg,
                           activebackground=bg, selectcolor="#E74C3C",
                           relief="flat").pack(side="left", padx=W_CHECK//4)

            # Aterro aceita C1/C2/C3 — padrão DESMARCADO (sem restrição)
            var_c1 = tk.BooleanVar(value=r_atual.aterro_aceita_c1 if r_atual else False)
            var_c2 = tk.BooleanVar(value=r_atual.aterro_aceita_c2 if r_atual else False)
            var_c3 = tk.BooleanVar(value=r_atual.aterro_aceita_c3 if r_atual else False)
            self.vars_c1[ramo] = var_c1
            self.vars_c2[ramo] = var_c2
            self.vars_c3[ramo] = var_c3
            for var in [var_c1, var_c2, var_c3]:
                tk.Checkbutton(row, variable=var, bg=bg,
                               activebackground=bg, selectcolor=COR_ACCENT,
                               relief="flat").pack(side="left", padx=W_CHECK//4)

            # Prioridade C3→C2→C1 — padrão DESMARCADO
            var_prio = tk.BooleanVar(
                value=getattr(r_atual, 'prioridade_c3_c2_c1', False) if r_atual else False)
            self.vars_prio[ramo] = var_prio
            tk.Checkbutton(row, variable=var_prio, bg=bg,
                           activebackground=bg, selectcolor="#F39C12",
                           relief="flat").pack(side="left", padx=W_CHECK//4)

            # Usa AE — padrão DESMARCADO
            var_ae = tk.BooleanVar(value=r_atual.aterro_usa_ae if r_atual else False)
            self.vars_ae[ramo] = var_ae
            tk.Checkbutton(row, variable=var_ae, bg=bg,
                           activebackground=bg, selectcolor=COR_ACCENT,
                           relief="flat").pack(side="left", padx=W_CHECK//4)

            # Seleção do AE
            var_aelbl = tk.StringVar(value=r_atual.ae_label if r_atual else
                                     (aes[0] if aes else ""))
            self.vars_aelbl[ramo] = var_aelbl
            if aes:
                styled_combo(row, var_aelbl, aes, width=10).pack(side="left", padx=4)
            else:
                tk.Label(row, text="(sem AE)", font=FONTE_SMALL,
                         fg=COR_SUBTEXTO, bg=bg).pack(side="left", padx=4)

    def _cancelar(self):
        if messagebox.askokcancel("Sair", "Deseja sair?", parent=self):
            self.master.quit()

    def _proximo(self):
        from restricoes_ramo import ConfigRestricoes, RestricoesRamo
        cfg = ConfigRestricoes()
        for ramo in self.vars_bf:
            r = RestricoesRamo(
                ramo                = ramo,
                corte_somente_bf    = self.vars_bf[ramo].get(),
                aterro_aceita_c1    = self.vars_c1[ramo].get(),
                aterro_aceita_c2    = self.vars_c2[ramo].get(),
                aterro_aceita_c3    = self.vars_c3[ramo].get(),
                aterro_usa_ae       = self.vars_ae[ramo].get(),
                ae_label            = self.vars_aelbl[ramo].get()
                                      if ramo in self.vars_aelbl else "",
                prioridade_c3_c2_c1 = self.vars_prio[ramo].get()
                                      if ramo in self.vars_prio else False,
            )
            # Só salva se tiver alguma restrição configurada
            if (r.corte_somente_bf or r.aterro_aceita_c1 or
                    r.aterro_aceita_c2 or r.aterro_aceita_c3 or
                    r.aterro_usa_ae or r.prioridade_c3_c2_c1):
                cfg.restricoes.append(r)
        self.estado.config_restricoes = cfg if cfg.restricoes else None
        self.destroy()
        self.callback_proximo(7)


class Janela7Gerar(JanelaBase):
    def __init__(self, master, estado, callback_voltar):
        super().__init__(master, "Gerar", 860, 750)
        self.estado = estado
        self.callback_voltar = callback_voltar
        self._resultados   = []   # ResultadoDeteccao — preenchido em _gerar_worker
        self._caminho_json = ""   # caminho do JSON gerado
        self._btn_pre      = None
        self._btn_pos      = None
        self._construir()
        self.adicionar_botoes(btn_cancelar=self._cancelar,
                              btn_voltar=callback_voltar,
                              btn_proximo=self._gerar,
                              texto_proximo="⚡ Gerar Excel + JSON")
        # Botão pré-distribuição (sempre ativo)
        self._btn_pre = styled_btn(
            self._inner_rodape, "📈 Brückner Pré",
            self._abrir_pre, cor="#F39C12", width=14)
        self._btn_pre.pack(side="left", padx=(8, 0))
        # Botão pós-distribuição (habilita após gerar ou se JSON já carregado)
        self._btn_pos = styled_btn(
            self._inner_rodape, "📈 Brückner Pós",
            self._abrir_pos, cor=COR_ACCENT, width=14)
        self._btn_pos.pack(side="left", padx=(4, 0))
        # Habilitar se JSON já disponível (projeto carregado)
        if self.estado.caminho_json and os.path.isfile(self.estado.caminho_json):
            self._btn_pos.config(state="normal")
        else:
            self._btn_pos.config(state="disabled")

    def _construir(self):
        c = self.conteudo
        styled_label(c, "GERAR DISTRIBUIÇÃO",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)

        card = styled_card(c); card.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(card, text="Resumo do Projeto", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))

        p = self.estado.params
        if isinstance(p, dict):
            usa_c3 = any(v.usar_corte3_interno for v in p.values())
            usa_c2 = any(v.usar_corte2_interno for v in p.values())
        elif p:
            usa_c3 = getattr(p, "usar_corte3_interno", False)
            usa_c2 = getattr(p, "usar_corte2_interno", False)
        else:
            usa_c3 = usa_c2 = False

        info = [
            ("Projeto:",     self.estado.nome or "-"),
            ("Arquivos:",    f"{len(self.estado.arquivos)} arquivo(s)"),
            ("Usar C3:",     "Sim" if usa_c3 else "Não"),
            ("Usar C2:",     "Sim" if usa_c2 else "Não"),
            ("Estratégia:",  self.estado.config_dist.estrategia if self.estado.config_dist else "-"),
            ("Bota fora:",   f"{len(self.estado.bota_foras)} cadastrado(s)"),
            ("Empréstimos:", f"{len(self.estado.emprestimos)} cadastrado(s)"),
        ]
        grid = tk.Frame(card, bg=COR_CARD); grid.pack(fill="x", padx=16, pady=(0,10))
        for i, (lbl, val) in enumerate(info):
            r = i // 2; cl = (i%2)*2
            tk.Label(grid, text=lbl, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_CARD, anchor="e", width=14
                     ).grid(row=r, column=cl, padx=(0,4), pady=3, sticky="e")
            tk.Label(grid, text=str(val), font=FONTE_SMALL, fg="#FFFFFF",
                     bg=COR_CARD, anchor="w"
                     ).grid(row=r, column=cl+1, padx=(0,20), pady=3, sticky="w")

        card2 = styled_card(c); card2.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(card2, text="Arquivo de Saída", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))
        r1 = tk.Frame(card2, bg=COR_CARD); r1.pack(fill="x", padx=16, pady=4)
        styled_label(r1, "Nome (sem extensão):", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_nome_saida = tk.StringVar(value=self.estado.nome or "Distribuicao")
        styled_entry(r1, self.var_nome_saida, width=30).pack(side="left")
        r2 = tk.Frame(card2, bg=COR_CARD); r2.pack(fill="x", padx=16, pady=(0,10))
        styled_label(r2, "Pasta de saída:", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_pasta = tk.StringVar(value=self._pasta_padrao())
        styled_entry(r2, self.var_pasta, width=40).pack(side="left", padx=(0,8))
        styled_btn(r2, "...", self._sel_pasta, cor=COR_BTN, width=3).pack(side="left")

        card3 = styled_card(c); card3.pack(fill="both", expand=True, padx=20, pady=(0,8))
        tk.Label(card3, text="Log de execução", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))
        self.txt_log = tk.Text(card3, font=FONTE_MONO, fg=COR_TEXTO,
                               bg=COR_INPUT, height=8, relief="flat",
                               state="disabled", wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0,12))

    def _pasta_padrao(self):
        if self.estado.arquivos:
            return os.path.dirname(self.estado.arquivos[0]["caminho"])
        return os.path.expanduser("~")

    def _sel_pasta(self):
        p = filedialog.askdirectory(parent=self)
        if p: self.var_pasta.set(p)

    def _log(self, msg):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", msg+"\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")
        self.update()

    def _gerar(self):
        nome  = self.var_nome_saida.get().strip()
        pasta = self.var_pasta.get().strip()
        if not nome:
            messagebox.showwarning("Atenção","Informe o nome do arquivo.", parent=self)
            return
        if not pasta or not os.path.isdir(pasta):
            messagebox.showwarning("Atenção","Pasta de saída inválida.", parent=self)
            return

        # Desabilitar botões durante o processamento para evitar cliques duplos
        for w in self._inner_rodape.winfo_children():
            try: w.config(state="disabled")
            except Exception: pass

        import threading
        t = threading.Thread(target=self._gerar_worker,
                             args=(nome, pasta), daemon=True)
        t.start()

    def _gerar_worker(self, nome, pasta):
        caminho_excel = os.path.join(pasta, f"{nome}.xlsx")
        caminho_json  = os.path.join(pasta, f"{nome}.json")

        def reabilitar():
            for w in self._inner_rodape.winfo_children():
                try: w.config(state="normal")
                except Exception: pass

        try:
            self._log("Iniciando distribuição...")
            if hasattr(self.estado, "_resultado_carregado") and not self.estado.config_restricoes:
                dados = self.estado._resultado_carregado
                resultados = dados["resultados_deteccao"]
                resultado  = dados["resultado_dist"]
                projeto    = None  # estacas não disponíveis ao carregar JSON
                self._log("Projeto carregado do JSON — regenerando Excel...")
            else:
                from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
                from detector_trechos import detectar_trechos
                from distribuidor2 import distribuir

                config_leitura = ConfigLeitura(
                    unidade=self.estado.unidade,
                    em_distancia=self.estado.em_distancia,
                    dist_estaca=self.estado.dist_estaca,
                    fatores_hom=self.estado.fatores_hom)

                self._log(f"Lendo {len(self.estado.arquivos)} arquivo(s)...")
                projeto = ler_multiplos_arquivos(self.estado.arquivos, config_leitura)

                self._log("Detectando trechos...")
                resultados = []
                _params = self.estado.params
                for ramo in projeto.ramos:
                    p = _params.get(ramo.nome, list(_params.values())[0]) \
                        if isinstance(_params, dict) else _params
                    res = detectar_trechos(ramo, self.estado.mapeamento, p,
                                           unidade=self.estado.unidade,
                                           restricoes=self.estado.config_restricoes)
                    resultados.append(res)
                    self._log(f"  {ramo.nome}: {len(res.trechos)} trechos")

                self._log("Executando distribuição (Stepping-Stone)...")
                resultado = distribuir(resultados, self.estado.mapeamento,
                                       _params, self.estado.config_dist,
                                       restricoes=self.estado.config_restricoes)
                self._log(f"  Custo: {resultado.custo_total:,.2f} km·m³"
                          f" | Iterações: {resultado.iteracoes}")
                # Guardar para Brückner Pré
                self._resultados = resultados

            self._log("Gerando Excel...")
            from gerador_excel import gerar_excel
            gerar_excel(resultado, resultados, caminho_excel, nome,
                        fatores_hom=self.estado.fatores_hom,
                        mapeamento=self.estado.mapeamento,
                        projeto=projeto,
                        restricoes=self.estado.config_restricoes)
            self._log(f"  ✓ Excel: {caminho_excel}")

            self._log("Salvando JSON...")
            from projeto_json import salvar_projeto
            from DISTRIBUICAO import ConfigLeitura
            caminho_json_real = salvar_projeto(
                caminho_json, nome, self.estado.arquivos,
                ConfigLeitura(unidade=self.estado.unidade,
                              em_distancia=self.estado.em_distancia,
                              dist_estaca=self.estado.dist_estaca,
                              dist_max_bloco=self.estado.dist_max_bloco,
                              fatores_hom=self.estado.fatores_hom),
                self.estado.mapeamento, self.estado.params,
                self.estado.config_dist, resultados, resultado,
                caminho_excel=caminho_excel,
                config_restricoes=self.estado.config_restricoes)
            # Usar o caminho real gerado (pode ter sufixo _vN)
            caminho_json = caminho_json_real or caminho_json
            self._log(f"  ✓ JSON: {caminho_json}")
            self._log("\n✅ Concluído com sucesso!")

            if resultado.alertas:
                self._log("\n⚠ Alertas:")
                for a in resultado.alertas:
                    self._log(f"  {a}")

            # Guardar caminho para Brückner Pós
            self._caminho_json = os.path.normpath(caminho_json)
            self.estado.caminho_json = os.path.normpath(caminho_json)

            def _habilitar_pos():
                reabilitar()
                if self._btn_pos:
                    self._btn_pos.config(state="normal")

            self.after(0, _habilitar_pos)
            self.after(0, lambda: messagebox.showinfo(
                "Sucesso!",
                f"Excel: {os.path.basename(caminho_excel)}\n"
                f"JSON:  {os.path.basename(caminho_json)}",
                parent=self))

        except Exception as ex:
            import traceback
            tb = traceback.format_exc()
            self._log(f"\n❌ Erro: {ex}")
            self._log(tb)
            self.after(0, reabilitar)
            self.after(0, lambda: messagebox.showerror("Erro", str(ex), parent=self))

    def _abrir_pre(self):
        """Abre o Diagrama de Massas pré-distribuição."""
        if self._resultados:
            from bruckner_viz import abrir_pre_distribuicao
            abrir_pre_distribuicao(self._resultados, self.estado.config_dist, self)
            return
        try:
            from bruckner_viz import abrir_pre_distribuicao
            from DISTRIBUICAO import ler_multiplos_arquivos, ConfigLeitura
            from detector_trechos import detectar_trechos
            if not self.estado.arquivos:
                messagebox.showwarning("Atenção",
                    "Nenhum arquivo carregado.", parent=self)
                return
            config_leitura = ConfigLeitura(
                unidade=self.estado.unidade,
                em_distancia=self.estado.em_distancia,
                dist_estaca=self.estado.dist_estaca,
                fatores_hom=self.estado.fatores_hom)
            projeto = ler_multiplos_arquivos(self.estado.arquivos, config_leitura)
            _params = self.estado.params
            resultados = []
            for ramo in projeto.ramos:
                p = (_params.get(ramo.nome, list(_params.values())[0])
                     if isinstance(_params, dict) else _params)
                res = detectar_trechos(ramo, self.estado.mapeamento, p,
                                       unidade=self.estado.unidade)
                resultados.append(res)
            self._resultados = resultados
            abrir_pre_distribuicao(resultados, self.estado.config_dist, self)
        except Exception as ex:
            import traceback
            messagebox.showerror("Erro", f"{ex}\n\n{traceback.format_exc()}",
                                 parent=self)

    def _abrir_pos(self):
        """Abre o Diagrama de Massas pós-distribuição."""
        from bruckner_viz import abrir_pos_distribuicao
        caminho = self._caminho_json or self.estado.caminho_json
        if caminho:
            caminho = os.path.normpath(caminho)
        if not caminho:
            messagebox.showinfo("Atenção",
                "Gere o Excel/JSON primeiro.", parent=self)
            return
        abrir_pos_distribuicao(caminho, self)

    def _cancelar(self):
        if messagebox.askokcancel("Sair","Deseja sair?",parent=self):
            self.master.quit()


# ---------------------------------------------------------------------------
# Controlador principal
# ---------------------------------------------------------------------------

class JanelaRedistribuicao(JanelaBase):
    """
    Janela de redistribuição entre segmentos — v2.
    Usa RelacaoSegmento com extensao + deslocamento + afastamento.
    Stepping-Stone global: BFs de todos os segmentos vs déficits de todos.
    """

    def __init__(self, master):
        super().__init__(master, "Redistribuição entre Segmentos", 980, 780)
        self.segmentos = []
        self.relacoes  = []
        self._jsons_redistribuidos = []   # caminhos dos JSONs gerados
        self._construir()
        self.adicionar_botoes(
            btn_cancelar=self.destroy,
            btn_proximo=self._redistribuir,
            texto_proximo="⚡ Redistribuir")
        # Botão Brückner pós-redistribuição (habilita após redistribuir)
        self._btn_bruckner = styled_btn(
            self._inner_rodape, "📈 Brückner Pós-redist",
            self._abrir_bruckner, cor=COR_ACCENT2, width=20)
        self._btn_bruckner.pack(side="left", padx=(8, 0))
        self._btn_bruckner.config(state="disabled")

    def _construir(self):
        c = self.conteudo
        styled_label(c, "REDISTRIBUIÇÃO ENTRE SEGMENTOS",
                     FONTE_SUB, COR_ACCENT).pack(anchor="w", padx=20, pady=10)
        styled_label(c,
                     "Selecione os JSONs e defina a relação espacial entre eles.\n"
                     "O Stepping-Stone analisa todos os BFs e déficits globalmente.",
                     cor=COR_SUBTEXTO).pack(anchor="w", padx=20, pady=(0,10))

        # Card segmentos
        card1 = styled_card(c); card1.pack(fill="x", padx=20, pady=(0,8))
        tk.Label(card1, text="📂  Segmentos (JSONs)", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,4))

        hdr = tk.Frame(card1, bg=COR_BORDA); hdr.pack(fill="x", padx=8, pady=(0,2))
        for txt, w, tip in [
            ("Segmento", 26, "Nome do segmento carregado."),
            ("BF disponível", 20, "Volume em bota-fora que entra na redistribuição."),
            ("Déficit", 14, "Volume de aterro sem material disponível."),
            ("Ramos", 18, "Ramos do segmento."),
        ]:
            lbl = tk.Label(hdr, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                           bg=COR_BORDA, width=w, anchor="w")
            lbl.pack(side="left", padx=4, pady=3)
            if tip: add_tooltip(lbl, tip)

        self.frame_segs = tk.Frame(card1, bg=COR_CARD)
        self.frame_segs.pack(fill="x", padx=8, pady=2)

        btn_row = tk.Frame(card1, bg=COR_CARD); btn_row.pack(anchor="w", padx=16, pady=8)
        styled_btn(btn_row, "+ Adicionar JSON", self._adicionar_json,
                   cor=COR_ACCENT, width=16).pack(side="left", padx=(0,8))
        styled_btn(btn_row, "📂 Carregar sessão", self._carregar_sessao,
                   cor=COR_BTN, width=18).pack(side="left")

        # Card relações segmento↔segmento
        card2 = styled_card(c); card2.pack(fill="both", expand=True, padx=20, pady=(0,8))
        tk.Label(card2, text="🔗  Posicionamento entre Segmentos", font=FONTE_SUB,
                 fg=COR_TEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(10,2))
        styled_label(card2,
                     "Defina onde cada segmento está posicionado em relação ao outro.\n"
                     "A ordem A→B indica que A vem antes de B fisicamente.",
                     cor=COR_SUBTEXTO, bg=COR_CARD).pack(anchor="w", padx=16, pady=(0,4))

        styled_btn(card2, "+ Adicionar Relação", self._adicionar_relacao,
                   cor=COR_ACCENT2, width=18).pack(anchor="w", padx=16, pady=(0,4))

        frame_sc = tk.Frame(card2, bg=COR_CARD)
        frame_sc.pack(fill="both", expand=True, padx=8, pady=(0,8))
        cv = tk.Canvas(frame_sc, bg=COR_CARD, highlightthickness=0)
        sb = tk.Scrollbar(frame_sc, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        self.frame_rels = tk.Frame(cv, bg=COR_CARD)
        cv.create_window((0,0), window=self.frame_rels, anchor="nw")
        self.frame_rels.bind("<Configure>",
                             lambda e: cv.configure(scrollregion=cv.bbox("all")))

        # Cards BF/AE movidos para cada linha de segmento (botões 🗑 BF e ⛏ AE)
        # Compatibilidade: manter atributos para não quebrar código existente
        self.dados_bf_redist = []
        self.dados_ae_redist = []
        # Pasta saída
        card3 = styled_card(c); card3.pack(fill="x", padx=20, pady=(0,8))
        r = tk.Frame(card3, bg=COR_CARD); r.pack(fill="x", padx=16, pady=10)
        styled_label(r, "Pasta de saída:", bg=COR_CARD).pack(side="left", padx=(0,8))
        self.var_pasta = tk.StringVar(value=os.path.expanduser("~"))
        styled_entry(r, self.var_pasta, width=40).pack(side="left", padx=(0,8))
        styled_btn(r, "...", self._sel_pasta, cor=COR_BTN, width=3).pack(side="left")

    # ------------------------------------------------------------------ #
    # Segmentos                                                            #
    # ------------------------------------------------------------------ #

    def _adicionar_json(self):
        from redistribuicao import carregar_segmento
        import json as _json
        path = filedialog.askopenfilename(
            title="Selecionar JSON do segmento",
            filetypes=[("JSON","*.json"),("Todos","*.*")], parent=self)
        if not path: return
        # Verificar se é uma sessão de redistribuição
        try:
            with open(path, 'r', encoding='utf-8') as _f:
                _d = _json.load(_f)
            if _d.get('tipo') == 'sessao_redistribuicao':
                messagebox.showinfo("Sessão detectada",
                    "Este arquivo é uma sessão de redistribuição.\n"
                    "Use o botão 'Carregar sessão' para carregá-lo.", parent=self)
                return
        except Exception:
            pass
        try:
            seg = carregar_segmento(path)
            self.segmentos.append(seg)
            self._add_linha_seg(seg)
        except Exception as ex:
            messagebox.showerror("Erro ao carregar JSON", str(ex), parent=self)

    def _add_linha_seg(self, seg):
        row = tk.Frame(self.frame_segs, bg=COR_CARD)
        row.pack(fill="x", pady=2)
        vol_bf    = sum(b["vol_disponivel"] for b in seg.bota_foras)
        vol_ae    = sum(d["vol_deficit"]    for d in seg.deficits)
        ramos_txt = ", ".join(seg.ramos[:3]) + (f" +{len(seg.ramos)-3}" if len(seg.ramos)>3 else "")
        tk.Label(row, text=seg.nome,       font=FONTE_SMALL, fg=COR_TEXTO,   bg=COR_CARD, width=20, anchor="w").pack(side="left", padx=4)
        tk.Label(row, text=f"{vol_bf:,.0f} m³", font=FONTE_SMALL, fg=COR_ACCENT2 if vol_bf>0 else COR_SUBTEXTO, bg=COR_CARD, width=14, anchor="w").pack(side="left")
        tk.Label(row, text=f"{vol_ae:,.0f} m³", font=FONTE_SMALL, fg=COR_DANGER if vol_ae>0 else COR_SUBTEXTO, bg=COR_CARD, width=12, anchor="w").pack(side="left")
        tk.Label(row, text=ramos_txt,         font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_CARD, width=12, anchor="w").pack(side="left")
        # Botões BF e AE por segmento — sem coluna Segmento na tabela
        tk.Button(row, text="🗑 BF", font=FONTE_SMALL, fg=COR_DANGER,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=lambda s=seg: self._abrir_tabela_seg(s, "BF")).pack(side="left", padx=2)
        tk.Button(row, text="⛏ AE", font=FONTE_SMALL, fg=COR_ACCENT2,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=lambda s=seg: self._abrir_tabela_seg(s, "AE")).pack(side="left", padx=2)
        tk.Button(row, text="⚙ Ramos", font=FONTE_SMALL, fg=COR_ACCENT2,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=lambda s=seg: self._config_ramos(s)).pack(side="left", padx=2)
        def remover(s=seg, r=row):
            self.segmentos.remove(s); r.destroy()
        tk.Button(row, text="✕", font=FONTE_SMALL, fg=COR_DANGER, bg=COR_CARD,
                  activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=remover).pack(side="left", padx=2)

    def _config_ramos(self, seg):
        """Janela para configurar quais ramos aceitam C2/C3 na redistribuição."""
        win = tk.Toplevel(self)
        win.title(f"Configurar ramos — {seg.nome}")
        win.configure(bg=COR_BG)
        win.geometry("520x480")
        win.grab_set()

        tk.Label(win, text=f"Ramos de {seg.nome}", font=FONTE_SUB,
                 fg=COR_ACCENT, bg=COR_BG).pack(anchor="w", padx=16, pady=(12,4))
        tk.Label(win,
                 text="Marque C2/C3 nos ramos que devem RECEBER essas categorias\n"
                      "na redistribuição, mesmo que não estejam marcados na distribuição.\n"
                      "Ramos com Prioridade já configurada são tratados automaticamente.",
                 font=FONTE_SMALL, fg=COR_SUBTEXTO, bg=COR_BG,
                 justify="left", wraplength=480).pack(anchor="w", padx=16, pady=(0,8))

        # Cabeçalho
        hdr = tk.Frame(win, bg=COR_BORDA); hdr.pack(fill="x", padx=16, pady=(0,2))
        for txt, w in [("Ramo", 28), ("Aceita C2", 10), ("Aceita C3", 10), ("Prio (info)", 10)]:
            tk.Label(hdr, text=txt, font=FONTE_SMALL, fg=COR_SUBTEXTO,
                     bg=COR_BORDA, width=w, anchor="w").pack(side="left", padx=4, pady=3)

        # Canvas scrollável
        frame_sc = tk.Frame(win, bg=COR_CARD); frame_sc.pack(fill="both", expand=True, padx=16)
        cv = tk.Canvas(frame_sc, bg=COR_CARD, highlightthickness=0)
        sb = tk.Scrollbar(frame_sc, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); cv.pack(fill="both", expand=True)
        inner = tk.Frame(cv, bg=COR_CARD)
        cv.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        vars_c2 = {}; vars_c3 = {}

        # Ramos com prioridade (só informativo)
        ramos_prio = set()
        for d in seg.deficits:
            if d.get('prioridade_c3_c2_c1', False):
                ramos_prio.add(d['ramo'])

        for ramo in seg.ramos:
            cfg = seg.config_ramos.get(ramo, {})
            prio = ramo in ramos_prio

            bg = COR_CARD if seg.ramos.index(ramo) % 2 == 0 else COR_PAINEL
            row = tk.Frame(inner, bg=bg); row.pack(fill="x", pady=1)

            tk.Label(row, text=ramo[:28], font=FONTE_SMALL, fg=COR_TEXTO,
                     bg=bg, width=28, anchor="w").pack(side="left", padx=4)

            v2 = tk.BooleanVar(value=cfg.get('aceita_c2', False))
            v3 = tk.BooleanVar(value=cfg.get('aceita_c3', False))
            vars_c2[ramo] = v2
            vars_c3[ramo] = v3

            state = "disabled" if prio else "normal"
            tk.Checkbutton(inner if False else row, variable=v2,
                           bg=bg, activebackground=bg, selectcolor=COR_ACCENT,
                           relief="flat", state=state,
                           width=9).pack(side="left", padx=4)
            tk.Checkbutton(row, variable=v3,
                           bg=bg, activebackground=bg, selectcolor=COR_ACCENT,
                           relief="flat", state=state,
                           width=9).pack(side="left", padx=4)

            prio_txt = "✅ Prio" if prio else ""
            tk.Label(row, text=prio_txt, font=FONTE_SMALL,
                     fg=COR_ACCENT2, bg=bg, width=10).pack(side="left")

        def _salvar():
            seg.config_ramos = {}
            for ramo in seg.ramos:
                c2 = vars_c2[ramo].get()
                c3 = vars_c3[ramo].get()
                if c2 or c3:
                    seg.config_ramos[ramo] = {'aceita_c2': c2, 'aceita_c3': c3}
            win.destroy()

        btn_f = tk.Frame(win, bg=COR_BG); btn_f.pack(fill="x", padx=16, pady=8)
        styled_btn(btn_f, "✓ Salvar", _salvar, COR_ACCENT, width=12).pack(side="right")
        styled_btn(btn_f, "Cancelar", win.destroy, COR_BTN, width=10).pack(side="right", padx=(0,8))

    # ------------------------------------------------------------------ #
    # Relações                                                             #
    # ------------------------------------------------------------------ #

    def _adicionar_relacao(self):
        if len(self.segmentos) < 2:
            messagebox.showwarning("Atenção","Adicione pelo menos 2 segmentos primeiro.", parent=self)
            return
        self._criar_rel_frame()

    def _criar_rel_frame(self, dados=None):
        """Cria frame de relação segmento↔segmento com novo modelo."""
        nomes = [s.nome for s in self.segmentos]

        frame = tk.Frame(self.frame_rels, bg=COR_CARD,
                         highlightthickness=1, highlightbackground=COR_BORDA)
        frame.pack(fill="x", pady=3, padx=2)

        def fv(key, default="0"):
            return str(dados.get(key, default)) if dados else default

        rd = {
            "frame":         frame,
            "seg_a":         tk.StringVar(value=dados["seg_a"] if dados else nomes[0]),
            "seg_b":         tk.StringVar(value=dados["seg_b"] if dados else (nomes[1] if len(nomes)>1 else nomes[0])),
            "extensao_a":    tk.StringVar(value=fv("extensao_a_m")),
            "extensao_b":    tk.StringVar(value=fv("extensao_b_m")),
            "deslocamento":  tk.StringVar(value=fv("deslocamento_m")),
            "afastamento":   tk.StringVar(value=fv("afastamento_m")),
            "usar_c1":       tk.BooleanVar(value=dados.get("usar_c1", True)  if dados else True),
            "usar_c2":       tk.BooleanVar(value=dados.get("usar_c2", False) if dados else False),
            "usar_c3":       tk.BooleanVar(value=dados.get("usar_c3", False) if dados else False),
        }
        self.relacoes.append(rd)

        # Linha 1: Seg A → Seg B
        r1 = tk.Frame(frame, bg=COR_CARD); r1.pack(fill="x", padx=8, pady=(6,2))

        styled_label(r1, "A (vem antes):", bg=COR_CARD).pack(side="left", padx=(0,4))
        combo_a = styled_combo(r1, rd["seg_a"], nomes, width=18)
        combo_a.pack(side="left", padx=(0,8))
        add_tooltip(combo_a,
                    "Segmento que vem ANTES fisicamente.\n"
                    "A ordem A→B define quem está a montante.")

        styled_label(r1, "→  B (vem depois):", bg=COR_CARD).pack(side="left", padx=(0,4))
        combo_b = styled_combo(r1, rd["seg_b"], nomes, width=18)
        combo_b.pack(side="left", padx=(0,16))
        add_tooltip(combo_b,
                    "Segmento que vem DEPOIS fisicamente.\n"
                    "O início de B é posicionado após o final de A + deslocamento.")

        tk.Button(r1, text="✕ Remover", font=FONTE_SMALL, fg=COR_DANGER,
                  bg=COR_CARD, activebackground=COR_CARD, relief="flat", cursor="hand2",
                  command=lambda f=frame, d=rd: self._remover_rel(f, d)
                  ).pack(side="right", padx=4)

        # Linha 2: Parâmetros de posicionamento
        r2 = tk.Frame(frame, bg=COR_CARD); r2.pack(fill="x", padx=8, pady=(2,2))

        for lbl, key, tip, w in [
            ("Extensão A (m):", "extensao_a",
             "Extensão total do segmento A em metros.\n"
             "Passe o mouse sobre o campo para ver o tooltip.\n"
             "Ex: segmento de 5km → 5000m",
             10),
            ("Extensão B (m):", "extensao_b",
             "Extensão total do segmento B em metros.",
             10),
            ("Deslocamento (m):", "deslocamento",
             "Distância entre o final de A e o início de B.\n"
             "0 = B começa exatamente onde A termina.\n"
             "Positivo = há um gap entre eles.\n"
             "Negativo = B começa antes do final de A (sobreposição).",
             10),
            ("Afastamento lateral (m):", "afastamento",
             "Distância lateral entre os eixos dos dois segmentos.\n"
             "0 = no mesmo eixo. Ex: 22m entre pistas paralelas.",
             8),
        ]:
            lbl_w = styled_label(r2, lbl, bg=COR_CARD)
            lbl_w.pack(side="left", padx=(0,4))
            add_tooltip(lbl_w, tip)
            e = styled_entry(r2, rd[key], width=w)
            e.pack(side="left", padx=(0,12))
            add_tooltip(e, tip)

        # Linha 3: Materiais permitidos
        r3 = tk.Frame(frame, bg=COR_CARD); r3.pack(fill="x", padx=8, pady=(2,8))
        styled_label(r3, "Materiais permitidos:", bg=COR_CARD).pack(side="left", padx=(0,8))
        for txt, key, tip in [
            ("C1", "usar_c1", "Incluir corte de 1ª categoria na redistribuição."),
            ("C2", "usar_c2", "Incluir corte de 2ª categoria na redistribuição."),
            ("C3", "usar_c3", "Incluir corte de 3ª categoria na redistribuição."),
        ]:
            cb = tk.Checkbutton(r3, text=txt, variable=rd[key],
                                font=FONTE_SMALL, fg=COR_TEXTO, bg=COR_CARD,
                                activebackground=COR_CARD, selectcolor="#E74C3C",
                                relief="flat")
            cb.pack(side="left", padx=6)
            add_tooltip(cb, tip)

    def _remover_rel(self, frame, rd):
        frame.destroy()
        if rd in self.relacoes: self.relacoes.remove(rd)

    def _abrir_tabela_seg(self, seg, tipo):
        """Abre tabela BF/AE fixada no segmento — sem coluna Segmento."""
        COLUNAS_BF = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Volume (m³)"]
        COLUNAS_AE = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Volume (m³)", "Fh"]
        colunas = COLUNAS_BF if tipo == "BF" else COLUNAS_AE
        # Dados existentes do segmento
        if not hasattr(seg, '_dados_bf'): seg._dados_bf = []
        if not hasattr(seg, '_dados_ae'): seg._dados_ae = []
        dados = seg._dados_bf if tipo == "BF" else seg._dados_ae
        listas = {"Eixo ref.": seg.ramos}

        def _ok(resultado, s=seg, t=tipo):
            # Filtrar linhas que realmente têm Nome preenchido
            resultado_valido = [r for r in resultado if r and r[0].strip()]
            dados_atuais = s._dados_bf if t == "BF" else s._dados_ae
            # Só atualiza se há dados válidos OU se não havia dados antes
            if resultado_valido:
                if t == "BF":
                    s._dados_bf = resultado_valido
                else:
                    s._dados_ae = resultado_valido
            elif not dados_atuais:
                # Sem dados antes e sem dados novos — zera normalmente
                if t == "BF": s._dados_bf = []
                else:          s._dados_ae = []
            # Se resultado_valido vazio mas havia dados → preserva dados existentes

        JanelaTabelaBFAE(self, tipo=tipo, colunas=colunas,
                         listas_suspensas=listas,
                         dados_iniciais=dados,
                         callback_ok=_ok,
                         seg_ramos={})

    def _abrir_tabela_redist(self, tipo):
        """Abre JanelaTabelaBFAE para BF ou AE da redistribuição."""
        colunas = self._colunas_bf_r if tipo == "BF" else self._colunas_ae_r
        dados   = self.dados_bf_redist if tipo == "BF" else self.dados_ae_redist
        nomes_segs = [s.nome for s in self.segmentos]
        # Mapa segmento → lista de ramos
        seg_ramos = {s.nome: s.ramos for s in self.segmentos}
        todos_eixos = [r for s in self.segmentos for r in s.ramos]
        listas = {"Segmento": nomes_segs, "Eixo ref.": todos_eixos}

        def _ok(resultado, t=tipo):
            if t == "BF":
                self.dados_bf_redist = resultado
                n = sum(1 for r in resultado if r and r[0].strip())
                self.lbl_bf_r.config(text=f"{n} BF(s) cadastrado(s)" if n else "Nenhum BF cadastrado")
            else:
                self.dados_ae_redist = resultado
                n = sum(1 for r in resultado if r and r[0].strip())
                self.lbl_ae_r.config(text=f"{n} AE(s) cadastrado(s)" if n else "Nenhum AE cadastrado")

        janela = JanelaTabelaBFAE(self, tipo=tipo, colunas=colunas,
                                   listas_suspensas=listas,
                                   dados_iniciais=dados,
                                   callback_ok=_ok,
                                   seg_ramos=seg_ramos)

    def _sel_pasta(self):
        p = filedialog.askdirectory(parent=self)
        if p: self.var_pasta.set(p)

    # ------------------------------------------------------------------ #
    # Sessão                                                               #
    # ------------------------------------------------------------------ #

    def _carregar_sessao(self):
        from redistribuicao import carregar_segmento, carregar_sessao
        import re
        path = filedialog.askopenfilename(
            title="Selecionar sessão de redistribuição",
            filetypes=[("Sessão JSON","*.json"),("Todos","*.*")], parent=self)
        if not path: return
        try:
            sessao = carregar_sessao(path)
        except Exception as ex:
            messagebox.showerror("Erro ao carregar sessão", str(ex), parent=self)
            return

        # Limpar estado
        self.segmentos.clear()
        for w in self.frame_segs.winfo_children(): w.destroy()
        for rd in list(self.relacoes): rd["frame"].destroy()
        self.relacoes.clear()

        def _json_mais_recente(caminho_original):
            """Busca o JSON com versão mais alta na mesma pasta.
            Se o caminho não existir, tenta:
            1. Trocar letra do drive (ex: D: → E:, C: etc)
            2. Buscar relativo à pasta da sessão
            """
            def _buscar_na_pasta(pasta, nome_base):
                """Busca o JSON mais recente na pasta dado o nome base."""
                nome_sem_versao = re.sub(r'_v\d+\.json$', '', nome_base)
                nome_sem_versao = re.sub(r'\.json$', '', nome_sem_versao)
                candidatos = []
                try:
                    for f in os.listdir(pasta):
                        if not f.endswith('.json'): continue
                        if not f.startswith(nome_sem_versao): continue
                        m = re.search(r'_v(\d+)\.json$', f)
                        if m:
                            candidatos.append((int(m.group(1)), os.path.join(pasta, f)))
                        elif f == nome_base:
                            candidatos.append((0, os.path.join(pasta, f)))
                except Exception:
                    return None
                if not candidatos:
                    return None
                candidatos.sort(key=lambda x: x[0], reverse=True)
                return candidatos[0][1]

            nome_base = os.path.basename(caminho_original)
            pasta_orig = os.path.dirname(caminho_original)

            # 1. Caminho original existe → buscar versão mais recente
            if os.path.isdir(pasta_orig):
                resultado = _buscar_na_pasta(pasta_orig, nome_base)
                if resultado:
                    return resultado
                return caminho_original

            # 2. Tentar trocar letra do drive (Windows: D:\ → E:\, C:\, F:\ etc)
            import string
            if len(caminho_original) >= 2 and caminho_original[1] == ':':
                resto = caminho_original[2:]  # ex: \Dropbox\...
                for letra in string.ascii_uppercase:
                    tentativa = letra + ':' + resto
                    pasta_tent = os.path.dirname(tentativa)
                    if os.path.isdir(pasta_tent):
                        resultado = _buscar_na_pasta(pasta_tent, nome_base)
                        if resultado:
                            return resultado

            # 3. Buscar na mesma pasta do arquivo de sessão
            if os.path.isdir(os.path.dirname(path)):
                resultado = _buscar_na_pasta(os.path.dirname(path), nome_base)
                if resultado:
                    return resultado

            # 4. Buscar recursivamente nas subpastas da pasta da sessão
            for raiz, dirs, arquivos in os.walk(os.path.dirname(path)):
                for arq in arquivos:
                    if arq == nome_base or (
                        arq.startswith(re.sub(r'_v\d+\.json$','',nome_base)) and
                        arq.endswith('.json')):
                        return os.path.join(raiz, arq)

            return caminho_original

        erros = []
        atualizados = []
        for info in sessao.get("segmentos", []):
            caminho_orig = info["caminho_json"]
            caminho = _json_mais_recente(caminho_orig)
            if os.path.normcase(caminho) != os.path.normcase(caminho_orig):
                atualizados.append(
                    f"  {os.path.basename(caminho_orig)} → {os.path.basename(caminho)}")
            if not os.path.exists(caminho):
                erros.append(f"Não encontrado: {caminho}"); continue
            try:
                seg = carregar_segmento(caminho)
                seg.config_ramos = info.get("config_ramos", {})
                seg._dados_bf    = info.get("dados_bf", [])
                seg._dados_ae    = info.get("dados_ae", [])
                self.segmentos.append(seg)
                self._add_linha_seg(seg)
            except Exception as ex:
                erros.append(f"{caminho}: {ex}")

        if erros:
            messagebox.showwarning("Arquivos não encontrados",
                                   "\n".join(erros), parent=self)
        if atualizados:
            messagebox.showinfo("JSONs atualizados",
                                "Os seguintes JSONs foram atualizados para a versão mais recente:\n"
                                + "\n".join(atualizados), parent=self)
        elif not erros:
            pass  # nada a informar — todos já estavam na versão mais recente

        if sessao.get("pasta_saida"):
            self.var_pasta.set(sessao["pasta_saida"])

        for rel in sessao.get("relacoes", []):
            self._criar_rel_frame(dados=rel)

        # Restaurar BF/AE da sessão nas listas de dados
        self.dados_bf_redist = []
        self.dados_ae_redist = []
        for item in sessao.get("bfae", []):
            tipo = item.get("tipo", "BF")
            colunas = self._colunas_bf_r if tipo == "BF" else self._colunas_ae_r
            idx_col = {c: i for i, c in enumerate(colunas)}
            vals = [""] * len(colunas)
            for campo, chave in [("Nome","nome"),("CMv","cmv_label"),("Segmento","segmento"),
                                   ("Eixo ref.","eixo_ref"),("Pos. rel. (m)","pos_relativa_m"),
                                   ("Afastamento (m)","afastamento_m"),("Volume (m³)","capacidade"),
                                   ("Fh","fh")]:
                if campo in idx_col and chave in item:
                    vals[idx_col[campo]] = str(item[chave])
            if tipo == "BF":
                self.dados_bf_redist.append(vals)
                self.lbl_bf_r.config(text=f"{len(self.dados_bf_redist)} BF(s) cadastrado(s)")
            else:
                self.dados_ae_redist.append(vals)
                self.lbl_ae_r.config(text=f"{len(self.dados_ae_redist)} AE(s) cadastrado(s)")

        messagebox.showinfo("Sessão carregada",
                            f"{len(self.segmentos)} segmento(s), "
                            f"{len(self.relacoes)} relação(ões).\n"
                            f"Data: {sessao.get('data','')}", parent=self)

    # ------------------------------------------------------------------ #
    # Redistribuir                                                         #
    # ------------------------------------------------------------------ #

    def _redistribuir(self):
        if len(self.segmentos) < 2:
            messagebox.showwarning("Atenção","Adicione pelo menos 2 segmentos.",parent=self)
            return
        if not self.relacoes:
            messagebox.showwarning("Atenção","Adicione pelo menos uma relação.",parent=self)
            return
        pasta = self.var_pasta.get().strip()
        if not pasta or not os.path.isdir(pasta):
            messagebox.showwarning("Atenção","Pasta de saída inválida.",parent=self)
            return
        try:
            from redistribuicao import (RelacaoSegmento, redistribuir,
                                         gerar_excel_redistribuido,
                                         salvar_json_redistribuido,
                                         salvar_sessao, LocalAuxiliarRedist)
            rels = []
            for rd in self.relacoes:
                try:
                    rel = RelacaoSegmento(
                        seg_a         = rd["seg_a"].get(),
                        seg_b         = rd["seg_b"].get(),
                        extensao_a_m  = float(rd["extensao_a"].get()),
                        extensao_b_m  = float(rd["extensao_b"].get()),
                        deslocamento_m= float(rd["deslocamento"].get()),
                        afastamento_m = float(rd["afastamento"].get()),
                        usar_c1       = rd["usar_c1"].get(),
                        usar_c2       = rd["usar_c2"].get(),
                        usar_c3       = rd["usar_c3"].get(),
                    )
                    if rel.seg_a == rel.seg_b:
                        messagebox.showwarning("Atenção",
                                               "Segmento A e B não podem ser iguais.",
                                               parent=self)
                        return
                    rels.append(rel)
                except ValueError:
                    messagebox.showwarning("Atenção",
                                           "Verifique os valores das relações.",
                                           parent=self)
                    return

            # Coletar BF/AE da redistribuição — por segmento (sem coluna Segmento)
            bfae_sessao = []
            COLUNAS_BF_S = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Volume (m³)"]
            COLUNAS_AE_S = ["Nome", "CMv", "Eixo ref.", "Pos. rel. (m)", "Afastamento (m)", "Volume (m³)", "Fh"]
            # Zerar listas antes de popular
            for seg in self.segmentos:
                seg.bota_foras_redist  = []
                seg.emprestimos_redist = []

            avisos_seg = []
            for seg_obj in self.segmentos:
                for dados, colunas, tipo in [
                    (getattr(seg_obj, '_dados_bf', []), COLUNAS_BF_S, "BF"),
                    (getattr(seg_obj, '_dados_ae', []), COLUNAS_AE_S, "AE"),
                ]:
                    idx_col = {c: i for i, c in enumerate(colunas)}
                    for row in dados:
                        try:
                            nome = row[idx_col["Nome"]].strip() if idx_col.get("Nome",99)<len(row) else ""
                            if not nome: continue
                            cmv_lbl = row[idx_col["CMv"]].strip()       if idx_col.get("CMv",99)<len(row) else ""
                            eixo    = row[idx_col["Eixo ref."]].strip()  if idx_col.get("Eixo ref.",99)<len(row) else (seg_obj.ramos[0] if seg_obj.ramos else "")
                            pos     = float(row[idx_col["Pos. rel. (m)"]].replace(",","."))   if idx_col.get("Pos. rel. (m)",99)<len(row) and row[idx_col["Pos. rel. (m)"]].strip() else 0.0
                            af      = float(row[idx_col["Afastamento (m)"]].replace(",",".")) if idx_col.get("Afastamento (m)",99)<len(row) and row[idx_col["Afastamento (m)"]].strip() else 0.0
                            vol_key = "Volume (m³)"
                            vol     = float(row[idx_col[vol_key]].replace(",","."))            if idx_col.get(vol_key,99)<len(row) and row[idx_col[vol_key]].strip() else 0.0
                            fh      = float(row[idx_col["Fh"]].replace(",","."))               if "Fh" in idx_col and idx_col["Fh"]<len(row) and row[idx_col["Fh"]].strip() else 1.0
                            if vol <= 0: continue

                            item = LocalAuxiliarRedist(
                                nome=nome, tipo=tipo, segmento=seg_obj.nome,
                                eixo_ref=eixo, pos_relativa_m=pos,
                                afastamento_m=af, capacidade=vol,
                                fh=fh, cmv_label=cmv_lbl,
                            )
                            if tipo == "BF":
                                seg_obj.bota_foras_redist.append(item)
                            else:
                                seg_obj.emprestimos_redist.append(item)
                            bfae_sessao.append({
                                "tipo": tipo, "segmento": seg_obj.nome,
                                "nome": nome, "cmv_label": cmv_lbl,
                                "eixo_ref": eixo, "pos_relativa_m": pos,
                                "afastamento_m": af, "capacidade": vol, "fh": fh,
                            })
                        except Exception as ex:
                            avisos_seg.append(f"  {tipo} '{seg_obj.nome}' linha: {ex}")

            if avisos_seg:
                messagebox.showwarning("Avisos BF/AE",
                    "Alguns itens não foram processados:\n" + "\n".join(avisos_seg),
                    parent=self)

            linhas_por_seg = redistribuir(self.segmentos, rels)

            for seg in self.segmentos:
                linhas = linhas_por_seg.get(seg.nome, [])
                nome_base = seg.nome.replace(" ","_").replace("/","_")
                excel_out = os.path.join(pasta, f"{nome_base}_redistribuido.xlsx")
                json_out  = os.path.join(pasta, f"{nome_base}_redistribuido.json")
                # Passar BFs e AEs externos de todos os segmentos
                bfs_ext = []
                for s in self.segmentos:
                    for bf_r in s.bota_foras_redist:
                        bfs_ext.append({
                            'tipo':          'BF',
                            'label_bf':      bf_r.nome,
                            'cmv_label':     bf_r.cmv_label,
                            'cmv_m':         bf_r.pos_relativa_m,
                            'ramo':          bf_r.eixo_ref,
                            'segmento':      s.nome,
                            'afastamento_m': bf_r.afastamento_m,
                        })
                    for ae_r in s.emprestimos_redist:
                        bfs_ext.append({
                            'tipo':          'AE',
                            'label_bf':      ae_r.nome,
                            'cmv_label':     ae_r.cmv_label,
                            'cmv_m':         ae_r.pos_relativa_m,
                            'ramo':          ae_r.eixo_ref,
                            'segmento':      s.nome,
                            'afastamento_m': ae_r.afastamento_m,
                        })
                gerar_excel_redistribuido(seg, linhas, excel_out,
                                          bfs_externos=bfs_ext,
                                          relacoes=rels)
                salvar_json_redistribuido(seg, linhas, json_out)
                self._jsons_redistribuidos.append(json_out)

            # Salvar sessão automaticamente
            relacoes_dict = [{
                "seg_a":          rd["seg_a"].get(),
                "seg_b":          rd["seg_b"].get(),
                "extensao_a_m":   rd["extensao_a"].get(),
                "extensao_b_m":   rd["extensao_b"].get(),
                "deslocamento_m": rd["deslocamento"].get(),
                "afastamento_m":  rd["afastamento"].get(),
                "usar_c1":        rd["usar_c1"].get(),
                "usar_c2":        rd["usar_c2"].get(),
                "usar_c3":        rd["usar_c3"].get(),
            } for rd in self.relacoes]

            sessao_out = os.path.join(pasta, "sessao_redistribuicao.json")
            salvar_sessao(self.segmentos, relacoes_dict, pasta, sessao_out,
                          bfae=bfae_sessao)

            messagebox.showinfo("✅ Concluído!",
                                f"Arquivos gerados em:\n{pasta}", parent=self)
            if self._btn_bruckner:
                self._btn_bruckner.config(state="normal")
        except Exception as ex:
            import traceback
            messagebox.showerror("Erro", f"{ex}\n\n{traceback.format_exc()}", parent=self)

    def _abrir_bruckner(self):
        """Abre o Diagrama de Massas pós-redistribuição."""
        from bruckner_viz import abrir_pos_redistribuicao
        if not self._jsons_redistribuidos:
            messagebox.showinfo("Atenção",
                "Execute a redistribuição primeiro.", parent=self)
            return
        if len(self._jsons_redistribuidos) == 1:
            abrir_pos_redistribuicao(self._jsons_redistribuidos[0], self)
        else:
            from tkinter import simpledialog
            nomes = [os.path.basename(p) for p in self._jsons_redistribuidos]
            escolha = simpledialog.askstring(
                "Selecionar segmento",
                "Qual segmento visualizar?\n\n" +
                "\n".join(f"{i+1}. {n}" for i, n in enumerate(nomes)) +
                "\n\nDigite o número:", parent=self)
            if not escolha:
                return
            try:
                idx = int(escolha.strip()) - 1
                if 0 <= idx < len(self._jsons_redistribuidos):
                    abrir_pos_redistribuicao(self._jsons_redistribuidos[idx], self)
                else:
                    messagebox.showwarning("Inválido",
                        "Número fora do intervalo.", parent=self)
            except ValueError:
                messagebox.showwarning("Inválido",
                    "Digite apenas o número.", parent=self)


def abrir_redistribuicao():
    root = tk.Tk(); root.withdraw()
    j = JanelaRedistribuicao(root)
    j.protocol("WM_DELETE_WINDOW", lambda: (j.destroy(), root.destroy()))
    root.mainloop()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.estado = EstadoProjeto()
        self._janela_atual = None
        self.abrir_janela(1)

    def abrir_janela(self, numero):
        if self._janela_atual:
            try: self._janela_atual.destroy()
            except Exception: pass

        e = self.estado
        ir = self.abrir_janela

        if numero == 1:
            j = Janela1Projeto(self, e, ir)
        elif numero == 2:
            j = Janela2Arquivos(self, e, ir, lambda: ir(1))
        elif numero == 3:
            j = Janela3Materiais(self, e, ir, lambda: ir(2))
        elif numero == 4:
            j = Janela4Parametros(self, e, ir, lambda: ir(3))
        elif numero == 5:
            j = Janela5BFAuxiliar(self, e, ir, lambda: ir(4))
        elif numero == 6:
            j = Janela6Restricoes(self, e, ir, lambda: ir(5))
        elif numero == 7:
            j = Janela7Gerar(self, e, lambda: ir(6))
        else:
            return

        self._janela_atual = j
        j.protocol("WM_DELETE_WINDOW", self._fechar)

    def _fechar(self):
        if messagebox.askokcancel("Sair","Deseja sair do programa?"):
            self.quit()
            self.destroy()


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        import traceback
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Erro ao iniciar", f"{e}\n\n{traceback.format_exc()}")
        root.destroy()


# ---------------------------------------------------------------------------
# Janela de Redistribuição entre Segmentos
# ---------------------------------------------------------------------------