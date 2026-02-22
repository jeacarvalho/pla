#!/usr/bin/env python3
"""
Organizze to Beancount Importer v4 - REGRAS DEFINITIVAS

a) Despesa: Linha D sem R pareado abaixo → Expense+ (conta G), Asset- (conta G)
b) Receita: Linha R sem D pareado acima → Asset+ (conta G), Income- (conta C)
c) Transferência: Duas linhas mesmo valor (D + R) → Asset+ da linha R, Asset- da linha D
   - Se 3 linhas (2D + 1R), a com "Outros" é transferência
d) Pagamento de cartão: D (positivo) no passivo do cartão, Credit na conta banco
"""

import hashlib
import re
from pathlib import Path
from collections import defaultdict

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

CARTAO_PAGAMENTO = {
    "BancoInter": "CartaoDeCreditoInter",
    "C6Bank": "MastercardC6Bank",
    "ItauPersonalite": "LatamPass",
    "BbCorrente": "Saraiva",  # Default, pode ajustar para Smiles depois
}


def sanitize_name(name):
    if pd.isna(name):
        return "Unknown"
    name = str(name).strip()
    accented = "áàâãéèêíïóôõúüñçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÑÇ"
    plain = "aaaaeeeiiooouuncAAAAEEIIIOOOUU"
    for a, p in zip(accented, plain):
        name = name.replace(a, p)
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    words = name.split()
    return "".join(word.capitalize() for word in words) if words else "Unknown"


def sanitize_description(desc):
    if pd.isna(desc):
        return "Sem descricao"
    desc = str(desc).strip().replace('"', "'").replace("\n", " ").replace("\r", " ")
    return desc[:57] + "..." if len(desc) > 60 else desc


def get_account_path(conta):
    account_type = ACCOUNTS_TYPE.get(conta, "Assets")
    return (
        f"Liabilities:Cartao:{conta}"
        if account_type == "Liabilities"
        else f"Assets:BR:{conta}"
    )


def generate_origin_id(row):
    return hashlib.sha256(
        f"{row['Data']}{row.get('Descrição', '')}{row['Valor']}{row.get('CONTA', '')}".encode()
    ).hexdigest()[:16]


def is_income_category(categoria, dr):
    """Detecta se categoria é receita."""
    if pd.isna(categoria):
        return False
    # Se é D (despesa), nunca é receita
    if dr == "D":
        return False
    cat_lower = str(categoria).lower()
    # Categorias que são SEMPRE transferência, não receita
    if "transfer" in cat_lower:
        return False
    income_keywords = [
        "renda",
        "salário",
        "salario",
        "juros",
        "recebimento",
        "depósito",
        "deposito",
        "transferência recebida",
        "outras receitas",
        "ofertas",
        "ajuda",
        "investimentos",
        "dividendos",
    ]
    return any(kw in cat_lower for kw in income_keywords)


