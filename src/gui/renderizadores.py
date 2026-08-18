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
    _estados_toolbar em callbacks.py), direto no Output dele.
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


def _linha_toggle_dupla(rotulo_esquerda, rotulo_direita, indice, ativo=False):
    """
    Variante de _linha_toggle com um rótulo de CADA LADO do
    interruptor, em vez de um rótulo só — usada pelo par 'Division' /
    'Subdivision' em 'Ticks': a própria POSIÇÃO do toggle (esquerda =
    Division, direita = Subdivision) já comunica qual dos dois modos
    está ativo, então os dois nomes ficam sempre visíveis (não só o
    que está ligado agora), diferente de um toggle com um rótulo único
    tipo 'Grid' ou 'Both sides'.

    Usa 'painel-edicao-toggle-modo' como classe extra (ver _toggle) —
    é o que deixa este toggle específico laranja quando ativo (modo
    Subdivision), em vez do teal padrão dos outros toggles do painel.
    """
    return html.Div(className='painel-edicao-toggle-linha painel-edicao-toggle-linha-dupla', children=[
        html.Span(rotulo_esquerda, className='painel-edicao-toggle-rotulo-lateral'),
        _toggle(indice, ativo=ativo, classe_extra='painel-edicao-toggle-modo'),
        html.Span(rotulo_direita, className='painel-edicao-toggle-rotulo-lateral'),
    ])


