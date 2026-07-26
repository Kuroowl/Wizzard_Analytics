import re
import pandas as pd
import numpy as np

# Palavras que costumam aparecer nos nomes das colunas de dados
COLUNAS_CHAVE = [
    'n#', 'data', 'hora', 'tempo', 'time',
    'pressao', 'pressão', 'p1', 'p2', 'p3', 'p4', 'p5',
    'temp', 'fw', 'ch', 'PRS', 'Temp', 'Ter', 'CH-', 'x' , 
    'y', 'u' , 'v' , 'z', 'X', 'Y', 'Z'
]


def detectar_encoding(caminho_arquivo, n_linhas=40):
    """
    Tenta abrir o arquivo com diferentes codificações e retorna a primeira
    que conseguir ler sem erro de decodificação.
    """
    for encoding in ['utf-8', 'cp1252', 'latin-1']:
        try:
            with open(caminho_arquivo, 'r', encoding=encoding) as f:
                for _ in range(n_linhas):
                    if not f.readline():
                        break
            return encoding
        except UnicodeDecodeError:
            continue
    return 'latin-1'  # fallback seguro, latin-1 nunca falha


def _tokenizar(linha):
    """
    Quebra uma linha em tokens testando, em ordem, tab / ponto-e-vírgula / vírgula
    e só cai para 'espaços múltiplos' (formato de largura fixa) se nada mais servir.
    Retorna (tokens, delimitador_usado).
    """
    if '\t' in linha:
        return [t.strip() for t in linha.split('\t') if t.strip()], '\t'
    if linha.count(';') >= 2:
        return [t.strip() for t in linha.split(';') if t.strip()], ';'
    if linha.count(',') >= 2:
        return [t.strip() for t in linha.split(',') if t.strip()], ','
    # formato de largura fixa / colunas alinhadas por espaço (muito comum em
    # exportações de instrumentos tipo Novus, dataloggers, etc.)
    return [t.strip() for t in re.split(r'\s+', linha.strip()) if t.strip()], r'\s+'


def _linha_parece_numerica(tokens, limiar=0.7):
    """
    Diz se uma linha já tokenizada 'parece dado' (maioria dos tokens dá pra
    converter em número) em vez de 'parece cabeçalho' (nomes de coluna,
    texto). Aceita tanto decimal com ponto quanto com vírgula.
    """
    if not tokens:
        return False
    numericos = 0
    for t in tokens:
        try:
            float(t.replace(',', '.'))
            numericos += 1
        except ValueError:
            pass
    return (numericos / len(tokens)) >= limiar


def detectar_delimitador(caminho_arquivo, encoding, max_linhas=40):
    """
    Detecta o delimitador olhando para os DADOS do arquivo, não para o
    cabeçalho. Isso é importante porque um cabeçalho com rótulos fora do
    comum (ex: nomes de canal customizados de um programa antigo) não deve
    impedir a detecção do delimitador — o delimitador é uma propriedade do
    arquivo inteiro, não dos nomes das colunas.

    Testa cada candidato (tab / ';' / ',' / largura fixa) tokenizando as
    primeiras linhas não-vazias e não-decorativas, e escolhe o que produz
    a contagem de colunas mais consistente (mesma contagem se repetindo em
    mais linhas, com pelo menos 2 colunas).
    """
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        linhas = [f.readline() for _ in range(max_linhas)]
    linhas = [l for l in linhas if l.strip() and not _linha_e_separador_decorativo(l)]

    candidatos = ['\t', ';', ',', r'\s+']
    melhor_delim, melhor_pontuacao = ',', -1

    for delim in candidatos:
        contagens = [
            len(_tokenizar_com_delimitador(linha, delim)) for linha in linhas
        ]
        contagens = [c for c in contagens if c >= 2]
        if not contagens:
            continue
        n_colunas_moda = max(set(contagens), key=contagens.count)
        n_linhas_batendo = contagens.count(n_colunas_moda)
        # prioriza delimitador que (a) concorda em mais linhas e (b) rende
        # mais colunas (desempate: um separador que quebra tudo em 2
        # colunas "por acidente" perde pra um que quebra em 9 de forma
        # consistente)
        pontuacao = n_linhas_batendo * n_colunas_moda
        if pontuacao > melhor_pontuacao:
            melhor_delim, melhor_pontuacao = delim, pontuacao

    return melhor_delim


