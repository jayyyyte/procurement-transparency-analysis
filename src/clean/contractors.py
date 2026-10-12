"""Winner identity: one stable key per contractor, so wins can be counted per contractor.

`winningCode` and `contractorName` are parallel lists in the API but NOT in the same order, and for a
consortium (liên danh) there is one name for several member codes — so identity comes from the codes
alone and names are never paired with codes by position.

  nha_thau_key       system code(s) of the winner(s), sorted and joined with " | ". A package whose winners
                     have no system code (unregistered contractors get a fresh UUID per result) is keyed by
                     name instead, scoped to its bid solicitor: "ten:<name key>@<ma_ben_moi_thau>".
  so_nha_thau_trung  number of winners (consortium members, or winners of the lots of a multi-lot package)
  nha_thau_chuan     display name: the contractor's most frequent cleaned name; for several winners the
                     cleaned name string as published
"""
from __future__ import annotations

import pandas as pd

from src.clean.normalize import MA_DINH_DANH, ten_nha_thau_chuan
from src.text import norm_key

SEP = " | "  # as joined by parse.records._join
NAME_PREFIX = "ten:"


def _map_unique(s: pd.Series, fn) -> pd.Series:
    return s.map({v: fn(v) for v in s.dropna().unique()})


def _split(s: pd.Series) -> pd.Series:
    return s.dropna().astype(str).str.split(SEP, regex=False).explode()


def resolve_winners(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Add the three columns above; `df` must have a unique index."""
    df = df.copy()
    clean = _map_unique(df["nha_thau_trung_thau"], ten_nha_thau_chuan)

    codes = _split(df["ma_nha_thau_trung_thau"])
    has_id = codes.index[codes.str.fullmatch(MA_DINH_DANH).to_numpy(dtype=bool)].unique()
    by_code = codes[codes.index.isin(has_id)]
    # no system code at all -> the names are the only identity; valid within one bid solicitor only,
    # because unregistered names ("Nguyễn Thị Hương", "Cửa hàng ...") collide across the country
    names = _split(clean[~clean.index.isin(has_id)])
    nk = _map_unique(names, norm_key).astype(str)
    scope = df["ma_ben_moi_thau"].reindex(names.index).fillna("").astype(str)
    by_name = (NAME_PREFIX + nk + "@" + scope)[(nk != "").to_numpy(dtype=bool)]

    long = pd.concat([by_code, by_name]).rename("key").rename_axis("row").reset_index()
    long = long.drop_duplicates().sort_values(["row", "key"])
    n = long.groupby("row")["key"].transform("size")
    one = long[n == 1].set_index("row")["key"]
    many = long[n > 1].groupby("row")["key"].agg(SEP.join)
    df["nha_thau_key"] = pd.concat([one, many]).reindex(df.index)
    df["so_nha_thau_trung"] = long.groupby("row").size().reindex(df.index)

    single = (df["so_nha_thau_trung"] == 1).to_numpy()
    seen = pd.DataFrame({"key": df.loc[single, "nha_thau_key"].astype(str), "name": clean[single]})
    seen = seen.value_counts().reset_index()
    canon = seen.sort_values(["key", "count", "name"], ascending=[True, False, True]).drop_duplicates("key")
    df["nha_thau_chuan"] = clean.where(~single, df["nha_thau_key"].map(canon.set_index("key")["name"]))

    by_name_rows = df["nha_thau_key"].fillna("").astype(str).str.startswith(NAME_PREFIX).to_numpy()
    variants = seen.loc[~seen["key"].str.startswith(NAME_PREFIX), "key"].value_counts()
    stats = {"packages_with_winner": int(df["nha_thau_key"].notna().sum()),
             "by_system_code": int((single & ~by_name_rows).sum()),
             "by_name_unregistered": int(by_name_rows.sum()),
             "multi_winner": int((df["so_nha_thau_trung"] > 1).sum()),
             "contractors": int(long["key"].nunique()),
             "codes_with_name_variants": int((variants > 1).sum())}
    return df, stats


def explode_winners(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (package, winner); the index still points at the package row."""
    d = df[df["nha_thau_key"].notna()]
    return d.assign(nha_thau_key=d["nha_thau_key"].astype(str).str.split(SEP, regex=False)).explode("nha_thau_key")


def contractor_names(df: pd.DataFrame) -> pd.Series:
    """nha_thau_key -> display name, for contractors seen as the only winner of some package."""
    d = df[df["so_nha_thau_trung"] == 1]
    return d.drop_duplicates("nha_thau_key").set_index("nha_thau_key")["nha_thau_chuan"]
