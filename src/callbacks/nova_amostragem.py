"""
Callbacks da Nova Amostragem (botão 'nova-amostra' da toolbar).

Liga/desliga o modo (barra de operações em cima do gráfico + painel
direito com a árvore de dados e a configuração), escolhe a operação e o
canal, gera o Preview e mantém o painel em dia com o que está no gráfico.

Regras de convivência (decisões da Fase 4):
  - Nova Amostragem e Nova Análise nunca ficam ligadas juntas: ligar uma
    desliga a outra;
  - Aparar/Excluir, fechar o gráfico e trocar/fechar aba desligam a Nova
    Amostragem (ela parte do X e dos Y desenhados na aba ativa).
  - O Preview some ao trocar de operação e ao desligar o modo; um novo
    Preview substitui o anterior.

O cálculo mora no core (src/core/operations/amostragem.py, Arquivo); a
aparência em src/gui/amostragem.py; o desenho do preview no plotter. Aqui
só a orquestração.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import processar_cliques_padrao
from src.core.operations.amostragem import OPERACOES, nome_padrao
from src.core.plotting.plotter import construir_figura_serie_temporal, resolver_eixo_x
from src.gui.amostragem import (
    CAMPOS_PARAMETROS, OPERACOES_BARRA, classe_botao_operacao, renderizar_config_amostragem,
    renderizar_painel_amostragem, renderizar_resultado_amostragem,
)
from src.gui.feedback import Feedback, saida_feedback

ESCONDIDO = {'display': 'none'}
VISIVEL = {'display': 'flex'}
CLASSE_BOTAO_TOOLBAR = 'toolbar-upload'
FIGURA_GRAFICO = Output('grafico-plotly-real', 'figure', allow_duplicate=True)


def _classes_barra(operacao):
    """className de cada botão da barra, na ordem do layout (Output com ALL)."""
    return [classe_botao_operacao(chave, operacao) for chave, _, _ in OPERACOES_BARRA]


def _eixo_x(estado, arquivo):
    return resolver_eixo_x(estado, arquivo) if arquivo is not None else None


def registrar_callbacks_nova_amostragem(app, estado):

    def painel(aba_ativa, operacao, canal_y):
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        return renderizar_painel_amostragem(estado, aba_ativa, _eixo_x(estado, arquivo), operacao, canal_y)

    def redesenhar(nome):
        """Remonta a figura de um arquivo (e o cache dela). Devolve a figura."""
        fig = construir_figura_serie_temporal(estado, nome)
        estado.arquivos[nome].figura = fig
        return fig

    def tirar_preview(aba_ativa):
        """
        Tira o preview da aba ativa. Devolve a figura nova pro Output do
        gráfico, ou no_update se não havia preview (nada a redesenhar).
        """
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is None or not arquivo.grafico_gerado:
            return no_update
        if not arquivo.limpar_preview_amostragem():
            return no_update
        return redesenhar(aba_ativa)

    def tirar_previews_em_segundo_plano():
        """
        Tira o preview de TODOS os arquivos sem tocar no gráfico da tela —
        pra quando a aba mudou (o preview era de outra aba, que só precisa
        do cache sem ele pra quando o usuário voltar).
        """
        for nome, arquivo in list(estado.arquivos.items()):
            tinha_grafico = arquivo.grafico_gerado
            if arquivo.limpar_preview_amostragem() and tinha_grafico:
                redesenhar(nome)

    # ------------------------------------------------------------------
    # Liga/desliga. Ligar desliga a Nova Análise (mesmas áreas da tela).
    # Desligar esquece a operação escolhida e tira o preview.
    # 'nova-amostra' é id fixo, nunca redesenhado: basta 'not n_clicks'.
    # O modo só liga com gráfico na tela (botão desabilitado sem ele), então
    # 'grafico-plotly-real' sempre existe quando o preview precisa sair.
    # ------------------------------------------------------------------
    @app.callback(
        Output('modo-nova-amostragem-store', 'data'),
        Output('nova-amostra', 'className'),
        Output('area-modo-nova-amostragem', 'style'),
        Output('area-modo-nova-amostragem-edicao', 'style'),
        Output('area-modo-nova-amostragem-edicao', 'children'),
        Output('amostragem-operacao-store', 'data'),
        Output({'type': 'amostragem-op', 'op': ALL}, 'className'),
        saida_feedback('amostragem-modo'),
        Output('modo-nova-analise-store', 'data', allow_duplicate=True),
        Output('nova-analise', 'className', allow_duplicate=True),
        Output('area-modo-nova-analise', 'style', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'style', allow_duplicate=True),
        FIGURA_GRAFICO,
        Input('nova-amostra', 'n_clicks'),
        State('modo-nova-amostragem-store', 'data'),
        State('modo-nova-analise-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('amostragem-canal-y-store', 'data'),
        prevent_initial_call=True,
    )
    def alternar_modo_nova_amostragem(n_clicks, ativo, analise_ativa, aba_ativa, canal_y):
        if not n_clicks:
            raise PreventUpdate

        if ativo:
            return (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO, no_update,
                    None, _classes_barra(None), Feedback.info('Nova Amostragem desligada.'),
                    no_update, no_update, no_update, no_update,
                    tirar_preview(aba_ativa))

        desligar_analise = (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO) if analise_ativa \
            else (no_update,) * 4
        feedback = Feedback.instrucao(
            'Nova Amostragem: escolha uma operação na barra acima do gráfico.')
        return (True, CLASSE_BOTAO_TOOLBAR + ' ativo', VISIVEL, VISIVEL,
                painel(aba_ativa, None, canal_y), None, _classes_barra(None), feedback,
                *desligar_analise, no_update)

    # ------------------------------------------------------------------
    # Desliga quando outro modo/ação toma a tela. Callbacks à parte (em vez
    # de Outputs a mais nos callbacks da Nova Análise, do corte, do gráfico
    # e das abas) pelo mesmo motivo de 'desligar_calculadora_ao_iniciar_
    # corte': cada módulo cuida do próprio estado.
    # ------------------------------------------------------------------
    SAIDAS_DESLIGAR = (
        Output('modo-nova-amostragem-store', 'data', allow_duplicate=True),
        Output('nova-amostra', 'className', allow_duplicate=True),
        Output('area-modo-nova-amostragem', 'style', allow_duplicate=True),
        Output('area-modo-nova-amostragem-edicao', 'style', allow_duplicate=True),
        Output('amostragem-operacao-store', 'data', allow_duplicate=True),
        Output({'type': 'amostragem-op', 'op': ALL}, 'className', allow_duplicate=True),
    )
    DESLIGADO = (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO, None, _classes_barra(None))

    # Nova Análise / Aparar / Excluir: o gráfico continua na tela, então o
    # preview sai redesenhando a figura no lugar ('figure', não o container
    # inteiro — o corte liga o clique no gráfico que já está na tela).
    @app.callback(
        *SAIDAS_DESLIGAR,
        saida_feedback('amostragem-desligar'),
        FIGURA_GRAFICO,
        Input('nova-analise', 'n_clicks'),
        Input('aparar-dados', 'n_clicks'),
        Input('excluir-dados', 'n_clicks'),
        State('modo-nova-amostragem-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_nova_amostragem(_analise, _aparar, _excluir, ativo, aba_ativa):
        if not ativo or processar_cliques_padrao(ctx.inputs_list) is None:
            raise PreventUpdate
        # Corte já diz o que está acontecendo; a Nova Análise não fala nada
        # ao ligar, então a mensagem vem daqui (senão ficaria a última
        # instrução da Amostragem).
        feedback = Feedback.info('Nova Análise ligada. A Nova Amostragem foi desligada.') \
            if ctx.triggered_id == 'nova-analise' else no_update
        return (*DESLIGADO, feedback, tirar_preview(aba_ativa))

    # Troca/abertura/fechamento de aba: o gráfico da tela já é de outra aba
    # (quem desenha é o callback das abas) — o preview sai só do cache.
    @app.callback(
        *SAIDAS_DESLIGAR,
        Input('aba-ativa-store', 'data'),
        State('modo-nova-amostragem-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_nova_amostragem_ao_trocar_aba(_aba, ativo):
        if not ativo:
            raise PreventUpdate
        tirar_previews_em_segundo_plano()
        return DESLIGADO

    # 'fechar-grafico' só existe enquanto há gráfico (nasce dentro dele, a
    # cada redesenho): num callback só dele, pra a ausência do botão não
    # atrapalhar os gatilhos acima. O gráfico está sendo fechado: o preview
    # só é esquecido (a figura é descartada pelo próprio fechar_grafico).
    @app.callback(
        *SAIDAS_DESLIGAR,
        Input('fechar-grafico', 'n_clicks'),
        State('modo-nova-amostragem-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_nova_amostragem_ao_fechar_grafico(n_clicks, ativo, aba_ativa):
        if not ativo or not n_clicks:
            raise PreventUpdate
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is not None:
            arquivo.limpar_preview_amostragem()
        return DESLIGADO

    # ------------------------------------------------------------------
    # Escolher a operação na barra. Os botões são fixos no layout, mas usam
    # padrão coringa: o filtro anti-fantasma vale do mesmo jeito. Trocar de
    # operação tira o preview da anterior.
    # ------------------------------------------------------------------
    @app.callback(
        Output('amostragem-operacao-store', 'data', allow_duplicate=True),
        Output({'type': 'amostragem-op', 'op': ALL}, 'className', allow_duplicate=True),
        Output('area-modo-nova-amostragem-edicao', 'children', allow_duplicate=True),
        saida_feedback('amostragem-operacao'),
        FIGURA_GRAFICO,
        Input({'type': 'amostragem-op', 'op': ALL}, 'n_clicks'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('amostragem-canal-y-store', 'data'),
        prevent_initial_call=True,
    )
    def escolher_operacao_amostragem(_cliques, operacao_atual, aba_ativa, canal_y):
        gatilho = processar_cliques_padrao(ctx.inputs_list)
        if gatilho is None:
            raise PreventUpdate
        operacao = gatilho.get('op')
        if operacao not in OPERACOES or operacao == operacao_atual:
            raise PreventUpdate
        figura = tirar_preview(aba_ativa)
        feedback = Feedback.instrucao(
            f'{OPERACOES[operacao].rotulo}: escolha o canal e os parâmetros e clique em Preview.')
        return operacao, _classes_barra(operacao), painel(aba_ativa, operacao, canal_y), feedback, figura

    # ------------------------------------------------------------------
    # Canal Y escolhido no painel: guarda (pra sobreviver aos redesenhos do
    # painel) e refaz só a configuração — os valores iniciais dos
    # parâmetros (ex: Δx sugerido) dependem dos dados desse canal.
    # O dropdown nasce de novo a cada redesenho com o valor já guardado:
    # valor igual ao do Store = redesenho, não escolha do usuário.
    # ------------------------------------------------------------------
    @app.callback(
        Output('amostragem-canal-y-store', 'data'),
        Output('amostragem-config-container', 'children'),
        Input('amostragem-canal-y', 'value'),
        State('amostragem-canal-y-store', 'data'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def escolher_canal_y_amostragem(canal_y, canal_guardado, operacao, aba_ativa):
        if not canal_y or canal_y == canal_guardado:
            raise PreventUpdate
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is None or operacao not in OPERACOES:
            raise PreventUpdate
        return canal_y, renderizar_config_amostragem(arquivo, _eixo_x(estado, arquivo), operacao, canal_y)

    # ------------------------------------------------------------------
    # Preview: calcula sobre os dados atuais e desenha por cima do gráfico,
    # sem registrar nada. Clicar de novo (com outros parâmetros) substitui.
    # 'amostragem-preview' nasce dentro da configuração redesenhada: filtro
    # anti-fantasma.
    # ------------------------------------------------------------------
    @app.callback(
        FIGURA_GRAFICO,
        Output('amostragem-resultado', 'children'),
        saida_feedback('amostragem-preview'),
        Input('amostragem-preview', 'n_clicks'),
        State('amostragem-canal-y', 'value'),
        State({'type': 'amostragem-param', 'nome': ALL}, 'value'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_preview_amostragem(_n, canal_y, _valores, operacao, aba_ativa):
        if processar_cliques_padrao(ctx.inputs_list) is None:
            raise PreventUpdate
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is None or operacao not in OPERACOES or not canal_y:
            raise PreventUpdate

        parametros = {item['id']['nome']: item.get('value') for item in ctx.states_list[1]}
        faltando = [CAMPOS_PARAMETROS[operacao][nome][0] for nome, valor in parametros.items() if valor is None]
        if faltando:
            return no_update, no_update, Feedback.aviso(f"Preencha: {', '.join(faltando)}.")

        eixo_x = _eixo_x(estado, arquivo)
        try:
            preview = arquivo.gerar_preview_amostragem(operacao, parametros, canal_y, eixo_x)
        except ValueError as erro:
            # Nada mudou: o preview anterior (se havia) continua no gráfico.
            return no_update, no_update, Feedback.erro(f'Preview não gerado: {erro}')

        nome = nome_padrao(operacao, arquivo.rotulo(canal_y))
        feedback = Feedback.sucesso(f'Preview de {nome}: {len(preview.serie)} pontos no gráfico.')
        return redesenhar(aba_ativa), renderizar_resultado_amostragem(preview), feedback

    # ------------------------------------------------------------------
    # O painel acompanha o gráfico: sempre que X/Y mudam (clique nos
    # canais, renomear, excluir...) 'selecao-eixos-container' é redesenhado
    # — é esse o sinal, sem precisar de Outputs a mais em canais.py.
    # Se o X mudou, o preview (calculado com o X antigo) é esquecido: a
    # figura nova já foi montada sem ele.
    # ------------------------------------------------------------------
    @app.callback(
        Output('area-modo-nova-amostragem-edicao', 'children', allow_duplicate=True),
        Input('selecao-eixos-container', 'children'),
        State('modo-nova-amostragem-store', 'data'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('amostragem-canal-y-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_painel_amostragem(_eixos, ativo, operacao, aba_ativa, canal_y):
        if not ativo:
            raise PreventUpdate
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is not None and arquivo.preview_amostragem is not None \
                and arquivo.preview_amostragem.eixo_x != _eixo_x(estado, arquivo):
            arquivo.limpar_preview_amostragem(invalidar_grafico=False)
        return painel(aba_ativa, operacao, canal_y)
