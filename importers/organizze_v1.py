#!/usr/bin/env python3
"""
Organizze to Beancount Importer v1.1
Converts multiple Organizze Excel exports to Beancount format.
Supports bank accounts and credit cards.
"""

import hashlib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd


ACCOUNTS_TO_SKIP = set()


def sanitize_name(name: str) -> str:
    """Remove special characters and convert to CamelCase for Beancount."""
    if pd.isna(name):
        return "Unknown"

    name = str(name).strip()

    accented = "áàâãéèêíïóôõúüñçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÑÇ"
    plain = "aaaaeeeiiooouuncAAAAEEIIIOOOUU"
    for a, p in zip(accented, plain):
        name = name.replace(a, p)

    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)

    words = name.split()
    if not words:
        return "Unknown"

    return "".join(word.capitalize() for word in words)


def extract_account_name(filename: str) -> str:
    """Extract account name from filename like 'banco-inter_0_01_02_2026...'"""
    name = Path(filename).stem
    name = name.split("_")[0]
    return sanitize_name(name.lower().replace("-", " ").replace("_", " ")).replace(
        " ", ""
    )


def detect_account_type(file_path: str, df: pd.DataFrame) -> str:
    """Detect if account is bank (Assets) or credit card (Liabilities)."""
    filename = Path(file_path).stem.lower()

    if "cartao" in filename or "credito" in filename or "mastercard" in filename:
        return "Liabilities"
    if "saraiva" in filename or "smiles" in filename:
        return "Liabilities"

    if "Cartão de crédito" in df.columns:
        return "Liabilities"

    return "Assets"


def generate_origin_id(row: pd.Series, account_name: str) -> str:
    """Generate SHA-256 hash for deduplication including account."""
    desc_col = "Descrição" if "Descrição" in row.index else "Descricao"
    desc = row.get(desc_col, "")
    account = row.get("Cartão de crédito", account_name)
    data = f"{row['Data']}{desc}{row['Valor']}{account}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def parse_date(date_val) -> datetime:
    """Parse various date formats from Excel."""
    if isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, str):
        for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
    return pd.to_datetime(date_val)


def load_data(file_path: str) -> pd.DataFrame:
    """Load and preprocess Organizze Excel export."""
    df = pd.read_excel(file_path)
    df.columns = [c.strip() for c in df.columns]
    df["Data"] = df["Data"].apply(parse_date)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
    df = df.sort_values("Data")
    return df


def sanitize_description(desc: str) -> str:
    """Remove or escape problematic characters from description."""
    if pd.isna(desc):
        return "Sem descricao"
    desc = str(desc).strip()
    desc = desc.replace('"', "'")
    desc = desc.replace("\n", " ").replace("\r", " ")
    if len(desc) > 60:
        desc = desc[:57] + "..."
    return desc


def process_all_files(data_dir: Path) -> tuple[list, list, list, list, list]:
    """Process all Excel files and collect accounts/transactions."""
    bank_accounts = set()
    credit_cards = set()
    expenses = set()
    incomes = set()
    all_transactions = []

    xlsx_files = sorted(data_dir.glob("*.xls*"))

    for excel_file in xlsx_files:
        account_name = extract_account_name(excel_file.name)

        if account_name.lower() in ACCOUNTS_TO_SKIP:
            print(f"Skipping already imported: {excel_file.name}")
            continue

        print(f"Processing: {excel_file.name}")
        df = load_data(str(excel_file))

        account_type = detect_account_type(str(excel_file), df)

        if account_type == "Assets":
            bank_accounts.add(account_name)
        else:
            credit_cards.add(account_name)

        for _, row in df.iterrows():
            category = row.get("Categoria", "")
            if pd.notna(category):
                clean_cat = sanitize_name(category)
                if row["Valor"] < 0:
                    expenses.add(clean_cat)
                else:
                    incomes.add(clean_cat)

            all_transactions.append(
                {
                    "file": excel_file.name,
                    "account_name": account_name,
                    "account_type": account_type,
                    "date": row["Data"],
                    "desc": sanitize_description(
                        row.get("Descrição", row.get("Descricao", ""))
                    ),
                    "category": sanitize_name(category)
                    if pd.notna(category)
                    else "SemCategoria",
                    "value": row["Valor"],
                    "status": row.get("Situação", row.get("Situacao", "Pago")),
                }
            )

        print(f"  -> {len(df)} transactions, type: {account_type}")

    return (
        sorted(bank_accounts),
        sorted(credit_cards),
        sorted(expenses),
        sorted(incomes),
        all_transactions,
    )


