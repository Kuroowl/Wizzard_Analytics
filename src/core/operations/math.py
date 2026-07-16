import pandas as pd

def multiplicar_por_constante(df, coluna, constante):
    """
    Multiplica uma coluna específica dos dados por um valor constante.
    Útil para aplicar ganhos, calibrações ou inverter sinais.
    """
    if df.empty or coluna not in df.columns:
        return df.copy()
 
    df_temp = df.copy()
    df_temp[coluna] = pd.to_numeric(df_temp[coluna], errors='coerce')
    df_temp[coluna] = df_temp[coluna] * constante
    return df_temp.reset_index(drop=True)

def dividir_por_constante(df, coluna, constante):
    """
    Divide uma coluna específica dos dados por um valor constante.
    Garante que não ocorra divisão por zero.
    """
    if constante == 0:
        raise ValueError("Impossível dividir por zero.")
        
    # Reutiliza a lógica de multiplicação com o inverso da constante
    return multiplicar_por_constante(df, coluna, 1 / constante)
           
def somar_constante(df, coluna, constante):
    """
    Soma um valor constante a uma coluna específica.
    Excelente para aplicar offsets, zerar sensores ou fazer "tara".
    """
    if df.empty or coluna not in df.columns:
        return df.copy()
 
    df_temp = df.copy()
    df_temp[coluna] = pd.to_numeric(df_temp[coluna], errors='coerce')
    df_temp[coluna] = df_temp[coluna] + constante
    return df_temp.reset_index(drop=True)


if __name__ == '__main__':
    # Teste rápido e simples das operações matemáticas remanescentes
    df_teste = pd.DataFrame({
        'Tempo_decorrido_s': [0.0, 1.0, 2.0, 3.0],
        'P1': [1.0, 1.2, 1.5, 2.0],
    })
 
    print("--- DataFrame de Teste Original ---")
    print(df_teste)
    
    print("\n--- Testando Multiplicar por Constante (P1 * 10) ---")
    print(multiplicar_por_constante(df_teste, 'P1', 10.0))
    
    print("\n--- Testando Somar Constante / Offset (P1 + 0.5) ---")
    print(somar_constante(df_teste, 'P1', 0.5))
