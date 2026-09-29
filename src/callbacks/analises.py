"""
Callbacks de 'Análises do arquivo:' (menu da esquerda): as análises da
Nova Amostragem que viraram canal pelo botão Add.

Clicar numa análise põe ela no eixo Y (só com o mesmo X de onde veio — o
mago explica quando não dá); clicar nela dentro da caixa Y: tira. Lápis
renomeia (Enter ou o lápis de novo salvam), lixeira tira a análise da
lista (a análise da árvore continua).

As regras moram no core (Arquivo.mover_derivado_para_y etc.); a aparência
em src/gui/analises.py. Aqui só a orquestração.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import processar_cliques_padrao
from src.core.plotting.plotter import construir_figura_serie_temporal
from src.gui.analises import renderizar_analises_da_aba_ativa
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import (
    renderizar_calculadora_botoes, renderizar_grafico_com_fechar, renderizar_selecao_eixos,
)


def registrar_callbacks_analises(app, estado):

    @app.callback(
        Output('lista-analises-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('analise-em-edicao-store', 'data'),
        saida_feedback('analises'),
        Output('area-modo-nova-analise-edicao', 'children', allow_duplicate=True),
        Input({'type': 'linha-analise', 'arquivo': ALL, 'canal': ALL}, 'n_clicks'),
        Input({'type': 'remover-analise-eixo', 'arquivo': ALL, 'canal': ALL}, 'n_clicks'),
        Input({'type': 'botao-editar-analise', 'arquivo': ALL, 'canal': ALL}, 'n_clicks'),
        Input({'type': 'botao-excluir-analise', 'arquivo': ALL, 'canal': ALL}, 'n_clicks'),
        Input({'type': 'input-editar-analise', 'arquivo': ALL, 'canal': ALL}, 'n_submit'),
        State({'type': 'input-editar-analise', 'arquivo': ALL, 'canal': ALL}, 'value'),
        State('analise-em-edicao-store', 'data'),
        State('modo-nova-analise-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_analises_lateral(_cliques, _remover, _lapis, _lixeira, _enter, _nomes, em_edicao,
                                   calculadora_ligada):
        gatilho = processar_cliques_padrao(ctx.inputs_list)
        if gatilho is None:
            raise PreventUpdate
        aba, nome = gatilho.get('arquivo'), gatilho.get('canal')
        arquivo = estado.arquivos.get(aba)
        if arquivo is None or nome not in arquivo.canais_derivados:
            raise PreventUpdate
        canal = arquivo.canal_derivado(nome)
        tipo = gatilho['type']
        tinha_grafico = arquivo.grafico_gerado
        nomes_digitados = {(i['id']['arquivo'], i['id']['canal']): i.get('value') for i in ctx.states_list[0]}

        def salvar_nome():
            novo = (nomes_digitados.get((aba, nome)) or '').strip()
            if not novo:
                return Feedback.aviso('O nome não pode ficar vazio.')
            if novo == canal.rotulo:
                return Feedback.manter()
            antigo = canal.rotulo
            arquivo.renomear_canal_derivado(nome, novo)
            return Feedback.sucesso(f"'{antigo}' agora se chama '{novo}'.")

        if tipo == 'linha-analise':
            try:
                arquivo.mover_derivado_para_y(nome)
            except ValueError as erro:
                return no_update, no_update, no_update, no_update, Feedback.aviso(str(erro)), no_update
            feedback = Feedback.sucesso(f"'{canal.rotulo}' adicionada ao eixo Y.")
        elif tipo == 'remover-analise-eixo':
            arquivo.remover_derivado_do_y(nome)
            feedback = Feedback.info(f"'{canal.rotulo}' voltou pra lista.")
        elif tipo == 'botao-excluir-analise':
            arquivo.excluir_canal_derivado(nome)
            feedback = Feedback.info(f"'{canal.rotulo}' saiu de Análises do arquivo. "
                                     "A análise continua na árvore da Nova Amostragem.")
            em_edicao = None
        elif tipo == 'botao-editar-analise':
            if em_edicao and em_edicao.get('arquivo') == aba and em_edicao.get('canal') == nome:
                feedback = salvar_nome()
                em_edicao = None
            else:
                em_edicao = {'arquivo': aba, 'canal': nome}
                feedback = Feedback.instrucao('Digite o novo nome e aperte Enter.')
        else:   # Enter no campo de nome
            feedback = salvar_nome()
            em_edicao = None

        # Redesenha o gráfico só se ele estava na tela (mesmo cuidado de
        # gerenciar_atribuicao_eixos): pôr/tirar do Y ou renomear algo
        # desenhado muda a figura.
        area_grafico = no_update
        if tinha_grafico and not arquivo.grafico_gerado:
            fig = construir_figura_serie_temporal(estado, aba)
            arquivo.figura = fig
            area_grafico = renderizar_grafico_com_fechar(fig)
        # Com a Nova Análise ligada, o teclado dela lista as análises (x', y'):
        # renomear ou tirar da lista precisa aparecer lá também.
        teclado = renderizar_calculadora_botoes(estado, aba) \
            if calculadora_ligada and tipo in ('botao-excluir-analise', 'botao-editar-analise',
                                               'input-editar-analise') else no_update
        return (renderizar_analises_da_aba_ativa(estado, aba, em_edicao),
                renderizar_selecao_eixos(estado, aba, analise_em_edicao=em_edicao), area_grafico, em_edicao,
                feedback, teclado)

    # ------------------------------------------------------------------
    # O ⚠ de uma análise muda quando os dados de origem mudam (corte,
    # calculadora) — e esses callbacks redesenham o gráfico. Em vez de
    # Outputs a mais em cada um deles, a lista acompanha o gráfico.
    # ------------------------------------------------------------------
    @app.callback(
        Output('lista-analises-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        Input('container-grafico', 'children'),
        State('aba-ativa-store', 'data'),
        State('analise-em-edicao-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_lista_analises(_grafico, aba_ativa, em_edicao):
        arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
        if arquivo is None or not arquivo.canais_derivados:
            raise PreventUpdate
        # A caixa Y: só é redesenhada se tem análise nela (o ⚠ dela); as
        # colunas comuns continuam por conta dos callbacks delas.
        caixa_y = renderizar_selecao_eixos(estado, aba_ativa, analise_em_edicao=em_edicao) \
            if arquivo.eixos_y_derivados else no_update
        return renderizar_analises_da_aba_ativa(estado, aba_ativa, em_edicao), caixa_y
