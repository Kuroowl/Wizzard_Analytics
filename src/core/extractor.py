import pandas as pd
import re

def detectar_delimitador(caminho_arquivo):
    """
    Analisa as primeiras linhas do arquivo para detectar se o separador
    é tabulação (\t), ponto e vírgula (;) ou vírgula (,).
    """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            primeira_linha = f.readline()
            if '\t' in primeira_linha:
                return '\t'
            elif ';' in primeira_linha:
                return ';'
            elif ',' in primeira_linha:
                return ','
    except Exception as e:
        print(f"Erro ao detectar delimitador: {e}")
    return ','  # Retorno padrão caso falhe


def carregar_dados(caminho_arquivo):
    """
    Lê arquivos TXT ou CSV, trata os cabeçalhos, remove linhas inválidas
    e retorna um DataFrame do Pandas limpo e pronto para uso.
    """
    delimitador = detectar_delimitador(caminho_arquivo)
    
    try:
        # Carrega o arquivo tratando vírgula como decimal (comum em arquivos PT-BR)
        df = pd.read_csv(
            caminho_arquivo, 
            sep=delimitador, 
            decimal=',', 
            encoding='utf-8', 
            on_bad_lines='skip',
            engine='python'
        )
        
        # Limpa espaços em branco extras nos nomes das colunas
        df.columns = [col.strip() for col in df.columns]
        
        # Garante que as colunas críticas sejam numéricas
        for col in df.columns:
            # Tenta converter colunas que parecem conter dados de tempo/pressão
            if any(palavra in col.lower() for palavra in ['tempo', 'pressao', 'pressure', 'time', 'p_']):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove linhas que ficaram com valores nulos nas colunas essenciais
        df = df.dropna().reset_index(drop=True)
        
        return df

    except Exception as e:
        raise ValueError(f"Falha ao processar o arquivo {caminho_arquivo}: {str(e)}")


def extrair_metadados(caminho_arquivo):
    """
    Procura por informações extras no topo do arquivo (como data do ensaio, 
    operador, máquina) que geralmente ficam antes do cabeçalho de dados.
    """
    metadados = {}
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in range(20):  # Analisa apenas as primeiras 20 linhas
                linha = f.readline().strip()
                # Procura padrões "Chave: Valor" ou "Chave = Valor"
                match = re.match(r'^([^:]+):(.+)$', linha) or re.match(r'^([^=]+)=(.+)$', linha)
                if match:
                    chave = match.group(1).strip()
                    valor = match.group(2).strip()
                    # Evita pegar colunas de dados como metadados
                    if not chave.replace('.', '', 1).isdigit() and len(chave) < 30:
                        metadados[chave] = valor
    except Exception as e:
        print(f"Erro ao extrair metadados: {e}")
    return metadados
