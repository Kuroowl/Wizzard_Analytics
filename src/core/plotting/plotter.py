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
    Monta a figura de 'Série Temporal' (linhas) plotando AUTOMATICAMENTE
    todos os canais numéricos disponíveis no(s) arquivo(s) ativo(s), 
    desconsiderando apenas a coluna definida como Eixo X.
    """
    fig = go.Figure()
    multiplos_arquivos = len(estado.arquivos) > 1
    indice_cor = 0  # Controle global para a paleta de cores não repetir na mesma figura

    # Percorre os arquivos abertos no estado
    for nome_arquivo, dados in estado.arquivos.items():
        df = dados['df']
        gerenciador = dados['gerenciador']

        # 1. Identifica a coluna do Eixo X
        colunas_numericas = df.select_dtypes(include='number').columns
        eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
            colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
        )

        # 2. Pega TODAS as colunas numéricas, removendo apenas o Eixo X
        colunas_y = [col for col in colunas_numericas if col != eixo_x]

        # Caso o arquivo não tenha colunas numéricas extras, tenta usar todas menos o eixo X
        if not colunas_y:
            colunas_y = [col for col in df.columns if col != eixo_x]

        # 3. Plota cada canal encontrado
        for coluna in colunas_y:
            rotulo = gerenciador.rotulo_atual(coluna)
            
            # Se houver múltiplos arquivos, adiciona o nome do arquivo no rótulo da legenda
            nome_trace = f"{nome_arquivo} → {rotulo}" if multiplos_arquivos else rotulo

            fig.add_trace(go.Scatter(
                x=df[eixo_x],
                y=df[coluna],
                mode='lines',
                name=nome_trace,
                line=dict(color=cor_da_coluna(indice_cor)),
            ))
            indice_cor += 1

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',
    )
    return fig