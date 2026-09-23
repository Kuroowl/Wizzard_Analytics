import json

from dash import Input, Output, State, ctx, ALL, MATCH, no_update
from dash.exceptions import PreventUpdate

from src.core.operations.sampling import aparar_dados, excluir_dados
from src.core.operations.calculadora import avaliar_expressao_calculadora, calc_criar_desabilitado
from src.core.plotting.plotter import (
    construir_figura_serie_temporal, resolver_eixo_x, colunas_plotadas, cor_da_coluna,
    aplicar_guias_corte,
)
from src.core.rotulos import sanitizar_rotulo_para_nome_coluna
from src.gui.renderizadores import (
    truncar_nome_arquivo, renderizar_colunas_da_aba_ativa,
    renderizar_selecao_eixos, renderizar_grafico_com_fechar,
    renderizar_painel_direito_padrao, renderizar_painel_edicao,
    renderizar_calculadora_barra, renderizar_area_calculadora_completa, renderizar_calculadora_botoes, _hex_para_rgb,
)
from src.gui.feedback import Feedback, saida_feedback
from src.gui.rodape import obter_estado_rodape, registrar_callbacks_rodape
from src.callbacks._comum import (
    _processar_cliques_padrao, _estados_toolbar, _classe_painel_direito,
)
from src.callbacks.abas import registrar_callbacks_abas
from src.callbacks.arquivos import registrar_callbacks_arquivos
from src.callbacks.grafico import registrar_callbacks_grafico
from src.callbacks.nova_amostragem import registrar_callbacks_nova_amostragem


