from dash import dcc, html

from src.gui.components import icone_colorido
from src.core.plotting.plotter import cor_da_coluna, colunas_plotadas, PALETA_CORES


def renderizar_info_rodape(estado, aba_ativa):
    """
    Texto fixo da esquerda do rodapé: 'ln N  col N  [encoding]' da aba
    ativa. Sem arquivo/aba selecionada, mostra um placeholder neutro.
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    info = arquivo.info if arquivo else {}

    if not info:
        # ln (5) | col (5) | encoding (10)
        return 'ln ()   col ()    [          ]'

    # Extrai os valores convertendo para string
    n_linhas = str(info.get('n_linhas', '—'))
    n_colunas = str(info.get('n_colunas', '—'))
    encoding = str(info.get('encoding', '—'))

    # <5  -> alinha à esquerda em um espaço reservado de 5 caracteres
    # <10 -> alinha à esquerda em um espaço reservado de 10 caracteres
    return f'ln {n_linhas:<5} col {n_colunas:<5} [{encoding:<10}]'


def renderizar_badge_alerta(estado, aba_ativa):
    """Texto do botão de alerta do rodapé: '⚠ (N)', N = nº de avisos da aba ativa."""
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    avisos = arquivo.avisos if arquivo else []
    return f'⚠ ({len(avisos)})'


def classe_badge_alerta(estado, aba_ativa):
    """
    Classe CSS do botão de alerta: destaca (âmbar) quando a aba ativa tem
    pelo menos 1 aviso pendente, neutro quando não tem nenhum.
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    avisos = arquivo.avisos if arquivo else []
    return 'rodape-alerta-badge com-avisos' if avisos else 'rodape-alerta-badge'


def renderizar_popup_alerta(estado, aba_ativa):
    """
    Conteúdo da subjanela (hide/show) que aparece ao clicar no alerta do
    rodapé — lista cada aviso de sanitização gerado no carregamento do
    arquivo da aba ativa (cabeçalho ajustado, linhas descartadas, NaN
    encontrado, amostragem do gráfico, etc.).
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    avisos = arquivo.avisos if arquivo else []

    if not avisos:
        return [html.Div('Nenhum aviso.', className='rodape-popup-vazio')]

    return [html.Div(aviso, className='rodape-popup-item') for aviso in avisos]


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


def renderizar_colunas_da_aba_ativa(estado, aba_ativa):
    if not aba_ativa or aba_ativa not in estado.arquivos:
        return html.Div('Abra um arquivo.', className='abas-placeholder', style={'padding': '14px'})

    arquivo = estado.arquivos[aba_ativa]

    lista_canais = []
    for coluna in arquivo.colunas_visiveis():
        rotulo = arquivo.rotulo(coluna)
        par_canal = (aba_ativa, coluna)
        selecionado = par_canal in estado.canais_selecionados

        classe_canal = 'coluna-item' + (' selecionada' if selecionado else '')
        marcador_check = '✓ ' if selecionado else '☐ '

        lista_canais.append(html.Div(
            id={'type': 'linha-canal', 'arquivo': aba_ativa, 'coluna': coluna},
            className=classe_canal,
            children=[
                html.Span(marcador_check, className="canal-checkbox"),
                html.Span(rotulo, className="canal-rotulo"),
                html.Button(
                    '🗑',
                    id={'type': 'botao-excluir-canal', 'arquivo': aba_ativa, 'coluna': coluna},
                    className="canal-lixeira-btn",
                    title=f"Excluir canal '{rotulo}'",
                    n_clicks=0,
                ),
            ]
        ))

    if not lista_canais:
        return []

    # Card separado do fundo da sidebar (que continua com o watermark de
    # 'file.svg' por baixo) — em vez dos itens ficarem soltos e
    # transparentes herdando a cor do menu, eles agora vivem 'sobre' ele,
    # com tom próprio e sombra sutil. Se a lista for curta, o cartão
    # também fica curto e o watermark aparece normalmente ao redor — não é
    # um problema, é o efeito desejado.
    return [html.Div(className='canais-cartao', children=lista_canais)]


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
            # gerar_grafico_serie_temporal) — por isso ganha um rótulo e
            # emoji de verdade em vez do ícone-placeholder genérico que os
            # outros 5 ainda usam (ver ICONES_OPCOES_GRAFICO acima).
            conteudo = [
                html.Span('📈', className='central-btn-emoji'),
                html.Span('Série temporal', className='toolbar-tooltip'),
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
# padrão visual já basta pra reconhecer, não precisa ler "Tracejada",
# "Traço-ponto longo" etc. pra saber qual é qual).
OPCOES_ESTILO_LINHA = [
    {'label': '─────────', 'value': 'solid'},
    {'label': '· · · · · · ·', 'value': 'dot'},
    {'label': '‑ ‑ ‑ ‑ ‑ ‑', 'value': 'dash'},
    {'label': '‑‑  ‑‑  ‑‑  ‑‑', 'value': 'longdash'},
    {'label': '‑ · ‑ · ‑ ·', 'value': 'dashdot'},
    {'label': '‑‑ · ‑‑ · ‑‑', 'value': 'longdashdot'},
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
    _estados_toolbar em callbacks.py), direto no Output dele.
    """
    return [
        html.Div('Opções do gráfico', className='painel-direito-titulo'),
        html.P('Customizações do gráfico', className='painel-direito-placeholder'),
    ]


