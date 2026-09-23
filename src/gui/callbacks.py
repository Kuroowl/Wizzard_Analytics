from dash import Input, Output, State, ctx, ALL, MATCH, no_update
from dash.exceptions import PreventUpdate

from src.core.operations.calculadora import avaliar_expressao_calculadora, calc_criar_desabilitado
from src.core.plotting.plotter import (
    construir_figura_serie_temporal, colunas_plotadas, cor_da_coluna,
)
from src.core.rotulos import sanitizar_rotulo_para_nome_coluna
from src.gui.renderizadores import (
    truncar_nome_arquivo, renderizar_colunas_da_aba_ativa,
    renderizar_selecao_eixos, renderizar_grafico_com_fechar,
    renderizar_painel_direito_padrao, renderizar_painel_edicao,
    renderizar_calculadora_barra, renderizar_area_calculadora_completa, renderizar_calculadora_botoes, _hex_para_rgb,
)
from src.gui.feedback import Feedback, saida_feedback
from src.gui.rodape import registrar_callbacks_rodape
from src.callbacks._comum import (
    _processar_cliques_padrao, _estados_toolbar, _classe_painel_direito,
)
from src.callbacks.abas import registrar_callbacks_abas
from src.callbacks.arquivos import registrar_callbacks_arquivos
from src.callbacks.canais import registrar_callbacks_canais
from src.callbacks.corte import registrar_callbacks_corte
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
    registrar_callbacks_canais(app, estado)
    registrar_callbacks_corte(app, estado)
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