def generate_accounts_file(
    bank_accounts: list[str],
    credit_cards: list[str],
    expenses: list[str],
    incomes: list[str],
    first_date: datetime,
    output_path: str,
):
    """Generate accounts.beancount with Open directives."""
    open_date = (first_date - timedelta(days=1)).strftime("%Y-%m-%d")

    lines = [
        "; Accounts Beancount - Auto-generated by organizze_v1.py",
        "; DO NOT EDIT MANUALLY",
        "",
    ]

    lines.append("; Assets (Contas bancárias)")
    for acc in bank_accounts:
        lines.append(f'2024-01-01 open Assets:BR:{acc} BRL "STRICT"')

    lines.append("")
    lines.append("; Liabilities (Cartões de crédito)")
    for card in credit_cards:
        lines.append(f'2024-01-01 open Liabilities:Cartao:{card} BRL "STRICT"')

    lines.append("")
    lines.append("; Expenses (Categorias de despesa)")
    for exp in expenses:
        if "transferencia" in exp.lower():
            continue
        lines.append(f'2024-01-01 open Expenses:{exp} BRL "STRICT"')

    lines.append("")
    lines.append("; Income (Categorias de receita)")
    for inc in incomes:
        if "transferencia" in inc.lower():
            continue
        lines.append(f'2024-01-01 open Income:{inc} BRL "STRICT"')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated: {output_path}")


def generate_history_file(
    transactions: list[dict],
    output_path: str,
    skip_account: str,
):
    """Generate history.beancount with transactions."""
    lines = [
        "; History Beancount - Auto-generated by organizze_v1.py",
        "; DO NOT EDIT MANUALLY",
        "",
    ]

    transactions = sorted(transactions, key=lambda x: (x["date"], x["desc"]))

    regular_entries = []
    all_transfers = []

    for txn in transactions:
        if txn["account_name"].lower() == skip_account.lower():
            continue

        date = txn["date"].strftime("%Y-%m-%d")
        desc = txn["desc"]
        category = txn["category"]
        value = txn["value"]
        status = txn["status"]
        account_name = txn["account_name"]
        account_type = txn["account_type"]

        flag = "*" if status == "Pago" else "!"

        if account_type == "Assets":
            asset_account = f"Assets:BR:{account_name}"
            liability_account = f"Liabilities:Cartao:{account_name}"
        else:
            asset_account = "Assets:BR:BancoInter"
            liability_account = f"Liabilities:Cartao:{account_name}"

        origin_id = generate_origin_id(
            pd.Series(
                {
                    "Data": date,
                    "Descrição": desc,
                    "Valor": value,
                    "Cartão de crédito": account_name,
                }
            ),
            account_name,
        )

        regular_entries.append(
            {
                "date": date,
                "flag": flag,
                "desc": desc,
                "category": category,
                "value": value,
                "asset_account": asset_account,
                "liability_account": liability_account,
                "account_type": account_type,
                "origin_id": origin_id,
            }
        )

    for entry in regular_entries:
        date = entry["date"]
        flag = entry["flag"]
        desc = entry["desc"]
        category = entry["category"]
        value = entry["value"]
        asset_account = entry["asset_account"]
        liability_account = entry["liability_account"]
        account_type = entry["account_type"]
        origin_id = entry["origin_id"]

        abs_value = abs(value)

        # Simplificado: apenas classificar como despesa ou receita
        if value < 0:
            if account_type == "Liabilities":
                debit_account = f"Expenses:{category}"
                credit_account = liability_account
            else:
                debit_account = f"Expenses:{category}"
                credit_account = asset_account
            debit_val = abs_value
            credit_val = -abs_value
        else:
            if account_type == "Liabilities":
                debit_account = liability_account
                credit_account = "Assets:BR:BancoInter"
            else:
                debit_account = asset_account
                credit_account = f"Income:{category}"
            debit_val = abs_value
            credit_val = -abs_value

        lines.append(f'{date} {flag} "{desc}"')
        lines.append(f"  {debit_account:40s} {debit_val:>10.2f} BRL")
        lines.append(f"  {credit_account:40s} {credit_val:>10.2f} BRL")
        lines.append(f'  origem_id: "{origin_id}"')
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated: {output_path}")


def main():
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    data_dir = project_dir / "data"
    ledger_dir = project_dir / "ledger"

    if not data_dir.exists():
        print("ERROR: data/ directory not found")
        sys.exit(1)

    print("=" * 50)
    print("Organizze -> Beancount Importer v1.1")
    print("=" * 50)

    (
        bank_accounts,
        credit_cards,
        expenses,
        incomes,
        transactions,
    ) = process_all_files(data_dir)

    if not transactions:
        print("ERROR: No transactions to import")
        sys.exit(1)

    print(f"\nTotal: {len(transactions)} transactions")
    print(f"Bank accounts: {len(bank_accounts)} - {bank_accounts}")
    print(f"Credit cards: {len(credit_cards)} - {credit_cards}")
    print(f"Expenses: {len(expenses)}")
    print(f"Incomes: {len(incomes)}")

    first_date = min(t["date"] for t in transactions)

    accounts_file = ledger_dir / "accounts.beancount"
    generate_accounts_file(
        bank_accounts, credit_cards, expenses, incomes, first_date, str(accounts_file)
    )

    history_file = ledger_dir / "history.beancount"
    generate_history_file(transactions, str(history_file), "banco-inter")

    print("\n" + "=" * 50)
    print("Done! Run: bean-check ledger/main.beancount")
    print("=" * 50)


if __name__ == "__main__":
    main()
