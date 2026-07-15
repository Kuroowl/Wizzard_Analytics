import pandas as pd
import re

def detectar_delimitador_e_encoding(caminho_arquivo):
    """
    Tenta abrir o arquivo com diferentes codificações para detectar
    o encoding correto (UTF-8 ou CP1252) e o delimitador de colunas.
    """
    encodings_para_testar = ['utf-8', 'cp1252', 'latin-1']
    
    for encoding in encodings_para_testar:
        try:
            with open(caminho_arquivo, 'r', encoding=encoding) as f:
                primeira_linha = f.readline()
                
                # Se conseguiu ler sem dar erro de encoding, descobrimos o correto!
                if '\t' in primeira_linha:
                    return '\t', encoding
                elif ';' in primeira_linha:
                    return ';', encoding
                elif ',' in primeira_linha:
                    return ',', encoding
                else:
                    return ',', encoding  # Padrão
        except UnicodeDecodeError:
            continue  # Tenta o próximo encoding se este falhar
            
    # Se todos falharem, usa padrão seguro
    return ',', 'latin-1'


def carregar_dados(caminho_arquivo):
    """
    Lê arquivos TXT ou CSV, trata automaticamente o encoding e os cabeçalhos,
    remove linhas inválidas e retorna um DataFrame do Pandas limpo.
    """
    delimitador, encoding_detectado = detectar_delimitador_e_encoding(caminho_arquivo)
    
    try:
        df = pd.read_csv(
            caminho_arquivo, 
            sep=delimitador, 
            decimal=',', 
            encoding=encoding_detectado, 
            on_bad_lines='skip',
            engine='python'
        )
        
        # Limpa espaços em branco extras nos nomes das colunas
        df.columns = [col.strip() for col in df.columns]
        
        # Garante que as colunas críticas sejam numéricas
        for col in df.columns:
            if any(palavra in col.lower() for palabra in ['tempo', 'pressao', 'pressure', 'time', 'p_']):
                # Remove espaços das strings antes de converter
                df[col] = df[col].astype(str).str.replace(',', '.').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove linhas que ficaram com valores nulos nas colunas essenciais
        df = df.dropna().reset_index(drop=True)
        
        return df

    except Exception as e:
        raise ValueError(f"Falha ao processar o arquivo {caminho_arquivo} (Encoding: {encoding_detectado}): {str(e)}")


def extrair_metadados(caminho_arquivo):
    """
    Procura por informações extras no topo do arquivo (como data do ensaio, 
    operador, máquina) com suporte a múltiplos encodings.
    """
    metadados = {}
    _, encoding_detectado = detectar_delimitador_e_encoding(caminho_arquivo)
    
    try:
        with open(caminho_arquivo, 'r', encoding=encoding_detectado, errors='ignore') as f:
            for _ in range(20):  # Analisa apenas as primeiras 20 linhas
                linha = f.readline().strip()
                match = re.match(r'^([^:]+):(.+)$', linha) or re.match(r'^([^=]+)=(.+)$', linha)
                if match:
                    chave = match.group(1).strip()
                    valor = match.group(2).strip()
                    if not chave.replace('.', '', 1).isdigit() and len(chave) < 30:
                        metadados[chave] = valor
    except Exception as e:
        print(f"Erro ao extrair metadados: {e}")
    return metadados
