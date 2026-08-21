import math

import numpy as np
import plotly.graph_objects as go

# Paleta fixa (é a paleta padrão do próprio Plotly) — compartilhada com a
# sidebar da interface, pra garantir que a bolinha ao lado do nome da coluna
# bate exatamente com a cor da curva no gráfico.
PALETA_CORES = [
    '#636efa', '#EF553B', '#00cc96', '#ab63fa', '#FFA15A',
    '#19d3f3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
]

# Número máximo de pontos que uma curva mostra NO GRÁFICO. É só uma máscara
# de exibição: os dados completos no DataFrame nunca são tocados, então
# qualquer operação futura (corte, filtro, exportação) continua enxergando
# a série inteira. Só o que vai pro Plotly é que fica mais leve.
MAX_PONTOS_EXIBICAO = 8000


def cor_da_coluna(indice):
    """Cor que a N-ésima coluna plotada vai receber — usada tanto aqui
    quanto na sidebar, pra manter os dois sincronizados."""
    return PALETA_CORES[indice % len(PALETA_CORES)]


# Tamanho do marcador quando 'Marker' != 'none' — não fica exposto
# como opção pro usuário (só a FORMA do marcador é escolhida no
# painel), é um valor fixo que deixa o marcador visível sem dominar o
# traço.
TAMANHO_MARCADOR = 7


def resolver_modo(estilo_linha, marcador):
    """
    Combina o que foi escolhido na caixa 'Style' (estilo_linha) e na
    caixa 'Marker' (marcador) — os dois são INDEPENDENTES, um não troca
    o outro — no 'mode' que go.Scatter espera:

      - estilo_linha != 'none'  -> inclui 'lines' no modo (desenha a
        linha no padrão escolhido: solid/dash/dot/...).
      - marcador != 'none'      -> inclui 'markers' no modo (desenha um
        marcador em cada ponto, ADICIONALMENTE à linha se ela também
        estiver ligada — não substitui, soma).

    Todas as 4 combinações são válidas: só linha, só marcador, os dois
    juntos, ou nenhum dos dois (nesse último caso a curva fica de fato
    invisível — 'mode' nunca pode ser vazio pro Plotly, então cai em
    'markers' com o marcador escondido via tamanho 0 em vez de dar erro
    — ver TAMANHO_MARCADOR abaixo, onde o tamanho real só é aplicado
    quando marcador != 'none').
    """
    partes = []
    if estilo_linha and estilo_linha != 'none':
        partes.append('lines')
    if marcador and marcador != 'none':
        partes.append('markers')
    return '+'.join(partes) if partes else 'markers'


def _indices_amostra_uniforme(n_pontos, max_pontos=MAX_PONTOS_EXIBICAO):
    """
    Devolve os ÍNDICES (não os dados) de uma amostra igualmente espaçada de
    tamanho no máximo `max_pontos`, cobrindo do primeiro ao último ponto da
    série. Isso preserva a forma geral da curva (não é um corte só do
    início) e é puramente para exibição — quem chama decide se aplica ou
    não; o DataFrame original nunca é alterado.

    Retorna None quando a série já é pequena o suficiente e não precisa de
    amostragem nenhuma (sinal de "usa tudo, sem cópia").
    """
    if n_pontos <= max_pontos:
        return None
    return np.linspace(0, n_pontos - 1, max_pontos).round().astype(int)


def colunas_plotadas(estado, aba_ativa):
    """
    Devolve, na mesma ordem usada para desenhar as curvas, as colunas do
    arquivo da aba ativa que estão de fato NO GRÁFICO agora (visíveis +
    marcadas em 'estado.canais_selecionados').

    Compartilhada entre `construir_figura_serie_temporal` (que desenha) e
    o painel de edição da curva (`renderizar_painel_edicao` em
    renderizadores.py, que precisa oferecer exatamente essas colunas na
    caixa 'Dado') — as duas precisam concordar sobre "o que está no
    gráfico", senão o painel deixaria escolher pra editar uma curva que
    não está sendo exibida (ou esconderia uma que está).
    """
    arquivo = estado.arquivos.get(aba_ativa)
    if arquivo is None:
        return []
    return [
        col for col in arquivo.colunas_visiveis()
        if (aba_ativa, col) in estado.canais_selecionados
    ]


