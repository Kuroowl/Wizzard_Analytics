import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from src.core.plotting.plotter import construir_figura, cor_da_coluna
from src.utils.helpers import carregar_dados_de_upload


def truncar_nome_arquivo(nome, limite=12):
    """'dados_do_teste_realizadoem122040.txt' -> 'dados_do....txt'"""
    base, ext = nome.rsplit('.', 1) if '.' in nome else (nome, '')
    if len(base) <= limite:
        return nome
    return f"{base[:limite]}...{('.' + ext) if ext else ''}"


# --- Lógica pura de múltiplos arquivos adaptada para o novo EstadoApp ---

def processar_upload(conteudo, nome_arquivo, estado):
    """
    Processa um upload e adiciona ao dicionário de arquivos do estado.
    """
    if conteudo is None:
        return None

    if nome_arquivo in estado.arquivos:
        return {'erro': f"O arquivo '{nome_arquivo}' já foi carregado."}

    try:
        df = carregar_dados_de_upload(conteudo, nome_arquivo)
    except Exception as e:
        return {'erro': f"Não consegui carregar '{nome_arquivo}': {e}"}

    # Adiciona o arquivo na nossa "fonte da verdade" multi-arquivo
    estado.adicionar_arquivo(nome_arquivo, df)

    return {
        'status': f"'{nome_arquivo}' adicionado com sucesso ({len(df)} linhas)."
    }


def renderizar_menu_esquerdo(estado):
    """
    Monta a árvore/lista do menu esquerdo:
    Para cada arquivo carregado, mostra o nome dele, um botão de deletar [X],
    e aninhado embaixo dele, a lista de canais/colunas identificadas.
    """
    if not estado.arquivos:
        return html.Div('Nenhum arquivo carregado', className='sidebar-placeholder')

    elementos_menu = []

    for nome_arq, dados in estado.arquivos.items():
        df_completo = dados["df"]
        gerenciador = dados["gerenciador"]
        nome_curto = truncar_nome_arquivo(nome_arq)

        # Cabeçalho do arquivo com botão de remover
        header_arquivo = html.Div(className='menu-arquivo-header', style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'fontWeight': 'bold', 'marginTop': '10px'}, children=[
            html.Span(nome_curto, title=nome_arq),
            html.Button('✕', id={'type': 'botao-remover-arquivo', 'arquivo': nome_arq}, n_clicks=0,
                        style={'background': 'transparent', 'border': 'none', 'color': 'red', 'cursor': 'pointer'})
        ])
        
        # Lista de canais deste arquivo específico
        lista_canais = []
        for coluna in df_completo.columns:
            rotulo = gerenciador.rotulo_atual(coluna)
            par_canal = (nome_arq, coluna)
            selecionado = par_canal in estado.canais_selecionados
            
            # Caixa estilizada ou item clicável para alternar seleção
            classe_canal = 'coluna-item' + (' selecionada' if selecionado else '')
            
            lista_canais.append(html.Div(
                id={'type': 'linha-canal', 'arquivo': nome_arq, 'coluna': coluna},
                className=classe_canal,
                n_clicks=0,
                style={'paddingLeft': '15px', 'cursor': 'pointer', 'color': 'var(--cor-texto)' if selecionado else 'var(--cor-texto-mudo)'},
                children=[
                    html.Span('✓ ' if selecionado else '☐ '),
                    html.Span(rotulo)
                ]
            ))

        # Bloco completo do arquivo agrupando o cabeçalho e seus canais
        elementos_menu.append(html.Div(className='bloco-arquivo', children=[
            header_arquivo,
            html.Div(lista_canais, className='menu-canais-container')
        ]))

    return elementos_menu


# --- Montagem do App Dash ---

FONTES_GOOGLE = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'