def encontrar_linha_cabecalho(caminho_arquivo, encoding, delimitador, max_linhas=80):
    """
    Localiza a linha de cabeçalho JÁ CONHECENDO o delimitador certo
    (detectado separadamente a partir dos dados, ver 'detectar_delimitador').

    Primeiro tenta achar por palavras-chave conhecidas em COLUNAS_CHAVE,
    exigindo pelo menos 2 tokens batendo (integralmente ou por prefixo) —
    evita falso positivo tipo 'p1' dentro de 'T25_P1_PAD' no título do
    ensaio, porque aqui comparamos tokens inteiros, não substrings soltas.

    Se nenhuma linha bater com as palavras-chave (comum quando o aparelho
    usa nomes de canal customizados, tipo 'Analise_9_fil_2_amost_erro'),
    cai num critério mais genérico: a primeira linha não-decorativa cujos
    tokens NÃO parecem numéricos — já que cabeçalho é texto e dados são
    número, essa é uma heurística que não depende de conhecer os nomes
    das colunas de antemão.
    """
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        linhas = [f.readline() for _ in range(max_linhas)]

    melhor_idx, melhor_score = None, 0
    idx_primeira_linha_textual = None

    for i, linha in enumerate(linhas):
        if not linha.strip() or _linha_e_separador_decorativo(linha):
            continue
        tokens = _tokenizar_com_delimitador(linha, delimitador)
        if len(tokens) < 3:
            continue

        tokens_lower = [t.lower() for t in tokens]
        score = sum(
            1 for t in tokens_lower
            if any(t == chave.lower() or t.startswith(chave.lower()) for chave in COLUNAS_CHAVE)
        )
        if score >= 2 and score > melhor_score:
            melhor_idx, melhor_score = i, score

        if idx_primeira_linha_textual is None and not _linha_parece_numerica(tokens):
            idx_primeira_linha_textual = i

    if melhor_idx is not None:
        return melhor_idx

    if idx_primeira_linha_textual is not None:
        # não achamos palavra-chave conhecida, mas achamos uma linha que
        # claramente não é numérica (nomes de coluna) antes dos dados
        return idx_primeira_linha_textual

    # não achamos nada parecido com cabeçalho nem linha textual: assume
    # que os dados começam do topo do arquivo
    return 0


def _linha_e_separador_decorativo(linha):
    """Detecta linhas tipo '---  ---------- ----------  -------  -------' """
    tokens = re.split(r'\s+', linha.strip())
    return _tokens_sao_decorativos(tokens)


def _tokens_sao_decorativos(tokens):
    """Mesma checagem de '_linha_e_separador_decorativo', mas recebendo
    tokens JÁ EXTRAÍDOS — evita tokenizar a mesma linha duas vezes (uma
    pra checar se é decorativa, outra pra pegar os campos de verdade),
    que é o principal gargalo em arquivos com dezenas de milhares de
    linhas."""
    return len(tokens) > 0 and all(re.fullmatch(r'-{2,}', t) for t in tokens)


def detectar_separador_decimal(caminho_arquivo, encoding, linha_cabecalho, delimitador):
    """
    Olha as primeiras linhas de dados reais (pulando a linha de cabeçalho e
    eventuais linhas decorativas de hífen) e verifica se os números usam
    vírgula ou ponto como separador decimal.
    """
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        for i, linha in enumerate(f):
            if i <= linha_cabecalho:
                continue
            if not linha.strip() or _linha_e_separador_decorativo(linha):
                continue
            if re.search(r'\d,\d', linha):
                return ','
            if re.search(r'\d\.\d', linha):
                return '.'
            break
    return '.'  # padrão internacional, mais comum em exportações desse tipo


