import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
from dash import no_update
import plotly.graph_objects as go

from src.gui.components import icone, icone_colorido
from src.utils.helpers import carregar_dados_de_upload


def truncar_nome_arquivo(nome, limite=15):
    base, ext = nome.rsplit('.', 1) if '.' in nome else (nome, '')
    if len(base) <= limite:
        return nome
    return f"{base[:limite]}...{('.' + ext) if ext else ''}"


# --- Renderizadores de Interface ---

def renderizar_abas_estilo_chrome(estado, aba_ativa):
    if not estado.arquivos:
        return html.Div("Nenhum arquivo", className="abas-placeholder")

    abas = []
    lista_arquivos = list(estado.arquivos.keys())

    for i, nome_arq in enumerate(lista_arquivos):
        e_ativa = (nome_arq == aba_ativa)
        nome_curto = truncar_nome_arquivo(nome_arq)
        classe_aba = "aba-chrome" + (" ativa" if e_ativa else "")

        conteudo_aba = html.Div(
            className=classe_aba,
            id={'type': 'aba-item', 'arquivo': nome_arq},
            children=[
                html.Span(nome_curto, title=nome_arq, className="aba-texto"),
                html.Button(
                    '✕',
                    id={'type': 'botao-fechar-aba', 'arquivo': nome_arq},
                    className="aba-fechar-btn",
                    n_clicks=0
                )
            ]
        )
        abas.append(conteudo_aba)

        if i < len(lista_arquivos) - 1:
            proximo = lista_arquivos[i + 1]
            if aba_ativa != nome_arq and aba_ativa != proximo:
                abas.append(html.Span("|", className="aba-divisor"))

    return abas


def renderizar_colunas_da_aba_ativa(estado, aba_ativa):
    if not aba_ativa or aba_ativa not in estado.arquivos:
        return html.Div('Abra um arquivo.', className='abas-placeholder', style={'padding': '14px'})

    dados = estado.arquivos[aba_ativa]
    df_completo = dados["df"]
    gerenciador = dados["gerenciador"]

    lista_canais = []
    for coluna in df_completo.columns:
        rotulo = gerenciador.rotulo_atual(coluna)
        par_canal = (aba_ativa, coluna)
        selecionado = par_canal in estado.canais_selecionados

        classe_canal = 'coluna-item' + (' selecionada' if selecionado else '')
        marcador_check = '✓ ' if selecionado else '☐ '

        lista_canais.append(html.Div(
            id={'type': 'linha-canal', 'arquivo': aba_ativa, 'coluna': coluna},
            className=classe_canal,
            children=[
                html.Span(marcador_check, className="canal-checkbox"),
                html.Span(rotulo)
            ]
        ))

    return lista_canais


SCRIPT_DIVISORIA = """
<script>
document.addEventListener('DOMContentLoaded', function () {
    function iniciar() {
        var divisor = document.getElementById('divisor-resize');
        var sidebar = document.querySelector('.sidebar');
        if (!divisor || !sidebar) {
            setTimeout(iniciar, 300);
            return;
        }
        var arrastando = false;
        var LARGURA_MIN = 200;
        var LARGURA_MAX = 600;

        divisor.addEventListener('mousedown', function (e) {
            arrastando = true;
            divisor.classList.add('arrastando');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', function (e) {
            if (!arrastando) return;
            var novaLargura = e.clientX - sidebar.getBoundingClientRect().left;
            novaLargura = Math.max(LARGURA_MIN, Math.min(LARGURA_MAX, novaLargura));
            sidebar.style.width = novaLargura + 'px';
        });

        document.addEventListener('mouseup', function () {
            if (!arrastando) return;
            arrastando = false;
            divisor.classList.remove('arrastando');
            document.body.style.cursor = 'default';
            document.body.style.userSelect = 'auto';
        });
    }
    iniciar();

    function iniciarNavegacaoAbas() {
        var container = document.getElementById('container-abas-chrome');
        var btnEsquerda = document.getElementById('aba-nav-esquerda');
        var btnDireita = document.getElementById('aba-nav-direita');
        if (!container || !btnEsquerda || !btnDireita) {
            setTimeout(iniciarNavegacaoAbas, 300);
            return;
        }

        var MARGEM = 2;

        function atualizarSetas() {
            var temOverflow = container.scrollWidth > container.clientWidth + MARGEM;
            var podeVoltar = container.scrollLeft > MARGEM;
            var podeAvancar = container.scrollLeft < (container.scrollWidth - container.clientWidth - MARGEM);

            btnEsquerda.classList.toggle('visivel', temOverflow && podeVoltar);
            btnDireita.classList.toggle('visivel', temOverflow && podeAvancar);
        }

        function larguraDeUmaAba() {
            var primeiraAba = container.querySelector('.aba-chrome');
            return primeiraAba ? primeiraAba.getBoundingClientRect().width : 120;
        }

        btnEsquerda.addEventListener('click', function () {
            container.scrollBy({ left: -larguraDeUmaAba(), behavior: 'smooth' });
        });
        btnDireita.addEventListener('click', function () {
            container.scrollBy({ left: larguraDeUmaAba(), behavior: 'smooth' });
        });

        container.addEventListener('scroll', atualizarSetas);
        window.addEventListener('resize', atualizarSetas);

        new MutationObserver(atualizarSetas).observe(container, { childList: true });

        atualizarSetas();
    }
    iniciarNavegacaoAbas();
});
</script>
"""


