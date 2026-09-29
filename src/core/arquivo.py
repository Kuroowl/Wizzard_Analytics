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

import numpy as np
import pandas as pd

from src.core.derivados import (
    OPERACAO_CALCULADORA, PARAMETROS_NA_UNIDADE_DE_X, ArvoreDerivados, CanalDerivado, DerivadoDuplicado, NoDerivado,
    PendenciaRecalculo, PreviewAmostragem, RelatorioRecalculo, Serie, parametros_iguais,
)
from src.core.operations.amostragem import ResultadoAmostragem, executar_operacao, nome_padrao
from src.core.operations.calculadora import analises_da_expressao, avaliar_com_series
from src.core.operations.sampling import aparar_dados, excluir_dados
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

    # --- Nova Amostragem ----------------------------------------------
    # 'arvore': os resultados registrados (OK) e de onde vieram — ver
    # src/core/derivados.py. 'versoes_colunas': quantas vezes os DADOS de
    # cada coluna mudaram (corte, sobrescrita pela calculadora); é assim
    # que um nó sabe que ficou desatualizado. Coluna ausente = versão 0.
    # 'reescritas_colunas': só as sobrescritas pela calculadora (o valor
    # muda de significado, ex: s -> min), separadas dos cortes (o valor
    # continua o mesmo, só some um trecho).
    arvore: ArvoreDerivados = field(default_factory=ArvoreDerivados)
    versoes_colunas: dict = field(default_factory=dict)
    reescritas_colunas: dict = field(default_factory=dict)
    # Preview da Nova Amostragem em exibição (None = nenhum). Estado de
    # tela, não de dados: o plotter desenha por cima das curvas enquanto
    # existir. Ver gerar_preview_amostragem / limpar_preview_amostragem.
    preview_amostragem: PreviewAmostragem | None = None
    # Análises que viraram canal (Add): pares (x', y') fora do df_editado,
    # e quais delas estão no eixo Y do gráfico (na ordem do clique).
    canais_derivados: dict = field(default_factory=dict)
    eixos_y_derivados: list = field(default_factory=list)

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
        self._dados_alterados([nome_interno])
        self.reescritas_colunas[nome_interno] = self.reescritas_colunas.get(nome_interno, 0) + 1
        self.invalidar_grafico()

    # --- Corte de dados (Aparar / Excluir) ---------------------------

    def cortar_dados(self, eixo_x: str, limite_a, limite_b, modo: str = 'aparar') -> None:
        """
        'aparar': mantém só o trecho entre os limites; 'excluir': remove o
        trecho. Os limites podem vir em qualquer ordem (são os dois cliques
        no gráfico). Todas as colunas mudam — derivados ficam desatualizados.
        """
        if modo not in ('aparar', 'excluir'):
            raise ValueError(f"modo deve ser 'aparar' ou 'excluir', não {modo!r}.")
        minimo, maximo = sorted((limite_a, limite_b))
        cortar = excluir_dados if modo == 'excluir' else aparar_dados
        self.df_editado = cortar(self.df_editado, eixo_x, minimo, maximo)
        self._dados_alterados(self.df_editado.columns)
        self.preview_amostragem = None     # calculado sobre os dados de antes do corte
        self.invalidar_grafico()

    def _dados_alterados(self, colunas) -> None:
        for coluna in colunas:
            self.versoes_colunas[coluna] = self.versoes_colunas.get(coluna, 0) + 1

    # --- Nova Amostragem: séries e árvore de derivados ---------------

    def serie_do_canal(self, canal_y: str, eixo_x: str) -> Serie:
        """Os dados ATUAIS (df_editado) de um canal contra um eixo X, como Serie."""
        return Serie.de_colunas(self.df_editado, eixo_x, canal_y)

    def serie_de_origem(self, canal_y: str, eixo_x: str, id_no: str | None = None) -> Serie:
        """
        Entrada de uma operação: o resultado do nó 'id_no', ou (id_no=None)
        o canal 'canal_y' contra 'eixo_x'.
        """
        if id_no is not None:
            return self.arvore.no(id_no).serie
        return self.serie_do_canal(canal_y, eixo_x)

    def gerar_preview_amostragem(self, operacao: str, parametros: dict, canal_y: str,
                                 eixo_x: str, pai: str | None = None) -> PreviewAmostragem:
        """
        Botão Preview: roda a operação sobre os dados ATUAIS da origem (canal
        contra o X, ou o nó 'pai') e guarda o resultado pra ser desenhado.
        Não mexe na árvore. Erros de parâmetro/dados: ValueError (o preview
        anterior continua).
        """
        if pai is not None:
            no_pai = self.arvore.no(pai)
            canal_y, eixo_x = no_pai.canal_raiz, no_pai.eixo_x
        resultado = executar_operacao(operacao, self.serie_de_origem(canal_y, eixo_x, pai), parametros)
        self.preview_amostragem = PreviewAmostragem(
            operacao=operacao, parametros=dict(parametros), canal_y=canal_y, eixo_x=eixo_x,
            serie=resultado.serie, info=dict(resultado.info), pai=pai,
        )
        self.invalidar_grafico()
        return self.preview_amostragem

    def registrar_preview_amostragem(self, nome: str | None = None) -> NoDerivado:
        """
        Botão OK: o preview em exibição vira um nó da árvore (mesma origem,
        operação, parâmetros e resultado) e sai do gráfico.
        """
        preview = self.preview_amostragem
        if preview is None:
            raise ValueError('Não há preview para registrar.')
        no = self.registrar_derivado(
            preview.operacao, preview.parametros, ResultadoAmostragem(preview.serie, preview.info),
            preview.canal_y, preview.eixo_x, pai=preview.pai, nome=nome,
        )
        self.limpar_preview_amostragem()
        return no

    def limpar_preview_amostragem(self, invalidar_grafico: bool = True) -> bool:
        """
        Tira o preview do gráfico. True se havia um. Por padrão invalida a
        figura (quem chama redesenha); 'invalidar_grafico=False' quando a
        figura em cache já não mostra o preview (ex: o X mudou).
        """
        if self.preview_amostragem is None:
            return False
        self.preview_amostragem = None
        if invalidar_grafico:
            self.invalidar_grafico()
        return True

    def rotulo_origem(self, canal_y: str, id_no: str | None = None) -> str:
        return self.arvore.no(id_no).nome if id_no is not None else self.rotulo(canal_y)

    def registrar_derivado(self, operacao: str, parametros: dict, resultado: ResultadoAmostragem,
                           canal_y: str, eixo_x: str, pai: str | None = None,
                           nome: str | None = None) -> NoDerivado:
        """
        Botão OK: guarda o resultado na árvore. Com 'pai', o nó é filho de
        outro nó (e herda dele o canal raiz e o eixo X); sem, sai direto do
        canal 'canal_y' contra 'eixo_x'.

        A mesma análise (mesma origem, operação e parâmetros) não entra duas
        vezes: DerivadoDuplicado, com o nó que já existe.
        """
        if pai is not None:
            no_pai = self.arvore.no(pai)
            canal_y, eixo_x = no_pai.canal_raiz, no_pai.eixo_x
        existente = self.derivado_equivalente(operacao, parametros, canal_y, eixo_x, pai)
        if existente is not None:
            raise DerivadoDuplicado(existente)
        no = NoDerivado(
            id=self.arvore.novo_id(),
            nome=nome or self._nome_livre(nome_padrao(operacao, self.rotulo_origem(canal_y, pai))),
            canal_raiz=canal_y,
            eixo_x=eixo_x,
            pai=pai,
            operacao=operacao,
            parametros=dict(parametros),
            serie=resultado.serie,
            info=dict(resultado.info),
        )
        self._carimbar(no)
        return self.arvore.adicionar(no)

    def _nome_livre(self, base: str) -> str:
        """'Downsampling sinal' -> 'Downsampling sinal (2)', '(3)'... se já existir."""
        usados = {no.nome for no in self.arvore}
        nome, n = base, 1
        while nome in usados:
            n += 1
            nome = f'{base} ({n})'
        return nome

    def derivado_equivalente(self, operacao: str, parametros: dict, canal_y: str, eixo_x: str,
                             pai: str | None = None) -> NoDerivado | None:
        """O nó que já tem esta mesma origem, operação e parâmetros (ou None)."""
        for no in self.arvore.filhos(pai, canal_y):
            if (no.operacao == operacao and no.canal_raiz == canal_y and no.eixo_x == eixo_x
                    and parametros_iguais(no.parametros, parametros)):
                return no
        return None

    def renomear_derivado(self, id_no: str, nome: str) -> None:
        nome = (nome or '').strip()
        if not nome:
            raise ValueError('O nome da análise não pode ficar vazio.')
        self.arvore.no(id_no).nome = nome
        self.invalidar_grafico()      # o nome aparece na legenda se estiver visível

    def sair_da_amostragem(self, invalidar_grafico: bool = True) -> bool:
        """
        Ao sair do modo Nova Amostragem, tudo que é ferramenta dele sai do
        gráfico: o preview e as análises com o olho aceso (o olho apaga).
        True se havia algo desenhado (o gráfico precisa ser redesenhado).
        """
        havia = self.preview_amostragem is not None or any(no.visivel for no in self.arvore)
        self.preview_amostragem = None
        for no in self.arvore:
            no.visivel = False
        if havia and invalidar_grafico:
            self.invalidar_grafico()
        return havia

    def alternar_visibilidade_derivado(self, id_no: str) -> bool:
        """Olho da árvore: liga/desliga o desenho do nó no gráfico. Devolve o novo estado."""
        no = self.arvore.no(id_no)
        no.visivel = not no.visivel
        self.invalidar_grafico()
        return no.visivel

    def _carimbar(self, no: NoDerivado) -> None:
        """Marca o nó como calculado sobre os dados ATUAIS da origem."""
        no.versoes_origem = {c: self.versoes_colunas.get(c, 0) for c in (no.eixo_x, no.canal_raiz)}
        no.reescritas_x = self.reescritas_colunas.get(no.eixo_x, 0)

    def _origem_mudou(self, no: NoDerivado) -> bool:
        return any(self.versoes_colunas.get(c, 0) != v for c, v in no.versoes_origem.items())

    def _x_reescrito(self, no: NoDerivado) -> bool:
        return self.reescritas_colunas.get(no.eixo_x, 0) != no.reescritas_x

    def derivado_desatualizado(self, id_no: str) -> bool:
        """
        True se os dados de origem mudaram depois do OK deste nó ou de
        qualquer nó acima dele (um filho de um nó velho também é velho).
        """
        return any(self._origem_mudou(no) for no in self.arvore.ancestrais(id_no))

    def derivado_compativel_com_x(self, id_no: str, eixo_x: str) -> bool:
        """
        Um derivado só pode ser exibido num gráfico cujo X é o MESMO canal
        de onde ele veio (senão os pontos não casam). Com X diferente, a
        interface mostra o nó acinzentado ('calculado com X = ...').
        """
        return self.arvore.no(id_no).eixo_x == eixo_x

    def manter_derivado(self, id_no: str) -> list[str]:
        """
        'Manter': o usuário aceita o resultado como está, mesmo com a
        origem alterada — o alerta some. Vale pra cadeia inteira que passa
        pelo nó (acima: a origem dele; abaixo: o que saiu dele). Nada é
        recalculado. Devolve os ids afetados.
        """
        grupo = self.arvore.ancestrais(id_no) + self.arvore.descendentes(id_no)
        for no in grupo:
            self._carimbar(no)
        return [no.id for no in grupo]

    def recalcular_derivado(self, id_no: str, parametros: dict | None = None) -> RelatorioRecalculo:
        """
        'Recalcular': refaz a cadeia sobre os dados ATUAIS, na mesma
        sequência e com os mesmos parâmetros.

        Começa nos nós desatualizados MAIS ALTOS acima de 'id_no' (ou no
        próprio nó) e desce por todos os que saíram deles. Uma análise só é
        refeita depois de TODAS as suas origens (as da calculadora podem ter
        várias). Em cada nó:
          - se a operação usa Δx e o X foi REESCRITO desde o OK, para ali
            com uma pendência 'revisar' (o mesmo número pode ter mudado de
            significado);
          - se a operação falha com os parâmetros antigos, para ali com uma
            pendência 'erro' e o resultado antigo fica.
        Os nós abaixo de uma pendência — ou com outra origem ainda
        desatualizada fora desta cadeia — ficam 'aguardando', intocados; os
        outros ramos seguem. Pra continuar, o usuário ajusta e chama de novo
        com 'parametros' (novos parâmetros do nó 'id_no').
        """
        alvo = self.arvore.no(id_no)
        ancestrais = self.arvore.ancestrais(id_no)
        desatualizados = {no.id for no in ancestrais if self._origem_mudou(no)}
        ordem_criacao = [no.id for no in self.arvore]
        inicios = sorted((no for no in ancestrais
                          if no.id in desatualizados and not any(p in desatualizados for p in no.pais)),
                         key=lambda no: ordem_criacao.index(no.id)) or [alvo]
        ordem = []
        for inicio in inicios:
            for no in [inicio] + self.arvore.descendentes(inicio.id):
                if no not in ordem:
                    ordem.append(no)
        no_conjunto = {no.id for no in ordem}
        novos = {id_no: dict(parametros)} if parametros is not None else {}
        relatorio = RelatorioRecalculo()
        feitos, parados = set(), set()

        def processar(no):
            parametros_no = novos.get(no.id, no.parametros)
            if no.id not in novos and self._x_reescrito(no):
                em_x = [p for p in PARAMETROS_NA_UNIDADE_DE_X if p in parametros_no]
                if em_x:
                    valores = ', '.join(f'{PARAMETROS_NA_UNIDADE_DE_X[p]} = {parametros_no[p]}' for p in em_x)
                    relatorio.pendencias.append(PendenciaRecalculo(
                        no.id, 'revisar',
                        f"O eixo X '{self.rotulo(no.eixo_x)}' foi reescrito. Confira {valores} "
                        f"(está na unidade de X) antes de recalcular '{no.nome}'."))
                    return False
            try:
                resultado = self._refazer(no, parametros_no)
            except (ValueError, KeyError) as erro:
                texto = erro.args[0] if erro.args else str(erro)
                relatorio.pendencias.append(PendenciaRecalculo(
                    no.id, 'erro', f"Não deu pra recalcular '{no.nome}': {texto}"))
                return False
            no.serie = resultado.serie
            no.info = dict(resultado.info)
            no.parametros = dict(parametros_no)
            self._carimbar(no)
            canal = self.canal_da_analise(no.id)
            if canal is not None:          # o canal (Add) acompanha a análise
                canal.serie = no.serie
            relatorio.recalculados.append(no.id)
            return True

        pendentes = list(ordem)
        while pendentes:
            avancou = False
            for no in list(pendentes):
                pais_na_cadeia = [p for p in no.pais if p in no_conjunto]
                if any(p in parados for p in pais_na_cadeia) or any(
                        self.derivado_desatualizado(p) for p in no.pais if p not in no_conjunto):
                    parados.add(no.id)                 # espera a origem que parou (ou que está fora)
                    relatorio.aguardando.append(no.id)
                elif all(p in feitos for p in pais_na_cadeia):
                    (feitos if processar(no) else parados).add(no.id)
                else:
                    continue                            # ainda falta uma origem desta cadeia
                pendentes.remove(no)
                avancou = True
            if not avancou:
                break
        return relatorio

    def _refazer(self, no: NoDerivado, parametros: dict) -> ResultadoAmostragem:
        """A operação do nó, de novo, sobre os resultados atuais de onde ele saiu."""
        if no.operacao == OPERACAO_CALCULADORA:
            refs = parametros['refs']
            if any(id_origem not in self.arvore for id_origem in refs.values()):
                raise ValueError('uma das análises de origem não existe mais.')
            series = {nome: self.arvore.no(id_origem).serie for nome, id_origem in refs.items()}
            rotulos = {nome: self.arvore.no(id_origem).nome for nome, id_origem in refs.items()}
            x, y = avaliar_com_series(parametros['expressao'], series, self, None, rotulos)
            return ResultadoAmostragem(Serie(x, y), {'n_obtido': len(x)})
        entrada = self.arvore.no(no.pai).serie if no.pai else self.serie_do_canal(no.canal_raiz, no.eixo_x)
        return executar_operacao(no.operacao, entrada, parametros)

    # --- Análises da calculadora (combinam análises da árvore) --------

    def origens_da_expressao(self, codigo: str) -> dict | None:
        """
        {nome usado na expressão: id da análise da árvore} de uma expressão
        de análises (der/derx), ou None se alguma delas não está ligada a
        uma análise da árvore (foi criada/editada na calculadora e ficou
        desvinculada) ou se elas vêm de X diferentes — nesses casos o
        resultado não entra na árvore, fica só em 'Análises do arquivo'.
        """
        refs = {}
        for nome in analises_da_expressao(codigo):
            canal = self.canais_derivados.get(nome)
            if canal is None or not canal.vinculado or canal.no_origem not in self.arvore:
                return None
            refs[nome] = canal.no_origem
        if not refs:
            return None
        if len({self.arvore.no(i).eixo_x for i in refs.values()}) != 1:
            return None
        return refs

    def registrar_analise_calculada(self, nome: str, codigo: str, exibida: str, refs: dict,
                                    x, y) -> NoDerivado:
        """
        Resultado da calculadora sobre análises da árvore: vira um nó cujas
        ORIGENS são todas elas (pai = a primeira, outros_pais = as demais) —
        'média A + média B' sai de A e de B. Refaz a conta no Recalcular.
        DerivadoDuplicado se a mesma conta sobre as mesmas origens já existe.
        """
        ids = list(dict.fromkeys(refs.values()))
        primeiro = self.arvore.no(ids[0])
        parametros = {'expressao': codigo, 'exibida': exibida, 'refs': dict(refs)}
        # A mesma conta sobre as mesmas origens (o texto exibido pode variar).
        existente = next((n for n in self.arvore.filhos(primeiro.id)
                          if n.operacao == OPERACAO_CALCULADORA and n.parametros.get('expressao') == codigo
                          and n.parametros.get('refs') == dict(refs)), None)
        if existente is not None:
            raise DerivadoDuplicado(existente)
        no = NoDerivado(
            id=self.arvore.novo_id(),
            nome=self._nome_livre((nome or '').strip() or 'Calculada'),
            canal_raiz=primeiro.canal_raiz, eixo_x=primeiro.eixo_x,
            pai=primeiro.id, outros_pais=ids[1:],
            operacao=OPERACAO_CALCULADORA, parametros=parametros,
            serie=Serie(np.asarray(x, dtype=float), np.asarray(y, dtype=float)),
            info={'n_obtido': len(x)},
        )
        self._carimbar(no)
        return self.arvore.adicionar(no)

    def excluir_derivado(self, id_no: str) -> list[str]:
        """
        Remove o nó e todos os que saíram dele. Devolve os ids removidos.
        Canais que vieram deles (Add) continuam, desvinculados.
        """
        removidos = self.arvore.excluir(id_no)
        for canal in self.canais_derivados.values():
            if canal.no_origem in removidos:
                canal.no_origem = None
        return removidos

    # --- Análises que viraram canal (Add) ------------------------------

    def canal_derivado(self, nome: str) -> CanalDerivado:
        try:
            return self.canais_derivados[nome]
        except KeyError:
            raise KeyError(f"Análise '{nome}' não existe em 'Análises do arquivo'.") from None

    def canal_da_analise(self, id_no: str) -> CanalDerivado | None:
        """O canal (Add) ligado a esta análise, se houver."""
        return next((c for c in self.canais_derivados.values() if c.no_origem == id_no), None)

    def adicionar_canal_derivado(self, id_no: str) -> CanalDerivado:
        """
        Botão Add: a análise vira um canal (x', y') em 'Análises do arquivo'.
        Uma análise vira canal uma vez só (ValueError se já virou).
        """
        no = self.arvore.no(id_no)
        existente = self.canal_da_analise(id_no)
        if existente is not None:
            raise ValueError(f"'{no.nome}' já está em Análises do arquivo como '{existente.rotulo}'.")
        canal = CanalDerivado(nome=self._nome_canal_derivado_livre(), rotulo=no.nome, serie=no.serie,
                              eixo_x=no.eixo_x, canal_raiz=no.canal_raiz, no_origem=id_no)
        self.canais_derivados[canal.nome] = canal
        no.canal = canal.nome
        return canal

    def _nome_canal_derivado_livre(self) -> str:
        n = 1
        while f'analise_{n}' in self.canais_derivados:
            n += 1
        return f'analise_{n}'

    def adicionar_canal_derivado_calculado(self, rotulo: str, x, y, eixo_x: str, canal_raiz: str,
                                           formula: str) -> CanalDerivado:
        """
        Calculadora com análises (x', y'): o resultado vira um par NOVO em
        'Análises do arquivo', com o x' de onde veio. Não está ligado a
        nenhuma análise da árvore.
        """
        rotulo = (rotulo or '').strip()
        if not rotulo:
            raise ValueError('Dê um nome pra essa análise antes de criar.')
        canal = CanalDerivado(nome=self._nome_canal_derivado_livre(), rotulo=rotulo,
                              serie=Serie(np.asarray(x, dtype=float), np.asarray(y, dtype=float)),
                              eixo_x=eixo_x, canal_raiz=canal_raiz, formula=formula)
        self.canais_derivados[canal.nome] = canal
        return canal

    def sobrescrever_canal_derivado(self, nome: str, eixo: str, valores, formula: str) -> CanalDerivado:
        """
        Calculadora: substitui o y' (eixo='y') ou o x' (eixo='x') de um par.
        O par deixa de acompanhar a análise de origem (DESVINCULADO): o que
        está nele agora foi editado à mão, e um Recalcular não pode apagar
        isso. Reescrever o x' marca 'x_editado'.
        """
        canal = self.canal_derivado(nome)
        if eixo not in ('x', 'y'):
            raise ValueError("eixo deve ser 'x' ou 'y'.")
        valores = np.asarray(valores, dtype=float)
        if len(valores) != len(canal.serie):
            raise ValueError(f"o resultado tem {len(valores)} pontos e '{canal.rotulo}' tem {len(canal.serie)}.")
        x = valores if eixo == 'x' else canal.serie.x
        y = valores if eixo == 'y' else canal.serie.y
        canal.serie = Serie(x, y)          # sem σ: ele era da análise de origem
        if canal.no_origem in self.arvore:
            self.arvore.no(canal.no_origem).canal = None
        canal.no_origem = None
        canal.formula = formula
        if eixo == 'x':
            canal.x_editado = True
        if nome in self.eixos_y_derivados:
            self.invalidar_grafico()
        return canal

    def renomear_canal_derivado(self, nome: str, rotulo: str) -> None:
        rotulo = (rotulo or '').strip()
        if not rotulo:
            raise ValueError('O nome não pode ficar vazio.')
        self.canal_derivado(nome).rotulo = rotulo
        if nome in self.eixos_y_derivados:
            self.invalidar_grafico()      # a legenda mostra o nome

    def excluir_canal_derivado(self, nome: str) -> CanalDerivado:
        """Tira o canal de 'Análises do arquivo' (a análise da árvore continua)."""
        canal = self.canais_derivados.pop(self.canal_derivado(nome).nome)
        if nome in self.eixos_y_derivados:
            self.eixos_y_derivados.remove(nome)
            self.invalidar_grafico()
        if canal.no_origem in self.arvore:
            self.arvore.no(canal.no_origem).canal = None
        return canal

    def mover_derivado_para_y(self, nome: str) -> None:
        """
        Põe o canal (x', y') no eixo Y. Só com o MESMO X de onde ele veio no
        gráfico (senão os pontos não casam): ValueError explicando.
        """
        canal = self.canal_derivado(nome)
        if self.eixo_x_manual is None:
            raise ValueError(f"Escolha o eixo X do gráfico antes: '{canal.rotulo}' "
                             f"precisa de X = '{self.rotulo(canal.eixo_x)}'.")
        if self.eixo_x_manual != canal.eixo_x:
            raise ValueError(f"'{canal.rotulo}' foi calculada com X = '{self.rotulo(canal.eixo_x)}': "
                             f"só pode ser vista com esse X no gráfico.")
        if nome not in self.eixos_y_derivados:
            self.eixos_y_derivados.append(nome)
            self.invalidar_grafico()

    def remover_derivado_do_y(self, nome: str) -> None:
        if nome in self.eixos_y_derivados:
            self.eixos_y_derivados.remove(nome)
            self.invalidar_grafico()

    def canal_derivado_desatualizado(self, nome: str) -> bool:
        """Ligado a uma análise cuja origem mudou (⚠ até Recalcular/Manter)."""
        canal = self.canal_derivado(nome)
        return canal.vinculado and canal.no_origem in self.arvore \
            and self.derivado_desatualizado(canal.no_origem)

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