def _tokenizar_com_delimitador(linha, delimitador):
    """Tokeniza uma linha com um delimitador JÁ CONHECIDO (não redetecta por
    linha) — importante porque linhas de dados com decimal em vírgula têm
    várias vírgulas, e se cada linha redetectasse seu próprio delimitador
    (como _tokenizar faz), a vírgula decimal seria confundida com separador
    de coluna.

    No modo largura fixa (\\s+) descarta tokens vazios, porque ali espaços
    múltiplos são só alinhamento visual entre colunas, sem significado de
    campo. Já com delimitador explícito (';', ',', tab) PRESERVA tokens
    vazios: uma posição entre dois delimitadores (ex: '1.2;;;4.5') é um
    campo vazio de verdade (canal não amostrado naquele instante), e
    descartá-lo desalinha todas as colunas seguintes e faz a linha parecer
    ter menos campos do que realmente tem."""
    if delimitador == r'\s+':
        return [t.strip() for t in re.split(r'\s+', linha.strip()) if t.strip()]
    return [t.strip() for t in linha.rstrip('\r\n').split(delimitador)]


def _ler_linha(caminho_arquivo, encoding, indice):
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        for i, linha in enumerate(f):
            if i == indice:
                return linha
    return ''


def _contar_colunas_dados(caminho_arquivo, encoding, linha_cabecalho, delimitador):
    """
    Conta quantas colunas a primeira linha de DADOS de verdade tem (pulando
    cabeçalho e linhas decorativas de hífen). Serve de 'verdade' sobre o
    número real de colunas, independente de o cabeçalho estar certo ou não.
    """
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        for i, linha in enumerate(f):
            if i <= linha_cabecalho:
                continue
            if not linha.strip() or _linha_e_separador_decorativo(linha):
                continue
            return len(_tokenizar_com_delimitador(linha, delimitador))
    return None


def _dividir_rotulos_colados(token):
    """
    Tenta dividir um token de cabeçalho que colou dois (ou mais) rótulos sem
    espaço entre eles — bug comum em aparelhos de largura fixa quando o nome
    de uma coluna ocupa exatamente o campo e "empurra" o próximo colado nele
    (ex: 'C6-Temp03C7-PRS06' -> ['C6-Temp03', 'C7-PRS06']).

    Assume a convenção comum de rótulo <letras><número>-<nome> (C1-, T2-,
    S3-...). Se o token não seguir esse padrão repetido, devolve ele mesmo
    sem alterar — é uma tentativa best-effort, não uma garantia.
    """
    partes = re.split(r'(?=[A-Za-z]+\d+-)', token)
    partes = [p for p in partes if p]
    return partes if partes else [token]


def _gerar_nomes_colunas(tokens_cabecalho, n_colunas_dados):
    """
    Gera a lista final de nomes de coluna, corrigindo o caso em que o
    cabeçalho tem menos rótulos do que colunas de dados de verdade:
      1) tenta dividir tokens colados (rótulo1+rótulo2 grudados);
      2) se ainda faltar rótulo depois disso, preenche o resto com nomes
         genéricos 'colunaN' — não trava o carregamento por causa de um
         rótulo que não deu pra recuperar;
      3) se sobrar rótulo (cabeçalho com mais tokens que os dados), avisa e
         descarta os excedentes do final.
    """
    rotulos = []
    for tok in tokens_cabecalho:
        rotulos.extend(_dividir_rotulos_colados(tok))

    if len(rotulos) == n_colunas_dados:
        return rotulos

    if len(rotulos) < n_colunas_dados:
        faltam = n_colunas_dados - len(rotulos)
        print(
            f"Aviso: o cabeçalho rendeu {len(rotulos)} rótulo(s) mas os dados têm "
            f"{n_colunas_dados} coluna(s) (provavelmente um rótulo colou com o "
            f"seguinte sem espaço, e não foi possível separar automaticamente). "
            f"Preenchendo {faltam} coluna(s) com nome genérico no final."
        )
        proximo_indice = len(rotulos) + 1
        for _ in range(faltam):
            rotulos.append(f'coluna{proximo_indice}')
            proximo_indice += 1
        return rotulos

    print(
        f"Aviso: o cabeçalho rendeu {len(rotulos)} rótulo(s) mas os dados têm apenas "
        f"{n_colunas_dados} coluna(s). Descartando os rótulos excedentes do final."
    )
    return rotulos[:n_colunas_dados]


def _linha_valida_de_dados(linha):
    """Uma linha 'conta' como dado se não for vazia nem decorativa (hífens)."""
    return bool(linha.strip()) and not _linha_e_separador_decorativo(linha)


