import json

from dash import Input, Output, State, ctx, ALL, MATCH, no_update
from dash.exceptions import PreventUpdate

from src.core.operations.sampling import aparar_dados, excluir_dados
from src.core.operations.calculadora import avaliar_expressao_calculadora, aplicar_operacao_rapida
from src.core.plotting.plotter import (
    construir_figura_serie_temporal, resolver_eixo_x, colunas_plotadas, cor_da_coluna,
    aplicar_guias_corte,
)
from src.core.rotulos import sanitizar_rotulo_para_nome_coluna
from src.gui.renderizadores import (
    truncar_nome_arquivo, renderizar_abas_estilo_chrome, renderizar_colunas_da_aba_ativa,
    renderizar_area_grafico, renderizar_grafico_com_fechar,
    renderizar_info_rodape, renderizar_badge_alerta, classe_badge_alerta, renderizar_popup_alerta,
    renderizar_painel_direito_padrao, renderizar_painel_edicao,
    renderizar_calculadora_barra, renderizar_calculadora_botoes, _hex_para_rgb,
)
from src.utils.helpers import carregar_dados_de_upload


# ============================================================================
# ⚠️ TEMPORÁRIO — DEBUG: desativa o filtro anti-"clique fantasma"
# (_processar_cliques_padrao, logo abaixo) a pedido explícito, pra
# isolar se ELE é a causa de "não consigo clicar em nenhuma coluna"
# reportado depois da reestruturação da calculadora. Com False, os
# callbacks que usam esse filtro (gerenciar_abas, gerenciar_selecao_
# canais, gerenciar_edicao_canal, registrar_token_calculadora,
# aplicar_operacao_rapida_calculadora) voltam a aceitar QUALQUER
# disparo como clique de verdade — inclusive os fantasmas de
# remontagem que o filtro existe pra bloquear (ver docstring completa
# de _processar_cliques_padrao). Voltar pra True depois de terminado o
# teste.
# ============================================================================
GUARD_CLIQUE_FANTASMA_ATIVO = False


def _clique_real(ctx_triggered):
    """
    Protege contra o disparo 'fantasma' que callbacks de padrão (ALL) do
    Dash costumam dar assim que componentes novos são criados dinamicamente
    (ex: uma aba nova, uma linha de canal nova), mesmo sem clique nenhum do
    usuário.

    Antes essa checagem também exigia `value not in (None, 0)`, mas para
    arquivos com nomes de coluna "atípicos" (ex.: 'N#', 'FW-A') o valor
    relatado por `ctx.triggered` no primeiro clique real de uma linha
    recém-renderizada nem sempre batia com o esperado, fazendo cliques de
    verdade serem descartados como fantasma. Bastar existir um gatilho já
    é suficiente aqui, porque cada callback que usa isso confere também o
    `type` do gatilho (`ctx.triggered_id.get('type')`) antes de agir.

    LIMITAÇÃO CONHECIDA: isto NÃO filtra o caso em que a LISTA INTEIRA de
    componentes casados é reconstruída do zero por OUTRO callback (ex:
    upload de arquivo reconstrói 'lista-canais-aba', trocar de aba
    reconstrói 'container-abas-chrome') — nesse caso 'ctx.triggered' vem
    não-vazio mesmo sem clique nenhum, porque os componentes recém-criados
    entram no padrão coringa com o valor inicial do Python (n_clicks=0).
    Pros callbacks expostos a essa reconstrução por TERCEIROS (não só por
    si mesmos) — gerenciar_abas, gerenciar_selecao_canais,
    alternar_edicao_canal — use '_processar_cliques_padrao' abaixo, que
    resolve isso rastreando o ÚLTIMO valor visto por componente.
    """
    return bool(ctx_triggered)


