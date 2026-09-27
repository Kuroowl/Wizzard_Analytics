"""
Como a Nova Amostragem aparece: a barra de operações (em cima do gráfico)
e o painel direito (árvore de dados em cima, configuração da operação
embaixo).

Funções puras: recebem o estado e devolvem componentes. Quem decide
QUANDO redesenhar é src/callbacks/nova_amostragem.py.
"""
from dash import dcc, html

from src.core.operations.amostragem import OPERACOES, parametros_iniciais
from src.core.plotting.plotter import cor_da_coluna


# Botões da barra, na ordem. 'model_fit' ainda não existe no core: aparece
# desabilitado pra mostrar que está previsto.
OPERACOES_BARRA = [
    ('downsampling', 'Downsampling', 'Escolhe N pontos da própria série, espalhados em X'),
    ('media_movel', 'Média móvel', 'Média e desvio padrão em janelas ±Δx'),
    ('ajuste_polinomial', 'Polynomial Fit', 'Ajusta um polinômio de grau 1, 2 ou 3'),
    ('model_fit', 'Model Fit', 'Em breve'),
]

# Como cada parâmetro aparece no painel, por operação: (rótulo, tipo, mínimo).
# tipo 'inteiro' | 'real' | 'grau' (seletor 1/2/3).
CAMPOS_PARAMETROS = {
    'downsampling': {
        'n_pontos': ('Quantidade de pontos', 'inteiro', 1),
    },
    'media_movel': {
        'n_pontos': ('Quantidade de subpontos', 'inteiro', 1),
        'delta_x': ('Janela ±Δx (na unidade de X)', 'real', 0),
    },
    'ajuste_polinomial': {
        'grau': ('Grau do polinômio', 'grau', 1),
        'n_pontos': ('Pontos da curva', 'inteiro', 2),
    },
}

DICA_BOTAO_PENDENTE = 'Disponível nas próximas etapas.'


def id_botao_operacao(chave):
    return {'type': 'amostragem-op', 'op': chave}


def classe_botao_operacao(chave, ativa):
    classe = 'amostragem-op-btn'
    if chave == ativa:
        classe += ' ativa'
    return classe


def renderizar_amostragem_barra():
    """
    Barra fixa (montada uma vez no layout, nunca reconstruída — só a
    classe do botão escolhido muda). Model Fit nasce desabilitado.
    """
    botoes = [
        html.Button(
            rotulo, id=id_botao_operacao(chave), n_clicks=0, title=dica,
            className=classe_botao_operacao(chave, None),
            disabled=chave not in OPERACOES,
        )
        for chave, rotulo, dica in OPERACOES_BARRA
    ]
    return html.Div(className='amostragem-barra-conteudo', children=[
        html.Div('Nova Amostragem', className='calculadora-grupo-titulo amostragem-barra-titulo'),
        html.Div(botoes, className='amostragem-barra-linha'),
    ])


# ============================================================================
# Painel direito
# ============================================================================

def _linha_no(arquivo, no, eixo_x, nivel):
    desatualizado = arquivo.derivado_desatualizado(no.id)
    compativel = arquivo.derivado_compativel_com_x(no.id, eixo_x)
    classes = ['amostragem-no']
    dicas = [f"{OPERACOES[no.operacao].rotulo} — {len(no.serie)} pontos"]
    if not compativel:
        classes.append('incompativel')
        dicas.append(f"Calculado com X = '{arquivo.rotulo(no.eixo_x)}': só aparece no gráfico com esse X.")
    if desatualizado:
        classes.append('desatualizado')
        dicas.append('Os dados de origem mudaram depois desta análise.')
    return html.Div(
        className=' '.join(classes),
        style={'paddingLeft': f'{12 + 16 * nivel}px'},
        title='\n'.join(dicas),
        children=[
            html.Span('└', className='amostragem-no-ramo'),
            html.Span(no.nome, className='amostragem-no-nome'),
            html.Span('⚠', className='amostragem-no-alerta') if desatualizado else None,
        ],
    )


