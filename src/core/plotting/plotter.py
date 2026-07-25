import pandas as pd
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


def _parece_coluna_contador(serie):
    """
    Detecta colunas que são só um CONTADOR/ÍNDICE de linha (ex: 'N#' de
    aparelhos Novus), não um canal de sinal de verdade — reconhece pelo
    COMPORTAMENTO (incrementa exatamente +1 a cada linha), não pelo nome,
    porque cada fabricante rotula essa coluna de um jeito diferente.

    Por quê isso importa: se essa coluna entrar na lista de canais
    plotados junto com sinais reais (pressão, temperatura, etc.), ela
    domina a escala do eixo Y (pode ir de 0 a dezenas de milhares de
    linhas) e "achata" todas as curvas de sinal de verdade numa linha
    invisível grudada no zero — o gráfico parece estar em branco, mas na
    verdade só está com a escala errada.
    """
    valores = pd.to_numeric(serie, errors='coerce')
    if valores.isna().any() or len(valores) < 3:
        return False
    diffs = valores.diff().dropna()
    return len(diffs) > 0 and (diffs == 1).all()


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


def construir_figura_serie_temporal(estado, nome_arquivo):
    """
    Monta a figura de 'Série Temporal' (linhas) para UM ÚNICO arquivo — o
    da aba que está sendo plotada — nunca para todos os arquivos abertos ao
    mesmo tempo. Cada aba tem seu próprio gráfico, independente: gerar ou
    alterar o gráfico de uma aba não deve tocar no gráfico de nenhuma
    outra aba já gerada, e trocar de aba só troca qual gráfico já pronto é
    exibido (isso é responsabilidade dos callbacks, não desta função).

    Eixo X: automaticamente 'Tempo_decorrido_s' (tempo decorrido em
    segundos), que o extractor já calcula no carregamento — esse é o
    padrão pra qualquer plot do tipo 'série temporal'.

    Canais (eixo Y): SÓ os que o usuário selecionou manualmente para ESTE
    arquivo (estado.canais_selecionados, filtrado por nome_arquivo). Se
    nenhum canal desse arquivo estiver selecionado ainda, cai no modo
    automático: todas as colunas numéricas exceto o eixo X e colunas tipo
    'contador de linha' (ex: 'N#'), que dominariam a escala do eixo Y e
    esconderiam os canais de sinal de verdade (ver _parece_coluna_contador).

    Combinar vários arquivos numa mesma figura (o botão 'fundir arquivos')
    é uma ação DIFERENTE e explícita — ver
    construir_figura_serie_temporal_combinada — não acontece aqui.
    """
    if nome_arquivo not in estado.arquivos:
        return go.Figure()

    dados = estado.arquivos[nome_arquivo]
    df = dados['df']
    gerenciador = dados['gerenciador']

    fig = go.Figure()

    # 1. Identifica a coluna do Eixo X (tempo decorrido, calculado no
    # carregamento; cai pra primeira numérica só se por algum motivo essa
    # coluna não existir nesse arquivo)
    colunas_numericas = df.select_dtypes(include='number').columns
    eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
        colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
    )

    # 2. Canais selecionados manualmente pelo usuário PARA ESTE arquivo
    canais_marcados = [
        coluna for (arq, coluna) in estado.canais_selecionados
        if arq == nome_arquivo and coluna in df.columns and coluna != eixo_x
    ]

    if canais_marcados:
        colunas_y = canais_marcados
    else:
        # Nada selecionado ainda: modo automático — todas as numéricas,
        # menos o eixo X e colunas tipo 'contador de linha'.
        colunas_y = [
            col for col in colunas_numericas
            if col != eixo_x and not _parece_coluna_contador(df[col])
        ]
        if not colunas_y:
            colunas_y = [col for col in df.columns if col != eixo_x]

    # 3. Plota cada canal encontrado
    for i, coluna in enumerate(colunas_y):
        fig.add_trace(go.Scatter(
            x=df[eixo_x],
            y=df[coluna],
            mode='lines',
            name=gerenciador.rotulo_atual(coluna),
            line=dict(color=cor_da_coluna(i)),
        ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',
        xaxis_title=gerenciador.rotulo_atual(eixo_x) if eixo_x in df.columns else None,
    )
    return fig


def construir_figura_serie_temporal_combinada(estado, nomes_arquivos=None):
    """
    Versão MULTI-arquivo: combina os canais selecionados de vários arquivos
    numa única figura, prefixando a legenda com o nome do arquivo. Isso é
    uma ação EXPLÍCITA e separada (pensada pro botão 'fundir arquivos'),
    nunca o comportamento padrão de gerar/atualizar o gráfico de uma aba.

    nomes_arquivos: lista de arquivos a combinar; se None, usa todos os
    arquivos abertos em estado.arquivos.
    """
    fig = go.Figure()
    nomes = nomes_arquivos if nomes_arquivos is not None else list(estado.arquivos.keys())
    indice_cor = 0

    for nome_arquivo in nomes:
        if nome_arquivo not in estado.arquivos:
            continue
        dados = estado.arquivos[nome_arquivo]
        df = dados['df']
        gerenciador = dados['gerenciador']

        colunas_numericas = df.select_dtypes(include='number').columns
        eixo_x = estado.coluna_x if estado.coluna_x in df.columns else (
            colunas_numericas[0] if len(colunas_numericas) else df.columns[0]
        )

        canais_marcados = [
            coluna for (arq, coluna) in estado.canais_selecionados
            if arq == nome_arquivo and coluna in df.columns and coluna != eixo_x
        ]
        colunas_y = canais_marcados or [
            col for col in colunas_numericas
            if col != eixo_x and not _parece_coluna_contador(df[col])
        ]

        for coluna in colunas_y:
            rotulo = gerenciador.rotulo_atual(coluna)
            fig.add_trace(go.Scatter(
                x=df[eixo_x],
                y=df[coluna],
                mode='lines',
                name=f"{nome_arquivo} → {rotulo}",
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