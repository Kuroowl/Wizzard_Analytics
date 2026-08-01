from dash import dcc, html

from src.gui.components import icone_colorido
from src.core.plotting.plotter import cor_da_coluna, colunas_plotadas


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


# Opções da caixa 'Style' do painel de edição da curva — cada valor bate
# exatamente com PreferenciasCanal.estilo_linha (src/core/arquivo.py) e
# com o que go.Scatter aceita em line.dash (plotter.py), então não existe
# nenhuma tradução/mapa no meio: o valor escolhido aqui é gravado e usado
# como está. O rótulo usa um traço desenhado em texto (não emoji — não
# existem emojis de tipo de linha) até entrarem ícones de verdade.
OPCOES_ESTILO_LINHA = [
    {'label': '───── Contínua', 'value': 'solid'},
    {'label': '‑ ‑ ‑ ‑ Tracejada', 'value': 'dash'},
    {'label': '· · · · Pontilhada', 'value': 'dot'},
    {'label': '‑ · ‑ · Traço-ponto', 'value': 'dashdot'},
]


def renderizar_painel_direito_padrao(disabled=True):
    """
    Conteúdo 'de repouso' do painel-direito: título + placeholder +
    botão 'Iniciar edição'. Usado tanto no primeiro carregamento da
    página (layout.py) quanto sempre que a edição precisa ser resetada
    (fechar o gráfico, trocar de aba, ou clicar em 'Fechar edição' no
    próprio painel de curva) — ter essa função num lugar só evita que
    esses 4 pontos divirjam no texto/markup com o tempo.

    'disabled' controla o botão 'Iniciar edição': só deve nascer
    habilitado se a aba ativa JÁ tem um gráfico gerado (ver
    _estados_toolbar em callbacks.py); quem chama decide isso.
    """
    return [
        html.Div('Opções do gráfico', className='painel-direito-titulo'),
        html.P('Propriedades e customizações da curva ativa.', className='painel-direito-placeholder'),
        html.Button(
            '🎨 Iniciar edição',
            id='iniciar-edicao',
            className='botao-iniciar-edicao',
            disabled=disabled,
            n_clicks=0,
        ),
    ]


def renderizar_painel_edicao(estado, aba_ativa, coluna_selecionada=None):
    """
    Conteúdo do painel-direito depois que o usuário clica em 'Iniciar
    edição': por enquanto só a seção 'Curva' do desenho original (cor /
    espessura / estilo de linha da curva escolhida) — as seções de eixo
    X, eixo Y e 'Ticks and Marks' ainda não foram implementadas, ficam
    para uma próxima etapa (o painel pode crescer com mais html.Div de
    'painel-edicao-secao' abaixo desta, sem mexer no que já existe).

    'coluna_selecionada' é opcional: se None ou se a coluna passada não
    estiver mais no gráfico (ex: usuário desmarcou o canal), cai na
    primeira coluna plotada.
    """
    colunas = colunas_plotadas(estado, aba_ativa)
    if not colunas:
        return [
            html.Div('Opções do gráfico', className='painel-direito-titulo'),
            html.P(
                'Marque ao menos um canal no gráfico para editar suas curvas.',
                className='painel-direito-placeholder',
            ),
        ]

    if coluna_selecionada not in colunas:
        coluna_selecionada = colunas[0]

    arquivo = estado.arquivos[aba_ativa]
    opcoes_dado = [{'label': arquivo.rotulo(coluna), 'value': coluna} for coluna in colunas]

    # Se a curva ainda não foi editada, os controles nascem refletindo
    # exatamente o que já está desenhado agora (mesma cor da paleta fixa,
    # espessura/estilo padrão) — ver mesma lógica de fallback em
    # construir_figura_serie_temporal (plotter.py), pra painel e gráfico
    # nunca mostrarem valores diferentes pra mesma curva.
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
                    tooltip={'placement': 'bottom', 'always_visible': False},
                ),
            ]),

            html.Div(className='painel-edicao-campo painel-edicao-linha', children=[
                html.Div(className='painel-edicao-subcampo', children=[
                    html.Label('cor:', htmlFor='edicao-curva-cor', className='painel-edicao-label'),
                    dcc.Input(
                        id='edicao-curva-cor',
                        type='color',
                        value=cor_atual,
                        className='painel-edicao-cor',
                    ),
                ]),
                html.Div(className='painel-edicao-subcampo painel-edicao-subcampo-estilo', children=[
                    html.Label('Style:', htmlFor='edicao-curva-estilo', className='painel-edicao-label'),
                    dcc.Dropdown(
                        id='edicao-curva-estilo',
                        options=OPCOES_ESTILO_LINHA,
                        value=estilo_atual,
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