def _processar_cliques_padrao(grupos_inputs_list, nclicks_anteriores):
    """
    Alternativa a '_clique_real' pros callbacks de padrão coringa
    ({'type': ..., 'chave': ALL}) cuja LISTA de componentes casados pode
    ser reconstruída do zero por OUTRO callback (não só por si mesmo) —
    ex: 'gerenciar_abas' (a lista de abas é reconstruída ao fazer
    upload de um arquivo novo) e 'gerenciar_selecao_canais'/
    'alternar_edicao_canal' (a lista de canais é reconstruída ao gerar/
    fechar o gráfico, trocar de aba, ou marcar/desmarcar OUTRO canal).

    Nesses casos, um simples 'bool(ctx.triggered)' (_clique_real) NÃO
    basta: sempre que a lista-mãe é reconstruída, TODOS os botões dela
    nascem de novo no Python com 'n_clicks=0' (são componentes NOVOS,
    não os mesmos de antes, mesmo com o MESMO id) — e o Dash trata esse
    reaparecimento de um id já observado por um Input de padrão coringa
    como um disparo válido do callback, item que aparece em
    'ctx.triggered' exatamente como um clique de verdade apareceria.
    Foi isso que causava o bug relatado: sempre que a lista de canais
    era reconstruída por OUTRO motivo (upload, gerar/fechar gráfico,
    marcar canal), 'gerenciar_selecao_canais' disparava sozinho tratando
    o primeiro botão da lista como se tivesse sido clicado de verdade.

    A única forma confiável de diferenciar os dois casos é comparar o
    valor ATUAL de CADA componente casado contra o ÚLTIMO valor já
    processado (guardado num dcc.Store, ver 'nclicks-padrao-store' em
    layout.py) — só conta como clique de VERDADE quando o valor sobe
    (0->1, 1->2...). Numa reconstrução "fantasma", o valor volta pra 0
    (o padrão do Python), que nunca é MAIOR que um valor já visto antes
    (seja 0 — nunca clicado — ou qualquer coisa maior — já clicado
    alguma vez), então nunca dispara ação nenhuma; só um clique físico
    de verdade faz o navegador reportar um valor MAIOR que o anterior.

    'grupos_inputs_list' são as entradas de 'ctx.inputs_list'
    correspondentes aos Inputs de padrão coringa deste callback (cada
    uma é uma LISTA de {'id', 'property', 'value'}, um item por
    componente casado — é assim que o Dash formata pattern-matching
    Inputs). 'nclicks_anteriores' é o 'data' atual do Store (dict, ou
    None/vazio na primeira chamada).

    Devolve (gatilho_id, novo_mapa):
      - gatilho_id: o id (dict) do componente com clique de VERDADE
        nesta chamada, ou None se nada disparou de verdade (só
        fantasma) — quem chama deve tratar None como PreventUpdate.
      - novo_mapa: o dict atualizado com o valor ATUAL de cada
        componente casado — sempre devolver isso como o novo 'data' do
        Store, mesmo quando gatilho_id vier None, senão a próxima
        reconstrução "esquece" a linha de base e volta a comparar
        contra um valor desatualizado.

    ------------------------------------------------------------------
    ⚠️ DESATIVADO TEMPORARIAMENTE (GUARD_CLIQUE_FANTASMA_ATIVO = False,
    logo no topo deste arquivo) — a pedido explícito, pra isolar se
    ESTE filtro é a causa de "não consigo clicar em nenhuma coluna"
    reportado depois da reestruturação da calculadora. Enquanto
    desativado, esta função volta a se comportar como a antiga
    '_clique_real' (aceita QUALQUER disparo como clique de verdade,
    inclusive fantasmas de remontagem) — ou seja, o bug ANTIGO que
    _processar_cliques_padrao existe pra resolver PODE voltar a
    aparecer (ex: o primeiro canal da lista marcando sozinho ao gerar/
    fechar gráfico). Isso é esperado enquanto o teste estiver rodando.
    Depois de confirmar (ou descartar) que este filtro é o culpado,
    voltar 'GUARD_CLIQUE_FANTASMA_ATIVO' pra True.
    ------------------------------------------------------------------
    """
    nclicks_anteriores = nclicks_anteriores or {}
    novo_mapa = dict(nclicks_anteriores)
    gatilho_id = None

    if not GUARD_CLIQUE_FANTASMA_ATIVO:
        # Bypass temporário: qualquer disparo conta como clique de
        # verdade (não compara contra o valor anterior) — ainda
        # atualiza 'novo_mapa' normalmente, pra não perder o rastreio
        # caso o guard seja religado no meio de uma sessão.
        for grupo in grupos_inputs_list:
            itens = grupo if isinstance(grupo, list) else [grupo]
            for item in itens:
                id_item = item.get('id')
                if not isinstance(id_item, dict):
                    continue
                chave = json.dumps(id_item, sort_keys=True)
                novo_mapa[chave] = item.get('value') or 0
        if ctx.triggered_id and isinstance(ctx.triggered_id, dict):
            gatilho_id = ctx.triggered_id
        return gatilho_id, novo_mapa

    for grupo in grupos_inputs_list:
        itens = grupo if isinstance(grupo, list) else [grupo]
        for item in itens:
            id_item = item.get('id')
            if not isinstance(id_item, dict):
                continue
            chave = json.dumps(id_item, sort_keys=True)
            valor_novo = item.get('value') or 0
            valor_antigo = novo_mapa.get(chave, 0)
            if valor_novo > valor_antigo:
                gatilho_id = id_item
            novo_mapa[chave] = valor_novo

    return gatilho_id, novo_mapa


def _estados_toolbar(estado, aba_ativa):
    """
    Calcula os 3 critérios independentes que decidem o 'disabled' dos
    botões da toolbar. Existe pra esses 3 booleans nunca ficarem
    dessincronizados entre callbacks diferentes (upload, trocar/fechar
    aba, gerar gráfico, fechar gráfico) — antes, um único
    'botoes_dependentes' era aplicado aos 5 botões de uma vez, o que
    misturava dois critérios diferentes (ver comentário abaixo) e
    deixava 'nova-amostra'/'exportar-dados' presos desabilitados depois
    de fechar o gráfico, mesmo com o arquivo ainda carregado.

    Retorna (sem_arquivo, sem_2_arquivos, sem_grafico_da_aba):
      - sem_arquivo: nenhum arquivo carregado -> usado por
        'nova-analise', 'nova-amostra' e 'exportar-dados' (dependem só
        de existir arquivo, não de gráfico).
      - sem_2_arquivos: menos de 2 arquivos carregados -> usado só por
        'fundir-arquivos'.
      - sem_grafico_da_aba: a aba ATIVA especificamente não tem gráfico
        gerado (nunca "algum arquivo tem gráfico") -> usado por
        'aparar-dados', 'excluir-dados' e 'exportar-grafico'.
    """
    sem_arquivo = len(estado.arquivos) == 0
    sem_2_arquivos = len(estado.arquivos) < 2
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    sem_grafico_da_aba = not (arquivo and arquivo.grafico_gerado)
    return sem_arquivo, sem_2_arquivos, sem_grafico_da_aba


