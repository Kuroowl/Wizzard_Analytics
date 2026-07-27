from dash import Input, Output, State, ctx, ALL, no_update
from dash.exceptions import PreventUpdate

from src.core.plotting.plotter import construir_figura_serie_temporal
from src.gui.renderizadores import (
    truncar_nome_arquivo, renderizar_abas_estilo_chrome, renderizar_colunas_da_aba_ativa,
    renderizar_area_grafico, renderizar_grafico_com_fechar,
    renderizar_info_rodape, renderizar_badge_alerta, classe_badge_alerta, renderizar_popup_alerta,
)
from src.utils.helpers import carregar_dados_de_upload


def _clique_real(ctx_triggered):
    """
    Protege contra o disparo 'fantasma' que callbacks de padrão (ALL) do
    Dash costumam dar assim que componentes novos são criados dinamicamente
    (ex: uma aba nova, uma linha de canal nova), mesmo sem clique nenhum do
    usuário.

    Antes essa checagem também exigia `value not in (None, 0)`, mas para
    arquivos com nomes de coluna "atípicos" (ex.: 'N#', 'FW-A') o valor
    relatado por `ctx.triggered` no primeiro clique real de uma linha
    recém-renderizada nem sempre batia com o esperado, fazendo cliques de
    verdade serem descartados como fantasma. Bastar existir um gatilho já
    é suficiente aqui, porque cada callback que usa isso confere também o
    `type` do gatilho (`ctx.triggered_id.get('type')`) antes de agir.
    """
    return bool(ctx_triggered)


