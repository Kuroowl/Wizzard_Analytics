import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from src.gui.components import icone
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


# --- Main Application ---

# JS puro (sem round-trip pro servidor Python a cada pixel arrastado) que liga
# a divisória entre sidebar e centro. Injetado no index_string porque é
# interação de mouse contínua (mousedown/mousemove/mouseup) — um clientside
# callback do Dash é pensado pra eventos discretos (clique, mudança de valor),
# não pra isso.
SCRIPT_DIVISORIA = """
<script>
document.addEventListener('DOMContentLoaded', function () {
    function iniciar() {
        var divisor = document.getElementById('divisor-resize');
        var sidebar = document.querySelector('.sidebar');
        if (!divisor || !sidebar) {
            setTimeout(iniciar, 300);  // o Dash ainda não montou o layout via React
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

    // --- navegação das abas (< / >): aparecem só quando há abas fora de vista ---
    function iniciarNavegacaoAbas() {
        var container = document.getElementById('container-abas-chrome');
        var btnEsquerda = document.getElementById('aba-nav-esquerda');
        var btnDireita = document.getElementById('aba-nav-direita');
        if (!container || !btnEsquerda || !btnDireita) {
            setTimeout(iniciarNavegacaoAbas, 300);
            return;
        }

        var MARGEM = 2;  // tolerância de arredondamento de subpixel

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

        // o Dash re-renderiza as abas (novo arquivo, fechar aba) substituindo os
        // filhos do container — um MutationObserver garante que as setas sejam
        // reavaliadas toda vez que isso acontecer, sem precisar de callback extra
        new MutationObserver(atualizarSetas).observe(container, { childList: true });

        atualizarSetas();
    }
    iniciarNavegacaoAbas();
});
</script>
"""


