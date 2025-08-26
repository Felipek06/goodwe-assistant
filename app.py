# app.py (versão só com análise, sem Streamlit)
import os
import json
from pathlib import Path
from datetime import datetime, date, time as dtime
import pandas as pd
from goodwe_client import crosslogin, get_inverter_data_by_column

ROOT = Path(__file__).parent
MOCK_PATH = ROOT / "data" / "mock_today.json"

def carregar_mock(path: Path) -> pd.DataFrame:
    """Carrega o arquivo JSON mock e devolve um DataFrame com datetime."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de mock não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    df = pd.DataFrame(payload["data"])
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
    df.attrs["meta"] = {
        "plant_id": payload.get("plant_id"),
        "inverter_sn": payload.get("inverter_sn"),
        "date": payload.get("date"),
        "timezone": payload.get("timezone"),
        "units": payload.get("units", {})
    }
    return df

def resumo_dia(df: pd.DataFrame) -> dict:
    """Calcula agregados simples para a análise."""
    if df.empty:
        return {}
    energia_dia = float(df["Eday"].dropna().iloc[-1]) if "Eday" in df.columns and not df["Eday"].dropna().empty else 0.0
    if "Pac" in df.columns and not df["Pac"].dropna().empty:
        idx_max = df["Pac"].idxmax()
        pico_p = float(df.loc[idx_max, "Pac"])
        pico_h = df.loc[idx_max, "time"] if "time" in df.columns else None
    else:
        pico_p, pico_h = 0.0, None
    soc_ini = int(df["Cbattery1"].dropna().iloc[0]) if "Cbattery1" in df.columns and not df["Cbattery1"].dropna().empty else None
    soc_fim = int(df["Cbattery1"].dropna().iloc[-1]) if "Cbattery1" in df.columns and not df["Cbattery1"].dropna().empty else None
    return {
        "energia_dia": energia_dia,
        "pico_potencia": pico_p,
        "hora_pico": pico_h,
        "soc_ini": soc_ini,
        "soc_fim": soc_fim,
    }

def parse_column_timeseries(resp_json, column_name: str) -> pd.DataFrame:
    """Extrai série temporal do formato comum do SEMS."""
    def _parse_time(ts):
        v = pd.to_datetime(ts, errors='coerce')
        if pd.isna(v):
            try:
                v = pd.to_datetime(ts, dayfirst=True, errors='coerce')
            except Exception:
                v = pd.NaT
        return v

    items = []
    if isinstance(resp_json, dict):
        data_obj = resp_json.get('data')
        if isinstance(data_obj, dict):
            for key in ('column1', 'column2', 'column3', 'items', 'list', 'datas', 'result'):
                if key in data_obj and isinstance(data_obj[key], list):
                    items = data_obj[key]
                    break
        if not items:
            for key in ('data', 'items', 'list', 'result', 'datas'):
                if key in resp_json and isinstance(resp_json[key], list):
                    items = resp_json[key]
                    break

    if not items:
        return pd.DataFrame()

    times, values = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = it.get('time') or it.get('date') or it.get('collectTime') or it.get('cTime') or it.get('tm')
        if column_name in it:
            v = it.get(column_name)
        else:
            v = it.get('value') or it.get('v') or it.get('val') or it.get('column')
        if t is None or v is None:
            continue
        t_parsed = _parse_time(t)
        if pd.isna(t_parsed):
            continue
        try:
            v_f = float(str(v).replace(',', '.'))
        except Exception:
            continue
        times.append(t_parsed)
        values.append(v_f)

    if not times:
        return pd.DataFrame()
    return pd.DataFrame({'time': times, column_name: values}).dropna()

def fetch_realtime_df(account: str, password: str, inverter_sn: str, req_date: date,
                      columns: list[str], login_region: str = "us", data_region: str = "eu") -> pd.DataFrame:
    """Executa crosslogin e busca várias colunas via GetInverterDataByColumn, unificando por 'time'."""
    token = crosslogin(account, password, login_region)
    dt_str = datetime.combine(req_date, dtime(0, 0)).strftime("%Y-%m-%d %H:%M:%S")
    dfs = []
    for col in columns:
        js = get_inverter_data_by_column(token, inverter_sn, col, dt_str, data_region)
        df_col = parse_column_timeseries(js, col)
        if not df_col.empty:
            dfs.append(df_col)
        else:
            print(f"[AVISO] Não consegui parsear a coluna '{col}'. Veja JSON bruto:")
            print(json.dumps(js, ensure_ascii=False, indent=2))
    if not dfs:
        return pd.DataFrame()
    out = dfs[0]
    for df_next in dfs[1:]:
        out = pd.merge_asof(out.sort_values("time"), df_next.sort_values("time"), on="time", direction="nearest")
    return out
