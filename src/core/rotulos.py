import re
import unicodedata

# GerenciadorRotulos foi removido daqui: sua responsabilidade (rótulo +
# histórico de rename por coluna) agora é da classe Canal, dentro de
# src/core/arquivo.py — porque o rótulo de uma coluna e seu ciclo de
# vida (original/calculado, visível/oculto/excluído) são parte da MESMA
# entidade, não duas estruturas soltas que precisavam ser sincronizadas
# manualmente.


def sanitizar_rotulo_para_nome_coluna(rotulo):
    texto = unicodedata.normalize('NFKD', str(rotulo))
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^0-9a-zA-Z_]+', '_', texto).strip('_')
    return texto or 'coluna'


# --- Texto livre com LaTeX/MathText (título do gráfico, título dos
# eixos, nome de colunas na legenda) ------------------------------
#
# Não é uma classe 'TextManager' à parte (o app inteiro é function-
# based, não OO — ver plotter.py/calculadora.py) — 'sanitizar_rotulo_
# para_nome_coluna' acima já cobre o papel de 'sanitize()' (produz um
# nome_interno seguro pro DataFrame a partir do que o usuário digitou,
# incluindo sintaxe LaTeX — '\','{','}' já viram '_' hoje, mesmo sem
# 'saber' que é LaTeX). 'is_math'/'renderizar_texto_grafico' abaixo
# são os dois que faltavam: detectar se um texto é LaTeX, e preparar
# ele pro Plotly renderizar de verdade.
#
# ESCOPO ATUAL (decisão explícita): só dentro do GRÁFICO (título,
# título dos eixos, nome das curvas na legenda — ver dcc.Graph(
# mathjax=True) em renderizadores.py e o uso de renderizar_texto_
# grafico em plotter.py). A lista 'Dados do arquivo:', os botões da
# calculadora, o dropdown 'Dado:' no painel de edição — são HTML puro,
# sem MathJax nenhum ligado ali; o rótulo aparece cru nesses lugares
# (ex: 'P_{12}' literal, sem virar subscrito) — fora de escopo por
# enquanto, pode ser um próximo passo separado.
#
# LIMITAÇÃO DO PRÓPRIO PLOTLY (não é algo que dá pra contornar em
# Python): quando o MathJax encontra '$...$' num campo de texto, TUDO
# que estiver FORA dos delimitadores é ignorado — não dá pra misturar
# texto normal e LaTeX no MESMO campo (ex: 'ΔP (kPa)' com só o 'ΔP'
# em LaTeX perderia o '(kPa)' na hora de desenhar). Por isso
# 'renderizar_texto_grafico' embrulha o texto INTEIRO ou não embrulha
# nada — nunca uma mistura.

_PADRAO_LATEX = re.compile(r'\\[a-zA-Z]+|[_^]\{')


def is_math(texto):
    """
    Heurística: este texto parece conter sintaxe LaTeX/MathText?

    Dispara em duas situações, escolhidas de propósito pra NÃO
    confundir nomes de coluna comuns (ex: 'Tempo_decorrido_s',
    'pressure_12', que têm underscore mas não são LaTeX nenhum) com
    matemática de verdade:
      1. Um comando LaTeX (barra invertida + letras: '\\delta',
         '\\Delta', '\\frac', '\\infty'...) — barra invertida
         praticamente nunca aparece em texto/nome de coluna comum,
         então é um sinal forte e seguro.
      2. Sub/sobrescrito com CHAVES explícitas ('_{' ou '^{', ex:
         'P_{12}') — deliberadamente NÃO dispara em '_' ou '^' soltos
         seguidos de letra/número sem chave (isso pegaria QUALQUER
         nome de coluna com underscore, o que seria um falso positivo
         em massa). Um '_x' sem chave só vira matemática aqui se vier
         acompanhado de um comando (regra 1), como em 'T_\\infty'.

    Também reconhece um texto que o próprio usuário já embrulhou em
    '$...$' manualmente — nesse caso é matemática por definição, sem
    precisar bater nenhum dos padrões acima.
    """
    if not texto:
        return False
    texto = str(texto)
    if texto.startswith('$') and texto.endswith('$') and len(texto) > 1:
        return True
    return bool(_PADRAO_LATEX.search(texto))


