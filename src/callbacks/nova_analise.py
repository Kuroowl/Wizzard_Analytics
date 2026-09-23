"""
Callbacks da Nova Análise: liga/desliga o modo (barra de cálculo no centro
+ teclado da calculadora no lugar do painel de edição) e a calculadora em
si (tokens, apagar, limpar, tipo de destino, criar canal calculado).

Também mora aqui 'desligar_calculadora_ao_iniciar_corte': é disparado pelos
botões de corte, mas só escreve no estado da Nova Análise.

A avaliação da expressão fica no core
(src/core/operations/calculadora.py); aqui só a orquestração.
"""
from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import _processar_cliques_padrao
from src.core.operations.calculadora import avaliar_expressao_calculadora, calc_criar_desabilitado
from src.core.plotting.plotter import construir_figura_serie_temporal
from src.core.rotulos import sanitizar_rotulo_para_nome_coluna
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import (
    renderizar_area_calculadora_completa, renderizar_calculadora_botoes,
    renderizar_colunas_da_aba_ativa, renderizar_grafico_com_fechar, renderizar_selecao_eixos,
)


def registrar_callbacks_nova_analise(app, estado):

    # ------------------------------------------------------------------
    # Modo "Nova Análise" — 'nova-analise' (toolbar) é um liga/desliga:
    # pressionado, faz DUAS coisas aparecerem ao mesmo tempo:
    #   1) uma BARRA fina no topo da área central, EMPURRANDO o gráfico
    #      pra baixo (não cobrindo mais ele — mudança de proposta,
    #      antes uma camada opaca escondia o gráfico inteiro; agora ele
    #      continua visível/interativo o tempo todo) — ver '.centro.
    #      calc-ativa' em central_menu.css.
    #   2) uma camada cobrindo o painel de edição inteiro, com os
    #      GRUPOS de botões da calculadora (Operações básicas/Colunas/
    #      Funções/Operações rápidas) — ver '.area-modo-nova-analise-
    #      edicao' em edit_menu.css.
    #
    # Por que nunca tocar em 'painel-direito-conteudo'/'container-
    # grafico': o gráfico (arquivo.figura, já cacheado — ver
    # Arquivo.grafico_gerado em src/core/arquivo.py) e o estado do
    # painel de edição (a classe 'ativa' de 'painel-direito' + o
    # conteúdo carregado) já são "propriedade dos objetos" existentes —
    # ninguém aqui precisa ser destruído/reconstruído, então desligar o
    # modo não precisa "restaurar" nada explicitamente.
    #
    # 'nova-analise' é um id ESTÁTICO (não um padrão coringa
    # {'type':...}), nunca recriado por nenhum outro callback — não
    # sofre o "disparo fantasma" de remontagem (ver
    # _processar_cliques_padrao, src/callbacks/_comum.py), então o guard
    # simples de 'not n_clicks' já basta aqui.
    # ------------------------------------------------------------------

    @app.callback(
        Output('modo-nova-analise-store', 'data'),
        Output('nova-analise', 'className'),
        Output('area-grafico-normal', 'style'),
        Output('area-modo-nova-analise', 'style'),
        Output('area-modo-nova-analise-edicao', 'style'),
        Output('area-modo-nova-analise', 'children'),
        Output('area-modo-nova-analise-edicao', 'children'),
        Input('nova-analise', 'n_clicks'),
        State('modo-nova-analise-store', 'data'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        prevent_initial_call=True,
    )
    def alternar_modo_nova_analise(n_clicks, modo_ativo_atual, aba_ativa, tokens_atuais):
        if not n_clicks:
            raise PreventUpdate

        novo_ativo = not modo_ativo_atual
        classe_botao = 'toolbar-upload' + (' ativo' if novo_ativo else '')
        # O gráfico real ('#area-grafico-normal') fica SEMPRE visível: a
        # barra ('#area-modo-nova-analise') aparece em cima dele e o
        # empurra pra baixo (ver layout.py/central_menu.css). O Output
        # continua existindo só pra não mexer no contrato agora — fica
        # pra limpeza da Fase 3.
        estilo_area_grafico = {'display': 'block'}
        estilo_area_calc = {'display': 'flex'} if novo_ativo else {'display': 'none'}
        estilo_area_edicao = {'display': 'flex'} if novo_ativo else {'display': 'none'}

        # A calculadora só precisa existir de verdade (com os botões/
        # miniatura do arquivo CERTO) quando o modo está LIGANDO — ao
        # desligar, 'no_update' preserva o que já estava montado (o
        # 'style' acima já cuida de esconder) e a expressão em
        # andamento ('calc-expressao-store') fica intocada, pra
        # continuar de onde parou se o usuário ligar de novo.
        conteudo_barra = no_update
        conteudo_botoes = no_update
        if novo_ativo:
            conteudo_barra = renderizar_area_calculadora_completa(estado, aba_ativa, tokens_atuais)
            conteudo_botoes = renderizar_calculadora_botoes(estado, aba_ativa)

        return (novo_ativo, classe_botao, estilo_area_grafico, estilo_area_calc, estilo_area_edicao,
                conteudo_barra, conteudo_botoes)

    # ------------------------------------------------------------------
    # Calculadora — 4 callbacks (era 5 — 'aplicar_operacao_rapida_
    # calculadora' foi removida: Derivada/Integral/Média/Máximo/Mínimo
    # viraram tokens comuns, mesma forma de sin(/cos(, não mais um
    # mecanismo de "resultado pendente" à parte — ver OPERACOES_
    # RAPIDAS/avaliar_expressao_calculadora em
    # src/core/operations/calculadora.py):
    #   1) registrar_token_calculadora: clique em QUALQUER token
    #      (número/operador/função/operação/coluna — todos usam o
    #      MESMO padrão de id, ver _botao_token_calculadora em
    #      renderizadores.py) anexa esse token na expressão. Só
    #      atualiza a BARRA (não os botões — que não mudam com a
    #      expressão, ver renderizar_calculadora_botoes).
    #   2) apagar_ultimo_token_calculadora: '⌫' remove o ÚLTIMO token —
    #      2 botões idênticos disparam (o da barra e o duplicado no
    #      topo do teclado, ver renderizar_calculadora_botoes).
    #   3) limpar_expressao_calculadora: 'Limpar'/'C' zera tudo — mesmo
    #      esquema de 2 botões.
    #   4) criar_canal_calculado_calculadora: 'Criar' — avalia a
    #      expressão (agora sempre via avaliar_expressao_calculadora,
    #      nunca mais um resultado pré-calculado à parte) e GRAVA o
    #      resultado como coluna NOVA ou SOBRESCREVENDO uma existente,
    #      conforme o seletor 'calc-tipo-destino' no início da barra.
    # ------------------------------------------------------------------

    @app.callback(
        Output('calc-nome-input', 'className'),
        Output('calc-coluna-destino', 'className'),
        Input('calc-tipo-destino', 'value'),
        prevent_initial_call=True,
    )
    def alternar_tipo_destino_calculadora(tipo_destino):
        """
        Troca o seletor 'Nova coluna' / 'Coluna existente' (início da
        barra) alterna qual dos dois campos fica visível — o campo de
        NOME (pra batizar a coluna nova) ou o DROPDOWN de qual coluna
        sobrescrever. Os dois já nascem sempre no DOM (ver
        renderizar_calculadora_barra, renderizadores.py — só um deles
        escondido via classe 'calculadora-oculto'); esta callback só
        precisava REAGIR à troca do seletor pra alternar qual classe
        cada um leva — antes só existia como leitura (State) nos
        outros callbacks (Criar/token/etc.), nunca como gatilho próprio
        pra essa troca visual, então o campo certo nunca aparecia
        sozinho ao mudar o seletor.

        Só troca 2 classNames — não reconstrói a barra inteira (evita
        remontar os outros componentes à toa, inclusive os de padrão
        coringa que são sensíveis a disparo fantasma em remontagem).
        """
        if not tipo_destino:
            raise PreventUpdate
        modo_nova = tipo_destino != 'existente'
        classe_nome = 'calculadora-nome-input' + ('' if modo_nova else ' calculadora-oculto')
        classe_coluna = 'calculadora-coluna-destino' + ('' if not modo_nova else ' calculadora-oculto')
        return classe_nome, classe_coluna

    @app.callback(
        Output('calc-criar', 'disabled', allow_duplicate=True),
        Output('calc-criar', 'className', allow_duplicate=True),
        Input('calc-nome-input', 'value'),
        Input('calc-coluna-destino', 'value'),
        Input('calc-tipo-destino', 'value'),
        State('calc-expressao-store', 'data'),
        prevent_initial_call=True,
    )
    def atualizar_estado_botao_criar_calculadora(nome_novo_canal, coluna_destino, tipo_destino, tokens_atuais):
        """
        Leve DE PROPÓSITO — só troca 'disabled'/'className' de
        'calc-criar', sem reconstruir a barra inteira (diferente de
        registrar_token_calculadora/apagar/limpar, que precisam
        reconstruir porque mexem na lista de chips). Existe pra
        digitar um nome (ou trocar a coluna a sobrescrever) já
        reativar/desativar 'Criar' NA HORA, sem precisar clicar em
        outro token pra isso.

        Mesma regra de calc_criar_desabilitado (calculadora.py) usada
        na reconstrução completa — as duas PRECISAM concordar, senão
        um dá um resultado e o outro reverte no próximo render.
        """
        desabilitado = calc_criar_desabilitado(tokens_atuais, tipo_destino, nome_novo_canal, coluna_destino)
        classe = 'calculadora-btn-criar' + (' calculadora-btn-criar-desabilitado' if desabilitado else '')
        return desabilitado, classe

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input({'type': 'calc-token', 'display': ALL, 'codigo': ALL, 'classe': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('calc-nome-input', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def registrar_token_calculadora(_n_clicks_list, aba_ativa, tokens_atuais, tipo_destino,
                                     coluna_destino, nome_novo_canal, nclicks_anteriores):
        # Mesmo cuidado de gerenciar_selecao_canais/gerenciar_abas: os
        # botões de token são padrão coringa, e a barra É reconstruída
        # por outro callback (alternar_modo_nova_analise, ao ligar, e
        # sincronizar_interface_por_aba, ao trocar de aba) — sem
        # comparar contra o último valor visto, uma reconstrução alheia
        # adicionaria um token sozinho, sem clique nenhum do usuário
        # (ver _processar_cliques_padrao, src/callbacks/_comum.py).
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate

        # 'classe' (ver _botao_token_calculadora, renderizadores.py)
        # viaja junto no id só pra a barra desenhar este token como um
        # "chip" com a MESMA cor do botão original (ver
        # renderizar_calculadora_barra) — pedido explícito, em vez de
        # texto solto sem cor nenhuma.
        novo_token = {
            'display': gatilho_id.get('display'),
            'codigo': gatilho_id.get('codigo'),
            'classe': gatilho_id.get('classe', ''),
        }
        novos_tokens = (tokens_atuais or []) + [novo_token]

        # 'nome_novo_canal' (lido aqui via State, só pra passar adiante)
        # é o que permite 'renderizar_calculadora_barra' decidir se
        # 'Criar' nasce desabilitado (ver calc_criar_desabilitado,
        # calculadora.py) já considerando o nome digitado ANTES deste
        # clique de token — sem isso, clicar num token depois de já
        # ter digitado um nome reativaria 'Criar' incorretamente com
        # base só no parêntese, ignorando o nome.
        conteudo = renderizar_area_calculadora_completa(
            estado, aba_ativa, novos_tokens, tipo_destino, coluna_destino, nome_novo_canal,
        )
        return conteudo, novos_tokens, novo_mapa

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input('calc-apagar', 'n_clicks'),
        Input('calc-apagar-teclado', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('calc-nome-input', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def apagar_ultimo_token_calculadora(_n1, _n2, aba_ativa, tokens_atuais, tipo_destino,
                                         coluna_destino, nome_novo_canal, nclicks_anteriores):
        """
        '⌫' remove o ÚLTIMO token — 2 botões idênticos disparam este
        callback: o da barra ('calc-apagar') e o duplicado no topo do
        teclado ('calc-apagar-teclado', ver renderizar_calculadora_
        botoes) — pedido explícito, pra poder apagar sem precisar
        olhar pra barra lá em cima.

        'calc-apagar' mora DENTRO da barra, que é reconstruída inteira
        a cada token clicado (ver registrar_token_calculadora) — sem
        _processar_cliques_padrao (que agora também rastreia ids
        FIXOS, não só padrão coringa, ver _chave_id_padrao), esse
        remonte disparava este callback SOZINHO logo depois de
        qualquer clique de token, apagando o token que acabara de ser
        adicionado (o bug "clico na coluna e ela some sozinha").
        """
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None or not tokens_atuais:
            raise PreventUpdate
        novos_tokens = tokens_atuais[:-1]
        conteudo = renderizar_area_calculadora_completa(
            estado, aba_ativa, novos_tokens, tipo_destino, coluna_destino, nome_novo_canal,
        )
        return conteudo, novos_tokens, novo_mapa

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input('calc-limpar', 'n_clicks'),
        Input('calc-limpar-teclado', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('calc-nome-input', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def limpar_expressao_calculadora(_n1, _n2, aba_ativa, tipo_destino, coluna_destino,
                                      nome_novo_canal, nclicks_anteriores):
        """'Limpar'/'C' zera tudo — mesmo esquema de 2 botões
        idênticos e mesmo guard anti-fantasma de
        'apagar_ultimo_token_calculadora' acima ('calc-limpar' também
        mora dentro da barra reconstruída a cada token)."""
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate
        conteudo = renderizar_area_calculadora_completa(
            estado, aba_ativa, [], tipo_destino, coluna_destino, nome_novo_canal,
        )
        return conteudo, [], novo_mapa

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('selecao-eixos-container', 'children', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'children', allow_duplicate=True),
        saida_feedback('calculadora'),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input('calc-criar', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('calc-nome-input', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def criar_canal_calculado_calculadora(n_clicks, aba_ativa, tokens_atuais,
                                           tipo_destino, coluna_destino, nome_novo_canal, nclicks_anteriores):
        """
        'calc-criar' TAMBÉM mora dentro da barra (reconstruída a cada
        token clicado) — mesmo guard anti-fantasma das outras 3
        callbacks da calculadora, ainda mais importante aqui: sem ele,
        clicar num token de coluna poderia disparar 'Criar' sozinho
        (gravando uma coluna nova sem o usuário ter pedido isso).
        """
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate

        arquivo = estado.arquivos.get(aba_ativa)
        if not arquivo:
            raise PreventUpdate

        def _sem_mudanca_de_conteudo(feedback):
            """Devolve os 8 valores desta callback quando SÓ a mensagem
            do rodapé muda (erro de validação) — a barra/expressão/
            listas continuam exatamente como estavam."""
            return no_update, no_update, no_update, no_update, no_update, no_update, feedback, novo_mapa

        codigo = ''.join(t['codigo'] for t in (tokens_atuais or []))
        try:
            valores = avaliar_expressao_calculadora(codigo, arquivo, estado).tolist()
        except ValueError as e:
            return _sem_mudanca_de_conteudo(Feedback.erro(f'Não deu pra criar: {e}'))

        area_grafico = no_update

        if tipo_destino == 'existente':
            # --- Sobrescreve uma coluna JÁ EXISTENTE ---
            if not coluna_destino or coluna_destino not in arquivo.df_editado.columns:
                return _sem_mudanca_de_conteudo(Feedback.aviso('Escolha qual coluna sobrescrever antes de criar.'))

            arquivo.df_editado[coluna_destino] = valores
            canal = arquivo.canais.get(coluna_destino) or arquivo.registrar_canal(coluna_destino)
            canal.origem = 'calculado'
            canal.formula = codigo
            # AGORA SIM invalida o cache — sobrescrever os DADOS de uma
            # coluna que já existe pode mudar uma curva JÁ desenhada no
            # gráfico (diferente de criar uma coluna nova, que nasce
            # sempre fora da seleção e não afeta nada plotado).
            if arquivo.grafico_gerado:
                arquivo.invalidar_grafico()
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)
            feedback = Feedback.sucesso(f"Coluna '{arquivo.rotulo(coluna_destino)}' recalculada.")
        else:
            # --- Cria uma coluna NOVA ---
            nome_novo_canal = (nome_novo_canal or '').strip()
            if not nome_novo_canal:
                return _sem_mudanca_de_conteudo(Feedback.aviso('Dê um nome pra essa análise antes de criar.'))

            # Nome interno sanitizado (sem espaço/acento/símbolo) pra
            # virar coluna de verdade no df_editado — o RÓTULO exibido
            # continua sendo o texto livre digitado (mesma separação
            # nome_interno/rótulo de todo Canal, ver src/core/arquivo.py).
            nome_interno = sanitizar_rotulo_para_nome_coluna(nome_novo_canal)
            sufixo = 1
            nome_interno_final = nome_interno
            while nome_interno_final in arquivo.df_editado.columns:
                sufixo += 1
                nome_interno_final = f'{nome_interno}_{sufixo}'

            arquivo.df_editado[nome_interno_final] = valores
            arquivo.registrar_canal(nome_interno_final, rotulo=nome_novo_canal,
                                     origem='calculado', formula=codigo)

            # ATRIBUI a coluna nova ao eixo Y e já REDESENHA (pedido
            # explícito: "ao gerar a nova coluna, atualizar o gráfico
            # com a nova coluna exibida, carregar a miniatura pra que
            # ela seja atualizada") — antes usava o antigo 'estado.
            # canais_selecionados' (checkbox), que deixou de ser lido
            # pelo gráfico desde o rework do 'Plotar Seleção' (ver
            # colunas_plotadas, plotter.py); agora usa 'Arquivo.
            # mover_para_eixo_y' (já cuida de ocultar da lista e
            # invalidar o cache sozinho). Vai sempre pra Y, nunca vira
            # X sozinha — faz mais sentido um canal recém-CALCULADO ser
            # uma curva, não o eixo. Só redesenha de verdade se JÁ
            # existia um gráfico montado nesta aba ANTES desta chamada
            # (mesmo cuidado de 'gerenciar_atribuicao_eixos' logo
            # abaixo: se o usuário ainda nem gerou o primeiro gráfico,
            # atribuir não deve empurrar ele direto pra visualização
            # sozinho — só garante que a curva já nasce atribuída pra
            # quando ele gerar). IMPORTANTE: precisa ser checado ANTES
            # de chamar 'mover_para_eixo_y' — esse método já invalida o
            # cache da figura sozinho, então checar DEPOIS sempre daria
            # False (mesmo bug já corrigido em gerenciar_atribuicao_eixos).
            tinha_grafico = arquivo.grafico_gerado
            arquivo.mover_para_eixo_y(nome_interno_final)
            if tinha_grafico:
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)
            feedback = Feedback.sucesso(f"Canal '{nome_novo_canal}' criado ({codigo}).")

        # Limpa a expressão depois de criar (mesmo espírito de um
        # formulário que reseta após salvar) — 'nome_novo_canal=None'
        # aqui é só pro CÁLCULO de 'disabled' de 'Criar' na barra
        # reconstruída (ver calc_criar_desabilitado); o campo de nome
        # em si é 'uncontrolled' (sem 'value=' fixo, ver
        # renderizar_calculadora_barra) e o navegador some com o texto
        # digitado sozinho quando o nó reconstruído tiver a mesma
        # estrutura — não precisa de um reset explícito aqui.
        conteudo = renderizar_area_calculadora_completa(estado, aba_ativa, [], tipo_destino, None, None)
        # 'area-modo-nova-analise-edicao' (grupo 'Colunas' do teclado,
        # ver renderizar_calculadora_botoes) — SEM isto, a coluna
        # recém-criada só aparecia como botão clicável depois de
        # recarregar a página inteira (pedido explícito: "quando eu
        # crio uma nova coluna, ela já aparece no espaço das colunas
        # pra poder ser operada de novo", ex: usar o resultado de um
        # cálculo como argumento de outro).
        botoes_calculadora = renderizar_calculadora_botoes(estado, aba_ativa)
        return (conteudo, [],
                renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                renderizar_selecao_eixos(estado, aba_ativa),
                area_grafico, botoes_calculadora, feedback, novo_mapa)

    @app.callback(
        Output('modo-nova-analise-store', 'data', allow_duplicate=True),
        Output('nova-analise', 'className', allow_duplicate=True),
        Output('area-grafico-normal', 'style', allow_duplicate=True),
        Output('area-modo-nova-analise', 'style', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'style', allow_duplicate=True),
        Input('aparar-dados', 'n_clicks'),
        Input('excluir-dados', 'n_clicks'),
        State('modo-nova-analise-store', 'data'),
        prevent_initial_call=True,
    )
    def desligar_calculadora_ao_iniciar_corte(n_clicks_aparar, n_clicks_excluir, modo_calculadora_ativo):
        """
        Desliga o modo 'Nova Análise' ao clicar em 'Aparar dados'/
        'Excluir dados' — SEPARADO de propósito de 'iniciar_selecao_
        corte' acima (mesmos 2 botões como Input, MAS nenhum Output em
        comum): a seleção de corte depende de clicar de verdade no
        gráfico PRINCIPAL ('#grafico-plotly-real', dentro de
        '#area-grafico-normal'), que fica 'display:none' enquanto o
        modo calculadora está ligado (ver alternar_modo_nova_analise)
        — sem desligar a calculadora primeiro, clicar em 'Aparar
        dados'/'Excluir dados' armava a seleção mas nunca recebia
        clique nenhum, porque o gráfico que precisa ser clicado estava
        escondido.

        Ficar num callback À PARTE (em vez de virar mais Outputs de
        'iniciar_selecao_corte') é proposital: uma tentativa anterior
        de fazer os dois num callback só introduziu um bug de "disparo
        fantasma" na calculadora (um token clicado sumia sozinho da
        barra) sem relação óbvia com este código — bug que sumiu ao
        separar de novo. Dash permite os DOIS callbacks escutarem os
        MESMOS botões em paralelo sem conflito, já que os conjuntos de
        Outputs de cada um não se cruzam.
        """
        if ctx.triggered_id not in ('aparar-dados', 'excluir-dados'):
            raise PreventUpdate
        if not modo_calculadora_ativo:
            raise PreventUpdate

        return (
            False,
            'toolbar-upload',
            {'display': 'block'},
            {'display': 'none'},
            {'display': 'none'},
        )
