"""
Configurações da coleta de dados de RH do Portal da Transparência de Sorocaba.
"""
from datetime import date

# --- Portal: não precisa de chave/API — a coleta é automação de navegador ---
PORTAL_URL = "https://transparencia.sorocaba.sp.gov.br/tdaportalclient.aspx?418"

# --- Período de coleta: últimos 4 anos (ano corrente + 3 anteriores) ---
ANO_ATUAL = date.today().year
MES_ATUAL = date.today().month
ANOS = list(range(ANO_ATUAL - 3, ANO_ATUAL + 1))

MESES = [
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
]

# --- Saída ---
DIR_SAIDA = "dados"
ARQUIVO_ESTADO = f"{DIR_SAIDA}/estado_coleta.json"

ARQUIVOS_CSV = {
    "por_cargo": f"{DIR_SAIDA}/servidores_por_cargo.csv",
    "por_secretaria": f"{DIR_SAIDA}/servidores_por_secretaria.csv",
    "folha_pagamento": f"{DIR_SAIDA}/folha_pagamento.csv",
}