def _ramos(arquivo, id_pai, canal, eixo_x, nivel):
    linhas = []
    for no in arquivo.arvore.filhos(id_pai, canal):
        linhas.append(_linha_no(arquivo, no, eixo_x, nivel))
        linhas.extend(_ramos(arquivo, no.id, canal, eixo_x, nivel + 1))
    return linhas


def renderizar_arvore_amostragem(arquivo, eixo_x):
    """
    Raízes = os canais que estão no Y do gráfico agora (na ordem e com a
    cor das curvas); embaixo de cada um, os derivados registrados. Um canal
    que sai do Y só some daqui — os derivados dele continuam no Arquivo.
    """
    canais_y = [c for c in arquivo.eixos_y_manual if c in arquivo.df_editado.columns]
    if not canais_y:
        return html.Div(
            'Nenhum canal no eixo Y. Clique nos canais da barra lateral pra colocá-los no gráfico.',
            className='amostragem-vazio',
        )
    blocos = []
    for indice, canal in enumerate(canais_y):
        ramos = _ramos(arquivo, None, canal, eixo_x, 1)
        blocos.append(html.Div(className='amostragem-raiz-bloco', children=[
            html.Div(className='amostragem-raiz', children=[
                html.Span('●', className='amostragem-raiz-cor', style={'color': cor_da_coluna(indice)}),
                html.Span(arquivo.rotulo(canal), className='amostragem-raiz-nome'),
            ]),
            *(ramos or [html.Div('sem análises', className='amostragem-sem-analises')]),
        ]))
    return html.Div(blocos, className='amostragem-arvore')


def _campo_parametro(operacao, nome, valor):
    rotulo, tipo, minimo = CAMPOS_PARAMETROS[operacao][nome]
    id_campo = {'type': 'amostragem-param', 'nome': nome}
    if tipo == 'grau':
        campo = dcc.Dropdown(
            id=id_campo, value=valor, clearable=False, searchable=False,
            options=[{'label': str(g), 'value': g} for g in (1, 2, 3)],
            className='amostragem-param-dropdown',
        )
    else:
        campo = dcc.Input(
            id=id_campo, type='number', value=valor, min=minimo,
            step=1 if tipo == 'inteiro' else 'any',
            debounce=True, className='amostragem-param-input',
        )
    return html.Div(className='amostragem-param', children=[
        html.Label(rotulo, className='amostragem-param-rotulo'),
        campo,
    ])


def _formatar_parametro(valor):
    if isinstance(valor, float):
        return float(f'{valor:.6g}')
    return valor


def preview_desta_configuracao(arquivo, operacao, canal_y, eixo_x):
    """O preview em exibição, se ele é desta operação/canal/X (senão None)."""
    preview = arquivo.preview_amostragem
    if preview and preview.pai is None and (preview.operacao, preview.canal_y, preview.eixo_x) == (operacao, canal_y, eixo_x):
        return preview
    return None


def _numero(valor):
    return f'{valor:.6g}'


def renderizar_resultado_amostragem(preview):
    """Resumo do resultado do preview: quantos pontos, estatísticas, coeficientes."""
    if preview is None:
        return []
    info = preview.info
    linhas = []
    if preview.operacao == 'downsampling':
        linhas.append(f"{info['n_obtido']} pontos selecionados de {info['n_origem']}.")
        if info['n_obtido'] < min(info['n_pedido'], info['n_origem']):
            linhas.append('Onde a aquisição é esparsa, alguns alvos caíram no mesmo ponto.')
    elif preview.operacao == 'media_movel':
        linhas.append(f"{info['n_obtido']} pontos · {info['pontos_por_janela_min']}–"
                      f"{info['pontos_por_janela_max']} pontos por janela "
                      f"(média {info['pontos_por_janela_media']:.1f}).")
        if info['janelas_vazias']:
            linhas.append(f"{info['janelas_vazias']} janela(s) sem pontos foram descartadas.")
    elif preview.operacao == 'ajuste_polinomial':
        linhas.append(info['equacao'])
        linhas.append(f"R² = {info['r2']:.6f}")
        grau = info['grau']
        linhas.append(' · '.join(f'a{grau - i} = {_numero(c)}' for i, c in enumerate(info['coeficientes'])))
    return [html.Div('Preview no gráfico', className='amostragem-resultado-titulo'),
            *[html.Div(linha, className='amostragem-resultado-linha') for linha in linhas]]