def criar_app(estado):
    app = Dash(__name__, external_stylesheets=[FONTES_GOOGLE])
    app.title = 'Wizard Analytics'

    app.layout = html.Div(className='app-shell', children=[
        html.Div(className='menubar', children=[
            html.Span('Arquivo', className='menubar-item'),
            html.Span('Editar', className='menubar-item'),
            html.Span('Ajuda', className='menubar-item'),
        ]),

        html.Div(className='toolbar', children=[
            dcc.Upload(
                id='upload-arquivo',
                children=html.Div('ABRIR ARQUIVO'),
                className='toolbar-upload',
                multiple=False,
            ),
            html.Div(className='toolbar-divisor'),
            # Novo botão que você pediu: só gera o gráfico se clicar aqui!
            html.Button('GERAR GRÁFICO', id='botao-gerar-grafico', className='toolbar-botao', n_clicks=0),
        ]),

        html.Div(className='corpo', children=[
            # O menu esquerdo contendo os arquivos abertos e os canais
            html.Div(className='sidebar', children=[
                html.Div('Arquivos e Canais', className='sidebar-secao-titulo'),
                html.Div(id='container-menu-esquerdo', children=renderizar_menu_esquerdo(estado)),
            ]),

            html.Div(className='centro', children=[
                dcc.Graph(id='grafico', figure=go.Figure(), style={'flex': '1'}),
                html.Pre(id='console-dev', className='console-dev', children='Envie um arquivo para começar.'),
            ]),

            html.Div(className='painel-direito', children=[
                html.Div('Opções do gráfico', className='painel-direito-titulo'),
                html.P('Configurações de suavização e cor aparecerão aqui conforme as curvas forem geradas.',
                       className='painel-direito-placeholder'),
            ]),
        ]),
    ])

    # 1. Callback de Upload
    @app.callback(
        Output('container-menu-esquerdo', 'children'),
        Output('console-dev', 'children'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo):
        resultado = processar_upload(conteudo, nome_arquivo, estado)
        if resultado is None:
            raise PreventUpdate
        
        status = resultado.get('erro') if 'erro' in resultado else resultado.get('status')
        return renderizar_menu_esquerdo(estado), status

    # 2. Callback para marcar/desmarcar Canais
    @app.callback(
        Output('container-menu-esquerdo', 'children', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def ao_clicar_canal(_clicks):
        if not ctx.triggered or ctx.triggered[0]['value'] in (None, 0):
            raise PreventUpdate
        
        # Identifica exatamente qual arquivo e qual coluna foi clicada
        dados_gatilho = ctx.triggered_id
        nome_arq = dados_gatilho['arquivo']
        coluna = dados_gatilho['coluna']
        
        # Alterna o estado de seleção usando a nova lógica multi-arquivo
        estado.alternar_selecao_canal(nome_arq, coluna)
        return renderizar_menu_esquerdo(estado)

    # 3. Callback para remover um arquivo inteiro
    @app.callback(
        Output('container-menu-esquerdo', 'children', allow_duplicate=True),
        Output('console-dev', 'children', allow_duplicate=True),
        Input({'type': 'botao-remover-arquivo', 'arquivo': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def ao_remover_arquivo(_clicks):
        if not ctx.triggered or ctx.triggered[0]['value'] in (None, 0):
            raise PreventUpdate
        
        nome_arq = ctx.triggered_id['arquivo']
        estado.remover_arquivo(nome_arq)
        return renderizar_menu_esquerdo(estado), f"Arquivo '{nome_arq}' removido da memória."

    # 4. Callback para o seu NOVO botão de gerar o gráfico manualmente
    @app.callback(
        Output('grafico', 'figure'),
        Input('botao-gerar-grafico', 'n_clicks'),
        prevent_initial_call=True,
    )
    def ao_clicar_gerar_grafico(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        
        fig = go.Figure()
        
        # Monta o gráfico juntando as curvas selecionadas de múltiplos arquivos se houver
        for (nome_arq, coluna) in estado.canais_selecionados:
            if nome_arq in estado.arquivos:
                df = estado.arquivos[nome_arq]["df"]
                
                # Se o arquivo contiver o eixo X padrão usa ele, senão usa a primeira coluna numérica
                colunas_num = df.select_dtypes(include='number').columns
                x_atual = estado.coluna_x if estado.coluna_x in df.columns else colunas_num[0]
                
                fig.add_trace(go.Scatter(
                    x=df[x_atual],
                    y=df[coluna],
                    mode='lines',
                    name=f"{truncar_nome_arquivo(nome_arq)} -> {coluna}"
                ))
                
        fig.update_layout(template="plotly_white", hovermode="x unified")
        return fig

    return app