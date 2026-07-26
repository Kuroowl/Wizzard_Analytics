import plotly.graph_objects as go

# Paleta fixa (é a paleta padrão do próprio Plotly) — compartilhada com a
# sidebar da interface, pra garantir que a bolinha ao lado do nome da coluna
# bate exatamente com a cor da curva no gráfico.
PALETA_CORES = [
    '#636efa', '#EF553B', '#00cc96', '#ab63fa', '#FFA15A',
    '#19d3f3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
]


def cor_da_coluna(indice):
    """Cor que a N-ésima coluna plotada vai receber — usada tanto aqui
    quanto na sidebar, pra manter os dois sincronizados."""
    return PALETA_CORES[indice % len(PALETA_CORES)]


def construir_figura(df, coluna_x, colunas_y, gerenciador, titulo=None):
    """
    Monta a figura Plotly. Função PURA: não guarda estado, sempre lê o df e
    os rótulos atuais na hora de desenhar — então basta chamar de novo
    depois de qualquer operação (filtro, ajuste, rename) pra refletir o
    estado mais recente.

    Os nomes de eixo e legenda vêm do GerenciadorRotulos, nunca direto do
    nome interno da coluna — assim, um rótulo customizado pelo usuário
    continua aparecendo mesmo depois do df ser recalculado.
    """
    fig = go.Figure()

    for i, coluna in enumerate(colunas_y):
        fig.add_trace(go.Scatter(
            x=df[coluna_x],
            y=df[coluna],
            mode='lines+markers',
            name=gerenciador.rotulo_atual(coluna),
            line=dict(color=cor_da_coluna(i)),
            marker=dict(color=cor_da_coluna(i)),
        ))

    fig.update_layout(
        title=titulo or 'Dados carregados',
        xaxis_title=gerenciador.rotulo_atual(coluna_x),
        yaxis_title='Valor',
        legend_title_text='Séries',
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=50, r=20, t=50, b=40),
    )

    return fig


def construir_figura_serie_temporal(estado, aba_ativa):
    """
    Monta a figura de 'Série Temporal' (linhas) plotando SOMENTE os canais
    que o usuário marcou (estado.canais_selecionados) para o ARQUIVO DA ABA
    ATIVA. Se nenhum canal estiver marcado, retorna uma figura vazia (só os
    eixos, sem nenhuma curva) — a curva só aparece quando o canal é
    selecionado no menu da esquerda.

    Importante: só considera o arquivo da aba ativa. Cada aba tem seu
    próprio gráfico e sua própria seleção de canais; um arquivo aberto em
    outra aba nunca deve aparecer aqui.
    """
    fig = go.Figure()

    if not aba_ativa or aba_ativa not in estado.arquivos:
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=50, r=20, t=20, b=40),
            hovermode='closest',
            uirevision='constant',
        )
        return fig

    dados = estado.arquivos[aba_ativa]
    df = dados['df']
    gerenciador = dados['gerenciador']

    # 1. Identifica a coluna do Eixo X
    colunas_numericas = df.select_dtypes(include='number').columns
    eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
        colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
    )

    # 2. Só entram no gráfico os canais deste arquivo que estão marcados
    #    em estado.canais_selecionados — respeitando a ordem das colunas
    #    do df pra manter a cor sempre consistente com a sidebar.
    colunas_y = [
        col for col in df.columns
        if col != eixo_x and (aba_ativa, col) in estado.canais_selecionados
    ]

    # 3. Plota cada canal selecionado
    #    IMPORTANTE: go.Scattergl (WebGL), não go.Scatter (SVG). Com
    #    arquivos de dezenas de milhares de linhas, marcar vários canais
    #    pode facilmente passar de meio milhão de pontos plotados de uma
    #    vez — SVG cria um nó no DOM por ponto e trava a aba do navegador
    #    inteira (o clique de fechar aba "não responde" nesse cenário
    #    porque a thread principal do navegador está ocupada demais pra
    #    processar qualquer clique, não porque o callback não disparou).
    #    Scattergl desenha via GPU/canvas e aguenta essa escala numa boa.
    for indice_cor, coluna in enumerate(colunas_y):
        rotulo = gerenciador.rotulo_atual(coluna)

        fig.add_trace(go.Scattergl(
            x=df[eixo_x],
            y=df[coluna],
            mode='lines',
            name=rotulo,
            line=dict(color=cor_da_coluna(indice_cor)),
        ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        # 'x unified' recalcula a distância do mouse contra TODOS os
        # pontos de TODAS as séries a cada movimento — outro ponto pesado
        # com dezenas de milhares de linhas. 'closest' é O(1) por trace.
        hovermode='closest',
        uirevision='constant',
    )
    return fig