def renderizar_texto_grafico(texto):
    """
    Prepara um texto (título do gráfico, título de eixo, rótulo de
    coluna) pro Plotly renderizar como LaTeX quando fizer sentido —
    RENDERER da arquitetura TextManager -> TextParser -> Renderer.

    Diferente da v1 (que classificava o texto INTEIRO como "é tudo
    matemática" ou "não é nada"): o Plotly troca de comportamento na
    hora que encontra QUALQUER '$...$' — tudo que estiver fora dos
    delimitadores é descartado (bug conhecido/documentado do próprio
    Plotly.js, não algo que dava pra contornar então). Um texto como
    'differential pressure, \\Delta P_{12}' virava TUDO matemática
    (a vírgula/espaço/palavras comuns iam pro modo matemático junto,
    resultado ilegível) — pedido explícito pra corrigir: fragmentar,
    não tratar como bloco único.

    Agora '_fragmentar_texto' (abaixo) quebra o texto em pedaços
    comuns e matemáticos, e cada pedaço COMUM vira um bloco '\\text
    {...}' DENTRO de uma única expressão matemática — differente de
    tentar vários pares de '$...$' soltos (que é exatamente o que o
    Plotly não suporta bem, ver docstring de _fragmentar_texto): como
    tudo fica dentro de UM SÓ par de '$...$', o Plotly nunca perde
    texto nenhum, e '\\text{}' é o comando padrão do LaTeX pra
    escrever texto comum (fonte reta, não itálico de variável) DENTRO
    do modo matemático — é assim que o resultado final ainda parece
    "texto normal, com uma fórmula no meio", que é o que o usuário via
    numa ferramenta LaTeX de verdade.

    Sem NENHUM pedaço reconhecido como matemática, devolve o texto
    ORIGINAL sem tocar em nada (nem embrulha em '$...$' à toa).
    """
    if not texto:
        return texto
    texto = str(texto)
    if texto.startswith('$') and texto.endswith('$') and len(texto) > 1:
        return texto

    partes = _fragmentar_texto(texto)
    if not any(tipo == 'math' for tipo, _ in partes):
        return texto

    pedacos_finais = []
    for tipo, pedaco in partes:
        if tipo == 'math':
            pedacos_finais.append(pedaco)
        else:
            # Escapa só '{'/'}' (os únicos caracteres que quebrariam o
            # balanceamento do '\text{...}' se aparecessem soltos num
            # trecho comum) — o resto do texto comum passa intacto.
            pedaco_seguro = pedaco.replace('{', r'\{').replace('}', r'\}')
            pedacos_finais.append('\\text{' + pedaco_seguro + '}')
    return '$' + ''.join(pedacos_finais) + '$'


_PADRAO_NUMERO = re.compile(r'^[0-9]+(?:[.,][0-9]+)?$')
_SIMBOLOS_MATEMATICOS = set('=+-*/<>≤≥±·×÷^')
_PONTUACAO_BORDA = '.,;:!?()[]{}'


def _classificar_palavra(palavra):
    """
    Classifica UMA palavra (token sem espaço) em 3 categorias:

      - 'seed': já bate 'is_math()' sozinha (tem comando LaTeX ou
        sub/sobrescrito com chave) — prova definitiva de que este
        pedaço do texto é matemática.
      - 'candidata': não é prova sozinha, mas é um tipo de palavra que
        SÓ faz sentido colada numa fórmula ao lado de uma 'seed' — um
        número puro ('1.8', '10'), um símbolo matemático solto ('=',
        '+', '×') ou uma única letra solta ('P', 'L', 'x' — variável
        de uma letra só, sem nome de verdade). Uma 'candidata' NUNCA
        vira matemática sozinha (ver _fragmentar_texto) — só quando
        está GRUDADA numa 'seed' na mesma sequência de palavras.
      - 'plain': qualquer outra palavra (texto normal, com 2+ letras
        e sem sintaxe LaTeX nenhuma).

    Pontuação nas BORDAS da palavra ('pressure,', '(kPa)') é ignorada
    pra esta classificação (usa 'nucleo', sem tocar na palavra
    original) — só importa o miolo alfanumérico.
    """
    if is_math(palavra):
        return 'seed'
    nucleo = palavra.strip(_PONTUACAO_BORDA)
    if not nucleo:
        return 'plain'
    if _PADRAO_NUMERO.match(nucleo):
        return 'candidata'
    if len(nucleo) == 1 and (nucleo.isalpha() or nucleo in _SIMBOLOS_MATEMATICOS):
        return 'candidata'
    return 'plain'


