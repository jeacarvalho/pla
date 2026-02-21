"""
Handler para processamento de despesas do Organizze.

Responsabilidades:
- Identificar saques ATM
- Identificar pagamentos de boleto/título
- Identificar despesas em contas de cartão (Categoria="Outros")
- Gerar entradas Beancount para despesas
"""

import logging
from typing import Any

import pandas as pd

from organizze_shared import (
    get_account_path,
    sanitize_description,
    sanitize_name,
)


logger = logging.getLogger(__name__)


def identify_saque_indices(df: pd.DataFrame) -> set[int]:
    """Identifica saques em dinheiro pelo descrição."""
    saque_indices = set()
    for idx, row in df.iterrows():
        if row["D/R"] != "D":
            continue

        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )
        if "saque" in desc:
            saque_indices.add(idx)

    logger.info(f"Saques ATM identificados: {len(saque_indices)}")
    return saque_indices


def identify_boleto_indices(df: pd.DataFrame) -> set[int]:
    """Identifica pagamentos de boleto/título."""
    boleto_indices = set()
    for idx, row in df.iterrows():
        if row["D/R"] != "D":
            continue

        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )
        if "pagamento de título" in desc or "boleto" in desc:
            boleto_indices.add(idx)

    logger.info(f"Pagamentos de boleto identificados: {len(boleto_indices)}")
    return boleto_indices


def identify_cartao_expense_indices(df: pd.DataFrame) -> set[int]:
    """Identifica despesas em contas de cartão (Categoria='Outros')."""
    cartao_expense_indices = set()
    for idx, row in df.iterrows():
        if row["D/R"] != "D":
            continue

        conta = row.get("CONTA", "")
        cat = row.get("Categoria", "")

        from organizze_shared import ACCOUNTS_TYPE

        if ACCOUNTS_TYPE.get(conta) == "Liabilities" and str(cat).lower() == "outros":
            cartao_expense_indices.add(idx)

    logger.info(f"Despesas em cartão identificadas: {len(cartao_expense_indices)}")
    return cartao_expense_indices


def generate_saque_entries(
    df: pd.DataFrame, saque_indices: set[int]
) -> tuple[list[str], int]:
    """Gera entradas Beancount para saques ATM."""
    lines = []
    count = 0
    for idx in sorted(saque_indices):
        row = df.iloc[idx]
        lines.extend(_build_saque_entry(row))
        count += 1
    return lines, count


def generate_boleto_entries(
    df: pd.DataFrame, boleto_indices: set[int]
) -> tuple[list[str], int]:
    """Gera entradas Beancount para pagamentos de boleto."""
    lines = []
    count = 0
    for idx in sorted(boleto_indices):
        row = df.iloc[idx]
        lines.extend(_build_boleto_entry(row))
        count += 1
    return lines, count


def generate_cartao_expense_entries(
    df: pd.DataFrame, cartao_expense_indices: set[int]
) -> tuple[list[str], int]:
    """Gera entradas Beancount para despesas em cartão."""
    lines = []
    count = 0
    for idx in sorted(cartao_expense_indices):
        row = df.iloc[idx]
        lines.extend(_build_cartao_expense_entry(row))
        count += 1
    return lines, count


def generate_expense_entries(
    df: pd.DataFrame,
    excluded_indices: set[int],
) -> tuple[list[str], int]:
    """
    Gera entradas Beancount para despesas regulares.

    Despesa: D sem R pareado → Expense+ / Asset-
    """
    lines = []
    count = 0

    for idx, row in df.iterrows():
        if idx in excluded_indices:
            continue

        if row["D/R"] != "D":
            continue

        desc = sanitize_description(row.get("Descrição", ""))

        if "saldo inicial" in desc.lower():
            continue

        date = row["Data"].strftime("%Y-%m-%d")
        value = abs(row["Valor"])
        conta = row.get("CONTA", "")
        categoria = sanitize_name(row.get("Categoria", "SemCategoria"))
        status = row.get("Situação", "Pago")
        flag = "*" if status == "Pago" else "!"

        debit = f"Expenses:{categoria}"
        credit = get_account_path(conta)

        lines.append(f'{date} {flag} "{desc}"')
        lines.append(f"  {debit:40s} {value:>10.2f} BRL")
        lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
        lines.append('  origem_id: "despesa"')
        lines.append("")
        count += 1

    return lines, count


def _build_saque_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    debit = "Expenses:SaquesATM"
    credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "saque_atm"',
        "",
    ]


def _build_boleto_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    debit = "Expenses:Boletos"
    credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "pagto_boleto"',
        "",
    ]


def _build_cartao_expense_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    debit = "Expenses:OutrosCartao"
    credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "despesa_cartao"',
        "",
    ]
