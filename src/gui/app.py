from dash import Dash, dcc, html, Input, Output, ctx

from src.core.plotting.plotter import construir_figura
from src.gui.eventos_graficos import extrair_edicao_titulo, extrair_edicao_eixo, extrair_edicao_legenda


def criar_app(df, coluna_x, colunas_y, gerenciador):
    """
    Monta o app Dash (layout + callbacks) a partir de um estado já pronto:
    df carregado, colunas escolhidas para o gráfico, e um GerenciadorRotulos
    já registrado com as colunas do df.

    Esta função não decide QUAL arquivo carregar nem QUANDO rodar o
    servidor — isso é responsabilidade do main.py. Assim, no futuro, um
    botão "abrir outro arquivo" na interface pode chamar criar_app() de
    novo (ou atualizar o estado interno) sem reiniciar o processo inteiro.
    """

    def figura_atual():
        # plotter.construir_figura é pura: sempre lê df/gerenciador atuais
        return construir_figura(df, coluna_x, colunas_y, gerenciador, titulo='Dados carregados')

    app = Dash(__name__)
    app.layout = html.Div([
        html.H3('Análise de dados'),
        dcc.Graph(id='grafico', figure=figura_atual(), config={'editable': True}),
        html.Pre(
            id='log-eventos',
            children='Edite o título, o eixo X ou a legenda no gráfico acima (clique duplo no texto).',
            style={'background': '#f4f4f4', 'padding': '10px', 'whiteSpace': 'pre-wrap'},
        ),
    ])

    @app.callback(
        Output('grafico', 'figure'),
        Output('log-eventos', 'children'),
        Input('grafico', 'relayoutData'),
        Input('grafico', 'restyleData'),
        prevent_initial_call=True,
    )
    def ao_editar_grafico(relayout_data, restyle_data):
        log = []
        gatilho = ctx.triggered_id

        if gatilho == 'grafico' and relayout_data:
            log.append(f"relayoutData bruto: {relayout_data}")

            novo_titulo = extrair_edicao_titulo(relayout_data)
            if novo_titulo:
                log.append(
                    f"-> título do gráfico mudou para '{novo_titulo}' "
                    "(é só do layout, não passa pelo GerenciadorRotulos)"
                )

            novo_rotulo_x = extrair_edicao_eixo(relayout_data, 'xaxis')
            if novo_rotulo_x:
                try:
                    gerenciador.renomear(coluna_x, novo_rotulo_x)
                    log.append(f"-> coluna interna '{coluna_x}' renomeada para '{novo_rotulo_x}'")
                except ValueError as e:
                    log.append(f"-> rename recusado: {e}")

        if restyle_data:
            log.append(f"restyleData bruto: {restyle_data}")
            edicao = extrair_edicao_legenda(restyle_data)
            if edicao:
                indice_trace, novo_nome = edicao
                nome_interno = colunas_y[indice_trace]
                try:
                    gerenciador.renomear(nome_interno, novo_nome)
                    log.append(f"-> coluna interna '{nome_interno}' renomeada para '{novo_nome}'")
                except ValueError as e:
                    log.append(f"-> rename recusado: {e}")

        return figura_atual(), '\n'.join(log) if log else 'Nenhum evento reconhecido ainda.'

    return app
