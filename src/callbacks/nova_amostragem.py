"""
Callbacks da Nova Amostragem (botão 'nova-amostra' da toolbar).

Liga/desliga o modo (barra de operações em cima do gráfico + painel
direito com a árvore de dados e a configuração), escolhe a operação e a
origem, gera o Preview, registra na árvore (OK) e cuida das ações sobre
os nós (Recalcular, Manter, usar como origem, excluir).

Regras de convivência (decisões da Fase 4):
  - Nova Amostragem e Nova Análise nunca ficam ligadas juntas: ligar uma
    desliga a outra;
  - Aparar/Excluir, fechar o gráfico e trocar/fechar aba desligam a Nova
    Amostragem (ela parte do X e dos Y desenhados na aba ativa).
  - O Preview some ao trocar de operação, ao desligar o modo e ao dar OK
    (o resultado passa a estar na árvore); um novo Preview substitui o
    anterior.

O cálculo mora no core (src/core/operations/amostragem.py, Arquivo); a
aparência em src/gui/amostragem.py; o desenho do preview no plotter. Aqui
só a orquestração.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import processar_cliques_padrao
from src.core.operations.amostragem import OPERACOES
from src.core.plotting.plotter import construir_figura_serie_temporal, resolver_eixo_x
from src.gui.amostragem import (
    CAMPOS_PARAMETROS, OPERACOES_BARRA, classe_botao_operacao, contexto_normalizado,
    origem_efetiva, renderizar_config_amostragem, renderizar_painel_amostragem,
    renderizar_resultado_amostragem,
)
from src.gui.feedback import Feedback, saida_feedback

ESCONDIDO = {'display': 'none'}
VISIVEL = {'display': 'flex'}
CLASSE_BOTAO_TOOLBAR = 'toolbar-upload'
FIGURA_GRAFICO = Output('grafico-plotly-real', 'figure', allow_duplicate=True)
PAINEL = Output('area-modo-nova-amostragem-edicao', 'children', allow_duplicate=True)
CONTEXTO = Output('amostragem-contexto-store', 'data', allow_duplicate=True)
OPERACAO = Output('amostragem-operacao-store', 'data', allow_duplicate=True)
CLASSES_BARRA = Output({'type': 'amostragem-op', 'op': ALL}, 'className', allow_duplicate=True)


def _classes_barra(operacao):
    """className de cada botão da barra, na ordem do layout (Output com ALL)."""
    return [classe_botao_operacao(chave, operacao) for chave, _, _ in OPERACOES_BARRA]


# Output com ALL não aceita um 'no_update' só: precisa de um por botão.
BARRA_SEM_MUDANCA = [no_update] * len(OPERACOES_BARRA)


def _eixo_x(estado, arquivo):
    return resolver_eixo_x(estado, arquivo) if arquivo is not None else None


def _parametros_do_painel(estados_params):
    """{nome: valor} a partir do State com ALL dos campos de parâmetro."""
    return {item['id']['nome']: item.get('value') for item in estados_params}


def _faltando(operacao, parametros):
    return [CAMPOS_PARAMETROS[operacao][nome][0] for nome, valor in parametros.items() if valor is None]


def registrar_callbacks_nova_amostragem(app, estado):

    def arquivo_da(aba_ativa):
        return estado.arquivos.get(aba_ativa) if aba_ativa else None

    def painel(aba_ativa, operacao, contexto):
        arquivo = arquivo_da(aba_ativa)
        return renderizar_painel_amostragem(estado, aba_ativa, _eixo_x(estado, arquivo), operacao, contexto)

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
        arquivo = arquivo_da(aba_ativa)
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
    # Liga/desliga. Ligar desliga a Nova Análise (mesmas áreas da tela) e
    # começa sem nada selecionado na árvore (o canal escolhido fica).
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
        Output('amostragem-contexto-store', 'data'),
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
        State('amostragem-contexto-store', 'data'),
        prevent_initial_call=True,
    )
    def alternar_modo_nova_amostragem(n_clicks, ativo, analise_ativa, aba_ativa, contexto):
        if not n_clicks:
            raise PreventUpdate

        if ativo:
            return (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO, no_update,
                    None, _classes_barra(None), no_update, Feedback.info('Nova Amostragem desligada.'),
                    no_update, no_update, no_update, no_update,
                    tirar_preview(aba_ativa))

        contexto = {**contexto_normalizado(None), 'canal_y': contexto_normalizado(contexto)['canal_y']}
        desligar_analise = (False, CLASSE_BOTAO_TOOLBAR, ESCONDIDO, ESCONDIDO) if analise_ativa \
            else (no_update,) * 4
        feedback = Feedback.instrucao(
            'Nova Amostragem: escolha uma operação na barra acima do gráfico.')
        return (True, CLASSE_BOTAO_TOOLBAR + ' ativo', VISIVEL, VISIVEL,
                painel(aba_ativa, None, contexto), None, _classes_barra(None), contexto, feedback,
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
        OPERACAO,
        CLASSES_BARRA,
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
        arquivo = arquivo_da(aba_ativa)
        if arquivo is not None:
            arquivo.limpar_preview_amostragem()
        return DESLIGADO

    # ------------------------------------------------------------------
    # Escolher a operação na barra. Os botões são fixos no layout, mas usam
    # padrão coringa: o filtro anti-fantasma vale do mesmo jeito. Trocar de
    # operação tira o preview da anterior e fecha o cartão do nó (a origem
    # continua a mesma).
    # ------------------------------------------------------------------
    @app.callback(
        OPERACAO, CLASSES_BARRA, PAINEL, CONTEXTO,
        saida_feedback('amostragem-operacao'),
        FIGURA_GRAFICO,
        Input({'type': 'amostragem-op', 'op': ALL}, 'n_clicks'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('amostragem-contexto-store', 'data'),
        prevent_initial_call=True,
    )
    def escolher_operacao_amostragem(_cliques, operacao_atual, aba_ativa, contexto):
        gatilho = processar_cliques_padrao(ctx.inputs_list)
        if gatilho is None:
            raise PreventUpdate
        operacao = gatilho.get('op')
        if operacao not in OPERACOES or operacao == operacao_atual:
            raise PreventUpdate
        contexto = {**contexto_normalizado(contexto), 'selecionado': None, 'recalculando': None}
        figura = tirar_preview(aba_ativa)
        feedback = Feedback.instrucao(
            f'{OPERACOES[operacao].rotulo}: escolha a origem e os parâmetros e clique em Preview.')
        return (operacao, _classes_barra(operacao), painel(aba_ativa, operacao, contexto),
                contexto, feedback, figura)

    # ------------------------------------------------------------------
    # Canal Y escolhido no dropdown: vira a origem e refaz só a
    # configuração — os valores iniciais dos parâmetros (ex: Δx sugerido)
    # dependem dos dados desse canal. O dropdown nasce de novo a cada
    # redesenho com o valor já guardado: valor igual ao do contexto =
    # redesenho, não escolha do usuário.
    # ------------------------------------------------------------------
    @app.callback(
        CONTEXTO,
        Output('amostragem-config-container', 'children'),
        Input('amostragem-canal-y', 'value'),
        State('amostragem-contexto-store', 'data'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def escolher_canal_y_amostragem(canal_y, contexto, operacao, aba_ativa):
        contexto = contexto_normalizado(contexto)
        if not canal_y or canal_y == contexto['canal_y'] or contexto['pai']:
            raise PreventUpdate
        arquivo = arquivo_da(aba_ativa)
        if arquivo is None:
            raise PreventUpdate
        contexto = {**contexto, 'canal_y': canal_y, 'selecionado': None, 'recalculando': None}
        return contexto, renderizar_config_amostragem(arquivo, _eixo_x(estado, arquivo), operacao, contexto)

    # ------------------------------------------------------------------
    # Preview: calcula sobre os dados atuais da origem (canal ou nó) e
    # desenha por cima do gráfico, sem registrar nada. Clicar de novo (com
    # outros parâmetros) substitui. Botão dentro da configuração
    # redesenhada: filtro anti-fantasma.
    # ------------------------------------------------------------------
    @app.callback(
        FIGURA_GRAFICO,
        Output('amostragem-resultado', 'children'),
        saida_feedback('amostragem-preview'),
        Input('amostragem-preview', 'n_clicks'),
        State({'type': 'amostragem-param', 'nome': ALL}, 'value'),
        State('amostragem-operacao-store', 'data'),
        State('amostragem-contexto-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_preview_amostragem(_n, _valores, operacao, contexto, aba_ativa):
        if processar_cliques_padrao(ctx.inputs_list) is None:
            raise PreventUpdate
        arquivo = arquivo_da(aba_ativa)
        if arquivo is None or operacao not in OPERACOES:
            raise PreventUpdate
        canal_y, eixo_origem, pai = origem_efetiva(arquivo, _eixo_x(estado, arquivo), contexto)
        if canal_y is None:
            raise PreventUpdate

        parametros = _parametros_do_painel(ctx.states_list[0])
        faltando = _faltando(operacao, parametros)
        if faltando:
            return no_update, no_update, Feedback.aviso(f"Preencha: {', '.join(faltando)}.")
        try:
            preview = arquivo.gerar_preview_amostragem(operacao, parametros, canal_y, eixo_origem, pai)
        except ValueError as erro:
            # Nada mudou: o preview anterior (se havia) continua no gráfico.
            return no_update, no_update, Feedback.erro(f'Preview não gerado: {erro}')

        nome = OPERACOES[operacao].rotulo + ' ' + arquivo.rotulo_origem(canal_y, pai)
        feedback = Feedback.sucesso(f'Preview de {nome}: {len(preview.serie)} pontos no gráfico.')
        return redesenhar(aba_ativa), renderizar_resultado_amostragem(preview), feedback

    # ------------------------------------------------------------------
    # OK: registra na árvore o que está configurado (mesma conta do
    # Preview, refeita sobre os dados atuais — o resultado é o mesmo que
    # está sendo visto). O preview sai do gráfico e o nó novo fica
    # selecionado. Com o Recalcular parado num nó ('recalculando'), o mesmo
    # botão (rótulo 'Recalcular') recalcula aquele nó com estes parâmetros
    # e segue a cadeia.
    # ------------------------------------------------------------------
    @app.callback(
        PAINEL, CONTEXTO, OPERACAO, CLASSES_BARRA,
        saida_feedback('amostragem-ok'),
        FIGURA_GRAFICO,
        Input('amostragem-ok', 'n_clicks'),
        State({'type': 'amostragem-param', 'nome': ALL}, 'value'),
        State('amostragem-operacao-store', 'data'),
        State('amostragem-contexto-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def registrar_ok_amostragem(_n, _valores, operacao, contexto, aba_ativa):
        if processar_cliques_padrao(ctx.inputs_list) is None:
            raise PreventUpdate
        arquivo = arquivo_da(aba_ativa)
        if arquivo is None or operacao not in OPERACOES:
            raise PreventUpdate
        contexto = contexto_normalizado(contexto)
        parametros = _parametros_do_painel(ctx.states_list[0])
        faltando = _faltando(operacao, parametros)
        if faltando:
            return (no_update, no_update, no_update, BARRA_SEM_MUDANCA,
                    Feedback.aviso(f"Preencha: {', '.join(faltando)}."), no_update)

        if contexto['recalculando'] and contexto['recalculando'] in arquivo.arvore:
            return resultado_recalculo(arquivo, aba_ativa, contexto['recalculando'], parametros)

        canal_y, eixo_origem, pai = origem_efetiva(arquivo, _eixo_x(estado, arquivo), contexto)
        if canal_y is None:
            raise PreventUpdate
        try:
            arquivo.gerar_preview_amostragem(operacao, parametros, canal_y, eixo_origem, pai)
        except ValueError as erro:
            return (no_update, no_update, no_update, BARRA_SEM_MUDANCA,
                    Feedback.erro(f'Não registrado: {erro}'), no_update)
        no = arquivo.registrar_preview_amostragem()
        figura = redesenhar(aba_ativa)
        contexto = {**contexto, 'canal_y': canal_y, 'selecionado': no.id, 'recalculando': None}
        feedback = Feedback.sucesso(f"'{no.nome}' registrado na árvore.")
        return (painel(aba_ativa, operacao, contexto), contexto, no_update, BARRA_SEM_MUDANCA,
                feedback, figura)

    def resultado_recalculo(arquivo, aba_ativa, id_no, parametros=None):
        """
        Roda o Recalcular e devolve (painel, contexto, operação, classes da
        barra, feedback, figura). Parou num nó -> ele fica selecionado, com a
        operação dele na barra e os parâmetros no painel pra ajustar.
        """
        relatorio = arquivo.recalcular_derivado(id_no, parametros)
        feito = len(relatorio.recalculados)
        if relatorio.concluido:
            no = arquivo.arvore.no(id_no)
            operacao = no.operacao
            contexto = {'canal_y': no.canal_raiz, 'pai': no.pai, 'selecionado': id_no,
                        'recalculando': None, 'motivo': None}
            feedback = Feedback.sucesso(f'Recalculado: {feito} análise(s) com os dados atuais.')
        else:
            pendencia = relatorio.pendencias[0]
            if parametros is not None and pendencia.id == id_no and not feito:
                # Os parâmetros novos também não serviram: o painel fica como
                # está (com o que o usuário digitou), só o mago avisa.
                return (no_update, no_update, no_update, BARRA_SEM_MUDANCA,
                        Feedback.aviso(pendencia.mensagem), no_update)
            no = arquivo.arvore.no(pendencia.id)
            operacao = no.operacao
            contexto = {'canal_y': no.canal_raiz, 'pai': no.pai, 'selecionado': no.id,
                        'recalculando': no.id, 'motivo': pendencia.mensagem}
            prefixo = f'{feito} análise(s) recalculada(s); ' if feito else ''
            feedback = Feedback.aviso(f"{prefixo}parou em '{no.nome}'. Veja o motivo no painel.")
        return (painel(aba_ativa, operacao, contexto), contexto, operacao, _classes_barra(operacao),
                feedback, no_update)

    # ------------------------------------------------------------------
    # Árvore e cartão do nó: clicar num canal (vira a origem), num nó (abre
    # o cartão e restaura a operação e os parâmetros) e os botões do
    # cartão (Recalcular, Manter, usar como origem, excluir, voltar ao
    # canal). Tudo nasce dentro do painel redesenhado: filtro anti-fantasma.
    # ------------------------------------------------------------------
    @app.callback(
        PAINEL, CONTEXTO, OPERACAO, CLASSES_BARRA,
        saida_feedback('amostragem-arvore'),
        FIGURA_GRAFICO,
        Input({'type': 'amostragem-raiz', 'canal': ALL}, 'n_clicks'),
        Input({'type': 'amostragem-no', 'id': ALL}, 'n_clicks'),
        Input({'type': 'amostragem-acao', 'acao': ALL, 'no': ALL}, 'n_clicks'),
        State('amostragem-operacao-store', 'data'),
        State('amostragem-contexto-store', 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def acao_arvore_amostragem(_raizes, _nos, _acoes, operacao, contexto, aba_ativa):
        gatilho = processar_cliques_padrao(ctx.inputs_list)
        arquivo = arquivo_da(aba_ativa)
        if gatilho is None or arquivo is None:
            raise PreventUpdate
        contexto = contexto_normalizado(contexto)
        tipo = gatilho.get('type')
        figura = no_update
        operacao_nova = no_update

        if tipo == 'amostragem-raiz':
            contexto = {**contexto, 'canal_y': gatilho['canal'], 'pai': None,
                        'selecionado': None, 'recalculando': None}
            feedback = Feedback.instrucao(f"Origem: canal '{arquivo.rotulo(gatilho['canal'])}'.")

        elif tipo == 'amostragem-no':
            id_no = gatilho['id']
            if id_no not in arquivo.arvore:
                raise PreventUpdate
            no = arquivo.arvore.no(id_no)
            # Restaura: a mesma operação, a mesma origem, os mesmos parâmetros.
            contexto = {'canal_y': no.canal_raiz, 'pai': no.pai, 'selecionado': id_no, 'recalculando': None}
            operacao_nova = no.operacao
            feedback = Feedback.info(f"'{no.nome}': operação e parâmetros restaurados.")

        else:
            acao, id_no = gatilho['acao'], gatilho['no']
            if acao == 'voltar-canal':
                contexto = {**contexto, 'pai': None, 'selecionado': None, 'recalculando': None}
                feedback = Feedback.instrucao(f"Origem: canal '{arquivo.rotulo(contexto['canal_y'])}'.")
            elif id_no not in arquivo.arvore:
                raise PreventUpdate
            elif acao == 'recalcular':
                return resultado_recalculo(arquivo, aba_ativa, id_no)
            elif acao == 'manter':
                arquivo.manter_derivado(id_no)
                contexto = {**contexto, 'recalculando': None}
                feedback = Feedback.info('Resultado mantido como está. O alerta foi removido.')
            elif acao == 'usar-origem':
                no = arquivo.arvore.no(id_no)
                contexto = {'canal_y': no.canal_raiz, 'pai': id_no, 'selecionado': None, 'recalculando': None}
                operacao_nova = None
                feedback = Feedback.instrucao(
                    f"Origem: '{no.nome}'. Escolha a operação na barra acima do gráfico.")
            elif acao == 'excluir':
                nome = arquivo.arvore.no(id_no).nome
                removidos = arquivo.excluir_derivado(id_no)
                if contexto['pai'] in removidos:
                    contexto = {**contexto, 'pai': None}
                if contexto['selecionado'] in removidos or contexto['recalculando'] in removidos:
                    contexto = {**contexto, 'selecionado': None, 'recalculando': None}
                preview = arquivo.preview_amostragem
                if preview is not None and preview.pai in removidos:
                    figura = tirar_preview(aba_ativa)
                extra = f' (e {len(removidos) - 1} análise(s) que saíram dela)' if len(removidos) > 1 else ''
                feedback = Feedback.info(f"'{nome}' excluída{extra}.")
            else:
                raise PreventUpdate

        operacao_painel = operacao if operacao_nova is no_update else operacao_nova
        classes = BARRA_SEM_MUDANCA if operacao_nova is no_update else _classes_barra(operacao_nova)
        if operacao_nova is not no_update and operacao_nova != operacao:
            figura = tirar_preview(aba_ativa)
        return (painel(aba_ativa, operacao_painel, contexto), contexto, operacao_nova, classes,
                feedback, figura)

    # ------------------------------------------------------------------
    # O painel acompanha o gráfico: sempre que X/Y mudam (clique nos
    # canais, renomear, excluir...) 'selecao-eixos-container' é redesenhado
    # — é esse o sinal, sem precisar de Outputs a mais em canais.py.
    # Se o X mudou, o preview (calculado com o X antigo) é esquecido: a
    # figura nova já foi montada sem ele.
    # ------------------------------------------------------------------
    @app.callback(
        PAINEL,
        Input('selecao-eixos-container', 'children'),
        State('modo-nova-amostragem-store', 'data'),
        State('amostragem-operacao-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('amostragem-contexto-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_painel_amostragem(_eixos, ativo, operacao, aba_ativa, contexto):
        if not ativo:
            raise PreventUpdate
        arquivo = arquivo_da(aba_ativa)
        if arquivo is not None and arquivo.preview_amostragem is not None \
                and arquivo.preview_amostragem.eixo_x != _eixo_x(estado, arquivo):
            arquivo.limpar_preview_amostragem(invalidar_grafico=False)
        return painel(aba_ativa, operacao, contexto)