def criar_app(estado):
    app = Dash(__name__, external_stylesheets=['https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'])
    app.title = 'Wizard Analytics'

    app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
        {SCRIPT_DIVISORIA}
    </body>
</html>
"""

    app.layout = html.Div(className='app-shell', children=[
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
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='excluir-dados',
                children=html.Div([icone_colorido('CutData_icon.png'), html.Span('Excluir dados', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='nova-analise',
                children=html.Div([icone_colorido('NewAnalysis_icon.png'), html.Span('Nova análise', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='nova-amostra',
                children=html.Div([icone_colorido('SampleData_icon.png'), html.Span('Nova Amostragem', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='fundir-arquivos',
                children=html.Div([icone_colorido('MergeData_icon.png'), html.Span('Fundir arquivos', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='exportar-grafico',
                children=html.Div([icone_colorido('ExportGraph_icon.png'), html.Span('Salvar gráfico', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
                multiple=False,
            ),
            dcc.Upload(
                id='exportar-dados',
                children=html.Div([icone_colorido('ExportData_icon.png'), html.Span('Exportar dados', className='toolbar-tooltip')]),
                className='toolbar-upload', disabled=True,
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
                    type="mono",
                    children=html.Div(
                        id='container-grafico',
                        style={
                            'flex': '1',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'backgroundImage': 'url("/assets/icones/bar-graph.svg")',
                            'backgroundRepeat': 'no-repeat',
                            'backgroundPosition': 'center',
                            'backgroundSize': '220px 220px',
                            'position': 'relative',
                            'width': '100%',
                            'height': '100%'
                        },
                        children=[
                            html.Div(
                                style={
                                    'display': 'grid',
                                    'gridTemplateColumns': 'repeat(3, 1fr)',
                                    'gap': '16px',
                                    'backgroundColor': 'rgba(255, 255, 255, 0.88)',
                                    'padding': '20px',
                                    'borderRadius': '8px',
                                    'boxShadow': '0 4px 12px rgba(0,0,0,0.08)',
                                    'backdropFilter': 'blur(3px)'
                                },
                                children=[
                                    html.Button('Ação 1', id='central-btn-1', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                    html.Button('Ação 2', id='central-btn-2', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                    html.Button('Ação 3', id='central-btn-3', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                    html.Button('Ação 4', id='central-btn-4', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                    html.Button('Ação 5', id='central-btn-5', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                    html.Button('Ação 6', id='central-btn-6', className='toolbar-botao', style={'padding': '12px 20px', 'minWidth': '90px'}),
                                ]
                            )
                        ]
                    ),
                ),
            ]),

            html.Div(className='painel-direito', style={'width': '260px', 'minWidth': '260px'}, children=[
                html.Div('Opções do gráfico', className='painel-direito-titulo'),
                html.P('Propriedades e customizações da curva ativa.', className='painel-direito-placeholder'),
            ]),
        ]),

        html.Div(className='rodape', children=[
            html.Span('infos do sistema (que futuramente vou carregar)', className='rodape-info'),
            html.Span(' | ', style={'margin': '0 8px', 'opacity': '0.4'}),
            html.Span(id='rodape-status', children='🧙‍♂️: " Aguardando ações... "')
        ]),
    ])

    @app.callback(
        Output('aba-ativa-store', 'data'),
        Output('rodape-status', 'children'),
        Output('nova-analise', 'disabled'),
        Output('fundir-arquivos', 'disabled'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo, aba_atual):
        if conteudo is None:
            raise PreventUpdate
        if nome_arquivo in estado.arquivos:
            return (nome_arquivo, f'🧙‍♂️: " O arquivo \'{nome_arquivo}\' já foi aberto! "',
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2)
        try:
            df = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df)
            return (nome_arquivo, f'🧙‍♂️: " Arquivo \'{nome_arquivo}\' aberto com sucesso! pronto. "',
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2)
        except Exception as e:
            return (aba_atual, f'🧙‍♂️: " Erro ao abrir arquivo: {str(e)} "',
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2)

    @app.callback(
        Output('aba-ativa-store', 'data', allow_duplicate=True),
        Output('container-abas-chrome', 'children'),
        Output('lista-canais-aba', 'children'),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('nova-analise', 'disabled', allow_duplicate=True),
        Output('fundir-arquivos', 'disabled', allow_duplicate=True),
        Input({'type': 'aba-item', 'arquivo': ALL}, 'n_clicks'),
        Input({'type': 'botao-fechar-aba', 'arquivo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_abas(_c_item, _c_fechar, aba_ativa):
        if not ctx.triggered:
            raise PreventUpdate

        gatilho_id = ctx.triggered_id
        tipo = gatilho_id.get('type')
        arquivo_alvo = gatilho_id.get('arquivo')

        if tipo == 'botao-fechar-aba':
            estado.remover_arquivo(arquivo_alvo)
            if aba_ativa == arquivo_alvo:
                aba_ativa = list(estado.arquivos.keys())[0] if estado.arquivos else None
            mensagem = f'🧙‍♂️: " Arquivo \'{arquivo_alvo}\' fechado. "'
        elif tipo == 'aba-item':
            aba_ativa = arquivo_alvo
            mensagem = f'🧙‍♂️: " Trabalhando em \'{truncar_nome_arquivo(arquivo_alvo)}\'. "'
        else:
            mensagem = no_update

        return (aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                mensagem, len(estado.arquivos) == 0, len(estado.arquivos) < 2)

    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_selecao_canais(n_clicks_list, aba_ativa):
        if not ctx.triggered or not aba_ativa:
            raise PreventUpdate

        gatilho_id = ctx.triggered_id
        mensagem = no_update
        if gatilho_id and gatilho_id.get('type') == 'linha-canal':
            arquivo, coluna = gatilho_id.get('arquivo'), gatilho_id.get('coluna')
            estado.alternar_selecao_canal(arquivo, coluna)
            ligado = (arquivo, coluna) in estado.canais_selecionados
            acao = 'ativado' if ligado else 'desativado'
            mensagem = f'🧙‍♂️: " Canal \'{coluna}\' {acao}. ({len(estado.canais_selecionados)} selecionado(s)) "'

        return renderizar_colunas_da_aba_ativa(estado, aba_ativa), mensagem

    @app.callback(
        Output('container-abas-chrome', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Input('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_interface_por_aba(aba_ativa):
        return renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa)

    @app.callback(
        Output('container-grafico', 'children'),
        Output('rodape-status', 'children', allow_duplicate=True),
        Input('central-btn-1', 'n_clicks'),
        prevent_initial_call=True,
    )
    def disparar_plotagem_sob_demanda(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        if not estado.canais_selecionados:
            return no_update, '🧙‍♂️: " Selecione ao menos um canal antes de gerar o gráfico. "'

        fig = go.Figure()

        for (nome_arq, coluna) in estado.canais_selecionados:
            if nome_arq in estado.arquivos:
                df = estado.arquivos[nome_arq]["df"]
                colunas_num = df.select_dtypes(include='number').columns
                eixo_x = estado.coluna_x if estado.coluna_x in df.columns else colunas_num[0]

                fig.add_trace(go.Scatter(
                    x=df[eixo_x],
                    y=df[coluna],
                    mode='lines',
                    name=f"{truncar_nome_arquivo(nome_arq)} → {coluna}"
                ))

        fig.update_layout(
            template="plotly_white",
            margin=dict(l=50, r=20, t=20, b=40),
            hovermode="x unified",
            uirevision='constant'
        )

        estado.grafico_gerado = True
        n_series = len(estado.canais_selecionados)
        mensagem = f'🧙‍♂️: " Gráfico gerado com {n_series} série(s). "'
        return dcc.Graph(id='grafico-plotly-real', figure=fig, style={'flex': '1', 'width': '100%', 'height': '100%'}), mensagem

    return app