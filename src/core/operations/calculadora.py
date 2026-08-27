"""
Vocabulário fixo de tokens da calculadora do modo 'Nova Análise' (ver
renderizar_calculadora em src/gui/renderizadores.py e a barra de
cálculo dentro de '#area-modo-nova-analise').

Cada token é um par (display, codigo):
  - display: o texto mostrado no BOTÃO e ecoado na barra de expressão
    quando clicado.
  - codigo: o fragmento de Python de VERDADE, concatenado com os
    outros tokens clicados e avaliado só na hora de 'Criar' (ver
    avaliar_expressao_calculadora logo abaixo) — 'np.' aqui sempre se
    refere a numpy, injetado explicitamente no namespace restrito da
    avaliação, nunca ao módulo importado neste arquivo.

Os tokens de COLUNA (um botão por canal visível do arquivo ativo) não
vivem aqui — são gerados dinamicamente por arquivo em
renderizar_calculadora, já que dependem de qual arquivo/aba está
ativa. Só o vocabulário FIXO (operadores, funções, atalhos) mora
aqui.
"""

import numpy as np


NUMEROS = [
    # Grade estilo teclado numérico de calculadora de verdade (7-8-9 /
    # 4-5-6 / 1-2-3 / 0-.) — separado de OPERADORES (logo abaixo) de
    # propósito: os dois eram um grid só antes, misturando números e
    # símbolos sem distinção visual nenhuma. Ver '.calculadora-token-
    # numero' (fundo claro/neutro) em edit_menu.css.
    ('7', '7'), ('8', '8'), ('9', '9'),
    ('4', '4'), ('5', '5'), ('6', '6'),
    ('1', '1'), ('2', '2'), ('3', '3'),
    ('0', '0'), ('.', '.'),
]

OPERADORES = [
    # Símbolos/operadores — cor DIFERENTE de NUMEROS (ver
    # '.calculadora-token-operador', fundo âmbar, em edit_menu.css),
    # igual toda calculadora física separa visualmente a coluna de
    # operadores do teclado numérico.
    ('÷', '/'), ('×', '*'), ('−', '-'), ('+', '+'),
    ('(', '('), (')', ')'),
]

FUNCOES = [
    # Cada função abre parêntese sozinha — o usuário fecha com o ')' de
    # OPERADORES (mesmo espírito de digitar 'sin(' numa calculadora
    # científica de verdade: abre, digita/clica o argumento, fecha).
    ('sin(', 'np.sin('),
    ('cos(', 'np.cos('),
    ('tan(', 'np.tan('),
    ('√(', 'np.sqrt('),
    ('log₁₀(', 'np.log10('),
    ('ln(', 'np.log('),
    ('exp(', 'np.exp('),
    ('abs(', 'np.abs('),
]

OPERACOES_RAPIDAS = [
    # Diferente de OPERADORES_BASICOS/FUNCOES (que são só texto anexado
    # à expressão), estas são AÇÕES DE VERDADE — cada uma chama uma
    # função pronta de src/core/operations/math.py sobre as colunas que
    # já estão na expressão, em vez de virar mais um pedaço de código
    # pra avaliar (não fazia sentido escrever 'derivada(' numa
    # expressão livre, já que derivada/integral precisam saber qual é
    # o eixo X do arquivo, não só a coluna Y). Ver
    # aplicar_operacao_rapida logo abaixo e
    # 'calc-op-rapida'/'calc-resultado-pendente-store' em
    # callbacks.py/layout.py.
    ('Derivada', 'derivada'),
    ('Integral', 'integral'),
    ('Média', 'media'),
    ('Máximo', 'maximo'),
    ('Mínimo', 'minimo'),
]


def avaliar_expressao_calculadora(codigo, arquivo):
    """
    Avalia 'codigo' (a concatenação dos 'codigo' de cada token
    clicado, ver 'calc-expressao-store' em layout.py) contra as
    colunas de 'arquivo.df_editado' e devolve uma pd.Series pronta
    pra virar uma coluna nova.

    SEGURANÇA: 'codigo' só pode conter fragmentos que ESTE módulo
    definiu (OPERADORES_BASICOS/FUNCOES/OPERACOES_RAPIDAS) mais
    'col["<nome_interno>"]' pros tokens de coluna (gerados em
    renderizar_calculadora com nome_interno passado por 'repr()`, não
    concatenação de string crua — ver lá) — nunca texto livre digitado
    pelo usuário. Mesmo assim, o eval roda com '__builtins__' vazio
    (bloqueia 'import', 'open', 'exec' etc.) e só 'col'/'np' no
    namespace, então mesmo um bug de token não vira uma porta pra
    executar código arbitrário.

    Levanta ValueError com uma mensagem amigável (pra virar mensagem
    do mago) se a expressão estiver vazia, malformada, ou não
    referenciar coluna nenhuma dando um resultado que não é uma
    Series/array do mesmo tamanho do df.
    """
    codigo = (codigo or '').strip()
    if not codigo:
        raise ValueError('a expressão está vazia.')

    col = {nome: arquivo.df_editado[nome] for nome in arquivo.df_editado.columns}
    namespace_seguro = {'col': col, 'np': np}

    try:
        resultado = eval(codigo, {'__builtins__': {}}, namespace_seguro)  # noqa: S307 — namespace restrito, ver docstring
    except ZeroDivisionError:
        raise ValueError('divisão por zero na expressão.')
    except Exception as e:
        raise ValueError(f'expressão inválida ({e}).')

    n_linhas = len(arquivo.df_editado)
    if np.isscalar(resultado) or isinstance(resultado, (int, float, np.number)):
        # Expressão sem coluna nenhuma (ex: '2+2') — permite, mas
        # espalha o mesmo valor em todas as linhas, pra virar uma
        # coluna de verdade (constante) em vez de recusar.
        import pandas as pd
        resultado = pd.Series([resultado] * n_linhas, index=arquivo.df_editado.index)
    elif len(resultado) != n_linhas:
        raise ValueError('o resultado não tem o mesmo número de linhas do arquivo.')

    return resultado