def is_pagto_cartao(desc):
    """Detecta se é pagamento de cartão."""
    if pd.isna(desc):
        return False
    desc_lower = str(desc).lower()
    accented = "áàâãéèêíïóôõúüñç"
    plain = "aaaaeeeiiooouunc"
    for a, p in zip(accented, plain):
        desc_lower = desc_lower.replace(a, p)
    return (
        "pagto cartao" in desc_lower
        or "pagto credito" in desc_lower
        or "pagamento da fatura" in desc_lower
        or "pagamento de fatura" in desc_lower
        or "fatura" in desc_lower
    )


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    ledger_dir = project_dir / "ledger"

    input_file = data_dir / "unificado_dr_ordenado.xlsx"
    if not input_file.exists():
        print(f"ERROR: {input_file} not found")
        return

    print("=" * 60)
    print("Organizze -> Beancount Importer v4")
    print("=" * 60)

    print("\nCarregando arquivo...")
    df = pd.read_excel(input_file)
    df["Data"] = pd.to_datetime(df["Data"])
    df = df.sort_values(["Data", "Valor", "D/R"]).reset_index(drop=True)

    print(f"Total: {len(df)} lançamentos")

    # Identificar contas
    bank_accounts, credit_cards = set(), set()
    for _, row in df.iterrows():
        conta = row.get("CONTA")
        if pd.notna(conta):
            acc_type = ACCOUNTS_TYPE.get(conta, "Assets")
            (bank_accounts if acc_type == "Assets" else credit_cards).add(conta)

    print(f"Contas: {len(bank_accounts)} bancárias, {len(credit_cards)} cartões")

    # Para categorias ambíguas, criar tanto expense quanto income
    all_expenses, all_incomes = set(), set()
    for _, row in df.iterrows():
        categoria = row.get("Categoria")
        dr = row.get("D/R")
        if pd.notna(categoria):
            clean_cat = sanitize_name(categoria)
            # Se é lançamento R (receita), criar como income
            if dr == "R":
                all_incomes.add(clean_cat)
            else:
                all_expenses.add(clean_cat)

    lines = [
        "; Accounts Beancount - Auto-generated by organizze_v4.py",
        "; DO NOT EDIT MANUALLY",
        "",
        '2018-01-01 open Equity:SaldoInicial BRL "STRICT"',
        "",
    ]
    for acc in sorted(bank_accounts):
        lines.append(f'2018-01-01 open Assets:BR:{acc} BRL "STRICT"')
    lines.append("")
    for acc in sorted(credit_cards):
        lines.append(f'2018-01-01 open Liabilities:Cartao:{acc} BRL "STRICT"')
    lines.append("")
    for exp in sorted(all_expenses):
        lines.append(f'2018-01-01 open Expenses:{exp} BRL "STRICT"')
    lines.append("")
    for inc in sorted(all_incomes):
        lines.append(f'2018-01-01 open Income:{inc} BRL "STRICT"')

    with open(ledger_dir / "accounts.beancount", "w") as f:
        f.write("\n".join(lines))

    # IDENTIFICAR TIPOS DE LANÇAMENTO
    print("\nIdentificando tipos de lançamento...")

    # Agrupar por (data, valor_absoluto)
    groups = defaultdict(list)
    for idx, row in df.iterrows():
        key = (row["Data"], abs(row["Valor"]))
        groups[key].append(idx)

    # Marcar transferências pareadas
    is_transfer = set()
    is_pagto_cartao_processed = set()

    for (date, valor_abs), indices in groups.items():
        if len(indices) < 2:
            continue

        # Contar D e R
        d_rows = [i for i in indices if df.iloc[i]["D/R"] == "D"]
        r_rows = [i for i in indices if df.iloc[i]["D/R"] == "R"]

        # Caso 1: 1 D + 1 R = transferência
        if len(d_rows) == 1 and len(r_rows) == 1:
            i, j = d_rows[0], r_rows[0]
            row_d = df.iloc[i]
            row_r = df.iloc[j]
            desc_d = str(row_d.get("Descrição", "")).lower()
            desc_r = str(row_r.get("Descrição", "")).lower()
            cat_d = str(row_d.get("Categoria", "")).lower()
            cat_r = str(row_r.get("Categoria", "")).lower()

            # É transferência se:
            # - As descrições são IGUAIS (mesma transação) OU
            # - Uma das categorias é "outros" OU
            # - Descrições têm palavra de transferência
            is_same_desc = desc_d == desc_r
            is_outros = cat_d == "outros" or cat_r == "outros"
            is_transfer_keyword = any(
                kw in desc_d or kw in desc_r
                for kw in [
                    "transfer",
                    "pix",
                    "pagto cartao",
                    "boleto",
                    "pagto credito",
                    "saque",
                ]
            )

            if is_same_desc or is_outros or is_transfer_keyword:
                is_transfer.add(i)
                is_transfer.add(j)
                continue

        # Caso 2: 2 D + 1 R = transferência (uma despesa + transferência)
        # A transferência tem categoria "Outros"
        if len(d_rows) == 2 and len(r_rows) == 1:
            for i in d_rows:
                cat = df.iloc[i].get("Categoria", "")
                if pd.notna(cat) and str(cat).lower() == "outros":
                    is_transfer.add(i)
                    is_transfer.add(r_rows[0])
                    break

        # Caso 3: 1 D + 2 R = transferência
        # A transferência tem categoria "Outros"
        if len(d_rows) == 1 and len(r_rows) == 2:
            for j in r_rows:
                cat = df.iloc[j].get("Categoria", "")
                if pd.notna(cat) and str(cat).lower() == "outros":
                    is_transfer.add(d_rows[0])
                    is_transfer.add(j)
                    break

    print(f"Transferências identificadas: {len(is_transfer) // 2}")

    # Gerar history.beancount
    print("\nGerando lançamentos...")
    lines = [
        "; History Beancount - Auto-generated by organizze_v4.py",
        "; DO NOT EDIT MANUALLY",
        "",
    ]

    transfer_count = 0
    regular_count = 0

    for idx, row in df.iterrows():
        date = row["Data"].strftime("%Y-%m-%d")
        desc = sanitize_description(row.get("Descrição", ""))
        value = abs(row["Valor"])  # Sempre positivo
        dr = row["D/R"]
        conta = row.get("CONTA", "")
        categoria = sanitize_name(row.get("Categoria", "SemCategoria"))
        status = row.get("Situação", "Pago")
        flag = "*" if status == "Pago" else "!"

        # Pular se é transferência (será tratada em grupo)
        if idx in is_transfer:
            continue

        # Verificar se é pagamento de cartão
        if is_pagto_cartao(desc):
            # d) Pagamento de cartão: D (positivo) no passivo do cartão, Credit na conta banco
            cartao = CARTAO_PAGAMENTO.get(conta)
            if cartao:
                # Débito no cartão (reduzindo dívida), Crédito na conta
                debit = f"Liabilities:Cartao:{cartao}"
                credit = get_account_path(conta)
                lines.append(f'{date} {flag} "{desc}"')
                lines.append(f"  {debit:40s} {value:>10.2f} BRL")
                lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
                lines.append(f'  origem_id: "{generate_origin_id(row)}"')
                lines.append("")
                is_pagto_cartao_processed.add(idx)
                regular_count += 1
            continue

        # Verificar se é Saldo Inicial
        if "saldo inicial" in desc.lower():
            # Equity -> Asset (entrada de saldo)
            debit = get_account_path(conta)
            credit = "Equity:SaldoInicial"
            lines.append(f'{date} {flag} "{desc}"')
            lines.append(f"  {debit:40s} {value:>10.2f} BRL")
            lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
            lines.append(f'  origem_id: "{generate_origin_id(row)}"')
            lines.append("")
            regular_count += 1
            continue

        # a) Despesa: D sem R pareado abaixo
        if dr == "D":
            # Expense+ (categoria), Asset- (conta)
            debit = f"Expenses:{categoria}"
            credit = get_account_path(conta)
            lines.append(f'{date} {flag} "{desc}"')
            lines.append(f"  {debit:40s} {value:>10.2f} BRL")
            lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
            lines.append(f'  origem_id: "{generate_origin_id(row)}"')
            lines.append("")
            regular_count += 1
            continue

        # b) Receita: R sem D pareado acima
        if dr == "R":
            # Asset+ (conta), Income- (categoria)
            debit = get_account_path(conta)
            credit = f"Income:{categoria}"
            lines.append(f'{date} {flag} "{desc}"')
            lines.append(f"  {debit:40s} {value:>10.2f} BRL")
            lines.append(f"  {credit:40s} {-value:>10.2f} BRL")
            lines.append(f'  origem_id: "{generate_origin_id(row)}"')
            lines.append("")
            regular_count += 1
            continue

    # Processar transferências (duas linhas: D + R)
    print("\nProcessando transferências...")
    transfer_groups = defaultdict(list)
    for idx in is_transfer:
        row = df.iloc[idx]
        key = (row["Data"], abs(row["Valor"]))
        transfer_groups[key].append(idx)

    for (date, valor_abs), indices in transfer_groups.items():
        if len(indices) != 2:
            continue

        row1 = df.iloc[indices[0]]
        row2 = df.iloc[indices[1]]

        # Encontrar D e R
        d_idx = indices[0] if row1["D/R"] == "D" else indices[1]
        r_idx = indices[1] if row2["D/R"] == "R" else indices[0]

        row_d = df.iloc[d_idx]
        row_r = df.iloc[r_idx]

        date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
        desc = sanitize_description(row_d.get("Descrição", ""))

        # c) Transferência: Asset+ da linha R, Asset- da linha D
        from_acc = get_account_path(row_d.get("CONTA"))  # D = origem (saída)
        to_acc = get_account_path(row_r.get("CONTA"))  # R = destino (entrada)

        lines.append(f'{date_str} * "{desc}"')
        lines.append(f"  {from_acc:40s} {-valor_abs:>10.2f} BRL")  # negativo = saída
        lines.append(f"  {to_acc:40s} {valor_abs:>10.2f} BRL")  # positivo = entrada
        lines.append('  origem_id: "transfer_pair"')
        lines.append("")
        transfer_count += 1

    print(f"Transferências processadas: {transfer_count}")
    print(f"Lançamentos regulares: {regular_count}")

    with open(ledger_dir / "history.beancount", "w") as f:
        f.write("\n".join(lines))

    print("\n" + "=" * 60)
    print("Done! Run: bean-check ledger/main.beancount")
    print("=" * 60)


if __name__ == "__main__":
    main()
