"""
Cliente de coleta via automação de navegador (Playwright) do Portal da
Transparência de Sorocaba.

O portal roda em GeneXus/ASP.NET (postbacks, awsgetcontentareas.aspx).
Estratégia: abrir a página de verdade, clicar na aba, aplicar Exercício/Mês
nos <select> (que disparam postback sozinhos) e acionar a exportação CSV
nativa do painel. Se um seletor mudar, o RuntimeError manda rodar o
diagnostico.py.
"""
import atexit
import logging
import re
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

import config

log = logging.getLogger(__name__)

TIMEOUT_MS = 90_000
DIR_DOWNLOADS = Path("downloads_temp")
TAMANHO_MINIMO_ARQUIVO = 2000  # bytes — abaixo disso, veio vazio/erro

# Textos exatos das abas (mapeados no DOM real)
ABA_POR_CARGO = "Número de Servidores por Cargo"
ABA_DETALHE = "Servidores - Detalhe"

_pw = _browser = _page = None


def _obter_page():
    """Browser lazy: abre uma vez e é reusado por todos os meses."""
    global _pw, _browser, _page
    if _page is None:
        log.info("Abrindo Chromium headless...")
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=True, args=["--no-sandbox"])
        _page = _browser.new_page()
        _page.set_default_timeout(TIMEOUT_MS)
        _page.goto(config.PORTAL_URL, wait_until="domcontentloaded", timeout=120_000)
        _page.wait_for_selector('select[id$="_exe"]', timeout=TIMEOUT_MS)
    return _page


def _fechar():
    global _pw, _browser, _page
    if _browser:
        _browser.close()
    if _pw:
        _pw.stop()
    _pw = _browser = _page = None


atexit.register(_fechar)


def _aguardar_grid(page):
    """Context manager: espera o postback que recarrega os painéis."""
    return page.expect_response(
        lambda r: "awsgetcontentareas" in r.url, timeout=TIMEOUT_MS
    )


def _aplicar_periodo(page, ano: int, mes: int):
    nome_mes = config.MESES[mes - 1][1].strip()
    with _aguardar_grid(page):
        page.locator('select[id$="_exe"]:visible').first.select_option(label=str(ano))
    if page.locator('select[id$="_mes"]:visible').count():
        try:
            with _aguardar_grid(page):
                page.locator('select[id$="_mes"]:visible').first.select_option(label=nome_mes)
        except Exception:
            log.warning("Label de mês falhou; usando índice %d", mes - 1)
            with _aguardar_grid(page):
                page.locator('select[id$="_mes"]:visible').first.select_option(index=mes - 1)


def _capturar_download(page, acionar, descricao: str) -> Path:
    """Dispara a ação; captura o download direto OU o fluxo em duas
    etapas (modal 'O arquivo foi gerado' → 'Clique aqui para baixar')."""
    DIR_DOWNLOADS.mkdir(exist_ok=True)
    try:
        with page.expect_download(timeout=TIMEOUT_MS) as info:
            acionar()
        download = info.value
    except Exception:
        link = page.get_by_text("Clique aqui para baixar o arquivo")
        link.wait_for(timeout=TIMEOUT_MS)
        with page.expect_download(timeout=TIMEOUT_MS) as info2:
            link.click()
        download = info2.value
    destino = DIR_DOWNLOADS / download.suggested_filename
    download.save_as(destino)
    tamanho = destino.stat().st_size
    if tamanho < TAMANHO_MINIMO_ARQUIVO:
        raise RuntimeError(f"Arquivo de '{descricao}' muito pequeno ({tamanho} bytes).")
    log.info("Download OK: %s (%d bytes)", destino.name, tamanho)
    return destino


def _gatilho_dropdown(page):
    page.locator('select[name="chartOptions"]:visible').first.select_option(label="CSV")


def _gatilho_modal(page):
    page.locator(
        'a[title*="Extração" i]:visible, button[title*="Extração" i]:visible, '
        'a[title*="Exportar" i]:visible, a[onclick*="Export"]:visible'
    ).first.click()
    page.get_by_text("CSV", exact=True).first.click()


def _gatilho_csv_direto(page):
    page.get_by_text("CSV", exact=True).first.click()


CANDIDATOS_GATILHO_EXPORT = [_gatilho_dropdown, _gatilho_modal, _gatilho_csv_direto]


