"""
Helpers compartilhados entre os módulos de callbacks.

Moram aqui porque são usados por mais de um módulo de src/callbacks/ — assim
nenhum módulo precisa importar outro.
"""
import json

from dash import ctx


def _chave_id_padrao(id_item):
    """
    Normaliza um id de componente — dict de padrão coringa
    ({'type': ..., ...}) ou string de id fixo (ex: 'calc-limpar') — numa
    chave única e estável pra comparar com os ids disparados. Devolve None
    se o formato for inesperado.
    """
    if isinstance(id_item, dict):
        return json.dumps(id_item, sort_keys=True)
    if isinstance(id_item, str):
        return id_item
    return None


def processar_cliques_padrao(grupos_inputs_list):
    """
    Devolve o id do componente que recebeu um CLIQUE DE VERDADE nesta
    chamada, ou None se o disparo foi só "fantasma" (quem chama trata None
    como PreventUpdate).

    O problema: botões que nascem dentro de listas reconstruídas por
    callbacks (abas, lista de canais, barra e teclado da calculadora)
    disparam o callback sozinhos quando a lista é redesenhada — o Dash
    trata o componente recém-criado como um "disparo" do Input, mesmo sem
    clique nenhum. Sem este filtro: o 1º canal marcava sozinho ao gerar ou
    fechar o gráfico, 'Derivada' disparava ao ligar a Nova Análise, e o ⌫
    apagava o token que acabara de ser clicado.

    A regra: todo botão nasce com n_clicks=0 no Python, então o disparo
    fantasma sempre chega com valor 0/None, e um clique real sempre chega
    com valor >= 1. Entre os componentes que REALMENTE dispararam agora
    (ctx.triggered_prop_ids — ids já decodificados pelo Dash, sem depender
    do texto de 'prop_id', então nomes de coluna "atípicos" como 'N#' ou
    'FW-A' não interferem), valor > 0 é clique de verdade.

    Histórico: até a Fase 2.7 a regra era "o valor precisa SUBIR em
    relação ao último guardado num dcc.Store" — isso perdia cliques reais
    quando um callback redesenhava a própria lista (o botão voltava a 0,
    mas o valor guardado continuava alto). O Store foi removido na 3.3.

    'grupos_inputs_list' é o 'ctx.inputs_list' do callback: cada entrada é
    um dict {'id', 'property', 'value'} (Input simples) ou uma LISTA deles
    (Input de padrão coringa, um item por componente casado).
    """
    chaves_disparadas = {
        _chave_id_padrao(id_disparado)
        for id_disparado in (ctx.triggered_prop_ids or {}).values()
    }

    gatilho_id = None
    for grupo in grupos_inputs_list:
        itens = grupo if isinstance(grupo, list) else [grupo]
        for item in itens:
            id_item = item.get('id')
            chave = _chave_id_padrao(id_item)
            if chave is None:
                continue
            if chave in chaves_disparadas and (item.get('value') or 0) > 0:
                gatilho_id = id_item
    return gatilho_id


def estados_toolbar(estado, aba_ativa):
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


def classe_painel_direito(ativo=False, selecionando=False):
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
