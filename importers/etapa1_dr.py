#!/usr/bin/env python3
"""
Etapa 1: Processa arquivo unificado
- Cria coluna D/R (Despesa/Receita) baseada no sinal
- Remove sinais negativos
"""

import pandas as pd
from pathlib import Path


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    unificado_file = data_dir / "unificado.xlsx"
    output_file = data_dir / "unificado_dr.xlsx"

    print("Carregando arquivo unificado...")
    df = pd.read_excel(unificado_file)

    print(f"Total de lançamentos: {len(df)}")

    # Criar coluna D/R baseada no sinal do valor
    # Negativo = D (Despesa), Positivo = R (Receita)
    df["D/R"] = df["Valor"].apply(lambda x: "D" if x < 0 else "R")

    # Remover sinais negativos (usar valor absoluto)
    df["Valor"] = df["Valor"].abs()

    # Salvar
    df.to_excel(output_file, index=False)
    print(f"\nArquivo salvo: {output_file}")

    # Mostrar exemplos
    print("\nPrimeiros 10 registros:")
    print(df[["Data", "Descrição", "Valor", "D/R", "CONTA"]].head(10))

    # Contagem
    print(f"\nContagem D/R:")
    print(df["D/R"].value_counts())


if __name__ == "__main__":
    main()
