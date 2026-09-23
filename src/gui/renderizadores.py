from dash import dcc, html

from src.gui.components import icone_colorido
from src.core.plotting.plotter import cor_da_coluna, colunas_plotadas, PALETA_CORES
from src.core.operations.calculadora import (
    NUMEROS, OPERADORES, FUNCOES, OPERACOES_RAPIDAS,
    calc_criar_desabilitado,
)


def truncar_nome_arquivo(nome, limite=15):
    base, ext = nome.rsplit('.', 1) if '.' in nome else (nome, '')
    if len(base) <= limite:
        return nome
    return f"{base[:limite]}...{('.' + ext) if ext else ''}"


def renderizar_abas_estilo_chrome(estado, aba_ativa):
    if not estado.arquivos:
        return html.Div("Nenhum arquivo", className="abas-placeholder")

    abas = []
    lista_arquivos = list(estado.arquivos.keys())

    for i, nome_arq in enumerate(lista_arquivos):
        e_ativa = (nome_arq == aba_ativa)
        nome_curto = truncar_nome_arquivo(nome_arq)
        classe_aba = "aba-chrome" + (" ativa" if e_ativa else "")

        conteudo_aba = html.Div(
            className=classe_aba,
            id={'type': 'aba-item', 'arquivo': nome_arq},
            children=[
                html.Span(nome_curto, title=nome_arq, className="aba-texto"),
                html.Button(
                    '✕',
                    id={'type': 'botao-fechar-aba', 'arquivo': nome_arq},
                    className="aba-fechar-btn",
                    n_clicks=0
                )
            ]
        )
        abas.append(conteudo_aba)

        if i < len(lista_arquivos) - 1:
            proximo = lista_arquivos[i + 1]
            if aba_ativa != nome_arq and aba_ativa != proximo:
                abas.append(html.Span("|", className="aba-divisor"))

    return abas


def _linha_canal_lateral(arquivo, aba_ativa, coluna, id_type_rotulo, titulo_rotulo,
                          canal_em_edicao=None, eixo=None):
    """
    UMA linha de canal (rótulo clicável + lápis + lixeira) — compartilhada
    entre a lista 'Dados do arquivo:' (renderizar_colunas_da_aba_ativa) e
    as caixas X:/Y: (renderizar_selecao_eixos, logo abaixo), pra ter
    EXATAMENTE a mesma aparência/comportamento nos dois lugares (pedido
    explícito: "mantenha a estética que já tinha... isso inclui até os
    botões de remover canal e renomear canal"). O que muda entre os dois
    contextos é só:
      - 'id_type_rotulo': o clique no NOME atribui (lista, 'linha-canal')
        ou devolve pra lista (caixa X/Y, 'remover-eixo-selecionado').
      - 'eixo': só preenchido pras linhas dentro da caixa X/Y (viaja
        junto no id, mesmo formato usado em gerenciar_atribuicao_eixos).
    Lápis (renomear) e lixeira (excluir) usam os MESMOS ids/callbacks
    nos dois lugares — 'gerenciar_edicao_canal' e 'gerenciar_atribuicao_
    eixos' não se importam se a coluna está visível na lista ou dentro
    de X/Y, então funcionam sem nenhuma duplicação de lógica.
    """
    rotulo = arquivo.rotulo(coluna)

    em_edicao = bool(canal_em_edicao) and canal_em_edicao.get('arquivo') == aba_ativa \
        and canal_em_edicao.get('coluna') == coluna

    # 'editando' força o lápis (e, por consistência visual, o resto
    # da linha) a ficar no estado "revelado" mesmo sem o mouse em
    # cima — sem essa classe, o lápis só aparece no ':hover' (ver
    # '.coluna-item:hover .canal-editar-btn' em file_menu.css), e o
    # usuário perdia de vista o próprio botão que precisa clicar
    # de novo pra fechar/salvar (ver gerenciar_edicao_canal,
    # callbacks.py) assim que tirava o mouse de cima da linha
    # depois de abrir a edição.
    #
    # 'calculado' distingue visualmente um canal criado pela
    # calculadora do modo 'Nova Análise' (ver
    # avaliar_expressao_calculadora, callbacks.py) de um canal
    # ORIGINAL do arquivo só renomeado — os dois têm rótulo livre
    # igual, então sem uma marca visual não dava pra saber "esse
    # dado eu inventei" só olhando a lista (ver 'canal.origem' em
    # src/core/arquivo.py, que já existia pronto pra isso — nunca
    # tinha UI nenhuma lendo ele até agora).
    calculado = arquivo.canais.get(coluna) and arquivo.canais[coluna].origem == 'calculado'
    # Índice implícito (arquivo com 1 coluna numérica, ver Arquivo.
    # criar_de_leitura): marcador '#' e SEM lixeira — pode renomear, não
    # pode excluir (é a referência do eixo X).
    indice = arquivo.canal_protegido(coluna)
    classe_canal = ('coluna-item'
                     + (' editando' if em_edicao else '')
                     + (' calculado' if calculado else '')
                     + (' indice' if indice else ''))

    if em_edicao:
        # Input no lugar do botão de rótulo — 'autoFocus' já abre
        # com o cursor pronto pra digitar (não precisa de um
        # segundo clique), e o valor de partida é o rótulo ATUAL
        # (não o nome_interno), pra edições incrementais (corrigir
        # só um detalhe do nome) não obrigarem redigitar tudo.
        # 'debounce=False': cada tecla já atualiza 'value' no
        # componente, mas o callback só LÊ esse valor no
        # Enter/blur (n_submit/n_blur, ver confirmar_edicao_canal)
        # — debounce aqui só atrasaria o que o usuário vê
        # digitado, sem ganho nenhum, já que ninguém reage a cada
        # tecla.
        campo_rotulo = dcc.Input(
            id={'type': 'input-editar-canal', 'arquivo': aba_ativa, 'coluna': coluna},
            type='text', value=rotulo, autoFocus=True, debounce=False,
            className='canal-rotulo-input',
            maxLength=80,
        )
    else:
        # Botão clicável — 'ƒ' na frente do rótulo pra canais
        # calculados, junto com a borda esquerda colorida (ver
        # '.coluna-item.calculado' em file_menu.css), é a segunda
        # metade do sinal visual "isto foi gerado, não é um dado
        # bruto do arquivo original".
        if calculado:
            conteudo_botao = [html.Span('ƒ', className='canal-calculado-marcador'), rotulo]
            titulo = f"Calculado: {arquivo.canais[coluna].formula or ''}"
        elif indice:
            conteudo_botao = [html.Span('#', className='canal-indice-marcador'), rotulo]
            titulo = ('Índice das amostras (0, 1, 2…), criado porque o arquivo tem só '
                      '1 coluna numérica. Pode ser usado na Nova Análise (ex: índice × 0.01).')
        else:
            conteudo_botao = rotulo
            titulo = titulo_rotulo
        id_rotulo = {'type': id_type_rotulo, 'arquivo': aba_ativa, 'coluna': coluna}
        if eixo is not None:
            id_rotulo['eixo'] = eixo
        campo_rotulo = html.Button(
            conteudo_botao,
            id=id_rotulo,
            className='canal-rotulo canal-rotulo-btn',
            title=titulo,
            n_clicks=0,
        )

    return html.Div(
        className=classe_canal,
        children=[
            campo_rotulo,
            html.Button(
                '✏️',
                id={'type': 'botao-editar-canal', 'arquivo': aba_ativa, 'coluna': coluna},
                className="canal-editar-btn",
                title=f"Renomear canal '{rotulo}'",
                n_clicks=0,
            ),
            *([] if indice else [html.Button(
                '🗑',
                id={'type': 'botao-excluir-canal', 'arquivo': aba_ativa, 'coluna': coluna},
                className="canal-lixeira-btn",
                title=f"Excluir canal '{rotulo}'",
                n_clicks=0,
            )]),
        ]
    )


def renderizar_colunas_da_aba_ativa(estado, aba_ativa, canal_em_edicao=None):
    """
    'canal_em_edicao': None (padrão) ou {'arquivo': <aba>, 'coluna':
    <nome_interno>} — quando bate com a aba/coluna desta linha, ela
    nasce com um <input> editável no lugar do rótulo estático (ver
    alternar_edicao_canal/confirmar_edicao_canal em callbacks.py, que
    escrevem/leem 'canal-em-edicao-store'). Qualquer outra linha
    continua no modo normal (Span/Button + lápis + lixeira) — ver
    '_linha_canal_lateral' acima, compartilhada com renderizar_
    selecao_eixos logo abaixo.

    Só lista canais VISÍVEIS (Arquivo.colunas_visiveis) — desde o
    rework do 'Plotar Seleção', um canal atribuído a X ou Y (ver
    Arquivo.mover_para_eixo_x/mover_para_eixo_y, src/core/arquivo.py)
    SOME desta lista e passa a aparecer na caixa X:/Y: acima — não tem
    mais "linha marcada" dentro desta lista (o antigo ☐/✓), só colunas
    ainda NÃO atribuídas a nada.

    ÁREA DE CLIQUE — 'id={'type': 'linha-canal', ...}' agora vive no
    PRÓPRIO rótulo (um <button>, não mais um <span>): clicar no NOME
    da coluna é o que manda ela pra X (se ainda não há X) ou pro fim
    de Y (ver gerenciar_atribuicao_eixos, callbacks.py) — substituiu a
    antiga caixinha ☐/✓ separada, que só (des)marcava a coluna sem
    tirá-la da lista. Lápis/lixeira continuam como IRMÃOS do rótulo
    (não descendentes), então cliques neles não borbulham pro clique
    de atribuição.
    """
    if not aba_ativa or aba_ativa not in estado.arquivos:
        return html.Div('Abra um arquivo.', className='abas-placeholder', style={'padding': '14px'})

    arquivo = estado.arquivos[aba_ativa]

    lista_canais = [
        _linha_canal_lateral(
            arquivo, aba_ativa, coluna, 'linha-canal',
            "Clique para usar como eixo X (ou Y, se já houver X)",
            canal_em_edicao,
        )
        for coluna in arquivo.colunas_visiveis()
    ]

    if not lista_canais:
        return []

    # Card separado do fundo da sidebar (que continua com o watermark de
    # 'file.svg' por baixo) — em vez dos itens ficarem soltos e
    # transparentes herdando a cor do menu, eles agora vivem 'sobre' ele,
    # com tom próprio e sombra sutil. Se a lista for curta, o cartão
    # também fica curto e o watermark aparece normalmente ao redor — não é
    # um problema, é o efeito desejado.
    return [html.Div(className='canais-cartao', children=lista_canais)]


