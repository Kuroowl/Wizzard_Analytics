"""
Callbacks da lista de canais (sidebar): atribuir colunas aos eixos X/Y,
devolver à lista, excluir (soft-delete) e renomear pelo lápis.
"""
import json

from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import processar_cliques_padrao
from src.core.plotting.plotter import construir_figura_serie_temporal
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import (
    renderizar_colunas_da_aba_ativa, renderizar_grafico_com_fechar,
    renderizar_painel_edicao, renderizar_selecao_eixos,
)
from src.gui.rodape import obter_estado_rodape


def registrar_callbacks_canais(app, estado):

    # ------------------------------------------------------------------
    # Lista de canais (sidebar) — 2 callbacks:
    #   1) gerenciar_atribuicao_eixos (era 'gerenciar_selecao_canais',
    #      renomeada porque o comportamento mudou por completo — ver
    #      docstring completa dela abaixo): clique no NOME da coluna
    #      (id 'linha-canal') atribui a X ou Y; clique num "chip" dentro
    #      da caixa X:/Y: (id 'remover-eixo-selecionado') devolve a
    #      coluna pra lista; clique na lixeira ('botao-excluir-canal')
    #      exclui (soft-delete, some da lista, o dado continua em
    #      df_editado). Os três padrão coringa — mesmo cuidado de
    #      sempre com processar_cliques_padrao.
    #   2) gerenciar_edicao_canal: lápis (✏️) pra renomear — ver
    #      docstring completa dela abaixo pro fluxo de toggle/Enter.
    # ------------------------------------------------------------------

    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        saida_feedback('eixos'),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'botao-excluir-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'remover-eixo-selecionado', 'arquivo': ALL, 'coluna': ALL, 'eixo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('painel-direito', 'className'),
        State('edicao-curva-dado-atual', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_atribuicao_eixos(n_clicks_linha, _n_clicks_excluir, _n_clicks_remover, aba_ativa,
                                    classe_painel_direito, coluna_em_edicao):
        """
        Rework do botão 'Plotar Seleção' (era 'Gerar Série Temporal')
        — substitui o antigo checkbox ☐/✓ (que só marcava/desmarcava
        uma coluna pro gráfico, com o eixo X sempre fixo e adivinhado
        sozinho em 'Tempo_decorrido_s'). Agora o clique é no NOME da
        coluna, e o que ele faz depende de já existir ou não um eixo X
        atribuído para este arquivo:

          - Sem X ainda -> este clique vira o X (Arquivo.
            mover_para_eixo_x).
          - Já tem X -> este clique se ACRESCENTA ao fim de Y (Arquivo.
            mover_para_eixo_y) — múltiplas colunas podem entrar em Y,
            na ordem em que forem clicadas.

        A coluna atribuída SOME da lista 'Dados do arquivo:' (fica
        OCULTA) e passa a aparecer como um "chip" na caixa X:/Y' (ver
        renderizar_selecao_eixos, renderizadores.py) — clicar nesse
        chip (id 'remover-eixo-selecionado') devolve ela pra lista
        (Arquivo.remover_da_selecao_eixos).

        Excluir um canal (lixeira) continua igual — soft-delete, some
        de vez — só que agora também limpa a atribuição X/Y se o
        canal excluído estivesse atribuído (ver Arquivo.excluir_canal,
        src/core/arquivo.py).
        """
        if not aba_ativa:
            raise PreventUpdate

        gatilho_id = processar_cliques_padrao(ctx.inputs_list)
        if gatilho_id is None:
            raise PreventUpdate

        # Sem mensagem própria, ainda cancela a troca agendada de uma
        # temporária anterior (mesmo comportamento de antes).
        feedback = Feedback.manter()
        area_grafico = no_update
        # Se o painel de edição estiver aberto ('ativa'), mudar a
        # atribuição de eixos ou excluir um canal pode fazer a curva
        # que ele está mostrando na caixa 'Dado' sumir do gráfico. Sem
        # isto, o 'Dado' ficava com um valor "fantasma" que não
        # corresponde a nada mais desenhado.
        em_edicao = classe_painel_direito and 'ativa' in classe_painel_direito.split()
        painel_edicao = no_update

        coluna = gatilho_id.get('coluna')
        arquivo = estado.arquivos.get(aba_ativa)
        if not arquivo:
            raise PreventUpdate

        # Capturado ANTES de qualquer mutação — BUG corrigido aqui:
        # 'Arquivo.excluir_canal'/'mover_para_eixo_x'/'mover_para_eixo_y'/
        # 'remover_da_selecao_eixos' (src/core/arquivo.py) já chamam
        # 'invalidar_grafico()' sozinhos (zeram 'arquivo.figura'), então
        # checar 'arquivo.grafico_gerado' DEPOIS de chamar qualquer um
        # deles sempre dava False — o gráfico nunca era redesenhado
        # depois da primeira vez (só a primeira geração, via 'Plotar
        # Seleção', funcionava, porque lá a figura ainda nem existia
        # mesmo). Guardando o valor de ANTES, sabemos de verdade se
        # havia um gráfico pra atualizar.
        tipo = gatilho_id.get('type')
        tinha_grafico = arquivo.grafico_gerado

        if tipo == 'botao-excluir-canal':
            rotulo = arquivo.rotulo(coluna)
            # excluir_canal() já invalida o cache da figura E limpa a
            # atribuição X/Y se o canal excluído estivesse atribuído
            # (ver Arquivo.excluir_canal, src/core/arquivo.py) —
            # soft-delete: some da lista, o dado continua no df_editado.
            arquivo.excluir_canal(coluna)
            feedback = Feedback.sucesso(f"Canal '{rotulo}' excluído.")

            if tinha_grafico:
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)

        elif tipo == 'linha-canal':
            rotulo = arquivo.rotulo(coluna)
            if arquivo.eixo_x_manual is None:
                arquivo.mover_para_eixo_x(coluna)
                feedback = Feedback.sucesso(f"'{rotulo}' definido como eixo X.")
            else:
                arquivo.mover_para_eixo_y(coluna)
                feedback = Feedback.sucesso(f"'{rotulo}' adicionado ao eixo Y.")

            # Só redesenha o gráfico se JÁ havia um gráfico aberto antes
            # deste clique (senão ainda estamos na grade de opções, e
            # atribuir um eixo não deve pular direto pra visualização).
            if tinha_grafico:
                # Pode empurrar o aviso de amostragem (>5000 linhas) pra
                # lista de avisos da aba — por isso recalculamos o badge
                #/popup do rodapé logo abaixo, depois desta chamada.
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)

        elif tipo == 'remover-eixo-selecionado':
            rotulo = arquivo.rotulo(coluna)
            arquivo.remover_da_selecao_eixos(coluna)
            feedback = Feedback.info(f"'{rotulo}' voltou pra lista.")

            # Mesmo se o X removido zerar 'eixo_x_manual', ainda
            # redesenha (se já havia gráfico) — 'construir_figura_
            # serie_temporal' (plotter.py) já sabe devolver uma figura
            # VAZIA quando não há X atribuído (pedido explícito: "remover
            # o X deveria gerar um gráfico vazio, à espera de um X").
            if tinha_grafico:
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)

        if em_edicao and aba_ativa in estado.arquivos:
            painel_edicao = renderizar_painel_edicao(estado, aba_ativa, coluna_em_edicao)

        rodape = obter_estado_rodape(estado, aba_ativa)
        return (renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                renderizar_selecao_eixos(estado, aba_ativa),
                feedback, area_grafico,
                rodape.badge_texto, rodape.badge_classe, rodape.popup,
                painel_edicao)

    # ------------------------------------------------------------------
    # Renomear canal (lápis ✏️ na lista de canais) — UM callback só,
    # 'gerenciar_edicao_canal', cobre os 3 jeitos de entrar/sair do modo
    # de edição:
    #   1) clicar no lápis de uma linha PARADA -> abre a edição nela
    #      (salvando antes qualquer edição pendente de OUTRA linha, se
    #      houver — só uma linha em edição por vez).
    #   2) clicar no lápis da MESMA linha que já está em edição -> fecha
    #      e salva (é o "toggle": pressionado = aberto).
    #   3) apertar Enter dentro do campo -> confirma e fecha.
    #
    # Não reage a 'n_blur' de propósito: o Dash dispara 'n_blur' (e
    # qualquer prop observada por um Input de padrão coringa) como
    # "mudança" assim que o PRÓPRIO <input> nasce pela primeira vez
    # (mesmo mecanismo de "disparo fantasma" de n_clicks em componentes
    # recém-criados) — então bastava clicar no lápis pra abrir a edição
    # que ela imediatamente "fechava sozinha" de novo, como se um
    # clique-fora tivesse acontecido na hora. Tirando 'n_blur' da
    # equação (só lápis de novo ou Enter fecham), esse vetor de disparo
    # fantasma nem existe mais pra esse fluxo.
    #
    # O rótulo gravado por Arquivo.renomear_canal (src/core/arquivo.py)
    # é o mesmo lido em TODO lugar que hoje já chama 'arquivo.rotulo(
    # coluna)' — a legenda do gráfico e a caixa 'Dado' do painel de
    # edição da curva — então renomear aqui já é a fonte única de
    # verdade pros dois lugares.
    # ------------------------------------------------------------------

    def _valor_por_id(grupo_lista, alvo_id):
        """
        Acha, dentro de UM grupo de 'ctx.states_list' (a lista de
        {'id','property','value'} correspondente a UM State de padrão
        coringa), o valor do componente cujo id bate com 'alvo_id'.
        Devolve None se não achar (linha já não existe mais na tela).
        """
        chave_alvo = json.dumps(alvo_id, sort_keys=True)
        for item in (grupo_lista or []):
            if json.dumps(item.get('id'), sort_keys=True) == chave_alvo:
                return item.get('value')
        return None

    @app.callback(
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        Output('canal-em-edicao-store', 'data', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        saida_feedback('edicao-canal'),
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Input({'type': 'botao-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'input-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_submit'),
        State({'type': 'input-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'value'),
        State('aba-ativa-store', 'data'),
        State('canal-em-edicao-store', 'data'),
        State('painel-direito', 'className'),
        State('edicao-curva-dado-atual', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_edicao_canal(_n_clicks_lapis, _n_submit_input, _valores_input_bruto, aba_ativa,
                                canal_em_edicao, classe_painel_direito, coluna_em_edicao_painel):
        if not aba_ativa:
            raise PreventUpdate

        gatilho_id = processar_cliques_padrao(ctx.inputs_list)
        if gatilho_id is None:
            raise PreventUpdate

        # 'ctx.states_list[0]' — não o parâmetro '_valores_input_bruto'
        # (que o Dash entrega como lista de VALORES soltos, sem id
        # nenhum junto, pra um State de padrão coringa) — é onde mora o
        # par {'id', 'value'} de cada campo de renomear atualmente na
        # tela; é isso que '_valor_por_id' precisa pra achar o valor do
        # campo certo por arquivo+coluna.
        grupo_valores_input = ctx.states_list[0] if ctx.states_list else []

        tipo = gatilho_id.get('type')
        feedback = no_update
        area_grafico = no_update
        novo_canal_em_edicao = canal_em_edicao

        def _salvar_se_mudou(arquivo_alvo, coluna, novo_nome):
            """Renomeia só se houver arquivo, texto não-vazio, e o nome
            for DIFERENTE do rótulo atual — silenciosamente ignora
            texto vazio/só espaço ou digitar o mesmo nome de novo (sem
            popup de erro pra um caso tão menor)."""
            nonlocal feedback, area_grafico
            arquivo = estado.arquivos.get(arquivo_alvo)
            if not arquivo or not novo_nome:
                return
            novo_nome = novo_nome.strip()
            if not novo_nome or novo_nome == arquivo.rotulo(coluna):
                return
            arquivo.renomear_canal(coluna, novo_nome)
            feedback = Feedback.sucesso(f"Canal renomeado para '{arquivo.rotulo(coluna)}'.")
            if arquivo.grafico_gerado:
                # A legenda do gráfico lê 'arquivo.rotulo(coluna)' na
                # hora de montar cada traço (ver 'name=rotulo' em
                # construir_figura_serie_temporal, plotter.py) — como o
                # rótulo já foi atualizado acima, só precisa redesenhar
                # pra essa legenda nova aparecer.
                fig = construir_figura_serie_temporal(estado, arquivo_alvo)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)

        if tipo == 'input-editar-canal':
            # Enter dentro do campo -> confirma e fecha. 'canal_em_edicao'
            # (State) já diz qual linha é essa (só existe um <input>
            # desse tipo na tela por vez).
            if not canal_em_edicao:
                raise PreventUpdate
            arquivo_alvo, coluna = canal_em_edicao.get('arquivo'), canal_em_edicao.get('coluna')
            valor = _valor_por_id(grupo_valores_input, gatilho_id)
            _salvar_se_mudou(arquivo_alvo, coluna, valor)
            novo_canal_em_edicao = None

        elif tipo == 'botao-editar-canal':
            arquivo_alvo, coluna = gatilho_id.get('arquivo'), gatilho_id.get('coluna')
            mesma_linha = (
                canal_em_edicao
                and canal_em_edicao.get('arquivo') == arquivo_alvo
                and canal_em_edicao.get('coluna') == coluna
            )
            if mesma_linha:
                # Lápis clicado de novo NA MESMA linha que já está
                # aberta -> fecha e salva (o "toggle": pressionado =
                # aberto). O valor atual do campo está em
                # 'grupo_valores_input', pelo MESMO id do lápis
                # (arquivo/coluna iguais, só o 'type' difere).
                valor = _valor_por_id(
                    grupo_valores_input, {'type': 'input-editar-canal', 'arquivo': arquivo_alvo, 'coluna': coluna})
                _salvar_se_mudou(arquivo_alvo, coluna, valor)
                novo_canal_em_edicao = None
            else:
                # Abrindo uma linha nova (ou trocando de linha) — se
                # havia OUTRA em edição, salva o que estava digitado
                # nela antes de trocar (mesmo espírito de "clicar fora
                # salva", só que agora é uma ação EXPLÍCITA do usuário —
                # clicar em outro lápis — não um blur fantasma).
                if canal_em_edicao:
                    valor_anterior = _valor_por_id(grupo_valores_input, {
                        'type': 'input-editar-canal',
                        'arquivo': canal_em_edicao.get('arquivo'),
                        'coluna': canal_em_edicao.get('coluna'),
                    })
                    _salvar_se_mudou(canal_em_edicao.get('arquivo'), canal_em_edicao.get('coluna'), valor_anterior)
                novo_canal_em_edicao = {'arquivo': arquivo_alvo, 'coluna': coluna}

        painel_edicao = no_update
        em_edicao_painel = classe_painel_direito and 'ativa' in classe_painel_direito.split()
        if em_edicao_painel and aba_ativa in estado.arquivos:
            # Mesmo raciocínio do gráfico: a caixa 'Dado' do card
            # 'Curva' lê 'arquivo.rotulo(coluna)' pra montar as opções
            # (ver opcoes_dado em renderizar_painel_edicao) — recarrega
            # o card pra essa lista de opções refletir o novo nome.
            painel_edicao = renderizar_painel_edicao(estado, aba_ativa, coluna_em_edicao_painel)

        return (renderizar_colunas_da_aba_ativa(estado, aba_ativa, novo_canal_em_edicao),
                renderizar_selecao_eixos(estado, aba_ativa, novo_canal_em_edicao),
                novo_canal_em_edicao, area_grafico, feedback, painel_edicao)