def criar_app(estado):
    app = Dash(__name__, external_stylesheets=['https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'])
    app.title = 'Análise de dados'

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
        # Memória local estável da UI
        dcc.Store(id='aba-ativa-store', data=None),

        # Linha 1: Menubar Fixo Superior
        html.Div(className='menubar', children=[
            html.Span('Arquivo', className='menubar-item'),
            html.Span('Editar', className='menubar-item'),
            html.Span('Ajuda', className='menubar-item'),
        ]),

        # Linha 2: Toolbar de Importação
        html.Div(className='toolbar', children=[
            dcc.Upload(
                id='upload-arquivo',
                children=html.Div([icone('AddFile_icon.png'), '']),
                className='toolbar-upload',
                multiple=False,
            ),
            html.Div(className='toolbar-divisor'),
            html.Button('EXPORTAR', className='toolbar-botao', disabled=True, title='Em breve'),
            html.Button('DESFAZER', className='toolbar-botao', disabled=True, title='Em breve'),
        ]),

        # Linha 3: Layout Principal (Corpo dividido usando as classes CSS do seu painel)
        html.Div(className='corpo', children=[

            # 1. PAINEL DA ESQUERDA (Fixo e Isolado)
            html.Div(className='sidebar', children=[
                # Container superior com abas estilo chrome + navegação lateral
                html.Div(className='abas-wrapper', children=[
                    html.Button('‹', id='aba-nav-esquerda', className='aba-nav-btn', n_clicks=0),
                    html.Div(id='container-abas-chrome', className='tabs-chrome-container'),
                    html.Button('›', id='aba-nav-direita', className='aba-nav-btn', n_clicks=0),
                ]),

                # Seção estática de título
                html.Div('Canais Disponíveis', className='sidebar-secao-titulo'),

                # Container interno dos canais com rolagem controlada
                html.Div(id='lista-canais-aba', className='menu-canais-container')
            ]),

            html.Div(id='divisor-resize', className='divisor-resize'),

            # 2. PAINEL CENTRAL (Controles Superiores Fixos + Área de Gráfico Dinâmica)
            html.Div(className='centro', children=[

                # Barra de Opções Superior do Gráfico (ESTÁTICA, ALINHADA COM O CSS)
                html.Div(className='selector-tipo-grafico-container', children=[
                    # Alinhado à esquerda
                    html.Div(style={'flex': '1'}, children=[
                        html.Button('Série Temporal', id='btn-serie-temporal', className='tipo-grafico-btn ativo', n_clicks=0),
                        html.Button('Histograma', id='btn-histograma', className='tipo-grafico-btn', n_clicks=0, disabled=True),
                        html.Button('X-Y Correlação', id='btn-xy', className='tipo-grafico-btn', n_clicks=0, disabled=True),
                    ]),
                    # Botão Fixo de Ação à Direita (Conforme o layout da sua imagem)
                    html.Button('GERAR GRÁFICO', id='botao-gerar-grafico', className='toolbar-botao', style={
                        'borderColor': 'var(--cor-accent)',
                        'background': 'rgba(47, 165, 160, 0.1)',
                        'color': 'var(--cor-texto-escuro)',
                        'padding': '6px 14px'
                    }, n_clicks=0),
                ]),

                # Espaço reservado para o gráfico (Plotly desligado por padrão)
                dcc.Loading(
                    id="loading-grafico",
                    type="mono",
                    children=html.Div(id='container-grafico', style={'flex': '1', 'display': 'flex', 'flexDirection': 'column'}),
                ),

                # Console de eventos para o Desenvolvedor
                html.Pre(id='console-dev', className='console-dev', children='Aguardando dados...'),
            ]),

            # 3. PAINEL DA DIREITA (Opções adicionais de customização)
            html.Div(className='painel-direito', style={'width': '260px', 'minWidth': '260px'}, children=[
                html.Div('Opções do gráfico', className='painel-direito-titulo'),
                html.P('Propriedades e customizações da curva ativa.', className='painel-direito-placeholder'),
            ]),
        ]),

        # Linha 4: Rodapé
        html.Div(className='rodape', children=[
            html.Span(id='rodape-status', children='Pronto.'),
        ]),
    ])

    # --- Callbacks Totalmente Isolados (Evita loops cruzados e renderizações indesejadas) ---

    # Callback 1: Gerencia o Upload de Arquivos
    @app.callback(
        Output('aba-ativa-store', 'data'),
        Output('console-dev', 'children'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo, aba_atual):
        if conteudo is None:
            raise PreventUpdate
        if nome_arquivo in estado.arquivos:
            return nome_arquivo, f"Arquivo '{nome_arquivo}' já selecionado."
        try:
            df = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df)
            return nome_arquivo, f"Sucesso: '{nome_arquivo}' carregado com sucesso."
        except Exception as e:
            return aba_atual, f"Erro ao processar arquivo: {str(e)}"

    # Callback 2: Gerencia a alternância e fechamento de abas
    @app.callback(
        Output('aba-ativa-store', 'data', allow_duplicate=True),
        Output('container-abas-chrome', 'children'),
        Output('lista-canais-aba', 'children'),
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
        elif tipo == 'aba-item':
            aba_ativa = arquivo_alvo

        return aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa)

    # Callback 3: Gerencia estritamente a seleção visual das linhas de Canais
    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_selecao_canais(n_clicks_list, aba_ativa):
        if not ctx.triggered or not aba_ativa:
            raise PreventUpdate

        gatilho_id = ctx.triggered_id
        if gatilho_id and gatilho_id.get('type') == 'linha-canal':
            estado.alternar_selecao_canal(gatilho_id.get('arquivo'), gatilho_id.get('coluna'))

        return renderizar_colunas_da_aba_ativa(estado, aba_ativa)

    # Callback 4: Sincroniza a barra lateral quando um novo arquivo altera a aba ativa
    @app.callback(
        Output('container-abas-chrome', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Input('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_interface_por_aba(aba_ativa):
        return renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa)

    # Callback 5: EXECUÇÃO DO PLOT (Apenas sob demanda do clique do botão!)
    @app.callback(
        Output('container-grafico', 'children'),
        Input('botao-gerar-grafico', 'n_clicks'),
        prevent_initial_call=True,
    )
    def disparar_plotagem_sob_demanda(n_clicks):
        # Proteção Absoluta: Se não houver clique ou canais selecionados, impede o carregamento do Plotly
        if not n_clicks or not estado.canais_selecionados:
            return html.Div("Selecione os canais desejados e clique em 'GERAR GRÁFICO' para plotar.",
                            style={'margin': 'auto', 'color': 'var(--cor-texto-mudo)', 'fontSize': '12px', 'fontFamily': 'var(--fonte-ui)'})

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
            uirevision='constant'  # Impede perda de zoom ao re-plotar novos canais
        )

        return dcc.Graph(id='grafico-plotly-real', figure=fig, style={'flex': '1'})

    return app