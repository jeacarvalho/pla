"""
Handler para processamento de receitas do Organizze.

Responsabilidades:
- Identificar transferências recebidas
- Identificar ajustes de saldo
- Gerar entradas Beancount para receitas
"""

import logging

import pandas as pd

from organizze_shared import (
    get_account_path,
    sanitize_description,
    sanitize_name,
)


logger = logging.getLogger(__name__)


def identify_transferencia_recebida_indices(df: pd.DataFrame) -> set[int]:
    """Identifica transferências recebidas."""
    transferencia_recebida_indices = set()
    for idx, row in df.iterrows():
        if row["D/R"] != "R":
            continue

        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )
        if "transferência recebida" in desc:
            transferencia_recebida_indices.add(idx)

    logger.info(
        f"Transferências recebidas identificadas: {len(transferencia_recebida_indices)}"
    )
    return transferencia_recebida_indices


def identify_ajuste_indices(df: pd.DataFrame) -> set[int]:
    """Identifica ajustes de saldo."""
    ajuste_indices = set()
    for idx, row in df.iterrows():
        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )
        if "ajuste" in desc and "saldo" in desc:
            ajuste_indices.add(idx)

    logger.info(f"Ajustes de saldo identificados: {len(ajuste_indices)}")
    return ajuste_indices


def generate_transferencia_recebida_entries(
    df: pd.DataFrame,
    transferencia_recebida_indices: set[int],
) -> tuple[list[str], int]:
    """Gera entradas Beancount para transferências recebidas."""
    lines = []
    count = 0
    for idx in sorted(transferencia_recebida_indices):
        row = df.iloc[idx]
        lines.extend(_build_transferencia_recebida_entry(row))
        count += 1
    return lines, count


def generate_ajuste_entries(
    df: pd.DataFrame,
    ajuste_indices: set[int],
) -> tuple[list[str], int]:
    """Gera entradas Beancount para ajustes de saldo."""
    lines = []
    count = 0
    for idx in sorted(ajuste_indices):
        row = df.iloc[idx]
        lines.extend(_build_ajuste_entry(row))
        count += 1
    return lines, count


def generate_income_entries(
    df: pd.DataFrame,
    excluded_indices: set[int],
) -> tuple[list[str], int]:
    """
    Gera entradas Beancount para receitas regulares.

    Receita: R sem D pareado → Asset+ / Income-
    """
    lines = []
    count = 0

    for idx, row in df.iterrows():
        if idx in excluded_indices:
            continue

        if row["D/R"] != "R":
            continue

        date = row["Data"].strftime("%Y-%m-%d")
        desc = sanitize_description(row.get("Descrição", ""))
        value = abs(row["Valor"])
        conta = row.get("CONTA", "")
        categoria = sanitize_name(row.get("Categoria", "SemCategoria"))
        status = row.get("Situação", "Pago")
        flag = "*" if status == "Pago" else "!"

        debit = get_account_path(conta)
        credit = f"Income:{categoria}"

        lines.append(f'{date} {flag} "{desc}"')
        lines.append(f"  {debit:40s} {value:>10.2f} BRL")
        lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
        lines.append('  origem_id: "receita"')
        lines.append("")
        count += 1

    return lines, count


def _build_transferencia_recebida_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    debit = get_account_path(conta)
    credit = "Income:TransferenciasRecebidas"

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "transferencia_recebida"',
        "",
    ]


def _build_ajuste_entry(row: pd.Series) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    dr = row["D/R"]
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    if dr == "D":
        debit = get_account_path(conta)
        credit = "Equity:Ajustes"
    else:
        debit = "Equity:Ajustes"
        credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "ajuste_saldo"',
        "",
    ]