def renderizar_config_amostragem(arquivo, eixo_x, operacao, canal_y=None):
    """
    Configuração da operação escolhida: canal Y (entre os do gráfico), o X
    (vem do gráfico, só informativo), os parâmetros com valores iniciais
    calculados sobre os dados e os botões Preview / OK / Add.
    """
    if operacao is None:
        return html.Div('Escolha uma operação na barra acima do gráfico.', className='amostragem-vazio')

    canais_y = [c for c in arquivo.eixos_y_manual if c in arquivo.df_editado.columns]
    if canal_y not in canais_y:
        canal_y = canais_y[0] if canais_y else None

    preview = preview_desta_configuracao(arquivo, operacao, canal_y, eixo_x)
    if canal_y is not None:
        serie = arquivo.serie_do_canal(canal_y, eixo_x)
        # Com um preview no gráfico, o painel mostra os parâmetros DELE (um
        # redesenho do painel não pode "esquecer" o que o usuário digitou).
        parametros = dict(preview.parametros) if preview else parametros_iniciais(operacao, serie)
        info = f'{len(serie)} pontos válidos na origem.'
    else:
        parametros = dict(OPERACOES[operacao].parametros_padrao)
        info = 'Coloque um canal no eixo Y do gráfico pra escolher a origem.'

    return html.Div(className='amostragem-config', children=[
        html.Div(className='amostragem-param', children=[
            html.Label('Canal Y', className='amostragem-param-rotulo'),
            dcc.Dropdown(
                id='amostragem-canal-y', value=canal_y, clearable=False,
                options=[{'label': arquivo.rotulo(c), 'value': c} for c in canais_y],
                placeholder='nenhum canal no Y', className='amostragem-param-dropdown',
            ),
        ]),
        html.Div(className='amostragem-param', children=[
            html.Label('Eixo X (do gráfico)', className='amostragem-param-rotulo'),
            html.Div(arquivo.rotulo(eixo_x) if eixo_x else '—', className='amostragem-param-fixo'),
        ]),
        *[_campo_parametro(operacao, nome, _formatar_parametro(valor)) for nome, valor in parametros.items()],
        html.Div(info, className='amostragem-info'),
        html.Div(id='amostragem-resultado', className='amostragem-resultado',
                 children=renderizar_resultado_amostragem(preview)),
        html.Div(className='amostragem-acoes', children=[
            html.Button('Preview', id='amostragem-preview', n_clicks=0, disabled=canal_y is None,
                        title='Mostra o resultado no gráfico, sem registrar',
                        className='amostragem-acao-btn'),
            html.Button('OK', id='amostragem-ok', n_clicks=0, disabled=True,
                        title=DICA_BOTAO_PENDENTE, className='amostragem-acao-btn principal'),
            html.Button('Add', id='amostragem-add', n_clicks=0, disabled=True,
                        title=DICA_BOTAO_PENDENTE, className='amostragem-acao-btn'),
        ]),
    ])


def renderizar_painel_amostragem(estado, aba_ativa, eixo_x, operacao, canal_y=None):
    """Conteúdo de '#area-modo-nova-amostragem-edicao': árvore em cima, configuração embaixo."""
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    if arquivo is None:
        return []
    titulo_config = OPERACOES[operacao].rotulo if operacao in OPERACOES else 'Operação'
    return html.Div(className='amostragem-painel', children=[
        html.Div(className='amostragem-secao amostragem-secao-arvore', children=[
            html.Div(className='calculadora-grupo-titulo', children=[
                'Dados e análises',
                html.Span(f"X: {arquivo.rotulo(eixo_x)}" if eixo_x else '', className='amostragem-titulo-x'),
            ]),
            renderizar_arvore_amostragem(arquivo, eixo_x),
        ]),
        html.Div(className='amostragem-secao amostragem-secao-config', children=[
            html.Div(titulo_config, className='calculadora-grupo-titulo'),
            html.Div(id='amostragem-config-container',
                     children=renderizar_config_amostragem(arquivo, eixo_x, operacao, canal_y)),
        ]),
    ])
