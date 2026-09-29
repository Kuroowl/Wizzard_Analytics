"""
Como a Nova Amostragem aparece: a barra de operações (em cima do gráfico)
e o painel direito (árvore de dados em cima, configuração da operação
embaixo).

Funções puras: recebem o estado e devolvem componentes. Quem decide
QUANDO redesenhar é src/callbacks/nova_amostragem.py.

A ORIGEM dos dados é escolhida só clicando na árvore: um canal ou uma
análise. A caixa "Origem dos dados" do painel começa vazia e mostra o que
foi clicado.

O "contexto" (dict guardado em 'amostragem-contexto-store'):
    canal_y       canal raiz da origem (nome interno); None = origem vazia
    pai           id da análise usada como origem (None = o próprio canal)
    selecionado   id da análise mostrada no cartão: a da origem, ou a que o
                  Recalcular está refazendo (None = nenhuma)
    recalculando  id da análise em que o Recalcular parou esperando parâmetros
    motivo        por que ele parou (texto mostrado no cartão)
    parou         id de uma análise da CALCULADORA em que o Recalcular parou
                  (não tem parâmetros pra ajustar aqui: só o motivo no cartão)
    renomeando    id da análise com o nome em edição (lápis)
    detalhes      detalhes da análise (origem, parâmetros, resultado) abertos
                  no cartão? Começa fechado: a árvore fica com mais altura.
    ultimos       {operação: parâmetros} usados por último (Preview/OK/Add):
                  o painel volta com eles em vez dos valores iniciais.
"""
from dash import dcc, get_asset_url, html

from src.core.operations.amostragem import OPERACOES, parametros_iniciais, rotulo_operacao
from src.core.plotting.plotter import cor_da_coluna


# Botões da barra, na ordem. 'model_fit' ainda não existe no core: aparece
# desabilitado pra mostrar que está previsto.
OPERACOES_BARRA = [
    ('downsampling', 'Downsampling', 'Escolhe N pontos da própria série, espalhados em X'),
    ('media_movel', 'Média móvel', 'Média e desvio padrão em janelas ±Δx'),
    ('ajuste_polinomial', 'Polynomial Fit', 'Ajusta um polinômio de grau 1, 2 ou 3'),
    ('model_fit', 'Model Fit', 'Em breve'),
]

# Ícone de cada operação (assets/icones/), com metade do tamanho dos da toolbar.
ICONES_OPERACOES = {
    'downsampling': 'down_icon.png',
    'media_movel': 'moving_icon.png',
    'ajuste_polinomial': 'poly_icon.png',
    'model_fit': 'model_icon.png',
}

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

CONTEXTO_VAZIO = {'canal_y': None, 'pai': None, 'selecionado': None,
                  'recalculando': None, 'motivo': None, 'renomeando': None,
                  'detalhes': False, 'ultimos': {}, 'parou': None}


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
    """Botões da árvore e do cartão (olho, renomear, excluir, recalcular, manter)."""
    return {'type': 'amostragem-acao', 'acao': acao, 'no': id_no}


