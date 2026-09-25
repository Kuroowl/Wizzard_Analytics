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
    não é recalculado sozinho.
"""

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
    canal: str | None = None


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