def _tokenizar_respeitando_chaves(texto):
    """
    Quebra 'texto' em tokens no espaço em branco — MAS ignora espaços
    que estejam DENTRO de chaves '{...}' (contando profundidade, então
    chaves aninhadas tipo '\\frac{\\Delta P}{L}' também funcionam).
    Sem isso, um comando como '\\frac{\\Delta P}{L}' (um dos exemplos
    originais do usuário, com espaço DENTRO da chave) quebraria ao
    meio num split ingênuo por espaço — '\\frac{\\Delta' de um lado,
    'P}{L}' do outro, os dois pedaços agora sem sentido LaTeX nenhum
    sozinhos.

    Espaços fora de qualquer chave continuam virando tokens próprios
    (preservados pra reconstrução exata do texto original).
    """
    tokens = []
    atual = []
    profundidade = 0
    for caractere in texto:
        if caractere == '{':
            profundidade += 1
            atual.append(caractere)
        elif caractere == '}':
            profundidade = max(0, profundidade - 1)
            atual.append(caractere)
        elif caractere.isspace() and profundidade == 0:
            if atual:
                tokens.append(''.join(atual))
                atual = []
            tokens.append(caractere)
        else:
            atual.append(caractere)
    if atual:
        tokens.append(''.join(atual))
    return tokens


def _fragmentar_texto(texto):
    """
    TextParser da arquitetura TextManager -> TextParser -> Renderer:
    quebra 'texto' numa lista de (tipo, pedaço) — tipo 'math' ou
    'plain' — SEM decidir isso pro texto inteiro de uma vez.

    Analisa PALAVRA POR PALAVRA (ver _classificar_palavra acima), não
    o texto inteiro de uma vez — pedido explícito: "o espaço [também]
    é um indicativo pra separar o texto". Ex: 'pressão = 1.8 \\times
    10^{4}' — só '\\times' e '10^{4}' batem 'is_math()' sozinhos; sem
    olhar palavra por palavra, o texto inteiro (por ter ALGUMA sintaxe
    LaTeX em algum canto) virava tudo matemática, engolindo 'pressão'
    também.

    Mas separar TODA palavra isolada quebraria fórmulas de várias
    palavras — '\\Delta P' (outro exemplo original) tem duas palavras,
    e 'P' sozinha (sem comando nem chave) não bate 'is_math()' — por
    isso a classificação usa 3 categorias, não 2 (ver
    _classificar_palavra): uma palavra 'candidata' (número solto,
    símbolo solto, letra única solta) só vira matemática de verdade
    quando está GRUDADA (mesma sequência de palavras não-comuns, sem
    nenhuma palavra comum no meio) a pelo menos uma 'seed' — é assim
    que 'P' ao lado de '\\Delta' vira matemática, mas um número solto
    no meio de uma frase comum ('capítulo 12 revisão') continua sendo
    só texto.

    Pedaços ADJACENTES do MESMO tipo final são unidos num só
    (preservando o espaço original entre eles).
    """
    tokens = _tokenizar_respeitando_chaves(texto)
    grupos = []
    buffer = []
    buffer_tipo = None       # 'plain' ou 'nao_plain' (grupo ainda sendo montado)
    buffer_tem_seed = False

    def _fechar_grupo():
        nonlocal buffer, buffer_tipo, buffer_tem_seed
        if not buffer:
            return
        texto_grupo = ''.join(buffer)
        # Um grupo 'nao_plain' SEM nenhuma seed (só candidatas soltas,
        # sem comando/chave nenhum por perto) rebaixa pra 'plain' —
        # ver docstring acima ("capítulo 12 revisão").
        tipo_final = 'math' if (buffer_tipo == 'nao_plain' and buffer_tem_seed) else 'plain'
        grupos.append((tipo_final, texto_grupo))
        buffer = []
        buffer_tem_seed = False

    for token in tokens:
        if token.isspace():
            if buffer:
                buffer.append(token)
            continue
        tipo_palavra = _classificar_palavra(token)
        tipo_grupo = 'plain' if tipo_palavra == 'plain' else 'nao_plain'
        if tipo_grupo != buffer_tipo:
            _fechar_grupo()
            buffer_tipo = tipo_grupo
        buffer.append(token)
        if tipo_palavra == 'seed':
            buffer_tem_seed = True
    _fechar_grupo()

    # Um grupo 'nao_plain' rebaixado pra 'plain' (sem seed) pode ficar
    # encostado num grupo 'plain' de verdade vizinho — funde os dois.
    mesclados = []
    for tipo, texto_pedaco in grupos:
        if mesclados and mesclados[-1][0] == tipo:
            mesclados[-1] = (tipo, mesclados[-1][1] + texto_pedaco)
        else:
            mesclados.append([tipo, texto_pedaco])
    return [tuple(item) for item in mesclados]