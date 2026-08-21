"""
Representação orientada a objeto de um arquivo carregado no Wizard
Analytics.

Antes, cada arquivo era um dict solto dentro de EstadoApp.arquivos
(com chaves "df", "gerenciador", "figura", "grafico_gerado", "avisos",
"info"), sincronizadas manualmente em vários pontos de callbacks.py e
renderizadores.py. Este módulo junta tudo isso em um objeto só, o que
elimina duas classes de bug que já existiam:

  1. Campos que sempre mudam juntos (ex: 'figura' e 'grafico_gerado')
     podiam ficar dessincronizados porque eram dois campos escritos à
     mão nos mesmos lugares. Agora 'grafico_gerado' é uma property
     derivada de 'figura' — não tem como dessincronizar.

  2. O rótulo de uma coluna (GerenciadorRotulos) vivia separado do
     ciclo de vida da própria coluna (existe? foi calculada? está
     escondida?). Agora isso é um Canal só, com um status.
"""

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class StatusCanal(Enum):
    VISIVEL = "visivel"    # aparece na lista de canais, pode ser selecionado
    OCULTO = "oculto"      # existe no df, mas não aparece na lista (ex: coluna auxiliar de cálculo)
    EXCLUIDO = "excluido"  # soft-delete: some da lista e da seleção, mas o dado continua no df_editado


@dataclass
class Canal:
    """
    Um canal = uma coluna do df_editado + seu rótulo de exibição + seu
    ciclo de vida (original/calculado, visível/oculto/excluído).

    Substitui o par solto (coluna do DataFrame + entrada no antigo
    GerenciadorRotulos).
    """
    nome_interno: str
    rotulo: str
    origem: str = "original"          # "original" | "calculado"
    status: StatusCanal = StatusCanal.VISIVEL
    formula: str | None = None        # ex: "media(['A', 'B'])" — auditoria de canal calculado
    _historico_rotulos: list = field(default_factory=list, repr=False)

    @property
    def visivel(self) -> bool:
        return self.status == StatusCanal.VISIVEL

    @property
    def excluido(self) -> bool:
        return self.status == StatusCanal.EXCLUIDO

    def renomear(self, novo_rotulo: str) -> None:
        novo_rotulo = novo_rotulo.strip()
        if not novo_rotulo:
            raise ValueError("O novo rótulo não pode ser vazio.")
        if novo_rotulo == self.rotulo:
            return
        self._historico_rotulos.append(self.rotulo)
        self.rotulo = novo_rotulo

    def desfazer_rotulo(self) -> bool:
        if not self._historico_rotulos:
            return False
        self.rotulo = self._historico_rotulos.pop()
        return True

    def excluir(self) -> None:
        self.status = StatusCanal.EXCLUIDO

    def restaurar(self) -> None:
        self.status = StatusCanal.VISIVEL

    def ocultar(self) -> None:
        self.status = StatusCanal.OCULTO


@dataclass
class PreferenciasCanal:
    """
    Como UM canal específico aparece no gráfico.

    'espessura' começa em 1.0 (não 2.0) para bater com o slider do painel
    de edição da curva (ver 'Thickness' em edit_menu.css/renderizadores.py),
    que também começa em 1 e sobe de 0.5 em 0.5.
    """
    cor: str | None = None
    espessura: float = 1.0
    estilo_linha: str = "solid"  # "solid" | "dash" | "dot" | "dashdot" | "none" (sem linha)
    # "none" (padrão — sem marcador) ou um símbolo do Plotly ("circle",
    # "square", "diamond", "triangle-up", "x") — INDEPENDENTE de
    # 'estilo_linha': as duas se somam na mesma curva (ver resolver_modo
    # em plotter.py), não uma substitui a outra.
    marcador: str = "none"


