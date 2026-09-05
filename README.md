# Coleta de RH — Portal da Transparência de Sorocaba

Coleta mensal (últimos 4 anos: 2023–2026) de: servidores por cargo,
servidores por secretaria (derivada) e folha de pagamento. Salva tudo em
CSV na pasta `dados/`.

## Status

✅ Pipeline completo: período, checkpoint incremental por categoria,
gravação em CSV, log, erro em uma categoria não refaz as outras.
✅ Automação: Playwright headless interage com o portal GeneXus
(aba → filtros Exercício/Mês → exportação CSV nativa do painel).
⏳ Fase 2: detalhe individual por servidor (`buscar_detalhe_servidores`
existe mas retorna vazio por enquanto).

## Como rodar

```bash
pip install -r requirements.txt
playwright install chromium
python coletor.py