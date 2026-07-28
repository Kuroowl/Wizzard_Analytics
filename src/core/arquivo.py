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
    """Como UM canal específico aparece no gráfico."""
    cor: str | None = None
    espessura: float = 2.0
    estilo_linha: str = "solid"  # "solid" | "dash" | "dot" | "dashdot"


@dataclass
class PreferenciasGrafico:
    """Como o gráfico inteiro aparece: eixos, limites, título."""
    titulo: str | None = None
    titulo_eixo_x: str | None = None
    titulo_eixo_y: str | None = None
    limite_x: tuple | None = None
    limite_y: tuple | None = None
    por_canal: dict[str, PreferenciasCanal] = field(default_factory=dict)

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
