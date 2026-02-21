import hashlib
import re

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
    return "".join(word.capitalize() for word in words) if words else "Unknown"


def sanitize_description(desc: str) -> str:
    if pd.isna(desc):
        return "Sem descricao"
    desc = str(desc).strip().replace('"', "'").replace("\n", " ").replace("\r", " ")
    return desc[:57] + "..." if len(desc) > 60 else desc


def get_account_path(conta: str) -> str:
    account_type = ACCOUNTS_TYPE.get(conta, "Assets")
    if account_type == "Liabilities":
        return f"Liabilities:Cartao:{conta}"
    return f"Assets:BR:{conta}"


def get_cartao_from_conta(conta: str, desc: str) -> str:
    mapeamento = {
        "BancoInter": "CartaoDeCreditoInter",
        "C6Bank": "MastercardC6Bank",
        "ItauPersonalite": "LatamPass",
    }

    if conta == "BbCorrente":
        desc_lower = str(desc).lower() if desc else ""
        if "smiles" in desc_lower:
            return "SmilesBbPlatinum"
        return "Saraiva"

    return mapeamento.get(conta)


def generate_pair_id(row1_idx: int, row2_idx: int) -> str:
    combined = f"{row1_idx}_{row2_idx}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def extract_accounts_from_df(df: pd.DataFrame) -> tuple[set, set]:
    bank_accounts, credit_cards = set(), set()
    for _, row in df.iterrows():
        conta = row.get("CONTA")
        if pd.notna(conta):
            acc_type = ACCOUNTS_TYPE.get(conta, "Assets")
            (bank_accounts if acc_type == "Assets" else credit_cards).add(conta)
    return bank_accounts, credit_cards


def extract_categories_from_df(df: pd.DataFrame) -> tuple[set, set]:
    expense_categories = set()
    income_categories = set()

    for _, row in df.iterrows():
        categoria = row.get("Categoria")
        dr = row.get("D/R")
        if pd.notna(categoria):
            clean_cat = sanitize_name(categoria)
            cat_lower = str(categoria).lower()

            if cat_lower in ["transferencias", "transferência", "pagamento de fatura"]:
                continue

            if dr == "R":
                income_categories.add(clean_cat)
            else:
                expense_categories.add(clean_cat)

    return expense_categories, income_categories
