"""
Callbacks de abas: trocar e fechar a aba ativa, e manter a interface
(abas, lista de canais, seleção de eixos, botões da calculadora) em
sincronia com ela.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import (
    _classe_painel_direito, _estados_toolbar, _processar_cliques_padrao,
)
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import (
    renderizar_abas_estilo_chrome, renderizar_area_grafico, renderizar_calculadora_botoes,
    renderizar_colunas_da_aba_ativa, renderizar_grafico_com_fechar,
    renderizar_painel_direito_padrao, renderizar_selecao_eixos,
)
from src.gui.rodape import obter_estado_rodape


def registrar_callbacks_abas(app, estado):

    # ------------------------------------------------------------------
    # Abas ('aba-item' pra trocar, 'botao-fechar-aba' pra fechar) — os
    # dois padrão coringa, então sujeitos ao mesmo "disparo fantasma"
    # de remontagem que _processar_cliques_padrao (src/callbacks/_comum.py)
    # existe pra filtrar: fechar/trocar de aba reconstrói a lista de
    # abas inteira, então clicar em QUALQUER botão de aba dispararia
    # este callback de novo sozinho sem o guard.
    # ------------------------------------------------------------------

    @app.callback(
        Output('aba-ativa-store', 'data', allow_duplicate=True),
        Output('container-abas-chrome', 'children'),
        Output('lista-canais-aba', 'children'),
        Output('selecao-eixos-container', 'children'),
        saida_feedback('abas'),
        Output('nova-analise', 'disabled', allow_duplicate=True),
        Output('fundir-arquivos', 'disabled', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('iniciar-edicao', 'disabled', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Output('rodape-info-arquivo', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Output('modo-nova-analise-store', 'data', allow_duplicate=True),
        Output('nova-analise', 'className', allow_duplicate=True),
        Output('area-grafico-normal', 'style', allow_duplicate=True),
        Output('area-modo-nova-analise', 'style', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'style', allow_duplicate=True),
        Input({'type': 'aba-item', 'arquivo': ALL}, 'n_clicks'),
        Input({'type': 'botao-fechar-aba', 'arquivo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('nclicks-padrao-store', 'data'),
        State('modo-nova-analise-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_abas(_c_item, _c_fechar, aba_ativa, nclicks_anteriores, modo_calculadora_ativo):
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate

        tipo = gatilho_id.get('type')
        arquivo_alvo = gatilho_id.get('arquivo')

        if tipo == 'botao-fechar-aba':
            estado.remover_arquivo(arquivo_alvo)
            if aba_ativa == arquivo_alvo:
                # A aba fechada era a ativa — escolhe a última restante
                # (ou None, se não sobrar nenhuma).
                restantes = list(estado.arquivos.keys())
                aba_ativa = restantes[-1] if restantes else None
        elif tipo == 'aba-item':
            aba_ativa = arquivo_alvo
        else:
            raise PreventUpdate

        # Trocar/fechar aba cancela a "próxima instrução" pendente de uma
        # mensagem temporária da aba anterior (Feedback.manter()).
        if estado.arquivos:
            feedback = Feedback.manter()
        else:
            feedback = Feedback.instrucao('Nenhum arquivo aberto. Carregue um arquivo pra começar.')

        # A área central precisa refletir o estado de VERDADE da nova
        # aba ativa — se ela já tinha um gráfico gerado antes (o
        # usuário só trocou de aba e voltou), mostra ELE de novo, não a
        # grade de opções do zero.
        arquivo_ativo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo_ativo and arquivo_ativo.grafico_gerado and arquivo_ativo.figura is not None:
            area_grafico = renderizar_grafico_com_fechar(arquivo_ativo.figura)
        else:
            area_grafico = renderizar_area_grafico(estado)

        sem_arquivo, sem_2_arquivos, sem_grafico_da_aba = _estados_toolbar(estado, aba_ativa)

        # Trocar/fechar aba SEMPRE desliga o modo 'Nova Análise' se
        # estava ligado — mesmo princípio já aplicado ao painel de
        # edição logo abaixo ('_classe_painel_direito(ativo=False)'):
        # o estado da calculadora (expressão em andamento, miniatura do
        # gráfico) é sobre UM arquivo específico, não faz sentido
        # continuar mostrando por cima de uma aba DIFERENTE. Sem isto,
        # fechar o arquivo com a calculadora aberta deixava a área da
        # calculadora visível (cobrindo o gráfico normal, que nem existe
        # mais se o arquivo foi fechado) e o botão 'nova-analise' preso
        # no visual "ativo" — nada se fechava sozinho.
        if modo_calculadora_ativo:
            modo_novo = False
            classe_botao_calc = 'toolbar-upload'
            estilo_grafico_normal = {'display': 'block'}
            estilo_area_calc = {'display': 'none'}
            estilo_area_edicao = {'display': 'none'}
        else:
            modo_novo = no_update
            classe_botao_calc = no_update
            estilo_grafico_normal = no_update
            estilo_area_calc = no_update
            estilo_area_edicao = no_update

        return (aba_ativa, renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                renderizar_selecao_eixos(estado, aba_ativa),
                feedback, sem_arquivo, sem_2_arquivos, area_grafico,
                sem_grafico_da_aba, sem_grafico_da_aba, sem_arquivo, sem_grafico_da_aba, sem_arquivo,
                sem_grafico_da_aba,
                _classe_painel_direito(ativo=False),
                renderizar_painel_direito_padrao(disabled=sem_grafico_da_aba),
                # Trocar/fechar aba muda qual arquivo é "o ativo": info, badge
                # e popup do rodapé precisam refletir a NOVA aba.
                *obter_estado_rodape(estado, aba_ativa),
                novo_mapa,
                modo_novo, classe_botao_calc, estilo_grafico_normal, estilo_area_calc, estilo_area_edicao)

    @app.callback(
        Output('container-abas-chrome', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'children', allow_duplicate=True),
        Input('aba-ativa-store', 'data'),
        State('modo-nova-analise-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_interface_por_aba(aba_ativa, modo_calculadora_ativo):
        # Os botões de COLUNA da calculadora (grupo 'Colunas', ver
        # renderizar_calculadora_botoes) dependem de qual arquivo está
        # ativo — sem isto, trocar de aba com o modo 'Nova Análise'
        # ligado deixava o painel de edição mostrando as colunas do
        # arquivo ANTERIOR, mesmo já estando noutra aba.
        botoes_calculadora = no_update
        if modo_calculadora_ativo:
            botoes_calculadora = renderizar_calculadora_botoes(estado, aba_ativa)
        return (renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                renderizar_selecao_eixos(estado, aba_ativa),
                botoes_calculadora)
