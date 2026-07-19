import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from src.core.plotting.plotter import construir_figura, cor_da_coluna
from src.gui.eventos_graficos import extrair_edicao_titulo, extrair_edicao_eixo, extrair_edicao_legenda
from src.utils.helpers import carregar_dados_de_upload


def truncar_nome_arquivo(nome, limite=12):
    """'dados_do_teste_realizadoem122040.txt' -> 'dados_do....txt'"""
    base, ext = nome.rsplit('.', 1) if '.' in nome else (nome, '')
    if len(base) <= limite:
        return nome
    return f"{base[:limite]}...{('.' + ext) if ext else ''}"


# --- lógica pura, separada da "fiação" do Dash, pra dar pra testar sem navegador ---

def processar_upload(conteudo, nome_arquivo, estado):
    """
    Processa um upload e atualiza 'estado' in-place (df, gerenciador, seleção
    padrão de X/Y). Devolve um dict com o que a interface precisa, ou
    {'erro': ...} se o arquivo não puder ser carregado.
    """
    if conteudo is None:
        return None

    try:
        df = carregar_dados_de_upload(conteudo, nome_arquivo)
    except Exception as e:
        return {'erro': f"Não consegui carregar '{nome_arquivo}': {e}"}

    colunas_numericas = df.select_dtypes(include='number').columns.tolist()
    colunas_ignoradas_no_padrao = {'n#', 'index', 'indice', 'id'}
    candidatas_y = [c for c in colunas_numericas if c.lower() not in colunas_ignoradas_no_padrao]

    x_padrao = 'Tempo_decorrido_s' if 'Tempo_decorrido_s' in df.columns else (
        colunas_numericas[0] if colunas_numericas else df.columns[0]
    )
    y_padrao = [c for c in candidatas_y if c != x_padrao][:2]

    estado.carregar(df, coluna_x_padrao=x_padrao, colunas_y_padrao=y_padrao)

    return {
        'nome_aba': truncar_nome_arquivo(nome_arquivo),
        'status': f"'{nome_arquivo}' carregado: {len(df)} linha(s), {len(df.columns)} coluna(s).",
    }


def processar_edicao_grafico(relayout_data, restyle_data, estado):
    """
    Interpreta relayout/restyle e aplica rename no estado.gerenciador
    conforme a regra combinada: eixo X e legenda renomeiam coluna
    (representam uma coluna específica); título e eixo Y são só visuais.
    Devolve a lista de linhas de log.
    """
    log = []

    if relayout_data:
        log.append(f"relayoutData bruto: {relayout_data}")

        novo_titulo = extrair_edicao_titulo(relayout_data)
        if novo_titulo:
            log.append(f"-> título mudou para '{novo_titulo}' (só visual)")

        novo_rotulo_y = extrair_edicao_eixo(relayout_data, 'yaxis')
        if novo_rotulo_y:
            log.append(f"-> rótulo do eixo Y mudou para '{novo_rotulo_y}' (só visual)")

        novo_rotulo_x = extrair_edicao_eixo(relayout_data, 'xaxis')
        if novo_rotulo_x:
            try:
                estado.gerenciador.renomear(estado.coluna_x, novo_rotulo_x)
                log.append(f"-> coluna '{estado.coluna_x}' (eixo X) renomeada para '{novo_rotulo_x}'")
            except ValueError as e:
                log.append(f"-> rename recusado: {e}")

    if restyle_data:
        log.append(f"restyleData bruto: {restyle_data}")
        edicao = extrair_edicao_legenda(restyle_data)
        if edicao:
            indice_trace, novo_nome = edicao
            nome_interno = estado.colunas_y[indice_trace]
            try:
                estado.gerenciador.renomear(nome_interno, novo_nome)
                log.append(f"-> coluna '{nome_interno}' renomeada para '{novo_nome}'")
            except ValueError as e:
                log.append(f"-> rename recusado: {e}")

    return log


