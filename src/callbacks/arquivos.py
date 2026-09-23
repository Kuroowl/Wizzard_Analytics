"""
Callbacks de arquivos: carregar um arquivo pela área de upload.

(Fundir e exportar arquivos também morarão aqui quando forem implementados.)
"""
from dash import Input, Output, State, no_update
from dash.exceptions import PreventUpdate

from src.callbacks._comum import estados_toolbar
from src.gui.feedback import Feedback, saida_feedback
from src.gui.renderizadores import renderizar_area_grafico
from src.gui.rodape import obter_estado_rodape
from src.utils.helpers import carregar_dados_de_upload


def registrar_callbacks_arquivos(app, estado):

    @app.callback(
        Output('aba-ativa-store', 'data'),
        saida_feedback('upload'),
        Output('nova-analise', 'disabled'),
        Output('fundir-arquivos', 'disabled'),
        Output('nova-amostra', 'disabled'),
        Output('exportar-dados', 'disabled'),
        Output('container-grafico', 'children', allow_duplicate=True),
        Output('rodape-info-arquivo', 'children'),
        Output('rodape-alerta-badge', 'children'),
        Output('rodape-alerta-badge', 'className'),
        Output('rodape-alerta-popup', 'children'),
        Input('upload-arquivo', 'contents'),
        State('upload-arquivo', 'filename'),
        State('aba-ativa-store', 'data'),
        prevent_initial_call=True,
    )
    def ao_fazer_upload(conteudo, nome_arquivo, aba_atual):
        if conteudo is None:
            raise PreventUpdate

        if nome_arquivo in estado.arquivos:
            # Arquivo já aberto: mensagem PERSISTENTE (cancela qualquer
            # troca agendada). Nenhuma contagem de arquivo mudou, então os
            # critérios de habilitação ficam como já estavam.
            sem_arquivo, sem_2_arquivos, _ = estados_toolbar(estado, nome_arquivo)
            feedback = Feedback.aviso(f"O arquivo '{nome_arquivo}' já foi aberto!")
            return (nome_arquivo, feedback,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    no_update,
                    *obter_estado_rodape(estado, nome_arquivo))
        try:
            df, avisos, info = carregar_dados_de_upload(conteudo, nome_arquivo)
            estado.adicionar_arquivo(nome_arquivo, df, avisos, info)

            # FORÇA a re-renderização da área central para desenhar a grade azul
            area_grafico = renderizar_area_grafico(estado)

            # Mensagem TEMPORÁRIA: aparece, some sozinha em ~3.5s e dá lugar
            # à próxima instrução — quem cuida do timer é o rodapé.
            feedback = Feedback.sucesso(
                f"Arquivo '{nome_arquivo}' carregado com sucesso!",
                depois=Feedback.instrucao('Escolha uma opção de gráfico...'),
            )

            # O arquivo recém-carregado ainda não tem gráfico gerado, então
            # 'aparar-dados'/'excluir-dados'/'exportar-grafico' continuam
            # desabilitados (não fazem parte deste callback — ver
            # gerar_grafico_serie_temporal). Só o que depende de "existe
            # arquivo" muda aqui: nova-analise, nova-amostra e exportar-dados.
            sem_arquivo, sem_2_arquivos, _ = estados_toolbar(estado, nome_arquivo)

            return (nome_arquivo, feedback,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    area_grafico,
                    *obter_estado_rodape(estado, nome_arquivo))
        except Exception as e:
            sem_arquivo, sem_2_arquivos, _ = estados_toolbar(estado, aba_atual)
            feedback = Feedback.erro(f'Erro ao abrir arquivo: {e}')
            return (aba_atual, feedback,
                    sem_arquivo, sem_2_arquivos, sem_arquivo, sem_arquivo,
                    no_update,
                    *obter_estado_rodape(estado, aba_atual))
