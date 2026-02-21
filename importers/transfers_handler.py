"""
Handler para processamento de transferências do Organizze.

Responsabilidades:
- Identificar transferências (D + R pareados por valor, ±2 dias)
- Identificar saques ATM (conta bancária -> Carteira)
- Isolar saldos iniciais e ajustes
- Processar transferências órfãs
- Gerar entradas Beancount para transferências
"""

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any

import pandas as pd

from organizze_shared import (
    generate_pair_id,
    get_account_path,
    sanitize_description,
)


logger = logging.getLogger(__name__)

CATEGORIAS_TRANSFERENCIA = {
    "transferências",
    "transferência",
    "outros",
    "pagamento de fatura",
}


def identify_transfers(
    df: pd.DataFrame,
    excluded_indices: set[int],
) -> tuple[set[int], list[dict[str, Any]]]:
    """
    Identifica transferências pareadas usando algoritmo de matching global.

    Returns:
        Tuple de (processed_indices, orphans)
    """
    transferencia_indices = []
    saldo_inicial_indices = []

    for idx, row in df.iterrows():
        if idx in excluded_indices:
            continue

        desc = (
            str(row.get("Descrição", "")).lower()
            if pd.notna(row.get("Descrição"))
            else ""
        )
        cat = (
            str(row.get("Categoria", "")).lower()
            if pd.notna(row.get("Categoria"))
            else ""
        )

        if "saldo inicial" in desc or "ajuste" in desc:
            saldo_inicial_indices.append(idx)
            continue

        if cat in CATEGORIAS_TRANSFERENCIA:
            transferencia_indices.append(idx)

    logger.info(
        f"Entradas com Categoria={CATEGORIAS_TRANSFERENCIA}: {len(transferencia_indices)}"
    )
    logger.info(f"Saldos iniciais/ajustes isolados: {len(saldo_inicial_indices)}")

    processed_as_transfer: set[int] = set()
    orphans: list[dict[str, Any]] = []

    # Agrupar por (data, valor) para matching global
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)

    for idx in transferencia_indices:
        row = df.iloc[idx]
        valor = abs(row["Valor"])
        data = row["Data"].date() if hasattr(row["Data"], "date") else row["Data"]

        groups[(data, valor)].append(
            {
                "idx": idx,
                "conta": row["CONTA"],
                "valor": valor,
                "data": row["Data"],
                "dr": row["D/R"],
                "categoria": str(row.get("Categoria", "")).lower(),
                "desc": row.get("Descrição", ""),
                "is_saque": "saque" in str(row.get("Descrição", "")).lower(),
            }
        )

    # Processar cada grupo: fazer matching otimizado
    for (data, valor), entries in groups.items():
        # Separar D e R
        debits = [e for e in entries if e["dr"] == "D"]
        credits = [e for e in entries if e["dr"] == "R"]

        if not debits or not credits:
            continue

        # Tentar matching: primeiro por categoria igual, depois por qualquer
        matched_debits = set()
        matched_credits = set()

        # Primeira fase: matching por categoria IGUAL
        for d in debits:
            if d["idx"] in matched_debits:
                continue
            for c in credits:
                if c["idx"] in matched_credits:
                    continue
                if d["conta"] != c["conta"] and d["categoria"] == c["categoria"]:
                    date_diff = abs((d["data"] - c["data"]).days)
                    if date_diff <= 2:
                        matched_debits.add(d["idx"])
                        matched_credits.add(c["idx"])
                        processed_as_transfer.add(d["idx"])
                        processed_as_transfer.add(c["idx"])
                        logger.debug(
                            f"Par encontrado (mesma cat): {d['idx']} <-> {c['idx']}"
                        )
                        break

        # Segunda fase: matching por categoria DIFERENTE (apenas para quem sobrou)
        for d in debits:
            if d["idx"] in matched_debits:
                continue
            for c in credits:
                if c["idx"] in matched_credits:
                    continue
                if d["conta"] != c["conta"]:
                    date_diff = abs((d["data"] - c["data"]).days)
                    if date_diff <= 2:
                        matched_debits.add(d["idx"])
                        matched_credits.add(c["idx"])
                        processed_as_transfer.add(d["idx"])
                        processed_as_transfer.add(c["idx"])
                        logger.debug(
                            f"Par encontrado (cat diff): {d['idx']} <-> {c['idx']}"
                        )
                        break

        # Marcar não pareados como órfãos
        for d in debits:
            if d["idx"] not in matched_debits:
                orphans.append({**d, "debug_motivo": "sem_par_identificado_D"})
        for c in credits:
            if c["idx"] not in matched_credits:
                orphans.append({**c, "debug_motivo": "sem_par_identificado_R"})

    # Processar saldos iniciais e ajustes
    for idx in saldo_inicial_indices:
        row = df.iloc[idx]
        desc = str(row.get("Descrição", "")).lower()

        if "saldo inicial" in desc:
            orphans.append(
                {
                    "idx": idx,
                    "conta": row["CONTA"],
                    "valor": abs(row["Valor"]),
                    "data": row["Data"],
                    "dr": row["D/R"],
                    "desc": row.get("Descrição", ""),
                    "tipo": "saldo_inicial",
                }
            )
        elif "ajuste" in desc:
            orphans.append(
                {
                    "idx": idx,
                    "conta": row["CONTA"],
                    "valor": abs(row["Valor"]),
                    "data": row["Data"],
                    "dr": row["D/R"],
                    "desc": row.get("Descrição", ""),
                    "tipo": "ajuste",
                }
            )

    # Log de órfãos
    for orphan in orphans:
        orphan_type = orphan.get("tipo", orphan.get("debug_motivo", "unknown"))
        logger.warning(
            f"Transferência órfã: {orphan['data']} | "
            f"{orphan['conta']} | {orphan['valor']} | D/R={orphan['dr']} | "
            f"motivo={orphan_type}"
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
    transfer_groups: dict[tuple, list[int]] = defaultdict(list)
    for idx in processed_as_transfer:
        row = df.iloc[idx]
        key = (row["Data"], abs(row["Valor"]))
        transfer_groups[key].append(idx)

    lines = []
    count = 0

    for (date, valor), indices in sorted(transfer_groups.items()):
        entries = [df.iloc[idx] for idx in indices]

        debits = [e for e in entries if e["D/R"] == "D"]
        credits = [e for e in entries if e["D/R"] == "R"]

        matched_debits = set()
        matched_credits = set()

        for d in debits:
            if d.name in matched_debits:
                continue
            for c in credits:
                if c.name in matched_credits:
                    continue
                if d["CONTA"] != c["CONTA"]:
                    matched_debits.add(d.name)
                    matched_credits.add(c.name)

                    date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
                    desc = sanitize_description(d.get("Descrição", ""))

                    desc_lower = str(d.get("Descrição", "")).lower()
                    is_saque = "saque" in desc_lower

                    from_acc = get_account_path(d.get("CONTA"))

                    if is_saque:
                        to_acc = get_account_path("Carteira")
                    else:
                        to_acc = get_account_path(c.get("CONTA"))

                    lines.append(f'{date_str} * "{desc}"')
                    lines.append(f"  {from_acc:40s} {-valor:>10.2f} BRL")
                    lines.append(f"  {to_acc:40s} {valor:>10.2f} BRL")
                    pair_id = generate_pair_id(d.name, c.name)
                    origem_id = "saque_atm" if is_saque else f"transfer_pair:{pair_id}"
                    lines.append(f'  origem_id: "{origem_id}"')
                    lines.append("")
                    count += 1
                    break

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
        valor = orphan["valor"]
        dr = orphan["dr"]

        orphan_type = orphan.get("tipo")
        debug_motivo = orphan.get("debug_motivo", "")

        conta = get_account_path(orphan["conta"])

        if orphan_type == "saldo_inicial":
            lines.append(f'{date_str} * "{desc}"')
            lines.append(f"  {conta:40s} {valor:>10.2f} BRL")
            lines.append(f"  Equity:SaldoInicial {-valor:>10.2f} BRL")
            lines.append(f'  origem_id: "saldo_inicial"')
            if debug_motivo:
                lines.append(f'  debug_motivo: "{debug_motivo}"')
            lines.append("")
            count += 1

        elif orphan_type == "ajuste":
            if dr == "D":
                lines.append(f'{date_str} * "{desc}"')
                lines.append(f"  {conta:40s} {valor:>10.2f} BRL")
                lines.append(f"  Equity:Ajustes {-valor:>10.2f} BRL")
            else:
                lines.append(f'{date_str} * "{desc}"')
                lines.append(f"  Equity:Ajustes {valor:>10.2f} BRL")
                lines.append(f"  {conta:40s} {-valor:>10.2f} BRL")
            lines.append(f'  origem_id: "ajuste_saldo"')
            if debug_motivo:
                lines.append(f'  debug_motivo: "{debug_motivo}"')
            lines.append("")
            count += 1

        else:
            lines.append(f'{date_str} * "{desc}"')
            lines.append(f"  Equity:TransferenciasPendentes {valor:>10.2f} BRL")
            lines.append(f"  {conta:40s} {-valor:>10.2f} BRL")
            lines.append(f'  origem_id: "orphan_transfer"')
            if debug_motivo:
                lines.append(f'  debug_motivo: "{debug_motivo}"')
            lines.append("")
            count += 1

    return lines, count