def renderizar_lista_colunas(estado):
    """
    Monta a lista de colunas da sidebar: uma linha por coluna, com bolinha
    colorida (cor da curva, se estiver no eixo Y), rótulo atual, e um botão
    'X' pra marcar a coluna como eixo X. Colunas não-numéricas aparecem
    listadas (são "identificadas"), mas não são clicáveis.
    """
    if not estado.carregado():
        return []

    linhas = []
    for coluna in estado.df.columns:
        numerica = pd.api.types.is_numeric_dtype(estado.df[coluna])
        rotulo = estado.gerenciador.rotulo_atual(coluna)
        na_selecao_y = coluna in estado.colunas_y
        e_x = (coluna == estado.coluna_x)

        if na_selecao_y:
            estilo_dot = {'background': cor_da_coluna(estado.colunas_y.index(coluna))}
            classe_dot = 'coluna-dot'
        else:
            estilo_dot = {}
            classe_dot = 'coluna-dot vazio'

        filhos_linha = [html.Span(className=classe_dot, style=estilo_dot)]

        if numerica:
            filhos_linha.append(html.Span(
                rotulo,
                id={'type': 'linha-y', 'coluna': coluna},
                n_clicks=0,
                style={'flex': '1', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap', 'cursor': 'pointer'},
            ))
            filhos_linha.append(html.Button(
                'X', id={'type': 'botao-x', 'coluna': coluna}, n_clicks=0,
                className='coluna-marcador-x',
                style={'background': 'transparent', 'cursor': 'pointer'} if not e_x else
                      {'background': 'var(--cor-accent)', 'color': 'var(--cor-superficie-escura)', 'cursor': 'pointer'},
            ))
        else:
            filhos_linha.append(html.Span(rotulo, style={'flex': '1', 'color': 'var(--cor-texto-mudo)'}))

        classe_linha = 'coluna-item' + (' selecionada' if (na_selecao_y or e_x) else '')
        linhas.append(html.Div(filhos_linha, className=classe_linha))

    return linhas


def _figura_ou_vazia(estado):
    if estado.coluna_x and estado.colunas_y:
        return construir_figura(estado.df, estado.coluna_x, estado.colunas_y, estado.gerenciador, titulo='Dados carregados')
    return go.Figure()


def _clique_real(valor_disparo):
    """Protege contra o disparo 'fantasma' que callbacks de padrão (ALL) do
    Dash costumam dar assim que os componentes são criados dinamicamente,
    mesmo sem clique nenhum do usuário."""
    return valor_disparo not in (None, 0)


# --- montagem do app Dash em si ---

FONTES_GOOGLE = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'


def criar_app(estado):
    app = Dash(__name__, external_stylesheets=[FONTES_GOOGLE])
    app.title = 'Análise de dados'

    app.layout = html.Div(className='app-shell', children=[
        html.Div(className='menubar', children=[
            html.Span('Arquivo', className='menubar-item'),
            html.Span('Editar', className='menubar-item'),
            html.Span('Exibir', className='menubar-item'),
            html.Span('Ajuda', className='menubar-item'),
        ]),

        html.Div(className='toolbar', children=[
            dcc.Upload(
                id='upload-arquivo',
                children=html.Div('ABRIR'),
                className='toolbar-upload',
                multiple=False,
            ),
            html.Div(className='toolbar-divisor'),
            html.Button('EXPORTAR', className='toolbar-botao', disabled=True, title='Em breve'),
            html.Button('DESFAZER', className='toolbar-botao', disabled=True, title='Em breve'),
        ]),

        html.Div(className='corpo', children=[
            html.Div(className='sidebar', children=[
                html.Div('Nenhum arquivo carregado', id='aba-arquivo', className='aba-arquivo'),
                html.Div('Colunas', className='sidebar-secao-titulo'),
                html.Div(id='lista-colunas', children=[]),
            ]),

            html.Div(className='centro', children=[
                dcc.Graph(id='grafico', figure=go.Figure(), config={'editable': True}, style={'flex': '1'}),
                html.Pre(id='console-dev', className='console-dev', children='Envie um arquivo pra começar.'),
            ]),

            html.Div(className='painel-direito', children=[
                html.Div('Opções do gráfico', className='painel-direito-titulo'),
                html.P('Em breve: filtros, ajustes de curva e estatísticas aplicáveis direto aqui.',
                       className='painel-direito-placeholder'),
            ]),
        ]),
    ])

    @app.callback(
        Output('aba-arquivo', 'children'),
        Output('lista-colunas', 'children'),
        Output('grafico', 'figure'),
        Output('console-dev', 'children'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo):
        resultado = processar_upload(conteudo, nome_arquivo, estado)
        if resultado is None:
            raise PreventUpdate
        if 'erro' in resultado:
            return 'Nenhum arquivo carregado', [], go.Figure(), resultado['erro']
        return resultado['nome_aba'], renderizar_lista_colunas(estado), _figura_ou_vazia(estado), resultado['status']

    @app.callback(
        Output('lista-colunas', 'children', allow_duplicate=True),
        Output('grafico', 'figure', allow_duplicate=True),
        Input({'type': 'linha-y', 'coluna': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def ao_clicar_coluna_y(_todos_n_clicks):
        if not estado.carregado() or not ctx.triggered or not _clique_real(ctx.triggered[0]['value']):
            raise PreventUpdate
        coluna = ctx.triggered_id['coluna']
        if coluna in estado.colunas_y:
            estado.colunas_y.remove(coluna)
        else:
            estado.colunas_y.append(coluna)
        return renderizar_lista_colunas(estado), _figura_ou_vazia(estado)

    @app.callback(
        Output('lista-colunas', 'children', allow_duplicate=True),
        Output('grafico', 'figure', allow_duplicate=True),
        Input({'type': 'botao-x', 'coluna': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def ao_clicar_definir_x(_todos_n_clicks):
        if not estado.carregado() or not ctx.triggered or not _clique_real(ctx.triggered[0]['value']):
            raise PreventUpdate
        coluna = ctx.triggered_id['coluna']
        estado.coluna_x = coluna
        if coluna in estado.colunas_y:
            estado.colunas_y.remove(coluna)  # não faz sentido a mesma coluna em X e Y
        return renderizar_lista_colunas(estado), _figura_ou_vazia(estado)

    @app.callback(
        Output('grafico', 'figure', allow_duplicate=True),
        Output('lista-colunas', 'children', allow_duplicate=True),
        Output('console-dev', 'children', allow_duplicate=True),
        Input('grafico', 'relayoutData'),
        Input('grafico', 'restyleData'),
        prevent_initial_call=True,
    )
    def ao_editar_grafico(relayout_data, restyle_data):
        if not estado.carregado() or ctx.triggered_id != 'grafico':
            raise PreventUpdate

        log = processar_edicao_grafico(relayout_data, restyle_data, estado)
        texto_log = '\n'.join(log) if log else 'Nenhum evento reconhecido ainda.'
        return _figura_ou_vazia(estado), renderizar_lista_colunas(estado), texto_log

    return app