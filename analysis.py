# analysis.py
from datetime import date
from goodwe_client import crosslogin, get_inverter_data_by_column
from app import parse_column_timeseries, fetch_realtime_df, resumo_dia
import pandas as pd

def obter_dados(account, password, inverter_sn, req_date=date.today(), columns=None):
    if columns is None:
        columns = ["Pac", "Eday", "Cbattery1"]

    df = fetch_realtime_df(account, password, inverter_sn, req_date, columns)
    return df

def analisar_dia(df: pd.DataFrame) -> dict:
    return resumo_dia(df)

if __name__ == "__main__":
    # Exemplo: usar credenciais reais ou demo
    account = "demo@goodwe.com"
    password = "GoodweSems123!@#"
    inverter_sn = "5010KETU229W6177"

    df = obter_dados(account, password, inverter_sn)
    print("DataFrame bruto:")
    print(df.head())

    resumo = analisar_dia(df)
    print("\nResumo do dia:")
    print(resumo)
