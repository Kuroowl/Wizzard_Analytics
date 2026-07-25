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
    Monta a figura de 'Série Temporal' considerando APENAS os canais
    selecionados pertencentes ao arquivo da aba ativa atual.
    """
    fig = go.Figure()

    # Se a aba_ativa não estiver nos arquivos carregados, retorna figura vazia
    if not aba_ativa or aba_ativa not in estado.arquivos:
        return fig

    dados = estado.arquivos[aba_ativa]
    df = dados['df']
    gerenciador = dados['gerenciador']

    # 1. Filtra os canais selecionados apenas do arquivo PAÍS/ATIVO desta aba
    canais_da_aba = [
        (arq, col) for (arq, col) in estado.canais_selecionados 
        if arq == aba_ativa
    ]

    # 2. Descobre o Eixo X
    colunas_numericas = df.select_dtypes(include='number').columns
    eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
        colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
    )

    # 3. Desenha apenas os canais selecionados desta aba
    for i, (nome_arquivo, coluna) in enumerate(sorted(canais_da_aba)):
        rotulo = gerenciador.rotulo_atual(coluna)

        fig.add_trace(go.Scatter(
            x=df[eixo_x],
            y=df[coluna],
            mode='lines',
            name=rotulo,
            line=dict(color=cor_da_coluna(i)),
        ))

    # 4. Configura o layout
    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',  # Preserva pan/zoom interativo
        xaxis_title=estado.coluna_x if estado.coluna_x in df.columns else eixo_x,
        yaxis_title="Valor",
    )

    # Se não tiver nenhum canal selecionado nesta aba, exibe a instrução
    if not canais_da_aba:
        fig.add_annotation(
            text="Selecione um ou mais canais na barra lateral para visualizar no gráfico.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )

    return fig