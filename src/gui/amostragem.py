"""
Como a Nova Amostragem aparece: a barra de operações (em cima do gráfico)
e o painel direito (árvore de dados em cima, configuração da operação
embaixo).

Funções puras: recebem o estado e devolvem componentes. Quem decide
QUANDO redesenhar é src/callbacks/nova_amostragem.py.

O "contexto" (dict guardado em 'amostragem-contexto-store') diz de onde a
próxima operação parte e o que está selecionado na árvore:
    canal_y       canal raiz escolhido (nome interno)
    pai           id do nó usado como ORIGEM (None = o próprio canal)
    selecionado   id do nó aberto no cartão (None = nenhum)
    recalculando  id do nó em que o Recalcular parou esperando parâmetros
    motivo        por que ele parou (texto mostrado no cartão)
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

CONTEXTO_VAZIO = {'canal_y': None, 'pai': None, 'selecionado': None, 'recalculando': None, 'motivo': None}


def contexto_normalizado(contexto):
    return {**CONTEXTO_VAZIO, **(contexto or {})}


def id_botao_operacao(chave):
    return {'type': 'amostragem-op', 'op': chave}


def classe_botao_operacao(chave, ativa):
    classe = 'amostragem-op-btn'
    if chave == ativa:
        classe += ' ativa'
    return classe


def id_acao(acao, id_no=''):
    """Botões do cartão do nó (recalcular, manter, usar como origem...)."""
    return {'type': 'amostragem-acao', 'acao': acao, 'no': id_no}


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
# Resumo de um resultado (preview ou nó)
# ============================================================================

def _numero(valor):
    return f'{valor:.6g}'.replace('-', '−')


def linhas_resultado(operacao, info):
    """Texto curto do resultado: quantos pontos, estatísticas, coeficientes."""
    linhas = []
    if operacao == 'downsampling':
        linhas.append(f"{info['n_obtido']} pontos selecionados de {info['n_origem']}.")
        if info['n_obtido'] < min(info['n_pedido'], info['n_origem']):
            linhas.append('Onde a aquisição é esparsa, alguns alvos caíram no mesmo ponto.')
    elif operacao == 'media_movel':
        linhas.append(f"{info['n_obtido']} pontos · {info['pontos_por_janela_min']}–"
                      f"{info['pontos_por_janela_max']} pontos por janela "
                      f"(média {info['pontos_por_janela_media']:.1f}).")
        if info['janelas_vazias']:
            linhas.append(f"{info['janelas_vazias']} janela(s) sem pontos foram descartadas.")
    elif operacao == 'ajuste_polinomial':
        linhas.append(info['equacao'])
        linhas.append(f"R² = {info['r2']:.6f}")
        grau = info['grau']
        linhas.append(' · '.join(f'a{grau - i} = {_numero(c)}' for i, c in enumerate(info['coeficientes'])))
    return linhas


def renderizar_resultado_amostragem(preview):
    """Resumo do preview em exibição (vazio sem preview)."""
    if preview is None:
        return []
    return [html.Div('Preview no gráfico', className='amostragem-resultado-titulo'),
            *[html.Div(linha, className='amostragem-resultado-linha')
              for linha in linhas_resultado(preview.operacao, preview.info)]]


# ============================================================================
# Árvore
# ============================================================================

def _linha_no(arquivo, no, eixo_x, nivel, contexto):
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
    if no.id == contexto['selecionado']:
        classes.append('selecionado')
    if no.id == contexto['pai']:
        classes.append('origem')
        dicas.append('Origem da próxima operação.')
    return html.Div(
        id={'type': 'amostragem-no', 'id': no.id}, n_clicks=0,
        className=' '.join(classes),
        style={'paddingLeft': f'{12 + 16 * nivel}px'},
        title='\n'.join(dicas),
        children=[
            html.Span('└', className='amostragem-no-ramo'),
            html.Span(no.nome, className='amostragem-no-nome'),
            html.Span('⚠', className='amostragem-no-alerta') if desatualizado else None,
        ],
    )


def _ramos(arquivo, id_pai, canal, eixo_x, nivel, contexto):
    linhas = []
    for no in arquivo.arvore.filhos(id_pai, canal):
        linhas.append(_linha_no(arquivo, no, eixo_x, nivel, contexto))
        linhas.extend(_ramos(arquivo, no.id, canal, eixo_x, nivel + 1, contexto))
    return linhas


def renderizar_arvore_amostragem(arquivo, eixo_x, contexto=None):
    """
    Raízes = os canais que estão no Y do gráfico agora (na ordem e com a
    cor das curvas); embaixo de cada um, os derivados registrados. Um canal
    que sai do Y só some daqui — os derivados dele continuam no Arquivo.
    Clicar num canal: ele vira a origem. Clicar num nó: abre o cartão dele
    e restaura a operação e os parâmetros.
    """
    contexto = contexto_normalizado(contexto)
    canais_y = [c for c in arquivo.eixos_y_manual if c in arquivo.df_editado.columns]
    if not canais_y:
        return html.Div(
            'Nenhum canal no eixo Y. Clique nos canais da barra lateral pra colocá-los no gráfico.',
            className='amostragem-vazio',
        )
    blocos = []
    for indice, canal in enumerate(canais_y):
        ramos = _ramos(arquivo, None, canal, eixo_x, 1, contexto)
        eh_origem = contexto['pai'] is None and contexto['canal_y'] == canal
        blocos.append(html.Div(className='amostragem-raiz-bloco', children=[
            html.Div(
                id={'type': 'amostragem-raiz', 'canal': canal}, n_clicks=0,
                className='amostragem-raiz' + (' origem' if eh_origem else ''),
                title='Usar este canal como origem',
                children=[
                    html.Span('●', className='amostragem-raiz-cor', style={'color': cor_da_coluna(indice)}),
                    html.Span(arquivo.rotulo(canal), className='amostragem-raiz-nome'),
                ],
            ),
            *(ramos or [html.Div('sem análises', className='amostragem-sem-analises')]),
        ]))
    return html.Div(blocos, className='amostragem-arvore')


# ============================================================================
# Cartão do nó selecionado
# ============================================================================

def _texto_parametros(no):
    campos = CAMPOS_PARAMETROS.get(no.operacao, {})
    partes = []
    for nome, valor in no.parametros.items():
        rotulo = campos.get(nome, (nome,))[0]
        partes.append(f"{rotulo}: {_numero(valor) if isinstance(valor, float) else valor}")
    return ' · '.join(partes)


def renderizar_cartao_no(arquivo, no, eixo_x, contexto):
    desatualizado = arquivo.derivado_desatualizado(no.id)
    compativel = arquivo.derivado_compativel_com_x(no.id, eixo_x)
    origem = arquivo.arvore.no(no.pai).nome if no.pai else arquivo.rotulo(no.canal_raiz)
    avisos = []
    acoes = []
    if desatualizado:
        if contexto['recalculando'] == no.id:
            avisos.append(html.Div(
                f"⚠ O Recalcular parou aqui. {contexto['motivo'] or ''} "
                'Ajuste os parâmetros abaixo e clique em Recalcular.',
                className='amostragem-cartao-aviso'))
        else:
            avisos.append(html.Div('⚠ Os dados de origem mudaram depois desta análise.',
                                   className='amostragem-cartao-aviso'))
            acoes += [
                html.Button('Recalcular', id=id_acao('recalcular', no.id), n_clicks=0,
                            title='Refaz esta cadeia com os dados atuais e os mesmos parâmetros',
                            className='amostragem-acao-btn principal'),
                html.Button('Manter', id=id_acao('manter', no.id), n_clicks=0,
                            title='Aceita o resultado como está; o alerta some',
                            className='amostragem-acao-btn'),
            ]
    if not compativel:
        avisos.append(html.Div(
            f"Calculado com X = '{arquivo.rotulo(no.eixo_x)}': só pode ser usado com esse X no gráfico.",
            className='amostragem-cartao-aviso neutro'))
    acoes += [
        html.Button('Usar como origem', id=id_acao('usar-origem', no.id), n_clicks=0,
                    disabled=not compativel,
                    title='A próxima operação parte deste resultado',
                    className='amostragem-acao-btn'),
        html.Button('🗑', id=id_acao('excluir', no.id), n_clicks=0,
                    title='Excluir esta análise e as que saíram dela',
                    className='amostragem-acao-btn excluir'),
    ]
    return html.Div(className='amostragem-cartao', children=[
        html.Div(no.nome, className='amostragem-cartao-nome'),
        html.Div(f"{OPERACOES[no.operacao].rotulo} de {origem} · X = {arquivo.rotulo(no.eixo_x)}",
                 className='amostragem-cartao-linha'),
        html.Div(_texto_parametros(no), className='amostragem-cartao-linha'),
        *[html.Div(linha, className='amostragem-cartao-linha dado') for linha in linhas_resultado(no.operacao, no.info)],
        *avisos,
        html.Div(acoes, className='amostragem-acoes'),
    ])


# ============================================================================
# Configuração da operação
# ============================================================================

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


def preview_desta_configuracao(arquivo, operacao, canal_y, eixo_x, pai=None):
    """O preview em exibição, se ele é desta operação/origem/X (senão None)."""
    preview = arquivo.preview_amostragem
    if preview and (preview.operacao, preview.canal_y, preview.eixo_x, preview.pai) == (operacao, canal_y, eixo_x, pai):
        return preview
    return None


def canais_do_grafico(arquivo):
    return [c for c in arquivo.eixos_y_manual if c in arquivo.df_editado.columns]


def origem_efetiva(arquivo, eixo_x, contexto):
    """
    (canal_y, eixo_x_da_origem, pai) de onde a próxima operação parte. Um
    nó de origem que não existe mais cai de volta pro canal.
    """
    contexto = contexto_normalizado(contexto)
    pai = contexto['pai'] if contexto['pai'] in arquivo.arvore else None
    if pai is not None:
        no = arquivo.arvore.no(pai)
        return no.canal_raiz, no.eixo_x, pai
    canais = canais_do_grafico(arquivo)
    canal_y = contexto['canal_y'] if contexto['canal_y'] in canais else (canais[0] if canais else None)
    return canal_y, eixo_x, None


def renderizar_config_amostragem(arquivo, eixo_x, operacao, contexto=None):
    """
    Cartão do nó selecionado (se houver) + configuração da operação
    escolhida: origem (canal Y do gráfico ou um nó), o X, os parâmetros e
    os botões Preview / OK / Add.

    Valores dos parâmetros, nesta ordem de preferência:
      1. Recalcular parado neste nó -> os parâmetros do nó (pra ajustar);
      2. nó selecionado desta mesma operação e origem -> os dele
         ("restaurar" uma análise);
      3. preview desta configuração no gráfico -> os do preview;
      4. valores iniciais calculados dos dados da origem.
    """
    contexto = contexto_normalizado(contexto)
    no_sel = arquivo.arvore.no(contexto['selecionado']) if contexto['selecionado'] in arquivo.arvore else None
    cartao = [renderizar_cartao_no(arquivo, no_sel, eixo_x, contexto)] if no_sel else []

    canal_y, eixo_origem, pai = origem_efetiva(arquivo, eixo_x, contexto)
    canais = canais_do_grafico(arquivo)
    recalculando = no_sel is not None and contexto['recalculando'] == no_sel.id

    # O dropdown de canal existe SEMPRE (escondido quando a origem é um nó):
    # os callbacks leem o valor dele como State.
    seletor_canal = html.Div(
        className='amostragem-param', style={'display': 'none'} if pai else None, children=[
            html.Label('Canal Y', className='amostragem-param-rotulo'),
            dcc.Dropdown(
                id='amostragem-canal-y', value=canal_y, clearable=False,
                options=[{'label': arquivo.rotulo(c), 'value': c} for c in canais],
                placeholder='nenhum canal no Y', className='amostragem-param-dropdown',
            ),
        ])
    origem_no = []
    if pai:
        origem_no = [html.Div(className='amostragem-param', children=[
            html.Label('Origem (análise)', className='amostragem-param-rotulo'),
            html.Div(className='amostragem-origem-no', children=[
                html.Span(arquivo.arvore.no(pai).nome),
                html.Button('usar o canal', id=id_acao('voltar-canal'), n_clicks=0,
                            title=f"Voltar a partir do canal '{arquivo.rotulo(canal_y)}'",
                            className='amostragem-link-btn'),
            ]),
        ])]

    if operacao is None:
        dica = ('Escolha uma operação na barra acima do gráfico'
                + (f" para aplicar sobre '{arquivo.arvore.no(pai).nome}'." if pai else '.'))
        return html.Div(className='amostragem-config', children=[
            *cartao, seletor_canal, *origem_no, html.Div(dica, className='amostragem-vazio'),
        ])

    compativel = eixo_origem == eixo_x
    preview = preview_desta_configuracao(arquivo, operacao, canal_y, eixo_origem, pai)
    if canal_y is not None:
        serie = arquivo.serie_de_origem(canal_y, eixo_origem, pai)
        if recalculando or (no_sel and no_sel.operacao == operacao and no_sel.pai == pai
                            and no_sel.canal_raiz == canal_y):
            parametros = dict(no_sel.parametros)
        elif preview:
            parametros = dict(preview.parametros)
        else:
            parametros = parametros_iniciais(operacao, serie)
        info = f'{len(serie)} pontos na origem.'
        if not compativel:
            info = (f"A origem foi calculada com X = '{arquivo.rotulo(eixo_origem)}'; "
                    'coloque esse X no gráfico para operar sobre ela.')
    else:
        parametros = dict(OPERACOES[operacao].parametros_padrao)
        info = 'Coloque um canal no eixo Y do gráfico pra escolher a origem.'

    pode_operar = canal_y is not None and compativel
    return html.Div(className='amostragem-config', children=[
        *cartao,
        seletor_canal,
        *origem_no,
        html.Div(className='amostragem-param', children=[
            html.Label('Eixo X', className='amostragem-param-rotulo'),
            html.Div(arquivo.rotulo(eixo_origem) if eixo_origem else '—', className='amostragem-param-fixo'),
        ]),
        *[_campo_parametro(operacao, nome, _formatar_parametro(valor)) for nome, valor in parametros.items()],
        html.Div(info, className='amostragem-info'),
        html.Div(id='amostragem-resultado', className='amostragem-resultado',
                 children=renderizar_resultado_amostragem(preview)),
        html.Div(className='amostragem-acoes', children=[
            html.Button('Preview', id='amostragem-preview', n_clicks=0, disabled=not pode_operar,
                        title='Mostra o resultado no gráfico, sem registrar',
                        className='amostragem-acao-btn'),
            html.Button('Recalcular' if recalculando else 'OK', id='amostragem-ok', n_clicks=0,
                        disabled=not pode_operar,
                        title=('Recalcula esta análise com estes parâmetros e segue a cadeia'
                               if recalculando else 'Registra esta análise na árvore'),
                        className='amostragem-acao-btn principal'),
            html.Button('Add', id='amostragem-add', n_clicks=0, disabled=True,
                        title=DICA_BOTAO_PENDENTE, className='amostragem-acao-btn'),
        ]),
    ])


def renderizar_painel_amostragem(estado, aba_ativa, eixo_x, operacao, contexto=None):
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
            renderizar_arvore_amostragem(arquivo, eixo_x, contexto),
        ]),
        html.Div(className='amostragem-secao amostragem-secao-config', children=[
            html.Div(titulo_config, className='calculadora-grupo-titulo'),
            html.Div(id='amostragem-config-container',
                     children=renderizar_config_amostragem(arquivo, eixo_x, operacao, contexto)),
        ]),
    ])
