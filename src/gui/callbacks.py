from dash import Input, Output, State, ctx, ALL, no_update
from dash.exceptions import PreventUpdate

from src.core.plotting.plotter import construir_figura_serie_temporal
from src.gui.renderizadores import (
    truncar_nome_arquivo, renderizar_abas_estilo_chrome, renderizar_colunas_da_aba_ativa,
    renderizar_area_grafico, renderizar_grafico_com_fechar,
)
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
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Input({'type': 'aba-item', 'arquivo': ALL}, 'n_clicks'),
        Input({'type': 'botao-fechar-aba', 'arquivo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_abas(_c_item, _c_fechar, aba_ativa):
        if not _clique_real(ctx.triggered):
            raise PreventUpdate

        aba_ativa_anterior = aba_ativa
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

        mudou_de_arquivo = aba_ativa != aba_ativa_anterior

        # Tratamento da área central:
        if aba_ativa is None:
            # Sem arquivos restantes -> Reseta para a área vazia/inicial
            area_grafico = renderizar_area_grafico(estado)
            botoes_dependentes = True
        elif mudou_de_arquivo and aba_ativa in estado.arquivos:
            dados_aba = estado.arquivos[aba_ativa]
            if dados_aba.get("grafico_gerado") and dados_aba.get("figura") is not None:
                area_grafico = renderizar_grafico_com_fechar(dados_aba["figura"])
                botoes_dependentes = False
            else:
                area_grafico = renderizar_area_grafico(estado)
                botoes_dependentes = True
        else:
            area_grafico = no_update
            botoes_dependentes = no_update

        return (aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                mensagem, len(estado.arquivos) == 0, len(estado.arquivos) < 2, area_grafico,
                botoes_dependentes, botoes_dependentes, botoes_dependentes, botoes_dependentes, botoes_dependentes)

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
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Input('central-btn-1', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_grafico_serie_temporal(n_clicks, aba_ativa):
        """
        Opção 1 da grade: 'Série Temporal' (linhas). O estilo específico
        desse gráfico mora em plotter.construir_figura_serie_temporal —
        cada opção futura (histograma, XY, etc.) deve ganhar sua própria
        função lá, e seu próprio callback aqui, do mesmo jeito.
        """
        if not n_clicks or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        if not estado.canais_selecionados:
            return (no_update, '🧙‍♂️: " Selecione ao menos um canal antes de gerar o gráfico. "',
                    no_update, no_update, no_update, no_update, no_update)

        fig = construir_figura_serie_temporal(estado)

        # 💾 SALVA O GRÁFICO ESPECÍFICO DESSA ABA NO ESTADO
        estado.arquivos[aba_ativa]["figura"] = fig
        estado.arquivos[aba_ativa]["grafico_gerado"] = True

        n_series = len(estado.canais_selecionados)
        mensagem = f'🧙‍♂️: " Gráfico gerado com {n_series} série(s). "'
        grafico = renderizar_grafico_com_fechar(fig)

        return grafico, mensagem, False, False, False, False, False

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Input('fechar-grafico', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def fechar_grafico(n_clicks, aba_ativa):
        """
        Fecha só a VISUALIZAÇÃO do gráfico, voltando pra grade de opções —
        não fecha arquivo nenhum (isso é o botão 'X' da aba, que já reseta
        tudo sozinho quando não sobra arquivo carregado).
        """
        if not n_clicks or not aba_ativa:
            raise PreventUpdate

        if aba_ativa in estado.arquivos:
            estado.arquivos[aba_ativa]["grafico_gerado"] = False
            estado.arquivos[aba_ativa]["figura"] = None

        area_grafico = renderizar_area_grafico(estado)
        mensagem = '🧙‍♂️: " Gráfico fechado. Escolha outra opção. "'

        return area_grafico, mensagem, True, True, True, True, True