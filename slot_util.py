from itertools import combinations
from pathlib import Path

import pandas as pd

DEFAULT_SYMBOL_ORDER = ["W", "K", "Q", "J", "10", "9", "S"]


def load_slot_tables(
    xlsx_path,
    reel_sheet="Reel",
    paytable_sheet="PayTable",
    payline_sheet="Payline",
    free_spins_sheet="FreeSpins",
    game_sheet="Game",
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

        payline_df = None
        if payline_sheet in workbook.sheet_names:
            payline_df = pd.read_excel(
                workbook,
                sheet_name=payline_sheet,
                keep_default_na=False,
            )

        free_spins_df = None
        if free_spins_sheet in workbook.sheet_names:
            free_spins_df = pd.read_excel(
                workbook,
                sheet_name=free_spins_sheet,
                keep_default_na=False,
            )

        game_settings = None
        if game_sheet in workbook.sheet_names:
            game_df = pd.read_excel(
                workbook,
                sheet_name=game_sheet,
                keep_default_na=False,
            )
            game_settings = game_df.set_index("Setting")["Value"]

    reel_df.attrs["表"] = "滾輪表"
    reel_df.attrs["列"] = "Stop 索引"
    reel_df.attrs["行"] = "第幾個滾輪"

    paytable_df["Symbol"] = paytable_df["Symbol"].astype(str)
    paytable_df.set_index("Symbol", inplace=True)

    paytable_df.attrs["表"] = "賠率表"
    paytable_df.attrs["列"] = "連線的 Symbol"
    paytable_df.attrs["行"] = "由左到右的連線數"

    if payline_df is not None:
        payline_df.set_index("Line", inplace=True)

        payline_df.attrs["表"] = "賠線表"
        payline_df.attrs["列"] = "Line"
        payline_df.attrs["行"] = "各滾輪上的 Row 索引"

    if free_spins_df is not None:
        free_spins_df["Symbol"] = free_spins_df["Symbol"].astype(str)
        free_spins_df.set_index("Symbol", inplace=True)

        free_spins_df.attrs["表"] = "免費遊戲次數表"
        free_spins_df.attrs["列"] = "Scatter Symbol"
        free_spins_df.attrs["行"] = "Scatter 數量"

    if game_settings is not None:
        game_settings.attrs["表"] = "遊戲設定"
        game_settings.attrs["列"] = "設定名稱"
        game_settings.attrs["值"] = "設定值"

    return (
        reel_df,
        paytable_df,
        payline_df,
        free_spins_df,
        game_settings,
    )


def load_mega_symbol_tables(
    xlsx_path,
    reel_sheet="Reel",
    paytable_sheet="PayTable",
    payline_sheet="Payline",
    mega_case_sheet="MegaCase",
    mega_symbol_sheet="MegaSymbol",
):
    reel_df, paytable_df, payline_df, _, _ = load_slot_tables(
        xlsx_path,
        reel_sheet=reel_sheet,
        paytable_sheet=paytable_sheet,
        payline_sheet=payline_sheet,
        free_spins_sheet=None,
        game_sheet=None,
    )

    with pd.ExcelFile(xlsx_path) as workbook:
        mega_case_df = pd.read_excel(
            workbook,
            sheet_name=mega_case_sheet,
            keep_default_na=False,
        )
        mega_symbol_df = pd.read_excel(
            workbook,
            sheet_name=mega_symbol_sheet,
            keep_default_na=False,
        )

    mega_case_df.set_index("Case", inplace=True)
    mega_case_df.attrs["表"] = "Mega Symbol 覆蓋 Case"
    mega_case_df.attrs["列"] = "Case"
    mega_case_df.attrs["行.Prob"] = "Case 出現機率"
    mega_case_df.attrs["行.Top/Middle/Bottom"] = "各 Row 是否被覆蓋"

    mega_symbol_df["Symbol"] = mega_symbol_df["Symbol"].astype(str)
    mega_symbol_df.set_index("Symbol", inplace=True)
    mega_symbol_df.attrs["表"] = "Mega Symbol 機率表"
    mega_symbol_df.attrs["列"] = "Mega Symbol"
    mega_symbol_df.attrs["行.Prob"] = "Mega Symbol 出現機率"

    return (
        reel_df,
        paytable_df,
        payline_df,
        mega_case_df,
        mega_symbol_df,
    )


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


def get_expanding_wild_window_df(
    reel_df,
    payline_df,
    window_height,
    wild_symbol="W",
):
    rows = []

    for line, payline_row in payline_df.iterrows():
        for reel_col in reel_df.columns:
            reel = reel_df.loc[
                reel_df[reel_col] != "",
                reel_col,
            ].tolist()
            line_position = int(payline_row[reel_col])

            for stop in range(len(reel)):
                window = [
                    reel[(stop + offset) % len(reel)]
                    for offset in range(window_height)
                ]
                has_wild = wild_symbol in window
                raw_symbol = window[line_position]

                rows.append({
                    "Line": line,
                    "Reel": reel_col,
                    "Stop": stop,
                    "LinePosition": line_position,
                    "RawSymbol": raw_symbol,
                    "HasWild": has_wild,
                    "EffectiveSymbol": (
                        wild_symbol if has_wild else raw_symbol
                    ),
                })

    window_df = pd.DataFrame(rows)

    window_df.attrs["表"] = "Expanding Wild 視窗結果"
    window_df.attrs["列"] = "Line x Reel x Stop"
    window_df.attrs["行.LinePosition"] = "Payline 在該 Reel 的 Row 索引"
    window_df.attrs["行.RawSymbol"] = "擴展前 Payline 位置的 Symbol"
    window_df.attrs["行.HasWild"] = "可見視窗內是否包含 Wild"
    window_df.attrs["行.EffectiveSymbol"] = "Expanding Wild 套用後的 Symbol"

    return window_df


def get_expanding_wild_reelstop_df(window_df, symbols):
    reel_cols = window_df["Reel"].drop_duplicates().tolist()
    line_reelstop_dfs = []

    for line, line_window_df in window_df.groupby("Line", sort=False):
        line_reelstop_df = (
            line_window_df
            .groupby(["EffectiveSymbol", "Reel"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=symbols, columns=reel_cols, fill_value=0)
            .astype(int)
        )
        line_reelstop_df.index.name = "Symbol"
        line_reelstop_df.loc["-"] = (
            line_window_df
            .groupby("Reel")["Stop"]
            .nunique()
            .reindex(reel_cols)
            .astype(int)
        )
        add_wild_combination_counts(line_reelstop_df, symbols)
        line_reelstop_dfs.append((line, line_reelstop_df))

    reelstop_df = pd.concat(
        [df for _, df in line_reelstop_dfs],
        keys=[line for line, _ in line_reelstop_dfs],
        names=["Line", "Symbol"],
    )
    
    reelstop_df.attrs["表"] = "各 Payline 的 Expanding Wild 有效 Stop 數"
    reelstop_df.attrs["列"] = "Line x Symbol"
    reelstop_df.attrs["行"] = "第幾個滾輪"

    return reelstop_df


def get_expanding_wild_line_rtp_df(
    line_pattern_df,
    expanding_reelstop_df,
    paytable_df,
):
    lines = (
        expanding_reelstop_df
        .index
        .get_level_values("Line")
        .unique()
    )
    line_rtp_dfs = []

    for line in lines:
        line_df = line_pattern_df.copy()
        add_line_rtp(
            line_df,
            expanding_reelstop_df.loc[line],
            paytable_df,
        )
        line_df.insert(0, "Line", line)
        line_rtp_dfs.append(line_df)

    expanding_line_df = pd.concat(
        line_rtp_dfs,
        ignore_index=True,
    )
    
    expanding_line_df.attrs["表"] = "各 Payline 的 Expanding Wild RTP"
    expanding_line_df.attrs["列"] = "Line x Symbol x MatchCount"

    return expanding_line_df


def _count_windows_without_symbols(
    reel,
    target_symbols,
    window_height,
):
    reel = reel.loc[reel != ""].tolist()

    return sum(
        all(
            reel[(stop + offset) % len(reel)] not in target_symbols
            for offset in range(window_height)
        )
        for stop in range(len(reel))
    )


def add_way_wild_combination_counts(
    reelstop_df,
    reel_df,
    symbols,
    window_height,
):
    base_symbols = get_base_symbols(symbols)

    for symbol in base_symbols:
        combination_symbol = f"W{symbol}"
        reelstop_df.loc[combination_symbol] = (
            reelstop_df.loc["W"] + reelstop_df.loc[symbol]
        ) * window_height

    for symbol in base_symbols:
        combination_symbol = f"W{symbol}"
        target_symbols = {"W", symbol}
        reelstop_df.loc[f"X_{combination_symbol}"] = [
            _count_windows_without_symbols(
                reel_df[reel_col],
                target_symbols,
                window_height,
            )
            for reel_col in reelstop_df.columns
        ]

def add_scatter_window_counts(reelstop_df, window_height):
    scatter_key = f"{window_height}S"
    reelstop_df.loc[scatter_key] = (
        reelstop_df.loc["S"] * window_height
    )
    reelstop_df.loc[f"X_{scatter_key}"] = (
        reelstop_df.loc["-"] - reelstop_df.loc[scatter_key]
    )

def _get_symbol_match_counts(table_df, symbol):
    if table_df is None or symbol not in table_df.index:
        return set()

    return {
        count
        for count, value in table_df.loc[symbol].items()
        if value != "" and pd.notna(value)
    }

def get_scatter_pattern_df(
    reel_df,
    match_counts,
    window_height,
):
    match_counts = sorted(match_counts, reverse=True)
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

    scatter_match_counts = (
        _get_symbol_match_counts(paytable_df, "S")
        | _get_symbol_match_counts(free_spins_df, "S")
    )
    if scatter_match_counts:
        scatter_df = get_scatter_pattern_df(
            reel_df,
            scatter_match_counts,
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

def get_way_pattern_df(
    reel_df,
    paytable_df,
    symbols,
    free_spins_df=None,
    window_height=3,
):
    way_df = get_line_pattern_df(
        reel_df,
        paytable_df,
        symbols,
        free_spins_df,
        window_height,
    )
    way_df.attrs["表"] = (
        "Way 與 Scatter 組合"
        if "S" in way_df["Symbol"].values
        else "Way 組合"
    )

    return way_df

def _get_paytable_value(paytable_df, symbol, match_count):
    if (
        symbol not in paytable_df.index
        or match_count not in paytable_df.columns
    ):
        return 0

    value = paytable_df.loc[symbol, match_count]
    return 0 if value == "" or pd.isna(value) else value

def _get_line_pay(row, paytable_df):
    symbol_pay = _get_paytable_value(
        paytable_df,
        row["Symbol"],
        row["MatchCount"],
    )

    if row.get("LineType") != "LineWK":
        return symbol_pay

    wild_pay = _get_paytable_value(
        paytable_df,
        "W",
        row["LeadingWCount"],
    )
    return max(symbol_pay, wild_pay)

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

    line_df["Pay"] = line_df.apply(
        lambda row: _get_line_pay(row, paytable_df),
        axis=1,
    )
    line_df["RTP"] = line_df["Prob"] * line_df["Pay"]


def get_sticky_wild_state_df(reel_df):
    reel_cols = list(reel_df.columns)
    state_count = 2 ** len(reel_cols)

    rows = []
    for state_id in range(state_count):
        state = f"{state_id:0{len(reel_cols)}b}"
        row = {"State": state}
        row.update({
            reel_col: int(sticky)
            for reel_col, sticky in zip(reel_cols, state)
        })
        rows.append(row)

    sticky_state_df = pd.DataFrame(rows)
    sticky_state_df.attrs["表"] = "Sticky Wild 狀態"
    sticky_state_df.attrs["列"] = "Sticky Wild 狀態"
    sticky_state_df.attrs["行.State"] = "0: 未黏住; 1: 已黏住"
    sticky_state_df.attrs["行.Ri"] = "第 i 輪位置是否已有 Sticky Wild"

    return sticky_state_df


def get_sticky_wild_line_probability_df(
    line_df,
    sticky_state_df,
    reelstop_df,
    paytable_df,
):
    reel_cols = list(reelstop_df.columns)
    sticky_line_df = line_df.copy()
    sticky_line_df["Pay"] = sticky_line_df.apply(
        lambda row: _get_line_pay(row, paytable_df),
        axis=1,
    )

    for _, state_row in sticky_state_df.iterrows():
        state = state_row["State"]
        probability = pd.Series(1.0, index=sticky_line_df.index)

        for reel_col in reel_cols:
            keys = sticky_line_df[reel_col]

            if state_row[reel_col] == 1:
                reel_probability = keys.isin(["W", "-"]).astype(float)
            else:
                reel_probability = (
                    keys.map(reelstop_df[reel_col])
                    .fillna(0)
                    / reelstop_df.loc["-", reel_col]
                )

            probability *= reel_probability

        sticky_line_df[state] = probability

    sticky_line_df.attrs["表"] = "各 Sticky Wild 狀態的連線組合機率"
    sticky_line_df.attrs["列"] = "LineType x Symbol x MatchCount"
    sticky_line_df.attrs["行.Pay"] = "該連線組合的得分"
    sticky_line_df.attrs["行.State"] = (
        "P(Line combination | Sticky Wild state)"
    )

    return sticky_line_df


def get_sticky_wild_state_probability_df(
    reelstop_df,
    sticky_state_df,
    free_spin_count,
):
    reel_cols = list(reelstop_df.columns)
    free_spins = pd.RangeIndex(
        start=1,
        stop=free_spin_count + 1,
        name="FreeSpin",
    )
    elapsed_spins = pd.Series(
        free_spins - 1,
        index=free_spins,
    )
    no_sticky_prob = {
        reel_col: (
            1 - reelstop_df.loc["W", reel_col] / reelstop_df.loc["-", reel_col]
        )
        for reel_col in reel_cols
    }

    state_probability_df = pd.DataFrame(index=free_spins)
    for _, state_row in sticky_state_df.iterrows():
        state = state_row["State"]
        probability = pd.Series(1.0, index=free_spins)

        for reel_col in reel_cols:
            not_sticky = no_sticky_prob[reel_col] ** elapsed_spins
            probability *= (
                1 - not_sticky
                if state_row[reel_col] == 1
                else not_sticky
            )

        state_probability_df[state] = probability

    state_probability_df.attrs["表"] = (
        "各 Free Spin 開始時的 Sticky Wild 狀態機率"
    )
    state_probability_df.attrs["列"] = "第幾把 Free Spin"
    state_probability_df.attrs["行.State"] = "P(Sticky Wild state)"

    return state_probability_df


def get_mega_symbol_state_df(mega_symbol_df):
    rows = []
    for mega_symbol in mega_symbol_df.index:
        for pattern_id in range(2 ** 3):
            pattern = f"{pattern_id:03b}"
            rows.append({
                "State": f"{mega_symbol}_{pattern}",
                "MegaSymbol": mega_symbol,
                "Pattern": pattern,
                "R2": int(pattern[0]),
                "R3": int(pattern[1]),
                "R4": int(pattern[2]),
            })

    mega_state_df = pd.DataFrame(rows)
    mega_state_df.attrs["表"] = "Mega Symbol State"
    mega_state_df.attrs["列"] = "MegaSymbol x Pattern"
    mega_state_df.attrs["行.State"] = "MegaSymbol_Pattern"
    mega_state_df.attrs["行.Pattern"] = (
        "R2、R3、R4 是否被 Mega Symbol 覆蓋"
    )

    return mega_state_df


def _fixed_symbol_matches_key(key, fixed_symbol):
    if key == "-":
        return True

    if key.startswith("X_W"):
        return fixed_symbol not in ("W", key[3:])

    if key.startswith("W") and key != "W":
        return fixed_symbol in ("W", key[1:])

    return key == fixed_symbol


def get_mega_symbol_line_probability_df(
    line_df,
    mega_state_df,
    reelstop_df,
    paytable_df,
):
    reel_cols = list(reelstop_df.columns)
    mega_line_df = line_df.copy()
    mega_line_df["Pay"] = mega_line_df.apply(
        lambda row: _get_line_pay(row, paytable_df),
        axis=1,
    )

    state_probabilities = {}
    for _, state_row in mega_state_df.iterrows():
        state = state_row["State"]
        mega_symbol = state_row["MegaSymbol"]
        probability = pd.Series(1.0, index=mega_line_df.index)

        for reel_col in reel_cols:
            keys = mega_line_df[reel_col]

            if reel_col in ("R2", "R3", "R4") and state_row[reel_col] == 1:
                reel_probability = keys.apply(
                    lambda key: float(
                        _fixed_symbol_matches_key(key, mega_symbol)
                    )
                )
            else:
                reel_probability = (
                    keys.map(reelstop_df[reel_col])
                    .fillna(0)
                    / reelstop_df.loc["-", reel_col]
                )

            probability *= reel_probability

        state_probabilities[state] = probability

    mega_line_df = pd.concat(
        [mega_line_df, pd.DataFrame(state_probabilities)],
        axis=1,
    )

    mega_line_df.attrs["表"] = (
        "各 Mega Symbol State 的連線組合機率"
    )
    mega_line_df.attrs["列"] = "LineType x Symbol x MatchCount"
    mega_line_df.attrs["行.Pay"] = "該連線組合的得分"
    mega_line_df.attrs["行.State"] = (
        "P(Line combination | Mega Symbol state)"
    )

    return mega_line_df


def get_mega_pattern_probability_df(payline_df, mega_case_df):
    row_names = {
        0: "Top",
        1: "Middle",
        2: "Bottom",
    }
    covered_reels = ["R2", "R3", "R4"]
    patterns = [f"{pattern_id:03b}" for pattern_id in range(2 ** 3)]
    pattern_probability_df = pd.DataFrame(
        0.0,
        index=payline_df.index,
        columns=patterns,
    )

    for line, payline_row in payline_df.iterrows():
        for _, case_row in mega_case_df.iterrows():
            pattern = "".join(
                str(int(case_row[row_names[int(payline_row[reel_col])]]))
                for reel_col in covered_reels
            )
            pattern_probability_df.loc[line, pattern] += case_row["Prob"]

    pattern_probability_df.index.name = "Line"
    pattern_probability_df.columns.name = "Pattern"
    pattern_probability_df.attrs["表"] = (
        "各 Payline 的 Mega Symbol Pattern 機率"
    )
    pattern_probability_df.attrs["列"] = "Line"
    pattern_probability_df.attrs["行.Pattern"] = (
        "P(該 Line 的 R2、R3、R4 覆蓋 Pattern)"
    )

    return pattern_probability_df


def add_way_rtp(
    way_df,
    reelstop_df,
    paytable_df,
    window_height,
    way_pay_bet,
):
    def get_reel_factor(key, reel_col):
        if key not in reelstop_df.index:
            return 0

        count = reelstop_df.loc[key, reel_col]
        if key in paytable_df.index:
            count *= window_height

        return count / reelstop_df.loc["-", reel_col]

    factor_cols = []
    for reel_col in reelstop_df.columns:
        factor_col = f"{reel_col} Factor"
        factor_cols.append(factor_col)

        way_df[factor_col] = way_df[reel_col].apply(
            lambda key: get_reel_factor(key, reel_col)
        )
    way_df["Ways"] = way_df[factor_cols].prod(axis=1)

    way_df["Pay"] = way_df.apply(
        lambda row: _get_paytable_value(
            paytable_df,
            row["Symbol"],
            row["MatchCount"],
        ),
        axis=1,
    )
    way_df["RTP"] = way_df["Ways"] * way_df["Pay"] / way_pay_bet

    way_df.attrs["行.Ri Factor"] = "第 i 輪對 Ways 的乘數 (平均有效符號數 / 不接續機率 / 1: 由 pattern 的 K、WK、X_WK、- 決定)"
    way_df.attrs["行.Ways"] = (
        "一般 Symbol：一次 spin 的平均 ways 數；"
        "Scatter：該組合的出現機率"
    )
    way_df.attrs["行.RTP"] = "Ways × Pay / WayPayBet"

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
