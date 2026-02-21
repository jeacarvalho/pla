"""
Handler para processamento de transferências do Organizze.

Responsabilidades:
- Identificar transferências (D + R pareados por valor, ±1 dia)
- Processar transferências órfãs
- Gerar entradas Beancount para transferências
"""

import logging
from datetime import timedelta
from typing import Any

import pandas as pd

from organizze_shared import (
    generate_pair_id,
    get_account_path,
    sanitize_description,
)


logger = logging.getLogger(__name__)


def identify_transfers(
    df: pd.DataFrame,
    excluded_indices: set[int],
) -> tuple[set[int], list[dict[str, Any]]]:
    """
    Identifica transferências pareadas (D + R com mesmo valor, ±1 dia).

    Returns:
        Tuple de (processed_indices, orphans)
    """
    transferencia_indices = []
    for idx, row in df.iterrows():
        if idx in excluded_indices:
            continue
        cat = (
            str(row.get("Categoria", "")).lower()
            if pd.notna(row.get("Categoria"))
            else ""
        )
        if cat == "outros":
            transferencia_indices.append(idx)

    logger.info(f"Entradas com Categoria='Outros': {len(transferencia_indices)}")

    pending_transfers: dict[tuple, dict] = {}
    processed_as_transfer: set[int] = set()

    for idx in transferencia_indices:
        if idx in processed_as_transfer:
            continue

        row = df.iloc[idx]
        valor = abs(row["Valor"])
        data = row["Data"]

        pair_found = False

        for look_ahead in range(-1, 2):
            search_date = data + timedelta(days=look_ahead)
            key = (search_date, valor)

            if key in pending_transfers:
                pending_row = pending_transfers[key]
                pending_idx = pending_row["idx"]

                if pending_row["conta"] != row["CONTA"]:
                    processed_as_transfer.add(idx)
                    processed_as_transfer.add(pending_idx)
                    pair_found = True
                    break

        if not pair_found:
            key = (data, valor)
            pending_transfers[key] = {
                "idx": idx,
                "conta": row["CONTA"],
                "valor": valor,
                "data": data,
                "dr": row["D/R"],
                "desc": row.get("Descrição", ""),
            }

    orphans = []
    for key, transfer in pending_transfers.items():
        idx = transfer["idx"]

        if "saldo inicial" in str(transfer["desc"]).lower():
            continue

        if idx in excluded_indices:
            continue

        if idx not in processed_as_transfer:
            orphans.append(transfer)
            logger.warning(
                f"Transferência órfã: {transfer['data']} | "
                f"{transfer['conta']} | {transfer['valor']}"
            )

    matched = len(processed_as_transfer) // 2
    logger.info(f"Transferências pareadas: {matched}")
    logger.info(f"Transferências órfãs: {len(orphans)}")

    return processed_as_transfer, orphans


def generate_transfer_entries(
    df: pd.DataFrame,
    processed_as_transfer: set[int],
) -> tuple[list[str], int]:
    """Gera entradas Beancount para transferências pareadas."""
    from collections import defaultdict

    transfer_groups: dict[tuple, list[int]] = defaultdict(list)
    for idx in processed_as_transfer:
        row = df.iloc[idx]
        key = (row["Data"], abs(row["Valor"]))
        transfer_groups[key].append(idx)

    lines = []
    count = 0

    for (date, valor), indices in sorted(transfer_groups.items()):
        if len(indices) != 2:
            continue

        row1 = df.iloc[indices[0]]
        row2 = df.iloc[indices[1]]

        if row1["D/R"] == "D":
            row_d, row_r = row1, row2
        else:
            row_d, row_r = row2, row1

        date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
        desc = sanitize_description(row_d.get("Descrição", ""))

        from_acc = get_account_path(row_d.get("CONTA"))
        to_acc = get_account_path(row_r.get("CONTA"))

        lines.append(f'{date_str} * "{desc}"')
        lines.append(f"  {from_acc:40s} {-valor:>10.2f} BRL")
        lines.append(f"  {to_acc:40s} {valor:>10.2f} BRL")
        pair_id = generate_pair_id(indices[0], indices[1])
        lines.append(f'  origem_id: "transfer_pair:{pair_id}"')
        lines.append("")
        count += 1

    return lines, count


def generate_orphan_transfer_entries(
    orphans: list[dict[str, Any]],
    df: pd.DataFrame,
) -> tuple[list[str], int]:
    """Gera entradas Beancount para transferências órfãs."""
    lines = []
    count = 0

    for orphan in orphans:
        idx = orphan["idx"]
        row = df.iloc[idx]

        date_str = row["Data"].strftime("%Y-%m-%d")
        desc = sanitize_description(row.get("Descrição", ""))

        conta = get_account_path(orphan["conta"])

        lines.append(f'{date_str} * "{desc} (ORPHAN)"')
        lines.append(f"  Equity:TransferenciasPendentes {orphan['valor']:>10.2f} BRL")
        lines.append(f"  {conta:40s} {-orphan['valor']:>10.2f} BRL")
        lines.append('  origem_id: "orphan_transfer"')
        lines.append("")
        count += 1

    return lines, count