@dataclass
class PreferenciasTexto:
    """
    Um texto editável do gráfico (título do gráfico, rótulo do eixo X,
    rótulo do eixo Y) + como ele aparece — ver a linha 'Title'/'Axis x'
    /'Axis y' da seção 'Eixos' no painel de edição (cada uma é um
    _linha_eixo em renderizadores.py: caixa de texto + stepper de
    fonte + stepper de espaçamento).

    'espacamento' é a DISTÂNCIA desse texto até o gráfico — equivalente
    ao parâmetro 'pad' de um título no matplotlib — não espaçamento
    ENTRE CARACTERES. Pro título do gráfico vira
    fig.update_layout(title=dict(pad=dict(b=...))) (o 'b' — bottom —
    é o que empurra o gráfico pra baixo, afastando da barra do
    título); pros rótulos de eixo vira xaxis/yaxis.title.standoff (a
    distância entre o rótulo do eixo e os números de tick). Ver
    _aplicar_preferencias_grafico em plotter.py.
    """
    texto: str = ''
    fonte: int = 12
    espacamento: int = 15


@dataclass
class PreferenciasLimiteEixo:
    """
    Limites (min/max) de UM eixo — sub-seção 'Limits' dentro de
    'Eixos' no painel (_linha_limite_eixo em renderizadores.py).

    'minimo'/'maximo' ficam None enquanto o usuário não digitou nada
    (ou clicou 'autoscale') — nesse estado o Plotly decide sozinho o
    range, olhando os dados (comportamento padrão, sem
    fig.update_xaxes(range=...) nenhum). 'travado' reflete o cadeado
    🔓/🔒: server-side ele não muda NADA sozinho (min/max já fixos
    fazem o eixo não mexer, trava ou não) — é só o que fica gravado pra
    a caixinha nascer com o ícone certo da próxima vez que a edição for
    reaberta.
    """
    minimo: float | None = None
    maximo: float | None = None
    travado: bool = False


@dataclass
class PreferenciasTicksEixo:
    """
    Como os ticks de UM eixo (x ou y) aparecem no gráfico — ver seção
    'Ticks' do painel de edição (renderizadores.py/callbacks.py).

    'divisoes'/'subdivisoes'.numero é o número de marcas NOVAS entre
    os extremos do eixo (ou entre duas marcas principais, no caso das
    subdivisões) — NÃO conta os próprios extremos, que já ficam
    implícitos na moldura do gráfico. Ex: numero=1 num eixo de 0 a 1
    -> só 1 marca nova, bem no meio (0.5); numero=5 (padrão) -> 5
    marcas novas. O passo entre elas (dtick) é calculado a partir do
    range REAL do eixo em _tick0_e_dtick (plotter.py) — que também
    arredonda esse range pra bordas "redondas" antes de dividir, pra
    não gerar marcas em números feios tipo 4.55095 quando os dados não
    terminam num valor redondo.

    'divisoes' e 'subdivisoes' guardam os mesmos 3 números (número de
    marcas / largura / comprimento do traço do tick) em dois conjuntos
    INDEPENDENTES — os ticks "principais" e os "secundários" (o
    recurso de minor ticks do Plotly, xaxis.minor=dict(...); as
    marcas SECUNDÁRIAS ficam igualmente espaçadas DENTRO de cada
    intervalo principal). O painel usa o MESMO trio de sliders pros
    dois (ver _campo_slider/sincronizar_campos_ticks), só troca qual
    dict aqui está sendo lido/escrito no momento.
    """
    divisoes: dict = field(default_factory=lambda: {'numero': 5, 'largura': 1, 'comprimento': 5})
    subdivisoes: dict = field(default_factory=lambda: {'numero': 4, 'largura': 1, 'comprimento': 3})
    # Espelha o tick pro lado oposto do eixo (topo/direita), via
    # fig.update_xaxes/yaxes(mirror='ticks') — ver 'Both sides' no
    # painel.
    both_sides: bool = False
    # Tamanho da fonte dos RÓTULOS de tick (os números ao lado de cada
    # marca, ex: '0', '2', '4'...) — fig.update_xaxes/yaxes(
    # tickfont=dict(size=...)). Diferente de PreferenciasTexto.fonte
    # (título do eixo): aquele é o tamanho do RÓTULO "Axis x:"/"Axis
    # y:" digitado pelo usuário; este é o tamanho dos números que o
    # Plotly desenha sozinho em cada tick.
    fonte_labels: int = 14
    # 'outside' (padrão) ou 'inside' — pra que lado o traço do tick
    # aponta a partir da linha do eixo, fig.update_xaxes/yaxes(
    # ticks=...); aplicado igual nos ticks principais E secundários
    # (não faz sentido visual ter um pra dentro e outro pra fora no
    # mesmo eixo).
    direcao: str = 'outside'


