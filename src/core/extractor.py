import re
import pandas as pd

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


def encontrar_cabecalho_e_delimitador(caminho_arquivo, encoding, max_linhas=80):
    """
    Localiza a linha de cabeçalho de forma robusta: em vez de checar se uma
    palavra-chave aparece em QUALQUER lugar da linha (o que gera falso
    positivo, ex: 'p1' dentro de 'T25_P1_PAD' no título do ensaio), quebra a
    linha em tokens e conta quantos tokens BATEM (inteiros ou por prefixo)
    com nomes de coluna conhecidos. Exige pelo menos 2 acertos para aceitar.
    """
    with open(caminho_arquivo, 'r', encoding=encoding, errors='ignore') as f:
        linhas = [f.readline() for _ in range(max_linhas)]

    melhor_idx, melhor_delim, melhor_score = None, ',', 0

    for i, linha in enumerate(linhas):
        if not linha.strip():
            continue
        tokens, delim = _tokenizar(linha)
        if len(tokens) < 3:
            continue
        tokens_lower = [t.lower() for t in tokens]
        score = sum(
            1 for t in tokens_lower
            if any(t == chave or t.startswith(chave) for chave in COLUNAS_CHAVE)
        )
        if score >= 2 and score > melhor_score:
            melhor_idx, melhor_delim, melhor_score = i, delim, score

    if melhor_idx is None:
        # não achamos nada parecido com cabeçalho: assume que os dados
        # começam do topo do arquivo
        return 0, ','

    return melhor_idx, melhor_delim


def _linha_e_separador_decorativo(linha):
    """Detecta linhas tipo '---  ---------- ----------  -------  -------' """
    tokens = re.split(r'\s+', linha.strip())
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
    linha_cabecalho, delimitador = encontrar_cabecalho_e_delimitador(
        caminho_arquivo, encoding_detectado
    )
    decimal_detectado = detectar_separador_decimal(
        caminho_arquivo, encoding_detectado, linha_cabecalho, delimitador
    )

    try:
        df = pd.read_csv(
            caminho_arquivo,
            sep=delimitador,
            decimal=decimal_detectado,
            encoding=encoding_detectado,
            skiprows=linha_cabecalho,
            on_bad_lines='skip',
            engine='python',
        )

        # Limpa espaços em branco extras nos nomes das colunas
        df.columns = [col.strip() for col in df.columns]

        # Remove linhas decorativas tipo "--- --- ---"
        df = df[~df.iloc[:, 0].astype(str).str.match(r'^-+$')].reset_index(drop=True)

        # Garante que colunas numéricas relevantes sejam realmente numéricas
        for col in df.columns:
            if any(p in col.lower() for p in ['tempo', 'pressao', 'pressure', 'time', 'p1', 'p2', 'p3', 'p4', 'p5', 'temp']):
                df[col] = df[col].astype(str).str.strip()
                if decimal_detectado == ',':
                    df[col] = df[col].str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(how='all').reset_index(drop=True)

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
    linha_cabecalho, _ = encontrar_cabecalho_e_delimitador(caminho_arquivo, encoding_detectado)

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
    caminho = sys.argv[1] if len(sys.argv) > 1 else 'teste.txt'
    print("=== METADADOS ===")
    for k, v in extrair_metadados(caminho).items():
        print(f"{k}: {v}")
    print("\n=== DADOS ===")
    df = carregar_dados(caminho)
    print(df.dtypes)
    print(df)