def renderizar_selecao_eixos(estado, aba_ativa, canal_em_edicao=None):
    """
    A área de atribuição manual de eixos do botão 'Plotar Seleção'
    (era 'Gerar Série Temporal') — dois "slots" acima da lista 'Dados
    do arquivo:' (ver renderizar_colunas_da_aba_ativa acima).

    Clicar no NOME de uma coluna na lista manda ela pra cá: a
    PRIMEIRA coluna clicada vira X, as seguintes se acumulam em Y, na
    ordem do clique (ver Arquivo.mover_para_eixo_x/mover_para_eixo_y,
    src/core/arquivo.py, e gerenciar_atribuicao_eixos, callbacks.py).
    Clicar de novo no NOME de uma linha aqui dentro devolve a coluna
    pra lista (Arquivo.remover_da_selecao_eixos).

    Cada linha usa '_linha_canal_lateral' (acima) — MESMA aparência e
    MESMOS botões de renomear/excluir da lista 'Dados do arquivo:'
    (pedido explícito: "mantenha a estética que já tinha... isso
    inclui até os botões de remover canal e renomear canal"), cada uma
    ocupando a largura TOTAL da caixa e empilhadas (não mais um "chip"
    pequeno lado a lado — pedido explícito também).

    SÓ aparece depois que 'Plotar Seleção' foi clicado pelo menos uma
    vez nesta aba (checa 'arquivo.grafico_gerado') — pedido explícito,
    revisando a versão anterior: "essa nova seção... só deve ser
    exibida quando clicamos em plotar seleção". Antes de clicar, a
    atribuição de X/Y ainda pode acontecer nos bastidores (clicar um
    nome na lista já registra em Arquivo.eixo_x_manual/eixos_y_manual),
    só não tem uma seção própria mostrando isso até existir um gráfico
    de verdade. Fechar o gráfico ('fechar_grafico', callbacks.py)
    também esconde esta seção de novo (mesmo sinal: 'grafico_gerado'
    vira False) — reabrir com 'Plotar Seleção' a traz de volta com a
    MESMA atribuição de antes (ela não é perdida ao fechar).

    Título 'Variáveis do gráfico:' na MESMA classe de 'Dados do
    arquivo:' (ver layout.py) — pedido explícito, pra ficar visualmente
    no mesmo padrão de separação de seção.
    """
    if not aba_ativa or aba_ativa not in estado.arquivos:
        return []
    arquivo = estado.arquivos[aba_ativa]
    if not arquivo.grafico_gerado:
        return []

    def _linha(coluna, eixo):
        return _linha_canal_lateral(
            arquivo, aba_ativa, coluna, 'remover-eixo-selecionado',
            f"Clique para tirar do eixo {eixo.upper()} e voltar pra lista",
            canal_em_edicao, eixo=eixo,
        )

    conteudo_x = (
        [_linha(arquivo.eixo_x_manual, 'x')] if arquivo.eixo_x_manual
        else [html.Span('clique num canal na lista abaixo', className='eixo-caixa-vazia')]
    )
    conteudo_y = (
        [_linha(coluna, 'y') for coluna in arquivo.eixos_y_manual] if arquivo.eixos_y_manual
        else [html.Span('clique nos canais que quer plotar', className='eixo-caixa-vazia')]
    )

    return [
        html.Div('Variáveis do gráfico:', className='sidebar-secao-titulo'),
        html.Div(className='selecao-eixos-container', children=[
            html.Div('X:', className='eixo-rotulo'),
            html.Div(conteudo_x, className='eixo-caixa'),
            html.Div('Y:', className='eixo-rotulo'),
            html.Div(conteudo_y, className='eixo-caixa'),
        ]),
    ]


# Nomes dos ícones das 6 opções de tipo de gráfico — placeholders genéricos,
# troque pelo nome de arquivo real (em assets/icones/) conforme for
# implementando cada opção de verdade.
ICONES_OPCOES_GRAFICO = [
    'ChartOption1_icon.png',
    'ChartOption2_icon.png',
    'ChartOption3_icon.png',
    'ChartOption4_icon.png',
    'ChartOption5_icon.png',
    'ChartOption6_icon.png',
]


def renderizar_area_grafico(estado):
    """
    Conteúdo do container-grafico ANTES de um gráfico de verdade existir:
    - nenhum arquivo carregado: mensagem simples, sem os botões de opção
    - pelo menos 1 arquivo carregado: a grade 2x3 de opções de tipo de
      gráfico (cada botão ainda não faz nada além do central-btn-1, que já
      dispara a plotagem — os outros 5 esperam você implementar depois)
    """
    if not estado.arquivos:
        return html.Div('Carregue um arquivo para começar.', className='area-grafico-vazia')

    opcoes = []
    for i, nome_icone in enumerate(ICONES_OPCOES_GRAFICO, start=1):
        if i == 1:
            # Único botão realmente funcional por enquanto (dispara
            # gerar_grafico_serie_temporal — nome da função Python não
            # mudou, só o RÓTULO visível: era 'Série temporal', agora
            # 'Plotar Seleção', desde o rework que trocou o eixo X
            # automático por atribuição manual de X/Y na barra lateral,
            # ver renderizar_selecao_eixos acima e gerenciar_atribuicao_
            # eixos em callbacks.py) — por isso ganha um rótulo e emoji
            # de verdade em vez do ícone-placeholder genérico que os
            # outros 5 ainda usam (ver ICONES_OPCOES_GRAFICO acima).
            conteudo = [
                html.Span('📈', className='central-btn-emoji'),
                html.Span('Plotar Seleção', className='toolbar-tooltip'),
            ]
        else:
            conteudo = [
                icone_colorido(nome_icone, tamanho=32),
                html.Span(f'Opção {i}', className='toolbar-tooltip'),
            ]
        opcoes.append(html.Button(
            conteudo,
            id=f'central-btn-{i}',
            className='toolbar-botao central-btn-opcao',
            n_clicks=0,
        ))

    return html.Div(className='grade-opcoes-grafico', children=opcoes)


# Opções da caixa 'Style' do painel de edição da curva — TODOS os 6
# valores que go.Scatter aceita em line.dash (plotter.py), não só um
# subconjunto: 'solid', 'dot', 'dash', 'longdash', 'dashdot',
# 'longdashdot'. Cada valor bate exatamente com PreferenciasCanal.
# estilo_linha (src/core/arquivo.py), sem nenhuma tradução/mapa no meio
# — o valor escolhido aqui é gravado e usado como está.
#
# O rótulo é só o traço desenhado em texto (sem nome por extenso — o
# padrão visual já basta pra reconhecer). Primeira opção ('' / 'none')
# é a ausência de linha — a curva não desenha traço nenhum (só o
# marcador, se algum estiver escolhido na caixa 'Marker' ao lado). O
# padrão de uma curva nova continua sendo 'solid' (linha contínua),
# não esta opção em branco — ver PreferenciasCanal.estilo_linha em
# src/core/arquivo.py.
OPCOES_ESTILO_LINHA = [
    {'label': '', 'value': 'none'},
    {'label': '──', 'value': 'solid'},
    {'label': '··', 'value': 'dot'},
    {'label': '––', 'value': 'dash'},
    {'label': '–·', 'value': 'dashdot'},
]

# Opções da caixa 'Marker' do painel de edição da curva — INDEPENDENTE
# da caixa 'Style': escolher um marcador aqui não troca o estilo da
# linha nem o "tipo" do gráfico, só soma um marcador em cada ponto da
# MESMA curva (ver resolver_modo em plotter.py). Primeira opção ('' /
# 'none') é a ausência de marcador — é o padrão de uma curva nova
# (PreferenciasCanal.marcador). Todas as combinações são possíveis:
# linha sozinha, marcador sozinho (escolhendo 'none' na caixa Style),
# ou linha + marcador juntos.
OPCOES_MARCADOR = [
    {'label': '', 'value': 'none'},
    {'label': '●', 'value': 'circle'},
    {'label': '■', 'value': 'square'},
    {'label': '◆', 'value': 'diamond'},
    {'label': '▲', 'value': 'triangle-up'},
    {'label': 'X', 'value': 'x'},
]

# Usado só como cor "de fábrica" quando o card 'Curva' abre sem nenhum
# canal plotado (ver renderizar_painel_edicao) — não existe mais uma
# paleta fixa de opções, o seletor de cor agora é livre (ver
# _seletor_cor logo abaixo).
PALETA_EDICAO_CORES = PALETA_CORES + ['#1B2430', '#7A8699', '#FFFFFF']


