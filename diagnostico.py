"""
Diagnóstico: abre o portal COM janela visível, imprime o mapa do DOM
(selects, gatilhos de exportação, abas e o link "Extração de Dados em
Formato Aberto") e loga toda requisição XHR enquanto você clica
manualmente nas exportações.

Uso: python diagnostico.py → opere o portal → copie a saída do terminal.
"""
import re
from playwright.sync_api import sync_playwright

import config

PADRAO_EXPORT = re.compile(r"extra|export|csv|xls|json|baixar|download", re.I)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()

        def log_req(req):
            if "awsgetcontentareas" in req.url or "gx-no-cache" in req.url \
               or req.resource_type in ("download",):
                print(f"[REQ {req.method}] {req.url}")

        page.on("request", log_req)
        page.goto(config.PORTAL_URL, wait_until="domcontentloaded")
        page.wait_for_selector('select[id$="_exe"]', timeout=90_000)

        print("\n=== SELECTS DE FILTRO ===")
        for s in page.locator("select").all():
            sid = s.get_attribute("id") or ""
            if sid.endswith(("_exe", "_mes", "_orh")) or s.get_attribute("name") == "chartOptions":
                print(f"id={sid!r} name={s.get_attribute('name')!r}")

        print("\n=== CANDIDATOS A GATILHO DE EXPORTAÇÃO ===")
        dados = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a,button,select,img').forEach(el => {
                const s = (el.title||'')+' '+((el.getAttribute('onclick'))||'')+' '
                        + (el.alt||'')+' '+(el.name||'')+' '+(el.textContent||'').slice(0,80);
                if (/extra|export|csv|xls|json|baixar|download/i.test(s)) {
                    out.push({tag: el.tagName, id: el.id||'', name: el.name||'',
                              title: el.title||'',
                              onclick: (el.getAttribute('onclick')||'').slice(0,160),
                              texto: (el.textContent||'').trim().replace(/\\s+/g,' ').slice(0,60)});
                }
            });
            return out;
        }""")
        for d in dados:
            print(d)

        print("\n=== ABAS (li) ===")
        for li in page.locator("li").all():
            try:
                t = (li.inner_text() or "").strip().replace("\n", " ")
                if t and len(t) < 60:
                    print("LI:", t)
            except Exception:
                pass

        input("\nAgora opere o portal (mude mês, clique nas exportações).\n"
              "As requisições [REQ ...] aparecem acima em tempo real.\n"
              "Pressione ENTER para fechar...")
        browser.close()


if __name__ == "__main__":
    main()