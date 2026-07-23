from dash import Input, Output, State, ctx, ALL, no_update, dcc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from src.gui.renderizadores import truncar_nome_arquivo, renderizar_abas_estilo_chrome, renderizar_colunas_da_aba_ativa, renderizar_area_grafico
from src.utils.helpers import carregar_dados_de_upload


def _clique_real(ctx_triggered):
    """
    Protege contra o disparo 'fantasma' que callbacks de padrão (ALL) do
    Dash costumam dar assim que componentes novos são criados dinamicamente
    (ex: uma aba nova, uma linha de canal nova), mesmo sem clique nenhum do
    usuário. n_clicks nasce em 0/None nesses casos — só considera clique de
    verdade se o valor for truthy (>= 1).
    """
    return bool(ctx_triggered) and ctx_triggered[0].get('value') not in (None, 0)


def registrar_callbacks(app, estado):
    """
    Registra todos os callbacks do app. Recebe 'app' (pra decorar com
    @app.callback) e 'estado' (o EstadoApp global, compartilhado com
    layout.py) — este módulo não decide qual app instanciar nem qual
    estado usar, só liga os dois.
    """

    @app.callback(
        Output('aba-ativa-store', 'data'),
        Output('rodape-status', 'children'),
        Output('nova-analise', 'disabled'),
        Output('fundir-arquivos', 'disabled'),
        Output('container-grafico', 'children', allow_duplicate=True),
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
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, no_update)
        try:
            df = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df)

            # FORÇA a re-renderização da área central para desenhar a grade azul
            area_grafico = renderizar_area_grafico(estado)

            return (nome_arquivo, f'🧙‍♂️: " Arquivo \'{nome_arquivo}\' aberto com sucesso! pronto. "',
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, area_grafico)
        except Exception as e:
            return (aba_atual, f'🧙‍♂️: " Erro ao abrir arquivo: {str(e)} "',
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, no_update)

    @app.callback(
        Output('aba-ativa-store', 'data', allow_duplicate=True),
        Output('container-abas-chrome', 'children'),
        Output('lista-canais-aba', 'children'),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('nova-analise', 'disabled', allow_duplicate=True),
        Output('fundir-arquivos', 'disabled', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Input({'type': 'aba-item', 'arquivo': ALL}, 'n_clicks'),
        Input({'type': 'botao-fechar-aba', 'arquivo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_abas(_c_item, _c_fechar, aba_ativa):
        if not _clique_real(ctx.triggered):
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

        # só mexe na área do gráfico quando o ÚLTIMO arquivo fecha — fechar
        # uma aba entre várias não deveria apagar um gráfico já plotado
        area_grafico = renderizar_area_grafico(estado) if not estado.arquivos else no_update

        return (aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                mensagem, len(estado.arquivos) == 0, len(estado.arquivos) < 2, area_grafico)

    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_selecao_canais(n_clicks_list, aba_ativa):
        if not _clique_real(ctx.triggered) or not aba_ativa:
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
        grafico = dcc.Graph(id='grafico-plotly-real', figure=fig, style={'flex': '1', 'width': '100%', 'height': '100%'})

        return grafico, mensagem