def nomes_colunas_da_expressao(tokens_expressao):
    """
    Extrai só os NOMES INTERNOS das colunas referenciadas na expressão
    atual — ignora operadores/funções/números, olhando só os tokens
    cujo 'codigo' bate com o formato 'col[<repr>]' que os botões de
    coluna geram (ver renderizar_calculadora_barra, renderizadores.py).
    Usado por 'aplicar_operacao_rapida' (Derivada/Integral/Média/
    Máximo/Mínimo, logo abaixo), que operam sobre COLUNAS inteiras,
    não sobre uma expressão livre — clicar 'Canal_A' e depois 'Média'
    não deveria exigir o usuário montar 'col[...]+col[...]' primeiro,
    só clicar as colunas que quer combinar, na ordem que quiser.

    Ordem PRESERVADA (não usa set) — importa pra Derivada/Integral,
    onde só a PRIMEIRA coluna clicada conta como Y.
    """
    import ast
    nomes = []
    for t in (tokens_expressao or []):
        codigo = t.get('codigo', '')
        if codigo.startswith('col[') and codigo.endswith(']'):
            try:
                nomes.append(ast.literal_eval(codigo[4:-1]))
            except (ValueError, SyntaxError):
                continue
    return nomes


def aplicar_operacao_rapida(operacao_id, arquivo, estado, tokens_expressao):
    """
    Ponto de entrada das 'Operações rápidas' (Derivada/Integral/Média/
    Máximo/Mínimo — ver OPERACOES_RAPIDAS acima). Diferente de
    'avaliar_expressao_calculadora', NÃO lê 'codigo' livre — olha só
    quais COLUNAS estão referenciadas na expressão atual (via
    'nomes_colunas_da_expressao') e chama a função de
    src/core/operations/math.py correspondente.

    Devolve (valores, sugestao_nome, descricao):
      - valores: lista de números, pronta pra virar a nova coluna.
      - sugestao_nome: pré-preenche o campo de nome da barra — o
        usuário ainda pode trocar antes de 'Criar'.
      - descricao: texto curto mostrado na barra no lugar da expressão
        (ex: 'Derivada(Pressão)'), já que o resultado de uma operação
        rápida não é mais uma expressão editável token a token.

    Levanta ValueError (mensagem amigável, vira mensagem do mago) se
    a quantidade de colunas selecionadas não bater com o que a
    operação espera.
    """
    from src.core.operations.math import derivada_coluna, integral_coluna, combinar_colunas
    from src.core.plotting.plotter import resolver_eixo_x

    colunas = nomes_colunas_da_expressao(tokens_expressao)
    df = arquivo.df_editado

    if operacao_id in ('derivada', 'integral'):
        if len(colunas) != 1:
            raise ValueError(f'clique em EXATAMENTE 1 coluna antes de "{operacao_id.capitalize()}" '
                              f'(cliquei {len(colunas)}).')
        coluna_y = colunas[0]
        coluna_x = resolver_eixo_x(estado, df)
        if coluna_x == coluna_y:
            raise ValueError('a coluna escolhida é o próprio eixo X do arquivo — escolha outra.')
        rotulo_y = arquivo.rotulo(coluna_y)
        if operacao_id == 'derivada':
            df_novo = derivada_coluna(df, coluna_y, coluna_x, nome_saida='__calc_temp__')
            descricao = f'Derivada({rotulo_y})'
            sugestao_nome = f'Derivada de {rotulo_y}'
        else:
            df_novo = integral_coluna(df, coluna_y, coluna_x, nome_saida='__calc_temp__', retorno='cumulativa')
            descricao = f'Integral({rotulo_y})'
            sugestao_nome = f'Integral de {rotulo_y}'
        valores = df_novo['__calc_temp__'].tolist()

    elif operacao_id in ('media', 'maximo', 'minimo'):
        if len(colunas) < 2:
            raise ValueError(f'clique em 2 OU MAIS colunas antes de "{operacao_id.capitalize()}" '
                              f'(cliquei {len(colunas)}).')
        rotulos = [arquivo.rotulo(c) for c in colunas]
        df_novo = combinar_colunas(df, colunas, '__calc_temp__', operacao=operacao_id)
        valores = df_novo['__calc_temp__'].tolist()
        nome_op = {'media': 'Média', 'maximo': 'Máximo', 'minimo': 'Mínimo'}[operacao_id]
        descricao = f'{nome_op}({", ".join(rotulos)})'
        sugestao_nome = f'{nome_op} de {", ".join(rotulos)}'

    else:
        raise ValueError(f'operação rápida desconhecida: {operacao_id}.')

    return valores, sugestao_nome, descricao
