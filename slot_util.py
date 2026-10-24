from itertools import combinations
from pathlib import Path

import pandas as pd

DEFAULT_SYMBOL_ORDER = ["W", "K", "Q", "J", "10", "9", "S"]


def load_slot_tables(
    xlsx_path,
    reel_sheet="Reel",
    paytable_sheet="PayTable",
    free_spins_sheet="FreeSpins",
):
    xlsx_path = Path(xlsx_path)

    with pd.ExcelFile(xlsx_path) as workbook:
        reel_df = pd.read_excel(
            workbook,
            sheet_name=reel_sheet,
            dtype=str,
            keep_default_na=False,
        )

        paytable_df = pd.read_excel(
            workbook,
            sheet_name=paytable_sheet,
            keep_default_na=False,
        )

        free_spins_df = None
        if free_spins_sheet in workbook.sheet_names:
            free_spins_df = pd.read_excel(
                workbook,
                sheet_name=free_spins_sheet,
                keep_default_na=False,
            )

    reel_df.attrs["表"] = "滾輪表"
    reel_df.attrs["列"] = "Stop 索引"
    reel_df.attrs["行"] = "第幾個滾輪"

    paytable_df["Symbol"] = paytable_df["Symbol"].astype(str)
    paytable_df.set_index("Symbol", inplace=True)

    paytable_df.attrs["表"] = "賠率表"
    paytable_df.attrs["列"] = "連線的 Symbol"
    paytable_df.attrs["行"] = "由左到右的連線數"

    if free_spins_df is not None:
        free_spins_df["Symbol"] = free_spins_df["Symbol"].astype(str)
        free_spins_df.set_index("Symbol", inplace=True)

        free_spins_df.attrs["表"] = "免費遊戲次數表"
        free_spins_df.attrs["列"] = "Scatter Symbol"
        free_spins_df.attrs["行"] = "Scatter 數量"

    return reel_df, paytable_df, free_spins_df

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


def add_scatter_window_counts(reelstop_df, window_height=3):
    scatter_key = f"{window_height}S"
    reelstop_df.loc[scatter_key] = (
        reelstop_df.loc["S"] * window_height
    )
    reelstop_df.loc[f"X_{scatter_key}"] = (
        reelstop_df.loc["-"] - reelstop_df.loc[scatter_key]
    )

def get_scatter_pattern_df(
    reel_df,
    free_spins_df,
    window_height=3,
):
    match_counts = sorted(free_spins_df.columns, reverse=True)
    reel_cols = list(reel_df.columns)
    scatter_key = f"{window_height}S"
    exclude_key = f"X_{scatter_key}"

    rows = []
    for count in match_counts:
        for scatter_reels in combinations(reel_cols, count):
            row = {
                "Symbol": "S",
                "MatchCount": count,
            }

            for reel_col in reel_cols:
                row[reel_col] = (
                    scatter_key
                    if reel_col in scatter_reels
                    else exclude_key
                )

            rows.append(row)

    scatter_df = pd.DataFrame(rows)
    scatter_df.attrs["表"] = "Scatter 組合"
    scatter_df.attrs["列"] = "Symbol x MatchCount"

    return scatter_df


def get_line_pattern_df(
    reel_df,
    paytable_df,
    symbols,
    free_spins_df=None,
    window_height=3,
):
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

    if free_spins_df is not None:
        scatter_df = get_scatter_pattern_df(
            reel_df,
            free_spins_df,
            window_height,
        )
        line_df = pd.concat(
            [line_df, scatter_df],
            ignore_index=True,
        )
        line_df.attrs["表"] = "連線與 Scatter 組合"
    else:
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


def get_fg_trigger_analysis(
    base_pattern_df,
    fg_pattern_df,
    free_spins_df,
):
    match_counts = sorted(free_spins_df.columns)
    free_spins = pd.to_numeric(
        free_spins_df.loc["S", match_counts]
    )

    base_probs = (
        base_pattern_df.loc[base_pattern_df["Symbol"] == "S"]
        .groupby("MatchCount")["Prob"]
        .sum()
    )
    fg_probs = (
        fg_pattern_df.loc[fg_pattern_df["Symbol"] == "S"]
        .groupby("MatchCount")["Prob"]
        .sum()
    )

    fg_trigger_df = pd.DataFrame({
        "MatchCount": match_counts,
        "BaseProb": base_probs.reindex(match_counts, fill_value=0).to_numpy(),
        "InitialSpins": free_spins.to_numpy(),
        "FGProb": fg_probs.reindex(match_counts, fill_value=0).to_numpy(),
        "RetriggerSpins": free_spins.to_numpy(),
    })
    fg_trigger_df["RetriggerContribution"] = (
        fg_trigger_df["FGProb"]
        * fg_trigger_df["RetriggerSpins"]
    )

    expected_retrigger_spins = (
        fg_trigger_df["RetriggerContribution"].sum()
    )
    if expected_retrigger_spins >= 1:
        raise ValueError(
            "Expected retrigger spins must be less than 1."
        )

    spin_multiplier = 1 / (1 - expected_retrigger_spins)
    fg_trigger_df["AverageSpinsPerTrigger"] = (
        fg_trigger_df["InitialSpins"] * spin_multiplier
    )
    fg_trigger_df["SpinsPerBaseSpin"] = (
        fg_trigger_df["BaseProb"]
        * fg_trigger_df["AverageSpinsPerTrigger"]
    )

    fg_trigger_summary = pd.Series(
        {
            "ExpectedRetriggerSpins": expected_retrigger_spins,
            "SpinMultiplier": spin_multiplier,
            "InitialSpinsPerBaseSpin": (
                fg_trigger_df["BaseProb"]
                * fg_trigger_df["InitialSpins"]
            ).sum(),
            "TotalSpinsPerBaseSpin": (
                fg_trigger_df["SpinsPerBaseSpin"].sum()
            ),
        },
        name="Value",
    )

    fg_trigger_df.attrs["表"] = "免費遊戲觸發分析"
    fg_trigger_df.attrs["列"] = "Scatter 數量"
    fg_trigger_df.attrs["行.MatchCount"] = "Scatter 數量 j"
    fg_trigger_df.attrs["行.BaseProb"] = (
        "q_j：Base spin 出現 j 個 Scatter 的機率"
    )
    fg_trigger_df.attrs["行.InitialSpins"] = (
        "t_j：初次觸發給予的免費遊戲次數"
    )
    fg_trigger_df.attrs["行.FGProb"] = (
        "p_j：FG spin 出現 j 個 Scatter 的機率"
    )
    fg_trigger_df.attrs["行.RetriggerSpins"] = (
        "s_j：再次觸發給予的免費遊戲次數"
    )
    fg_trigger_df.attrs["行.RetriggerContribution"] = "p_j s_j"
    fg_trigger_df.attrs["行.AverageSpinsPerTrigger"] = "t_j X"
    fg_trigger_df.attrs["行.SpinsPerBaseSpin"] = "Y_j = q_j t_j X"

    fg_trigger_summary.attrs["表"] = "免費遊戲觸發摘要"
    fg_trigger_summary.attrs["ExpectedRetriggerSpins"] = "Σ p_j s_j"
    fg_trigger_summary.attrs["SpinMultiplier"] = (
        "X = 1 / (1 - Σ p_j s_j)"
    )
    fg_trigger_summary.attrs["InitialSpinsPerBaseSpin"] = (
        "Σ q_j t_j"
    )
    fg_trigger_summary.attrs["TotalSpinsPerBaseSpin"] = "Σ Y_j"

    return fg_trigger_df, fg_trigger_summary