def _seletor_cor(cor_atual):
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

    'edicao-curva-cor' (dcc.Store, mesmo de antes) continua sendo a
    fonte de verdade em hexadecimal pra aplicar_preferencias_curva; os
    campos R/G/B são o que o usuário mexe de fato — um callback
    (sincronizar_cor_rgb, em callbacks.py) traduz pra hex e grava lá.

    'data-hue'/'data-sat'/'data-val' no wrapper guardam o HSV atual: é
    o que o arraste do mouse lê/escreve, porque RGB sozinho não
    distingue "matiz perdida" (cinza puro) da matiz que o usuário
    tinha escolhido antes de arrastar só o brilho, por exemplo.
    """
    r, g, b = _hex_para_rgb(cor_atual)
    h, s, v = _rgb_para_hsv(r, g, b)

    return html.Div(
        className='cor-picker-wrapper',
        **{'data-hue': round(h, 2), 'data-sat': round(s, 4), 'data-val': round(v, 4)},
        children=[
            html.Button(
                id='cor-picker-caixa', className='cor-picker-caixa', n_clicks=0,
                title='Escolher cor', style={'backgroundColor': cor_atual},
            ),
            html.Div(id='cor-picker-painel', className='cor-picker-painel', children=[
                html.Div(id='cor-picker-area', className='cor-picker-area', children=[
                    html.Div(
                        id='cor-picker-area-fundo', className='cor-picker-area-fundo',
                        style={'backgroundColor': f'hsl({h:.1f}, 100%, 50%)'},
                    ),
                    html.Div(
                        id='cor-picker-area-cursor', className='cor-picker-area-cursor',
                        style={'left': f'{s * 100:.2f}%', 'top': f'{(1 - v) * 100:.2f}%'},
                    ),
                ]),
                html.Div(id='cor-picker-hue', className='cor-picker-hue', children=[
                    html.Div(
                        id='cor-picker-hue-cursor', className='cor-picker-hue-cursor',
                        style={'left': f'{(h / 360) * 100:.2f}%'},
                    ),
                ]),
                html.Div(className='cor-picker-campos', children=[
                    _campo_rgb('edicao-curva-rgb-r', 'R', r),
                    _campo_rgb('edicao-curva-rgb-g', 'G', g),
                    _campo_rgb('edicao-curva-rgb-b', 'B', b),
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

    return [
        html.Div(className='painel-edicao-secao', children=[
            html.Div(className='painel-edicao-secao-cabecalho', children=[
                html.Span('Curva:', className='painel-edicao-secao-titulo'),
                html.Button(
                    '✕', id='fechar-edicao-curva', className='painel-edicao-fechar-btn',
                    title='Fechar edição', n_clicks=0,
                ),
            ]),

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
                    dcc.Store(id='edicao-curva-cor', data=cor_atual),
                    _seletor_cor(cor_atual),
                ]),
                html.Div(className='painel-edicao-subcampo painel-edicao-subcampo-estilo', children=[
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
            ]),
        ]),
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
        dcc.Graph(id='grafico-plotly-real', figure=fig, className='grafico-plotly'),
    ])