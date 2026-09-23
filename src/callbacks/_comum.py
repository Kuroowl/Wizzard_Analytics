"""
Helpers compartilhados entre os módulos de callbacks.

Moram aqui porque são usados por mais de um módulo de src/callbacks/ — assim
nenhum módulo precisa importar outro. Movidos SEM modificação de
src/gui/callbacks.py (Fase 2 do rework: mover sem mudar).
"""
import json

from dash import ctx


# ============================================================================
# Filtro anti-"clique fantasma" (_processar_cliques_padrao, logo
# abaixo) — REATIVADO. Foi desligado temporariamente pra um teste de
# diagnóstico (a pedido explícito), mas o próprio teste PROVOU que ele
# não era o culpado: com o filtro desligado, o botão 'Derivada' passou
# a disparar SOZINHO (mensagem de erro amigável aparecendo sem clique
# nenhum) assim que o modo 'Nova Análise' é ligado — exatamente o
# disparo fantasma que este filtro existe pra bloquear, agora
# acontecendo nos NOVOS botões da calculadora também (não só nos
# canais/abas de antes). E o problema original ("não consigo clicar em
# nada") continuou acontecendo mesmo com o filtro desligado — ou seja,
# desligá-lo não ajudou em nada e ainda piorou (deixou passar disparos
# fantasmas que antes eram bloqueados). Voltando pra True.
# ============================================================================
GUARD_CLIQUE_FANTASMA_ATIVO = True


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


def _chave_id_padrao(id_item):
    """
    Normaliza um id de componente (dict de padrão coringa
    {'type':...,...} OU string de id fixo, tipo 'calc-limpar') numa
    CHAVE única e estável pra usar como entrada em 'nclicks-padrao-
    store' — devolve None se 'id_item' não for nem dict nem string
    (formato inesperado, ignora).

    Existe porque o MESMO problema de "disparo fantasma" (ver
    _processar_cliques_padrao logo abaixo) também afeta componentes de
    ID FIXO, não só padrão coringa — descoberto quando 'calc-apagar'
    (um botão de id fixo, sem padrão nenhum) começou a disparar
    sozinho toda vez que a barra de cálculo era reconstruída (a cada
    token clicado, ver registrar_token_calculadora): o botão INTEIRO é
    remontado do zero junto com o resto da barra, e o Dash trata esse
    remonte como um "disparo" de 'n_clicks' mesmo sem clique nenhum —
    exatamente o mesmo mecanismo que já causava disparo fantasma em
    botões de padrão coringa (canais, abas), só que agora também
    acontece com um id fixo comum. Sem rastrear o valor anterior
    TAMBÉM pra esses ids fixos, um clique em QUALQUER token da
    calculadora (que reconstrói a barra) fazia 'apagar_ultimo_token_
    calculadora' disparar sozinho logo em seguida, apagando o token
    que acabara de ser clicado — o bug fica visível: "clico na
    coluna, ela aparece na barra e alguma coisa tira ela na hora".
    """
    if isinstance(id_item, dict):
        return json.dumps(id_item, sort_keys=True)
    if isinstance(id_item, str):
        return id_item
    return None


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
    CORREÇÃO (Fase 2.7) — cliques "engolidos"
    ------------------------------------------------------------------
    A regra original ("só é clique se o valor SUBIR em relação ao
    último guardado") perdia cliques de verdade: quando um callback
    redesenha a PRÓPRIA lista (ex: o lápis reconstrói a lista de
    canais), o Dash NÃO dispara esse callback de novo — então o botão
    renasce com n_clicks=0 no navegador, mas o valor guardado no Store
    continua alto. Os próximos cliques (1, 2...) ficavam <= ao valor
    antigo e eram descartados até o contador "alcançar" o número velho.
    Medido no navegador: lápis abria/fechava só em 3 de 6 cliques;
    na calculadora, depois do 1º canal criado, token e 'Criar' eram
    ignorados.

    Regra atual: um disparo FANTASMA de remontagem sempre chega com
    valor 0/None (todo botão nasce com n_clicks=0 no Python), e um
    clique real sempre chega com valor >= 1. Então, entre os
    componentes que REALMENTE dispararam nesta chamada
    (ctx.triggered_prop_ids), qualquer valor > 0 é clique de verdade —
    sem comparar com o Store. Os ids disparados vêm já decodificados
    pelo Dash (não do texto de 'prop_id'), e o valor vem de
    'grupos_inputs_list', então nomes de coluna "atípicos" (ex: 'N#',
    'FW-A') não interferem.

    'nclicks-padrao-store'/'novo_mapa' continuam sendo atualizados
    (assinatura inalterada pros callbacks), mas não decidem mais nada.
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
                chave = _chave_id_padrao(id_item)
                if chave is None:
                    continue
                novo_mapa[chave] = item.get('value') or 0
        if ctx.triggered_id is not None:
            gatilho_id = ctx.triggered_id
        return gatilho_id, novo_mapa

    chaves_disparadas = {
        _chave_id_padrao(id_disparado)
        for id_disparado in (ctx.triggered_prop_ids or {}).values()
    }

    for grupo in grupos_inputs_list:
        itens = grupo if isinstance(grupo, list) else [grupo]
        for item in itens:
            id_item = item.get('id')
            chave = _chave_id_padrao(id_item)
            if chave is None:
                continue
            valor_novo = item.get('value') or 0
            # Clique real = disparou AGORA e tem valor >= 1. Fantasma de
            # remontagem chega com 0 (ver docstring, "CORREÇÃO").
            if chave in chaves_disparadas and valor_novo > 0:
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
