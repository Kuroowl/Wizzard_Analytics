"""
Callbacks do gráfico principal: gerar ('Plotar Seleção') e fechar a
visualização.

Observação: 'fechar_grafico' também cancela uma seleção de corte em
andamento, então escreve em Outputs que pertencem ao corte
('corte-selecao-store', sidebar, toolbar, prompt de confirmação).
Dependência cruzada mantida como estava na Fase 2 (só mover).
"""
from dash import Input, Output, State, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import classe_painel_direito, estados_toolbar
from src.core.plotting.plotter import construir_figura_serie_temporal, resolver_eixo_x
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import (
    renderizar_area_grafico, renderizar_colunas_da_aba_ativa, renderizar_grafico_com_fechar,
    renderizar_painel_direito_padrao, renderizar_selecao_eixos,
)
from src.gui.rodape import obter_estado_rodape


def registrar_callbacks_grafico(app, estado):

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        saida_feedback('grafico-gerar'),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('iniciar-edicao', 'disabled', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Input('central-btn-1', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_grafico_serie_temporal(n_clicks, aba_ativa):
        """
        Botão 'Plotar Seleção' (era 'Gerar Série Temporal' — só o
        RÓTULO/comportamento mudou; o nome da função Python ficou o
        mesmo por simplicidade, não afeta o usuário).

        ANTES: gerava o gráfico e só DEPOIS decidia o eixo X sozinho
        (resolver_eixo_x, sempre tentando 'Tempo_decorrido_s' primeiro),
        escondendo esse canal da lista — o usuário nunca escolhia o X
        de propósito, só marcava quais Y queria via checkbox ☐/✓.

        AGORA: X e Y já foram escolhidos ANTES de chegar aqui, clicando
        nos nomes das colunas na barra lateral (ver
        gerenciar_atribuicao_eixos, Arquivo.mover_para_eixo_x/
        mover_para_eixo_y) — este botão só desenha com o que já está
        montado. Se o usuário ainda não clicou em NADA (nenhum X
        escolhido), resolvemos um X razoável automaticamente (mesmo
        fallback de sempre — ver resolver_eixo_x, plotter.py) e
        REGISTRAMOS essa escolha como se ele tivesse clicado (pra
        'selecao-eixos-container' refletir o que está de fato
        desenhado, e cliques seguintes na lista já caírem direto em
        Y, sem precisar escolher X de novo).
        """
        if not n_clicks or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]

        if not arquivo.eixo_x_manual:
            eixo_x_resolvido = resolver_eixo_x(estado, arquivo)
            arquivo.mover_para_eixo_x(eixo_x_resolvido)

        # Gera o gráfico com o X e os Y já atribuídos até agora (Y pode
        # ser nenhum ainda — nesse caso nasce só com o eixo X definido,
        # sem curva nenhuma, e o usuário vai populando ao clicar mais
        # colunas na barra lateral, que agora caem direto em Y). Se o
        # arquivo tiver mais de 5000 linhas, essa chamada também empurra
        # um aviso de amostragem pra lista de avisos da aba (ver
        # plotter.py).
        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig

        tem_y = bool(arquivo.eixos_y_manual)
        if tem_y:
            feedback = Feedback.sucesso('Gráfico gerado.')
        else:
            feedback = Feedback.instrucao(
                f"Gráfico gerado com X = '{arquivo.rotulo(arquivo.eixo_x_manual)}'. "
                'Clique nos canais na barra lateral pra adicionar ao eixo Y.')
        grafico = renderizar_grafico_com_fechar(fig)

        rodape = obter_estado_rodape(estado, aba_ativa)
        return (grafico, renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                renderizar_selecao_eixos(estado, aba_ativa), feedback,
                False, False, False, False, False, False,
                rodape.badge_texto, rodape.badge_classe, rodape.popup)

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        saida_feedback('grafico-fechar'),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('iniciar-edicao', 'disabled', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('sidebar-principal', 'className', allow_duplicate=True),
        Output('toolbar-icones', 'className', allow_duplicate=True),
        Output('toolbar-confirmacao-corte', 'style', allow_duplicate=True),
        Input('fechar-grafico', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('corte-selecao-store', 'data'),
        prevent_initial_call=True,
    )
    def fechar_grafico(n_clicks, aba_ativa, dados_selecao):
        """
        Fecha só a VISUALIZAÇÃO do gráfico, voltando pra grade de opções —
        não fecha arquivo nenhum (isso é o botão 'X' da aba, que já reseta
        tudo sozinho quando não sobra arquivo carregado).

        Se uma seleção de corte ('Aparar dados'/'Excluir dados') estiver
        EM ANDAMENTO (esperando o 2º clique no gráfico) na hora de fechar
        — 'dados_selecao' não-vazio — cancela ela TAMBÉM: sem isso, o
        gráfico sumia mas 'corte-selecao-store' continuava "armado"
        esperando um clique que nunca mais vai vir (o gráfico que
        precisava ser clicado não existe mais), e a sidebar/toolbar
        ficavam travadas no visual borrado/inativo pra sempre, sem
        nenhum jeito de destravar (o botão 'Cancelar' do prompt também
        estava escondido, já que o gráfico sumiu junto com ele).
        """
        if not n_clicks or not aba_ativa:
            raise PreventUpdate

        lista_canais = no_update
        selecao_eixos = no_update
        if aba_ativa in estado.arquivos:
            estado.arquivos[aba_ativa].invalidar_grafico()
            # ANTES: o canal do eixo X só ficava oculto ENQUANTO o
            # gráfico estava aberto, e fechar devolvia ele pra lista
            # (exibir_canal_eixo). Desde o rework do 'Plotar Seleção',
            # a atribuição de X/Y é uma escolha PERSISTENTE do usuário
            # (Arquivo.eixo_x_manual/eixos_y_manual) — fechar só a
            # VISUALIZAÇÃO não desfaz essa escolha; ela continua valendo
            # pra próxima vez que ele clicar em 'Plotar Seleção' de novo
            # (não mexemos em 'lista_canais' aqui). A SEÇÃO 'Variáveis
            # do gráfico:' em si, porém, PRECISA sumir junto (pedido
            # explícito: só aparece "quando clicamos em Plotar
            # Seleção") — 'renderizar_selecao_eixos' já esconde
            # sozinha quando 'arquivo.grafico_gerado' é False (que
            # 'invalidar_grafico()' logo acima acabou de tornar
            # verdade), então só precisa chamar de novo aqui.
            selecao_eixos = renderizar_selecao_eixos(estado, aba_ativa)

        area_grafico = renderizar_area_grafico(estado)
        feedback = Feedback.instrucao('Gráfico fechado. Escolha outra opção.')

        # Cancela uma seleção de corte em andamento, se houver — ver
        # docstring acima. 'no_update' quando não havia seleção nenhuma,
        # pra não sobrescrever a sidebar/toolbar à toa.
        if dados_selecao:
            corte_store = None
            classe_sidebar = 'sidebar'
            classe_toolbar_icones = 'toolbar-icones'
            estilo_prompt_corte = {'display': 'none'}
        else:
            corte_store = no_update
            classe_sidebar = no_update
            classe_toolbar_icones = no_update
            estilo_prompt_corte = no_update

        # O arquivo continua carregado (só o gráfico foi fechado), então
        # 'nova-amostra' e 'exportar-dados' NÃO devem voltar a ficar
        # desabilitados aqui — só 'aparar-dados'/'excluir-dados'/
        # 'exportar-grafico'/'iniciar-edicao' (que dependem do gráfico da
        # aba ativa, agora invalidado) e o painel de edição (que volta ao
        # estado normal, já que não faz sentido continuar "em edição" de
        # um gráfico que não existe mais).
        sem_arquivo, _, sem_grafico_da_aba = estados_toolbar(estado, aba_ativa)
        return (area_grafico, lista_canais, selecao_eixos, feedback,
                sem_grafico_da_aba, sem_grafico_da_aba, sem_arquivo, sem_grafico_da_aba, sem_arquivo,
                sem_grafico_da_aba, classe_painel_direito(ativo=False),
                renderizar_painel_direito_padrao(disabled=sem_grafico_da_aba),
                corte_store, classe_sidebar, classe_toolbar_icones, estilo_prompt_corte)