def _hex_para_rgb(cor_hex):
    """'#RRGGBB' -> (r, g, b), 0-255 cada. Hex inválido/ausente vira preto."""
    cor_hex = (cor_hex or '#000000').lstrip('#')
    if len(cor_hex) != 6:
        cor_hex = '000000'
    try:
        return tuple(int(cor_hex[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _rgb_para_hsv(r, g, b):
    """(r, g, b) 0-255 -> (h, s, v) com h em graus (0-360) e s/v em 0-1."""
    r, g, b = r / 255, g / 255, b / 255
    maximo, minimo = max(r, g, b), min(r, g, b)
    delta = maximo - minimo

    if delta == 0:
        h = 0.0
    elif maximo == r:
        h = 60 * (((g - b) / delta) % 6)
    elif maximo == g:
        h = 60 * (((b - r) / delta) + 2)
    else:
        h = 60 * (((r - g) / delta) + 4)

    s = 0.0 if maximo == 0 else delta / maximo
    v = maximo
    return h, s, v


def renderizar_painel_direito_padrao(disabled=True):
    """
    Conteúdo 'de repouso' de 'painel-direito-conteudo': só título +
    placeholder. Usado tanto no primeiro carregamento da página
    (layout.py) quanto sempre que a edição precisa ser resetada (fechar
    o gráfico, trocar de aba, ou clicar em 'Fechar edição' no próprio
    painel de curva) — ter essa função num lugar só evita que esses
    pontos divirjam no texto/markup com o tempo.

    O botão 'Iniciar edição' NÃO faz mais parte deste retorno — ele
    agora é um elemento FIXO de 'painel-direito' (ver layout.py),
    escondido via CSS (.painel-direito.ativa .botao-iniciar-edicao)
    quando o card 'Curva' está aberto, em vez de ser destruído e
    recriado a cada troca de estado.
    Antes ele nascia/morria junto com este 'children', e qualquer
    callback que tentasse setar 'iniciar-edicao'.disabled ENQUANTO o
    card 'Curva' estava na tela (ex: ao_fazer_upload de outro arquivo)
    quebrava com "A nonexistent object was used in an Output" — porque
    o id literalmente não existia na árvore naquele instante. Manter o
    botão sempre presente elimina essa classe de erro por completo.

    'disabled' é aceito por compatibilidade com quem chama (mesma
    assinatura de antes) mas não é mais usado aqui — quem controla o
    'disabled' do botão fixo agora é o próprio callback que o gera (ver
    estados_toolbar em callbacks.py), direto no Output dele.
    """
    return [
        html.Div('Opções do gráfico', className='painel-direito-titulo'),
        html.P('Customizações do gráfico', className='painel-direito-placeholder'),
    ]


def _seletor_cor(cor_atual, prefixo):
    """
    Seletor de cor customizado: uma caixinha mostrando a cor atual que,
    ao ser clicada, abre um painel com uma área de saturação/brilho +
    barra de matiz (arraste com o mouse — ver iniciarSeletorCor em
    scripts_js.py) e 3 campos numéricos R/G/B (edição direta, sem
    precisar do mouse). Substitui a antiga grade de swatches fixos:
    dcc.Input(type='color') não é um 'type' válido no
    dash-core-components instalado (só aceita text/number/password/
    email/range/search/tel/url/hidden), então o seletor nativo do
    navegador nunca foi opção aqui.

    'prefixo' identifica QUAL seletor de cor é este (ex: 'curva',
    'fundo') — usado como 'index' de todo id em padrão {'type':...,
    'index': prefixo} (MATCH em callbacks.py) e como 'data-prefixo' no
    wrapper. Foi generalizado a partir da versão original (que só
    existia uma vez, com ids fixos tipo 'cor-picker-caixa') pra poder
    nascer mais de uma instância no mesmo painel — hoje: a cor da
    'Curva' e a cor de fundo do gráfico em 'Outros' — sem duplicar
    nenhum callback nem a lógica de arraste em scripts_js.py, que já
    trabalha só com querySelector RELATIVO ao próprio wrapper (nunca
    por id fixo).

    O dcc.Store com o hex final (fonte de verdade pra quem consome a
    cor, ex: aplicar_preferencias_curva) fica de fora desta função —
    quem chama _seletor_cor decide o id dele (ver renderizar_painel_
    edicao), sempre como {'type': 'cor-store', 'index': prefixo}.

    'data-hue'/'data-sat'/'data-val' no wrapper guardam o HSV atual: é
    o que o arraste do mouse lê/escreve, porque RGB sozinho não
    distingue "matiz perdida" (cinza puro) da matiz que o usuário
    tinha escolhido antes de arrastar só o brilho, por exemplo.
    """
    r, g, b = _hex_para_rgb(cor_atual)
    h, s, v = _rgb_para_hsv(r, g, b)

    return html.Div(
        className='cor-picker-wrapper',
        **{
            'data-prefixo': prefixo,
            'data-hue': round(h, 2), 'data-sat': round(s, 4), 'data-val': round(v, 4),
        },
        children=[
            html.Button(
                id={'type': 'cor-picker-caixa', 'index': prefixo},
                className='cor-picker-caixa', n_clicks=0,
                title='Escolher cor', style={'backgroundColor': cor_atual},
            ),
            html.Div(className='cor-picker-painel', children=[
                html.Div(className='cor-picker-area', children=[
                    html.Div(
                        id={'type': 'cor-picker-area-fundo', 'index': prefixo},
                        className='cor-picker-area-fundo',
                        style={'backgroundColor': f'hsl({h:.1f}, 100%, 50%)'},
                    ),
                    html.Div(
                        id={'type': 'cor-picker-area-cursor', 'index': prefixo},
                        className='cor-picker-area-cursor',
                        style={'left': f'{s * 100:.2f}%', 'top': f'{(1 - v) * 100:.2f}%'},
                    ),
                ]),
                html.Div(className='cor-picker-hue', children=[
                    html.Div(
                        id={'type': 'cor-picker-hue-cursor', 'index': prefixo},
                        className='cor-picker-hue-cursor',
                        style={'left': f'{(h / 360) * 100:.2f}%'},
                    ),
                ]),
                html.Div(className='cor-picker-campos', children=[
                    _campo_rgb({'type': 'cor-rgb-r', 'index': prefixo}, 'R', r),
                    _campo_rgb({'type': 'cor-rgb-g', 'index': prefixo}, 'G', g),
                    _campo_rgb({'type': 'cor-rgb-b', 'index': prefixo}, 'B', b),
                ]),
            ]),
        ],
    )


def _campo_rgb(id_input, rotulo, valor):
    return html.Div(className='cor-picker-campo', children=[
        dcc.Input(
            id=id_input, type='number', min=0, max=255, step=1, value=valor,
            className='cor-picker-input',
        ),
        html.Label(rotulo, className='cor-picker-label'),
    ])


def _secao_colapsavel(id_secao, titulo, conteudo, aberta=False):
    """
    Casca reaproveitável de uma seção recolhível do painel de edição
    ('Curva', 'Eixos', 'Ticks', 'Outros'...). O cabeçalho é um botão
    com pattern-id (ver alternar_secao_edicao em callbacks.py) que
    liga/desliga a classe 'aberta' no wrapper — é essa classe que
    mostra/esconde '.painel-edicao-secao-corpo' via CSS (ver
    edit_menu.css), sem precisar de um callback Python por seção.

    'id_secao' precisa ser único dentro do painel (ex: 'curva',
    'eixos', 'ticks') — é ele que liga cabeçalho e wrapper no mesmo
    par {'type': ..., 'index': id_secao} usado pelo MATCH.
    """
    classes = 'painel-edicao-secao' + (' aberta' if aberta else '')
    return html.Div(
        id={'type': 'secao-wrapper', 'index': id_secao},
        className=classes,
        children=[
            html.Button(
                id={'type': 'secao-header', 'index': id_secao},
                className='painel-edicao-secao-cabecalho',
                n_clicks=0,
                children=[
                    html.Span(titulo, className='painel-edicao-secao-titulo'),
                    html.Span('▼', className='painel-edicao-secao-seta'),
                ],
            ),
            html.Div(className='painel-edicao-secao-corpo', children=conteudo),
        ],
    )


def _stepper(index, valor, minimo, maximo, step=1):
    """
    Par de botões '-'/'+' ao lado de um campo numérico — reaproveitável
    por qualquer seção do painel (hoje: tamanho de fonte e espaçamento
    de 'Eixos'; no futuro: os mesmos controles em 'Ticks'). 'index'
    precisa ser único dentro do painel — é ele que liga os 3 elementos
    (menos/valor/mais) no callback genérico alternar_stepper
    (callbacks.py, MATCH), que decide o sinal (+/-) olhando qual dos
    dois botões foi clicado, e lê min/max/step direto dos atributos do
    próprio dcc.Input (sem precisar duplicar esses limites no Python).
    """
    return html.Div(className='painel-edicao-stepper', children=[
        html.Button(
            '−', id={'type': 'stepper-menos', 'index': index},
            className='painel-edicao-stepper-btn', n_clicks=0,
        ),
        dcc.Input(
            id={'type': 'stepper-valor', 'index': index},
            type='number', value=valor, min=minimo, max=maximo, step=step,
            className='painel-edicao-stepper-input',
        ),
        html.Button(
            '+', id={'type': 'stepper-mais', 'index': index},
            className='painel-edicao-stepper-btn', n_clicks=0,
        ),
    ])


def _toggle(indice, ativo=False, classe_extra=None):
    """
    Interruptor genérico (on/off), no mesmo espírito visual de um
    <input type='checkbox'> mas como um <button> — mesma técnica já
    usada pro cadeado de 'Limits' (_linha_limite_eixo /
    alternar_cadeado_limite): a classe 'ativo' liga/desliga via
    callback (ver alternar_toggle em callbacks.py, MATCH), sem
    precisar de um dcc.Checklist por trás.

    Reaproveitado em: 'Both sides' e 'Division/Subdivision' (seção
    'Ticks') e 'Grid' (seção 'Outros') — qualquer novo on/off do
    painel pode usar este mesmo componente, bastando um 'indice'
    próprio (único dentro do painel).

    'classe_extra' é uma classe FIXA (não mexida pelo callback, que só
    liga/desliga 'ativo' preservando o resto — ver alternar_toggle)
    pendurada no botão além de 'painel-edicao-toggle'. Serve pra dar
    uma cor PRÓPRIA a um toggle específico sem afetar os outros: hoje
    só o toggle 'Division/Subdivision' usa isso
    ('painel-edicao-toggle-modo', ver .painel-edicao-toggle-modo.ativo
    em edit_menu.css), pra ficar laranja em vez do teal padrão — o
    mesmo tom usado nos sliders quando 'Subdivision' está ativo,
    reforçando visualmente que os dois estão no mesmo modo.
    """
    classes = ['painel-edicao-toggle']
    if classe_extra:
        classes.append(classe_extra)
    if ativo:
        classes.append('ativo')
    return html.Button(
        id={'type': 'toggle', 'index': indice},
        className=' '.join(classes), n_clicks=0, type='button',
        children=html.Span(className='painel-edicao-toggle-bolinha'),
    )


def _linha_toggle(rotulo, indice, ativo=False, classe_rotulo='painel-edicao-limite-titulo'):
    """Rótulo + _toggle numa linha só (cabeçalho de 'Both sides'/'Grid')."""
    return html.Div(className='painel-edicao-toggle-linha', children=[
        html.Span(rotulo, className=classe_rotulo),
        _toggle(indice, ativo=ativo),
    ])


def _linha_toggle_dupla(rotulo_externo, rotulo_esquerda, rotulo_direita, indice, ativo=False):
    """
    Toggle SEGMENTADO — rótulo FIXO à esquerda (ex: 'Type:', como
    qualquer outro campo do painel) + uma pílula que ocupa o resto da
    linha, com os DOIS nomes das opções escritos DENTRO dela (ex:
    'Division' | 'Subdivision'). Qual das duas está ativa vira uma
    cápsula colorida/preenchida com texto branco em negrito, um pouco
    MAIOR que a outra (ver '.painel-edicao-segmentado-opcao' em
    edit_menu.css); a inativa fica lisa, sem preenchimento — pedido
    explícito revisando a v1 (que tinha os 2 nomes como rótulos SOLTOS
    flanqueando um interruptor pequeno tipo <input type=checkbox>, sem
    rótulo de linha nenhum e sem cor nenhuma indicando o lado ativo).

    Reaproveita o MESMO id pattern ({'type': 'toggle', 'index':
    indice}) e a MESMA classe 'ativo' do interruptor clássico (ver
    _toggle acima) — o callback genérico 'alternar_toggle'
    (callbacks.py) só manipula essa classe via string, não olha pra
    estrutura interna do botão, então funciona sem nenhuma mudança ali.

    'ativo=False' = opção ESQUERDA selecionada (roxo, --cor-accent-
    divisao); 'ativo=True' = opção DIREITA (verde, --cor-accent-
    subdivisao) — MESMAS duas cores em TODOS os toggles duplos do
    painel (pedido explícito: "isso ocorre em todas as cores dessa
    divisão"), a mesma dupla de cores já usada nos 3 sliders de
    'Division/Subdivision' (ver .painel-edicao-ticks-sliders.modo-
    subdivisao) — não uma cor inventada nova por par.
    """
    return html.Div(className='painel-edicao-campo painel-edicao-campo-linha', children=[
        html.Label(rotulo_externo, className='painel-edicao-label'),
        html.Div(className='painel-edicao-segmentado-wrapper', children=[
            html.Button(
                id={'type': 'toggle', 'index': indice},
                className='painel-edicao-segmentado' + (' ativo' if ativo else ''),
                n_clicks=0, type='button',
                children=[
                    html.Span(rotulo_esquerda, className='painel-edicao-segmentado-opcao'),
                    html.Span(rotulo_direita, className='painel-edicao-segmentado-opcao'),
                ],
            ),
        ]),
    ])


def _campo_slider(rotulo, id_slider, valor, minimo, maximo, step=1):
    """
    Rótulo + dcc.Slider NA MESMA LINHA (era empilhado — rótulo em cima,
    barra embaixo; pedido explícito: "todos esses controladores são
    ao lado do texto que os descreve"). Reaproveitado pelos 3 sliders
    de 'Division'/'Subdivision' em 'Ticks' — os mesmos 3 componentes
    (mesmos ids) trocam de VALOR quando o toggle 'Division/
    Subdivision' é ligado/desligado (ver alternar_modo_ticks em
    callbacks.py); não nascem 6 sliders duplicados. Ficam dentro de
    um wrapper com id próprio ('edicao-ticks-sliders-wrapper') cuja
    CLASSE também troca junto (mesmo callback) — é o que permite os
    3 sliders mudarem de cor (teal <-> laranja) ao trocar de modo, ver
    .painel-edicao-ticks-sliders.modo-subdivisao em edit_menu.css.

    O rótulo usa a MESMA largura fixa de toda linha do painel (78px,
    ver '.painel-edicao-campo-linha > .painel-edicao-label' em
    edit_menu.css) — é isso que faz a barra de 'Number:' começar
    exatamente no mesmo x que a de 'Width:'/'Length:'/'Font size:',
    apesar dos rótulos terem comprimentos diferentes (pedido
    explícito: "pra que as barras não fiquem descasadas").
    """
    return html.Div(className='painel-edicao-campo painel-edicao-campo-linha', children=[
        html.Label(rotulo, className='painel-edicao-label'),
        dcc.Slider(
            id=id_slider, min=minimo, max=maximo, step=step, value=valor,
            marks=None, tooltip={'placement': 'bottom', 'always_visible': False},
        ),
    ])


def _linha_eixo(rotulo, id_texto, valor_texto, id_fonte, valor_fonte, id_espacamento, valor_espacamento):
    """
    Uma linha da seção 'Eixos': rótulo + caixa de texto (LaTeX simples,
    ver 'painel-edicao-latex-input' em edit_menu.css e
    traduzirLatexSimples em scripts_js.py) + stepper de tamanho de
    fonte + stepper de espaçamento entre caracteres. Usada 3x
    (Título / Axis x / Axis y) por renderizar_painel_edicao.
    """
    return html.Div(className='painel-edicao-linha-eixo', children=[
        html.Label(rotulo, className='painel-edicao-label'),
        dcc.Input(
            id=id_texto, type='text', value=valor_texto,
            placeholder='enter text...',
            className='painel-edicao-latex-input',
            autoComplete='off',
        ),
        _stepper(id_fonte, valor_fonte, minimo=6, maximo=48, step=1),
        _stepper(id_espacamento, valor_espacamento, minimo=-5, maximo=20, step=1),
    ])


def _linha_limite_eixo(letra_eixo, id_min, id_max, index_cadeado, valor_min=None, valor_max=None, travado=False):
    """
    Uma linha da sub-seção 'Limits' dentro de 'Eixos': [min] < x <
    [max] + botão de autoscale (limpa min/max — volta o eixo a decidir
    sozinho o range a partir dos dados, ver aplicar_preferencias_eixos
    em callbacks.py) + botão de cadeado (só reflete visualmente
    'travado' — ver PreferenciasLimiteEixo.travado em
    src/core/arquivo.py; o que realmente TRAVA o eixo nesse
    intervalo é min/max estarem os dois preenchidos, o cadeado é só
    pra lembrar visualmente desse estado entre uma edição e outra).

    'index_cadeado' é o 'index' do par {'type': 'limite-cadeado',
    'index': ...} — precisa ser único (aqui: 'x' / 'y').
    """
    return html.Div(className='painel-edicao-linha-limite', children=[
        dcc.Input(
            id=id_min, type='number', placeholder='min', value=valor_min,
            className='painel-edicao-limite-input',
        ),
        html.Span('<', className='painel-edicao-limite-simbolo'),
        html.Span(letra_eixo, className='painel-edicao-limite-eixo-letra'),
        html.Span('<', className='painel-edicao-limite-simbolo'),
        dcc.Input(
            id=id_max, type='number', placeholder='max', value=valor_max,
            className='painel-edicao-limite-input',
        ),
        html.Button(
            '🔄', id={'type': 'limite-autoscale', 'index': index_cadeado},
            className='painel-edicao-limite-btn', title='Autoscale (recalcula os limites)',
            n_clicks=0,
        ),
        html.Button(
            '🔒' if travado else '🔓', id={'type': 'limite-cadeado', 'index': index_cadeado},
            className='painel-edicao-limite-btn travado' if travado else 'painel-edicao-limite-btn',
            title='Travar eixo neste intervalo',
            n_clicks=0,
        ),
    ])


def renderizar_painel_edicao(estado, aba_ativa, coluna_selecionada=None):
    """
    Conteúdo do painel-direito depois que o usuário clica em 'Iniciar
    edição': por enquanto só a seção 'Curva' do desenho original (cor /
    espessura / estilo de linha da curva escolhida) — as seções de eixo
    X, eixo Y e 'Ticks and Marks' ainda não foram implementadas, ficam
    para uma próxima etapa (o painel pode crescer com mais html.Div de
    'painel-edicao-secao' abaixo desta, sem mexer no que já existe).

    O card 'Curva' agora é SEMPRE montado, mesmo sem nenhum canal
    plotado — antes, sem canal, a função devolvia um texto solto no
    lugar do card inteiro, então o próprio 'Dado' (a caixa de seleção
    que devia só listar os canais plotados) nem chegava a existir. A
    caixa "só tem que ler quais canais estão plotados; se nenhum foi
    marcado, ela fica vazia" — é isso que o bloco abaixo faz: com
    'colunas' vazia, 'opcoes_dado' vira [], o dropdown nasce sem valor
    e os demais controles (espessura/cor/estilo) nascem desabilitados,
    porque não existe curva nenhuma pra aplicar espessura/cor/estilo.

    'coluna_selecionada' é opcional: se None ou se a coluna passada não
    estiver mais no gráfico (ex: usuário desmarcou o canal), cai na
    primeira coluna plotada (ou fica None, se não houver nenhuma).
    """
    colunas = colunas_plotadas(estado, aba_ativa)
    arquivo = estado.arquivos[aba_ativa]

    sem_canal = not colunas
    if coluna_selecionada not in colunas:
        coluna_selecionada = colunas[0] if colunas else None

    opcoes_dado = [{'label': arquivo.rotulo(coluna), 'value': coluna} for coluna in colunas]

    if sem_canal:
        cor_atual, espessura_atual, estilo_atual = PALETA_EDICAO_CORES[0], 1.0, 'solid'
        marcador_atual = 'none'
        tamanho_marcador_atual = 7.0
    else:
        # Se a curva ainda não foi editada, os controles nascem refletindo
        # exatamente o que já está desenhado agora (mesma cor da paleta
        # fixa, espessura/estilo padrão) — ver mesma lógica de fallback em
        # construir_figura_serie_temporal (plotter.py), pra painel e
        # gráfico nunca mostrarem valores diferentes pra mesma curva.
        prefs = arquivo.preferencias.por_canal.get(coluna_selecionada)
        indice_cor = colunas.index(coluna_selecionada)
        cor_atual = prefs.cor if (prefs and prefs.cor) else cor_da_coluna(indice_cor)
        espessura_atual = prefs.espessura if prefs else 1.0
        estilo_atual = prefs.estilo_linha if prefs else 'solid'
        marcador_atual = prefs.marcador if prefs else 'none'
        tamanho_marcador_atual = prefs.tamanho_marcador if prefs else 7.0

    # A barra 'Marker size' só faz sentido com um marcador escolhido (sem
    # marcador, o tamanho não tem nada pra controlar) — nasce visível ou
    # escondida de acordo com 'marcador_atual' e alterna sozinha depois
    # disso via callback (ver alternar_barra_tamanho_marcador em
    # callbacks.py, disparado pelo próprio dropdown 'Marker').
    estilo_barra_tamanho_marcador = (
        {} if marcador_atual and marcador_atual != 'none' else {'display': 'none'}
    )

    conteudo_curva = [
        html.Div(className='painel-edicao-campo', children=[
            html.Label('Dado:', htmlFor='edicao-curva-dado', className='painel-edicao-label'),
            dcc.Dropdown(
                id='edicao-curva-dado',
                options=opcoes_dado,
                value=coluna_selecionada,
                placeholder='Nenhum canal plotado',
                disabled=sem_canal,
                clearable=False,
                searchable=False,
                className='painel-edicao-dropdown',
            ),
        ]),

        html.Div(className='painel-edicao-campo', children=[
            html.Label('Thickness:', className='painel-edicao-label'),
            dcc.Slider(
                id='edicao-curva-espessura',
                min=1, max=6, step=0.5,
                value=espessura_atual,
                marks=None,
                disabled=sem_canal,
                tooltip={'placement': 'bottom', 'always_visible': False},
            ),
        ]),

        html.Div(className='painel-edicao-campo painel-edicao-linha', children=[
            html.Div(className='painel-edicao-subcampo', children=[
                html.Label('cor:', className='painel-edicao-label'),
                dcc.Store(id={'type': 'cor-store', 'index': 'curva'}, data=cor_atual),
                _seletor_cor(cor_atual, 'curva'),
            ]),
            html.Div(className='painel-edicao-subcampo', children=[
                html.Label('Style:', htmlFor='edicao-curva-estilo', className='painel-edicao-label'),
                dcc.Dropdown(
                    id='edicao-curva-estilo',
                    options=OPCOES_ESTILO_LINHA,
                    value=estilo_atual,
                    disabled=sem_canal,
                    clearable=False,
                    searchable=False,
                    className='painel-edicao-dropdown painel-edicao-dropdown-estilo',
                ),
            ]),
            html.Div(className='painel-edicao-subcampo', children=[
                html.Label('Marker:', htmlFor='edicao-curva-marcador', className='painel-edicao-label'),
                dcc.Dropdown(
                    id='edicao-curva-marcador',
                    options=OPCOES_MARCADOR,
                    value=marcador_atual,
                    disabled=sem_canal,
                    clearable=False,
                    searchable=False,
                    className='painel-edicao-dropdown painel-edicao-dropdown-marcador',
                ),
            ]),
        ]),

        # Só existe enquanto 'Marker' != 'none' (ver estilo_barra_tamanho_
        # marcador acima e alternar_barra_tamanho_marcador em callbacks.py,
        # que reagem ao dropdown 'Marker' e escondem/mostram este Div
        # inteiro) — tirar o marcador esconde a barra de novo, sem apagar
        # o valor ajustado (ele volta a aparecer se o marcador for
        # reselecionado).
        html.Div(
            id='edicao-curva-tamanho-marcador-wrapper',
            className='painel-edicao-campo',
            style=estilo_barra_tamanho_marcador,
            children=[
                html.Label('Marker size:', className='painel-edicao-label'),
                dcc.Slider(
                    id='edicao-curva-tamanho-marcador',
                    min=2, max=20, step=1,
                    value=tamanho_marcador_atual,
                    marks=None,
                    disabled=sem_canal,
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ],
        ),
    ]

    # 'Eixos' — igual a 'Ticks'/'Outros' (comentário nessas seções
    # logo abaixo): valores de partida vêm de 'arquivo.preferencias'
    # (titulo/titulo_eixo_x/titulo_eixo_y — PreferenciasTexto; limite_x/
    # limite_y — PreferenciasLimiteEixo, ver src/core/arquivo.py), não
    # mais fixos/vazios — e cada edição grava de volta e redesenha o
    # gráfico (ver aplicar_preferencias_eixos/alternar_cadeado_limite/
    # limpar_limite_eixo em callbacks.py).
    titulo_prefs = arquivo.preferencias.titulo
    eixo_x_prefs = arquivo.preferencias.titulo_eixo_x
    eixo_y_prefs = arquivo.preferencias.titulo_eixo_y
    limite_x_prefs = arquivo.preferencias.limite_x
    limite_y_prefs = arquivo.preferencias.limite_y

    conteudo_eixos = [
        html.Div(className='painel-edicao-eixos-cabecalho', children=[
            html.Div(className='painel-edicao-eixos-cabecalho-rotulo'),
            html.Span('Aa', className='painel-edicao-eixos-cabecalho-coluna'),
            html.Span('↔', className='painel-edicao-eixos-cabecalho-coluna'),
        ]),
        _linha_eixo(
            'Title:', 'edicao-eixo-titulo-texto', titulo_prefs.texto,
            'edicao-eixo-titulo-fonte', titulo_prefs.fonte,
            'edicao-eixo-titulo-espacamento', titulo_prefs.espacamento,
        ),
        _linha_eixo(
            'Axis x:', 'edicao-eixo-x-texto', eixo_x_prefs.texto,
            'edicao-eixo-x-fonte', eixo_x_prefs.fonte,
            'edicao-eixo-x-espacamento', eixo_x_prefs.espacamento,
        ),
        _linha_eixo(
            'Axis y:', 'edicao-eixo-y-texto', eixo_y_prefs.texto,
            'edicao-eixo-y-fonte', eixo_y_prefs.fonte,
            'edicao-eixo-y-espacamento', eixo_y_prefs.espacamento,
        ),

        html.Hr(className='painel-edicao-separador'),

        html.Div('Limits:', className='painel-edicao-limite-titulo'),
        _linha_limite_eixo(
            'x', 'edicao-eixo-x-limite-min', 'edicao-eixo-x-limite-max', 'x',
            valor_min=limite_x_prefs.minimo, valor_max=limite_x_prefs.maximo,
            travado=limite_x_prefs.travado,
        ),
        _linha_limite_eixo(
            'y', 'edicao-eixo-y-limite-min', 'edicao-eixo-y-limite-max', 'y',
            valor_min=limite_y_prefs.minimo, valor_max=limite_y_prefs.maximo,
            travado=limite_y_prefs.travado,
        ),
    ]

    # 'Ticks' — ao contrário de 'Eixos' (ainda placeholder de valores),
    # esta seção JÁ lê os valores de partida direto de
    # 'arquivo.preferencias' (ver PreferenciasTicksEixo em
    # src/core/arquivo.py) — abrir a edição herda o que está REALMENTE
    # desenhado no gráfico agora, não um valor fixo de fábrica. A
    # partir daqui, qualquer alteração (slider, toggle, dropdown de
    # eixo) grava de volta nesse mesmo objeto e redesenha a figura
    # (ver sincronizar_campos_ticks/aplicar_preferencias_ticks em
    # callbacks.py).
    #
    # O dropdown 'Eixo' nasce em 'x' (não 'both') — cada eixo tem seu
    # PRÓPRIO conjunto de valores (ticks_x/ticks_y); 'x' é só o ponto
    # de partida mais direto pra mostrar 1 conjunto sem ambiguidade.
    # 'Both' continua disponível pra editar os dois de uma vez (grava
    # o mesmo valor em ticks_x E ticks_y), mas ao SELECIONAR 'Both' os
    # sliders mostram os valores de X (ver _prefs_ticks_eixo em
    # callbacks.py) — se X e Y estiverem diferentes nesse momento, é
    # o valor de X que aparece até a primeira edição igualar os dois.
    ticks_x = arquivo.preferencias.ticks_x
    valores_divisoes_iniciais = ticks_x.divisoes

    conteudo_ticks = [
        html.Div(className='painel-edicao-campo painel-edicao-campo-linha', children=[
            html.Label('Eixo:', htmlFor='edicao-ticks-eixo', className='painel-edicao-label'),
            # Wrapper PRÓPRIO ('painel-edicao-dropdown-largura') em
            # volta do dcc.Dropdown — BUG corrigido: 'flex: 1 1 auto'
            # direto em '.painel-edicao-dropdown' não bastava porque
            # esse nome de classe pode não cair no elemento que o
            # Dash realmente usa como FILHO DIRETO desta linha (o
            # componente de dropdown embrulha a própria estrutura
            # interna, então o seletor '> .painel-edicao-dropdown' às
            # vezes não batia em nada, e a caixa continuava do tamanho
            # do texto selecionado — 'X' estreita, 'Both' larga). Com
            # um <div> AUTORAL em volta, garantido como filho direto
            # de verdade, o flex:1 tem onde grudar; o dropdown em si
            # só precisa preencher esse wrapper (width: 100%, ver
            # '.painel-edicao-dropdown-largura .painel-edicao-
            # dropdown' em edit_menu.css — descendente, não filho
            # direto, então funciona não importa quantos níveis o
            # componente insira por dentro).
            html.Div(className='painel-edicao-dropdown-largura', children=[
                dcc.Dropdown(
                    id='edicao-ticks-eixo',
                    options=[
                        {'label': 'X', 'value': 'x'},
                        {'label': 'Y', 'value': 'y'},
                        {'label': 'Both', 'value': 'both'},
                    ],
                    value='x',
                    clearable=False, searchable=False,
                    className='painel-edicao-dropdown',
                ),
            ]),
        ]),

        # Toggle 'Major' <-> 'Minor' (nomes exibidos — o índice
        # continua 'ticks-subdivisao' por baixo, mesmo significado de
        # sempre: Major = Division, Minor = Subdivision, ver
        # sincronizar_campos_ticks/aplicar_preferencias_ticks em
        # callbacks.py, que só olham a classe 'ativo', nunca o texto).
        # 'Major'/'Minor' (era 'Division'/'Subdivision') — pedido
        # explícito, pra caber dentro da pílula sem cortar/comprimir
        # (ver tamanho fixo calculado em '.painel-edicao-segmentado-
        # opcao', edit_menu.css). A POSIÇÃO/COR da cápsula ativa já diz
        # qual dos dois modos está sendo editado agora — não precisa de
        # um título 'Divisions' separado em cima nem de um segundo
        # toggle 'Subdivision' lá embaixo (era redundante com este).
        # Logo abaixo do 'Eixo' por pedido: é o primeiro controle que o
        # usuário vê ao abrir 'Ticks', antes mesmo dos sliders que ele
        # afeta.
        _linha_toggle_dupla('Type:', 'Major', 'Minor', 'ticks-subdivisao'),

        html.Hr(className='painel-edicao-separador'),

        # --- REORGANIZAÇÃO DE LAYOUT (pedido explícito, mockup
        # fornecido) — 3 sub-seções com título próprio ('Tick size' /
        # 'Position' / 'Label'), mesma classe/estilo de 'Limits:' na
        # seção 'Eixos' logo acima ('.painel-edicao-limite-titulo' —
        # maiúsculas pequenas, cor apagada; reaproveitada aqui, não é
        # exclusiva de 'Limits'). NENHUM id/comportamento mudou, só a
        # ORDEM e o agrupamento visual dos mesmos controles de sempre:
        #   - 'Tick size': os 3 sliders (Number/Width/Length), que
        #     antes vinham soltos direto após o toggle Division/
        #     Subdivision, sem cabeçalho nenhum os identificando como
        #     grupo.
        #   - 'Position': 'Outward/Inward' (antes ficava sozinho lá no
        #     FINAL do painel, depois até da fonte do label — sem
        #     relação visual nenhuma com 'Both sides', apesar dos dois
        #     serem sobre POSICIONAMENTO da marca) + 'Both sides'
        #     (antes ficava logo após os sliders de tamanho, sem
        #     conexão visual com 'Outward/Inward').
        #   - 'Label': só o slider de fonte, que antes vinha solto
        #     depois do separador, sem título nenhum contextualizando
        #     que aquele controle é sobre o RÓTULO da marca.
        html.Div('Tick size:', className='painel-edicao-limite-titulo'),
        html.Div(
            id='edicao-ticks-sliders-wrapper',
            className='painel-edicao-ticks-sliders',
            children=[
                _campo_slider(
                    # minimo=1 (era 2): 'Number' agora é o número de
                    # marcas NOVAS entre os extremos do eixo (ver
                    # _tick0_e_dtick em plotter.py) — 1 é um valor
                    # válido e útil (1 marca no meio do intervalo),
                    # não um caso degenerado a evitar.
                    'Number:', 'edicao-ticks-numero',
                    valores_divisoes_iniciais['numero'], minimo=1, maximo=20, step=1,
                ),
                _campo_slider(
                    'Width:', 'edicao-ticks-largura',
                    valores_divisoes_iniciais['largura'], minimo=1, maximo=10, step=1,
                ),
                _campo_slider(
                    'Length:', 'edicao-ticks-comprimento',
                    valores_divisoes_iniciais['comprimento'], minimo=1, maximo=20, step=1,
                ),
            ],
        ),

        html.Hr(className='painel-edicao-separador'),

        html.Div('Position:', className='painel-edicao-limite-titulo'),
        _linha_toggle_dupla('Direction:', 'Outward', 'Inward', 'ticks-direcao', ativo=(ticks_x.direcao == 'inside')),
        # 'Single'/'Both' (era um interruptor de rótulo único 'Both
        # sides') — convertido pro MESMO componente segmentado dos
        # outros dois toggles duplos deste painel (pedido explícito:
        # "os dois botões ali devem ter o mesmo comportamento e o
        # mesmo tamanho" [de Direction]). Semântica igual: 'ativo'
        # continua = "mostrar ticks dos dois lados" — só a opção da
        # DIREITA (verde) mudou de rótulo 'Both sides' pra 'Both', com
        # 'Single' aparecendo agora como a opção da esquerda (roxa)
        # quando desativado, em vez de um interruptor sem texto nenhum
        # do lado esquerdo.
        _linha_toggle_dupla('Side:', 'Single', 'Both', 'ticks-both-sides', ativo=ticks_x.both_sides),

        html.Hr(className='painel-edicao-separador'),

        html.Div('Label:', className='painel-edicao-limite-titulo'),
        # Fonte dos rótulos de tick: NÃO troca de valor com o toggle
        # Division/Subdivision (é uma propriedade do eixo inteiro, só
        # existe UM tamanho de fonte pros números — não tem 'fonte dos
        # labels das subdivisões' separada), mas fica ESCONDIDA em
        # modo 'Subdivision' — a pedido explícito: como as marcas
        # secundárias não têm número/rótulo nenhum do lado (só as
        # principais têm), o controle de fonte não tem o que afetar
        # visivelmente nesse modo, então melhor sumir do que ficar
        # solto sem efeito aparente. Ver 'edicao-ticks-fonte-labels-
        # wrapper' (Output em sincronizar_campos_ticks, callbacks.py).
        # Rótulo do campo agora só 'Font size:' (era 'Label font:') —
        # o título da sub-seção 'Label:' logo acima já deixa claro do
        # que se trata, repetir 'Label' no campo ficaria redundante
        # (mesma simplificação do mockup fornecido).
        html.Div(
            id='edicao-ticks-fonte-labels-wrapper',
            children=_campo_slider(
                'Font size:', 'edicao-ticks-fonte-labels',
                ticks_x.fonte_labels, minimo=6, maximo=24, step=1,
            ),
        ),
    ]

    # 'Outros' — Grid (on/off) e a cor de fundo da área de plotagem.
    # Igual a 'Ticks': valores de partida vêm de 'arquivo.preferencias'
    # (grid/cor_fundo — ver PreferenciasGrafico em src/core/arquivo.py),
    # não de um padrão fixo — e cada alteração grava de volta e
    # redesenha o gráfico (ver aplicar_preferencias_outros em
    # callbacks.py).
    #
    # O seletor de cor em si é EXATAMENTE o mesmo widget do campo 'cor'
    # de 'Curva' (mesma _seletor_cor, mesmo _campo_rgb, mesmo JS de
    # arraste) — só o destino muda: aqui grava em 'preferencias.
    # cor_fundo', não numa curva. Por isso fica dentro de um
    # 'painel-edicao-subcampo' de largura fixa (86px, igual à coluna
    # 'cor:' de Curva) em vez de um 'painel-edicao-campo' esticado —
    # sem isso a caixinha vira uma barra comprida em vez do
    # quadradinho compacto que aparece em Curva.
    cor_fundo_atual = arquivo.preferencias.cor_fundo or '#FFFFFF'

    conteudo_outros = [
        _linha_toggle('Grid', 'outros-grid', ativo=arquivo.preferencias.grid),

        html.Div(className='painel-edicao-campo', children=[
            html.Label('Background:', className='painel-edicao-label'),
            html.Div(className='painel-edicao-subcampo', style={'flex': '0 0 auto', 'width': '86px'}, children=[
                dcc.Store(id={'type': 'cor-store', 'index': 'fundo'}, data=cor_fundo_atual),
                _seletor_cor(cor_fundo_atual, 'fundo'),
            ]),
        ]),
    ]

    # 'fechar-edicao-curva' (mesmo id de antes) agora fecha o painel
    # inteiro, não só a seção 'Curva' — por isso saiu do cabeçalho da
    # seção e virou um cabeçalho geral, acima do acordeão. Nenhum
    # callback que já usava esse id precisou mudar (ver
    # fechar_edicao_curva em callbacks.py).
    return [
        html.Div(className='painel-edicao-cabecalho-geral', children=[
            html.Span('Opções do gráfico', className='painel-edicao-titulo-geral'),
            html.Button(
                '✕', id='fechar-edicao-curva', className='painel-edicao-fechar-btn',
                title='Fechar edição', n_clicks=0,
            ),
        ]),
        # 'aberta=False': o painel de edição nasce com TODAS as seções
        # recolhidas (igual 'Eixos'/'Ticks'/'Outros' logo abaixo, que
        # já não passavam 'aberta' nenhum = usam o padrão False de
        # _secao_colapsavel) — 'Curva' não tem mais tratamento especial
        # de vir aberta por padrão.
        _secao_colapsavel('curva', 'Curva', conteudo_curva),
        _secao_colapsavel('eixos', 'Eixos', conteudo_eixos),
        _secao_colapsavel('ticks', 'Ticks', conteudo_ticks),
        _secao_colapsavel('outros', 'Outros', conteudo_outros),
    ]


def renderizar_grafico_com_fechar(fig):
    """
    Embrulha a figura num container com o botão 'X' no canto superior
    direito. Clicar nele não fecha arquivo nenhum — só volta o
    container-grafico pra grade de opções (fechar de verdade, via aba,
    é outra ação, que já reseta tudo porque não sobra arquivo carregado).
    """
    return html.Div(className='grafico-wrapper', children=[
        html.Button('✕', id='fechar-grafico', className='botao-fechar-grafico', n_clicks=0),
        # 'config.edits.shapePosition=True' — permissão GLOBAL do
        # Plotly pra shapes arrastáveis, PAUSADA junto com o resto da
        # interação de arraste das guias de corte (ver comentário
        # completo com o passo a passo pra retomar em
        # aplicar_guias_corte, src/core/plotting/plotter.py). Sem
        # nenhum shape com 'editable=True' no momento (todos ficam
        # explicitamente False enquanto isso durar), manter ou não
        # este config não muda nada na prática — comentado só por
        # consistência com o resto da pausa.
        # config={'edits': {'shapePosition': True}},
        dcc.Graph(id='grafico-plotly-real', figure=fig, className='grafico-plotly'),
    ])

def _botao_token_calculadora(display, codigo, classe_extra='', titulo=None):
    """
    Um botão de token (número/operador/função/operação/coluna) — todos
    usam o MESMO padrão de id, {'type': 'calc-token', 'display':...,
    'codigo':..., 'classe':...}: o próprio id já carrega o que precisa
    ser anexado à expressão, então UM único callback (ver
    registrar_token_calculadora, callbacks.py) cobre todo mundo sem
    precisar de uma tabela de consulta à parte no servidor.

    'classe' (a MESMA 'classe_extra' que colore este botão aqui, ex:
    'calculadora-token-coluna') viaja junto no id só pra
    'registrar_token_calculadora' poder gravá-la junto do token em
    'calc-expressao-store' — é o que permite a barra (ver
    renderizar_calculadora_barra) desenhar cada pedaço da expressão
    como um "chip" colorido igual ao botão original, não texto solto.

    'titulo' vira o tooltip nativo (atributo 'title' do HTML) — usado
    pelos botões de COLUNA (ver colunas_pares em
    renderizar_calculadora_botoes) pra mostrar o nome COMPLETO do canal
    ao passar o mouse, já que o texto visível do botão pode estar
    truncado (nomes longos viram '6 primeiros caracteres + ..', pra
    todo botão de coluna manter o MESMO tamanho fixo).
    """
    return html.Button(
        display,
        id={'type': 'calc-token', 'display': display, 'codigo': codigo, 'classe': classe_extra},
        className='calculadora-token ' + classe_extra,
        n_clicks=0,
        title=titulo,
    )


def _truncar_nome_coluna_calculadora(rotulo, limite=8):
    """
    Todo botão de COLUNA na calculadora precisa ter o MESMO tamanho
    fixo, não importa o nome do canal (pedido explícito) — nomes até
    'limite' (8) caracteres aparecem inteiros; nomes maiores viram os
    6 PRIMEIROS caracteres + '..' (dois pontos, não reticências de
    3 pontos) — sempre no máximo 8 caracteres visíveis, então a
    largura fixa do botão (ver '.calculadora-token-coluna' em
    edit_menu.css) nunca precisa cortar/cabe sempre confortável.
    """
    if len(rotulo) > limite:
        return rotulo[:6] + '..'
    return rotulo


def _grupo_calculadora(titulo, pares_display_codigo, classe_extra=''):
    return html.Div(className='calculadora-grupo', children=[
        html.Div(titulo, className='calculadora-grupo-titulo'),
        html.Div(className='calculadora-grupo-botoes', children=[
            _botao_token_calculadora(display, codigo, classe_extra) for display, codigo in pares_display_codigo
        ]),
    ])


def renderizar_calculadora_barra(estado, aba_ativa, tokens_expressao=None,
                                  tipo_destino='nova', coluna_destino=None,
                                  nome_novo_canal=None):
    """
    A BARRA de cálculo — o pedaço de CIMA de '#area-modo-nova-analise'
    (ver renderizar_area_calculadora_completa logo abaixo, que embrulha
    só esta barra; o gráfico real fica embaixo). Mostra a expressão sendo
    construída — como uma sequência de "chips" coloridos, um por
    token clicado (ver 'calculadora-chip' abaixo — cada chip reaproveita
    a MESMA cor do botão que o gerou, só numa escala menor, pra não
    tomar a barra inteira), o seletor "Nova coluna" / "Coluna
    existente", o campo de nome (ou o dropdown de coluna a
    sobrescrever, conforme o seletor) e Criar/Apagar/Limpar.

    Os GRUPOS DE BOTÕES (calculadora inteira — números/operadores/
    funções/operações/colunas) não moram mais aqui — foram pro painel
    de edição, ver renderizar_calculadora_botoes logo abaixo.

    Derivada/Integral/Média/Máximo/Mínimo (ver OPERACOES_RAPIDAS,
    calculadora.py) viraram tokens comuns iguais a sin(/cos( — não
    existe mais um "resultado pendente" separado da expressão; tudo
    que aparece aqui é sempre a expressão token a token, avaliada de
    verdade só na hora de 'Criar' (ver avaliar_expressao_calculadora).
    """
    tokens_expressao = tokens_expressao or []

    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    opcoes_colunas_destino = []
    if arquivo:
        # 'colunas_disponiveis_calculo' (não 'colunas_visiveis') — pra
        # poder sobrescrever até um canal que esteja atribuído a X/Y
        # do gráfico agora (ver docstring completa em Arquivo.
        # colunas_disponiveis_calculo, src/core/arquivo.py).
        opcoes_colunas_destino = [
            {'label': arquivo.rotulo(nome), 'value': nome} for nome in arquivo.colunas_disponiveis_calculo()
        ]

    # Nome-input e dropdown-de-coluna-existente nascem OS DOIS sempre
    # no DOM (um deles só escondido via CSS, classe
    # 'calculadora-oculto' — ver central_menu.css) em vez de um
    # substituir o outro condicionalmente: assim os Estados que os
    # callbacks leem (State('calc-nome-input','value')/
    # State('calc-coluna-destino','value')) sempre encontram os dois
    # componentes de verdade no DOM, nunca 'None' por o componente
    # simplesmente não existir na renderização atual.
    modo_nova = tipo_destino != 'existente'

    if tokens_expressao:
        # Cada token vira um "chip" pequeno com a MESMA classe de cor
        # do botão original ('t["classe"]', gravado por
        # registrar_token_calculadora a partir do id do botão clicado —
        # ver _botao_token_calculadora) — '.calculadora-chip' (central_
        # menu.css) é quem encolhe a escala (fonte/padding menores que
        # os botões de verdade da calculadora), reaproveitando a MESMA
        # cor de fundo/borda pra continuar reconhecível de relance.
        conteudo_expressao = [
            html.Span(t['display'], className='calculadora-token calculadora-chip ' + t.get('classe', ''))
            for t in tokens_expressao
        ]
    else:
        conteudo_expressao = html.Span(' ', className='calculadora-chip-vazio')

    return html.Div(className='calculadora-barra-central-conteudo', children=[
        # Título — mesmo padrão visual dos grupos de botões
        # ('.calculadora-grupo-titulo', reaproveitado aqui), pedido
        # explícito pra a barra ter uma identificação igual a
        # 'Operações básicas' e os outros containers.
        html.Div('Barra de cálculo', className='calculadora-grupo-titulo calculadora-barra-titulo'),
        # Voltamos pro design ORIGINAL em linha única (desfaz a grade
        # 3x3 do patch anterior) — ORDEM pedida explicitamente:
        # tipo-destino -> área de cálculo -> nome/coluna-destino ->
        # Criar. Apagar/C não ficam mais soltos na linha: agora moram
        # dentro de '.calculadora-criar-popover', que só aparece
        # quando o mouse passa por cima de 'Criar' (pedido explícito)
        # — ver '.calculadora-criar-wrapper' em central_menu.css.
        html.Div(className='calculadora-barra-linha', children=[
            dcc.Dropdown(
                id='calc-tipo-destino',
                options=[
                    {'label': 'Nova coluna', 'value': 'nova'},
                    {'label': 'Coluna existente', 'value': 'existente'},
                ],
                value=tipo_destino, clearable=False, searchable=False,
                className='calculadora-tipo-destino',
            ),
            html.Div(conteudo_expressao, id='calc-expressao-display', className='calculadora-expressao'),
            # 'value' explícito: a barra é redesenhada a cada token/⌫/C, e
            # sem isso o nome digitado sumia no primeiro clique (os
            # callbacks repassam o valor atual do campo como State).
            dcc.Input(
                id='calc-nome-input', type='text', placeholder='nova coluna',
                value=nome_novo_canal or '',
                className='calculadora-nome-input' + ('' if modo_nova else ' calculadora-oculto'),
                maxLength=80,
            ),
            dcc.Dropdown(
                id='calc-coluna-destino',
                options=opcoes_colunas_destino, value=coluna_destino,
                placeholder='sobrescrever qual coluna?',
                className='calculadora-coluna-destino' + ('' if not modo_nova else ' calculadora-oculto'),
            ),
            # 'calculadora-criar-wrapper': só existe pra dar um
            # 'position:relative' de referência pro popover — o
            # ':hover' que revela Apagar/C é neste wrapper (cobre o
            # botão Criar + a área do popover), não só no botão Criar
            # sozinho, senão o popover sumiria assim que o mouse saísse
            # de cima do botão pra descer até ele.
            html.Div(className='calculadora-criar-wrapper', children=[
                # 'disabled' + classe extra quando a expressão ainda
                # não está pronta pra virar coluna (ver
                # calc_criar_desabilitado, calculadora.py — parêntese
                # aberto OU nome/coluna-destino vazio) — pedido
                # explícito: antes só o parêntese travava o botão;
                # faltava cobrir o caso de tentar 'Criar' sem ter
                # escrito um nome pra coluna nova (ou sem escolher qual
                # sobrescrever no modo 'Coluna existente'), que hoje só
                # falhava DEPOIS do clique com mensagem de erro. A
                # VALIDAÇÃO DE VERDADE continua em criar_canal_
                # calculado_calculadora/avaliar_expressao_calculadora
                # (defesa em profundidade — 'disabled' no HTML não
                # impede um clique disparado por outro meio), isto
                # aqui é só o aviso visual antecipado.
                html.Button(
                    'Criar', id='calc-criar',
                    className='calculadora-btn-criar' + (
                        ' calculadora-btn-criar-desabilitado'
                        if calc_criar_desabilitado(tokens_expressao, tipo_destino, nome_novo_canal, coluna_destino)
                        else ''
                    ),
                    disabled=calc_criar_desabilitado(tokens_expressao, tipo_destino, nome_novo_canal, coluna_destino),
                    n_clicks=0,
                ),
                # Apagar/C — mesmo par de ações que já existe duplicado
                # no teclado do menu ao lado ('calc-apagar-teclado'/
                # 'calc-limpar-teclado', mais abaixo nesta função) —
                # aqui usam as MESMAS classes visuais deles
                # ('calculadora-btn-c'/'calculadora-btn-del', ver
                # edit_menu.css), pedido explícito pra terem o mesmo
                # aspecto (fundo vermelho translúcido, não sólido).
                html.Div(className='calculadora-criar-popover', children=[
                    # '⌫' remove só o ÚLTIMO token inteiro (não um
                    # caractere — ver docstring de 'calc-expressao-
                    # store', layout.py) — separado de 'C' (que zera
                    # tudo de uma vez), pra corrigir um clique errado
                    # sem perder a expressão inteira.
                    html.Button('⌫', id='calc-apagar', className='calculadora-btn-del', n_clicks=0,
                                title='Apagar último'),
                    html.Button('C', id='calc-limpar', className='calculadora-btn-c', n_clicks=0,
                                title='Limpar tudo'),
                ]),
            ]),
        ]),
    ])



def renderizar_area_calculadora_completa(estado, aba_ativa, tokens_expressao=None,
                                          tipo_destino='nova', coluna_destino=None,
                                          nome_novo_canal=None):
    """
    Conteúdo de '#area-modo-nova-analise': só a barra de cálculo
    ('renderizar_calculadora_barra' acima). Essa área fica EM CIMA do
    gráfico real, que continua visível e funcionando embaixo — não há
    mais miniatura (ver '.centro' em central_menu.css e layout.py).
    """
    return [
        renderizar_calculadora_barra(estado, aba_ativa, tokens_expressao, tipo_destino, coluna_destino,
                                     nome_novo_canal),
    ]


def renderizar_calculadora_botoes(estado, aba_ativa):
    """
    Os GRUPOS DE BOTÕES da calculadora — vivem em
    '#area-modo-nova-analise-edicao' (painel de edição, cobrindo tudo
    com watermark de analysis.svg, ver edit_menu.css), NÃO mais dentro
    do gráfico. Layout MAIS VERTICAL de propósito (grupos empilhados,
    um por linha, cada um com seus botões em grade estreita) — a
    versão anterior ficava na área central, larga, com os grupos lado
    a lado; aqui o painel é estreito (~400px, mesma largura de sempre)
    e alto, então empilhar verticalmente aproveita o espaço de
    verdade, em vez de forçar quebra de linha toda hora.

    Diferente da barra (renderizar_calculadora_barra), este bloco NÃO
    precisa ser reconstruído a cada clique de token — os botões em si
    não mudam com a expressão, só a barra reflete o que foi clicado.
    Só precisa recarregar quando o MODO liga (arquivo pode ter mudado)
    ou a aba ativa muda enquanto o modo está ligado.
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    colunas_pares = []
    if arquivo:
        # 'colunas_disponiveis_calculo' (não 'colunas_visiveis') — os
        # botões de coluna da calculadora precisam continuar oferecendo
        # um canal mesmo depois dele virar X/Y do gráfico (ver
        # docstring completa em Arquivo.colunas_disponiveis_calculo,
        # src/core/arquivo.py — pedido explícito: "posso estar exibindo
        # P1 no gráfico e querer fazer contas com P1"). Antes seguia
        # 'colunas_visiveis()', a MESMA lista da barra lateral — um
        # canal virar X/Y não deveria também tirá-lo da disponibilidade
        # de cálculo, são preocupações diferentes.
        for nome_interno in arquivo.colunas_disponiveis_calculo():
            rotulo = arquivo.rotulo(nome_interno)
            # 'display' é o texto TRUNCADO (o que aparece no botão e no
            # chip da barra — ver _truncar_nome_coluna_calculadora
            # acima); 'rotulo' (o nome COMPLETO) vira o tooltip do
            # botão, pra quem precisar conferir o nome inteiro sem
            # precisar abrir a lista de canais.
            colunas_pares.append((_truncar_nome_coluna_calculadora(rotulo), f'col[{nome_interno!r}]', rotulo))

    return html.Div(className='calculadora-botoes', children=[
        html.Div(className='calculadora-grupo', children=[
            html.Div('Calculadora', className='calculadora-grupo-titulo'),
            # Teclado tipo calculadora CIENTÍFICA de verdade — Funções
            # (coluna estreita à esquerda) + Números (grade 3 colunas,
            # no meio) + Operadores (coluna estreita à direita), mesma
            # disposição geral de uma calculadora física. Antes
            # 'Funções' era um grupo À PARTE, solto embaixo — juntar
            # tudo num teclado só deixa mais óbvio que fazem parte da
            # MESMA ferramenta.
            html.Div(className='calculadora-teclado-corpo', children=[
                # Operações rápidas: coluna própria à esquerda das funções
                # (antes eram um grupo separado, o 3º cartão do painel).
                # São TOKENS comuns, como sin(/cos( — abrem parêntese, o
                # usuário clica a coluna e fecha (ver OPERACOES_RAPIDAS e
                # avaliar_expressao_calculadora em calculadora.py).
                html.Div(className='calculadora-rapidas-coluna', children=[
                    _botao_token_calculadora(display, codigo, 'calculadora-token-rapido')
                    for display, codigo in OPERACOES_RAPIDAS
                ]),
                html.Div(className='calculadora-funcoes-coluna', children=[
                    _botao_token_calculadora(display, codigo, 'calculadora-token-funcao')
                    for display, codigo in FUNCOES
                ]),
                # 'calculadora-numeros-coluna': C/⌫ + a grade de números
                # AGORA moram dentro do MESMO wrapper (pedido explícito
                # — antes 'calculadora-teclado-topo' era uma linha
                # SOLTA, largura cheia do grupo, alinhada com
                # 'justify-content: flex-end'; como a grade de números
                # fica CENTRALIZADA dentro de 'calculadora-teclado-
                # corpo' — e sua posição horizontal muda conforme a
                # largura da coluna de Funções à esquerda — C/⌫
                # ficavam desalinhados dela, coladas na borda direita
                # do grupo em vez de alinhadas com os números que
                # servem). Com os dois dentro do MESMO wrapper de
                # largura igual à grade (ver '.calculadora-numeros-
                # coluna'/'.calculadora-teclado-topo' em edit_menu.css
                # — mesma largura calculada: 3 botões de 32px + 2 gaps
                # de 5px), C/⌫ ficam sempre exatamente acima da grade,
                # não importa quanto a coluna de Funções cresça/encolha.
                html.Div(className='calculadora-numeros-coluna', children=[
                    html.Div(className='calculadora-teclado-topo', children=[
                        html.Button('C', id='calc-limpar-teclado', className='calculadora-btn-c',
                                    n_clicks=0, title='Limpar tudo'),
                        html.Button('⌫', id='calc-apagar-teclado', className='calculadora-btn-del',
                                    n_clicks=0, title='Apagar último'),
                    ]),
                    html.Div(className='calculadora-numeros-grid', children=[
                        _botao_token_calculadora(display, codigo, 'calculadora-token-numero')
                        for display, codigo in NUMEROS
                    ]),
                ]),
                html.Div(className='calculadora-operadores-coluna', children=[
                    _botao_token_calculadora(display, codigo, 'calculadora-token-operador')
                    for display, codigo in OPERADORES
                ]),
            ]),
        ]),
        html.Div(className='calculadora-grupo calculadora-grupo-colunas', children=[
            html.Div('Colunas', className='calculadora-grupo-titulo'),
            html.Div(className='calculadora-grupo-botoes', children=(
                [_botao_token_calculadora(display, codigo, 'calculadora-token-coluna', titulo=rotulo_completo)
                 for display, codigo, rotulo_completo in colunas_pares]
                if colunas_pares else
                [html.Div('Abra um arquivo pra ver as colunas aqui.', className='calculadora-colunas-vazio')]
            )),
        ]),
    ])
