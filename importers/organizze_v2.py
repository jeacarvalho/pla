#!/usr/bin/env python3
"""
Organizze to Beancount Importer v2
Lê arquivo unificado e importa ano a ano.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


ACCOUNTS_TYPE = {
    "BancoInter": "Assets",
    "BbCorrente": "Assets",
    "C6Bank": "Assets",
    "Carteira": "Assets",
    "Caixa": "Assets",
    "BancoDoBrasilPoupanca": "Assets",
    "ItauPersonalite": "Assets",
    "RendaVariavelInter": "Assets",
    "CdbC6": "Assets",
    "CdbInter": "Assets",
    "CdbEFundosDaycoval": "Assets",
    "TesouroDiretoInter": "Assets",
    "TesouroEasyinvest": "Assets",
    "Pagol": "Assets",
    "CartaoDeCreditoInter": "Liabilities",
    "MastercardC6Bank": "Liabilities",
    "Saraiva": "Liabilities",
    "SmilesBbPlatinum": "Liabilities",
    "LatamPass": "Liabilities",
}


def sanitize_name(name: str) -> str:
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


def sanitize_description(desc: str) -> str:
    if pd.isna(desc):
        return "Sem descricao"
    desc = str(desc).strip()
    desc = desc.replace('"', "'")
    desc = desc.replace("\n", " ").replace("\r", " ")
    if len(desc) > 60:
        desc = desc[:57] + "..."
    return desc


def get_account_path(conta: str, account_type: str) -> str:
    if account_type == "Liabilities":
        return f"Liabilities:Cartao:{conta}"
    return f"Assets:BR:{conta}"


def generate_origin_id(row: pd.Series) -> str:
    desc = row.get("Descrição", "")
    data = f"{row['Data']}{desc}{row['Valor']}{row.get('CONTA', '')}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def calculate_balances(df: pd.DataFrame) -> dict:
    balances = {}
    for _, row in df.iterrows():
        conta = row.get("CONTA", "")
        if pd.notna(conta):
            acc_type = ACCOUNTS_TYPE.get(conta, "Assets")
            acc_path = get_account_path(conta, acc_type)
            if acc_path not in balances:
                balances[acc_path] = 0.0
            balances[acc_path] += row["Valor"]
    return balances


def process_year(df_year: pd.DataFrame, year: int) -> tuple[set, set, list]:
    """Processa um ano e retorna (expenses, incomes, transfers)."""

    # Identificar transferências (DESABILITADO - pareamento não está funcionando)
    # Os transfers ficam como expenses/incomes e podem ser ajustados manualmente
    paired = set()
    transfers = []

    paired_set = paired

    expenses = set()
    incomes = set()
    transactions = []

    for idx, row in df_year.iterrows():
        if idx in paired_set:
            continue

        date = row["Data"].strftime("%Y-%m-%d")
        desc = sanitize_description(row.get("Descrição", ""))
        category = sanitize_name(row.get("Categoria", "SemCategoria"))
        value = row["Valor"]
        conta = row.get("CONTA", "")
        status = row.get("Situação", "Pago")

        account_type = ACCOUNTS_TYPE.get(conta, "Assets")
        flag = "*" if status == "Pago" else "!"
        origin_id = generate_origin_id(row)

        abs_value = abs(value)

        if value < 0:
            if account_type == "Liabilities":
                debit = f"Expenses:{category}"
                credit = f"Liabilities:Cartao:{conta}"
            else:
                debit = f"Expenses:{category}"
                credit = get_account_path(conta, account_type)
            expenses.add(category)
            transactions.append(
                {
                    "date": date,
                    "flag": flag,
                    "desc": desc,
                    "debit": debit,
                    "credit": credit,
                    "debit_val": abs_value,
                    "credit_val": -abs_value,
                    "origin_id": origin_id,
                }
            )
        else:
            if account_type == "Liabilities":
                debit = f"Liabilities:Cartao:{conta}"
                credit = "Assets:BR:BancoInter"
            else:
                debit = get_account_path(conta, account_type)
                credit = f"Income:{category}"
            incomes.add(category)
            transactions.append(
                {
                    "date": date,
                    "flag": flag,
                    "desc": desc,
                    "debit": debit,
                    "credit": credit,
                    "debit_val": abs_value,
                    "credit_val": -abs_value,
                    "origin_id": origin_id,
                }
            )

    # Adicionar transferências pareadas
    for t in transfers:
        date = t["date"].strftime("%Y-%m-%d")
        desc = sanitize_description(t["desc"])
        val = abs(t["value"])

        if t["value"] < 0:
            from_acc = get_account_path(t["conta1"], t["type1"])
            to_acc = get_account_path(t["conta2"], t["type2"])
        else:
            from_acc = get_account_path(t["conta2"], t["type2"])
            to_acc = get_account_path(t["conta1"], t["type1"])

        transactions.append(
            {
                "date": date,
                "flag": "*",
                "desc": desc,
                "debit": from_acc,
                "credit": to_acc,
                "debit_val": val,
                "credit_val": -val,
                "origin_id": "transfer_pair",
            }
        )

    return expenses, incomes, transactions


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    ledger_dir = project_dir / "ledger"

    unificado_file = data_dir / "unificado.xlsx"
    if not unificado_file.exists():
        print(f"ERROR: {unificado_file} not found")
        return

    print("=" * 60)
    print("Organizze -> Beancount Importer v2 (Completo)")
    print("=" * 60)

    print("\nCarregando arquivo unificado...")
    df = pd.read_excel(unificado_file)
    df["Data"] = pd.to_datetime(df["Data"])
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)

    years = sorted(df["Data"].dt.year.unique())
    print(f"Anos encontrados: {years}")

    # Descobrir todas as contas
    bank_accounts = set()
    credit_cards = set()
    all_expenses = set()
    all_incomes = set()

    for _, row in df.iterrows():
        conta = row.get("CONTA", "")
        if pd.notna(conta):
            acc_type = ACCOUNTS_TYPE.get(conta, "Assets")
            if acc_type == "Assets":
                bank_accounts.add(conta)
            else:
                credit_cards.add(conta)

        category = row.get("Categoria", "")
        if pd.notna(category):
            clean_cat = sanitize_name(category)
            if df.loc[row.name, "Valor"] < 0:
                all_expenses.add(clean_cat)
            else:
                all_incomes.add(clean_cat)

    print(f"Contas bancárias: {len(bank_accounts)}")
    print(f"Cartões: {len(credit_cards)}")

    # Gerar accounts.beancount
    lines = [
        "; Accounts Beancount - Auto-generated by organizze_v2.py",
        "; DO NOT EDIT MANUALLY",
        "",
        "; Equity",
        '2024-01-01 open Equity:SaldoInicial BRL "STRICT"',
        "",
    ]

    lines.append("; Assets (Contas bancárias)")
    for acc in sorted(bank_accounts):
        lines.append(f'2024-01-01 open Assets:BR:{acc} BRL "STRICT"')

    lines.append("")
    lines.append("; Liabilities (Cartões)")
    for acc in sorted(credit_cards):
        lines.append(f'2024-01-01 open Liabilities:Cartao:{acc} BRL "STRICT"')

    lines.append("")
    lines.append("; Expenses")
    for exp in sorted(all_expenses):
        if "transfer" in exp.lower():
            continue
        lines.append(f'2024-01-01 open Expenses:{exp} BRL "STRICT"')

    lines.append("")
    lines.append("; Income")
    for inc in sorted(all_incomes):
        if "transfer" in inc.lower():
            continue
        lines.append(f'2024-01-01 open Income:{inc} BRL "STRICT"')

    accounts_file = ledger_dir / "accounts.beancount"
    with open(accounts_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated: {accounts_file}")

    # Gerar history.beancount por ano
    all_transactions = []

    for year in years:
        print(f"\nProcessando ano {year}...")
        df_year = df[df["Data"].dt.year == year].copy()
        df_year = df_year.sort_values("Data").reset_index(drop=True)

        expenses, incomes, transactions = process_year(df_year, year)
        all_transactions.extend(transactions)
        print(f"  -> {len(transactions)} transações")

    # Ordenar todas as transações por data
    all_transactions.sort(key=lambda x: (x["date"], x["desc"]))

    # Gerar history.beancount
    lines = [
        "; History Beancount - Auto-generated by organizze_v2.py",
        "; DO NOT EDIT MANUALLY",
        "",
    ]

    for txn in all_transactions:
        lines.append(f'{txn["date"]} {txn["flag"]} "{txn["desc"]}"')
        lines.append(f"  {txn['debit']:40s} {txn['debit_val']:>10.2f} BRL")
        lines.append(f"  {txn['credit']:40s} {txn['credit_val']:>10.2f} BRL")
        lines.append(f'  origem_id: "{txn["origin_id"]}"')
        lines.append("")

    history_file = ledger_dir / "history.beancount"
    with open(history_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nGenerated: {history_file}")

    print("\n" + "=" * 60)
    print("Done! Run: bean-check ledger/main.beancount")
    print("=" * 60)


if __name__ == "__main__":
    main()
