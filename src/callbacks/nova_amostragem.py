"""
Callbacks da Nova Amostragem (botão 'nova-amostra' da toolbar).

Funcionalidade ainda em definição — este módulo só reserva o lugar. Quando
os callbacks nascerem, a regra é:
  - aqui: interpretar o clique, chamar o core, atualizar estado/gráfico e
    emitir um Feedback (origem própria em ORIGENS_FEEDBACK,
    src/gui/feedback.py);
  - src/core/operations/sampling.py: o cálculo em si (downsample, média
    móvel, ajuste polinomial...), sem nada de Dash.
"""


def registrar_callbacks_nova_amostragem(app, estado):
    """Nenhum callback ainda."""