def _valores_rodape(estado, aba_ativa):
    """
    Agrupa os 4 valores que qualquer callback que mexe no rodapé precisa
    devolver, sempre na mesma ordem: (info, badge_texto, badge_classe,
    popup_children). Existe só pra não repetir as mesmas 4 chamadas em
    cada callback abaixo.
    """
    return (
        renderizar_info_rodape(estado, aba_ativa),
        renderizar_badge_alerta(estado, aba_ativa),
        classe_badge_alerta(estado, aba_ativa),
        renderizar_popup_alerta(estado, aba_ativa),
    )


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
        Output('rodape-info-arquivo', 'children'),
        Output('rodape-alerta-badge', 'children'),
        Output('rodape-alerta-badge', 'className'),
        Output('rodape-alerta-popup', 'children'),
        Output('rodape-mensagem-seguinte', 'data'),
        Output('rodape-timer-mensagem', 'disabled'),
        Output('rodape-timer-mensagem', 'n_intervals'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo, aba_atual):
        if conteudo is None:
            raise PreventUpdate

        if nome_arquivo in estado.arquivos:
            # Arquivo já aberto: mensagem PERSISTENTE — cancela qualquer
            # timer pendente (senão uma expiração antiga poderia
            # sobrescrever essa mensagem daqui a pouco).
            mensagem = f'🧙‍♂️: " O arquivo \'{nome_arquivo}\' já foi aberto! "'
            return (nome_arquivo, mensagem,
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, no_update,
                    *_valores_rodape(estado, nome_arquivo),
                    no_update, True, no_update)
        try:
            df, avisos, info = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df, avisos, info)

            # FORÇA a re-renderização da área central para desenhar a grade azul
            area_grafico = renderizar_area_grafico(estado)

            # Mensagem TEMPORÁRIA: aparece, some sozinha em ~3.5s e dá lugar
            # à próxima instrução ("Escolha uma opção de gráfico...") — ver
            # 'rodape-timer-mensagem' / expirar_mensagem_temporaria() abaixo.
            mensagem = f'🧙‍♂️: " Arquivo \'{nome_arquivo}\' carregado com sucesso! "'
            mensagem_seguinte = '🧙‍♂️: " Escolha uma opção de gráfico... "'

            return (nome_arquivo, mensagem,
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, area_grafico,
                    *_valores_rodape(estado, nome_arquivo),
                    mensagem_seguinte, False, 0)
        except Exception as e:
            mensagem = f'🧙‍♂️: " Erro ao abrir arquivo: {str(e)} "'
            return (aba_atual, mensagem,
                    len(estado.arquivos) == 0, len(estado.arquivos) < 2, no_update,
                    *_valores_rodape(estado, aba_atual),
                    no_update, True, no_update)

    @app.callback(
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input('rodape-timer-mensagem', 'n_intervals'),
        State('rodape-mensagem-seguinte', 'data'),
        prevent_initial_call=True,
    )
    def expirar_mensagem_temporaria(n_intervals, mensagem_seguinte):
        """
        Dispara quando uma mensagem temporária do mago (a inicial, ou o
        'Arquivo carregado com sucesso!') termina seu tempo de exibição.
        Troca o texto do rodapé pelo que ficou guardado em
        'rodape-mensagem-seguinte' (pode ser '' — nesse caso a mensagem
        simplesmente some) e desarma o timer de novo.
        """
        if not n_intervals:
            raise PreventUpdate
        return (mensagem_seguinte or ''), True

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
        Output('rodape-info-arquivo', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
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
            arquivo = estado.arquivos[aba_ativa]
            if arquivo.grafico_gerado:
                area_grafico = renderizar_grafico_com_fechar(arquivo.figura)
                botoes_dependentes = False
            else:
                area_grafico = renderizar_area_grafico(estado)
                botoes_dependentes = True
        else:
            area_grafico = no_update
            botoes_dependentes = no_update

        return (aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                mensagem, len(estado.arquivos) == 0, len(estado.arquivos) < 2, area_grafico,
                botoes_dependentes, botoes_dependentes, botoes_dependentes, botoes_dependentes, botoes_dependentes,
                # Trocar/fechar aba muda qual arquivo é "o ativo": info, badge
                # e popup do rodapé precisam refletir a NOVA aba, e qualquer
                # mensagem temporária pendente da aba anterior é cancelada.
                *_valores_rodape(estado, aba_ativa),
                True)

    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_selecao_canais(n_clicks_list, aba_ativa):
        if not _clique_real(ctx.triggered) or not aba_ativa:
            raise PreventUpdate

        gatilho_id = ctx.triggered_id
        mensagem = no_update
        area_grafico = no_update

        if gatilho_id and gatilho_id.get('type') == 'linha-canal':
            arquivo, coluna = gatilho_id.get('arquivo'), gatilho_id.get('coluna')
            estado.alternar_selecao_canal(arquivo, coluna)
            ligado = (arquivo, coluna) in estado.canais_selecionados
            acao = 'ativado' if ligado else 'desativado'
            mensagem = f'🧙‍♂️: " Canal \'{coluna}\' {acao}. ({len(estado.canais_selecionados)} selecionado(s)) "'

            # Só redesenha o gráfico se a aba ativa já estiver com um
            # gráfico aberto (senão ainda estamos na grade de opções, e
            # marcar um canal não deve pular direto pra visualização).
            arquivo = estado.arquivos.get(aba_ativa)
            if arquivo and arquivo.grafico_gerado:
                # Pode empurrar o aviso de amostragem (>5000 linhas) pra
                # lista de avisos da aba — por isso recalculamos o badge
                #/popup do rodapé logo abaixo, depois desta chamada.
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)

        _, badge_texto, badge_classe, popup_children = _valores_rodape(estado, aba_ativa)
        return (renderizar_colunas_da_aba_ativa(estado, aba_ativa), mensagem, area_grafico,
                badge_texto, badge_classe, popup_children,
                True)

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
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input('central-btn-1', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_grafico_serie_temporal(n_clicks, aba_ativa):
        if not n_clicks or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        # Gera o gráfico com os canais já marcados até agora (pode ser
        # nenhum ainda — nesse caso nasce em branco, e o usuário vai
        # populando ao marcar colunas na barra lateral). Se o arquivo tiver
        # mais de 5000 linhas, essa chamada também empurra um aviso de
        # amostragem pra lista de avisos da aba (ver plotter.py).
        fig = construir_figura_serie_temporal(estado, aba_ativa)

        # Salva o gráfico no estado da aba ativa. 'grafico_gerado' é uma
        # property derivada de 'figura' (ver src/core/arquivo.py) — não
        # precisa (e não pode) ser setada à parte.
        estado.arquivos[aba_ativa].figura = fig

        tem_canal = any(arq == aba_ativa for arq, _ in estado.canais_selecionados)
        mensagem = (
            '🧙‍♂️: " Gráfico de série temporal gerado. Marque os canais na barra lateral. "'
            if not tem_canal else
            '🧙‍♂️: " Gráfico de série temporal gerado. "'
        )
        grafico = renderizar_grafico_com_fechar(fig)

        _, badge_texto, badge_classe, popup_children = _valores_rodape(estado, aba_ativa)
        return (grafico, mensagem, False, False, False, False, False,
                badge_texto, badge_classe, popup_children,
                True)

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
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
            estado.arquivos[aba_ativa].invalidar_grafico()

        area_grafico = renderizar_area_grafico(estado)
        mensagem = '🧙‍♂️: " Gráfico fechado. Escolha outra opção. "'

        return area_grafico, mensagem, True, True, True, True, True, True