def _campo_slider(rotulo, id_slider, valor, minimo, maximo, step=1):
    """
    Rótulo + dcc.Slider, no mesmo padrão do slider 'Thickness' da
    seção 'Curva' (ver renderizar_painel_edicao). Reaproveitado pelos
    3 sliders de 'Division'/'Subdivision' em 'Ticks' — os mesmos 3
    componentes (mesmos ids) trocam de VALOR quando o toggle
    'Division/Subdivision' é ligado/desligado (ver alternar_modo_ticks
    em callbacks.py); não nascem 6 sliders duplicados. Ficam dentro de
    um wrapper com id próprio ('edicao-ticks-sliders-wrapper') cuja
    CLASSE também troca junto (mesmo callback) — é o que permite os
    3 sliders mudarem de cor (teal <-> laranja) ao trocar de modo, ver
    .painel-edicao-ticks-sliders.modo-subdivisao em edit_menu.css.
    """
    return html.Div(className='painel-edicao-campo', children=[
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


def _linha_limite_eixo(letra_eixo, id_min, id_max, index_cadeado):
    """
    Uma linha da sub-seção 'Limits' dentro de 'Eixos': [min] < x <
    [max] + botão de autoscale (recalcula os limites automaticamente
    a partir dos dados — ainda só visual, ver comentário no fim de
    renderizar_painel_edicao) + botão de cadeado (trava/destrava o
    eixo nesse min/max fixo; TEM callback já funcionando, ver
    alternar_cadeado_limite em callbacks.py, MATCH — só a troca do
    ícone/estado, a aplicação de verdade no gráfico vem na etapa de
    conexão com 'estado').

    'index_cadeado' é o 'index' do par {'type': 'limite-cadeado',
    'index': ...} — precisa ser único (aqui: 'x' / 'y').
    """
    return html.Div(className='painel-edicao-linha-limite', children=[
        dcc.Input(
            id=id_min, type='number', placeholder='min',
            className='painel-edicao-limite-input',
        ),
        html.Span('<', className='painel-edicao-limite-simbolo'),
        html.Span(letra_eixo, className='painel-edicao-limite-eixo-letra'),
        html.Span('<', className='painel-edicao-limite-simbolo'),
        dcc.Input(
            id=id_max, type='number', placeholder='max',
            className='painel-edicao-limite-input',
        ),
        html.Button(
            '🔄', id={'type': 'limite-autoscale', 'index': index_cadeado},
            className='painel-edicao-limite-btn', title='Autoscale (recalcula os limites)',
            n_clicks=0,
        ),
        html.Button(
            '🔓', id={'type': 'limite-cadeado', 'index': index_cadeado},
            className='painel-edicao-limite-btn', title='Travar eixo neste intervalo',
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
    ]

    # Valores 'de fábrica' das linhas de Eixos — ainda não vêm de
    # 'estado' (não existe campo de preferências de eixo no dataclass
    # hoje, só por-curva: cor/espessura/estilo/marcador). Os campos já
    # funcionam de ponta a ponta (digitar, +/-, tradução de LaTeX
    # simples) — falta só a parte de LER/GRAVAR esses valores em
    # 'estado' e aplicar no plotter quando isso for definido.
    conteudo_eixos = [
        html.Div(className='painel-edicao-eixos-cabecalho', children=[
            html.Div(className='painel-edicao-eixos-cabecalho-rotulo'),
            html.Span('Aa', className='painel-edicao-eixos-cabecalho-coluna'),
            html.Span('↔', className='painel-edicao-eixos-cabecalho-coluna'),
        ]),
        _linha_eixo(
            'Title:', 'edicao-eixo-titulo-texto', '',
            'edicao-eixo-titulo-fonte', 14,
            'edicao-eixo-titulo-espacamento', 1,
        ),
        _linha_eixo(
            'Axis x:', 'edicao-eixo-x-texto', '',
            'edicao-eixo-x-fonte', 10,
            'edicao-eixo-x-espacamento', 1,
        ),
        _linha_eixo(
            'Axis y:', 'edicao-eixo-y-texto', '',
            'edicao-eixo-y-fonte', 12,
            'edicao-eixo-y-espacamento', 1,
        ),

        html.Hr(className='painel-edicao-separador'),

        html.Div('Limits:', className='painel-edicao-limite-titulo'),
        _linha_limite_eixo('x', 'edicao-eixo-x-limite-min', 'edicao-eixo-x-limite-max', 'x'),
        _linha_limite_eixo('y', 'edicao-eixo-y-limite-min', 'edicao-eixo-y-limite-max', 'y'),
    ]

    # Valores 'de fábrica' de 'Ticks' — mesmo caso de 'Eixos' (comentário
    # acima): os controles já funcionam de ponta a ponta (dropdown de
    # eixo, sliders de divisão/subdivisão trocando de valor no toggle,
    # 'both sides'), só falta a parte de LER/GRAVAR em 'estado' e
    # aplicar de fato no plotter (fig.update_xaxes/update_yaxes) quando
    # isso for definido.
    #
    # O MESMO trio de sliders (ids fixos 'edicao-ticks-numero'/
    # '-largura'/'-comprimento') serve pras 'Divisions' E pra
    # 'Subdivision' — não nascem 6 sliders. 'edicao-ticks-divisoes-store'
    # guarda os dois conjuntos de valores (um por modo); o toggle
    # 'Subdivision' só troca QUAL dos dois conjuntos os sliders mostram
    # agora (ver alternar_modo_ticks/gravar_valores_ticks em
    # callbacks.py, MATCH em cima do toggle genérico _toggle).
    valores_divisoes_padrao = {'numero': 4, 'largura': 1, 'comprimento': 5}
    valores_subdivisoes_padrao = {'numero': 2, 'largura': 1, 'comprimento': 3}

    conteudo_ticks = [
        html.Div(className='painel-edicao-campo', children=[
            html.Label('Eixo:', htmlFor='edicao-ticks-eixo', className='painel-edicao-label'),
            dcc.Dropdown(
                id='edicao-ticks-eixo',
                options=[
                    {'label': 'X', 'value': 'x'},
                    {'label': 'Y', 'value': 'y'},
                    {'label': 'Both', 'value': 'both'},
                ],
                value='both',
                clearable=False, searchable=False,
                className='painel-edicao-dropdown',
            ),
        ]),

        # Toggle 'Division' <-> 'Subdivision': a POSIÇÃO do interruptor
        # (esquerda/direita) já diz qual dos dois modos está sendo
        # editado agora — não precisa mais de um título 'Divisions'
        # separado em cima nem de um segundo toggle 'Subdivision' lá
        # embaixo (era redundante com este). Logo abaixo do 'Eixo' por
        # pedido: é o primeiro controle que o usuário vê ao abrir
        # 'Ticks', antes mesmo dos sliders que ele afeta.
        _linha_toggle_dupla('Division', 'Subdivision', 'ticks-subdivisao'),

        html.Div(
            id='edicao-ticks-sliders-wrapper',
            className='painel-edicao-ticks-sliders',
            children=[
                _campo_slider(
                    'Number:', 'edicao-ticks-numero',
                    valores_divisoes_padrao['numero'], minimo=2, maximo=20, step=1,
                ),
                _campo_slider(
                    'Width:', 'edicao-ticks-largura',
                    valores_divisoes_padrao['largura'], minimo=1, maximo=10, step=1,
                ),
                _campo_slider(
                    'Length:', 'edicao-ticks-comprimento',
                    valores_divisoes_padrao['comprimento'], minimo=1, maximo=20, step=1,
                ),
            ],
        ),
        _linha_toggle('Both sides', 'ticks-both-sides'),

        dcc.Store(id='edicao-ticks-divisoes-store', data={
            'divisoes': valores_divisoes_padrao,
            'subdivisoes': valores_subdivisoes_padrao,
        }),
    ]

    # 'Outros' — por enquanto só Grid (on/off) e a cor do grid/fundo do
    # gráfico. Mesmo status de 'Ticks'/'Eixos': o seletor de cor
    # (_seletor_cor, generalizado com 'prefixo' pra caber mais de uma
    # instância no painel — ver comentário na própria função) e o
    # toggle já funcionam de ponta a ponta; falta só ligar os dois em
    # 'estado' e no plotter (fig.update_layout(plot_bgcolor=...) /
    # showgrid=False nos eixos) quando essa etapa for definida.
    #
    # O seletor em si é EXATAMENTE o mesmo widget do campo 'cor' de
    # 'Curva' (mesma _seletor_cor, mesmo _campo_rgb, mesmo JS de
    # arraste) — só o destino muda: aqui grava em
    # {'type': 'cor-store', 'index': 'fundo'}, não 'curva'. Por isso
    # fica dentro de um 'painel-edicao-subcampo' de largura fixa (86px,
    # igual à coluna 'cor:' de Curva) em vez de um 'painel-edicao-campo'
    # esticado — sem isso a caixinha vira uma barra comprida em vez do
    # quadradinho compacto que aparece em Curva.
    cor_fundo_padrao = '#FFFFFF'

    conteudo_outros = [
        _linha_toggle('Grid', 'outros-grid', ativo=True),

        html.Div(className='painel-edicao-campo', children=[
            html.Label('Grid / Background:', className='painel-edicao-label'),
            html.Div(className='painel-edicao-subcampo', style={'flex': '0 0 auto', 'width': '86px'}, children=[
                dcc.Store(id={'type': 'cor-store', 'index': 'fundo'}, data=cor_fundo_padrao),
                _seletor_cor(cor_fundo_padrao, 'fundo'),
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
        _secao_colapsavel('curva', 'Curva', conteudo_curva, aberta=True),
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
        dcc.Graph(id='grafico-plotly-real', figure=fig, className='grafico-plotly'),
    ])