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


def construir_figura_serie_temporal(estado):
    """
    Monta a figura de 'Série Temporal' (linhas) a partir dos canais
    selecionados em estado.canais_selecionados — que podem vir de vários
    arquivos ao mesmo tempo (por isso não usa construir_figura, que assume
    um df/gerenciador únicos).

    Usa o rótulo ATUAL de cada coluna (via o GerenciadorRotulos do arquivo
    dela) na legenda — não o nome interno bruto — e a mesma paleta de cores
    compartilhada do resto do app.

    Eixo X: tenta 'Tempo_decorrido_s' primeiro (a coluna que o extractor.py
    já gera sozinho quando acha Data/Hora no arquivo bruto — é o padrão de
    estado.coluna_x). Só cai pra primeira coluna numérica do arquivo se ESSE
    arquivo específico não tiver conseguido gerar essa coluna (ex: sem
    Data/Hora reconhecível no cabeçalho). Não escondemos nem mexemos nas
    outras colunas de data/hora no menu lateral — elas continuam lá,
    disponíveis, mesmo sem serem usadas como eixo X aqui.
    """
    fig = go.Figure()
    multiplos_arquivos = len(estado.arquivos) > 1

    for i, (nome_arquivo, coluna) in enumerate(sorted(estado.canais_selecionados)):
        if nome_arquivo not in estado.arquivos:
            continue

        dados = estado.arquivos[nome_arquivo]
        df = dados['df']
        gerenciador = dados['gerenciador']

        colunas_numericas = df.select_dtypes(include='number').columns
        eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
            colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
        )

        rotulo = gerenciador.rotulo_atual(coluna)
        # com mais de 1 arquivo aberto, prefixa o nome do arquivo — evita
        # confundir duas colunas de mesmo nome vindas de arquivos diferentes
        nome_trace = f"{nome_arquivo} → {rotulo}" if multiplos_arquivos else rotulo

        fig.add_trace(go.Scatter(
            x=df[eixo_x],
            y=df[coluna],
            mode='lines',
            name=nome_trace,
            line=dict(color=cor_da_coluna(i)),
        ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',
    )
    return fig