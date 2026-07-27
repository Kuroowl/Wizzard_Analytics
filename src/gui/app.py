from dash import Dash

from src.gui.layout import montar_layout
from src.gui.callbacks import registrar_callbacks
from src.gui.scripts_js import construir_index_string


FONTES_GOOGLE = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'


def criar_app(estado):
    """
    Monta o app Dash a partir de um EstadoApp (vazio ou já com arquivos
    carregados). Não decide QUAL arquivo carregar — isso acontece via
    upload, na própria interface.
    """
    app = Dash(__name__, external_stylesheets=[FONTES_GOOGLE], suppress_callback_exceptions=True)
    app.title = 'Wizard Analytics'
    app.index_string = construir_index_string()
    app.layout = montar_layout(estado)
    registrar_callbacks(app, estado)
    return app