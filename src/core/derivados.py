"""
Dados derivados da Nova Amostragem: séries com X próprio e a árvore de
proveniência.

Por que não uma coluna a mais no df_editado?
    Um downsampling de 'Pressão' tem 500 pontos; a tabela tem 10.000.
    Preencher o resto com None daria a falsa ideia de que os dois estão
    alinhados ponto a ponto. Uma Serie guarda o SEU x e o SEU y, do
    tamanho que tiverem.

A árvore
    Cada NoDerivado lembra de onde veio (canal raiz + eixo X, ou o nó pai),
    que operação foi aplicada, com quais parâmetros, e o resultado. Um nó
    pode ser origem de outra operação, formando a cadeia
        Pressão -> Média móvel -> Polynomial Fit -> ...

    Desatualização: o nó guarda a VERSÃO das colunas de origem (X e Y do
    canal raiz) no momento do OK. Se depois o usuário apara/exclui dados ou
    sobrescreve o canal pela calculadora, a versão muda e o nó (e toda a
    cadeia abaixo dele) aparece como desatualizado. O resultado guardado
    não é recalculado sozinho; o usuário escolhe (ver Arquivo):
      - Recalcular: refaz a cadeia na mesma sequência, com os mesmos
        parâmetros. Para no primeiro nó que não dá pra refazer (erro, ou
        Δx a revisar porque o próprio X foi reescrito) — RelatorioRecalculo.
      - Manter: aceita os resultados como estão; o alerta some.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ============================================================================
# Serie
# ============================================================================

@dataclass(frozen=True, eq=False)
class Serie:
    """
    Pares (x, y) com tamanho próprio, ordenados por x. 'sigma' (opcional)
    é a incerteza de cada y — ex: desvio padrão da janela na média móvel.
    """
    x: np.ndarray
    y: np.ndarray
    sigma: np.ndarray | None = None

    def __post_init__(self):
        x = np.asarray(self.x, dtype=float)
        y = np.asarray(self.y, dtype=float)
        if x.shape != y.shape or x.ndim != 1:
            raise ValueError(f'x e y precisam ser vetores do mesmo tamanho ({x.shape} != {y.shape}).')
        object.__setattr__(self, 'x', x)
        object.__setattr__(self, 'y', y)
        if self.sigma is not None:
            sigma = np.asarray(self.sigma, dtype=float)
            if sigma.shape != x.shape:
                raise ValueError('sigma precisa ter o mesmo tamanho de x e y.')
            object.__setattr__(self, 'sigma', sigma)

    def __len__(self):
        return len(self.x)

    @property
    def vazia(self) -> bool:
        return len(self.x) == 0

    @classmethod
    def de_colunas(cls, df: pd.DataFrame, coluna_x: str, coluna_y: str) -> 'Serie':
        """
        Série (x, y) a partir de duas colunas de uma tabela: converte pra
        número, descarta as linhas em que x OU y não é número e ordena por
        x (ordenação estável: empates mantêm a ordem da tabela).
        """
        for coluna in (coluna_x, coluna_y):
            if coluna not in df.columns:
                raise KeyError(f"A coluna '{coluna}' não existe nos dados.")
        x = pd.to_numeric(df[coluna_x], errors='coerce').to_numpy(dtype=float)
        y = pd.to_numeric(df[coluna_y], errors='coerce').to_numpy(dtype=float)
        validos = np.isfinite(x) & np.isfinite(y)
        x, y = x[validos], y[validos]
        ordem = np.argsort(x, kind='stable')
        return cls(x[ordem], y[ordem])


# ============================================================================
# Árvore
# ============================================================================

@dataclass
class NoDerivado:
    """
    Um resultado registrado (botão OK) da Nova Amostragem.

    canal_raiz      canal Y onde a cadeia começa (nome interno)
    eixo_x          canal X usado quando a cadeia começou (nome interno)
    pai             id do nó de origem; None = veio direto do canal raiz
    operacao        chave da operação (ver src/core/operations/amostragem.py)
    parametros      o que o usuário configurou (reabre o painel igual)
    serie           o resultado
    info            extras do resultado: coeficientes, R², janelas vazias...
    versoes_origem  versão de cada coluna de origem no momento do OK
    reescritas_x    quantas vezes a coluna X tinha sido REESCRITA (calculadora)
                    no momento do OK — se mudar, parâmetros na unidade de X
                    (Δx) precisam de revisão antes de recalcular
    canal           nome interno do canal criado pelo 'Add' (None = não virou canal)
    """
    id: str
    nome: str
    canal_raiz: str
    eixo_x: str
    pai: str | None
    operacao: str
    parametros: dict
    serie: Serie
    info: dict = field(default_factory=dict)
    versoes_origem: dict = field(default_factory=dict)
    reescritas_x: int = 0
    canal: str | None = None
    visivel: bool = False     # olho da árvore: desenhado no gráfico?


class DerivadoDuplicado(ValueError):
    """
    OK de uma análise que já existe: mesma origem (canal/X ou nó pai),
    mesma operação e mesmos parâmetros. 'existente' é o nó que já está lá.
    """
    def __init__(self, existente: 'NoDerivado'):
        super().__init__(f"Essa análise já existe: '{existente.nome}'.")
        self.existente = existente


def parametros_iguais(a: dict, b: dict) -> bool:
    """Mesmos nomes e mesmos valores (60 == 60.0; 0.4 ≈ 0.4000000001)."""
    if set(a) != set(b):
        return False
    for nome in a:
        va, vb = a[nome], b[nome]
        try:
            if not math.isclose(float(va), float(vb), rel_tol=1e-9, abs_tol=1e-12):
                return False
        except (TypeError, ValueError):
            if va != vb:
                return False
    return True


@dataclass(frozen=True)
class PreviewAmostragem:
    """
    Resultado MOSTRADO no gráfico mas ainda não registrado (botão Preview).
    Não entra na árvore; some ao trocar de operação ou desligar o modo.
    'parametros' e a origem ficam juntos pro OK registrar exatamente o que
    está sendo visto.
    """
    operacao: str
    parametros: dict
    canal_y: str
    eixo_x: str
    serie: Serie
    info: dict
    pai: str | None = None


# Parâmetros medidos na unidade do eixo X: se o X for reescrito (ex: s -> min),
# o mesmo número passa a significar outra coisa.
PARAMETROS_NA_UNIDADE_DE_X = {'delta_x': 'Δx'}   # nome interno -> como aparece nas mensagens


@dataclass
class PendenciaRecalculo:
    """
    Nó em que o Recalcular parou.
    motivo: 'revisar' (Δx na unidade de um X que foi reescrito: o usuário
            confere antes) | 'erro' (a operação falhou com os parâmetros
            antigos, ex: pontos insuficientes depois de um corte).
    """
    id: str
    motivo: str
    mensagem: str


@dataclass
class RelatorioRecalculo:
    recalculados: list = field(default_factory=list)   # ids refeitos com sucesso
    pendencias: list = field(default_factory=list)     # [PendenciaRecalculo]
    aguardando: list = field(default_factory=list)     # ids abaixo de uma pendência (não tocados)

    @property
    def concluido(self) -> bool:
        return not self.pendencias


class ArvoreDerivados:
    """
    Os nós derivados de UM arquivo. Guarda a ordem de criação (a mesma
    usada pra listar irmãos na interface).
    """

    def __init__(self):
        self._nos: dict[str, NoDerivado] = {}
        self._proximo_id = 1

    def __len__(self):
        return len(self._nos)

    def __contains__(self, id_no):
        return id_no in self._nos

    def __iter__(self):
        return iter(self._nos.values())

    def no(self, id_no: str) -> NoDerivado:
        try:
            return self._nos[id_no]
        except KeyError:
            raise KeyError(f"Nó derivado '{id_no}' não existe.") from None

    def novo_id(self) -> str:
        id_no = f'd{self._proximo_id}'
        self._proximo_id += 1
        return id_no

    def adicionar(self, no: NoDerivado) -> NoDerivado:
        if no.id in self._nos:
            raise ValueError(f"Já existe um nó com id '{no.id}'.")
        if no.pai is not None:
            pai = self.no(no.pai)
            if pai.canal_raiz != no.canal_raiz:
                raise ValueError('O nó filho precisa ter o mesmo canal raiz do pai.')
        self._nos[no.id] = no
        return no

    def filhos(self, id_pai: str | None, canal_raiz: str | None = None) -> list[NoDerivado]:
        """
        Filhos diretos de um nó. Com id_pai=None, os nós que saem direto
        de um canal — aí 'canal_raiz' diz de qual.
        """
        return [
            no for no in self._nos.values()
            if no.pai == id_pai and (id_pai is not None or no.canal_raiz == canal_raiz)
        ]

    def canais_com_derivados(self) -> list[str]:
        vistos = []
        for no in self._nos.values():
            if no.canal_raiz not in vistos:
                vistos.append(no.canal_raiz)
        return vistos

    def ancestrais(self, id_no: str) -> list[NoDerivado]:
        """O caminho do nó até o topo: [nó, pai, avô, ...]."""
        caminho = []
        atual = self.no(id_no)
        while atual is not None:
            caminho.append(atual)
            atual = self._nos.get(atual.pai) if atual.pai else None
        return caminho

    def descendentes(self, id_no: str) -> list[NoDerivado]:
        """Todos os nós abaixo de 'id_no' (sem incluir ele), em profundidade."""
        resultado = []
        for filho in self.filhos(id_no):
            resultado.append(filho)
            resultado.extend(self.descendentes(filho.id))
        return resultado

    def excluir(self, id_no: str) -> list[str]:
        """Remove o nó e tudo abaixo dele. Devolve os ids removidos."""
        removidos = [self.no(id_no)] + self.descendentes(id_no)
        for no in removidos:
            del self._nos[no.id]
        return [no.id for no in removidos]
