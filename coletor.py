"""
Coletor mensal de dados de RH do Portal da Transparência de Sorocaba.
Incremental por (ano, mês, categoria): cada execução verifica o que ainda
não foi coletado com sucesso e busca só isso. Serve tanto pro backfill
inicial (últimos 4 anos) quanto pra rotina mensal — mesmo script, rodado
no GitHub Actions ou manualmente.
"""
import csv
import json
import logging
import os
import time

import api_client
import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

CATEGORIAS = [
    ("por_cargo", api_client.buscar_por_cargo),
    ("por_secretaria", api_client.buscar_por_secretaria),
    ("folha_pagamento", api_client.buscar_folha_pagamento),
]


def carregar_estado() -> dict:
    if os.path.exists(config.ARQUIVO_ESTADO):
        with open(config.ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_estado(estado: dict) -> None:
    os.makedirs(config.DIR_SAIDA, exist_ok=True)
    with open(config.ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def gravar_csv(caminho: str, linhas: list[dict]) -> None:
    if not linhas:
        return
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    novo = not os.path.exists(caminho)
    with open(caminho, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        if novo:
            writer.writeheader()
        writer.writerows(linhas)


def periodo_a_coletar():
    """(ano, mes) dos últimos 4 anos, sem incluir meses futuros."""
    for ano in config.ANOS:
        for mes, _nome in config.MESES:
            if ano == config.ANO_ATUAL and mes > config.MES_ATUAL:
                continue
            yield ano, mes


def falta_algo(ano: int, mes: int, estado: dict) -> bool:
    return any(
        estado.get(f"{ano}-{mes:02d}:{categoria}") != "ok"
        for categoria, _ in CATEGORIAS
    )


def coletar_mes(ano: int, mes: int, estado: dict) -> None:
    for categoria, funcao in CATEGORIAS:
        chave = f"{ano}-{mes:02d}:{categoria}"
        if estado.get(chave) == "ok":
            continue
        log.info(f"Coletando {categoria} — {mes:02d}/{ano}...")
        try:
            linhas = funcao(ano, mes)
            for linha in linhas:
                linha.update(ano=ano, mes=mes)
            gravar_csv(config.ARQUIVOS_CSV[categoria], linhas)
            estado[chave] = "ok"
        except Exception as e:
            log.error(f"Falha em {categoria} {ano}-{mes:02d}: {e}")
            estado[chave] = "erro"
        salvar_estado(estado)


def main():
    estado = carregar_estado()
    pendentes = [(ano, mes) for ano, mes in periodo_a_coletar() if falta_algo(ano, mes, estado)]
    if not pendentes:
        log.info("Nada pendente — todos os meses já foram coletados.")
        return
    log.info(f"{len(pendentes)} mes(es) com alguma pendência.")
    for ano, mes in pendentes:
        coletar_mes(ano, mes, estado)
        time.sleep(1)  # não martelar o portal
    log.info("Coleta finalizada.")


if __name__ == "__main__":
    main()