def resolver_eixo_x(estado, df):
    """
    Decide qual coluna de UM arquivo serve de eixo X: a preferência
    global (`estado.coluna_x`, hoje sempre 'Tempo_decorrido_s') se ela
    existir nesse arquivo; senão a primeira coluna numérica; senão a
    primeira coluna de qualquer tipo (fallback pra nunca travar).

    Compartilhada entre o plotter (que monta a figura) e a sidebar
    (`renderizadores.renderizar_colunas_da_aba_ativa`, que precisa saber
    qual canal NÃO oferecer como curva plotável) — as duas precisam
    concordar sobre qual é o eixo X, senão a sidebar deixa marcar um
    canal que o gráfico depois descarta silenciosamente.
    """
    if estado.coluna_x in df.columns:
        return estado.coluna_x
    colunas_numericas = df.select_dtypes(include='number').columns
    return colunas_numericas[0] if len(colunas_numericas) else df.columns[0]


def _intervalo_arredondado(vmin, vmax):
    """
    Arredonda [vmin, vmax] pra baixo/cima até a POTÊNCIA DE 10 mais
    próxima do tamanho do intervalo — ex: [0.3, 4.55095] -> [0, 5], não
    fica preso aos valores exatos (e meio aleatórios) dos dados. É o
    que evita rótulos de tick tipo '4.5509166...' quando o usuário só
    queria ver '0, 1, 2, 3, 4, 5'.

    Não é o algoritmo "nice numbers" completo (tipo o do matplotlib,
    que também escolhe passos em 1/2/5 vezes a potência de 10) — só a
    parte de arredondar as BORDAS do intervalo; o passo entre ticks
    (dtick, calculado por _dtick_major/_dtick_minor logo abaixo) ainda
    pode sair com casas decimais depois de dividir esse intervalo já
    arredondado pelo número de divisões escolhido — arredondar o passo
    TAMBÉM exigiria ajustar o número de divisões pra baixo/cima do que
    o usuário pediu, o que preferimos não fazer (o slider 'Number' diz
    respeito ao que o usuário vê e mexe, então o valor dele fica
    intocado).
    """
    if vmin is None or vmax is None or vmin == vmax:
        return vmin, vmax
    span = vmax - vmin
    if span <= 0:
        return vmin, vmax
    magnitude = 10 ** math.floor(math.log10(span))
    vmin_novo = math.floor(vmin / magnitude) * magnitude
    vmax_novo = math.ceil(vmax / magnitude) * magnitude
    return vmin_novo, vmax_novo


def _range_dos_dados(fig, eixo):
    """
    Min/max de TODOS os traços já desenhados em 'fig' pro eixo 'x' ou
    'y' — usado como base pro cálculo de dtick quando o usuário NÃO
    travou um limite manual pra esse eixo (ver PreferenciasLimiteEixo
    em arquivo.py). Lê direto de 'fig.data' (os traços já montados,
    já com a amostragem de exibição aplicada se houve) em vez do
    DataFrame original — mesma faixa que está REALMENTE desenhada.

    (None, None) se não há nenhum traço ainda (gráfico em branco, sem
    canal marcado) — quem chama trata isso como "sem dtick calculável,
    volta pro comportamento automático do Plotly".
    """
    valores_min, valores_max = [], []
    for traco in fig.data:
        dados = getattr(traco, eixo, None)
        if dados is None or len(dados) == 0:
            continue
        valores_min.append(np.nanmin(dados))
        valores_max.append(np.nanmax(dados))
    if not valores_min:
        return None, None
    return min(valores_min), max(valores_max)