@dataclass
class PreferenciasGrafico:
    """Como o gráfico inteiro aparece: eixos, limites, título."""
    titulo: PreferenciasTexto = field(default_factory=lambda: PreferenciasTexto(fonte=18))
    titulo_eixo_x: PreferenciasTexto = field(default_factory=lambda: PreferenciasTexto(fonte=16))
    titulo_eixo_y: PreferenciasTexto = field(default_factory=lambda: PreferenciasTexto(fonte=16))
    limite_x: PreferenciasLimiteEixo = field(default_factory=PreferenciasLimiteEixo)
    limite_y: PreferenciasLimiteEixo = field(default_factory=PreferenciasLimiteEixo)
    por_canal: dict[str, PreferenciasCanal] = field(default_factory=dict)
    # Ticks de cada eixo — independentes entre si (ver
    # PreferenciasTicksEixo). Quando o painel edita com 'Eixo: Both'
    # selecionado, os DOIS são escritos com o mesmo valor (ver
    # _prefs_ticks_alvos em callbacks.py), mas continuam podendo
    # divergir se o usuário editar X e Y separadamente depois.
    ticks_x: PreferenciasTicksEixo = field(default_factory=PreferenciasTicksEixo)
    ticks_y: PreferenciasTicksEixo = field(default_factory=PreferenciasTicksEixo)
    # 'Outros': grid ligado/desligado (fig.update_xaxes/yaxes(showgrid=))
    # e cor de fundo da ÁREA de plotagem (fig.update_layout(plot_bgcolor=)).
    # 'cor_fundo' None = deixa o Plotly usar o padrão do template
    # ('plotly_white'), não força branco por cima.
    grid: bool = True
    cor_fundo: str | None = None

    def preferencias_do_canal(self, nome_interno: str) -> PreferenciasCanal:
        """Cria (na primeira vez) e devolve as preferências de um canal."""
        if nome_interno not in self.por_canal:
            self.por_canal[nome_interno] = PreferenciasCanal()
        return self.por_canal[nome_interno]


