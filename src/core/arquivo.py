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

from src.core.rotulos import sanitizar_rotulo_para_nome_coluna


# Origem do canal criado na leitura quando o arquivo tem só 1 coluna
# numérica: o número da amostra (0, 1, 2...) vira o eixo X implícito.
ORIGEM_INDICE = "indice"
ROTULO_INDICE = "índice"


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
    origem: str = "original"          # "original" | "calculado" | "indice"
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
    # Tamanho do marcador (só tem efeito enquanto 'marcador' != 'none' —
    # ver TAMANHO_MARCADOR_PADRAO em plotter.py, que é o valor de fábrica
    # usado tanto aqui quanto no slider 'Marker size' do painel de edição,
    # que só aparece na tela quando um marcador está selecionado).
    tamanho_marcador: float = 7.0


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

    # --- Atribuição manual de eixos ('Plotar Seleção') ---------------
    # 'eixo_x_manual': nome_interno da coluna escolhida como X (None =
    # ninguém escolheu ainda — resolver_eixo_x, plotter.py, cai pro
    # fallback automático de sempre). 'eixos_y_manual': lista ORDENADA
    # (ordem de clique = ordem de plotagem/cor) das colunas escolhidas
    # como Y — substitui o antigo mecanismo de checkbox (estado.
    # canais_selecionados, ainda existe mas não é mais lido pelo
    # gráfico principal, ver colunas_plotadas em plotter.py). Ver os
    # métodos mover_para_eixo_x/mover_para_eixo_y/remover_da_selecao_
    # eixos logo abaixo.
    eixo_x_manual: str | None = None
    eixos_y_manual: list = field(default_factory=list)

    def __post_init__(self):
        # Registra um Canal pra cada coluna que já veio no df, se ainda
        # não foi passado nenhum registro explícito de canais.
        if not self.canais:
            ocultas = set(self.colunas_ocultas_iniciais)
            for coluna in self.df_editado.columns:
                status = StatusCanal.OCULTO if coluna in ocultas else StatusCanal.VISIVEL
                self.canais[coluna] = Canal(nome_interno=coluna, rotulo=str(coluna), status=status)

    # --- Gráfico ---------------------------------------------------

    @classmethod
    def criar_de_leitura(cls, nome, df, avisos=None, info=None):
        """
        Monta o Arquivo a partir do que o extractor leu, aplicando as
        regras de "o que dá pra analisar":

          - 0 linhas ou 0 colunas numéricas -> ValueError (o arquivo é
            recusado: não há nada pra plotar nem calcular);
          - 1 coluna numérica -> cria a coluna do ÍNDICE (0, 1, 2...),
            origem 'indice', já atribuída ao eixo X. Clicar na única
            coluna manda ela direto pro Y, e o índice fica disponível na
            calculadora (ex: índice × 0.01 = tempo em segundos);
          - 2 ou mais -> como sempre.

        O índice é criado em df_original TAMBÉM: ele faz parte do arquivo
        "como lido" — depois de aparar/excluir trechos, ele guarda o número
        ORIGINAL de cada amostra.
        """
        info = dict(info or {})
        avisos = list(avisos or [])
        nao_numericas = list(info.get('colunas_nao_numericas', []))
        numericas = [c for c in df.columns if c not in nao_numericas]

        if df.empty or not numericas:
            motivo = 'nenhuma linha de dados' if df.empty else 'nenhuma coluna numérica'
            raise ValueError(f"'{nome}' não tem {motivo} para analisar.")

        nome_indice = None
        if len(numericas) == 1:
            df = df.copy()
            nome_indice, sufixo = 'indice', 1
            while nome_indice in df.columns:
                sufixo += 1
                nome_indice = f'indice_{sufixo}'
            df.insert(0, nome_indice, range(len(df)))
            avisos.append(
                f"Aviso: o arquivo tem só 1 coluna numérica ('{numericas[0]}'). "
                f"O índice das amostras (0, 1, 2…) foi criado e usado como eixo X."
            )

        arquivo = cls(
            nome=nome,
            df_original=df.copy(),
            df_editado=df.copy(),
            avisos=avisos,
            info=info,
            colunas_ocultas_iniciais=nao_numericas,
        )
        if nome_indice:
            canal = arquivo.canais[nome_indice]
            canal.origem = ORIGEM_INDICE
            canal.rotulo = ROTULO_INDICE
            arquivo.mover_para_eixo_x(nome_indice)
        return arquivo

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

    def colunas_disponiveis_calculo(self) -> list:
        """
        Canais que podem ser usados na CALCULADORA — nos botões de
        'Colunas' (ver renderizar_calculadora_botoes, renderizadores.py)
        e no dropdown de 'Coluna existente' pra sobrescrever.

        DIFERENTE de colunas_visiveis(): inclui também os canais
        atribuídos ao eixo X ou a algum eixo Y do gráfico (ver
        mover_para_eixo_x/mover_para_eixo_y abaixo) — esses ficam
        OCULTOS da lista lateral 'Dados do arquivo:' de propósito, mas
        estar sendo plotado não deve impedir usar o mesmo dado numa
        conta (pedido explícito: "posso estar exibindo P1 no gráfico e
        querer fazer contas com P1" — antes a lista da calculadora
        seguia a mesma visibilidade da barra lateral, então um canal
        que tinha acabado de virar X/Y sumia dali também, o que não
        fazia sentido: a disponibilidade pra CÁLCULO nunca deveria
        depender de o quê está sendo mostrado no gráfico AGORA).

        NÃO inclui os outros OCULTOS (ex: colunas não-numéricas
        escondidas no carregamento, ver colunas_ocultas_iniciais em
        EstadoApp.adicionar_arquivo) — essas continuam de fora porque
        não servem pra conta nenhuma mesmo, incluí-las só poluiria a
        lista de botões com colunas que sempre dariam erro ao usar.
        Nem EXCLUÍDOS (soft-delete) — esses realmente não devem
        aparecer em lugar nenhum.
        """
        atribuidas_a_eixo = set(self.eixos_y_manual)
        if self.eixo_x_manual:
            atribuidas_a_eixo.add(self.eixo_x_manual)
        return [
            nome for nome, canal in self.canais.items()
            if canal.status == StatusCanal.VISIVEL or nome in atribuidas_a_eixo
        ]

    @property
    def indice_implicito(self) -> str | None:
        """Nome interno do índice implícito, se este arquivo tiver um."""
        for nome, canal in self.canais.items():
            if canal.origem == ORIGEM_INDICE:
                return nome
        return None

    def canal_protegido(self, nome_interno: str) -> bool:
        """
        Canais que podem ser renomeados mas NÃO excluídos: hoje só o
        índice implícito (ver criar_de_leitura), que é a referência do
        eixo X quando o arquivo tem uma única coluna numérica.
        """
        canal = self.canais.get(nome_interno)
        return bool(canal) and canal.origem == ORIGEM_INDICE

    def excluir_canal(self, nome_interno: str) -> None:
        """
        Soft-delete: o canal some da lista/seleção, mas o dado permanece no df_editado.

        Se o canal excluído estava atribuído a X ou Y (ver mover_para_
        eixo_x/mover_para_eixo_y abaixo), limpa essa atribuição também
        — sem isso, 'eixo_x_manual'/'eixos_y_manual' ficariam
        apontando pra um canal excluído, e o gráfico tentaria usar um
        eixo "fantasma".
        """
        if self.canal_protegido(nome_interno):
            return
        if nome_interno in self.canais:
            self.canais[nome_interno].excluir()
            if self.eixo_x_manual == nome_interno:
                self.eixo_x_manual = None
            if nome_interno in self.eixos_y_manual:
                self.eixos_y_manual.remove(nome_interno)
            self.invalidar_grafico()

    def restaurar_canal(self, nome_interno: str) -> None:
        if nome_interno in self.canais:
            self.canais[nome_interno].restaurar()
            self.invalidar_grafico()

    def ocultar_canal_eixo(self, nome_interno: str) -> None:
        """
        DEPRECATED — mantido só por compatibilidade histórica de
        comentários antigos. O mecanismo de "ocultar o canal usado
        como eixo X" foi substituído por 'mover_para_eixo_x' abaixo,
        que já oculta o canal na hora da atribuição manual (rework do
        botão 'Plotar Seleção' — antes 'Gerar Série Temporal' fixava
        o eixo X sozinho olhando 'Tempo_decorrido_s'). Ninguém no
        código chama mais este método.
        """
        canal = self.canais.get(nome_interno)
        if canal:
            canal.ocultar()

    def exibir_canal_eixo(self, nome_interno: str) -> None:
        """DEPRECATED — ver ocultar_canal_eixo acima. Ninguém chama mais."""
        canal = self.canais.get(nome_interno)
        if canal and canal.status == StatusCanal.OCULTO:
            canal.restaurar()

    # --- Atribuição manual de eixos (botão 'Plotar Seleção') ---------
    #
    # Substitui o antigo fluxo "clica a caixinha ☐/✓ pra marcar uma
    # curva Y + eixo X sempre fixo em 'Tempo_decorrido_s'" (ver
    # docstring completa da mudança em callbacks.gerenciar_atribuicao_
    # eixos). Agora o próprio NOME da coluna, clicado na lista lateral,
    # é o alvo — a primeira coluna clicada vira X, as seguintes se
    # acumulam em Y, na ordem do clique (essa ordem também é a ordem
    # de cor/plotagem das curvas — ver colunas_plotadas, plotter.py).
    #
    # Uma coluna atribuída a X ou Y SOME da lista "Dados do arquivo"
    # (fica com status OCULTO, mesmo status que canais não-numéricos
    # já usavam por padrão — ver Arquivo.__post_init__) — ela só volta
    # a aparecer lá se for removida da seleção (remover_da_selecao_
    # eixos) ou excluída de vez (excluir_canal).

    def mover_para_eixo_x(self, nome_interno: str) -> None:
        """
        Atribui 'nome_interno' como o eixo X (substitui o anterior, se
        havia um — só existe UM X por vez; o antigo volta pra lista
        normal). Se a coluna já estava em Y, sai de lá primeiro (não
        faz sentido ser X e Y ao mesmo tempo).
        """
        if nome_interno not in self.canais or self.eixo_x_manual == nome_interno:
            return
        if nome_interno in self.eixos_y_manual:
            self.eixos_y_manual.remove(nome_interno)
        anterior = self.eixo_x_manual
        if anterior and anterior in self.canais:
            self.canais[anterior].restaurar()
        self.canais[nome_interno].ocultar()
        self.eixo_x_manual = nome_interno
        self.invalidar_grafico()

    def mover_para_eixo_y(self, nome_interno: str) -> None:
        """
        Acrescenta 'nome_interno' ao FIM da lista de curvas Y (ordem
        de clique = ordem de plotagem). Se a coluna já era o X, sai de
        lá primeiro. Não faz nada se já estiver em Y (evita duplicar
        com um clique repetido).
        """
        if nome_interno not in self.canais or nome_interno in self.eixos_y_manual:
            return
        if self.eixo_x_manual == nome_interno:
            self.eixo_x_manual = None
        self.canais[nome_interno].ocultar()
        self.eixos_y_manual.append(nome_interno)
        self.invalidar_grafico()

    def remover_da_selecao_eixos(self, nome_interno: str) -> None:
        """
        Tira 'nome_interno' de onde estiver (X ou Y) e devolve pra
        lista normal "Dados do arquivo" (status volta a VISIVEL) —
        contrapartida de mover_para_eixo_x/mover_para_eixo_y, chamada
        ao clicar num chip dentro da caixa X:/Y: (ver 'remover-eixo-
        selecionado' em callbacks.py).
        """
        mudou = False
        if self.eixo_x_manual == nome_interno:
            self.eixo_x_manual = None
            mudou = True
        if nome_interno in self.eixos_y_manual:
            self.eixos_y_manual.remove(nome_interno)
            mudou = True
        if mudou:
            if nome_interno in self.canais:
                self.canais[nome_interno].restaurar()
            self.invalidar_grafico()

    def nome_interno_livre(self, rotulo: str) -> str:
        """
        Nome de coluna interno (sem espaço/acento/símbolo) derivado de
        'rotulo' e que ainda não existe em df_editado: 'Potência (W)' ->
        'Potencia_W', e se já existir -> 'Potencia_W_2', '_3'...
        """
        base = sanitizar_rotulo_para_nome_coluna(rotulo)
        nome, sufixo = base, 1
        while nome in self.df_editado.columns:
            sufixo += 1
            nome = f'{base}_{sufixo}'
        return nome

    def adicionar_canal_calculado(self, rotulo: str, valores, formula: str) -> str:
        """
        Grava 'valores' como uma coluna NOVA em df_editado (nome interno
        único gerado a partir do rótulo) e registra o Canal como
        "calculado", com a fórmula guardada pra auditoria. O rótulo exibido
        continua sendo o texto livre digitado. Devolve o nome interno.

        Uma coluna nova nasce fora da seleção de eixos, então não mexe no
        gráfico já desenhado — quem chama decide se ela vai pra algum eixo.
        """
        nome = self.nome_interno_livre(rotulo)
        self.df_editado[nome] = valores
        self.registrar_canal(nome, rotulo=rotulo, origem="calculado", formula=formula)
        return nome

    def sobrescrever_canal_com_calculo(self, nome_interno: str, valores, formula: str) -> None:
        """
        Substitui os DADOS de uma coluna que já existe por 'valores' e marca
        o Canal como "calculado" (com a fórmula). O rótulo não muda. Invalida
        o cache da figura: a coluna pode estar desenhada no gráfico.
        """
        if nome_interno not in self.df_editado.columns:
            raise KeyError(f"Coluna '{nome_interno}' não existe em df_editado.")
        self.df_editado[nome_interno] = valores
        canal = self.canais.get(nome_interno) or self.registrar_canal(nome_interno)
        canal.origem = "calculado"
        canal.formula = formula
        self.invalidar_grafico()

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