def _tentar_converter_numerico(serie, decimal):
    """
    Tenta converter uma coluna pra numérico com base no CONTEÚDO dela, não
    no nome — mais robusto que uma lista de palavras-chave, porque rótulos
    de aparelho variam muito (ex: 'C1-PRS04', 'C8-MVZ01' não batem com
    nenhuma palavra-chave óbvia, mas os valores são claramente numéricos).

    Só converte se pelo menos 90% dos valores não-vazios da coluna virarem
    número válido; senão mantém a coluna como texto (evita destruir colunas
    como 'Data' ou 'Hora', que não são numéricas por natureza).
    """
    bruta = serie.astype(str).str.strip()
    preparada = bruta.str.replace(',', '.', regex=False) if decimal == ',' else bruta
    convertida = pd.to_numeric(preparada, errors='coerce')

    nao_vazios = (bruta != '') & (bruta.str.lower() != 'nan')
    if nao_vazios.sum() == 0:
        return serie

    taxa_sucesso = convertida[nao_vazios].notna().sum() / nao_vazios.sum()
    return convertida if taxa_sucesso >= 0.9 else serie


def _adicionar_tempo_decorrido(df):
    """
    Se o DataFrame tiver colunas de Data e/ou Hora (texto), combina as duas
    num datetime e cria 'Tempo_decorrido_s': segundos desde a primeira
    aquisição. Essa é a coluna que deve ser usada como eixo X quando o
    usuário quiser filtrar/plotar por tempo — as colunas Data/Hora originais
    continuam intactas, só para exibição.
    """
    col_data = next((c for c in df.columns if c.lower() == 'data'), None)
    col_hora = next((c for c in df.columns if c.lower() == 'hora'), None)

    if col_data is None and col_hora is None:
        return df

    if col_data is not None and col_hora is not None:
        texto_datetime = df[col_data].astype(str) + ' ' + df[col_hora].astype(str)
    else:
        texto_datetime = df[col_data if col_data is not None else col_hora].astype(str)

    datetimes = pd.to_datetime(texto_datetime, errors='coerce', dayfirst=True)

    if datetimes.isna().all():
        # não conseguiu interpretar como data/hora; não trava o carregamento,
        # só não cria a coluna de tempo decorrido
        return df

    inicio = datetimes.dropna().iloc[0]
    df['Tempo_decorrido_s'] = (datetimes - inicio).dt.total_seconds()
    return df


