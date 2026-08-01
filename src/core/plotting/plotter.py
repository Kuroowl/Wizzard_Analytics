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

            fig.add_trace(go.Scatter(
                x=x_valores,
                y=y_valores,
                mode='lines',
                name=rotulo,
                line=dict(
                    color=(prefs.cor if prefs and prefs.cor else cor_da_coluna(indice_cor)),
                    width=(prefs.espessura if prefs else 1.0),
                    dash=(prefs.estilo_linha if prefs else 'solid'),
                ),
            ))

    fig.update_layout(
        template='plotly_white',
        margin=dict(l=50, r=20, t=20, b=40),
        hovermode='x unified',
        uirevision='constant',

    )

    if houve_amostragem:
        fig.add_annotation(
            text=(
                f"Exibindo até {MAX_PONTOS_EXIBICAO:,} pontos por curva "
                f"(amostra uniforme) — dados completos preservados"
            ).replace(',', '.'),
            xref='paper', yref='paper', x=0, y=1.06,
            showarrow=False, font=dict(size=11, color='#888'),
        )

        # Alimenta a caixinha de alerta do rodapé (só uma vez por arquivo —
        # regenerar o gráfico ao marcar/desmarcar canal não deve empilhar
        # o mesmo aviso de novo).
        mensagem = (
            f"Aviso: o arquivo tem mais de {MAX_PONTOS_EXIBICAO:,} linhas — o gráfico "
            f"exibe uma amostra uniforme por curva, mas os dados completos "
            f"continuam preservados para filtros/exportação."
        ).replace(',', '.')
        arquivo.adicionar_aviso(mensagem)

    return fig