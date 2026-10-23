from itertools import combinations
from pathlib import Path

import pandas as pd

DEFAULT_SYMBOL_ORDER = ["W", "K", "Q", "J", "10", "9", "S"]


def load_slot_tables(xlsx_path):
    xlsx_path = Path(xlsx_path)

    reel_df = pd.read_excel(
        xlsx_path,
        sheet_name="Reel",
        dtype=str,
        keep_default_na=False,
    )

    reel_df.attrs["表"] = "滾輪表"
    reel_df.attrs["列"] = "Stop 索引"
    reel_df.attrs["行"] = "第幾個滾輪"

    paytable_df = pd.read_excel(
        xlsx_path,
        sheet_name="PayTable",
        keep_default_na=False,
    )
    paytable_df["Symbol"] = paytable_df["Symbol"].astype(str)
    paytable_df.set_index("Symbol", inplace=True)

    paytable_df.attrs["表"] = "賠率表"
    paytable_df.attrs["列"] = "連線的 Symbol"
    paytable_df.attrs["行"] = "由左到右的連線數"

    return reel_df, paytable_df


def print_df_attrs(df):
    print("shape:", df.shape)
    for col, desc in df.attrs.items():
        print(f"{col}: {desc}")


def get_reel_symbols(reel_df, preferred_order=DEFAULT_SYMBOL_ORDER):
    symbols = (
        pd.Series(reel_df.to_numpy().ravel())
        .loc[lambda x: x != ""]
        .drop_duplicates()
        .tolist()
    )

    return sorted(
        symbols,
        key=lambda x: (
            preferred_order.index(x)
            if x in preferred_order
            else len(preferred_order)
        ),
    )


def get_reelstop_df(reel_df, symbols):
    reelstop_df = (
        reel_df.apply(lambda col: col.loc[col != ""].value_counts())
        .fillna(0)
        .astype(int)
        .reindex(symbols)
    )
    reelstop_df.loc["-"] = (reel_df != "").sum(axis=0)
    reelstop_df.index.name = "Symbol"

    reelstop_df.attrs["表"] = "Symbol 在各滾輪的 Stop 數"
    reelstop_df.attrs["列"] = "Symbol"
    reelstop_df.attrs["行"] = "第幾個滾輪"

    return reelstop_df


def get_base_symbols(symbols):
    return [
        symbol
        for symbol in symbols
        if symbol not in ("W", "S")
    ]


def add_wild_combination_counts(reelstop_df, symbols):
    base_symbols = get_base_symbols(symbols)

    for symbol in base_symbols:
        combination_symbol = f"W{symbol}"
        reelstop_df.loc[combination_symbol] = (
            reelstop_df.loc["W"] + reelstop_df.loc[symbol]
        )

    for symbol in base_symbols:
        combination_symbol = f"W{symbol}"
        reelstop_df.loc[f"X_{combination_symbol}"] = (
            reelstop_df.loc["-"]
            - reelstop_df.loc[combination_symbol]
        )


def get_line_pattern_df(reel_df, paytable_df, symbols):
    base_symbols = get_base_symbols(symbols)
    match_counts = sorted(paytable_df.columns, reverse=True)
    reel_cols = list(reel_df.columns)

    rows = []
    for symbol in base_symbols:
        for count in match_counts:
            row = {
                "Symbol": symbol,
                "MatchCount": count,
            }

            for reel_id, reel_col in enumerate(reel_cols, start=1):
                if reel_id == 1:
                    row[reel_col] = symbol
                elif reel_id <= count:
                    row[reel_col] = f"W{symbol}"
                elif reel_id == count + 1:
                    row[reel_col] = f"X_W{symbol}"
                else:
                    row[reel_col] = "-"

            rows.append(row)

    line_df = pd.DataFrame(rows)

    line_df.attrs["表"] = "連線組合"
    line_df.attrs["列"] = "Symbol x MatchCount"

    return line_df


def get_line_with_wild_pattern_df(reel_df, paytable_df, symbols):
    base_symbols = get_base_symbols(symbols)
    match_counts = sorted(paytable_df.columns, reverse=True)
    reel_cols = list(reel_df.columns)

    rows = []
    for symbol in base_symbols:
        for count in match_counts:
            row = {
                "LineType": "LineK",
                "Symbol": symbol,
                "MatchCount": count,
                "LeadingWCount": 0,
            }

            for reel_id, reel_col in enumerate(reel_cols, start=1):
                if reel_id <= count:
                    row[reel_col] = symbol
                elif reel_id == count + 1:
                    row[reel_col] = f"X_W{symbol}"
                else:
                    row[reel_col] = "-"

            rows.append(row)

    for symbol in base_symbols:
        for count in match_counts:
            for wild_count in range(1, count):
                for wild_positions in combinations(range(count), wild_count):
                    combination = [symbol] * count
                    for position in wild_positions:
                        combination[position] = "W"

                    leading_w_count = 0
                    for key in combination:
                        if key != "W":
                            break
                        leading_w_count += 1

                    row = {
                        "LineType": "LineWK",
                        "Symbol": symbol,
                        "MatchCount": count,
                        "LeadingWCount": leading_w_count,
                    }

                    for reel_id, reel_col in enumerate(reel_cols, start=1):
                        if reel_id <= count:
                            row[reel_col] = combination[reel_id - 1]
                        elif reel_id == count + 1:
                            row[reel_col] = f"X_W{symbol}"
                        else:
                            row[reel_col] = "-"

                    rows.append(row)

    for count in match_counts:
        row = {
            "LineType": "LineW",
            "Symbol": "W",
            "MatchCount": count,
            "LeadingWCount": count,
        }

        for reel_id, reel_col in enumerate(reel_cols, start=1):
            if reel_id <= count:
                row[reel_col] = "W"
            elif reel_id == count + 1:
                row[reel_col] = "S"
            else:
                row[reel_col] = "-"

        rows.append(row)

    line_df = pd.DataFrame(rows)
    line_df.attrs["表"] = "R1 可為 Wild 的連線組合"
    line_df.attrs["列"] = "LineType x Symbol x MatchCount"

    return line_df


def add_line_rtp(line_df, reelstop_df, paytable_df):
    def get_reel_probability(key, reel_col):
        if key not in reelstop_df.index:
            return 0

        return (
            reelstop_df.loc[key, reel_col]
            / reelstop_df.loc["-", reel_col]
        )

    prob_cols = []
    for reel_col in reelstop_df.columns:
        prob_col = f"{reel_col} Prob"
        prob_cols.append(prob_col)

        line_df[prob_col] = line_df[reel_col].apply(
            lambda key: get_reel_probability(key, reel_col)
        )
    line_df["Prob"] = line_df[prob_cols].prod(axis=1)

    def get_pay(row):
        symbol_pay = paytable_df.loc[
            row["Symbol"],
            row["MatchCount"],
        ]

        if row.get("LineType") != "LineWK":
            return symbol_pay

        leading_w_count = row["LeadingWCount"]
        wild_pay = (
            paytable_df.loc["W", leading_w_count]
            if leading_w_count in paytable_df.columns
            else 0
        )
        return max(symbol_pay, wild_pay)

    line_df["Pay"] = line_df.apply(get_pay, axis=1)
    line_df["RTP"] = line_df["Prob"] * line_df["Pay"]