def _classe_painel_direito(ativo=False, selecionando=False):
    """
    Classe do painel de edição: combina os DOIS estados independentes
    que ele pode ter ao mesmo tempo:
      - 'ativa' -> o formulário de edição está aberto (ligado só por
        'Iniciar edição'/'✕', ver abrir_painel_edicao/fechar_edicao_curva).
      - 'area-inativa-selecao' -> borrado/bloqueado durante uma seleção
        de corte em andamento ('Aparar dados'/'Excluir dados').

    Os dois toggles são INDEPENDENTES: uma seleção de corte pode
    começar com o painel de edição aberto OU fechado, e nos dois casos
    ela precisa voltar EXATAMENTE pro mesmo estado de antes ao
    terminar (confirmar ou cancelar a seleção) — nunca forçando
    'ativo=False' de propósito. Antes, iniciar_selecao_corte e
    _restaurar_apos_selecao (mais abaixo) escreviam a className do
    painel na mão ('painel-direito area-inativa-selecao' /
    'painel-direito'), descartando a classe 'ativa' sempre que ela
    estivesse presente — por isso o botão 'Iniciar edição' reaparecia
    (some só via '.painel-direito.ativa .botao-iniciar-edicao') e o
    título 'Opções do gráfico' + as guias recolhíveis, que continuavam
    no DOM (painel-direito-conteudo não é reconstruído nesse fluxo),
    voltavam a ficar centralizados (a regra de esticar/alinhar à
    esquerda também só vale sob '.ativa') assim que o usuário
    completava a seleção de 'Aparar dados' com o painel de edição
    aberto.
    """
    classes = ['painel-direito']
    if ativo:
        classes.append('ativa')
    if selecionando:
        classes.append('area-inativa-selecao')
    return ' '.join(classes)


def _valores_rodape(estado, aba_ativa):
    """
    Agrupa os 4 valores que qualquer callback que mexe no rodapé precisa
    devolver, sempre na mesma ordem: (info, badge_texto, badge_classe,
    popup_children). Existe só pra não repetir as mesmas 4 chamadas em
    cada callback abaixo.
    """
    return (
        renderizar_info_rodape(estado, aba_ativa),
        renderizar_badge_alerta(estado, aba_ativa),
        classe_badge_alerta(estado, aba_ativa),
        renderizar_popup_alerta(estado, aba_ativa),
    )