def _tick0_e_dtick(vmin, vmax, numero_divisoes):
    """
    'numero_divisoes' é o número de marcas NOVAS (o slider 'Number' em
    Ticks) entre vmin e vmax, SEM CONTAR os dois extremos — os extremos
    já estão implícitos (é a própria moldura do gráfico, ver 'moldura
    fechada' em _aplicar_preferencias_grafico). Então 'numero_divisoes'
    marcas dividem o intervalo em (numero_divisoes + 1) pedaços iguais:
    numero_divisoes=1 num intervalo de 0 a 1 -> 1 marca nova, bem no
    meio (0.5) — 2 pedaços. numero_divisoes=5 (padrão) num intervalo
    de 0 a 5 -> 5 marcas novas (1, 2, 3, 4 e... nesse caso dtick=5/6,
    então nem sempre as marcas caem em número redondo — só as BORDAS
    do intervalo (via _intervalo_arredondado) são garantidamente
    redondas, o passo entre elas depende de quantas divisões o usuário
    pediu).

    Devolve (None, None) se não dá pra calcular (faltam dados, ou
    'numero_divisoes' inválido) — quem chama cai de volta pro
    comportamento automático do Plotly (nticks aproximado) nesse caso.
    """
    if vmin is None or vmax is None or not numero_divisoes or numero_divisoes <= 0:
        return None, None
    span = vmax - vmin
    if span <= 0:
        return None, None
    dtick = span / (numero_divisoes + 1)
    return vmin, dtick


