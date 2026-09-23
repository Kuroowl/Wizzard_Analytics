"""
Callbacks do modo de seleção de corte ('Aparar dados' / 'Excluir dados'):
iniciar -> registrar os 2 cliques no gráfico -> confirmar OU cancelar.

A operação sobre os dados (aparar_dados/excluir_dados) mora no core
(src/core/operations/sampling.py); aqui só a orquestração.

Observação: 'desligar_calculadora_ao_iniciar_corte' escuta os mesmos
botões, mas escreve só no estado da Nova Análise — por isso mora com ela,
não aqui. E 'fechar_grafico' (grafico.py) também cancela um corte em
andamento.
"""
from dash import Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import _classe_painel_direito
from src.core.operations.sampling import aparar_dados, excluir_dados
from src.core.plotting.plotter import (
    aplicar_guias_corte, construir_figura_serie_temporal, resolver_eixo_x,
)
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import renderizar_grafico_com_fechar


def registrar_callbacks_corte(app, estado):

    # ------------------------------------------------------------------
    # Modo de seleção de corte ('Aparar dados') — 4 callbacks formam o
    # ciclo completo: iniciar (clique no ícone) -> registrar cada clique
    # no gráfico (2 vezes) -> confirmar (aplica de verdade) OU cancelar
    # (desiste, sem tocar em nada). 'corte-selecao-store' é a fonte de
    # verdade compartilhada entre eles (ver dcc.Store em layout.py).
    #
    # A operação de dados em si (aparar_dados) já existe pronta em
    # src/core/operations/sampling.py — filtra 'arquivo.df_editado'
    # (nunca 'df_original', que fica intocado pra sempre — ver
    # src/core/arquivo.py), então desfazer é sempre possível recarregando
    # do zero, mesmo que essa etapa de "desfazer" ainda não tenha um
    # botão dedicado.
    # ------------------------------------------------------------------

    @app.callback(
        Output('corte-selecao-store', 'data'),
        Output('sidebar-principal', 'className'),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('toolbar-icones', 'className'),
        Output('container-grafico', 'className'),
        saida_feedback('corte-iniciar'),
        Input('aparar-dados', 'n_clicks'),
        Input('excluir-dados', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('painel-direito', 'className'),
        prevent_initial_call=True,
    )
    def iniciar_selecao_corte(n_clicks_aparar, n_clicks_excluir, aba_ativa, classe_painel_atual):
        """
        Liga o modo de seleção — de 'Aparar dados' OU 'Excluir dados'
        (mesmo mecanismo de 2 cliques pros dois; 'ctx.triggered_id' diz
        qual dos dois foi clicado, e isso vira 'tipo' em 'corte-
        selecao-store', lido depois por registrar_clique_corte
        (decide ONDE a hachura aparece) e confirmar_corte (decide qual
        operação de dados aplicar — aparar_dados ou excluir_dados,
        src/core/operations/sampling.py)).

        Borra sidebar/painel de edição ('.area-inativa-selecao',
        estilo.css — pointer-events desligado de verdade, não só
        visual), apaga os ícones da toolbar (menos o que foi clicado,
        que fica destacado — ver '.toolbar-icones.ferramenta-aparar/
        -excluir', icon_menu.css) e liga a classe 'corte-ativo' (é ela
        que faz iniciarSelecaoCorte, scripts_js.py, começar a reagir a
        mousemove/click no gráfico).

        A classe 'corte-ativo' vai em 'container-grafico' (o wrapper
        ESTÁVEL, definido uma vez em layout.py — nunca recriado), não
        direto no 'grafico-plotly-real' (o próprio dcc.Graph): esse
        componente, na prática, NÃO reflete atualizações de className
        via callback (peculiaridade da biblioteca — confirmado testando
        em navegador real: o mesmo callback atualiza sidebar/painel/
        ícones sem problema, só o className do Graph em si fica
        parado). scripts_js.py já sabe ler a classe daqui e olhar o
        elemento do Plotly separadamente.

        NÃO mexe no modo 'Nova Análise' — de propósito, voltou a ser
        assim (era assim antes de uma tentativa de fazer os dois
        coexistirem, que introduziu um bug novo de "disparo fantasma"
        na calculadora sem relação nenhuma aparente, mas que sumiu ao
        reverter esta função pro estado original). Quem desliga o modo
        calculadora ao clicar em 'Aparar dados'/'Excluir dados' agora é
        um callback SEPARADO e independente — ver
        desligar_calculadora_ao_iniciar_corte, logo abaixo — que não
        toca em NENHUM dos Outputs desta função aqui, só observa os
        MESMOS 2 botões em paralelo.
        """
        gatilho = ctx.triggered_id
        if gatilho not in ('aparar-dados', 'excluir-dados'):
            raise PreventUpdate
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        # Preserva se o painel de edição JÁ estava aberto antes de
        # começar a seleção — 'painel_ativo' viaja dentro de
        # 'corte-selecao-store' até confirmar_corte/cancelar_corte
        # (mais abaixo), pra devolver o painel exatamente a este mesmo
        # estado ao terminar, em vez de forçar fechado (ver docstring
        # de _classe_painel_direito).
        painel_ativo = bool(classe_painel_atual) and 'ativa' in classe_painel_atual.split()

        tipo = 'aparar' if gatilho == 'aparar-dados' else 'excluir'
        dados_selecao = {
            'tipo': tipo, 'aba': aba_ativa, 'primeiro': None, 'segundo': None,
            'painel_ativo': painel_ativo,
        }
        if tipo == 'aparar':
            feedback = Feedback.instrucao('Clique no gráfico para marcar o INÍCIO do recorte.')
        else:
            feedback = Feedback.instrucao('Clique no gráfico para marcar o INÍCIO do trecho a excluir.')

        return (
            dados_selecao,
            'sidebar area-inativa-selecao',
            _classe_painel_direito(ativo=painel_ativo, selecionando=True),
            'toolbar-icones inativo ferramenta-' + tipo,
            'area-grafico-container corte-ativo',
            feedback,
        )

    @app.callback(
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('grafico-plotly-real', 'figure', allow_duplicate=True),
        saida_feedback('corte-clique'),
        Output('toolbar-confirmacao-corte', 'style'),
        Output('container-grafico', 'className', allow_duplicate=True),
        Input('corte-clique-x', 'value'),
        State('corte-selecao-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def registrar_clique_corte(valor_x, dados_selecao, aba_ativa):
        """
        Reage a CADA clique no gráfico (o valor chega via
        'corte-clique-x', escrito pelo JS — ver iniciarSelecaoCorte em
        scripts_js.py) enquanto uma seleção está em andamento.

        1º clique: vira 'primeiro'. Em modo 'aparar', já redesenha com
        uma guia sólida + hachura à esquerda dela — cada faixa já faz
        sentido sozinha ("tudo antes deste ponto"). Em modo 'excluir',
        só a linha aparece ainda (sem hachura — com um clique só não
        dá pra saber a extensão do trecho a excluir); ver 'modo' em
        aplicar_guias_corte, plotter.py.
        2º clique: só é aceito se for MAIOR que o primeiro (senão o
        intervalo não faz sentido — ignora silenciosamente, o usuário
        só tenta de novo); vira 'segundo' — redesenha com as DUAS
        guias (+ a hachura, nos dois modos agora — em 'excluir' ela só
        nasce aqui, cobrindo o intervalo ENTRE os dois pontos), revela
        o prompt 'Confirmar seleção?' na toolbar E soma a classe
        'corte-completo' em 'container-grafico' (junto com 'corte-
        ativo', que continua lá) — é essa classe extra que faz a guia
        TRACEJADA parar de seguir o mouse (ver iniciarSelecaoCorte,
        scripts_js.py: só desenha a guia viva quando 'corte-ativo'
        está presente E 'corte-completo' não está). Cliques depois
        disso (os dois já marcados) são ignorados — só resta confirmar
        ou cancelar.
        """
        if not dados_selecao or valor_x is None:
            raise PreventUpdate
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        tipo = dados_selecao.get('tipo', 'aparar')
        primeiro = dados_selecao.get('primeiro')
        segundo = dados_selecao.get('segundo')
        classe_container = no_update

        if primeiro is None:
            primeiro = valor_x
            if tipo == 'aparar':
                feedback = Feedback.instrucao('Agora clique um pouco mais à direita para marcar o FIM do recorte.')
            else:
                feedback = Feedback.instrucao('Agora clique um pouco mais à direita para marcar o FIM do trecho a excluir.')
            estilo_prompt = no_update
        elif segundo is None:
            if valor_x <= primeiro:
                raise PreventUpdate
            segundo = valor_x
            feedback = Feedback.instrucao('Confirma?')
            estilo_prompt = {'display': 'flex'}
            classe_container = 'area-grafico-container corte-ativo corte-completo'
        else:
            raise PreventUpdate

        dados_selecao = dict(dados_selecao, primeiro=primeiro, segundo=segundo)
        # 'arrastavel' fica sempre False por enquanto — ver comentário
        # em _pilula_arraste/aplicar_guias_corte (plotter.py) sobre a
        # interação de arraste estar PAUSADA (o passo a passo pra
        # retomar está lá).
        fig = aplicar_guias_corte(arquivo.figura, primeiro=primeiro, segundo=segundo, arrastavel=False, modo=tipo)
        return dados_selecao, fig, feedback, estilo_prompt, classe_container

    # PAUSADO por enquanto: arraste das guias já confirmadas (ver
    # comentário detalhado em aplicar_guias_corte, plotter.py, com o
    # passo a passo completo pra retomar — inclui religar este
    # callback). Já tinha ficado funcionando e testado em navegador
    # real (linha/hachura/manípulo sincronizados, limite entre os 2
    # cortes respeitado), mas a decisão foi adiar essa interação
    # específica por enquanto ("a barra ainda não está 100%").
    #
    # @app.callback(
    #     Output('corte-selecao-store', 'data', allow_duplicate=True),
    #     Output('grafico-plotly-real', 'figure', allow_duplicate=True),
    #     Input('corte-arraste-primeiro', 'value'),
    #     Input('corte-arraste-segundo', 'value'),
    #     State('corte-selecao-store', 'data'),
    #     State('aba-ativa-store', 'data'),
    #     prevent_initial_call=True,
    # )
    # def arrastar_corte(novo_primeiro, novo_segundo, dados_selecao, aba_ativa):
    #     if not dados_selecao:
    #         raise PreventUpdate
    #     if not aba_ativa or aba_ativa not in estado.arquivos:
    #         raise PreventUpdate
    #
    #     primeiro = dados_selecao.get('primeiro')
    #     segundo = dados_selecao.get('segundo')
    #     if primeiro is None or segundo is None:
    #         raise PreventUpdate
    #
    #     gatilho = ctx.triggered_id
    #     if gatilho == 'corte-arraste-primeiro':
    #         if novo_primeiro is None or novo_primeiro >= segundo:
    #             raise PreventUpdate
    #         primeiro = novo_primeiro
    #     elif gatilho == 'corte-arraste-segundo':
    #         if novo_segundo is None or novo_segundo <= primeiro:
    #             raise PreventUpdate
    #         segundo = novo_segundo
    #     else:
    #         raise PreventUpdate
    #
    #     arquivo = estado.arquivos[aba_ativa]
    #     dados_selecao = dict(dados_selecao, primeiro=primeiro, segundo=segundo)
    #     tipo = dados_selecao.get('tipo', 'aparar')
    #     fig = aplicar_guias_corte(arquivo.figura, primeiro=primeiro, segundo=segundo, arrastavel=True, modo=tipo)
    #     return dados_selecao, fig

    def _restaurar_apos_selecao(painel_ativo=False):
        """
        Devolve os 5 valores que desligam o modo de seleção — comuns a
        confirmar_corte e cancelar_corte (só a figura final e a
        mensagem mudam entre os dois, ver cada callback abaixo).

        'painel_ativo' precisa vir de 'dados_selecao.get("painel_ativo")'
        (gravado lá atrás em iniciar_selecao_corte) — NUNCA fixo em
        False aqui, senão o painel de edição sempre fecha ao
        confirmar/cancelar um corte, mesmo quando estava aberto antes
        de a seleção começar (ver docstring de _classe_painel_direito).
        """
        return (
            None,
            'sidebar',
            _classe_painel_direito(ativo=painel_ativo),
            'toolbar-icones',
            'area-grafico-container',
            {'display': 'none'},
        )

    @app.callback(
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('sidebar-principal', 'className', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('toolbar-icones', 'className', allow_duplicate=True),
        Output('container-grafico', 'className', allow_duplicate=True),
        Output('toolbar-confirmacao-corte', 'style', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        saida_feedback('corte-confirmar'),
        Input('corte-confirmar', 'n_clicks'),
        State('corte-selecao-store', 'data'),
        prevent_initial_call=True,
    )
    def confirmar_corte(n_clicks, dados_selecao):
        """
        Aplica o corte DE VERDADE — 'aparar_dados' (mantém só o que
        fica ENTRE os dois cliques) OU 'excluir_dados' (remove o que
        fica entre eles, mantém o resto — src/core/operations/
        sampling.py, conforme 'tipo' em 'corte-selecao-store', ver
        iniciar_selecao_corte acima) — filtrando 'arquivo.df_editado'
        (NUNCA 'df_original', que continua intocado — ver
        src/core/arquivo.py), redesenha o gráfico do zero a partir
        desses dados já filtrados (nenhuma guia/hachura sobra — essas
        eram só um overlay temporário em cima da figura antiga) e
        desliga o modo de seleção.
        """
        if not n_clicks or not dados_selecao:
            raise PreventUpdate

        aba_ativa = dados_selecao.get('aba')
        tipo = dados_selecao.get('tipo', 'aparar')
        primeiro = dados_selecao.get('primeiro')
        segundo = dados_selecao.get('segundo')
        if not aba_ativa or aba_ativa not in estado.arquivos or primeiro is None or segundo is None:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        eixo_x = resolver_eixo_x(estado, arquivo)
        if tipo == 'excluir':
            arquivo.df_editado = excluir_dados(arquivo.df_editado, eixo_x, primeiro, segundo)
            feedback = Feedback.sucesso('Trecho excluído! O que estava entre os dois cortes sumiu, o resto ficou.')
        else:
            arquivo.df_editado = aparar_dados(arquivo.df_editado, eixo_x, primeiro, segundo)
            feedback = Feedback.sucesso('Dados aparados! Só ficou o que estava entre os dois cortes.')
        arquivo.invalidar_grafico()

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        container_grafico = renderizar_grafico_com_fechar(fig)

        _, sidebar, painel, icones, grafico_classe, prompt_estilo = _restaurar_apos_selecao(
            painel_ativo=dados_selecao.get('painel_ativo', False))
        return None, sidebar, painel, icones, grafico_classe, prompt_estilo, container_grafico, feedback

    @app.callback(
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('sidebar-principal', 'className', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('toolbar-icones', 'className', allow_duplicate=True),
        Output('container-grafico', 'className', allow_duplicate=True),
        Output('toolbar-confirmacao-corte', 'style', allow_duplicate=True),
        Output('grafico-plotly-real', 'figure', allow_duplicate=True),
        saida_feedback('corte-cancelar'),
        Input('corte-cancelar', 'n_clicks'),
        State('corte-selecao-store', 'data'),
        prevent_initial_call=True,
    )
    def cancelar_corte(n_clicks, dados_selecao):
        """
        Desiste da seleção sem tocar em nada — os dados nunca foram
        alterados (aparar_dados só é chamado em confirmar_corte, aqui
        acima), então "desfazer" é simplesmente reexibir
        'arquivo.figura' original (sem as guias/hachura, que eram só
        um overlay client-side/temporário) e desligar o modo de
        seleção.
        """
        if not n_clicks or not dados_selecao:
            raise PreventUpdate

        aba_ativa = dados_selecao.get('aba')
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        fig = arquivo.figura if arquivo and arquivo.grafico_gerado else no_update
        feedback = Feedback.info('Seleção cancelada. Nada foi alterado.')

        _, sidebar, painel, icones, grafico_classe, prompt_estilo = _restaurar_apos_selecao(
            painel_ativo=dados_selecao.get('painel_ativo', False))
        return None, sidebar, painel, icones, grafico_classe, prompt_estilo, fig, feedback