def carregar_dados(caminho_arquivo):
    """
    Lê arquivos TXT ou CSV, descobre dinamicamente onde começam os dados
    (pulando metadados decorativos), detecta encoding, delimitador e
    separador decimal, e retorna um DataFrame limpo.
    """
    encoding_detectado = detectar_encoding(caminho_arquivo)
    delimitador = detectar_delimitador(caminho_arquivo, encoding_detectado)
    linha_cabecalho = encontrar_linha_cabecalho(
        caminho_arquivo, encoding_detectado, delimitador
    )
    decimal_detectado = detectar_separador_decimal(
        caminho_arquivo, encoding_detectado, linha_cabecalho, delimitador
    )

    # Gera os nomes de coluna corrigindo eventuais rótulos colados sem
    # espaço no cabeçalho (ex: 'C6-Temp03C7-PRS06'), comparando com o número
    # real de colunas encontrado numa linha de dados.
    texto_cabecalho = _ler_linha(caminho_arquivo, encoding_detectado, linha_cabecalho)
    tokens_cabecalho = _tokenizar_com_delimitador(texto_cabecalho, delimitador)
    n_colunas_dados = _contar_colunas_dados(caminho_arquivo, encoding_detectado, linha_cabecalho, delimitador)
    nomes_colunas = (
        _gerar_nomes_colunas(tokens_cabecalho, n_colunas_dados)
        if n_colunas_dados is not None else tokens_cabecalho
    )

    try:
        n_colunas = len(nomes_colunas)
        linhas_validas = []
        linhas_ajustadas = 0

        with open(caminho_arquivo, 'r', encoding=encoding_detectado, errors='ignore') as f:
            for i, linha in enumerate(f):
                if i <= linha_cabecalho:
                    continue
                if not linha.strip():
                    continue

                # Tokeniza UMA vez só: antes, a linha era tokenizada aqui e
                # de novo dentro de '_linha_valida_de_dados' (pra checar se
                # era uma linha decorativa de hífens) — dobrando o custo de
                # regex por linha. Em arquivos de dezenas de milhares de
                # linhas isso é o principal motivo do carregamento
                # (e, por consequência, a interface inteira) travar.
                tokens = _tokenizar_com_delimitador(linha, delimitador)

                if _tokens_sao_decorativos(tokens):
                    continue

                if len(tokens) == n_colunas:
                    linhas_validas.append(tokens)
                elif len(tokens) > n_colunas:
                    # linha com campos a mais que o esperado: mantém só os
                    # primeiros n_colunas (não deveria acontecer com o
                    # cálculo de n_colunas_dados vindo de uma linha real,
                    # mas protege contra anomalias pontuais no arquivo)
                    linhas_validas.append(tokens[:n_colunas])
                    linhas_ajustadas += 1
                elif len(tokens) >= n_colunas - 2:
                    # faltam só 1-2 campos (comum na última linha de um
                    # arquivo cortado no meio da aquisição): completa com vazio
                    linhas_validas.append(tokens + [''] * (n_colunas - len(tokens)))
                    linhas_ajustadas += 1
                else:
                    linhas_ajustadas += 1  # linha claramente incompleta: descarta

        if linhas_ajustadas > 0:
            print(
                f"Aviso: {linhas_ajustadas} linha(s) com número de campos diferente "
                f"do esperado ({n_colunas}) foram ajustadas ou descartadas."
            )

        df = pd.DataFrame(linhas_validas, columns=nomes_colunas)
        df.columns = [col.strip() for col in df.columns]

        # Converte pra numérico com base no conteúdo de cada coluna (não no
        # nome), então funciona com qualquer convenção de rótulo do aparelho
        for col in df.columns:
            df[col] = _tentar_converter_numerico(df[col], decimal_detectado)

        df = df.replace('', np.nan).dropna(how='all').reset_index(drop=True)

        # Cria uma coluna numérica de tempo decorrido (em segundos), a partir
        # das colunas de Data/Hora, para servir de eixo X em operações de
        # filtro/gráfico. As colunas originais de Data/Hora continuam
        # disponíveis como texto, para exibição.
        df = _adicionar_tempo_decorrido(df)

        return df

    except Exception as e:
        raise ValueError(
            f"Falha ao processar o arquivo {caminho_arquivo} "
            f"(encoding={encoding_detectado}, delimitador={delimitador!r}, "
            f"decimal={decimal_detectado!r}): {str(e)}"
        )


def extrair_metadados(caminho_arquivo):
    """
    Procura por informações extras no topo do arquivo (data do ensaio,
    operador, máquina, etc.), parando antes da linha de cabeçalho de dados
    para não confundir nomes de coluna com metadados.
    """
    metadados = {}
    encoding_detectado = detectar_encoding(caminho_arquivo)
    delimitador = detectar_delimitador(caminho_arquivo, encoding_detectado)
    linha_cabecalho = encontrar_linha_cabecalho(caminho_arquivo, encoding_detectado, delimitador)

    try:
        with open(caminho_arquivo, 'r', encoding=encoding_detectado, errors='ignore') as f:
            for i, linha in enumerate(f):
                if i >= linha_cabecalho:
                    break
                linha = linha.strip()
                match = re.match(r'^([^:]+):(.+)$', linha) or re.match(r'^([^=]+)=(.+)$', linha)
                if match:
                    chave = match.group(1).strip()
                    valor = match.group(2).strip()
                    if not chave.replace('.', '', 1).isdigit() and len(chave) < 40:
                        metadados[chave] = valor
    except Exception as e:
        print(f"Erro ao extrair metadados: {e}")
    return metadados


if __name__ == '__main__':
    import sys
    caminho = sys.argv[1] if len(sys.argv) > 1 else 'fieldlogger_data.txt'
    print("=== METADADOS ===")
    for k, v in extrair_metadados(caminho).items():
        print(f"{k}: {v}")
    print("\n=== DADOS ===")
    df = carregar_dados(caminho)
    print(df.dtypes)
    print(df)