def registrar_callbacks(app, estado):
    """
    Registra todos os callbacks do app. Recebe 'app' (pra decorar com
    @app.callback) e 'estado' (o EstadoApp global, compartilhado com
    layout.py) — este módulo não decide qual app instanciar nem qual
    estado usar, só liga os dois.
    """

    @app.callback(
        Output('aba-ativa-store', 'data'),
        Output('rodape-status', 'children'),
        Output('nova-analise', 'disabled'),
        Output('fundir-arquivos', 'disabled'),
        Output('nova-amostra', 'disabled'),
        Output('exportar-dados', 'disabled'),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-info-arquivo', 'children'),
        Output('rodape-alerta-badge', 'children'),
        Output('rodape-alerta-badge', 'className'),
        Output('rodape-alerta-popup', 'children'),
        Output('rodape-mensagem-seguinte', 'data'),
        Output('rodape-timer-mensagem', 'disabled'),
        Output('rodape-timer-mensagem', 'n_intervals'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo, aba_atual):
        if conteudo is None:
            raise PreventUpdate

        if nome_arquivo in estado.arquivos:
            # Arquivo já aberto: mensagem PERSISTENTE — cancela qualquer
            # timer pendente (senão uma expiração antiga poderia
            # sobrescrever essa mensagem daqui a pouco). Nenhuma contagem
            # de arquivo mudou, então os critérios de habilitação ficam
            # como já estavam.
            sem_arquivo, sem_2_arquivos, _ = _estados_toolbar(estado, nome_arquivo)
            mensagem = f'🧙‍♂️: " O arquivo \'{nome_arquivo}\' já foi aberto! "'
            return (nome_arquivo, mensagem,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    no_update,
                    *_valores_rodape(estado, nome_arquivo),
                    no_update, True, no_update)
        try:
            df, avisos, info = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df, avisos, info)

            # FORÇA a re-renderização da área central para desenhar a grade azul
            area_grafico = renderizar_area_grafico(estado)

            # Mensagem TEMPORÁRIA: aparece, some sozinha em ~3.5s e dá lugar
            # à próxima instrução ("Escolha uma opção de gráfico...") — ver
            # 'rodape-timer-mensagem' / expirar_mensagem_temporaria() abaixo.
            mensagem = f'🧙‍♂️: " Arquivo \'{nome_arquivo}\' carregado com sucesso! "'
            mensagem_seguinte = '🧙‍♂️: " Escolha uma opção de gráfico... "'

            # O arquivo recém-carregado ainda não tem gráfico gerado, então
            # 'aparar-dados'/'excluir-dados'/'exportar-grafico' continuam
            # desabilitados (não fazem parte deste callback — ver
            # gerar_grafico_serie_temporal). Só o que depende de "existe
            # arquivo" muda aqui: nova-analise, nova-amostra e exportar-dados.
            sem_arquivo, sem_2_arquivos, _ = _estados_toolbar(estado, nome_arquivo)

            return (nome_arquivo, mensagem,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    area_grafico,
                    *_valores_rodape(estado, nome_arquivo),
                    mensagem_seguinte, False, 0)
        except Exception as e:
            sem_arquivo, sem_2_arquivos, _ = _estados_toolbar(estado, aba_atual)
            mensagem = f'🧙‍♂️: " Erro ao abrir arquivo: {str(e)} "'
            return (aba_atual, mensagem,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    no_update,
                    *_valores_rodape(estado, aba_atual),
                    no_update, True, no_update)

    @app.callback(
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input('rodape-timer-mensagem', 'n_intervals'),
        State('rodape-mensagem-seguinte', 'data'),
        prevent_initial_call=True,
    )
    def expirar_mensagem_temporaria(n_intervals, mensagem_seguinte):
        """
        Dispara quando uma mensagem temporária do mago (a inicial, ou o
        'Arquivo carregado com sucesso!') termina seu tempo de exibição.
        Troca o texto do rodapé pelo que ficou guardado em
        'rodape-mensagem-seguinte' (pode ser '' — nesse caso a mensagem
        simplesmente some) e desarma o timer de novo.
        """
        if not n_intervals:
            raise PreventUpdate
        return (mensagem_seguinte or ''), True
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
    # _processar_cliques_padrao, topo deste arquivo), então o guard
    # simples de 'not n_clicks' já basta aqui.
    # ------------------------------------------------------------------

    @app.callback(
        Output('modo-nova-analise-store', 'data'),
        Output('nova-analise', 'className'),
        Output('centro-grafico', 'className'),
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
        # 'centro-grafico' só precisa da classe 'calc-ativa' pra
        # empurrar '#container-grafico' pra baixo (ver '.centro.calc-
        # ativa .area-grafico-container' em central_menu.css) — a
        # VISIBILIDADE da barra em si (logo abaixo) é decidida pelo
        # 'style' inline dela mesma, não por essa classe do ancestral
        # (mesmo padrão já testado/funcionando de
        # '#toolbar-confirmacao-corte', em vez de depender de uma
        # classe cascateando por CSS até um filho).
        classe_centro = 'centro' + (' calc-ativa' if novo_ativo else '')
        estilo_area_barra = {'display': 'flex'} if novo_ativo else {'display': 'none'}
        estilo_area_edicao = {'display': 'flex'} if novo_ativo else {'display': 'none'}

        # A calculadora só precisa existir de verdade (com os botões de
        # coluna do arquivo CERTO) quando o modo está LIGANDO — ao
        # desligar, 'no_update' preserva o que já estava montado (o
        # 'style' acima já cuida de esconder) e a expressão em
        # andamento ('calc-expressao-store') fica intocada, pra
        # continuar de onde parou se o usuário ligar de novo.
        conteudo_barra = no_update
        conteudo_botoes = no_update
        if novo_ativo:
            conteudo_barra = renderizar_calculadora_barra(estado, aba_ativa, tokens_atuais)
            conteudo_botoes = renderizar_calculadora_botoes(estado, aba_ativa)

        return (novo_ativo, classe_botao, classe_centro, estilo_area_barra, estilo_area_edicao,
                conteudo_barra, conteudo_botoes)

    # ------------------------------------------------------------------
    # Calculadora — 5 callbacks:
    #   1) registrar_token_calculadora: clique em token de OPERADOR/
    #      FUNÇÃO/COLUNA (todos usam o MESMO padrão de id, ver
    #      _botao_token_calculadora em renderizadores.py) anexa esse
    #      token na expressão. Só atualiza a BARRA (não os botões — que
    #      não mudam com a expressão, ver renderizar_calculadora_botoes)
    #      — diferente da versão anterior, que reconstruía a
    #      calculadora inteira a cada clique.
    #   2) aplicar_operacao_rapida_calculadora: clique em Derivada/
    #      Integral/Média/Máximo/Mínimo — NÃO anexa token, dispara um
    #      cálculo de verdade (ver aplicar_operacao_rapida, src/core/
    #      operations/calculadora.py) sobre as colunas já referenciadas
    #      na expressão, guardando o resultado em
    #      'calc-resultado-pendente-store' até o usuário confirmar com
    #      'Criar'.
    #   3) apagar_ultimo_token_calculadora: '⌫' remove o ÚLTIMO token,
    #      ou descarta um resultado de operação rápida pendente
    #      (voltando a poder editar a expressão token a token).
    #   4) limpar_expressao_calculadora: 'Limpar' zera tudo.
    #   5) criar_canal_calculado_calculadora: 'Criar' — usa o resultado
    #      pendente (se houver) ou avalia a expressão livre, e GRAVA o
    #      resultado como coluna NOVA ou SOBRESCREVENDO uma existente,
    #      conforme o seletor 'calc-tipo-destino' no início da barra.
    # ------------------------------------------------------------------

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('calc-resultado-pendente-store', 'data', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input({'type': 'calc-token', 'display': ALL, 'codigo': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def registrar_token_calculadora(_n_clicks_list, aba_ativa, tokens_atuais, tipo_destino,
                                     coluna_destino, nclicks_anteriores):
        # Mesmo cuidado de gerenciar_selecao_canais/gerenciar_abas: os
        # botões de token são padrão coringa, e a barra É reconstruída
        # por outro callback (alternar_modo_nova_analise, ao ligar, e
        # sincronizar_interface_por_aba, ao trocar de aba) — sem
        # comparar contra o último valor visto, uma reconstrução alheia
        # adicionaria um token sozinho, sem clique nenhum do usuário
        # (ver _processar_cliques_padrao, topo deste arquivo).
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate

        novo_token = {'display': gatilho_id.get('display'), 'codigo': gatilho_id.get('codigo')}
        novos_tokens = (tokens_atuais or []) + [novo_token]

        # Continuar montando a expressão token a token DESCARTA
        # qualquer resultado de operação rápida pendente — os dois
        # modos (expressão livre / resultado de operação rápida) são
        # mutuamente exclusivos na barra (ver renderizar_calculadora_
        # barra, renderizadores.py, que mostra UM ou OUTRO).
        conteudo = renderizar_calculadora_barra(estado, aba_ativa, novos_tokens, tipo_destino, coluna_destino, None)
        return conteudo, novos_tokens, None, novo_mapa

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-resultado-pendente-store', 'data', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('nclicks-padrao-store', 'data', allow_duplicate=True),
        Input({'type': 'calc-op-rapida', 'operacao': ALL}, 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('nclicks-padrao-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_operacao_rapida_calculadora(_n_clicks_list, aba_ativa, tokens_atuais, tipo_destino,
                                             coluna_destino, nclicks_anteriores):
        gatilho_id, novo_mapa = _processar_cliques_padrao(ctx.inputs_list, nclicks_anteriores)
        if gatilho_id is None:
            raise PreventUpdate

        arquivo = estado.arquivos.get(aba_ativa)
        if not arquivo:
            raise PreventUpdate

        operacao_id = gatilho_id.get('operacao')
        try:
            valores, sugestao_nome, descricao = aplicar_operacao_rapida(operacao_id, arquivo, estado, tokens_atuais)
        except ValueError as e:
            mensagem = f'🧙‍♂️: " Não deu pra calcular: {e} "'
            return no_update, no_update, mensagem, novo_mapa

        resultado_pendente = {'valores': valores, 'sugestao_nome': sugestao_nome, 'descricao': descricao}
        conteudo = renderizar_calculadora_barra(
            estado, aba_ativa, tokens_atuais, tipo_destino, coluna_destino, resultado_pendente)
        return conteudo, resultado_pendente, no_update, novo_mapa

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('calc-resultado-pendente-store', 'data', allow_duplicate=True),
        Input('calc-apagar', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-resultado-pendente-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        prevent_initial_call=True,
    )
    def apagar_ultimo_token_calculadora(n_clicks, aba_ativa, tokens_atuais, resultado_pendente,
                                         tipo_destino, coluna_destino):
        if not n_clicks:
            raise PreventUpdate
        # Um resultado de operação rápida pendente conta como "o último
        # passo dado" — apagar descarta ELE primeiro (volta a poder
        # editar a expressão token a token), só depois passa a remover
        # tokens um a um.
        if resultado_pendente:
            novos_tokens = tokens_atuais or []
            novo_resultado_pendente = None
        elif tokens_atuais:
            novos_tokens = tokens_atuais[:-1]
            novo_resultado_pendente = None
        else:
            raise PreventUpdate

        conteudo = renderizar_calculadora_barra(
            estado, aba_ativa, novos_tokens, tipo_destino, coluna_destino, novo_resultado_pendente)
        return conteudo, novos_tokens, novo_resultado_pendente

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('calc-resultado-pendente-store', 'data', allow_duplicate=True),
        Input('calc-limpar', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        prevent_initial_call=True,
    )
    def limpar_expressao_calculadora(n_clicks, aba_ativa, tipo_destino, coluna_destino):
        if not n_clicks:
            raise PreventUpdate
        conteudo = renderizar_calculadora_barra(estado, aba_ativa, [], tipo_destino, coluna_destino, None)
        return conteudo, [], None

    @app.callback(
        Output('area-modo-nova-analise', 'children', allow_duplicate=True),
        Output('calc-expressao-store', 'data', allow_duplicate=True),
        Output('calc-resultado-pendente-store', 'data', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Input('calc-criar', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        State('calc-expressao-store', 'data'),
        State('calc-resultado-pendente-store', 'data'),
        State('calc-tipo-destino', 'value'),
        State('calc-coluna-destino', 'value'),
        State('calc-nome-input', 'value'),
        prevent_initial_call=True,
    )
    def criar_canal_calculado_calculadora(n_clicks, aba_ativa, tokens_atuais, resultado_pendente,
                                           tipo_destino, coluna_destino, nome_novo_canal):
        if not n_clicks:
            raise PreventUpdate

        arquivo = estado.arquivos.get(aba_ativa)
        if not arquivo:
            raise PreventUpdate

        def _sem_mudanca_de_conteudo(mensagem):
            """Devolve os 6 valores desta callback quando SÓ a mensagem
            do rodapé muda (erro de validação) — a barra/expressão/
            listas continuam exatamente como estavam."""
            return no_update, no_update, no_update, no_update, no_update, mensagem

        # 1) Resultado de uma Operação rápida pendente tem PRIORIDADE
        #    sobre a expressão livre (os dois são mutuamente
        #    exclusivos, ver renderizar_calculadora_barra) — se
        #    existir, usa ele direto, sem reavaliar 'codigo' nenhum.
        if resultado_pendente:
            valores = resultado_pendente['valores']
            formula_ou_descricao = resultado_pendente['descricao']
        else:
            codigo = ''.join(t['codigo'] for t in (tokens_atuais or []))
            try:
                valores = avaliar_expressao_calculadora(codigo, arquivo).tolist()
            except ValueError as e:
                return _sem_mudanca_de_conteudo(f'🧙‍♂️: " Não deu pra criar: {e} "')
            formula_ou_descricao = codigo

        area_grafico = no_update

        if tipo_destino == 'existente':
            # --- Sobrescreve uma coluna JÁ EXISTENTE ---
            if not coluna_destino or coluna_destino not in arquivo.df_editado.columns:
                return _sem_mudanca_de_conteudo('🧙‍♂️: " Escolha qual coluna sobrescrever antes de criar. "')

            arquivo.df_editado[coluna_destino] = valores
            canal = arquivo.canais.get(coluna_destino) or arquivo.registrar_canal(coluna_destino)
            canal.origem = 'calculado'
            canal.formula = formula_ou_descricao
            # AGORA SIM invalida o cache — sobrescrever os DADOS de uma
            # coluna que já existe pode mudar uma curva JÁ desenhada no
            # gráfico (diferente de criar uma coluna nova, que nasce
            # sempre fora da seleção e não afeta nada plotado).
            if arquivo.grafico_gerado:
                arquivo.invalidar_grafico()
                fig = construir_figura_serie_temporal(estado, aba_ativa)
                arquivo.figura = fig
                area_grafico = renderizar_grafico_com_fechar(fig)
            mensagem = f'🧙‍♂️: " Coluna \'{arquivo.rotulo(coluna_destino)}\' recalculada. "'
        else:
            # --- Cria uma coluna NOVA ---
            nome_novo_canal = (nome_novo_canal or '').strip()
            if not nome_novo_canal:
                return _sem_mudanca_de_conteudo('🧙‍♂️: " Dê um nome pra essa análise antes de criar. "')

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
            # SEM invalidar o gráfico aqui de propósito — o canal novo
            # nasce OCULTO da seleção (como qualquer canal recém-
            # registrado), não afeta nenhuma curva já desenhada.
            arquivo.registrar_canal(nome_interno_final, rotulo=nome_novo_canal,
                                     origem='calculado', formula=formula_ou_descricao)
            mensagem = f'🧙‍♂️: " Canal \'{nome_novo_canal}\' criado ({formula_ou_descricao}). "'

        # Limpa a expressão/resultado pendente depois de criar (mesmo
        # espírito de um formulário que reseta após salvar).
        conteudo = renderizar_calculadora_barra(estado, aba_ativa, [], tipo_destino, None, None)
        return (conteudo, [], None,
                renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                area_grafico, mensagem)

    @app.callback(
        Output('container-abas-chrome', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('area-modo-nova-analise-edicao', 'children', allow_duplicate=True),
        Input('aba-ativa-store', 'data'),
        State('modo-nova-analise-store', 'data'),
        prevent_initial_call=True,
    )
    def sincronizar_interface_por_aba(aba_ativa, modo_calculadora_ativo):
        # Os botões de COLUNA da calculadora (grupo 'Colunas', ver
        # renderizar_calculadora_botoes) dependem de qual arquivo está
        # ativo — sem isto, trocar de aba com o modo 'Nova Análise'
        # ligado deixava o painel de edição mostrando as colunas do
        # arquivo ANTERIOR, mesmo já estando noutra aba.
        botoes_calculadora = no_update
        if modo_calculadora_ativo:
            botoes_calculadora = renderizar_calculadora_botoes(estado, aba_ativa)
        return (renderizar_abas_estilo_chrome(estado, aba_ativa), renderizar_colunas_da_aba_ativa(estado, aba_ativa),
                botoes_calculadora)

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('iniciar-edicao', 'disabled', allow_duplicate=True),
        Output('rodape-alerta-badge', 'children', allow_duplicate=True),
        Output('rodape-alerta-badge', 'className', allow_duplicate=True),
        Output('rodape-alerta-popup', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input('central-btn-1', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def gerar_grafico_serie_temporal(n_clicks, aba_ativa):
        if not n_clicks or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]

        # Gera o gráfico com os canais já marcados até agora (pode ser
        # nenhum ainda — nesse caso nasce em branco, e o usuário vai
        # populando ao marcar colunas na barra lateral). Se o arquivo tiver
        # mais de 5000 linhas, essa chamada também empurra um aviso de
        # amostragem pra lista de avisos da aba (ver plotter.py).
        fig = construir_figura_serie_temporal(estado, aba_ativa)

        # Salva o gráfico no estado da aba ativa. 'grafico_gerado' é uma
        # property derivada de 'figura' (ver src/core/arquivo.py) — não
        # precisa (e não pode) ser setada à parte.
        arquivo.figura = fig

        # A partir de agora esse canal ESTÁ sendo usado como eixo X deste
        # gráfico — some da lista de canais plotáveis da barra lateral
        # (ver Arquivo.ocultar_canal_eixo). Fechar o gráfico desfaz isso
        # (ver fechar_grafico, abaixo).
        eixo_x = resolver_eixo_x(estado, arquivo.df_editado)
        arquivo.ocultar_canal_eixo(eixo_x)

        tem_canal = any(arq == aba_ativa for arq, _ in estado.canais_selecionados)
        mensagem = (
            '🧙‍♂️: " Gráfico de série temporal gerado. Marque os canais na barra lateral. "'
            if not tem_canal else
            '🧙‍♂️: " Gráfico de série temporal gerado. "'
        )
        grafico = renderizar_grafico_com_fechar(fig)

        _, badge_texto, badge_classe, popup_children = _valores_rodape(estado, aba_ativa)
        return (grafico, renderizar_colunas_da_aba_ativa(estado, aba_ativa), mensagem,
                False, False, False, False, False, False,
                badge_texto, badge_classe, popup_children,
                True)

    @app.callback(
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('lista-canais-aba', 'children', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
        Output('aparar-dados', 'disabled', allow_duplicate=True),
        Output('excluir-dados', 'disabled', allow_duplicate=True),
        Output('nova-amostra', 'disabled', allow_duplicate=True),
        Output('exportar-grafico', 'disabled', allow_duplicate=True),
        Output('exportar-dados', 'disabled', allow_duplicate=True),
        Output('iniciar-edicao', 'disabled', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('painel-direito-conteudo', 'children', allow_duplicate=True),
        Output('rodape-timer-mensagem', 'disabled', allow_duplicate=True),
        Input('fechar-grafico', 'n_clicks'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def fechar_grafico(n_clicks, aba_ativa):
        """
        Fecha só a VISUALIZAÇÃO do gráfico, voltando pra grade de opções —
        não fecha arquivo nenhum (isso é o botão 'X' da aba, que já reseta
        tudo sozinho quando não sobra arquivo carregado).
        """
        if not n_clicks or not aba_ativa:
            raise PreventUpdate

        lista_canais = no_update
        if aba_ativa in estado.arquivos:
            arquivo = estado.arquivos[aba_ativa]
            arquivo.invalidar_grafico()

            # O canal do eixo X só ficava oculto enquanto ESTE gráfico
            # estava aberto (ver gerar_grafico_serie_temporal) — fechando
            # o gráfico, ele volta a aparecer normalmente na barra lateral.
            eixo_x = resolver_eixo_x(estado, arquivo.df_editado)
            arquivo.exibir_canal_eixo(eixo_x)
            lista_canais = renderizar_colunas_da_aba_ativa(estado, aba_ativa)

        area_grafico = renderizar_area_grafico(estado)
        mensagem = '🧙‍♂️: " Gráfico fechado. Escolha outra opção. "'

        # O arquivo continua carregado (só o gráfico foi fechado), então
        # 'nova-amostra' e 'exportar-dados' NÃO devem voltar a ficar
        # desabilitados aqui — só 'aparar-dados'/'excluir-dados'/
        # 'exportar-grafico'/'iniciar-edicao' (que dependem do gráfico da
        # aba ativa, agora invalidado) e o painel de edição (que volta ao
        # estado normal, já que não faz sentido continuar "em edição" de
        # um gráfico que não existe mais).
        sem_arquivo, _, sem_grafico_da_aba = _estados_toolbar(estado, aba_ativa)
        return (area_grafico, lista_canais, mensagem,
                sem_grafico_da_aba, sem_grafico_da_aba, sem_arquivo, sem_grafico_da_aba, sem_arquivo,
                sem_grafico_da_aba, _classe_painel_direito(ativo=False),
                renderizar_painel_direito_padrao(disabled=sem_grafico_da_aba), True)

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
        Output('rodape-status', 'children', allow_duplicate=True),
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
            mensagem = '🧙‍♂️: " Clique no gráfico para marcar o INÍCIO do recorte. "'
        else:
            mensagem = '🧙‍♂️: " Clique no gráfico para marcar o INÍCIO do trecho a excluir. "'

        return (
            dados_selecao,
            'sidebar area-inativa-selecao',
            _classe_painel_direito(ativo=painel_ativo, selecionando=True),
            'toolbar-icones inativo ferramenta-' + tipo,
            'area-grafico-container corte-ativo',
            mensagem,
        )

    @app.callback(
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('grafico-plotly-real', 'figure', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
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
                mensagem = '🧙‍♂️: " Agora clique um pouco mais à direita para marcar o FIM do recorte. "'
            else:
                mensagem = '🧙‍♂️: " Agora clique um pouco mais à direita para marcar o FIM do trecho a excluir. "'
            estilo_prompt = no_update
        elif segundo is None:
            if valor_x <= primeiro:
                raise PreventUpdate
            segundo = valor_x
            mensagem = '🧙‍♂️: " Confirma? "'
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
        return dados_selecao, fig, mensagem, estilo_prompt, classe_container

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
        Output('rodape-status', 'children', allow_duplicate=True),
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
        eixo_x = resolver_eixo_x(estado, arquivo.df_editado)
        if tipo == 'excluir':
            arquivo.df_editado = excluir_dados(arquivo.df_editado, eixo_x, primeiro, segundo)
            mensagem = '🧙‍♂️: " Trecho excluído! O que estava entre os dois cortes sumiu, o resto ficou. "'
        else:
            arquivo.df_editado = aparar_dados(arquivo.df_editado, eixo_x, primeiro, segundo)
            mensagem = '🧙‍♂️: " Dados aparados! Só ficou o que estava entre os dois cortes. "'
        arquivo.invalidar_grafico()

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        container_grafico = renderizar_grafico_com_fechar(fig)

        _, sidebar, painel, icones, grafico_classe, prompt_estilo = _restaurar_apos_selecao(
            painel_ativo=dados_selecao.get('painel_ativo', False))
        return None, sidebar, painel, icones, grafico_classe, prompt_estilo, container_grafico, mensagem

    @app.callback(
        Output('corte-selecao-store', 'data', allow_duplicate=True),
        Output('sidebar-principal', 'className', allow_duplicate=True),
        Output('painel-direito', 'className', allow_duplicate=True),
        Output('toolbar-icones', 'className', allow_duplicate=True),
        Output('container-grafico', 'className', allow_duplicate=True),
        Output('toolbar-confirmacao-corte', 'style', allow_duplicate=True),
        Output('grafico-plotly-real', 'figure', allow_duplicate=True),
        Output('rodape-status', 'children', allow_duplicate=True),
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
        mensagem = '🧙‍♂️: " Seleção cancelada. Nada foi alterado. "'

        _, sidebar, painel, icones, grafico_classe, prompt_estilo = _restaurar_apos_selecao(
            painel_ativo=dados_selecao.get('painel_ativo', False))
        return None, sidebar, painel, icones, grafico_classe, prompt_estilo, fig, mensagem

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
        os 4 controles abaixo (Thickness, cor, Style, Marker) precisam
        refletir o que JÁ está salvo pra essa curva especificamente —
        senão eles ficariam mostrando o valor da curva anterior. Também
        dispara (efeito colateral esperado, não um bug) na primeira vez
        que o painel abre, já que a caixa 'Dado' acabou de nascer com um
        valor — é o mesmo 'gatilho fantasma' de componente recém-criado
        comentado em _clique_real, aqui é ele quem faz os controles
        nascerem com os valores certos sem precisar duplicar essa lógica
        em abrir_painel_edicao.

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
        r, g, b = _hex_para_rgb(cor_atual)
        return espessura_atual, cor_atual, estilo_atual, marcador_atual, r, g, b

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
        Input('edicao-curva-espessura', 'value'),
        Input({'type': 'cor-store', 'index': 'curva'}, 'data'),
        Input('edicao-curva-estilo', 'value'),
        Input('edicao-curva-marcador', 'value'),
        State('edicao-curva-dado', 'value'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def aplicar_preferencias_curva(espessura, cor, estilo, marcador, coluna, aba_ativa):
        """
        Grava os 4 controles do painel 'Curva' como preferência
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

        Os 4 Inputs disparam juntos neste único callback (em vez de 4
        callbacks separados) porque os 4 preenchem o MESMO
        PreferenciasCanal e precisam terminar sempre com os 4 valores
        atuais gravados juntos — gravar só o campo que mudou arriscaria
        um 'value' desatualizado vencer a corrida se dois campos forem
        mexidos em sequência rápida.
        """
        if not coluna or not aba_ativa or aba_ativa not in estado.arquivos:
            raise PreventUpdate

        arquivo = estado.arquivos[aba_ativa]
        if not arquivo.grafico_gerado or coluna not in colunas_plotadas(estado, aba_ativa):
            raise PreventUpdate

        prefs = arquivo.preferencias.preferencias_do_canal(coluna)
        prefs.espessura = espessura or 1.0
        prefs.cor = cor
        prefs.estilo_linha = estilo or 'solid'
        prefs.marcador = marcador or 'none'

        fig = construir_figura_serie_temporal(estado, aba_ativa)
        arquivo.figura = fig
        return renderizar_grafico_com_fechar(fig)

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
        classe_both_sides = 'painel-edicao-toggle' + (' ativo' if prefs_eixo.both_sides else '')
        classe_direcao = 'painel-edicao-toggle' + (' ativo' if prefs_eixo.direcao == 'inside' else '')
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