def _aplicar_preferencias_grafico(fig, preferencias):
    """
    Aplica em 'fig' o que foi ajustado nas seções 'Eixos', 'Ticks' e
    'Outros' do painel de edição (ver PreferenciasGrafico em
    src/core/arquivo.py) — chamado no fim de
    construir_figura_serie_temporal, depois que as curvas já foram
    desenhadas, porque essas propriedades são do LAYOUT (eixos/fundo),
    não de uma curva específica (e porque o cálculo de dtick, logo
    abaixo, precisa OLHAR os traços já desenhados pra saber o range
    real dos dados quando o usuário não travou um limite manual).

    Mapeamento pros parâmetros do Plotly:
      - 'titulo'/'titulo_eixo_x'/'titulo_eixo_y' (PreferenciasTexto) ->
        fig.update_layout(title=...) e fig.update_xaxes/yaxes(
        title=...), com 'font.size' pro tamanho. O título do gráfico
        nasce CENTRALIZADO no topo (x=0.5, xanchor='center') — o
        padrão do Plotly é alinhado à esquerda. 'espacamento' vira a
        DISTÂNCIA até o gráfico (não espaçamento entre caracteres —
        ver PreferenciasTexto em arquivo.py): 'pad.b' pro título do
        gráfico (empurra o gráfico pra baixo, afastando da barra do
        título) e 'standoff' pros rótulos de eixo (distância até os
        números de tick). Um texto vazio ('') não é enviado (fica
        None) — sem isso, um título vazio ainda ocuparia a margem
        reservada pro título no layout do Plotly.
      - 'limite_x'/'limite_y' (PreferenciasLimiteEixo) -> range=[min,
        max] só quando os DOIS estão preenchidos (um só, sem o outro,
        não define um intervalo válido — fica ambíguo se seria só
        limite inferior/superior aberto, então nesse caso o Plotly
        continua decidindo sozinho, como se nada tivesse sido digitado).
      - 'divisoes'/'subdivisoes' (ticks principais/secundários) ->
        tick0+dtick calculados na mão (ver _tick0_e_dtick) a partir do
        range EFETIVO do eixo — os limites travados manualmente
        (PreferenciasLimiteEixo), OU (se não há limite travado) o
        range dos dados JÁ ARREDONDADO pra bordas redondas (ver
        _intervalo_arredondado — evita dtick baseado em algo tipo
        4.55095). 'numero_divisoes' é o número de marcas NOVAS entre
        os extremos, ver _tick0_e_dtick pra a conta exata. As
        secundárias usam o MESMO dtick principal dividido pelo número
        de subdivisões, pra ficarem igualmente espaçadas DENTRO de
        cada intervalo principal.

        Se não der pra calcular (gráfico em branco, sem traço nenhum
        ainda) cai de volta em 'nticks' (contagem aproximada, decidida
        pelo próprio Plotly) — mesmo comportamento de antes.
      - 'direcao' ('outside'/'inside', ver 'Inward'/'Outward' no
        painel) em ambos (principal e minor) — sem 'ticks' definido
        (string vazia, o padrão do Plotly) o eixo desenha só as LINHAS
        de grade, nenhum traço de tick de verdade, então largura/
        comprimento (tickwidth/ticklen) não teriam efeito visual
        nenhum.
      - 'fonte_labels' -> tickfont.size (tamanho dos NÚMEROS ao lado
        de cada tick — diferente da fonte do RÓTULO do eixo, que é
        PreferenciasTexto.fonte).
      - moldura fechada (as 4 bordas do gráfico, padrão matplotlib):
        showline=True + linecolor sempre ligados, e 'mirror' copiando
        a linha do eixo pro lado oposto — sem isso o Plotly
        ('plotly_white') não desenha NENHUMA linha de eixo por padrão.
      - 'both_sides' -> só controla se os TICKS (marcas) também
        espelham pro lado oposto (mirror='ticks') ou só a linha da
        moldura (mirror=True, sem marca do lado espelhado) — a
        moldura em si aparece sempre, independente deste toggle.
      - 'grid' -> showgrid nos dois eixos (o painel só tem UM
        interruptor 'Grid' em 'Outros', não um por eixo).
      - 'cor_fundo' -> plot_bgcolor (a ÁREA de plotagem; 'paper_bgcolor',
        a moldura ao redor, continua a cargo do template).
    """
    if preferencias.titulo.texto:
        fig.update_layout(title=dict(
            text=preferencias.titulo.texto,
            font=dict(size=preferencias.titulo.fonte),
            x=0.5, xanchor='center',
            pad=dict(b=max(0, preferencias.titulo.espacamento)),
        ))

    for prefs_texto, atualizar_eixo, prefs_limite in (
        (preferencias.titulo_eixo_x, fig.update_xaxes, preferencias.limite_x),
        (preferencias.titulo_eixo_y, fig.update_yaxes, preferencias.limite_y),
    ):
        kwargs = {}
        if prefs_texto.texto:
            kwargs['title'] = dict(
                text=prefs_texto.texto,
                font=dict(size=prefs_texto.fonte),
                standoff=max(0, prefs_texto.espacamento),
            )
        if prefs_limite.minimo is not None and prefs_limite.maximo is not None:
            kwargs['range'] = [prefs_limite.minimo, prefs_limite.maximo]
        if kwargs:
            atualizar_eixo(**kwargs)

    for eixo_prefs, atualizar_eixo, prefs_limite, letra_eixo in (
        (preferencias.ticks_x, fig.update_xaxes, preferencias.limite_x, 'x'),
        (preferencias.ticks_y, fig.update_yaxes, preferencias.limite_y, 'y'),
    ):
        divisoes = eixo_prefs.divisoes
        subdivisoes = eixo_prefs.subdivisoes

        # Range efetivo pro cálculo de dtick: o limite TRAVADO (se os
        # dois — min E max — estiverem preenchidos), senão o range dos
        # dados já desenhados, arredondado pra bordas redondas (ver
        # docstring da função).
        if prefs_limite.minimo is not None and prefs_limite.maximo is not None:
            vmin, vmax = prefs_limite.minimo, prefs_limite.maximo
        else:
            vmin, vmax = _range_dos_dados(fig, letra_eixo)
            vmin, vmax = _intervalo_arredondado(vmin, vmax)

        tick0, dtick = _tick0_e_dtick(vmin, vmax, divisoes.get('numero'))
        _, dtick_minor = (
            (None, dtick / (subdivisoes.get('numero') + 1))
            if dtick and subdivisoes.get('numero')
            else (None, None)
        )

        kwargs_eixo = dict(
            showgrid=preferencias.grid,
            # Moldura fechada em volta da área de plotagem (as 4
            # bordas — comum no matplotlib, onde os eixos SEMPRE vêm
            # com essa caixa por padrão) — sem 'showline'/'linecolor'
            # aqui, o Plotly (template 'plotly_white') não desenha
            # NENHUMA linha de eixo, só as linhas de grade internas;
            # 'mirror' copia a linha do eixo pro lado oposto (topo/
            # direita), fechando a caixa nos 4 lados.
            #
            # 'both_sides' (toggle 'Both sides' em Ticks) continua
            # controlando só os TICKS (as marcas) mirrados ou não pro
            # lado oposto — a caixa em si aparece sempre,
            # independente disso: 'ticks' mirra linha E marcas,
            # True (sem 'both_sides') mirra só a linha, fechando a
            # caixa sem marca nenhuma do lado espelhado.
            showline=True,
            linewidth=1,
            linecolor='#4A5560',
            mirror='ticks' if eixo_prefs.both_sides else True,
            ticks=eixo_prefs.direcao,
            tickfont=dict(size=eixo_prefs.fonte_labels),
            tickwidth=divisoes.get('largura'),
            ticklen=divisoes.get('comprimento'),
        )
        if dtick:
            kwargs_eixo['tick0'] = tick0
            kwargs_eixo['dtick'] = dtick
        else:
            # Sem range calculável (gráfico em branco) — volta pro
            # comportamento aproximado de antes, só pra não deixar o
            # eixo sem tick nenhum.
            kwargs_eixo['nticks'] = divisoes.get('numero')

        kwargs_minor = dict(
            ticks=eixo_prefs.direcao,
            tickwidth=subdivisoes.get('largura'),
            ticklen=subdivisoes.get('comprimento'),
        )
        if dtick_minor:
            kwargs_minor['dtick'] = dtick_minor
        else:
            kwargs_minor['nticks'] = subdivisoes.get('numero')
        kwargs_eixo['minor'] = kwargs_minor

        atualizar_eixo(**kwargs_eixo)

    if preferencias.cor_fundo:
        fig.update_layout(plot_bgcolor=preferencias.cor_fundo)


