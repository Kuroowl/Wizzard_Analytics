from dash import dcc, html

from src.gui.components import icone_colorido
from src.gui.renderizadores import (
    renderizar_area_grafico, renderizar_info_rodape,
    renderizar_badge_alerta, renderizar_popup_alerta,
)

# Tempo (ms) que uma mensagem "temporária" do mago fica visível antes de
# desaparecer sozinha — ver 'rodape-timer-mensagem' e o callback
# '_expirar_mensagem_temporaria' em callbacks.py.
DURACAO_MENSAGEM_TEMPORARIA_MS = 3500


def montar_layout(estado):
    """
    Monta a árvore de componentes do app. Os estados iniciais de habilitação
    dos botões são calculados a partir de 'estado' (em vez de fixos), pra
    ficar consistente mesmo no caso raro de a app já nascer com arquivos
    carregados.
    """
    sem_arquivo = len(estado.arquivos) == 0
    menos_de_2_arquivos = len(estado.arquivos) < 2
    sem_grafico = not estado.grafico_gerado

    return html.Div(className='app-shell', children=[
        dcc.Store(id='aba-ativa-store', data=None),

        html.Div(className='menubar', children=[
            html.Span('Arquivo', className='menubar-item'),
            html.Span('Editar', className='menubar-item'),
            html.Span('Ajuda', className='menubar-item'),
        ]),

        html.Div(className='toolbar', children=[
            dcc.Upload(
                id='upload-arquivo',
                children=html.Div([icone_colorido('AddFile_icon.png'), html.Span('Carregar arquivo', className='toolbar-tooltip')]),
                className='toolbar-upload',
                multiple=False,
            ),
            dcc.Upload(
                id='aparar-dados',
                children=html.Div([icone_colorido('TrimData_icon.png'), html.Span('Aparar dados', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_grafico,
                multiple=False,
            ),
            dcc.Upload(
                id='excluir-dados',
                children=html.Div([icone_colorido('CutData_icon.png'), html.Span('Excluir dados', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_grafico,
                multiple=False,
            ),
            dcc.Upload(
                id='nova-analise',
                children=html.Div([icone_colorido('NewAnalysis_icon.png'), html.Span('Nova análise', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_arquivo,
                multiple=False,
            ),
            dcc.Upload(
                id='nova-amostra',
                children=html.Div([icone_colorido('SampleData_icon.png'), html.Span('Nova Amostragem', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_grafico,
                multiple=False,
            ),
            dcc.Upload(
                id='fundir-arquivos',
                children=html.Div([icone_colorido('MergeData_icon.png'), html.Span('Fundir arquivos', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=menos_de_2_arquivos,
                multiple=False,
            ),
            dcc.Upload(
                id='exportar-grafico',
                children=html.Div([icone_colorido('ExportGraph_icon.png'), html.Span('Salvar gráfico', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_grafico,
                multiple=False,
            ),
            dcc.Upload(
                id='exportar-dados',
                children=html.Div([icone_colorido('ExportData_icon.png'), html.Span('Exportar dados', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=sem_grafico,
                multiple=False,
            ),
        ]),

        html.Div(className='corpo', children=[

            html.Div(className='sidebar', children=[
                html.Div(className='abas-wrapper', children=[
                    html.Button('‹', id='aba-nav-esquerda', className='aba-nav-btn', n_clicks=0),
                    html.Div(id='container-abas-chrome', className='tabs-chrome-container'),
                    html.Button('›', id='aba-nav-direita', className='aba-nav-btn', n_clicks=0),
                ]),
                html.Div('', className='sidebar-secao-titulo'),
                html.Div(id='lista-canais-aba', className='menu-canais-container')
            ]),

            html.Div(id='divisor-resize', className='divisor-resize'),

            html.Div(className='centro', children=[
                dcc.Loading(
                    id="loading-grafico",
                    type="circle",
                    children=html.Div(
                        id='container-grafico',
                        className='area-grafico-container',
                        children=renderizar_area_grafico(estado),
                    ),
                ),
            ]),

            html.Div(className='painel-direito', style={'width': '260px', 'minWidth': '260px'}, children=[
                html.Div('Opções do gráfico', className='painel-direito-titulo'),
                html.P('Propriedades e customizações da curva ativa.', className='painel-direito-placeholder'),
            ]),
        ]),

        html.Div(className='rodape', children=[
            html.Span(id='rodape-info-arquivo', className='rodape-info',
                      children=renderizar_info_rodape(estado, None)),

            html.Span(' | ', className='rodape-separador'),

            html.Div(id='rodape-alerta-wrapper', className='rodape-alerta-wrapper', children=[
                html.Div(id='rodape-alerta-popup', className='rodape-alerta-popup',
                         children=renderizar_popup_alerta(estado, None)),
                html.Button(id='rodape-alerta-badge', className='rodape-alerta-badge',
                            children=renderizar_badge_alerta(estado, None), n_clicks=0),
            ]),

            html.Span(' | ', className='rodape-separador'),

            html.Span(id='rodape-status', children='🧙‍♂️: " Carregue um arquivo para começar... "'),

            # --- Máquina da mensagem temporária do mago ---
            # 'rodape-mensagem-seguinte' guarda o que deve aparecer QUANDO a
            # mensagem atual expirar (string vazia = simplesmente some).
            # 'rodape-timer-mensagem' já nasce ativo (disabled=False) pra
            # fazer a mensagem inicial acima desaparecer sozinha nos
            # primeiros segundos, sem precisar de nenhuma ação do usuário.
            dcc.Store(id='rodape-mensagem-seguinte', data=''),
            dcc.Interval(
                id='rodape-timer-mensagem',
                interval=DURACAO_MENSAGEM_TEMPORARIA_MS,
                n_intervals=0,
                max_intervals=1,
                disabled=False,
            ),
        ]),
    ])