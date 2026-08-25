from dash import dcc, html

from src.gui.components import icone_colorido
from src.gui.renderizadores import (
    renderizar_area_grafico, renderizar_info_rodape,
    renderizar_badge_alerta, renderizar_popup_alerta,
    renderizar_painel_direito_padrao,
)

# Tempo (ms) que uma mensagem "temporária" do mago fica visível antes de
# desaparecer sozinha — ver 'rodape-timer-mensagem' e o callback
# '_expirar_mensagem_temporaria' em callbacks.py.
DURACAO_MENSAGEM_TEMPORARIA_MS = 3500


def montar_layout(estado):
    """
    Monta a árvore de componentes do app. Os estados iniciais de habilitação
    dos botões são calculados a partir de 'estado' (em vez de fixos), pra
    ficar consistente mesmo no caso raro de a app já nascer com arquivos
    carregados.
    """
    sem_arquivo = len(estado.arquivos) == 0
    menos_de_2_arquivos = len(estado.arquivos) < 2
    # 'sem_grafico' aqui é só pro estado INICIAL da toolbar (não há aba
    # ativa ainda nesse ponto do carregamento da página) — os callbacks
    # depois disso sempre olham o gráfico da ABA ATIVA especificamente
    # (ver _estados_toolbar em callbacks.py), nunca "algum arquivo".
    sem_grafico = not estado.algum_arquivo_com_grafico()

    return html.Div(className='app-shell', children=[
        dcc.Store(id='aba-ativa-store', data=None),
        # Espelha 'edicao-curva-dado'.value. Existe sempre (diferente do
        # dropdown, que só nasce quando o painel de edição está aberto) —
        # é isso que permite ler a curva em edição como State em callbacks
        # que disparam independente do painel estar aberto (ver
        # gerenciar_selecao_canais em callbacks.py), sem cair no erro
        # "A nonexistent object was used in an State of a Dash callback".
        dcc.Store(id='edicao-curva-dado-atual', data=None),

        # 'canal-em-edicao-store': None enquanto nenhum canal está sendo
        # renomeado; vira {'arquivo': <aba>, 'coluna': <nome_interno>}
        # entre o clique no lápis (✏️, ver alternar_edicao_canal em
        # callbacks.py) e a confirmação (Enter ou clicar fora, ver
        # confirmar_edicao_canal) — é isso que diz pra
        # renderizar_colunas_da_aba_ativa (renderizadores.py) qual linha
        # específica da lista deve nascer com um <input> editável no
        # lugar do rótulo estático, em vez de precisar reconstruir a
        # lista inteira num modo "tudo editável".
        dcc.Store(id='canal-em-edicao-store', data=None),

        # 'nclicks-padrao-store': {} inicialmente, depois um dict
        # {chave_do_id_json: último_n_clicks_processado} — rastreio
        # compartilhado por TODOS os callbacks que escutam cliques em
        # componentes de padrão coringa ({'type':..., ALL}) cuja LISTA
        # de componentes casados é reconstruída do zero por outro
        # callback (abas — 'aba-item'/'botao-fechar-aba' — e canais —
        # 'linha-canal'/'botao-excluir-canal'/'botao-editar-canal', ver
        # gerenciar_abas/gerenciar_selecao_canais/alternar_edicao_canal
        # em callbacks.py).
        #
        # Toda vez que a lista-mãe (abas ou canais) é reconstruída
        # (upload de arquivo, gerar/fechar gráfico, trocar de aba,
        # marcar/desmarcar canal — qualquer callback com Output nessas
        # listas), os botões daquela linha nascem de novo com
        # 'n_clicks=0' no Python (são componentes NOVOS, não os mesmos
        # de antes) — e o Dash trata esse reaparecimento de um id que
        # já casava um Input de padrão coringa como um "disparo" válido
        # do callback, MESMO sem clique nenhum do usuário (é assim que
        # o Dash lida com componentes novos entrando num padrão
        # coringa). Sem rastrear o ÚLTIMO valor já visto de cada botão
        # (é isso que este Store guarda), não dá pra distinguir esse
        # "disparo fantasma" de um clique de verdade só olhando
        # 'ctx.triggered' — os dois aparecem lá igualzinho. Os
        # callbacks acima só tratam como clique de VERDADE quando o
        # valor reportado for MAIOR que o último valor guardado aqui
        # (nunca só "diferente de None/vazio") — ver
        # _processar_cliques_padrao em callbacks.py.
        dcc.Store(id='nclicks-padrao-store', data={}),

        # 'modo-nova-analise-store': True/False — 'Nova análise' na
        # toolbar deixou de ser um dcc.Upload (nunca esteve de fato
        # conectado a nenhum callback de 'contents', então clicar nele
        # só abria o seletor de arquivo do sistema à toa — ver
        # ao_fazer_upload em callbacks.py, que só reage a
        # 'upload-arquivo') e virou um BOTÃO DE LIGA/DESLIGA: um modo de
        # trabalho alternativo, onde a área central e o painel de
        # edição saem de cena (cobertos por uma camada opaca própria,
        # com watermark de analysis.svg/gear.svg) sem que nada por
        # baixo seja destruído — o gráfico e a edição continuam
        # exatamente como estavam (são 'propriedade do objeto', não
        # precisam de nenhum Store à parte pra isso), só ficam
        # temporariamente encobertos. Ver alternar_modo_nova_analise em
        # callbacks.py.
        dcc.Store(id='modo-nova-analise-store', data=False),

        # 'calc-expressao-store': lista de TOKENS da calculadora do modo
        # 'Nova Análise' (ver renderizar_calculadora, renderizadores.py,
        # e a barra de cálculo dentro de 'area-modo-nova-analise').
        # Cada token é {'display': <texto mostrado na barra>, 'codigo':
        # <fragmento de expressão Python de verdade, usado só na hora
        # de avaliar>} — os dois SEPARADOS de propósito: um botão de
        # coluna mostra o RÓTULO (ex: 'Vazão de entrada') mas o código
        # de verdade referencia a coluna por 'nome_interno' via um
        # dicionário seguro ('col["Vazao_s"]', nunca o nome bruto
        # solto na expressão — ver _avaliar_expressao_calculadora em
        # callbacks.py), então rótulos com espaço/acento/caractere
        # especial nunca quebram a avaliação. Uma LISTA (não uma string
        # só) também permite 'Apagar' (⌫) remover só o ÚLTIMO token
        # inteiro (um nome de coluna inteiro, uma função inteira como
        # 'sin(') em vez de um caractere por vez.
        dcc.Store(id='calc-expressao-store', data=[]),

        # 'corte-selecao-store': None enquanto nenhuma seleção de corte
        # está em andamento; durante 'Aparar dados' (e, no futuro,
        # 'Excluir dados' — mesma mecânica, ver aparar_dados/excluir_dados
        # em src/core/operations/sampling.py), guarda
        # {'tipo': 'aparar', 'aba': <arquivo>, 'primeiro': <x ou None>,
        # 'segundo': <x ou None>} — ver iniciar_selecao_corte/
        # registrar_clique_corte/confirmar_corte/cancelar_corte em
        # callbacks.py.
        dcc.Store(id='corte-selecao-store', data=None),
        # Ponte entre o clique real do usuário NO GRÁFICO (capturado via
        # JS puro — iniciarSelecaoCorte em scripts_js.py, que já resolve
        # pixel -> valor de dado usando o range atual do eixo, sem
        # round-trip nenhum pro servidor só pra isso) e um callback Dash
        # de verdade: o JS escreve o valor aqui (mesmo truque de setter
        # nativo + evento 'input' usado no seletor de cor) e
        # registrar_clique_corte (callbacks.py) reage a isso como um
        # Input comum. Fica escondido — não é um campo que o usuário
        # preenche à mão.
        dcc.Input(id='corte-clique-x', type='number', value=None, style={'display': 'none'}),
        # Mesma ponte JS -> Dash de 'corte-clique-x', só que pro
        # ARRASTE das linhas de corte já confirmadas (só liberado
        # depois do 2º clique — ver 'arrastavel' em aplicar_guias_corte,
        # plotter.py) — um campo pra cada linha (não dá pra reaproveitar
        # um só: precisa saber QUAL corte moveu, e o nome do campo já
        # resolve isso sem precisar mandar um índice à parte). Ver
        # 'plotly_relayout' em iniciarSelecaoCorte (scripts_js.py) e
        # arrastar_corte (callbacks.py).
        dcc.Input(id='corte-arraste-primeiro', type='number', value=None, style={'display': 'none'}),
        dcc.Input(id='corte-arraste-segundo', type='number', value=None, style={'display': 'none'}),

        html.Div(className='menubar', children=[
            html.Span('Arquivo', className='menubar-item'),
            html.Span('Editar', className='menubar-item'),
            html.Span('Ajuda', className='menubar-item'),
        ]),

        html.Div(className='toolbar', children=[
            html.Div(id='toolbar-icones', className='toolbar-icones', children=[
                dcc.Upload(
                    id='upload-arquivo',
                    children=html.Div([icone_colorido('AddFile_icon.png'), html.Span('Carregar arquivo', className='toolbar-tooltip')]),
                    className='toolbar-upload',
                    multiple=False,
                ),
                # 'aparar-dados'/'excluir-dados' são html.Button (não
                # dcc.Upload como os outros) — precisam de um clique DE
                # VERDADE (n_clicks) pra entrar no modo de seleção no
                # gráfico; um dcc.Upload abriria o seletor de arquivo
                # nativo do sistema, o que não faz sentido nenhum aqui.
                # Os dois usam o MESMO fluxo de 2 cliques (ver
                # iniciar_selecao_corte, callbacks.py) — só muda o
                # 'tipo' gravado em 'corte-selecao-store' e, por
                # tabela, onde a hachura aparece e qual operação de
                # dados roda no fim (aparar_dados vs excluir_dados,
                # src/core/operations/sampling.py).
                html.Button(
                    id='aparar-dados',
                    children=html.Div([icone_colorido('TrimData_icon.png'), html.Span('Aparar dados', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_grafico, n_clicks=0,
                ),
                html.Button(
                    id='excluir-dados',
                    children=html.Div([icone_colorido('CutData_icon.png'), html.Span('Excluir dados', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_grafico, n_clicks=0,
                ),
                # 'nova-analise' era um dcc.Upload, mas NUNCA esteve
                # ligado a nenhum callback de 'contents' (só
                # 'upload-arquivo' é — ver ao_fazer_upload,
                # callbacks.py) — clicar nele só abria o seletor de
                # arquivo do sistema sem fazer nada com o resultado.
                # Virou um <button> de verdade (mesmo motivo de
                # 'aparar-dados'/'excluir-dados' acima: precisa de
                # 'n_clicks' de verdade) porque agora é um LIGA/DESLIGA
                # — ver alternar_modo_nova_analise em callbacks.py, que
                # cobre a área central e o painel de edição com uma
                # camada própria (analysis.svg / gear.svg) enquanto
                # este modo está ativo. A classe 'ativo' (ver
                # icon_menu.css) dá o visual "pressionado".
                html.Button(
                    id='nova-analise',
                    children=html.Div([icone_colorido('NewAnalysis_icon.png'), html.Span('Nova análise', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_arquivo, n_clicks=0,
                ),
                dcc.Upload(
                    id='nova-amostra',
                    children=html.Div([icone_colorido('SampleData_icon.png'), html.Span('Nova Amostragem', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_arquivo,
                    multiple=False,
                ),
                dcc.Upload(
                    id='fundir-arquivos',
                    children=html.Div([icone_colorido('MergeData_icon.png'), html.Span('Fundir arquivos', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=menos_de_2_arquivos,
                    multiple=False,
                ),
                dcc.Upload(
                    id='exportar-grafico',
                    children=html.Div([icone_colorido('ExportGraph_icon.png'), html.Span('Salvar gráfico', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_grafico,
                    multiple=False,
                ),
                dcc.Upload(
                    id='exportar-dados',
                    children=html.Div([icone_colorido('ExportData_icon.png'), html.Span('Exportar dados', className='toolbar-tooltip')]),
                    className='toolbar-upload', disabled=sem_arquivo,
                    multiple=False,
                ),
            ]),

            # Prompt 'Confirmar seleção?' — nasce escondido
            # (style display:none; ver iniciar_selecao_corte/
            # registrar_clique_corte em callbacks.py, que só o revela
            # depois do SEGUNDO clique no gráfico, quando os dois cortes
            # já estão marcados). Fica ao lado dos ícones (não no
            # rodapé) porque é uma decisão sobre a AÇÃO da toolbar que
            # está em andamento, não uma mensagem passageira do mago.
            html.Div(
                id='toolbar-confirmacao-corte',
                className='toolbar-confirmacao',
                style={'display': 'none'},
                children=[
                    # Barra de "algo está acontecendo" — mesmo padrão
                    # visual da barra do rodapé (reaproveita as classes
                    # 'rodape-carregando'/'rodape-concluido'), mas quem
                    # dispara ela agora é a PRÓPRIA transição deste
                    # 'style.display' pra 'flex' (ver
                    # iniciarBarraCarregamentoToolbar em scripts_js.py) —
                    # não mais o carregamento do Dash. Fica ATRÁS do
                    # grupo mago/texto/botões (position:absolute + o
                    # grupo com z-index implícito por cima via
                    # 'position: relative').
                    html.Div(id='toolbar-confirmacao-progresso', className='toolbar-confirmacao-progresso'),
                    # Mago + texto + botões agrupados num wrapper só —
                    # é ELE (não cada filho individualmente) que o JS
                    # esconde por um instante assim que o prompt aparece
                    # e revela só depois da barra "carregar" (ver
                    # '.toolbar-confirmacao-conteudo' em icon_menu.css),
                    # pra a barra chamar atenção PRIMEIRO, antes do
                    # usuário ler a pergunta.
                    html.Div(
                        className='toolbar-confirmacao-conteudo',
                        children=[
                            html.Span('🧙‍♂️', className='toolbar-confirmacao-mago'),
                            html.Span('Confirmar seleção?', className='toolbar-confirmacao-texto'),
                            html.Button('✓', id='corte-confirmar', className='toolbar-confirmacao-btn confirmar', n_clicks=0, title='Confirmar'),
                            html.Button('✕', id='corte-cancelar', className='toolbar-confirmacao-btn cancelar', n_clicks=0, title='Cancelar'),
                        ],
                    ),
                ],
            ),
        ]),

        html.Div(className='corpo', children=[

            html.Div(id='sidebar-principal', className='sidebar', children=[
                html.Div(className='abas-wrapper', children=[
                    html.Button('‹', id='aba-nav-esquerda', className='aba-nav-btn', n_clicks=0),
                    html.Div(id='container-abas-chrome', className='tabs-chrome-container'),
                    html.Button('›', id='aba-nav-direita', className='aba-nav-btn', n_clicks=0),
                ]),
                html.Div('Dados do arquivo:', className='sidebar-secao-titulo'),
                html.Div(id='lista-canais-aba', className='menu-canais-container')
            ]),

            html.Div(id='divisor-resize', className='divisor-resize'),

            html.Div(className='centro', children=[
                dcc.Loading(
                    id="loading-grafico",
                    type="circle",
                    children=html.Div(
                        id='container-grafico',
                        className='area-grafico-container',
                        children=renderizar_area_grafico(estado),
                    ),
                ),
                # Camada do "modo Nova Análise" — cobre '.centro'
                # inteiro por CIMA de '#container-grafico' (mesma
                # técnica de 'position:absolute; inset:0' que
                # '.area-grafico-container' já usa, ver
                # central_menu.css) quando 'nova-analise' está
                # pressionado (ver alternar_modo_nova_analise,
                # callbacks.py). NASCE ESCONDIDA (display:none) —
                # importante que seja só isso (não um 'children'
                # trocado): o gráfico por baixo continua existindo e
                # renderizado o tempo todo, só fica coberto/inacessível
                # enquanto este modo está ligado, então nada precisa
                # ser salvo/restaurado à parte pra voltar exatamente
                # como estava ao desligar.
                html.Div(id='area-modo-nova-analise', className='area-modo-nova-analise', style={'display': 'none'}),
            ]),

            html.Div(id='divisor-resize-edit', className='divisor-resize'),

            # A cor/watermark de 'painel-direito' NÃO muda mais sozinha
            # quando um gráfico é gerado — só quando o usuário clica em
            # 'Iniciar edição' (ver ativar_modo_edicao em callbacks.py).
            # O botão em si nasce desabilitado (não há aba ativa ainda
            # neste ponto do carregamento da página; os callbacks reavaliam
            # isso a partir daqui olhando o gráfico da aba ativa — ver
            # _estados_toolbar).
            #
            # 'iniciar-edicao' é FIXO aqui (fora de 'painel-direito-
            # -conteudo', que é o pedaço que troca de children entre o
            # estado 'padrão' e o card 'Curva'). Antes o botão nascia e
            # morria junto com esse conteúdo trocável — e qualquer
            # callback que tentasse setar seu 'disabled' enquanto o card
            # 'Curva' estava na tela (ex: subir um arquivo novo com outra
            # aba em edição) quebrava com "A nonexistent object was used
            # in an Output", porque o id não existia naquele instante.
            # Com o botão sempre presente, isso não acontece mais — a
            # visibilidade dele quando o card 'Curva' está aberto é só
            # CSS (.painel-direito.ativa .botao-iniciar-edicao, ver
            # edit_menu.css), não remoção do DOM.
            html.Div(id='painel-direito', className='painel-direito', children=[
                html.Div(
                    id='painel-direito-conteudo',
                    className='painel-direito-conteudo',
                    children=renderizar_painel_direito_padrao(disabled=True),
                ),
                html.Button(
                    '🎨 Iniciar edição',
                    id='iniciar-edicao',
                    className='botao-iniciar-edicao',
                    disabled=True,
                    n_clicks=0,
                ),
                # Camada do "modo Nova Análise" — mesmo espírito da
                # irmã em '.centro' (ver 'area-modo-nova-analise' acima):
                # cobre '#painel-direito' inteiro por CIMA do conteúdo
                # normal (repouso OU o card 'Curva' aberto), sem
                # remover/trocar nada por baixo. Precisa de
                # 'position: relative' em '.painel-direito' (ver
                # edit_menu.css) pra este 'position:absolute; inset:0;'
                # ancorar no painel certo, não em algum ancestral mais
                # distante.
                html.Div(id='area-modo-nova-analise-edicao', className='area-modo-nova-analise-edicao', style={'display': 'none'}),
            ]),
        ]),

        # --- Rodapé: 3 seções cujas larguras acompanham a do painel acima
        # delas (sidebar / centro / painel-direito) — ver 'habilitarDivisor'
        # em scripts_js.py. A vinculação é só de tamanho (puramente visual),
        # não de conteúdo.
        html.Div(className='rodape', children=[

            # --- Seção vinculada ao file menu (sidebar) ---
            html.Div(id='rodape-secao-arquivo', className='rodape-secao rodape-secao-arquivo', children=[
                html.Span(id='rodape-info-arquivo', className='rodape-info',
                          children=renderizar_info_rodape(estado, None)),

                # Sem separador de texto ' | ' aqui: o alerta agora é
                # empurrado pra ponta direita da seção via
                # 'justify-content: space-between' (ver .rodape-secao-
                # -arquivo em status_menu.css) e a própria borda direita
                # da seção já faz o papel visual do '|' no fim da linha.
                html.Div(id='rodape-alerta-wrapper', className='rodape-alerta-wrapper', children=[
                    html.Div(id='rodape-alerta-popup', className='rodape-alerta-popup',
                             children=renderizar_popup_alerta(estado, None)),
                    html.Button(id='rodape-alerta-badge', className='rodape-alerta-badge',
                                children=renderizar_badge_alerta(estado, None), n_clicks=0),
                ]),
            ]),

            # --- Seção vinculada ao menu central (mensagem do mago) ---
            html.Div(id='rodape-secao-central', className='rodape-secao rodape-secao-central', children=[
                # Camada de fundo do preenchimento de carregamento: ocupa a
                # seção inteira (não só o texto da mensagem), assim mesmo uma
                # mensagem curta como "oi" preenche visualmente a barra toda.
                # A largura é controlada via JS em iniciarBarraCarregamentoRodape().
                html.Div(id='rodape-progresso-central', className='rodape-progresso-central'),

                html.Div(className='rodape-central-conteudo', children=[
                    html.Span(id='rodape-status', children='🧙‍♂️: " Carregue um arquivo para começar... "'),
                ]),

                # --- Máquina da mensagem temporária do mago ---
                # 'rodape-mensagem-seguinte' guarda o que deve aparecer QUANDO a
                # mensagem atual expirar (string vazia = simplesmente some).
                # 'rodape-timer-mensagem' já nasce ativo (disabled=False) pra
                # fazer a mensagem inicial acima desaparecer sozinha nos
                # primeiros segundos, sem precisar de nenhuma ação do usuário.
                dcc.Store(id='rodape-mensagem-seguinte', data=''),
                dcc.Interval(
                    id='rodape-timer-mensagem',
                    interval=DURACAO_MENSAGEM_TEMPORARIA_MS,
                    n_intervals=0,
                    max_intervals=1,
                    disabled=False,
                ),
            ]),

            # --- Seção vinculada ao edit menu (painel-direito) ---
            # Vazio por enquanto — reservada pra quando as edições forem
            # implementadas; hoje só acompanha a largura do painel acima.
            html.Div(id='rodape-secao-edit', className='rodape-secao rodape-secao-edit'),
        ]),
    ])