def _exportar_painel(page, nome_aba: str, ano: int, mes: int, descricao: str) -> Path:
    with _aguardar_grid(page):
        page.locator("li", has_text=nome_aba).first.click()
    _aplicar_periodo(page, ano, mes)
    ultimo_erro = None
    for gatilho in CANDIDATOS_GATILHO_EXPORT:
        try:
            return _capturar_download(page, lambda g=gatilho: g(page), descricao)
        except Exception as e:
            ultimo_erro = e
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
    raise RuntimeError(
        f"Nenhum gatilho de exportação funcionou para '{descricao}'. "
        f"Rode `python diagnostico.py` e envie a saída. Último erro: {ultimo_erro}"
    )


def _ler_csv(caminho: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin1", "cp1252"):
        try:
            df = pd.read_csv(caminho, sep=None, engine="python", encoding=enc, dtype=str)
            if len(df.columns) > 1:
                df.columns = [str(c).strip().lower() for c in df.columns]
                return df
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Não consegui decodificar o CSV {caminho}.")


def _serie_num(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip().str.replace(r"[^\d,.-]", "", regex=True)
    t = t.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(t.replace("", "0"), errors="coerce").fillna(0.0)


# ------------------------------------------------------------------ #
# Interface usada pelo coletor.py                                     #
# ------------------------------------------------------------------ #

def buscar_por_cargo(ano: int, mes: int) -> list[dict]:
    arquivo = _exportar_painel(_obter_page(), ABA_POR_CARGO, ano, mes, "por_cargo")
    df = _ler_csv(arquivo)
    ren = {}
    for col in df.columns:
        if "cargo" in col:
            ren[col] = "cargo"
        elif "secretaria" in col or "orgao" in col or "órgão" in col:
            ren[col] = "secretaria"
        elif "quantidade" in col or "funcion" in col:
            ren[col] = "quantidade"
    df = df.rename(columns=ren)
    faltando = {"cargo", "secretaria", "quantidade"} - set(df.columns)
    if faltando:
        raise RuntimeError(
            f"Colunas não mapeadas no CSV de cargo: {faltando}. Reais: {list(df.columns)}."
        )
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0).astype(int)
    return df[["cargo", "secretaria", "quantidade"]].to_dict("records")


def buscar_por_secretaria(ano: int, mes: int) -> list[dict]:
    """Deriva o total por secretaria a partir do mesmo export de 'por cargo'."""
    registros = buscar_por_cargo(ano, mes)
    df = pd.DataFrame(registros)
    agrupado = df.groupby("secretaria", as_index=False)["quantidade"].sum()
    return agrupado.sort_values("quantidade", ascending=False).to_dict("records")


def buscar_folha_pagamento(ano: int, mes: int) -> list[dict]:
    arquivo = _exportar_painel(_obter_page(), ABA_DETALHE, ano, mes, "folha_pagamento")
    df = _ler_csv(arquivo)
    ren = {}
    for col in df.columns:
        if "tipo" in col and "folha" in col:
            ren[col] = "tipo_folha"
        elif "bruto" in col:
            ren[col] = "salario_bruto"
        elif "liquido" in col or "líquido" in col:
            ren[col] = "salario_liquido"
    df = df.rename(columns=ren)
    faltando = {"tipo_folha", "salario_bruto", "salario_liquido"} - set(df.columns)
    if faltando:
        raise RuntimeError(
            f"Colunas não mapeadas no CSV de folha: {faltando}. Reais: {list(df.columns)}."
        )
    df["salario_bruto"] = _serie_num(df["salario_bruto"])
    df["salario_liquido"] = _serie_num(df["salario_liquido"])
    # Se veio o detalhe por servidor em vez dos 4 totais, agrega por tipo:
    if any("matricula" in c or "matrícula" in c for c in df.columns):
        df = df.groupby("tipo_folha", as_index=False)[["salario_bruto", "salario_liquido"]].sum()
    return df[["tipo_folha", "salario_bruto", "salario_liquido"]].to_dict("records")


def buscar_detalhe_servidores(ano: int, mes: int) -> list[dict]:
    """Fase 2: detalhe individual por servidor (ver README)."""
    log.info("buscar_detalhe_servidores: fora de escopo por enquanto (ver README).")
    return []