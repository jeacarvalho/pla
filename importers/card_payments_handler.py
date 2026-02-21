"""
Handler para processamento de pagamentos de cartão do Organizze.

Responsabilidades:
- Identificar pagamentos de cartão (D com Categoria="Outros" + descrição com "pagamento/fatura")
- Gerar entradas Beancount para pagamentos de cartão
"""

import logging

import pandas as pd

from organizze_shared import (
    get_account_path,
    get_cartao_from_conta,
    sanitize_description,
)


logger = logging.getLogger(__name__)


def identify_card_payment_indices(df: pd.DataFrame) -> set[int]:
    """
    Identifica pagamentos de cartão.

    D com Categoria="Outros" ou "Pagamento de fatura" +
    descrição com "pagamento/fatura" + conta é Asset.
    """
    pagto_cartao_indices = set()
    for idx, row in df.iterrows():
        if row["D/R"] != "D":
            continue

        cat = row.get("Categoria", "")
        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )

        if pd.notna(cat):
            cat_lower = str(cat).lower()
            if cat_lower in ["outros", "pagamento de fatura"]:
                if any(
                    kw in desc for kw in ["pagamento", "fatura", "invoice", "payment"]
                ):
                    conta = row.get("CONTA", "")
                    from organizze_shared import ACCOUNTS_TYPE

                    if ACCOUNTS_TYPE.get(conta) == "Assets":
                        pagto_cartao_indices.add(idx)

    logger.info(f"Pagamentos de cartão identificados: {len(pagto_cartao_indices)}")
    return pagto_cartao_indices


def generate_card_payment_entries(
    df: pd.DataFrame,
    pagto_cartao_indices: set[int],
) -> tuple[list[str], int]:
    """Gera entradas Beancount para pagamentos de cartão."""
    lines = []
    count = 0

    for idx in sorted(pagto_cartao_indices):
        row = df.iloc[idx]
        lines.extend(_build_card_payment_entry(row))
        count += 1

    return lines, count


def _build_card_payment_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    cartao = get_cartao_from_conta(conta, row.get("Descrição", ""))

    if not cartao:
        return []

    debit = f"Liabilities:Cartao:{cartao}"
    credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "pagto_cartao"',
        "",
    ]