@dataclass
class Arquivo:
    """
    Um arquivo carregado: seus dados, seus canais e seu gráfico.

    - df_original: nunca é modificado depois da leitura. Serve pra
      resetar o arquivo do zero se o usuário quiser desfazer tudo.
    - df_editado: cópia de trabalho — é nela que canais calculados
      entram e onde qualquer operação (filtro, corte, amostragem)
      mexe. Canais excluídos continuam fisicamente aqui (soft-delete).
    - figura: cache da última figura Plotly montada. É a ÚNICA fonte
      de verdade sobre "tem gráfico gerado ou não" (ver grafico_gerado).
    """
    nome: str
    df_original: pd.DataFrame
    df_editado: pd.DataFrame
    avisos: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    canais: dict[str, Canal] = field(default_factory=dict)
    preferencias: PreferenciasGrafico = field(default_factory=PreferenciasGrafico)
    figura: object = None
    # Nomes de coluna que devem nascer com status OCULTO em vez de
    # VISIVEL — hoje alimentado pelo extractor com as colunas que não
    # deram pra converter em numérico (texto/booleano/data como string):
    # elas continuam no df_editado, só não entopem a lista de canais
    # plotáveis por padrão (ver extractor.carregar_dados, chave
    # 'colunas_nao_numericas' de 'info').
    colunas_ocultas_iniciais: list = field(default_factory=list)

    def __post_init__(self):
        # Registra um Canal pra cada coluna que já veio no df, se ainda
        # não foi passado nenhum registro explícito de canais.
        if not self.canais:
            ocultas = set(self.colunas_ocultas_iniciais)
            for coluna in self.df_editado.columns:
                status = StatusCanal.OCULTO if coluna in ocultas else StatusCanal.VISIVEL
                self.canais[coluna] = Canal(nome_interno=coluna, rotulo=str(coluna), status=status)

    # --- Gráfico ---------------------------------------------------

    @property
    def grafico_gerado(self) -> bool:
        """True assim que existe uma figura montada para este arquivo."""
        return self.figura is not None

    def invalidar_grafico(self) -> None:
        """Descarta o cache da figura — próxima leitura terá que remontar."""
        self.figura = None

    # --- Canais ------------------------------------------------------

    def registrar_canal(self, nome_interno, rotulo=None, origem="original", formula=None) -> Canal:
        canal = Canal(
            nome_interno=nome_interno,
            rotulo=str(rotulo) if rotulo else str(nome_interno),
            origem=origem,
            formula=formula,
        )
        self.canais[nome_interno] = canal
        return canal

    def rotulo(self, nome_interno: str) -> str:
        """
        Rótulo de exibição de um canal. Auto-registra o canal se ele
        não existir ainda (ex: coluna calculada fora do fluxo normal),
        pra nunca travar a interface com KeyError — mesmo espírito
        resiliente do antigo GerenciadorRotulos.
        """
        canal = self.canais.get(nome_interno)
        if canal is None:
            canal = self.registrar_canal(nome_interno)
        return canal.rotulo

    def renomear_canal(self, nome_interno: str, novo_rotulo: str) -> None:
        canal = self.canais.get(nome_interno) or self.registrar_canal(nome_interno)
        canal.renomear(novo_rotulo)

    def colunas_visiveis(self) -> list:
        """Canais que devem aparecer na lista lateral e podem ser plotados."""
        return [nome for nome, canal in self.canais.items() if canal.status == StatusCanal.VISIVEL]

    def excluir_canal(self, nome_interno: str) -> None:
        """Soft-delete: o canal some da lista/seleção, mas o dado permanece no df_editado."""
        if nome_interno in self.canais:
            self.canais[nome_interno].excluir()
            self.invalidar_grafico()

    def restaurar_canal(self, nome_interno: str) -> None:
        if nome_interno in self.canais:
            self.canais[nome_interno].restaurar()
            self.invalidar_grafico()

    def ocultar_canal_eixo(self, nome_interno: str) -> None:
        """
        Oculta o canal usado como eixo X de um gráfico (ex:
        'Tempo_decorrido_s') — chamado quando esse gráfico é gerado (ver
        callbacks.gerar_grafico_serie_temporal). Diferente de
        excluir_canal, este canal continua "vivo": não é dado plotado
        como série, é o próprio eixo, então ocultá-lo/exibi-lo NÃO invalida
        a figura em cache (não muda nada do que já está desenhado).
        """
        canal = self.canais.get(nome_interno)
        if canal:
            canal.ocultar()

    def exibir_canal_eixo(self, nome_interno: str) -> None:
        """
        Contrapartida de ocultar_canal_eixo: chamado ao fechar o gráfico
        (ver callbacks.fechar_grafico), pra o canal do eixo voltar a
        aparecer na lista. Só mexe se ele ainda estiver OCULTO — não
        reverte uma exclusão manual (soft-delete) que o usuário tenha
        feito por conta própria enquanto o gráfico estava aberto.
        """
        canal = self.canais.get(nome_interno)
        if canal and canal.status == StatusCanal.OCULTO:
            canal.restaurar()

    def criar_canal_calculado(self, nome_saida: str, operacao_fn, *args, **kwargs) -> None:
        """
        Aplica uma função de src/core/operations/*.py sobre o
        df_editado e registra o resultado como um novo Canal
        "calculado", com a fórmula guardada para auditoria.
        """
        self.df_editado = operacao_fn(self.df_editado, *args, nome_saida=nome_saida, **kwargs)
        argumentos = ", ".join(str(a) for a in args)
        self.registrar_canal(
            nome_saida,
            rotulo=nome_saida,
            origem="calculado",
            formula=f"{operacao_fn.__name__}({argumentos})" if argumentos else operacao_fn.__name__,
        )
        self.invalidar_grafico()

    # --- Avisos / info do rodapé -------------------------------------

    def adicionar_aviso(self, mensagem: str) -> None:
        if mensagem not in self.avisos:
            self.avisos.append(mensagem)