def renderizar_amostragem_barra():
    """
    Barra fixa (montada uma vez no layout, nunca reconstruída — só a
    classe do botão escolhido muda). Model Fit nasce desabilitado.
    """
    botoes = [
        html.Button(
            [html.Img(src=get_asset_url(f'icones/{ICONES_OPERACOES[chave]}'), className='amostragem-op-icone',
                      alt=''),
             html.Span(rotulo)],
            id=id_botao_operacao(chave), n_clicks=0, title=dica,
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
    elif operacao == 'calculadora':
        linhas.append(f"{info.get('n_obtido', '?')} pontos.")
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

LARGURA_BRACO = 12   # px por faixa de braço (análises com várias origens)
ALCANCE_ENCAIXE = 84  # px da trilha da 1ª faixa até o fim do nome (atravessa os botões do hover)


def _bracos(segmentos):
    """
    Trilhas da margem direita de UMA linha: um pedaço por faixa. 'inicio' =
    primeira origem (desce do meio da linha), 'pai' = outra origem (passa e
    encosta), 'passa' = só atravessa, 'fim' = a análise que as origens
    geraram (chega no meio da linha), None = faixa vazia nesta linha.
    """
    if not segmentos:
        return None
    pedacos = []
    for k, s in enumerate(segmentos):
        # Encaixe horizontal: da trilha desta faixa até o fim do nome
        # (passa por trás dos botões do hover — 👁 ✏️ 🗑 — e das faixas à
        # esquerda). O nome termina numa guia pontilhada (_linha_no).
        encaixe = [html.Span(className='braco-encaixe' + (' seta' if s == 'fim' else ''),
                             style={'width': f'{ALCANCE_ENCAIXE + LARGURA_BRACO * k}px'})] \
            if s in ('inicio', 'pai', 'fim') else []
        pedacos.append(html.Span(className='braco' + (f' {s}' if s else ''), children=encaixe))
    return html.Div(className='amostragem-bracos', style={'width': f'{LARGURA_BRACO * len(segmentos)}px'},
                    children=pedacos)


def _estilo_linha(padding_esquerda, n_faixas):
    estilo = {'paddingLeft': f'{padding_esquerda}px'}
    if n_faixas:
        estilo['paddingRight'] = f'{LARGURA_BRACO * n_faixas + 6}px'
    return estilo


def _linha_no(arquivo, no, eixo_x, nivel, contexto, segmentos=None):
    """
    Uma análise: rótulo clicável (vira a origem e abre o cartão) + botões
    que aparecem no hover, no mesmo padrão do menu da esquerda: olho
    (mostra no gráfico — fica aceso enquanto ligado), lápis (renomeia) e
    lixeira (exclui com o que saiu dela).
    """
    desatualizado = arquivo.derivado_desatualizado(no.id)
    compativel = arquivo.derivado_compativel_com_x(no.id, eixo_x)
    renomeando = contexto['renomeando'] == no.id
    canal = arquivo.canal_da_analise(no.id)       # virou canal (Add)?
    classes = ['amostragem-no']
    dicas = [f"{rotulo_operacao(no.operacao)} — {len(no.serie)} pontos"]
    if len(no.pais) > 1:
        nomes = [arquivo.arvore.no(p).nome for p in no.pais if p in arquivo.arvore]
        dicas.append('Depende de: ' + ', '.join(f"'{n}'" for n in nomes) + '.')
    if not compativel:
        classes.append('incompativel')
        dicas.append(f"Calculado com X = '{arquivo.rotulo(no.eixo_x)}': só aparece no gráfico com esse X.")
    if desatualizado:
        classes.append('desatualizado')
        dicas.append('Os dados de origem mudaram depois desta análise.')
    if no.id == contexto['pai']:
        classes.append('origem')
    if no.visivel and compativel:
        classes.append('visivel')
    if renomeando:
        classes.append('editando')

    if renomeando:
        rotulo = dcc.Input(
            id={'type': 'amostragem-nome-input', 'no': no.id}, type='text', value=no.nome,
            autoFocus=True, debounce=False, maxLength=80, className='canal-rotulo-input',
        )
    else:
        rotulo = html.Div(
            id={'type': 'amostragem-no', 'id': no.id}, n_clicks=0,
            className='amostragem-no-rotulo', title='\n'.join(dicas + ['Clique para usar como origem.']),
            children=[
                html.Span('└', className='amostragem-no-ramo'),
                html.Span(no.nome, className='amostragem-no-nome'),
                html.Span('◆', className='amostragem-no-canal', title=f"Virou canal: '{canal.rotulo}'")
                if canal else None,
                html.Span('⚠', className='amostragem-no-alerta') if desatualizado else None,
                # Guia pontilhada até o braço (só nas linhas ligadas a um).
                html.Span(className='amostragem-no-guia')
                if any(s in ('inicio', 'pai', 'fim') for s in (segmentos or [])) else None,
            ],
        )
    olho = html.Button(
        '👁', id=id_acao('olho', no.id), n_clicks=0, disabled=not compativel,
        title=('Esconder do gráfico' if no.visivel else 'Mostrar no gráfico') if compativel
        else f"Só pode ser mostrada com X = '{arquivo.rotulo(no.eixo_x)}'",
        className='amostragem-olho-btn' + (' ligado' if no.visivel and compativel else ''),
    )
    return html.Div(
        className=' '.join(classes),
        style=_estilo_linha(12 + 16 * nivel, len(segmentos or [])),
        children=[
            rotulo,
            olho,
            html.Button('✏️', id=id_acao('renomear', no.id), n_clicks=0,
                        title='Salvar o nome' if renomeando else f"Renomear '{no.nome}'",
                        className='canal-editar-btn'),
            html.Button('🗑', id=id_acao('excluir', no.id), n_clicks=0,
                        title=f"Excluir '{no.nome}' e as análises que saíram dela",
                        className='canal-lixeira-btn'),
            _bracos(segmentos),
        ],
    )


def _linhas_da_arvore(arquivo, raizes):
    """
    A árvore "achatada" em linhas, na ordem de exibição:
    ('raiz', canal) | ('no', nó, nível) | ('vazio', canal).

    Uma análise com várias origens (calculadora: média A + média B) aparece
    UMA vez, logo abaixo da ÚLTIMA das suas origens na ordem da árvore —
    o braço da margem direita (_faixas_dos_bracos) liga as outras até ela.
    """
    linhas, emitidos = [], set()

    def descer(id_pai, canal, nivel):
        for no in arquivo.arvore.filhos(id_pai, canal):
            if no.id in emitidos or any(p not in emitidos for p in no.pais):
                continue            # ainda falta uma origem: entra debaixo dela, mais adiante
            emitidos.add(no.id)
            linhas.append(('no', no, nivel))
            descer(no.id, None, nivel + 1)

    for canal in raizes:
        linhas.append(('raiz', canal))
        antes = len(linhas)
        descer(None, canal, 1)
        if len(linhas) == antes:
            linhas.append(('vazio', canal))
    return linhas


def _faixas_dos_bracos(linhas):
    """
    Pra cada linha, o pedaço de braço em cada faixa (ver _bracos). Um braço
    vai da primeira origem até a análise que elas geraram; braços que se
    sobrepõem na vertical ganham faixas diferentes.
    """
    posicao = {linha[1].id: i for i, linha in enumerate(linhas) if linha[0] == 'no'}
    bracos = []
    for i, linha in enumerate(linhas):
        if linha[0] == 'no' and len(linha[1].pais) > 1:
            pais = [posicao[p] for p in linha[1].pais if p in posicao]
            if pais:
                bracos.append((min(pais), i, set(pais)))
    faixas_fim = []                 # última linha ocupada de cada faixa
    alocados = []
    for inicio, fim, pais in sorted(bracos):
        faixa = next((k for k, ultimo in enumerate(faixas_fim) if ultimo < inicio), None)
        if faixa is None:
            faixa = len(faixas_fim)
            faixas_fim.append(fim)
        else:
            faixas_fim[faixa] = fim
        alocados.append((faixa, inicio, fim, pais))
    n = len(faixas_fim)
    segmentos = [[None] * n for _ in linhas]
    for faixa, inicio, fim, pais in alocados:
        for i in range(inicio, fim + 1):
            if i == inicio:
                segmentos[i][faixa] = 'inicio'
            elif i == fim:
                segmentos[i][faixa] = 'fim'
            else:
                segmentos[i][faixa] = 'pai' if i in pais else 'passa'
    return segmentos


def renderizar_arvore_amostragem(arquivo, eixo_x, contexto=None):
    """
    Raízes = os canais que estão no Y do gráfico agora (na ordem e com a
    cor das curvas) e, depois deles, os que JÁ TÊM análises mesmo fora do
    Y (○) — a árvore é o histórico do que foi feito. Um canal fora do Y e
    sem análises não aparece. Clicar num canal ou numa análise: vira a
    origem dos dados. Análises com várias origens (calculadora) ficam
    ligadas a todas por um braço na margem direita.
    """
    contexto = contexto_normalizado(contexto)
    canais_y = canais_do_grafico(arquivo)
    raizes = raizes_da_arvore(arquivo)
    if not raizes:
        return html.Div(
            'Nenhum canal no eixo Y. Clique nos canais da barra lateral pra colocá-los no gráfico.',
            className='amostragem-vazio',
        )
    linhas = _linhas_da_arvore(arquivo, raizes)
    segmentos = _faixas_dos_bracos(linhas)
    componentes = []
    for linha, seg in zip(linhas, segmentos):
        tipo = linha[0]
        if tipo == 'no':
            componentes.append(_linha_no(arquivo, linha[1], eixo_x, linha[2], contexto, seg))
            continue
        canal = linha[1]
        if tipo == 'vazio':
            componentes.append(html.Div(className='amostragem-sem-analises', style=_estilo_linha(22, len(seg)),
                                        children=['sem análises', _bracos(seg)]))
            continue
        eh_origem = contexto['pai'] is None and contexto['canal_y'] == canal
        no_grafico = canal in canais_y
        componentes.append(html.Div(
            id={'type': 'amostragem-raiz', 'canal': canal}, n_clicks=0,
            className='amostragem-raiz' + (' origem' if eh_origem else '') + ('' if no_grafico else ' fora-do-grafico'),
            title=('Clique para usar este canal como origem' if no_grafico else
                   'Fora do gráfico: aparece aqui porque já tem análises. Clique para usar como origem.'),
            style=_estilo_linha(4, len(seg)),
            children=[
                html.Span('●' if no_grafico else '○', className='amostragem-raiz-cor',
                          style={'color': cor_da_coluna(canais_y.index(canal))} if no_grafico else None),
                html.Span(arquivo.rotulo(canal), className='amostragem-raiz-nome'),
                _bracos(seg),
            ],
        ))
    return html.Div(componentes, className='amostragem-arvore')


# ============================================================================
# Cartão da análise selecionada
# ============================================================================

def _texto_parametros(no):
    if no.operacao == 'calculadora':
        return f"Expressão: {no.parametros.get('exibida') or no.parametros.get('expressao')}"
    campos = CAMPOS_PARAMETROS.get(no.operacao, {})
    partes = []
    for nome, valor in no.parametros.items():
        rotulo = campos.get(nome, (nome,))[0]
        partes.append(f"{rotulo}: {_numero(valor) if isinstance(valor, float) else valor}")
    return ' · '.join(partes)


def renderizar_cartao_no(arquivo, no, eixo_x, contexto):
    """Resultado da análise clicada e, se desatualizada, Recalcular/Manter."""
    desatualizado = arquivo.derivado_desatualizado(no.id)
    compativel = arquivo.derivado_compativel_com_x(no.id, eixo_x)
    origem = ' + '.join(arquivo.arvore.no(p).nome for p in no.pais if p in arquivo.arvore) \
        if no.pais else arquivo.rotulo(no.canal_raiz)
    avisos = []
    acoes = []
    if desatualizado:
        if contexto['recalculando'] == no.id:
            avisos.append(html.Div(
                f"⚠ O Recalcular parou aqui. {contexto['motivo'] or ''} "
                'Ajuste os parâmetros abaixo e clique em Recalcular.',
                className='amostragem-cartao-aviso'))
        else:
            texto = ('⚠ Os dados de origem mudaram depois desta análise.' if contexto['parou'] != no.id else
                     f"⚠ O Recalcular parou aqui. {contexto['motivo'] or ''} "
                     'Refaça a conta na calculadora, ou Manter / excluir.')
            avisos.append(html.Div(texto, className='amostragem-cartao-aviso'))
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
    # Cabeçalho sempre à vista (nome, ⚠, avisos e Recalcular/Manter); os
    # detalhes (origem, parâmetros, resultado) recolhem — começam fechados.
    aberto = bool(contexto['detalhes'])
    detalhes = [
        html.Div(f"{rotulo_operacao(no.operacao)} de {origem} · X = {arquivo.rotulo(no.eixo_x)}",
                 className='amostragem-cartao-linha'),
        html.Div(_texto_parametros(no), className='amostragem-cartao-linha'),
        *[html.Div(linha, className='amostragem-cartao-linha dado') for linha in linhas_resultado(no.operacao, no.info)],
    ] if aberto else []
    return html.Div(className='amostragem-cartao' + (' aberto' if aberto else ''), children=[
        html.Button(
            id=id_acao('detalhes', no.id), n_clicks=0,
            title='Esconder os detalhes' if aberto else 'Mostrar origem, parâmetros e resultado',
            className='amostragem-cartao-cabecalho',
            children=[
                html.Span('▾' if aberto else '▸', className='amostragem-cartao-seta'),
                html.Span(no.nome, className='amostragem-cartao-nome'),
                html.Span('⚠', className='amostragem-no-alerta') if desatualizado else None,
            ],
        ),
        *detalhes,
        *avisos,
        html.Div(acoes, className='amostragem-acoes') if acoes else None,
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


def raizes_da_arvore(arquivo):
    """Os canais do Y e, depois, os que têm análises (histórico) mesmo fora do Y."""
    canais_y = canais_do_grafico(arquivo)
    com_analises = [c for c in arquivo.arvore.canais_com_derivados()
                    if c not in canais_y and c in arquivo.df_editado.columns]
    return canais_y + com_analises


def origem_efetiva(arquivo, eixo_x, contexto):
    """
    (canal_y, eixo_x_da_origem, pai) de onde a próxima operação parte, ou
    (None, eixo_x, None) com a origem vazia. Uma análise que não existe
    mais, ou um canal que saiu do Y, esvaziam a origem.
    """
    contexto = contexto_normalizado(contexto)
    pai = contexto['pai']
    if pai is not None:
        if pai in arquivo.arvore:
            no = arquivo.arvore.no(pai)
            return no.canal_raiz, no.eixo_x, pai
        return None, eixo_x, None
    canal_y = contexto['canal_y'] if contexto['canal_y'] in raizes_da_arvore(arquivo) else None
    return canal_y, eixo_x, None


def _caixa_origem(arquivo, canal_y, eixo_origem, pai):
    """'Origem dos dados': vazia até o usuário clicar na árvore."""
    if canal_y is None:
        conteudo = html.Span('Clique num canal ou numa análise na árvore acima.',
                             className='amostragem-origem-vazia')
    elif pai is not None:
        no = arquivo.arvore.no(pai)
        conteudo = [html.Span(no.nome, className='amostragem-origem-nome'),
                    html.Span(f"{rotulo_operacao(no.operacao)} · {len(no.serie)} pontos",
                              className='amostragem-origem-detalhe')]
    else:
        conteudo = [html.Span(arquivo.rotulo(canal_y), className='amostragem-origem-nome'),
                    html.Span('canal', className='amostragem-origem-detalhe')]
    return html.Div(className='amostragem-param', children=[
        html.Label('Origem dos dados', className='amostragem-param-rotulo'),
        html.Div(conteudo, className='amostragem-origem' + (' vazia' if canal_y is None else '')),
    ])


def renderizar_config_amostragem(arquivo, eixo_x, operacao, contexto=None):
    """
    Cartão da análise clicada (se houver) + configuração: a origem dos
    dados (caixa preenchida pelo clique na árvore), o X, os parâmetros e os
    botões Preview / OK / Add.

    Valores dos parâmetros, nesta ordem de preferência:
      1. Recalcular parado numa análise -> os parâmetros dela (pra ajustar);
      2. preview desta configuração no gráfico -> os do preview;
      3. os últimos usados nesta operação (OK/Add não "esquecem" o que foi
         digitado);
      4. valores iniciais calculados dos dados da origem.
    """
    contexto = contexto_normalizado(contexto)
    if operacao not in OPERACOES:       # ex: 'calculadora' não é operação da barra
        operacao = None
    no_sel = arquivo.arvore.no(contexto['selecionado']) if contexto['selecionado'] in arquivo.arvore else None
    cartao = [renderizar_cartao_no(arquivo, no_sel, eixo_x, contexto)] if no_sel else []

    canal_y, eixo_origem, pai = origem_efetiva(arquivo, eixo_x, contexto)
    recalculando = no_sel is not None and contexto['recalculando'] == no_sel.id
    caixa_origem = _caixa_origem(arquivo, canal_y, eixo_origem, pai)

    if operacao is None:
        return html.Div(className='amostragem-config', children=[
            *cartao, caixa_origem,
            html.Div('Escolha uma operação na barra acima do gráfico.', className='amostragem-vazio'),
        ])

    compativel = eixo_origem == eixo_x
    preview = preview_desta_configuracao(arquivo, operacao, canal_y, eixo_origem, pai)
    if canal_y is not None:
        serie = arquivo.serie_de_origem(canal_y, eixo_origem, pai)
        ultimos = (contexto['ultimos'] or {}).get(operacao)
        if recalculando:
            parametros = dict(no_sel.parametros)
        elif preview:
            parametros = dict(preview.parametros)
        elif ultimos:
            parametros = {**parametros_iniciais(operacao, serie), **ultimos}
        else:
            parametros = parametros_iniciais(operacao, serie)
        info = f'{len(serie)} pontos na origem.'
        if not compativel:
            info = (f"A origem foi calculada com X = '{arquivo.rotulo(eixo_origem)}'; "
                    'coloque esse X no gráfico para operar sobre ela.')
    else:
        parametros = dict(OPERACOES[operacao].parametros_padrao)
        info = ''

    pode_operar = canal_y is not None and compativel
    return html.Div(className='amostragem-config', children=[
        *cartao,
        caixa_origem,
        html.Div(className='amostragem-param', children=[
            html.Label('Eixo X', className='amostragem-param-rotulo'),
            html.Div(arquivo.rotulo(eixo_origem) if eixo_origem else '—', className='amostragem-param-fixo'),
        ]),
        *[_campo_parametro(operacao, nome, _formatar_parametro(valor)) for nome, valor in parametros.items()],
        html.Div(info, className='amostragem-info') if info else None,
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
            html.Button('Add', id='amostragem-add', n_clicks=0, disabled=not pode_operar or recalculando,
                        title="Transforma esta análise num canal (x', y') em 'Análises do arquivo'",
                        className='amostragem-acao-btn'),
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
