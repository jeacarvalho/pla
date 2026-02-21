#!/usr/bin/env python3
"""
Consolida todos os arquivos de exportação do Organizze em um único arquivo.
Adiciona coluna CONTA para identificar qual conta originou cada lançamento.
"""

import pandas as pd
from pathlib import Path


def extract_account_name(filename: str) -> str:
    """Extrai nome da conta do nome do arquivo."""
    name = Path(filename).stem
    name = name.split("_")[0]
    name = name.replace("-", " ").replace("_", " ")
    words = name.split()
    return "".join(word.capitalize() for word in words)


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    output_file = data_dir / "unificado.xlsx"

    all_transactions = []

    xlsx_files = sorted(data_dir.glob("*.xls*"))
    xlsx_files = [f for f in xlsx_files if not f.name.startswith(".")]
    xlsx_files = [f for f in xlsx_files if not f.name.startswith("~")]
    # Excluir arquivos já processados
    xlsx_files = [f for f in xlsx_files if "unificado" not in f.name.lower()]

    for f in xlsx_files:
        account_name = extract_account_name(f.name)
        print(f"Processando: {f.name} -> CONTA: {account_name}")

        df = pd.read_excel(f)
        df["CONTA"] = account_name

        all_transactions.append(df)

    # Consolidar
    consolidated = pd.concat(all_transactions, ignore_index=True)

    # Converter data para datetime
    consolidated["Data"] = pd.to_datetime(consolidated["Data"], dayfirst=True)

    # Ordenar por data
    consolidated = consolidated.sort_values(["Data", "Valor"]).reset_index(drop=True)

    # Salvar
    consolidated.to_excel(output_file, index=False)
    print(f"\nArquivo consolidado salvo: {output_file}")
    print(f"Total de lançamentos: {len(consolidated)}")
    print(f"Colunas: {consolidated.columns.tolist()}")


if __name__ == "__main__":
    main()