def construir_figura_serie_temporal(estado, aba_ativa):
    """
    Monta a figura de 'Série Temporal' (linhas) para UM ÚNICO arquivo: o da
    aba ativa (`aba_ativa`). Cada aba é independente — tem seu próprio
    menu de canais, seu próprio gráfico e seu próprio painel de edição;
    trocar de aba só troca qual figura já pronta é exibida (isso é feito
    em `callbacks.py`, olhando `arquivo.figura`), nunca refaz ou
    mistura dados de outro arquivo.

    Por isso essa função nunca itera por `estado.arquivos` inteiro — ela
    só lê `estado.arquivos[aba_ativa]`. Combinar canais de arquivos
    diferentes num mesmo gráfico é uma feature à parte (o botão "Fundir
    arquivos"), ainda não implementada, e não deve acontecer por acidente
    aqui.

    Se nenhum canal estiver marcado ainda para esse arquivo, a figura
    volta sem nenhuma curva — é assim que o gráfico nasce "em branco" na
    primeira vez que o usuário abre a opção de Série Temporal, e vai
    ganhando curvas conforme ele marca colunas na barra lateral.

    Em séries longas, os pontos plotados são amostrados de forma uniforme
    (ver `_indices_amostra_uniforme`) só para exibição — o DataFrame
    guardado em `arquivo.df_editado` continua com todas as linhas originais,
    intacto para qualquer corte/filtro que o usuário for aplicar depois.
    """
    fig = go.Figure()

    arquivo = estado.arquivos.get(aba_ativa)
    if arquivo is None:
        # Aba inexistente/fechada: devolve figura vazia em vez de estourar,
        # quem chama decide o que fazer (normalmente nem chega a acontecer,
        # os callbacks já checam isso antes).
        return fig

    df = arquivo.df_editado
    houve_amostragem = False

    # 1. Identifica a coluna do Eixo X (deste arquivo)
    eixo_x = resolver_eixo_x(estado, df)

    # 2. Só entram as colunas DESTE arquivo que estão visíveis (não
    #    excluídas/ocultas — o próprio eixo X já nasce OCULTO, ver
    #    Arquivo.__post_init__ em src/core/arquivo.py) e que o usuário
    #    marcou explicitamente na barra lateral.
    colunas_y = colunas_plotadas(estado, aba_ativa)

    if colunas_y:
        # 3. Calcula os índices de amostragem para exibição — reaproveitados
        #    em todas as colunas pra manter X e Y sempre alinhados entre si.
        indices_exibicao = _indices_amostra_uniforme(len(df))
        if indices_exibicao is not None:
            houve_amostragem = True
            x_valores = df[eixo_x].to_numpy()[indices_exibicao]
        else:
            x_valores = df[eixo_x]

        # 4. Plota cada canal marcado, respeitando as preferências que o
        #    usuário já tenha ajustado no painel de edição da curva (cor,
        #    espessura, estilo de linha — ver PreferenciasCanal em
        #    src/core/arquivo.py). Um canal ainda não editado não tem
        #    entrada em 'por_canal', então cai nos padrões de sempre: cor
        #    da paleta fixa (mesmo esquema da sidebar) e traço fino sólido.
        for indice_cor, coluna in enumerate(colunas_y):
            rotulo = arquivo.rotulo(coluna)
            prefs = arquivo.preferencias.por_canal.get(coluna)

            y_valores = (
                df[coluna].to_numpy()[indices_exibicao]
                if indices_exibicao is not None
                else df[coluna]
            )

            cor_curva = prefs.cor if prefs and prefs.cor else cor_da_coluna(indice_cor)
            estilo_curva = prefs.estilo_linha if prefs else 'solid'
            marcador_curva = prefs.marcador if prefs else 'none'
            modo = resolver_modo(estilo_curva, marcador_curva)
            tem_marcador = marcador_curva and marcador_curva != 'none'

            fig.add_trace(go.Scatter(
                x=x_valores,
                y=y_valores,
                mode=modo,
                name=rotulo,
                line=dict(
                    color=cor_curva,
                    width=(prefs.espessura if prefs else 1.0),
                    dash=(estilo_curva if estilo_curva != 'none' else 'solid'),
                ),
                marker=dict(
                    color=cor_curva,
                    symbol=(marcador_curva if tem_marcador else 'circle'),
                    # Tamanho 0 quando não há marcador escolhido — cobre
                    # o caso raro de 'mode' cair no fallback 'markers'
                    # (ver resolver_modo) por style e marker estarem os
                    # dois em 'none': sem isso, um marcador 'circle'
                    # apareceria sozinho mesmo sem o usuário ter pedido.
                    size=(TAMANHO_MARCADOR if tem_marcador else 0),
                ),
            ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',

    )

    _aplicar_preferencias_grafico(fig, arquivo.preferencias)

    if houve_amostragem:
        # A mensagem pro usuário vive só no alerta do rodapé (o
        # "mago") agora — ela costumava também aparecer como anotação
        # dentro da própria figura, mas isso brigava visualmente com o
        # título do gráfico (que pode ocupar a mesma área, perto do
        # topo) sempre que o usuário definia um. Um aviso duplicado
        # (dentro do gráfico E no rodapé) também não agregava nada.
        mensagem = (
            f"Aviso: o arquivo tem mais de {MAX_PONTOS_EXIBICAO:,} linhas — o gráfico "
            f"exibe uma amostra uniforme por curva, mas os dados completos "
            f"continuam preservados para filtros/exportação."
        ).replace(',', '.')
        arquivo.adicionar_aviso(mensagem)

    return fig


# Cor das guias de corte (linha + hachura) — vermelho, deliberadamente
# fora da paleta de curvas (PALETA_CORES acima) pra nunca ser confundida
# com um traço de dado de verdade. Compartilhada entre 'Aparar dados' e,
# no futuro, 'Excluir dados' (mesma mecânica de 2 cliques — ver
# aparar_dados/excluir_dados em src/core/operations/sampling.py).
COR_GUIA_CORTE = '#D62728'


def _linha_guia_corte(x, arrastavel=False):
    """Uma linha vertical sólida, ponta a ponta no eixo Y (yref='paper'
    — sempre cobre 0% a 100% da altura da área de plotagem, não importa
    o range de Y no momento) — marca um corte já CONFIRMADO (clicado).

    'arrastavel' só engrossa a linha (6px em vez de 2px, pra ler como
    uma "barra" agarrável) — a linha em si NUNCA é o shape que o
    Plotly arrasta de verdade (editable sempre False aqui); quem
    arrasta é o manípulo/pílula por cima dela (ver _pilula_arraste) —
    testando em navegador real, um manípulo decorativo 'acima' da
    linha na mesma pilha (layer='above' nos dois) SEMPRE intercepta o
    clique antes dele chegar na linha (é o elemento visualmente no
    topo), então dava pra arrastar o manípulo mas ele saía "solto",
    sem mover a linha de verdade. Inverter — o manípulo É o alvo, a
    linha só ACOMPANHA — resolve o conflito de uma vez: bate com o
    que o usuário vê (segura o "puxador", não um pedaço qualquer da
    barra) e não tem chance de um roubar o clique do outro.
    """
    return dict(
        type='line', xref='x', yref='paper', x0=x, x1=x, y0=0, y1=1,
        line=dict(color=COR_GUIA_CORTE, width=6 if arrastavel else 2),
        editable=False,
    )


def _pilula_arraste(x, span):
    """
    'Manípulo' de arraste no meio de uma linha de corte ARRASTÁVEL —
    mesmo espírito visual do manípulo do divisor de painéis da própria
    interface (ver '.divisor-resize' em estilo.css: uma pilula clara
    no meio de uma barra fina), só que aqui é um shape do Plotly (SVG
    puro), não dá pra usar ::before/::after de CSS. Uma ELIPSE estreita
    e um pouco mais alta que larga (inscrita numa caixa x0:x1 × 0.46:
    0.54 em coordenadas 'paper'), centralizada verticalmente na área
    de plotagem.

    'span' é o tamanho do range visível do eixo X (max-min) — a
    largura da elipse é uma fração pequena disso (não um valor fixo em
    unidades de dado, que ficaria enorme ou minúsculo dependendo da
    escala dos dados).

    ESTE é o shape que arrasta de verdade (editable=True) — não a
    linha por trás dele (ver docstring de _linha_guia_corte pro
    motivo). O JS (iniciarSelecaoCorte, scripts_js.py) lê o
    deslocamento do manípulo e MOVE a linha + a hachura juntas pra
    acompanhar, no fim do gesto.
    """
    largura = max(span * 0.006, 1e-9)
    return dict(
        type='circle', xref='x', yref='paper',
        x0=x - largura, x1=x + largura, y0=0.46, y1=0.54,
        fillcolor='#FFFFFF', line=dict(color=COR_GUIA_CORTE, width=2),
        layer='above', editable=True,
    )


def _faixa_hachurada_corte(x0, x1):
    """
    Área semitransparente vermelha entre x0 e x1 — indica visualmente
    'isto vai ser descartado' assim que o corte for confirmado.
    'layer=below' pra ficar ATRÁS das curvas (senão a faixa tampava o
    próprio traço de dado dentro da região marcada).

    'editable=False' EXPLÍCITO (não é só deixar de fora) — descoberto
    testando em navegador real: 'config={'edits': {'shapePosition':
    True}}' (renderizadores.py, necessário pra 'Linha ARRASTÁVEL'
    funcionar de verdade) libera arraste em QUALQUER shape que não
    diga o contrário, não só nas que têm 'editable=True' — sem este
    'False' explícito aqui, a HACHURA (não a linha) era o que
    respondia ao arraste do mouse. Quem se move por arraste é sempre
    a LINHA; a faixa só ACOMPANHA (sincronizada via JS, ver
    iniciarSelecaoCorte em scripts_js.py), pra não ter duas alças de
    arraste desencontradas na mesma região.
    """
    return dict(
        type='rect', xref='x', yref='paper', x0=x0, x1=x1, y0=0, y1=1,
        fillcolor='rgba(214, 39, 40, 0.15)', line=dict(width=0), layer='below',
        editable=False,
    )


def aplicar_guias_corte(fig, primeiro=None, segundo=None, arrastavel=False, modo='aparar'):
    """
    Devolve uma CÓPIA de 'fig' com as guias visuais dos cortes já
    CONFIRMADOS (clicados) desenhadas por cima — usado durante o modo de
    seleção de 'Aparar dados'/'Excluir dados' (ver registrar_clique_corte
    em callbacks.py), enquanto o usuário ainda não confirmou a ação de
    verdade. NUNCA modifica 'fig' original nem toca em 'arquivo.figura'
    — só o que aparece na tela nesse meio-tempo; cancelar a seleção
    (cancelar_corte, callbacks.py) simplesmente reexibe a figura
    original, intocada.

    A guia de arraste "ao vivo" (acompanhando o mouse antes do clique)
    NÃO é desenhada aqui — é 100% client-side (ver iniciarSelecaoCorte
    em scripts_js.py, que desenha/apaga essa linha tracejada direto via
    Plotly.relayout, sem round-trip com o servidor a cada movimento do
    mouse). Esta função só cuida das linhas SÓLIDAS (já clicadas).

    'primeiro'/'segundo' (float ou None): os dois cortes.

    'modo' decide ONDE a hachura aparece — e QUANDO:
      - 'aparar' (padrão): mantém o que fica ENTRE os dois cortes, então
        a hachura cobre FORA desse intervalo (da borda esquerda até
        'primeiro', e de 'segundo' até a borda direita) — aparece
        PROGRESSIVAMENTE, uma faixa a cada clique, porque cada faixa já
        faz sentido sozinha (é só "tudo antes/depois deste ponto").
      - 'excluir': REMOVE o que fica entre os dois, então a hachura
        cobre o intervalo [primeiro, segundo] — só aparece depois do
        2º clique (com um clique só não dá pra saber a extensão do
        buraco ainda); o 1º clique desenha só a linha, sem hachura
        nenhuma.
      As bordas ('aparar') vêm do range REAL dos dados já plotados
      (_range_dos_dados, definida mais acima neste módulo), com uma
      margem de 5% pra a hachura alcançar visualmente a moldura do
      gráfico mesmo se o Plotly folgar um pouco o autorange.

    'arrastavel': PAUSADO por enquanto (ver bloco comentado no fim desta
    função) — o parâmetro continua aqui e _linha_guia_corte ainda lê ele
    (só pra engrossar a linha, ver essa função), mas nenhum chamador
    atual passa True; fica pronto pra retomar quando essa interação
    voltar a ser trabalhada.
    """
    fig = go.Figure(fig)
    if primeiro is None and segundo is None:
        return fig

    x_min, x_max = _range_dos_dados(fig, 'x')
    if x_min is None:
        return fig

    span = x_max - x_min
    margem = span * 0.05 if span > 0 else 1
    borda_esquerda, borda_direita = x_min - margem, x_max + margem

    formas = []
    if modo == 'excluir':
        if primeiro is not None:
            formas.append(_linha_guia_corte(primeiro, arrastavel=arrastavel))
        if segundo is not None:
            formas.append(_faixa_hachurada_corte(primeiro, segundo))
            formas.append(_linha_guia_corte(segundo, arrastavel=arrastavel))
    else:
        if primeiro is not None:
            formas.append(_faixa_hachurada_corte(borda_esquerda, primeiro))
            formas.append(_linha_guia_corte(primeiro, arrastavel=arrastavel))
        if segundo is not None:
            formas.append(_faixa_hachurada_corte(segundo, borda_direita))
            formas.append(_linha_guia_corte(segundo, arrastavel=arrastavel))

    # PAUSADO por enquanto: arraste das guias já confirmadas via um
    # manípulo/pílula no meio de cada linha (ver _pilula_arraste, logo
    # acima) — a interação inteira já tinha ficado funcionando e
    # testada (linha/hachura/manípulo sincronizados, limite entre os 2
    # cortes respeitado), mas a decisão foi adiar essa etapa por
    # enquanto ("a barra ainda não está 100%"). Pra retomar:
    #   1) descomentar o bloco abaixo;
    #   2) em callbacks.py: trocar 'arrastavel=False' de volta pra
    #      'arrastavel=(segundo is not None)' em registrar_clique_corte,
    #      e descomentar o callback arrastar_corte inteiro;
    #   3) em renderizadores.py: religar 'config={'edits': {
    #      'shapePosition': True}}' no dcc.Graph;
    #   4) em scripts_js.py: descomentar o bloco 'gd.on(plotly_relayout,
    #      ...)' inteiro dentro de iniciarSelecaoCorte;
    #   5) em icon_menu.css: religar as regras de cursor 'grab'/
    #      'grabbing' pros manípulos (path[data-index='4'/'5']).
    # if arrastavel:
    #     if primeiro is not None:
    #         formas.append(_pilula_arraste(primeiro, span))
    #     if segundo is not None:
    #         formas.append(_pilula_arraste(segundo, span))

    fig.update_layout(shapes=formas)
    return fig
    return fig