def registrar_callbacks(app, estado):
    """
    Registra todos os callbacks do app. Recebe 'app' (pra decorar com
    @app.callback) e 'estado' (o EstadoApp global, compartilhado com
    layout.py) — este módulo não decide qual app instanciar nem qual
    estado usar, só liga os dois.
    """
    # A mensagem do mago tem um único dono (src/gui/rodape.py). Os
    # callbacks abaixo só emitem Feedback em seu próprio canal.
    registrar_callbacks_rodape(app)

    # --- Módulos já migrados pra src/callbacks/ (Fase 2) ---
    registrar_callbacks_arquivos(app, estado)
    registrar_callbacks_abas(app, estado)
    registrar_callbacks_grafico(app, estado)
    registrar_callbacks_nova_amostragem(app, estado)

    # --- Ainda não migrados (tudo abaixo) ---

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
        # As DUAS áreas ('#area-grafico-normal' e '#area-modo-nova-
        # analise') são MUTUAMENTE EXCLUSIVAS — nunca as duas visíveis
        # ao mesmo tempo (ver docstring completa em layout.py sobre por
        # que viraram áreas separadas, em vez de tentar encaixar a
        # barra dentro da área do gráfico normal). '#container-grafico'
        # dentro de '#area-grafico-normal' NUNCA é tocado aqui — o
        # gráfico continua exatamente como estava, só fica escondido/
        # mostrado por inteiro via este 'display'.
        estilo_area_grafico = {'display': 'none'} if novo_ativo else {'display': 'block'}
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
    #      sempre com _processar_cliques_padrao.
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
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input({'type': 'linha-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'botao-excluir-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'remover-eixo-selecionado', 'arquivo': ALL, 'coluna': ALL, 'eixo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('painel-direito', 'className'),
        State('edicao-curva-dado-atual', 'data'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_atribuicao_eixos(n_clicks_linha, _n_clicks_excluir, _n_clicks_remover, aba_ativa,
                                    classe_painel_direito, coluna_em_edicao, nclicks_anteriores):
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

        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
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
                painel_edicao, novo_mapa)

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
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input({'type': 'botao-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_clicks'),
        Input({'type': 'input-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'n_submit'),
        State({'type': 'input-editar-canal', 'arquivo': ALL, 'coluna': ALL}, 'value'),
        State('aba-ativa-store', 'data'),
        State('canal-em-edicao-store', 'data'),
        State('painel-direito', 'className'),
        State('edicao-curva-dado-atual', 'data'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_edicao_canal(_n_clicks_lapis, _n_submit_input, _valores_input_bruto, aba_ativa,
                                canal_em_edicao, classe_painel_direito, coluna_em_edicao_painel,
                                nclicks_anteriores):
        if not aba_ativa:
            raise PreventUpdate

        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
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
                novo_canal_em_edicao, area_grafico, feedback, painel_edicao, novo_mapa)

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

    @app.callback(
        Output('edicao-curva-dado-atual', 'data'),
        Input('edicao-curva-dado', 'value'),
        prevent_initial_call=True,
    )
    def sincronizar_curva_em_edicao(coluna):
        """
        Espelha 'edicao-curva-dado'.value em 'edicao-curva-dado-atual'
        (Store fixo, ver layout.py) toda vez que o dropdown muda. Como
        'edicao-curva-dado' é o próprio Input aqui, esse callback só
        chega a rodar quando ele já existe na árvore — nada a temer
        (diferente de usá-lo como State em outro callback, ver
        gerenciar_selecao_canais).
        """
        return coluna

    @app.callback(
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Input('iniciar-edicao', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def abrir_painel_edicao(n_clicks, aba_ativa):
        """
        Único gatilho que liga o modo 'edição' do painel de edição — não
        reage sozinho a upload de arquivo ou geração de gráfico, só a
        este clique. Fechar o gráfico, trocar de aba ou clicar em
        'Fechar edição' desliga de novo (ver fechar_grafico,
        gerenciar_abas e fechar_edicao_curva).

        Diferente da versão antiga: não é mais só uma troca de classe
        CSS (cor de fundo) — agora carrega de verdade o painel 'Curva'
        (renderizar_painel_edicao) dentro de 'painel-direito-conteudo',
        com a caixa 'Dado' já preenchida com as curvas que estão no
        gráfico agora.
        """
        if not n_clicks or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate
        return renderizar_painel_edicao(estado, aba_ativa), _classe_painel_direito(ativo=True)

    @app.callback(
        Output('edicao-curva-espessura', 'value'),
        Output({'type': 'cor-store', 'index': 'curva'}, 'data'),
        Output('edicao-curva-estilo', 'value'),
        Output('edicao-curva-marcador', 'value'),
        Output('edicao-curva-tamanho-marcador', 'value'),
        Output('edicao-curva-tamanho-marcador-wrapper', 'style'),
        Output({'type': 'cor-rgb-r', 'index': 'curva'}, 'value'),
        Output({'type': 'cor-rgb-g', 'index': 'curva'}, 'value'),
        Output({'type': 'cor-rgb-b', 'index': 'curva'}, 'value'),
        Input('edicao-curva-dado', 'value'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_campos_curva_selecionada(coluna, aba_ativa):
        """
        Toda vez que o usuário troca a curva escolhida na caixa 'Dado',
        os controles abaixo (Thickness, cor, Style, Marker e o Marker
        size) precisam refletir o que JÁ está salvo pra essa curva
        especificamente — senão eles ficariam mostrando o valor da curva
        anterior. Também dispara (efeito colateral esperado, não um bug)
        na primeira vez que o painel abre, já que a caixa 'Dado' acabou
        de nascer com um valor — é o mesmo 'gatilho fantasma' de
        componente recém-criado comentado em _clique_real, aqui é ele
        quem faz os controles nascerem com os valores certos sem
        precisar duplicar essa lógica em abrir_painel_edicao.

        A barra 'Marker size' também precisa nascer ESCONDIDA ou VISÍVEL
        de acordo com o marcador salvo dessa curva (não só o valor —
        o wrapper inteiro, ver 'edicao-curva-tamanho-marcador-wrapper'
        em renderizadores.py), senão trocar de curva podia deixar a
        barra visível sem marcador nenhum, ou escondida com um marcador
        já escolhido.

        'Dado' pode nascer SEM valor agora (nenhum canal plotado, ver
        renderizar_painel_edicao) — nesse caso não tem curva nenhuma
        pra sincronizar, então só sai sem fazer nada.
        """
        if not coluna or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        colunas = colunas_plotadas(estado, aba_ativa)
        if coluna not in colunas:
            raise PreventUpdate

        prefs = arquivo.preferencias.por_canal.get(coluna)
        cor_atual = prefs.cor if (prefs and prefs.cor) else cor_da_coluna(colunas.index(coluna))
        espessura_atual = prefs.espessura if prefs else 1.0
        estilo_atual = prefs.estilo_linha if prefs else 'solid'
        marcador_atual = prefs.marcador if prefs else 'none'
        tamanho_marcador_atual = prefs.tamanho_marcador if prefs else 7.0
        estilo_barra_tamanho_marcador = (
            {} if marcador_atual != 'none' else {'display': 'none'}
        )
        r, g, b = _hex_para_rgb(cor_atual)
        return (
            espessura_atual, cor_atual, estilo_atual, marcador_atual,
            tamanho_marcador_atual, estilo_barra_tamanho_marcador,
            r, g, b,
        )

    @app.callback(
        Output({'type': 'cor-store', 'index': MATCH}, 'data', allow_duplicate=True),
        Output({'type': 'cor-picker-caixa', 'index': MATCH}, 'style', allow_duplicate=True),
        Input({'type': 'cor-rgb-r', 'index': MATCH}, 'value'),
        Input({'type': 'cor-rgb-g', 'index': MATCH}, 'value'),
        Input({'type': 'cor-rgb-b', 'index': MATCH}, 'value'),
        prevent_initial_call=True,
    )
    def sincronizar_cor_rgb(r, g, b):
        """
        Fonte de verdade dos 3 campos R/G/B de QUALQUER seletor de cor
        do painel (ver _seletor_cor em renderizadores.py) — preenchidos
        tanto por digitação direta quanto pelo arraste do mouse na área
        de saturação/matiz (que escreve nesses mesmos campos disparando
        um evento 'input' nativo, ver iniciarSeletorCor em
        scripts_js.py).

        MATCH liga cada instância deste callback a UM seletor de cor
        específico (mesmo 'index'/prefixo nos ids do trio R/G/B, do
        Store e da caixinha) — é o que permite existir mais de um
        seletor de cor no painel (hoje: cor da 'Curva' e cor de fundo
        do gráfico em 'Outros') com um único callback genérico, em vez
        de duplicar esta função por seletor.

        Traduz pra hex e grava no Store 'cor-store' daquele índice (o
        que aplicar_preferencias_curva lê pra cor da curva; a cor de
        fundo ainda não tem um consumidor no gráfico — ver comentário
        em conteudo_outros, renderizadores.py) e atualiza a cor de
        fundo da caixinha visível fora do painel.
        """
        if r is None or g is None or b is None:
            raise PreventUpdate
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        cor_hex = f'#{r:02x}{g:02x}{b:02x}'
        return cor_hex, {'backgroundColor': cor_hex}

    # Callback client-side (roda no navegador, sem round-trip com o
    # servidor): reposiciona o cursor da área de saturação/brilho, o
    # cursor da barra de matiz e a cor de fundo da área, toda vez que
    # os campos R/G/B mudam — seja por digitação direta, seja porque
    # 'sincronizar_campos_curva_selecionada' trocou de curva. Sem isto,
    # o seletor visual ficaria "desalinhado" do valor real sempre que a
    # cor mudasse por um caminho que não fosse o próprio arraste do
    # mouse (que já se auto-posiciona, ver moverNaArea/moverNoHue em
    # scripts_js.py).
    #
    # MATCH também aqui (mesmo 'index'/prefixo nos 3 R/G/B de entrada e
    # nos 3 alvos de saída) — cada seletor de cor do painel atualiza só
    # o próprio cursor/área, nunca o de outro seletor. Pra achar O
    # WRAPPER certo (guardar hue/sat/val em dataset, usado pelo próximo
    # arraste do mouse) não dá pra usar mais um id fixo tipo
    # 'cor-picker-caixa' — em vez disso lê 'triggered_id.index' (o
    # mesmo prefixo) e procura o wrapper por '[data-prefixo=...]',
    # atributo gravado no Python em _seletor_cor (renderizadores.py).
    app.clientside_callback(
        """
        function(r, g, b) {
            if (r === null || r === undefined || g === null || g === undefined || b === null || b === undefined) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            var hsv = window.wizzardCor.rgbParaHsv(
                Math.max(0, Math.min(255, r)),
                Math.max(0, Math.min(255, g)),
                Math.max(0, Math.min(255, b))
            );
            var triggered = window.dash_clientside.callback_context.triggered_id;
            var prefixo = triggered ? triggered.index : null;
            var wrapper = prefixo
                ? document.querySelector('.cor-picker-wrapper[data-prefixo="' + prefixo + '"]')
                : null;
            if (wrapper) {
                wrapper.dataset.hue = hsv.h;
                wrapper.dataset.sat = hsv.s;
                wrapper.dataset.val = hsv.v;
            }
            return [
                {backgroundColor: 'hsl(' + hsv.h.toFixed(1) + ', 100%, 50%)'},
                {left: (hsv.s * 100).toFixed(2) + '%', top: ((1 - hsv.v) * 100).toFixed(2) + '%'},
                {left: (hsv.h / 360 * 100).toFixed(2) + '%'},
            ];
        }
        """,
        Output({'type': 'cor-picker-area-fundo', 'index': MATCH}, 'style'),
        Output({'type': 'cor-picker-area-cursor', 'index': MATCH}, 'style'),
        Output({'type': 'cor-picker-hue-cursor', 'index': MATCH}, 'style'),
        Input({'type': 'cor-rgb-r', 'index': MATCH}, 'value'),
        Input({'type': 'cor-rgb-g', 'index': MATCH}, 'value'),
        Input({'type': 'cor-rgb-b', 'index': MATCH}, 'value'),
        prevent_initial_call=True,
    )

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('edicao-curva-tamanho-marcador-wrapper', 'style', allow_duplicate=True),
        Input('edicao-curva-espessura', 'value'),
        Input({'type': 'cor-store', 'index': 'curva'}, 'data'),
        Input('edicao-curva-estilo', 'value'),
        Input('edicao-curva-marcador', 'value'),
        Input('edicao-curva-tamanho-marcador', 'value'),
        State('edicao-curva-dado', 'value'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_preferencias_curva(espessura, cor, estilo, marcador, tamanho_marcador, coluna, aba_ativa):
        """
        Grava os 5 controles do painel 'Curva' como preferência
        PERMANENTE do canal (arquivo.preferencias, ver src/core/arquivo.py)
        e redesenha o gráfico na hora — é o que faz o slider/color-
        picker/dropdown(s) terem efeito visual imediato, em vez de só
        ficarem guardados sem uso (que era o estado anterior: o modelo
        já existia, só não era lido por construir_figura_serie_temporal).

        'marcador' é INDEPENDENTE de 'estilo' — escolher um marcador
        soma um símbolo em cada ponto da MESMA curva, sem trocar o
        estilo da linha nem "virar" outro tipo de gráfico (ver
        resolver_modo em plotter.py, que combina os dois no 'mode' que
        go.Scatter entende). Voltar pra opção em branco (value 'none')
        em qualquer uma das duas caixas basta pra desfazer aquele lado
        específico (linha ou marcador) — não existe botão "desfazer"
        separado.

        'tamanho_marcador' só tem efeito visual enquanto 'marcador' !=
        'none' (ver TAMANHO_MARCADOR_PADRAO/tamanho_marcador em
        plotter.py) — mas o valor do slider é sempre gravado, mesmo com
        a barra escondida, pra não perder o ajuste do usuário se ele
        remover e escolher outro marcador em seguida.

        Este é também o callback que ESCONDE/MOSTRA a barra 'Marker
        size' em tempo real: como 'marcador' já é um dos Inputs (pra
        gravar a preferência), o mesmo disparo calcula o 'style' do
        wrapper da barra — visível assim que um marcador é escolhido,
        escondida de novo assim que volta pra 'none' — sem precisar de
        um callback à parte escutando o mesmo dropdown.

        Os Inputs disparam juntos neste único callback (em vez de vários
        callbacks separados) porque todos preenchem o MESMO
        PreferenciasCanal e precisam terminar sempre com os valores
        atuais gravados juntos — gravar só o campo que mudou arriscaria
        um 'value' desatualizado vencer a corrida se dois campos forem
        mexidos em sequência rápida.
        """
        if not coluna or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        if not arquivo.grafico_gerado or coluna not in colunas_plotadas(estado, aba_ativa):
            raise PreventUpdate

        marcador = marcador or 'none'
        prefs = arquivo.preferencias.preferencias_do_canal(coluna)
        prefs.espessura = espessura or 1.0
        prefs.cor = cor
        prefs.estilo_linha = estilo or 'solid'
        prefs.marcador = marcador
        prefs.tamanho_marcador = tamanho_marcador or 7.0

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        estilo_barra_tamanho_marcador = {} if marcador != 'none' else {'display': 'none'}
        return renderizar_grafico_com_fechar(fig), estilo_barra_tamanho_marcador

    @app.callback(
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Input('fechar-edicao-curva', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def fechar_edicao_curva(n_clicks, aba_ativa):
        """
        Botão '✕' dentro do próprio card 'Curva' — volta o painel pro
        estado de repouso sem depender de trocar de aba ou fechar o
        gráfico (que já fazem o mesmo reset por outros gatilhos, ver
        gerenciar_abas / fechar_grafico). O 'disabled' do botão
        'Iniciar edição' que volta a aparecer é recalculado aqui (não
        fixo em True), pra continuar habilitado se a aba ativa ainda
        tiver gráfico gerado.
        """
        if not n_clicks:
            raise PreventUpdate
        _, _, sem_grafico_da_aba = _estados_toolbar(estado, aba_ativa)
        return renderizar_painel_direito_padrao(disabled=sem_grafico_da_aba), _classe_painel_direito(ativo=False)

    @app.callback(
        Output({'type': 'secao-wrapper', 'index': MATCH}, 'className'),
        Input({'type': 'secao-header', 'index': MATCH}, 'n_clicks'),
        State({'type': 'secao-wrapper', 'index': MATCH}, 'className'),
        prevent_initial_call=True,
    )
    def alternar_secao_edicao(n_clicks, classe_atual):
        """
        Abre/fecha UMA seção recolhível do painel de edição ('Curva',
        'Eixos', 'Ticks', 'Outros'...), independente das outras.
        MATCH garante uma instância deste callback por seção — cada
        clique só afeta o 'secao-wrapper' com o mesmo 'index' do
        'secao-header' clicado, sem precisar de um Store extra pra
        guardar qual seção está aberta (ver _secao_colapsavel em
        renderizadores.py).
        """
        if not n_clicks:
            raise PreventUpdate
        aberta = 'aberta' in (classe_atual or '').split()
        return 'painel-edicao-secao' if aberta else 'painel-edicao-secao aberta'

    @app.callback(
        Output({'type': 'stepper-valor', 'index': MATCH}, 'value'),
        Input({'type': 'stepper-menos', 'index': MATCH}, 'n_clicks'),
        Input({'type': 'stepper-mais', 'index': MATCH}, 'n_clicks'),
        State({'type': 'stepper-valor', 'index': MATCH}, 'value'),
        State({'type': 'stepper-valor', 'index': MATCH}, 'step'),
        State({'type': 'stepper-valor', 'index': MATCH}, 'min'),
        State({'type': 'stepper-valor', 'index': MATCH}, 'max'),
        prevent_initial_call=True,
    )
    def alternar_stepper(n_menos, n_mais, valor_atual, passo, minimo, maximo):
        """
        Callback ÚNICO e genérico pra qualquer par de botões '-'/'+'
        do painel de edição (hoje: tamanho de fonte e espaçamento das
        3 linhas de 'Eixos'; serve também pra qualquer stepper futuro
        em 'Ticks', sem precisar escrever um callback novo — basta
        usar _stepper com um 'index' próprio, ver renderizadores.py).

        MATCH liga cada instância deste callback a UM stepper
        específico (mesmo 'index' nos 3 ids: menos/valor/mais). Qual
        dos dois botões foi clicado é lido em 'ctx.triggered_id'
        (o dict completo do id do componente que disparou), não pelos
        valores de n_clicks em si — comparar n_clicks entre os dois
        botões não diria qual foi o ÚLTIMO clicado de forma confiável.

        min/max/step vêm como State do próprio dcc.Input (não são
        fixos aqui): cada linha de 'Eixos' já nasce com limites
        diferentes (fonte: 6-48, espaçamento: -5-20 — ver _linha_eixo),
        e este callback só respeita o que já está declarado no
        componente, em vez de duplicar esses números em dois lugares.
        """
        if not ctx.triggered_id:
            raise PreventUpdate

        passo = passo if passo not in (None, 0) else 1
        valor_atual = valor_atual if valor_atual is not None else (minimo or 0)

        if ctx.triggered_id.get('type') == 'stepper-menos':
            novo_valor = valor_atual - passo
        else:
            novo_valor = valor_atual + passo

        if minimo is not None:
            novo_valor = max(minimo, novo_valor)
        if maximo is not None:
            novo_valor = min(maximo, novo_valor)
        return novo_valor

    @app.callback(
        Output({'type': 'limite-cadeado', 'index': MATCH}, 'children'),
        Output({'type': 'limite-cadeado', 'index': MATCH}, 'className'),
        Input({'type': 'limite-cadeado', 'index': MATCH}, 'n_clicks'),
        State({'type': 'limite-cadeado', 'index': MATCH}, 'className'),
        prevent_initial_call=True,
    )
    def alternar_cadeado_limite(n_clicks, classe_atual):
        """
        Alterna o ícone/estado visual do cadeado de 'Limits' (Eixos) —
        🔓 (destravado, padrão) <-> 🔒 (travado). Quem GRAVA esse
        estado em 'estado' (PreferenciasLimiteEixo.travado, ver
        src/core/arquivo.py) é aplicar_preferencias_eixos logo abaixo,
        que lê a className deste botão como Input — travar de verdade
        o range no gráfico já acontece hoje (min/max preenchidos), o
        cadeado é só o lembrete visual desse estado.
        """
        if not n_clicks:
            raise PreventUpdate
        travado = 'travado' in (classe_atual or '').split()
        if travado:
            return '🔓', 'painel-edicao-limite-btn'
        return '🔒', 'painel-edicao-limite-btn travado'

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Input('edicao-eixo-titulo-texto', 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-titulo-fonte'}, 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-titulo-espacamento'}, 'value'),
        Input('edicao-eixo-x-texto', 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-x-fonte'}, 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-x-espacamento'}, 'value'),
        Input('edicao-eixo-y-texto', 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-y-fonte'}, 'value'),
        Input({'type': 'stepper-valor', 'index': 'edicao-eixo-y-espacamento'}, 'value'),
        Input('edicao-eixo-x-limite-min', 'value'),
        Input('edicao-eixo-x-limite-max', 'value'),
        Input('edicao-eixo-y-limite-min', 'value'),
        Input('edicao-eixo-y-limite-max', 'value'),
        Input({'type': 'limite-cadeado', 'index': 'x'}, 'className'),
        Input({'type': 'limite-cadeado', 'index': 'y'}, 'className'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_preferencias_eixos(
        titulo_texto, titulo_fonte, titulo_espacamento,
        x_texto, x_fonte, x_espacamento,
        y_texto, y_fonte, y_espacamento,
        x_min, x_max, y_min, y_max,
        classe_cadeado_x, classe_cadeado_y,
        aba_ativa,
    ):
        """
        Grava TODA a seção 'Eixos' (título do gráfico, rótulo+fonte+
        espaçamento de cada eixo, limites min/max, estado do cadeado)
        em 'arquivo.preferencias' (PreferenciasTexto/
        PreferenciasLimiteEixo — src/core/arquivo.py) e redesenha o
        gráfico — mesmo padrão de aplicar_preferencias_ticks/outros:
        um callback só cobre a seção inteira em vez de um por campo,
        porque toda edição aqui acaba caindo no mesmo redesenho de
        figura de qualquer forma.

        Os 6 campos de fonte/espaçamento são _stepper (renderizadores.
        py) — o valor de verdade não fica no id simples que aparece no
        rótulo (ex: 'edicao-eixo-titulo-fonte'), e sim num dcc.Input
        interno com id em padrão {'type': 'stepper-valor', 'index':
        'edicao-eixo-titulo-fonte'} (MATCH em alternar_stepper) — usar
        o id simples aqui apontaria pra um componente que não existe
        no layout, e o Dash recusa rodar o callback (erro só visível
        no console do navegador, silencioso pro usuário).

        Os valores de min/max chegam como None quando o campo está
        vazio (inclusive logo depois de um clique em 'Autoscale', que
        limpa os dois — ver autoscale_limite abaixo) — None é
        justamente o que _aplicar_preferencias_grafico (plotter.py)
        interpreta como "deixa o Plotly decidir o range sozinho".
        """
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        if not arquivo.grafico_gerado:
            raise PreventUpdate

        prefs = arquivo.preferencias

        prefs.titulo.texto = titulo_texto or ''
        prefs.titulo.fonte = titulo_fonte if titulo_fonte is not None else prefs.titulo.fonte
        prefs.titulo.espacamento = titulo_espacamento if titulo_espacamento is not None else prefs.titulo.espacamento

        prefs.titulo_eixo_x.texto = x_texto or ''
        prefs.titulo_eixo_x.fonte = x_fonte if x_fonte is not None else prefs.titulo_eixo_x.fonte
        prefs.titulo_eixo_x.espacamento = x_espacamento if x_espacamento is not None else prefs.titulo_eixo_x.espacamento

        prefs.titulo_eixo_y.texto = y_texto or ''
        prefs.titulo_eixo_y.fonte = y_fonte if y_fonte is not None else prefs.titulo_eixo_y.fonte
        prefs.titulo_eixo_y.espacamento = y_espacamento if y_espacamento is not None else prefs.titulo_eixo_y.espacamento

        prefs.limite_x.minimo = x_min
        prefs.limite_x.maximo = x_max
        prefs.limite_x.travado = 'travado' in (classe_cadeado_x or '').split()

        prefs.limite_y.minimo = y_min
        prefs.limite_y.maximo = y_max
        prefs.limite_y.travado = 'travado' in (classe_cadeado_y or '').split()

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        return renderizar_grafico_com_fechar(fig)

    def _registrar_autoscale(letra_eixo):
        """
        Fábrica do callback de 'Autoscale' (🔄) de UM eixo — gerada em
        função, não um único callback com MATCH, porque o alvo (campos
        'edicao-eixo-x/y-limite-min/max', ids simples, não em padrão
        {'type':...}) já é fixo por eixo há mais tempo que os padrões
        MATCH mais recentes do painel; só duas instâncias (x/y) não
        justificam converter esses ids agora.

        Limpa os dois campos (volta a None — 'sem limite definido',
        ver aplicar_preferencias_eixos acima) e destrava o cadeado: não
        faz sentido continuar 'travado' num intervalo que acabou de
        ser apagado.
        """
        @app.callback(
            Output(f'edicao-eixo-{letra_eixo}-limite-min', 'value'),
            Output(f'edicao-eixo-{letra_eixo}-limite-max', 'value'),
            Output({'type': 'limite-cadeado', 'index': letra_eixo}, 'children', allow_duplicate=True),
            Output({'type': 'limite-cadeado', 'index': letra_eixo}, 'className', allow_duplicate=True),
            Input({'type': 'limite-autoscale', 'index': letra_eixo}, 'n_clicks'),
            prevent_initial_call=True,
        )
        def autoscale_limite(n_clicks):
            if not n_clicks:
                raise PreventUpdate
            return None, None, '🔓', 'painel-edicao-limite-btn'

        return autoscale_limite

    _registrar_autoscale('x')
    _registrar_autoscale('y')

    def _prefs_ticks_eixo(arquivo, eixo):
        """
        Devolve o PreferenciasTicksEixo (ver src/core/arquivo.py) que
        representa 'eixo' ('x'/'y'/'both') pra fins de LEITURA (o que
        mostrar nos sliders). 'both' não tem um objeto próprio — mostra
        o de X (ver justificativa em renderizar_painel_edicao,
        renderizadores.py: X e Y só divergem se o usuário editar cada
        um separadamente; ao editar com 'Both' selecionado os dois são
        igualados de novo, ver _prefs_ticks_alvos abaixo).
        """
        return arquivo.preferencias.ticks_x if eixo != 'y' else arquivo.preferencias.ticks_y

    def _prefs_ticks_alvos(arquivo, eixo):
        """
        Devolve a LISTA de PreferenciasTicksEixo que uma EDIÇÃO deve
        gravar: só X, só Y, ou os dois juntos (mesmo valor nos dois)
        quando 'Eixo: Both' está selecionado — é assim que 'Both'
        funciona como atalho pra editar os dois eixos de uma vez, sem
        precisar de um terceiro conjunto de preferências.
        """
        prefs = arquivo.preferencias
        if eixo == 'x':
            return [prefs.ticks_x]
        if eixo == 'y':
            return [prefs.ticks_y]
        return [prefs.ticks_x, prefs.ticks_y]

    @app.callback(
        Output({'type': 'toggle', 'index': MATCH}, 'className'),
        Input({'type': 'toggle', 'index': MATCH}, 'n_clicks'),
        State({'type': 'toggle', 'index': MATCH}, 'className'),
        prevent_initial_call=True,
    )
    def alternar_toggle(n_clicks, classe_atual):
        """
        Callback ÚNICO e genérico pra QUALQUER interruptor on/off do
        painel de edição (ver _toggle em renderizadores.py) — hoje:
        'Both sides' e 'Division/Subdivision' (seção 'Ticks') e 'Grid'
        (seção 'Outros'). MATCH liga cada instância a UM toggle
        específico (mesmo 'index'), no mesmo espírito de
        alternar_secao_edicao/alternar_cadeado_limite logo acima —
        nenhum callback novo precisa ser escrito pra um interruptor
        futuro, só usar _toggle() com um 'index' próprio.

        Só ADICIONA/REMOVE a classe 'ativo' na lista de classes
        existente (em vez de devolver uma string fixa) — mais robusto
        a qualquer classe extra que _toggle venha a pendurar no botão
        no futuro (hoje nenhum toggle usa isso, mas o suporte continua
        aqui pronto).
        """
        if not n_clicks:
            raise PreventUpdate
        classes = (classe_atual or 'painel-edicao-toggle').split()
        if 'ativo' in classes:
            classes.remove('ativo')
        else:
            classes.append('ativo')
        return ' '.join(classes)

    @app.callback(
        Output('edicao-ticks-numero', 'value'),
        Output('edicao-ticks-largura', 'value'),
        Output('edicao-ticks-comprimento', 'value'),
        Output('edicao-ticks-sliders-wrapper', 'className'),
        # allow_duplicate=True: este Output também é atingido pelo
        # callback genérico alternar_toggle (Output({'type':'toggle',
        # 'index': MATCH}, 'className')) — sem isso o Dash recusa
        # registrar os dois porque, em tese, os dois PODERIAM escrever
        # no mesmo componente ao mesmo tempo. Na prática nunca colidem
        # de verdade: alternar_toggle só dispara em resposta a um
        # clique no PRÓPRIO toggle 'Both sides' (n_clicks), enquanto
        # este aqui só dispara em resposta ao dropdown 'Eixo' ou ao
        # toggle 'Division/Subdivision' — nunca os dois no mesmo
        # clique.
        Output({'type': 'toggle', 'index': 'ticks-both-sides'}, 'className', allow_duplicate=True),
        Output('edicao-ticks-fonte-labels', 'value'),
        Output({'type': 'toggle', 'index': 'ticks-direcao'}, 'className', allow_duplicate=True),
        Output('edicao-ticks-fonte-labels-wrapper', 'className'),
        Input('edicao-ticks-eixo', 'value'),
        Input({'type': 'toggle', 'index': 'ticks-subdivisao'}, 'className'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_campos_ticks(eixo, classe_modo, aba_ativa):
        """
        Repopula os controles de 'Ticks' sempre que muda QUAL conjunto
        de valores deve aparecer — seja porque o usuário trocou o
        dropdown 'Eixo' (X/Y/Both), seja porque ligou/desligou o toggle
        'Division/Subdivision'. Os 4 (eixo × modo) formam a matriz de
        onde ler: 'estado.arquivos[aba_ativa].preferencias.ticks_x/
        ticks_y . divisoes/subdivisoes' (ver PreferenciasTicksEixo em
        src/core/arquivo.py) — é essa leitura direta de 'estado' que
        corrige o bug relatado (trocar de X pra Y não deve herdar o
        último valor mexido, e sim o que está REALMENTE aplicado
        naquele eixo específico).

        TAMBÉM sincroniza o toggle 'Both sides' (reflete
        'both_sides' do eixo que passou a estar selecionado) e a
        classe do wrapper dos sliders (cor roxo/verde conforme o modo
        — ver .painel-edicao-ticks-sliders.modo-subdivisao em
        edit_menu.css). 'Label font' e o toggle 'Outward/Inward' só
        reagem à troca de EIXO (não têm um conjunto separado por modo
        — ver comentário em conteudo_ticks, renderizadores.py), então
        ficam de fora do 'if modo_subdivisao' que decide os 3 sliders
        — MAS a VISIBILIDADE do slider 'Label font' (não o valor)
        ainda depende do modo: escondido em 'Subdivision' (marcas
        secundárias não têm rótulo/número do lado, então o controle
        não teria efeito visível nesse modo — ver '.painel-edicao-
        oculto' em edit_menu.css).
        """
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        prefs_eixo = _prefs_ticks_eixo(arquivo, eixo)
        modo_subdivisao = 'ativo' in (classe_modo or '').split()
        conjunto = prefs_eixo.subdivisoes if modo_subdivisao else prefs_eixo.divisoes
        classe_wrapper = 'painel-edicao-ticks-sliders' + (' modo-subdivisao' if modo_subdivisao else '')
        # 'painel-edicao-segmentado' (era 'painel-edicao-toggle') —
        # BUG corrigido aqui: esta função reescreve a className de
        # 'Direction'/'Side' toda vez que o Eixo OU o toggle 'Major/
        # Minor' mudam (pra sincronizar o 'ativo' com o valor salvo
        # daquele eixo/modo) — mas ainda usava o nome de classe
        # ANTIGO do interruptor pequeno (pré-rework), de antes de
        # 'Direction'/'Side' virarem o toggle segmentado (ver
        # '_linha_toggle_dupla', renderizadores.py). Resultado: trocar
        # de Major pra Minor (ou de Eixo) apagava o estilo/cor desses
        # dois toggles, deixando só o texto cru sem pílula nenhuma —
        # a classe 'painel-edicao-toggle' não tem NADA a ver com
        # '.painel-edicao-segmentado'/'.painel-edicao-segmentado-
        # opcao' (CSS completamente diferente), então nenhuma regra
        # de cor/formato batia mais.
        classe_both_sides = 'painel-edicao-segmentado' + (' ativo' if prefs_eixo.both_sides else '')
        classe_direcao = 'painel-edicao-segmentado' + (' ativo' if prefs_eixo.direcao == 'inside' else '')
        classe_fonte_labels_wrapper = 'painel-edicao-oculto' if modo_subdivisao else ''

        return (
            conjunto.get('numero', 2), conjunto.get('largura', 1), conjunto.get('comprimento', 3),
            classe_wrapper, classe_both_sides,
            prefs_eixo.fonte_labels, classe_direcao,
            classe_fonte_labels_wrapper,
        )

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Input('edicao-ticks-numero', 'value'),
        Input('edicao-ticks-largura', 'value'),
        Input('edicao-ticks-comprimento', 'value'),
        Input({'type': 'toggle', 'index': 'ticks-both-sides'}, 'className'),
        Input('edicao-ticks-fonte-labels', 'value'),
        Input({'type': 'toggle', 'index': 'ticks-direcao'}, 'className'),
        State('edicao-ticks-eixo', 'value'),
        State({'type': 'toggle', 'index': 'ticks-subdivisao'}, 'className'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_preferencias_ticks(
        numero, largura, comprimento, classe_both_sides, fonte_labels, classe_direcao,
        eixo, classe_modo, aba_ativa,
    ):
        """
        Grava os 3 sliders + 'Both sides' + 'Label font' + a direção
        (Outward/Inward) como preferência PERMANENTE do(s) eixo(s)
        alvo (ver _prefs_ticks_alvos: X, Y, ou os dois se 'Eixo: Both'
        estiver selecionado) e redesenha o gráfico na hora (ver
        _aplicar_preferencias_grafico em plotter.py) — mesmo espírito
        de aplicar_preferencias_curva, só que pro LAYOUT em vez de uma
        curva.

        Grava no conjunto 'divisoes' ou 'subdivisoes' conforme o
        estado ATUAL do toggle 'Division/Subdivision' (lido como
        State, não Input — este callback não deve disparar sozinho só
        porque o modo mudou; quem faz os sliders REFLETIREM a troca de
        modo é sincronizar_campos_ticks acima; este aqui só reage a
        edição de verdade nos sliders/both-sides). 'Label font' e a
        direção NÃO dependem do modo (são do eixo inteiro, não de
        'divisoes' vs 'subdivisoes' — ver comentário em
        conteudo_ticks, renderizadores.py), por isso são gravados fora
        do 'if modo_subdivisao'.

        Também dispara (gravação idempotente, mesmo valor) logo depois
        de sincronizar_campos_ticks trocar os sliders de eixo/modo —
        mesma classe de gatilho 'fantasma' comentado em _clique_real;
        sem efeito real no gráfico além de redesenhar com os mesmos
        números.
        """
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        if not arquivo.grafico_gerado:
            raise PreventUpdate

        modo_subdivisao = 'ativo' in (classe_modo or '').split()
        chave = 'subdivisoes' if modo_subdivisao else 'divisoes'
        both_sides = 'ativo' in (classe_both_sides or '').split()
        direcao = 'inside' if 'ativo' in (classe_direcao or '').split() else 'outside'
        conjunto = {'numero': numero, 'largura': largura, 'comprimento': comprimento}

        for prefs_eixo in _prefs_ticks_alvos(arquivo, eixo):
            setattr(prefs_eixo, chave, conjunto)
            prefs_eixo.both_sides = both_sides
            prefs_eixo.fonte_labels = fonte_labels
            prefs_eixo.direcao = direcao

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        return renderizar_grafico_com_fechar(fig)

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Input({'type': 'toggle', 'index': 'outros-grid'}, 'className'),
        Input({'type': 'cor-store', 'index': 'fundo'}, 'data'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_preferencias_outros(classe_grid, cor_fundo, aba_ativa):
        """
        Grava 'Grid' e a cor de fundo (seção 'Outros') como preferência
        PERMANENTE do gráfico inteiro (ver PreferenciasGrafico.grid/
        cor_fundo em src/core/arquivo.py) e redesenha na hora — mesmo
        padrão de aplicar_preferencias_ticks acima. Diferente de
        'Ticks', não tem um 'eixo alvo': 'Grid' liga/desliga nos DOIS
        eixos junto (o painel só tem um interruptor pros dois) e a cor
        de fundo é do gráfico inteiro, não de um eixo específico.
        """
        if not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        if not arquivo.grafico_gerado:
            raise PreventUpdate

        arquivo.preferencias.grid = 'ativo' in (classe_grid or '').split()
        arquivo.preferencias.cor_fundo = cor_fundo

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        return renderizar_grafico_com_fechar(fig)
