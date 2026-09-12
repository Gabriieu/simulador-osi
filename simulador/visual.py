"""Interface grafica do simulador, construida com tkinter.

A interface le a lista de eventos produzida pelo motor e desenha a tela
correspondente ao evento corrente. Ela nao instancia camadas, nao chama
metodos de camada e nao conhece a implementacao do encapsulamento: tudo o que
aparece na tela vem de um objeto ``Evento``.

Os sete requisitos de visualizacao do enunciado estao distribuidos assim:

======  ======================================================================
V1      ``PainelMapa``, com o caminho percorrido em destaque
V2      ``PainelPilhas``, com a camada ativa em destaque
V3      ``PainelUnidade``, com os blocos da unidade de dados
V4      ``PainelEnderecos``, com os dois pares visiveis ao mesmo tempo
V5      ``BarraDeControle``, com passo a passo, execucao continua e pausa
V6      ``PainelRegistro``, rolavel e com gravacao em arquivo
V7      ``BarraSuperior``, com a alternancia entre a pilha OSI e a TCP/IP
======  ======================================================================
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Sequence, Tuple
import ctypes

from .ambiente import pasta_do_programa, topologia_padrao
from .camadas import CARGA_POR_SEGMENTO, LIMITE_SEGMENTACAO
from .cenarios import Cenario, Fluxo, cenarios_padrao
from .motor import (
    ErroDeSimulacaoError,
    ResultadoSimulacao,
    Simulacao,
    comparar_eficiencias,
)
from .pdu import TAMANHO_CABECALHO, TAMANHO_FINALIZADOR
from .rede import ErroDeTopologiaError, Topologia
from .registro import Evento, salvar

# Identidade visual


PALETA = {
    "fundo": "#EEF2F5",
    "painel": "#FFFFFF",
    "borda": "#C7D4DD",
    "tinta": "#10212B",
    "tinta_fraca": "#5C7183",
    "estrutura": "#0B6E8F",
    "estrutura_clara": "#DCEDF4",
    "ativo": "#E8A317",
    "ativo_claro": "#FDF1D8",
    "erro": "#B0392E",
    "erro_claro": "#F8E3E0",
    "entrega": "#2E7D5B",
    "inativo": "#9FB0BC",
    "dados": "#2E7D5B",
    "dados_claro": "#DFF0E7",
}

#: Tons dos cabecalhos por camada, do topo da pilha para a base.
COR_CAMADA = {
    7: "#5B4B8A",
    6: "#3F6CA8",
    5: "#0B6E8F",
    4: "#0E8577",
    3: "#37773E",
    2: "#8A6D1F",
    1: "#6B7C8F",
}

NOME_CAMADA = {
    7: "Aplicação",
    6: "Apresentação",
    5: "Sessão",
    4: "Transporte",
    3: "Rede",
    2: "Enlace",
    1: "Física",
}

VELOCIDADES = (("Lenta", 1200), ("Normal", 500), ("Rápida", 150))


# Janela principal


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class AplicacaoSimulador(tk.Tk):
    """Janela principal do simulador."""

    def __init__(self, caminho_topologia: Optional[str] = None) -> None:
        super().__init__()
        self.title("Simulador do modelo OSI — Comunicação de Dados")
        SPI_GETWORKAREA = 0x0030
        rect = RECT()

        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
        )

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        self.geometry(f"{width}x{height}+{rect.left}+{rect.top}")
        # self.geometry(f"{screen_width}x{screen_height}+0+0")
        self.minsize(1120, 720)
        self.configure(background=PALETA["fundo"])

        self._cenarios: List[Cenario] = cenarios_padrao()
        self._topologia: Optional[Topologia] = None
        self._resultado: Optional[ResultadoSimulacao] = None
        self._indice = -1
        self._modo_pilha = "OSI"
        self._reproduzindo = False
        self._agendamento: Optional[str] = None
        self._derrubados: List[str] = []
        self._erro_de_bit: Optional[str] = None
        self._eficiencias_referencia: Dict[str, object] = {}

        self._preparar_estilos()
        self._construir_layout()
        self._registrar_atalhos()

        self._carregar_topologia(caminho_topologia or topologia_padrao(), inicial=True)

    # -- aparencia ---------------------------------------------------------

    def _preparar_estilos(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:  # pragma: no cover - depende do sistema
            pass
        base = ("Segoe UI", 9)
        self.fonte_base = base
        self.fonte_titulo = ("Segoe UI Semibold", 10)
        self.fonte_cabecalho = ("Segoe UI Semibold", 13)
        self.fonte_mono = ("Consolas", 9)
        self.fonte_mono_pequena = ("Consolas", 8)

        estilo.configure(
            ".", background=PALETA["fundo"], foreground=PALETA["tinta"], font=base
        )
        estilo.configure("TFrame", background=PALETA["fundo"])
        estilo.configure(
            "Painel.TFrame", background=PALETA["painel"], relief="solid", borderwidth=1
        )
        estilo.configure("Interno.TFrame", background=PALETA["painel"], borderwidth=0)
        estilo.configure(
            "TLabel", background=PALETA["fundo"], foreground=PALETA["tinta"]
        )
        estilo.configure("Painel.TLabel", background=PALETA["painel"])
        estilo.configure(
            "Titulo.TLabel",
            background=PALETA["painel"],
            foreground=PALETA["estrutura"],
            font=self.fonte_titulo,
        )
        estilo.configure(
            "Cabecalho.TLabel",
            background=PALETA["fundo"],
            foreground=PALETA["tinta"],
            font=self.fonte_cabecalho,
        )
        estilo.configure(
            "Fraco.TLabel",
            background=PALETA["painel"],
            foreground=PALETA["tinta_fraca"],
        )
        estilo.configure(
            "Mono.TLabel", background=PALETA["painel"], font=self.fonte_mono
        )
        estilo.configure("TButton", padding=(10, 5))
        estilo.configure("Acao.TButton", padding=(12, 6), font=self.fonte_titulo)
        estilo.configure(
            "TLabelframe", background=PALETA["painel"], borderwidth=1, relief="solid"
        )
        estilo.configure(
            "TLabelframe.Label",
            background=PALETA["painel"],
            foreground=PALETA["estrutura"],
            font=self.fonte_titulo,
        )
        estilo.configure("TRadiobutton", background=PALETA["painel"])
        estilo.configure("TCheckbutton", background=PALETA["painel"])

    def _painel(self, pai, titulo: str) -> ttk.Labelframe:
        quadro = ttk.Labelframe(pai, text=titulo, padding=8)
        return quadro

    # -- layout ------------------------------------------------------------

    def _construir_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)
        self.rowconfigure(2, weight=2)

        self._construir_barra_superior()

        meio = ttk.Frame(self, padding=(10, 0, 10, 0))
        meio.grid(row=1, column=0, sticky="nsew")
        meio.columnconfigure(0, weight=34, uniform="col")
        meio.columnconfigure(1, weight=34, uniform="col")
        meio.columnconfigure(2, weight=32, uniform="col")
        meio.rowconfigure(0, weight=1)

        self._construir_coluna_mapa(meio)
        self._construir_coluna_pilhas(meio)
        self._construir_coluna_dados(meio)

        inferior = ttk.Frame(self, padding=(10, 8, 10, 10))
        inferior.grid(row=2, column=0, sticky="nsew")
        inferior.columnconfigure(0, weight=1)
        inferior.rowconfigure(1, weight=1)
        self._construir_controles(inferior)
        self._construir_registro(inferior)

        self._barra_estado = ttk.Label(
            self, text="Pronto.", anchor="w", padding=(12, 4), style="TLabel"
        )
        self._barra_estado.grid(row=3, column=0, sticky="ew")

    def _construir_barra_superior(self) -> None:
        barra = ttk.Frame(self, padding=(10, 10, 10, 6))
        barra.grid(row=0, column=0, sticky="ew")
        barra.columnconfigure(6, weight=1)

        ttk.Label(barra, text="Simulador do modelo OSI", style="Cabecalho.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 18)
        )

        ttk.Label(barra, text="Cenário").grid(row=0, column=1, sticky="w", padx=(0, 4))
        self._var_cenario = tk.StringVar()
        self._combo_cenario = ttk.Combobox(
            barra,
            textvariable=self._var_cenario,
            state="readonly",
            width=42,
            values=[c.nome_exibicao for c in self._cenarios],
        )
        self._combo_cenario.grid(row=0, column=2, sticky="w")
        self._combo_cenario.current(1)
        self._combo_cenario.bind(
            "<<ComboboxSelected>>", lambda _e: self._carregar_cenario()
        )

        ttk.Button(barra, text="Carregar cenário", command=self._carregar_cenario).grid(
            row=0, column=3, padx=6
        )
        ttk.Button(
            barra, text="Abrir topologia…", command=self._escolher_topologia
        ).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(
            barra, text="Tabelas de encaminhamento", command=self._mostrar_tabelas
        ).grid(row=0, column=5)

        self._var_pilha = tk.StringVar(value="OSI")
        alternancia = ttk.Frame(barra)
        alternancia.grid(row=0, column=7, sticky="e")
        ttk.Label(alternancia, text="Exibir pilha").pack(side="left", padx=(0, 6))
        for rotulo in ("OSI", "TCP/IP"):
            ttk.Radiobutton(
                alternancia,
                text=rotulo,
                value=rotulo,
                variable=self._var_pilha,
                command=self._alternar_pilha,
            ).pack(side="left")

    # -- coluna 1: mapa e falhas ------------------------------------------

    def _construir_coluna_mapa(self, pai) -> None:
        coluna = ttk.Frame(pai)
        coluna.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        coluna.columnconfigure(0, weight=1)
        coluna.rowconfigure(0, weight=1)

        painel = self._painel(coluna, "Mapa da rede")
        painel.grid(row=0, column=0, sticky="nsew")
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(0, weight=1)
        self._canvas_mapa = tk.Canvas(
            painel, background=PALETA["painel"], highlightthickness=0, height=300
        )
        self._canvas_mapa.grid(row=0, column=0, sticky="nsew")
        self._canvas_mapa.bind("<Configure>", lambda _e: self._desenhar_mapa())

        falhas = self._painel(coluna, "Provocar falhas")
        falhas.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        falhas.columnconfigure(1, weight=1)

        ttk.Label(falhas, text="Enlace", style="Painel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self._var_enlace = tk.StringVar()
        self._combo_enlace = ttk.Combobox(
            falhas, textvariable=self._var_enlace, state="readonly", width=26
        )
        self._combo_enlace.grid(row=0, column=1, sticky="ew", padx=6)

        botoes = ttk.Frame(falhas, style="Interno.TFrame")
        botoes.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(botoes, text="Derrubar enlace", command=self._derrubar_enlace).pack(
            side="left"
        )
        ttk.Button(botoes, text="Injetar erro de bit", command=self._injetar_erro).pack(
            side="left", padx=6
        )
        ttk.Button(botoes, text="Restaurar rede", command=self._restaurar_rede).pack(
            side="left"
        )

        self._rotulo_falhas = ttk.Label(
            falhas,
            text="Rede íntegra.",
            style="Fraco.TLabel",
            wraplength=340,
            justify="left",
        )
        self._rotulo_falhas.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # -- coluna 2: pilhas --------------------------------------------------

    def _construir_coluna_pilhas(self, pai) -> None:
        painel = self._painel(pai, "Pilhas dos dispositivos")
        painel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(0, weight=1)
        self._canvas_pilhas = tk.Canvas(
            painel, background=PALETA["painel"], highlightthickness=0
        )
        self._canvas_pilhas.grid(row=0, column=0, sticky="nsew")
        self._canvas_pilhas.bind("<Configure>", lambda _e: self._desenhar_pilhas())
        self._rotulo_passo = ttk.Label(
            painel,
            text="Carregue um cenário para começar.",
            style="Fraco.TLabel",
            wraplength=420,
            justify="left",
        )
        self._rotulo_passo.grid(row=1, column=0, sticky="w", pady=(6, 0))

    # -- coluna 3: parametros, unidade, enderecos, eficiencia --------------

    def _construir_coluna_dados(self, pai) -> None:
        coluna = ttk.Frame(pai)
        coluna.grid(row=0, column=2, sticky="nsew")
        coluna.columnconfigure(0, weight=1)
        coluna.rowconfigure(3, weight=1)

        parametros = self._painel(coluna, "Origem, destino e mensagem")
        parametros.grid(row=0, column=0, sticky="ew")
        parametros.columnconfigure(1, weight=1)
        parametros.columnconfigure(3, weight=1)

        self._var_origem = tk.StringVar()
        self._var_destino = tk.StringVar()
        self._var_processo_origem = tk.StringVar(value="navegador")
        self._var_processo_destino = tk.StringVar(value="servidorWeb")
        self._var_porta_origem = tk.StringVar(value="5210")
        self._var_porta_destino = tk.StringVar(value="443")
        self._var_mensagem = tk.StringVar()

        ttk.Label(parametros, text="Origem", style="Painel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self._combo_origem = ttk.Combobox(
            parametros, textvariable=self._var_origem, state="readonly", width=10
        )
        self._combo_origem.grid(row=0, column=1, sticky="ew", padx=(4, 10))

        ttk.Label(parametros, text="Destino", style="Painel.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self._combo_destino = ttk.Combobox(
            parametros, textvariable=self._var_destino, width=16
        )
        self._combo_destino.grid(row=0, column=3, sticky="ew", padx=(4, 0))

        ttk.Label(parametros, text="Processo", style="Painel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(parametros, textvariable=self._var_processo_origem).grid(
            row=1, column=1, sticky="ew", padx=(4, 10), pady=(6, 0)
        )
        ttk.Label(parametros, text="Processo destino", style="Painel.TLabel").grid(
            row=1, column=2, sticky="w", pady=(6, 0)
        )
        ttk.Entry(parametros, textvariable=self._var_processo_destino).grid(
            row=1, column=3, sticky="ew", padx=(4, 0), pady=(6, 0)
        )

        ttk.Label(parametros, text="Porta origem", style="Painel.TLabel").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(parametros, textvariable=self._var_porta_origem).grid(
            row=2, column=1, sticky="ew", padx=(4, 10), pady=(6, 0)
        )
        ttk.Label(parametros, text="Porta destino", style="Painel.TLabel").grid(
            row=2, column=2, sticky="w", pady=(6, 0)
        )
        ttk.Entry(parametros, textvariable=self._var_porta_destino).grid(
            row=2, column=3, sticky="ew", padx=(4, 0), pady=(6, 0)
        )

        ttk.Label(parametros, text="Mensagem", style="Painel.TLabel").grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )
        entrada = ttk.Entry(parametros, textvariable=self._var_mensagem)
        entrada.grid(
            row=3, column=1, columnspan=3, sticky="ew", padx=(4, 0), pady=(6, 0)
        )

        self._rotulo_tamanho = ttk.Label(parametros, text="", style="Fraco.TLabel")
        self._rotulo_tamanho.grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )
        self._var_mensagem.trace_add(
            "write", lambda *_a: self._atualizar_tamanho_mensagem()
        )

        ttk.Button(
            parametros, text="Simular", style="Acao.TButton", command=self._simular
        ).grid(row=4, column=3, sticky="e", pady=(6, 0))

        unidade = self._painel(coluna, "Unidade de dados")
        unidade.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        unidade.columnconfigure(0, weight=1)
        self._canvas_unidade = tk.Canvas(
            unidade, background=PALETA["painel"], highlightthickness=0, height=104
        )
        self._canvas_unidade.grid(row=0, column=0, sticky="ew")
        self._canvas_unidade.bind("<Configure>", lambda _e: self._desenhar_unidade())

        enderecos = self._painel(coluna, "Endereços vigentes")
        enderecos.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        enderecos.columnconfigure(0, weight=1)
        enderecos.columnconfigure(1, weight=1)
        self._canvas_enderecos = tk.Canvas(
            enderecos, background=PALETA["painel"], highlightthickness=0, height=112
        )
        self._canvas_enderecos.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._canvas_enderecos.bind(
            "<Configure>", lambda _e: self._desenhar_enderecos()
        )

        eficiencia = self._painel(coluna, "Custo do empilhamento")
        eficiencia.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        eficiencia.columnconfigure(0, weight=1)
        eficiencia.rowconfigure(0, weight=1)
        self._texto_eficiencia = tk.Text(
            eficiencia,
            height=12,
            font=self.fonte_mono,
            background=PALETA["painel"],
            foreground=PALETA["tinta"],
            relief="flat",
            wrap="none",
            state="disabled",
        )
        self._texto_eficiencia.grid(row=0, column=0, sticky="nsew")
        rolagem = ttk.Scrollbar(
            eficiencia, orient="vertical", command=self._texto_eficiencia.yview
        )
        rolagem.grid(row=0, column=1, sticky="ns")
        self._texto_eficiencia.configure(yscrollcommand=rolagem.set)

    # -- controles e registro ---------------------------------------------

    def _construir_controles(self, pai) -> None:
        barra = ttk.Frame(pai, style="Painel.TFrame", padding=8)
        barra.grid(row=0, column=0, sticky="ew")
        barra.columnconfigure(8, weight=1)

        self._botao_passo = ttk.Button(barra, text="Passo", command=self._passo)
        self._botao_passo.grid(row=0, column=0)
        self._botao_executar = ttk.Button(
            barra, text="Executar", command=self._executar
        )
        self._botao_executar.grid(row=0, column=1, padx=6)
        self._botao_pausar = ttk.Button(barra, text="Pausar", command=self._pausar)
        self._botao_pausar.grid(row=0, column=2)
        ttk.Button(barra, text="Reiniciar", command=self._reiniciar).grid(
            row=0, column=3, padx=6
        )

        ttk.Separator(barra, orient="vertical").grid(
            row=0, column=4, sticky="ns", padx=10
        )

        ttk.Label(barra, text="Velocidade", style="Painel.TLabel").grid(row=0, column=5)
        self._var_velocidade = tk.IntVar(value=VELOCIDADES[1][1])
        grupo = ttk.Frame(barra, style="Interno.TFrame")
        grupo.grid(row=0, column=6, padx=(6, 0))
        for rotulo, intervalo in VELOCIDADES:
            ttk.Radiobutton(
                grupo, text=rotulo, value=intervalo, variable=self._var_velocidade
            ).pack(side="left")

        ttk.Separator(barra, orient="vertical").grid(
            row=0, column=7, sticky="ns", padx=10
        )

        self._rotulo_progresso = ttk.Label(
            barra, text="Passo 0 de 0", style="Painel.TLabel"
        )
        self._rotulo_progresso.grid(row=0, column=8, sticky="w")

        ttk.Button(barra, text="Salvar registro…", command=self._salvar_registro).grid(
            row=0, column=9, sticky="e"
        )

    def _construir_registro(self, pai) -> None:
        painel = self._painel(pai, "Registro de eventos")
        painel.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(0, weight=1)

        self._texto_registro = tk.Text(
            painel,
            font=self.fonte_mono_pequena,
            background="#FBFDFE",
            foreground=PALETA["tinta"],
            relief="flat",
            wrap="none",
            height=10,
            state="disabled",
        )
        self._texto_registro.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(
            painel, orient="vertical", command=self._texto_registro.yview
        )
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            painel, orient="horizontal", command=self._texto_registro.xview
        )
        horizontal.grid(row=1, column=0, sticky="ew")
        self._texto_registro.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self._texto_registro.tag_configure(
            "atual", background=PALETA["ativo_claro"], foreground=PALETA["tinta"]
        )
        self._texto_registro.tag_configure("descarte", foreground=PALETA["erro"])
        self._texto_registro.tag_configure("futuro", foreground=PALETA["inativo"])

    def _registrar_atalhos(self) -> None:
        self.bind("<space>", lambda _e: self._passo())
        self.bind("<Return>", lambda _e: self._executar())
        self.bind("<Escape>", lambda _e: self._pausar())
        self.bind("<Control-r>", lambda _e: self._reiniciar())
        self.bind("<Control-s>", lambda _e: self._salvar_registro())

    # ------------------------------------------------------------------
    # Topologia e cenarios
    # ------------------------------------------------------------------

    def _carregar_topologia(self, caminho: str, inicial: bool = False) -> None:
        try:
            topologia = Topologia.carregar(caminho)
        except ErroDeTopologiaError as erro:
            messagebox.showerror("Topologia não carregada", str(erro), parent=self)
            if inicial and self._topologia is None:
                self._informar("Nenhuma topologia carregada. Use “Abrir topologia…”.")
            return

        self._topologia = topologia
        self._derrubados = []
        self._erro_de_bit = None
        computadores = sorted(topologia.computadores())
        self._combo_origem.configure(values=computadores)
        self._combo_destino.configure(
            values=[topologia.interfaces_de(c)[0].logico for c in computadores]
        )
        self._combo_enlace.configure(
            values=[topologia.rotulo_enlace(s) for s in topologia.enlaces_derrubaveis()]
        )
        if self._combo_enlace["values"]:
            self._combo_enlace.current(0)
        try:
            self._eficiencias_referencia = comparar_eficiencias(topologia)
        except (ErroDeSimulacaoError, ErroDeTopologiaError):
            # Topologia diferente da de referencia: a comparacao C1 x C2 do
            # enunciado nao se aplica, e apenas o cenario corrente e exibido.
            self._eficiencias_referencia = {}
        self._informar(
            f"Topologia “{topologia.nome}” carregada de {os.path.basename(caminho)} "
            f"({len(topologia.dispositivos)} dispositivos, {len(topologia.segmentos)} redes)."
        )
        self._carregar_cenario()

    def _escolher_topologia(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Escolher arquivo de topologia",
            initialdir=pasta_do_programa(),
            filetypes=[("Topologia em JSON", "*.json"), ("Todos os arquivos", "*.*")],
        )
        if caminho:
            self._carregar_topologia(caminho)

    def _cenario_selecionado(self) -> Cenario:
        indice = max(0, self._combo_cenario.current())
        return self._cenarios[indice]

    def _carregar_cenario(self) -> None:
        """Preenche os campos com o cenário escolhido e executa a simulação."""
        if self._topologia is None:
            return
        cenario = self._cenario_selecionado()
        fluxo = cenario.fluxos[0]
        computadores = sorted(self._topologia.computadores())
        # O cenario C5 usa de proposito um destino que nao existe na topologia,
        # entao a ausencia do endereco nao o torna incompativel.
        destino_conhecido = (
            self._topologia.interface_por_logico(fluxo.destino_logico) is not None
        )
        compativel = fluxo.origem in computadores and (
            destino_conhecido or cenario.codigo == "C5"
        )

        self._var_origem.set(
            fluxo.origem if fluxo.origem in computadores else computadores[0]
        )
        self._var_destino.set(fluxo.destino_logico)
        self._var_processo_origem.set(fluxo.processo_origem)
        self._var_processo_destino.set(fluxo.processo_destino)
        self._var_porta_origem.set(str(fluxo.porta_origem))
        self._var_porta_destino.set(str(fluxo.porta_destino))
        self._var_mensagem.set(fluxo.texto)

        derrubado = cenario.enlace_derrubado
        self._derrubados = (
            [derrubado] if derrubado and derrubado in self._topologia.segmentos else []
        )
        erro = cenario.erro_de_bit
        self._erro_de_bit = erro if erro and erro in self._topologia.segmentos else None
        self._atualizar_falhas()

        if compativel:
            self._simular(cenario=cenario, usar_fluxos_do_cenario=True, silencioso=True)
        else:
            self._informar(
                f"O cenário {cenario.codigo} foi escrito para a topologia de referência. "
                f"Ajuste origem e destino e pressione Simular."
            )
            self._resultado = None
            self._indice = -1
            self._preencher_registro()
            self._redesenhar()

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------

    def _coletar_fluxos(self) -> Sequence[Fluxo]:
        """Monta o fluxo a partir dos campos da tela, validando as entradas."""
        origem = self._var_origem.get().strip()
        destino = self._var_destino.get().strip()
        mensagem = self._var_mensagem.get()
        if not origem:
            raise ErroDeSimulacaoError("escolha o computador de origem")
        if not destino:
            raise ErroDeSimulacaoError("informe o endereço lógico de destino")
        if not mensagem.strip():
            raise ErroDeSimulacaoError("a mensagem não pode ficar vazia")
        try:
            porta_origem = int(self._var_porta_origem.get())
            porta_destino = int(self._var_porta_destino.get())
        except ValueError:
            raise ErroDeSimulacaoError("as portas devem ser números inteiros") from None
        return (
            Fluxo(
                origem=origem,
                destino_logico=destino,
                processo_origem=self._var_processo_origem.get().strip() or "processo",
                processo_destino=self._var_processo_destino.get().strip() or "processo",
                porta_origem=porta_origem,
                porta_destino=porta_destino,
                texto=mensagem,
            ),
        )

    def _simular(
        self,
        cenario: Optional[Cenario] = None,
        usar_fluxos_do_cenario: bool = False,
        silencioso: bool = False,
    ) -> None:
        """Executa a simulação com os parâmetros da tela.

        :param silencioso: quando verdadeiro, um erro de parâmetro aparece na
            barra de estado em vez de abrir uma caixa de mensagem. E o que se
            usa ao trocar de cenário, para que a troca nunca interrompa o uso.
        """
        if self._topologia is None:
            messagebox.showwarning(
                "Sem topologia",
                "Carregue um arquivo de topologia antes de simular.",
                parent=self,
            )
            return
        self._pausar()
        cenario = cenario or self._cenario_selecionado()
        try:
            fluxos = None if usar_fluxos_do_cenario else self._coletar_fluxos()
            simulacao = Simulacao(
                self._topologia,
                cenario,
                fluxos=fluxos,
                enlaces_derrubados=self._derrubados,
                erro_de_bit=self._erro_de_bit,
            )
            self._resultado = simulacao.executar()
        except (ErroDeSimulacaoError, ErroDeTopologiaError) as erro:
            if silencioso:
                self._informar(f"Não foi possível simular: {erro}")
            else:
                messagebox.showerror("Não foi possível simular", str(erro), parent=self)
            return
        except Exception as erro:  # pragma: no cover - salvaguarda da janela
            messagebox.showerror(
                "Erro inesperado",
                f"A simulação foi interrompida: {erro}\nA janela continua aberta.",
                parent=self,
            )
            return

        self._indice = -1
        self._preencher_registro()
        self._atualizar_eficiencia()
        self._atualizar_tamanho_mensagem()
        self._redesenhar()
        self._informar(
            f"{cenario.nome_exibicao}: {self._resultado.total_de_passos} passos. "
            f"Use Passo ou Executar."
        )

    def _passo(self) -> None:
        if not self._resultado:
            return
        if self._indice + 1 >= len(self._resultado.eventos):
            self._pausar()
            self._informar("Fim da simulação. Use Reiniciar para executar novamente.")
            return
        self._indice += 1
        self._redesenhar()

    def _executar(self) -> None:
        if not self._resultado or self._reproduzindo:
            return
        self._reproduzindo = True
        self._agendar()

    def _agendar(self) -> None:
        if not self._reproduzindo:
            return
        self._passo()
        if self._resultado and self._indice + 1 < len(self._resultado.eventos):
            self._agendamento = self.after(self._var_velocidade.get(), self._agendar)
        else:
            self._reproduzindo = False

    def _pausar(self) -> None:
        self._reproduzindo = False
        if self._agendamento is not None:
            try:
                self.after_cancel(self._agendamento)
            except tk.TclError:  # pragma: no cover
                pass
            self._agendamento = None

    def _reiniciar(self) -> None:
        self._pausar()
        self._indice = -1
        self._redesenhar()
        self._informar("Simulação reiniciada no passo 0.")

    # ------------------------------------------------------------------
    # Falhas
    # ------------------------------------------------------------------

    def _segmento_escolhido(self) -> Optional[str]:
        if self._topologia is None:
            return None
        indice = self._combo_enlace.current()
        if indice < 0:
            return None
        return self._topologia.enlaces_derrubaveis()[indice]

    def _derrubar_enlace(self) -> None:
        segmento = self._segmento_escolhido()
        if segmento is None:
            return
        if segmento in self._derrubados:
            self._derrubados.remove(segmento)
        else:
            self._derrubados.append(segmento)
        self._atualizar_falhas()
        self._simular()

    def _injetar_erro(self) -> None:
        segmento = self._segmento_escolhido()
        if segmento is None:
            return
        self._erro_de_bit = None if self._erro_de_bit == segmento else segmento
        self._atualizar_falhas()
        self._simular()

    def _restaurar_rede(self) -> None:
        self._derrubados = []
        self._erro_de_bit = None
        self._atualizar_falhas()
        self._simular()

    def _atualizar_falhas(self) -> None:
        partes = []
        if self._derrubados:
            partes.append("Enlaces derrubados: " + ", ".join(self._derrubados))
        if self._erro_de_bit:
            partes.append(f"Erro de bit injetado em: {self._erro_de_bit}")
        self._rotulo_falhas.configure(
            text="\n".join(partes) if partes else "Rede íntegra."
        )

    # ------------------------------------------------------------------
    # Desenho
    # ------------------------------------------------------------------

    def _evento_atual(self) -> Optional[Evento]:
        if not self._resultado or self._indice < 0:
            return None
        if self._indice >= len(self._resultado.eventos):
            return None
        return self._resultado.eventos[self._indice]

    def _redesenhar(self) -> None:
        self._desenhar_mapa()
        self._desenhar_pilhas()
        self._desenhar_unidade()
        self._desenhar_enderecos()
        self._destacar_registro()
        total = len(self._resultado.eventos) if self._resultado else 0
        self._rotulo_progresso.configure(
            text=f"Passo {max(0, self._indice + 1)} de {total}"
        )
        evento = self._evento_atual()
        if evento is None:
            self._rotulo_passo.configure(
                text="Passo 0. Nenhuma camada ativa ainda — pressione Passo."
            )
        else:
            self._rotulo_passo.configure(
                text=(
                    f"{evento.dispositivo} · camada {evento.camada} "
                    f"({NOME_CAMADA.get(evento.camada, '')}) · {evento.acao}\n"
                    f"{evento.descricao}"
                )
            )

    def _alternar_pilha(self) -> None:
        self._modo_pilha = self._var_pilha.get()
        self._desenhar_pilhas()

    # -- mapa --------------------------------------------------------------

    def _desenhar_mapa(self) -> None:
        canvas = self._canvas_mapa
        canvas.delete("all")
        if self._topologia is None:
            return
        largura = canvas.winfo_width()
        altura = canvas.winfo_height()
        if largura < 60 or altura < 60:
            return

        margem_x, margem_y = 46, 34
        posicoes = self._topologia.posicoes()

        def ponto(nome: str) -> Tuple[float, float]:
            rx, ry = posicoes[nome]
            return (
                margem_x + rx * (largura - 2 * margem_x),
                margem_y + ry * (altura - 2 * margem_y),
            )

        evento = self._evento_atual()
        caminho = evento.caminho if evento else ()
        pares = {frozenset(par) for par in caminho}

        for ligacao in self._topologia.ligacoes_visuais():
            membros = ligacao["membros"]
            ativo = ligacao["segmento"] not in self._derrubados
            if len(membros) == 2:
                a, b = membros[0]["dispositivo"], membros[1]["dispositivo"]
                destacado = frozenset((a, b)) in pares
                self._traco(canvas, ponto(a), ponto(b), ativo, destacado)
                meio = (
                    (ponto(a)[0] + ponto(b)[0]) / 2,
                    (ponto(a)[1] + ponto(b)[1]) / 2,
                )
                canvas.create_text(
                    meio[0],
                    meio[1] - 10,
                    text=(
                        ligacao["prefixo"]
                        if ligacao["tipo"] == "local"
                        else f"custo {ligacao['custo']}"
                    ),
                    font=self.fonte_mono_pequena,
                    fill=PALETA["erro"] if not ativo else PALETA["tinta_fraca"],
                )
                self._rotulo_interface(
                    canvas, ponto(a), ponto(b), membros[0]["interface"]
                )
                self._rotulo_interface(
                    canvas, ponto(b), ponto(a), membros[1]["interface"]
                )
            else:
                if ligacao["posicao"]:
                    centro = (
                        margem_x + ligacao["posicao"][0] * (largura - 2 * margem_x),
                        margem_y + ligacao["posicao"][1] * (altura - 2 * margem_y),
                    )
                else:
                    pontos = [ponto(m["dispositivo"]) for m in membros]
                    centro = (
                        sum(p[0] for p in pontos) / len(pontos),
                        sum(p[1] for p in pontos) / len(pontos),
                    )
                nomes = [m["dispositivo"] for m in membros]
                destacados = {
                    nome for par in pares if par <= set(nomes) for nome in par
                }
                for membro in membros:
                    nome = membro["dispositivo"]
                    self._traco(canvas, ponto(nome), centro, ativo, nome in destacados)
                    self._rotulo_interface(
                        canvas, ponto(nome), centro, membro["interface"]
                    )
                canvas.create_oval(
                    centro[0] - 30,
                    centro[1] - 13,
                    centro[0] + 30,
                    centro[1] + 13,
                    fill=PALETA["estrutura_clara"],
                    outline=PALETA["estrutura"],
                )
                canvas.create_text(
                    centro[0],
                    centro[1],
                    text=ligacao["segmento"].replace("Rede ", ""),
                    font=self.fonte_mono_pequena,
                    fill=PALETA["estrutura"],
                )
                canvas.create_text(
                    centro[0],
                    centro[1] + 22,
                    text=ligacao["prefixo"],
                    font=self.fonte_mono_pequena,
                    fill=PALETA["tinta_fraca"],
                )

        atual = evento.dispositivo if evento else None
        for nome, descricao in self._topologia.dispositivos.items():
            x, y = ponto(nome)
            roteador = descricao.tipo == "roteador"
            largura_caixa, altura_caixa = (34, 26) if roteador else (32, 24)
            destaque = nome == atual
            cor_fundo = (
                PALETA["ativo_claro"]
                if destaque
                else (PALETA["estrutura_clara"] if roteador else PALETA["painel"])
            )
            cor_borda = PALETA["ativo"] if destaque else PALETA["estrutura"]
            if roteador:
                canvas.create_polygon(
                    x,
                    y - altura_caixa,
                    x + largura_caixa,
                    y,
                    x,
                    y + altura_caixa,
                    x - largura_caixa,
                    y,
                    fill=cor_fundo,
                    outline=cor_borda,
                    width=2 if destaque else 1,
                )
            else:
                canvas.create_rectangle(
                    x - largura_caixa,
                    y - altura_caixa,
                    x + largura_caixa,
                    y + altura_caixa,
                    fill=cor_fundo,
                    outline=cor_borda,
                    width=2 if destaque else 1,
                )
            canvas.create_text(
                x, y - 6, text=nome, font=self.fonte_titulo, fill=PALETA["tinta"]
            )
            canvas.create_text(
                x,
                y + 8,
                text=descricao.interfaces[0].logico,
                font=self.fonte_mono_pequena,
                fill=PALETA["tinta_fraca"],
            )

    def _traco(self, canvas, origem, destino, ativo: bool, destacado: bool) -> None:
        if not ativo:
            canvas.create_line(
                *origem, *destino, fill=PALETA["erro"], width=2, dash=(5, 4)
            )
            meio = ((origem[0] + destino[0]) / 2, (origem[1] + destino[1]) / 2)
            canvas.create_text(
                meio[0],
                meio[1] + 10,
                text="X",
                fill=PALETA["erro"],
                font=self.fonte_titulo,
            )
            return
        canvas.create_line(
            *origem,
            *destino,
            fill=PALETA["ativo"] if destacado else PALETA["inativo"],
            width=4 if destacado else 1.5,
        )

    def _rotulo_interface(self, canvas, origem, destino, nome: str) -> None:
        dx, dy = destino[0] - origem[0], destino[1] - origem[1]
        comprimento = max(1.0, (dx * dx + dy * dy) ** 0.5)
        fator = min(0.34, 44 / comprimento)
        canvas.create_text(
            origem[0] + dx * fator,
            origem[1] + dy * fator,
            text=nome,
            font=self.fonte_mono_pequena,
            fill=PALETA["tinta_fraca"],
        )

    # -- pilhas ------------------------------------------------------------

    def _faixas(self, tipo: str) -> List[Tuple[str, set]]:
        """Faixas exibidas na pilha, conforme o modelo escolhido."""
        if self._modo_pilha == "OSI":
            numeros = [7, 6, 5, 4, 3, 2, 1] if tipo == "computador" else [3, 2, 1]
            return [(f"L{n} {NOME_CAMADA[n]}", {n}) for n in numeros]
        if tipo == "computador":
            return [
                ("Aplicação (5-7)", {5, 6, 7}),
                ("L4 Transporte", {4}),
                ("L3 Rede", {3}),
                ("L2 Enlace", {2}),
                ("L1 Física", {1}),
            ]
        return [("L3 Rede", {3}), ("L2 Enlace", {2}), ("L1 Física", {1})]

    def _desenhar_pilhas(self) -> None:
        canvas = self._canvas_pilhas
        canvas.delete("all")
        if not self._resultado:
            return
        largura = canvas.winfo_width()
        altura = canvas.winfo_height()
        if largura < 60 or altura < 60:
            return

        envolvidos = list(self._resultado.dispositivos_envolvidos)
        if not envolvidos:
            return
        evento = self._evento_atual()
        coluna = largura / len(envolvidos)
        topo = 22
        altura_util = altura - topo - 8

        for indice, nome in enumerate(envolvidos):
            descricao = self._topologia.dispositivos[nome]
            faixas = self._faixas(descricao.tipo)
            altura_faixa = min(34.0, altura_util / max(len(faixas), 1))
            x0 = indice * coluna + 8
            x1 = (indice + 1) * coluna - 8
            ativo_aqui = evento is not None and evento.dispositivo == nome
            canvas.create_text(
                (x0 + x1) / 2,
                10,
                text=nome,
                font=self.fonte_titulo,
                fill=PALETA["ativo"] if ativo_aqui else PALETA["tinta"],
            )
            for posicao, (rotulo, numeros) in enumerate(faixas):
                y0 = topo + posicao * altura_faixa
                y1 = y0 + altura_faixa - 3
                ativa = ativo_aqui and evento.camada in numeros
                decisao_de_rota = (
                    ativa and descricao.tipo == "roteador" and evento.camada == 3
                )
                canvas.create_rectangle(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill=PALETA["ativo_claro"] if ativa else PALETA["painel"],
                    outline=PALETA["ativo"] if ativa else PALETA["borda"],
                    width=3 if decisao_de_rota else (2 if ativa else 1),
                )
                canvas.create_text(
                    (x0 + x1) / 2,
                    (y0 + y1) / 2,
                    text=rotulo if (x1 - x0) > 96 else rotulo.split(" ")[0],
                    font=self.fonte_base,
                    fill=PALETA["tinta"] if ativa else PALETA["tinta_fraca"],
                )
                if ativa:
                    canvas.create_rectangle(
                        x0 + 2,
                        y0 + 2,
                        x0 + 6,
                        y1 - 2,
                        fill=PALETA["ativo"],
                        outline=PALETA["ativo"],
                    )

    # -- unidade de dados --------------------------------------------------

    def _desenhar_unidade(self) -> None:
        canvas = self._canvas_unidade
        canvas.delete("all")
        largura = canvas.winfo_width()
        if largura < 60:
            return
        evento = self._evento_atual()
        if evento is None or not evento.blocos:
            canvas.create_text(
                largura / 2,
                52,
                text="A unidade de dados aparece aqui a cada passo.",
                fill=PALETA["tinta_fraca"],
                font=self.fonte_base,
            )
            return

        titulo = f"{evento.unidade}"
        if evento.identificador:
            titulo += f" {evento.identificador}"
        titulo += f" — {evento.tamanho} octetos"
        canvas.create_text(
            8, 12, text=titulo, anchor="w", font=self.fonte_titulo, fill=PALETA["tinta"]
        )

        blocos = list(evento.blocos)
        total = sum(max(b["tamanho"], 1) for b in blocos)
        util = largura - 16
        minimo = 30.0
        larguras = [max(minimo, util * max(b["tamanho"], 1) / total) for b in blocos]
        excesso = sum(larguras) - util
        if excesso > 0:
            folgados = [i for i, w in enumerate(larguras) if w > minimo]
            disponivel = sum(larguras[i] - minimo for i in folgados) or 1
            for i in folgados:
                larguras[i] -= (larguras[i] - minimo) * excesso / disponivel

        x = 8.0
        y0, y1 = 28, 76
        for bloco, largura_bloco in zip(blocos, larguras):
            if bloco["tipo"] == "dados":
                fundo, borda = PALETA["dados_claro"], PALETA["dados"]
            elif bloco["tipo"] == "finalizador":
                fundo, borda = "#EFF2F4", PALETA["tinta_fraca"]
            else:
                borda = COR_CAMADA.get(bloco["camada"], PALETA["estrutura"])
                fundo = (
                    PALETA["ativo_claro"]
                    if bloco["camada"] == evento.camada
                    else "#F4F8FA"
                )
            canvas.create_rectangle(
                x, y0, x + largura_bloco, y1, fill=fundo, outline=borda, width=2
            )
            canvas.create_text(
                x + largura_bloco / 2,
                (y0 + y1) / 2 - 7,
                text=bloco["rotulo"],
                font=self.fonte_titulo,
                fill=borda,
            )
            canvas.create_text(
                x + largura_bloco / 2,
                (y0 + y1) / 2 + 9,
                text=f"{bloco['tamanho']} B",
                font=self.fonte_mono_pequena,
                fill=PALETA["tinta_fraca"],
            )
            x += largura_bloco

        canvas.create_text(
            8,
            90,
            anchor="w",
            text="Cabeçalhos à esquerda dos dados; finalizador da camada 2 à direita.",
            font=self.fonte_mono_pequena,
            fill=PALETA["tinta_fraca"],
        )

    # -- enderecos ---------------------------------------------------------

    def _desenhar_enderecos(self) -> None:
        canvas = self._canvas_enderecos
        canvas.delete("all")
        largura = canvas.winfo_width()
        if largura < 60:
            return
        evento = self._evento_atual()
        metade = largura / 2 - 6

        def caixa(x: float, titulo: str, nota: str, par, cor: str, mono: bool) -> None:
            canvas.create_rectangle(
                x, 6, x + metade, 104, fill=PALETA["painel"], outline=cor, width=2
            )
            canvas.create_text(
                x + 10, 20, text=titulo, anchor="w", font=self.fonte_titulo, fill=cor
            )
            canvas.create_text(
                x + 10,
                36,
                text=nota,
                anchor="w",
                font=self.fonte_mono_pequena,
                fill=PALETA["tinta_fraca"],
            )
            origem, destino = par if par else ("—", "—")
            fonte = self.fonte_mono if mono else self.fonte_base
            canvas.create_text(
                x + 10,
                60,
                text=f"origem  {origem}",
                anchor="w",
                font=fonte,
                fill=PALETA["tinta"],
            )
            canvas.create_text(
                x + 10,
                82,
                text=f"destino {destino}",
                anchor="w",
                font=fonte,
                fill=PALETA["tinta"],
            )

        caixa(
            2,
            "Endereços lógicos",
            "inseridos na origem, constantes até o destino",
            evento.logicos if evento else None,
            PALETA["estrutura"],
            True,
        )
        caixa(
            largura / 2 + 4,
            "Endereços físicos",
            f"substituídos a cada salto{' · ' + evento.enlace if evento and evento.enlace else ''}",
            evento.fisicos if evento else None,
            PALETA["ativo"],
            True,
        )

    # -- registro ----------------------------------------------------------

    def _preencher_registro(self) -> None:
        self._texto_registro.configure(state="normal")
        self._texto_registro.delete("1.0", "end")
        if self._resultado:
            for evento in self._resultado.eventos:
                marcas = ("descarte",) if evento.descarte else ()
                self._texto_registro.insert("end", evento.linha + "\n", marcas)
        self._texto_registro.configure(state="disabled")

    def _destacar_registro(self) -> None:
        self._texto_registro.configure(state="normal")
        self._texto_registro.tag_remove("atual", "1.0", "end")
        if self._indice >= 0:
            linha = self._indice + 1
            self._texto_registro.tag_add("atual", f"{linha}.0", f"{linha}.end+1c")
            self._texto_registro.see(f"{linha}.0")
        self._texto_registro.configure(state="disabled")

    def _salvar_registro(self) -> None:
        if not self._resultado:
            messagebox.showinfo(
                "Nada para salvar",
                "Execute uma simulação antes de salvar o registro.",
                parent=self,
            )
            return
        caminho = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar registro de eventos",
            initialdir=pasta_do_programa(),
            initialfile=f"registro_{self._resultado.cenario.codigo.lower()}.txt",
            defaultextension=".txt",
            filetypes=[("Arquivo de texto", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return
        try:
            destino = salvar(
                caminho,
                self._resultado.eventos,
                self._resultado.resumo,
                titulo=(
                    f"Simulador do modelo OSI — {self._resultado.cenario.nome_exibicao}"
                ),
            )
        except OSError as erro:
            messagebox.showerror("Registro não salvo", str(erro), parent=self)
            return
        self._informar(f"Registro salvo em {destino}")

    # -- eficiencia --------------------------------------------------------

    def _atualizar_eficiencia(self) -> None:
        self._texto_eficiencia.configure(state="normal")
        self._texto_eficiencia.delete("1.0", "end")
        linhas: List[str] = []
        if self._resultado and self._resultado.resumo:
            linhas.extend(self._resultado.resumo.como_linhas())
            linhas.append("")
        referencia = self._eficiencias_referencia
        if referencia:
            c1, c2 = referencia.get("C1"), referencia.get("C2")
            if c1 and c2:
                linhas.append("Comparação exigida no enunciado")
                linhas.append(
                    f"  C1 (1 enlace)   {c1.octetos_uteis} B úteis / "
                    f"{c1.octetos_transmitidos} B transmitidos = {c1.eficiencia_percentual}"
                )
                linhas.append(
                    f"  C2 (4 enlaces)  {c2.octetos_uteis} B úteis / "
                    f"{c2.octetos_transmitidos} B transmitidos = {c2.eficiencia_percentual}"
                )
        linhas.append("")
        linhas.append(
            f"Cabeçalhos: L5={TAMANHO_CABECALHO[5]} L4={TAMANHO_CABECALHO[4]} "
            f"L3={TAMANHO_CABECALHO[3]} L2={TAMANHO_CABECALHO[2]}+{TAMANHO_FINALIZADOR}"
        )
        linhas.append(
            f"Segmentação: acima de {LIMITE_SEGMENTACAO} B, "
            f"{CARGA_POR_SEGMENTO} B por segmento"
        )
        self._texto_eficiencia.insert("1.0", "\n".join(linhas))
        self._texto_eficiencia.configure(state="disabled")

    def _atualizar_tamanho_mensagem(self) -> None:
        octetos = len(self._var_mensagem.get().encode("utf-8"))
        aviso = (
            " (será segmentada)"
            if octetos + TAMANHO_CABECALHO[5] > LIMITE_SEGMENTACAO
            else ""
        )
        self._rotulo_tamanho.configure(text=f"{octetos} octetos{aviso}")

    # -- tabelas -----------------------------------------------------------

    def _mostrar_tabelas(self) -> None:
        if self._topologia is None:
            return
        janela = tk.Toplevel(self)
        janela.title("Tabelas de encaminhamento")
        janela.configure(background=PALETA["fundo"])
        janela.geometry("560x460")
        janela.transient(self)

        caderno = ttk.Notebook(janela)
        caderno.pack(fill="both", expand=True, padx=10, pady=10)
        for roteador in sorted(self._topologia.roteadores()):
            aba = ttk.Frame(caderno, padding=6)
            caderno.add(aba, text=roteador)
            tabela = ttk.Treeview(
                aba,
                columns=("destino", "salto", "custo", "interface"),
                show="headings",
                height=12,
            )
            for coluna, titulo, largura in (
                ("destino", "Rede de destino", 150),
                ("salto", "Próximo salto", 130),
                ("custo", "Custo", 60),
                ("interface", "Interface", 90),
            ):
                tabela.heading(coluna, text=titulo)
                tabela.column(coluna, width=largura, anchor="w")
            for rota in self._topologia.tabela_encaminhamento(roteador):
                tabela.insert(
                    "",
                    "end",
                    values=(
                        rota.destino,
                        rota.proximo_salto or "entrega direta",
                        rota.custo,
                        rota.interface,
                    ),
                )
            tabela.pack(fill="both", expand=True)
        ttk.Label(
            janela,
            text=(
                "Tabelas calculadas a partir dos custos do arquivo de topologia, "
                "pelo algoritmo de menor custo."
            ),
            wraplength=520,
            padding=(10, 0, 10, 10),
        ).pack(anchor="w")

    # -- estado ------------------------------------------------------------

    def _informar(self, mensagem: str) -> None:
        self._barra_estado.configure(text=mensagem)


def executar(caminho_topologia: Optional[str] = None) -> None:
    """Abre a janela do simulador."""
    aplicacao = AplicacaoSimulador(caminho_topologia)
    aplicacao.mainloop()
