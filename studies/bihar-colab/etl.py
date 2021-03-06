from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


collect = 'date_of_first_sample_collection'
confirm = 'date_of_positive_test_confirmation'
release = 'date_of_discharge'
death   = 'date_of_death'

districts = [
    'MUNGER', 'PATNA', 'SIWAN', 'NALANDA', 'LAKHISARAI', 'GOPALGANJ',
    'GAYA', 'BEGUSARAI', 'SARAN', 'BHAGALPUR', 'NAWADA', 'VAISHALI',
    'BUXAR', 'BHOJPUR', 'ROHTAS', 'EAST CHAMPARAN', 'BANKA', 'KAIMUR',
    'MADHEPURA', 'AURANGABAD', 'ARWAL', 'JEHANABAD', 'MADHUBANI',
    'PURNEA', 'DARBHANGA', 'ARARIA', 'SHEIKPURA', 'SITAMARHI',
    'WEST CHAMPARAN', 'KATIHAR', 'SHEOHAR', 'SAMASTIPUR', 'KISHANGANJ',
    'SUPAUL', 'SAHARSA', 'KHAGARIA', 'MUZZAFARPUR'
]

replacements = {
    "PASHCHIM CHAMPARAN": "WEST CHAMPARAN", 
    "PURBA CHAMPARAN"   : "EAST CHAMPARAN", 
    "KAIMUR (BHABUA)"   : "KAIMUR", 
    "MUZAFFARPUR"       : "MUZZAFARPUR", 
    "SHEIKHPURA"        : "SHEIKPURA",
    "SHIEKHPURA"        : "SHEIKPURA",
    "PURNIA"            : "PURNEA"
}

def load_cases(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=[collect, confirm, release])

def split_cases_by_district(cases: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {district: cases[cases["district"] == district] for district in districts}

def get_time_series(cases: pd.DataFrame) -> pd.Series:
    R = cases["case_status"] == "Recovered"
    D = cases["case_status"] == "Deceased"
    H = cases["case_status"].isna()
    recovered = cases[release][R].value_counts().rename("time") 
    infected  = cases[confirm][H].value_counts().rename("time")
    deceased  = cases[death  ][D].value_counts().rename("time")

    time_series = pd.DataFrame({"Hospitalized": infected, "Recovered": recovered, "Deceased": deceased}).fillna(0)
    return time_series
    
def assume_missing_0(df: pd.DataFrame, col: str):
    return df[col] if col in df.columns else 0

def log_delta(time_series: pd.DataFrame) -> pd.DataFrame:
    time_series["cases"] = assume_missing_0(time_series, "Hospitalized") - assume_missing_0(time_series, "Recovered") -  assume_missing_0(time_series, "Deceased")
    log_delta = pd.DataFrame(np.log(time_series.cases)).rename(columns = {"cases" : "logdelta"})
    log_delta["time"] = (log_delta.index - log_delta.index.min()).days
    return log_delta

def district_migration_matrix(matrix_path: Path) -> np.matrix:
    mm = pd.read_csv(matrix_path)
    mm_state = mm[(mm.D_StateCensus2001 == "BIHAR") & (mm.O_StateCensus2001 == "BIHAR")]
    pivot    = mm_state.pivot(index = "D_DistrictCensus2001", columns = "O_DistrictCensus2001", values = "NSS_STMigrants").fillna(0)
    M  = np.matrix(pivot)
    Mn = M/M.sum(axis = 0)
    Mn[np.isnan(Mn)] = 0

    districts = [replacements.get(district, district) for district in pivot.index]

    return (districts, mm_state.groupby("O_DistrictCensus2001")["O_Population_2011"].agg(lambda x: list(x)[0]).values, Mn)

def migratory_influx_matrix(influx_path: Path, num_migrants: int, release_rate: float) -> Dict[str, float]:
    # sources = ['Maharashtra', 'Kerala', 'Karnataka', 'Telangana', 'Andhra Pradesh', 'Gujarat', 'Rajasthan', 'Delhi', 'Punjab', 'Haryana', 'Uttar Pradesh', 'Tamil Nadu', 'Chandigarh']
    source_actives = np.array([21468, 80, 539, 461, 1007, 5291, 1893, 5254, 1595, 377, 1797, 7438, 148])
    source_pops    = np.array([112400000.0, 34520000.0, 61100000.0, 35190000.0, 84580000.0, 60440000.0, 68550000.0, 26500000.0, 27740000.0, 27760000.0, 199800000.0, 72150000.0, 1055000.0])

    flux = pd.read_csv(influx_path).fillna(0)
    flux = flux[flux.State != "Other States"] 
    flux = flux[flux.State != "Grand Total"] 
    flux = flux[[col for col in flux.columns if col not in {"State", "Unknown", "Grand Total"}]]
    # flux.rename(columns = {"Muzaffarpur" : "Muzzafarpur"})

    # influx proportions
    proportions = (flux * (source_actives/source_pops)[:, None]).sum(axis = 0)
    return {replacements.get(k.upper(), k.upper()): v for (k, v) in (num_migrants * release_rate * (proportions / proportions.sum())).astype(int).to_dict().items()}
