#!/usr/bin/env python3
"""
Etapa 2: Ordena arquivo unificado por Data e Valor
确定性 transferências fiquem juntas (D e R pareados)
"""

import pandas as pd
from pathlib import Path


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    input_file = data_dir / "unificado_dr.xlsx"
    output_file = data_dir / "unificado_dr_ordenado.xlsx"

    print("Carregando arquivo...")
    df = pd.read_excel(input_file)

    print(f"Total de lançamentos: {len(df)}")

    # Ordenar por Data e depois por Valor (para parear transferências)
    df = df.sort_values(["Data", "Valor", "D/R"]).reset_index(drop=True)

    # Salvar
    df.to_excel(output_file, index=False)
    print(f"Arquivo salvo: {output_file}")

    # Mostrar exemplos de transferências (D e R juntos)
    print("\nPrimeiros 15 registros (ordenados):")
    print(df[["Data", "Descrição", "Valor", "D/R", "CONTA"]].head(15))

    # Verificar se há pares de transferência próximos
    print("\nVerificando pareamento...")
    for i in range(len(df) - 1):
        row1 = df.iloc[i]
        row2 = df.iloc[i + 1]

        # Se mesma data, mesmo valor, mas D/R diferente = transferência
        if (
            row1["Data"] == row2["Data"]
            and row1["Valor"] == row2["Valor"]
            and row1["D/R"] != row2["D/R"]
        ):
            print(f"\nPareamento encontrado:")
            print(
                f"  {row1['Data']} | {row1['Valor']:.2f} | {row1['D/R']} | {row1['CONTA']} | {row1['Descrição'][:40]}"
            )
            print(
                f"  {row2['Data']} | {row2['Valor']:.2f} | {row2['D/R']} | {row2['CONTA']} | {row2['Descrição'][:40]}"
            )
            break

    print("\nPronto! Arquivo ordenado por Data e Valor.")


if __name__ == "__main__":
    main()
