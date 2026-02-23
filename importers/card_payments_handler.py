"""
Handler para processamento de pagamentos de cartão do Organizze.

Responsabilidades:
- Identificar pagamentos de cartão (D com Categoria="Outros" + descrição com "pagamento/fatura")
- Gerar entradas Beancount para pagamentos de cartão

Lógica de identificação de cartão:
- 2021 - 09/04/2023: qualquer pagamento BB = Saraiva
- 10/04/2023 - 31/01/2025: usa descrição (smiles = Smiles, caso contrário = Saraiva)
- 01/02/2025+: para BbCorrente, maior valor = Smiles, menor = Saraiva
"""

import logging
from collections import defaultdict
from datetime import datetime

import pandas as pd

from organizze_shared import (
    ACCOUNTS_TYPE,
    get_account_path,
    sanitize_description,
)


logger = logging.getLogger(__name__)

DATE_THRESHOLD_SMILE = datetime(2023, 4, 10)
DATE_THRESHOLD_VALUES = datetime(2025, 2, 1)


logger = logging.getLogger(__name__)


def _get_cartao_from_conta(conta: str, desc: str, data: datetime) -> str | None:
    """
    Identifica qual cartão foi pago baseado na conta, descrição e data.

    Lógica:
    - 2021 - 09/04/2023: qualquer pagamento BB = Saraiva
    - 10/04/2023 - 31/01/2025: usa descrição (smiles = Smiles, caso contrário = Saraiva)
    - 01/02/2025+: para BbCorrente, maior valor = Smiles, menor = Saraiva (lógica tratada depois)
    """
    mapeamento = {
        "BancoInter": "CartaoDeCreditoInter",
        "C6Bank": "MastercardC6Bank",
        "ItauPersonalite": "LatamPass",
    }

    if conta in mapeamento:
        return mapeamento[conta]

    if conta == "BbCorrente":
        desc_lower = str(desc).lower() if desc else ""

        if data < DATE_THRESHOLD_SMILE:
            return "Saraiva"

        if data < DATE_THRESHOLD_VALUES:
            if "smiles" in desc_lower:
                return "SmilesBbPlatinum"
            return "Saraiva"

        return "BbCorrente_Pendente"

    return None


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
    """
    Gera entradas Beancount para pagamentos de cartão.

    Para BbCorrente a partir de 01/02/2025: agrupa por mês e determina
    qual é Saraiva (menor valor) e Smiles (maior valor).
    """
    indices = sorted(pagto_cartao_indices)

    bb_indices_by_month = defaultdict(list)

    for idx in indices:
        row = df.iloc[idx]
        conta = row.get("CONTA", "")
        data = row["Data"]

        if conta == "BbCorrente" and data >= DATE_THRESHOLD_VALUES:
            year_month = data.strftime("%Y-%m")
            bb_indices_by_month[year_month].append(idx)

    cartao_mapping = {}

    for year_month, month_indices in bb_indices_by_month.items():
        values = [(idx, abs(df.iloc[idx]["Valor"])) for idx in month_indices]
        values.sort(key=lambda x: x[1])

        menor_idx = values[0][0]
        maior_idx = values[-1][0]

        cartao_mapping[menor_idx] = "Saraiva"
        cartao_mapping[maior_idx] = "SmilesBbPlatinum"

        logger.debug(
            f"2025+: {year_month} - Saraiva={values[0][1]:.2f}, "
            f"Smiles={values[-1][1]:.2f}"
        )

    lines = []
    count = 0

    for idx in indices:
        row = df.iloc[idx]
        data = row["Data"]
        conta = row.get("CONTA", "")

        if idx in cartao_mapping:
            cartao = cartao_mapping[idx]
        else:
            cartao = _get_cartao_from_conta(conta, row.get("Descrição", ""), data)

        if not cartao:
            continue

        lines.extend(_build_card_payment_entry(row, cartao))
        count += 1

    return lines, count


def _build_card_payment_entry(row: pd.Series, cartao: str) -> list[str]:
    date = row["Data"].strftime("%Y-%m-%d")
    desc = sanitize_description(row.get("Descrição", ""))
    value = abs(row["Valor"])
    conta = row.get("CONTA", "")
    status = row.get("Situação", "Pago")
    flag = "*" if status == "Pago" else "!"

    conta_beancount = row.get("conta_beancount")
    if conta_beancount and pd.notna(conta_beancount):
        debit = str(conta_beancount).strip()
    else:
        debit = f"Liabilities:Cartao:{cartao}"

    conta_beancount_credit = row.get("conta_beancount")
    if conta_beancount_credit and pd.notna(conta_beancount_credit):
        credit = str(conta_beancount_credit).strip()
    else:
        credit = get_account_path(conta)

    return [
        f'{date} {flag} "{desc}"',
        f"  {debit:40s} {value:>10.2f} BRL",
        f"  {credit:40s} {-value:>10.2f} BRL",
        '  origem_id: "pagto_cartao"',
        "",
    ]
