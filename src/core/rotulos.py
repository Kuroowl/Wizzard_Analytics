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