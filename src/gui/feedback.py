"""
Feedback — o contrato entre os callbacks e a mensagem do mago.

Um callback NÃO escreve mais em 'rodape-status' nem mexe no timer da
mensagem temporária. Ele só diz O QUE aconteceu:

    from src.gui.feedback import Feedback, saida_feedback

    @app.callback(
        ...,
        saida_feedback('eixos'),          # <- canal próprio deste callback
        ...
    )
    def gerenciar_atribuicao_eixos(...):
        ...
        return ..., Feedback.sucesso(f"Canal '{rotulo}' excluído."), ...

e o rodapé (src/gui/rodape.py, 'apresentar_feedback') decide COMO isso
aparece: fala do mago, classe CSS por tipo, timer, mensagem seguinte.

Por que um canal (dcc.Store) por callback?
    É o que elimina o 'allow_duplicate=True' de 'rodape-status': cada
    Store tem exatamente UM escritor, e o apresentador escuta todos de
    uma vez via padrão coringa. Se dois callbacks tentarem usar a mesma
    origem, o próprio Dash acusa Output duplicado na inicialização — o
    erro aparece na hora, não como uma mensagem sobrescrita em runtime.

Pra adicionar um callback novo que fala com o usuário (ex: Nova
Amostragem): acrescente a origem em ORIGENS_FEEDBACK e use
'saida_feedback(<origem>)' como Output. Só isso.
"""
import itertools
from dataclasses import dataclass, field
from typing import Optional

from dash import Output


# ============================================================================
# Origens (um canal por callback escritor)
# ============================================================================

ORIGENS_FEEDBACK = (
    'upload',
    'abas',
    'calculadora',
    'eixos',
    'edicao-canal',
    'grafico-gerar',
    'grafico-fechar',
    'corte-iniciar',
    'corte-clique',
    'corte-confirmar',
    'corte-cancelar',
)

TIPO_STORE_FEEDBACK = 'feedback'


def id_feedback(origem):
    """Id (padrão coringa) do dcc.Store de feedback de uma origem."""
    if origem not in ORIGENS_FEEDBACK:
        raise ValueError(
            f"Origem de feedback desconhecida: {origem!r}. "
            f"Registre-a em ORIGENS_FEEDBACK (src/gui/feedback.py).")
    return {'type': TIPO_STORE_FEEDBACK, 'origem': origem}


def saida_feedback(origem):
    """Output que um callback usa pra emitir um Feedback."""
    return Output(id_feedback(origem), 'data')


# ============================================================================
# Contrato
# ============================================================================

TIPOS_FEEDBACK = ('info', 'sucesso', 'aviso', 'erro', 'instrucao')

# Ordem de emissão. Serve pra dois propósitos: (1) garantir que o 'data'
# do Store SEMPRE muda, mesmo repetindo a mesma mensagem (senão o
# apresentador não dispara), e (2) desempatar quando dois canais mudam
# na mesma rodada — vence o mais recente.
_sequencia = itertools.count(1)


@dataclass(frozen=True)
class Feedback:
    """
    O que o mago deve dizer.

    texto       Texto PURO, sem emoji nem aspas — a formatação da fala é
                responsabilidade do rodapé. None = "não mude o texto",
                ver Feedback.manter().
    tipo        'info' | 'sucesso' | 'aviso' | 'erro' | 'instrucao'.
    temporaria  Se True, some sozinha depois de alguns segundos.
    depois      Feedback exibido quando esta expirar (implica temporária).

    Sem 'temporaria'/'depois' a mensagem é PERSISTENTE: fica até a
    próxima, e cancela qualquer troca agendada por uma temporária
    anterior.
    """
    texto: Optional[str]
    tipo: str = 'info'
    temporaria: bool = False
    depois: Optional['Feedback'] = None
    seq: int = field(default_factory=lambda: next(_sequencia), compare=False, repr=False)

    def __post_init__(self):
        if self.tipo not in TIPOS_FEEDBACK:
            raise ValueError(f'Tipo de feedback inválido: {self.tipo!r}. Use um de {TIPOS_FEEDBACK}.')
        if self.depois is not None:
            object.__setattr__(self, 'temporaria', True)

    # --- Construtores semânticos ------------------------------------------

    @classmethod
    def info(cls, texto, *, temporaria=False, depois=None):
        return cls(texto, 'info', temporaria, depois)

    @classmethod
    def sucesso(cls, texto, *, temporaria=False, depois=None):
        return cls(texto, 'sucesso', temporaria, depois)

    @classmethod
    def aviso(cls, texto, *, temporaria=False, depois=None):
        return cls(texto, 'aviso', temporaria, depois)

    @classmethod
    def erro(cls, texto, *, temporaria=False, depois=None):
        return cls(texto, 'erro', temporaria, depois)

    @classmethod
    def instrucao(cls, texto, *, temporaria=False, depois=None):
        return cls(texto, 'instrucao', temporaria, depois)

    @classmethod
    def manter(cls):
        """
        Mantém o texto atual e só CANCELA uma troca agendada — usado
        quando o contexto muda (ex: troca de aba) e a "próxima
        instrução" pendente da mensagem temporária anterior deixou de
        fazer sentido.
        """
        return cls(None)

    # --- (De)serialização pro dcc.Store -------------------------------------

    def to_plotly_json(self):
        """
        Chamado pelo serializador do Dash — por isso o callback pode
        devolver o Feedback direto no return, sem converter na mão.
        """
        return {
            'texto': self.texto,
            'tipo': self.tipo,
            'temporaria': self.temporaria,
            'depois': self.depois.to_plotly_json() if self.depois else None,
            'seq': self.seq,
        }

    @classmethod
    def de_dict(cls, dados):
        if not dados:
            return None
        return cls(
            texto=dados.get('texto'),
            tipo=dados.get('tipo', 'info'),
            temporaria=bool(dados.get('temporaria')),
            depois=cls.de_dict(dados.get('depois')),
            seq=dados.get('seq', 0),
        )
