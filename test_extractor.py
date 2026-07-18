import os
from src.core.extractor import carregar_dados, extrair_metadados

def testar_meu_extrator():
    # Substitua pelo caminho de um arquivo TXT ou CSV de teste que você tenha no seu computador
    caminho_do_teste = "fieldlogger_data.txt" 
    
    if not os.path.exists(caminho_do_teste):
        print(f"❌ Erro: Coloque um arquivo de teste real no mesmo diretório ou mude o caminho acima!")
        print(f"Tentando procurar por: {os.path.abspath(caminho_do_teste)}")
        return

    print("=" * 50)
    print("🧙‍♂️ INICIANDO TESTE DO WIZARD EXTRACTOR 🧙‍♂️")
    print("=" * 50)

    try:
        # 1. Testando os Metadados (cabeçalhos extras)
        print("\n[1/2] Extraindo Metadados do topo do arquivo...")
        metadados = extrair_metadados(caminho_do_teste)
        if metadados:
            for chave, valor in metadados.items():
                print(f"   🔹 {chave}: {valor}")
        else:
            print("   ⚠️ Nenhum metadados extra encontrado (arquivo limpo direto para os dados).")

        # 2. Testando o Carregamento dos Dados
        print("\n[2/2] Carregando e limpando a tabela de dados...")
        df = carregar_dados(caminho_do_teste)
        
        print("\n✅ SUCESSO! Dados carregados com sucesso.")
        print("-" * 50)
        print(f"📊 Total de linhas válidas importadas: {len(df)}")
        print(f"📋 Colunas identificadas: {list(df.columns)}")
        print("-" * 50)
        print("🔍 Primeiras 5 linhas importadas:")
        print(df.head())
        print("-" * 50)
        print("🔍 Tipos de dados de cada coluna (devem ser float64 ou int64 para plotar):")
        print(df.dtypes)
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ O TESTE FALHOU!")
        print(f"Erro encontrado: {e}")
        print("=" * 50)

if __name__ == "__main__":
    testar_meu_extrator()
