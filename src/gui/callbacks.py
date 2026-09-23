from src.gui.rodape import registrar_callbacks_rodape
from src.callbacks.abas import registrar_callbacks_abas
from src.callbacks.arquivos import registrar_callbacks_arquivos
from src.callbacks.canais import registrar_callbacks_canais
from src.callbacks.corte import registrar_callbacks_corte
from src.callbacks.edicao import registrar_callbacks_edicao
from src.callbacks.grafico import registrar_callbacks_grafico
from src.callbacks.nova_amostragem import registrar_callbacks_nova_amostragem
from src.callbacks.nova_analise import registrar_callbacks_nova_analise


def registrar_callbacks(app, estado):
    """
    Registra todos os callbacks do app. Recebe 'app' (pra decorar com
    @app.callback) e 'estado' (o EstadoApp global, compartilhado com
    layout.py) — este módulo não decide qual app instanciar nem qual
    estado usar, só liga os dois.

    Todos os callbacks já moram em src/callbacks/ (Fase 2). Este índice
    se muda pra src/callbacks/__init__.py na próxima etapa (2.11).
    """
    # A mensagem do mago tem um único dono (src/gui/rodape.py). Os
    # callbacks abaixo só emitem Feedback em seu próprio canal.
    registrar_callbacks_rodape(app)

    registrar_callbacks_arquivos(app, estado)
    registrar_callbacks_abas(app, estado)
    registrar_callbacks_grafico(app, estado)
    registrar_callbacks_canais(app, estado)
    registrar_callbacks_corte(app, estado)
    registrar_callbacks_nova_analise(app, estado)
    registrar_callbacks_nova_amostragem(app, estado)
    registrar_callbacks_edicao(app, estado)
