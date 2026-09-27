"""
Callbacks da Nova Amostragem (botão 'nova-amostra' da toolbar).

Liga/desliga o modo (barra de operações em cima do gráfico + painel
direito com a árvore de dados e a configuração), escolhe a operação e
mantém o painel em dia com o que está no gráfico.

Regras de convivência (decisões da Fase 4):
  - Nova Amostragem e Nova Análise nunca ficam ligadas juntas: ligar uma
    desliga a outra;
  - Aparar/Excluir, fechar o gráfico e trocar/fechar aba desligam a Nova
    Amostragem (ela parte do X e dos Y desenhados na aba ativa).

O cálculo mora no core (src/core/operations/amostragem.py, Arquivo); a
aparência em src/gui/amostragem.py. Aqui só a orquestração.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import processar_cliques_padrao
from src.core.operations.amostragem import OPERACOES
from src.core.plotting.plotter import resolver_eixo_x
from src.gui.amostragem import (
    OPERACOES_BARRA, classe_botao_operacao, renderizar_config_amostragem,
    renderizar_painel_amostragem,
)
from src.gui.feedback import Feedback, saida_feedback

ESCONDIDO = {'display': 'none'}
VISIVEL = {'display': 'flex'}
CLASSE_BOTAO_TOOLBAR = 'toolbar-upload'


def _classes_barra(operacao):
    """className de cada botão da barra, na ordem do layout (Output com ALL)."""
    return [classe_botao_operacao(chave, operacao) for chave, _, _ in OPERACOES_BARRA]


def _eixo_x(estado, arquivo):
    return resolver_eixo_x(estado, arquivo) if arquivo is not None else None


def registrar_callbacks_nova_amostragem(app, estado):

    def painel(aba_ativa, operacao, canal_y):
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        return renderizar_painel_amostragem(estado, aba_ativa, _eixo_x(estado, arquivo), operacao, canal_y)

    # ------------------------------------------------------------------
    # Liga/desliga. Ligar desliga a Nova Análise (mesmas áreas da tela).
    # Desligar esquece a operação escolhida: ao religar, começa do zero.
    # 'nova-amostra' é id fixo, nunca redesenhado: basta 'not n_clicks'.
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
                    no_update, no_update, no_update, no_update)

        desligar_analise = (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO) if analise_ativa \
            else (no_update,) * 4
        feedback = Feedback.instrucao(
            'Nova Amostragem: escolha uma operação na barra acima do gráfico.')
        return (True, CLASSE_BOTAO_TOOLBAR + ' ativo', VISIVEL, VISIVEL,
                painel(aba_ativa, None, canal_y), None, _classes_barra(None), feedback,
                *desligar_analise)

    # ------------------------------------------------------------------
    # Desliga quando outro modo/ação toma a tela. Callback à parte (em vez
    # de Outputs a mais nos callbacks da Nova Análise, do corte, do gráfico
    # e das abas) pelo mesmo motivo de 'desligar_calculadora_ao_iniciar_
    # corte': cada módulo cuida do próprio estado.
    # Troca de aba ('aba-ativa-store') vale sempre; os botões, só clique
    # de verdade (valor > 0).
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

    @app.callback(
        *SAIDAS_DESLIGAR,
        saida_feedback('amostragem-desligar'),
        Input('nova-analise', 'n_clicks'),
        Input('aparar-dados', 'n_clicks'),
        Input('excluir-dados', 'n_clicks'),
        Input('aba-ativa-store', 'data'),
        State('modo-nova-amostragem-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_nova_amostragem(_analise, _aparar, _excluir, _aba, ativo):
        if not ativo:
            raise PreventUpdate
        if ctx.triggered_id != 'aba-ativa-store' and processar_cliques_padrao(ctx.inputs_list[:3]) is None:
            raise PreventUpdate
        # Corte e troca de aba já dizem o que está acontecendo; a Nova
        # Análise não fala nada ao ligar, então a mensagem vem daqui (senão
        # ficaria a última instrução da Amostragem).
        feedback = Feedback.info('Nova Análise ligada. A Nova Amostragem foi desligada.') \
            if ctx.triggered_id == 'nova-analise' else no_update
        return (*DESLIGADO, feedback)

    # 'fechar-grafico' só existe enquanto há gráfico (nasce dentro dele, a
    # cada redesenho): num callback só dele, pra a ausência do botão não
    # atrapalhar os gatilhos acima.
    @app.callback(
        *SAIDAS_DESLIGAR,
        Input('fechar-grafico', 'n_clicks'),
        State('modo-nova-amostragem-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_nova_amostragem_ao_fechar_grafico(n_clicks, ativo):
        if not ativo or not n_clicks:
            raise PreventUpdate
        return DESLIGADO

    # ------------------------------------------------------------------
    # Escolher a operação na barra. Os botões são fixos no layout, mas usam
    # padrão coringa: o filtro anti-fantasma vale do mesmo jeito.
    # ------------------------------------------------------------------
    @app.callback(
        Output('amostragem-operacao-store', 'data', allow_duplicate=True),
        Output({'type': 'amostragem-op', 'op': ALL}, 'className', allow_duplicate=True),
        Output('area-modo-nova-amostragem-edicao', 'children', allow_duplicate=True),
        saida_feedback('amostragem-operacao'),
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
        feedback = Feedback.instrucao(
            f'{OPERACOES[operacao].rotulo}: escolha o canal e os parâmetros no painel à direita.')
        return operacao, _classes_barra(operacao), painel(aba_ativa, operacao, canal_y), feedback

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
    # O painel acompanha o gráfico: sempre que X/Y mudam (clique nos
    # canais, renomear, excluir...) 'selecao-eixos-container' é redesenhado
    # — é esse o sinal, sem precisar de Outputs a mais em canais.py.
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
        return painel(aba_ativa, operacao, canal_y)
