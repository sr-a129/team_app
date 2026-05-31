import streamlit as st
import pandas as pd
import random
from collections import defaultdict

st.set_page_config(
    page_title="企画班分けシステム",
    layout="wide",
)


# -------------------------
# CSV アップロード
# -------------------------
with st.container(border=True):
    st.header("📂 CSV アップロード")
    participants_file = st.file_uploader("参加者CSV", type=["csv"])
    ng_file = st.file_uploader("NGペアCSV", type=["csv"])
    leader_file = st.file_uploader("班長候補CSV", type=["csv"])
    staff_file = st.file_uploader("幹部CSV（任意）", type=["csv"])


if not participants_file:
    st.stop()

df = pd.read_csv(participants_file)
participants = df["名前"].tolist()

# NGペア読み込み
ng_pairs = []
if ng_file:
    ng_df = pd.read_csv(ng_file)
    colA, colB = ng_df.columns[0], ng_df.columns[1]

    for _, row in ng_df.iterrows():
        a = str(row[colA]).strip()
        b = str(row[colB]).strip()

        if a in participants and b in participants:
            ng_pairs.append((a, b))

# -------------------------
# NGチェック関数
# -------------------------
def violates_ng(name, group):
    for member in group:
        if (name, member["名前"]) in ng_pairs or (member["名前"], name) in ng_pairs:
            return True
    return False
    
def check_ng_in_group(group_members):

    names = [m["名前"] for m in group_members]

    for a, b in ng_pairs:
        if a in names and b in names:
            return True, (a, b)

    return False, None

# 幹部読み込み
staff_list = []
if staff_file:
    staff_df = pd.read_csv(staff_file)
    staff_list = [n for n in staff_df["名前"].tolist() if n in participants]

# -------------------------
# 班数設定
# -------------------------
with st.container(border=True):
    st.header("🔢 班数設定")

    mode = st.radio(
        "班数の決め方",
        ["班数を指定", "1班あたり人数を指定"],
        horizontal=True
    )

if mode == "班数を指定":
    group_count = st.number_input("班数", min_value=2, max_value=20, value=6)
else:
    size = st.number_input("1班あたり人数", min_value=3, max_value=20, value=8)
    group_count = max(2, round(len(df) / size))

st.write(f"→ 班数：{group_count}")

# -------------------------
# 補完設定
# -------------------------
with st.container(border=True):
    st.header("🧩 班長候補が不足した場合の補完設定")

    補完属性 = st.multiselect(
        "補完に使う属性（複数選択可）",
        ["1年", "2年", "3年", "幹部CSV"]
    )

col1, col2 = st.columns(2)

with col1:
    generate_button = st.button(
        "🚀 班分け実行",
        use_container_width=True
    )

with col2:
    clear_button = st.button(
        "🔄 リセット",
        use_container_width=True
    )

if clear_button:
    st.session_state["groups"] = None
    st.session_state["true_leaders"] = set()
    st.rerun()

if "groups" not in st.session_state:
    st.session_state["groups"] = None
if "true_leaders" not in st.session_state:
    st.session_state["true_leaders"] = set()

# -------------------------
# 班分けを一度だけ実行
# -------------------------
if generate_button:

    groups = {i: [] for i in range(group_count)}


    # -------------------------
    # 班長候補読み込み ＋ 配置準備（CSVの順番を優先）
    # -------------------------
    leader_list = []
    leader_records = []

    if leader_file:
        leader_df = pd.read_csv(leader_file)

        # CSVの順番どおりに、参加者にいる人だけ採用（strip で安全比較）
        for name in leader_df["名前"].astype(str).str.strip().tolist():
            row = df[df["名前"].astype(str).str.strip() == name]
            if len(row) > 0:
                leader_list.append(name)
                leader_records.append(row.iloc[0].to_dict())

    # -------------------------
    # 班長候補を配置（CSVの順番を優先）
    # -------------------------
    groups = {i: [] for i in range(group_count)}

    # ① 班長候補のうち、実際に班に置く分（班数 or 候補数の少ない方）
    leaders_for_groups = leader_records[:group_count]

    for i, rec in enumerate(leaders_for_groups):
        groups[i].append(rec)

    # ② この時点での「本物の班長」集合
    true_leaders = set(m["名前"] for m in leaders_for_groups)

    # ③ 余った班長候補は通常メンバーへ
    extra_leaders = leader_records[group_count:]
    others = df[~df["名前"].astype(str).str.strip().isin(leader_list)].to_dict("records")
    others += extra_leaders

    # -------------------------
    # 補完候補の抽出
    # -------------------------
    補完候補 = []

    if "1年" in 補完属性:
        補完候補 += df[df["属性"] == "1年"]["名前"].tolist()
    if "2年" in 補完属性:
        補完候補 += df[df["属性"] == "2年"]["名前"].tolist()
    if "3年" in 補完属性:
        補完候補 += df[df["属性"] == "3年"]["名前"].tolist()
    if "幹部CSV" in 補完属性:
        補完候補 += staff_list

    補完候補 = list(
        set(補完候補)
        - set(leader_list)                     # すでに班長候補の人は除外
        - set(m["名前"] for m in extra_leaders)  # 余り班長候補として others に回した人も除外
    )

    補完_records = df[df["名前"].isin(補完候補)].to_dict("records")

    # -------------------------
    # 班長補完（班長候補が班数より少ないときだけ）
    # -------------------------
    if len(leaders_for_groups) < group_count:
        needed = group_count - len(leaders_for_groups)

        for g in range(group_count):
            if needed == 0:
                break
            if len(groups[g]) == 0 and 補完_records:
                cand = 補完_records.pop(0)
                groups[g].append(cand)
                true_leaders.add(cand["名前"])  # 補完で入った人も班長扱い
                needed -= 1

    # -------------------------
    # 残りメンバーを属性バランスで配置
    # -------------------------
    others = [p for p in others if p["名前"] not in 補完候補]

    buckets = defaultdict(list)
    for p in others:
        buckets[(p["属性"], p["性別"])].append(p)

    for key, members in buckets.items():
        random.shuffle(members)

        for person in members:
            placed = False

            # 人数が少ない班から順に試す
            sorted_groups = sorted(groups.keys(), key=lambda x: len(groups[x]))

            for g in sorted_groups:
                if not violates_ng(person["名前"], groups[g]):
                    groups[g].append(person)
                    placed = True
                    break

            if not placed:
                st.error(f"NG制約が強すぎて {person['名前']} を配置できませんでした")


    st.session_state["groups"] = groups
    st.session_state["true_leaders"] = true_leaders


# 2回目以降は保存済みを使う
groups = st.session_state.get("groups")
true_leaders = st.session_state.get("true_leaders", set())


# -------------------------
# タブ構成
# -------------------------
tab_search, tab_result, tab_adjust, tab_export = st.tabs(["🔍 名前検索", "📊 班分け結果", "✏️ 手動調整", "📥 出力"])

with tab_search:
    if groups is None:
        st.info("先に『班分け実行』を押してください")
        st.stop()
    st.header("🔍 名前で検索")

    search_name = st.text_input("名前の一部を入力（例：さ、ゆ、たなど）")

    if search_name:
        candidates = [p for p in df["名前"].tolist() if search_name in p]

        if candidates:
            selected = st.selectbox("該当者を選択", candidates)

            # 選択された人の情報
            person_info = df[df["名前"] == selected].iloc[0]

            # 班を特定
            found_group = None
            for g_id, members in groups.items():
                if any(m["名前"] == selected for m in members):
                    found_group = g_id
                    break

            # 班長かどうか
            is_leader = selected in true_leaders

            if found_group is not None:
                if is_leader:
                    st.success(f"【{selected}】さんは **{found_group+1} 班（班長）** です")
                else:
                    st.success(f"【{selected}】さんは **{found_group+1} 班** です")

                # 班のメンバー一覧
                with st.expander(f"{found_group+1} 班のメンバーを見る"):
                    show_group = pd.DataFrame(groups[found_group])[["名前", "属性", "性別"]]

                    # 班長を太字にする
                    show_group["名前"] = show_group["名前"].astype(str).apply(
                        lambda x: f"⭐ {x}" if x in true_leaders else x
                    )

                    st.dataframe(show_group, use_container_width=True)


            else:
                st.warning("班が見つかりませんでした")

        else:
            st.warning("該当する名前がありません")

with tab_result:
    if groups is None:
        st.info("先に『班分け実行』を押してください")
        st.stop()
    st.header("📊 班分け結果")

    for g_id, members in groups.items():
        show = pd.DataFrame(members)[["名前", "属性", "性別"]]
        
        # 班長を太字に
        show["名前"] = show["名前"].astype(str).apply(
            lambda x: f"⭐ {x}" if x in true_leaders else x
        )

        with st.expander(f"🟦 {g_id + 1} 班（人数 {len(members)}）"):
            st.dataframe(show, use_container_width=True)

            st.write("性別")
            st.write(show["性別"].value_counts())

            st.write("属性")
            st.write(show["属性"].value_counts())
    st.divider()

with tab_adjust:

    st.header("✏️ 手動調整")

    if groups is None:
        st.info("先に班分けを実行してください")
        st.stop()

    # -------------------------
    # 全メンバー取得
    # -------------------------
    member_to_group = {}

    for g_id, members in groups.items():
        for m in members:
            member_to_group[m["名前"]] = g_id

    all_members = sorted(member_to_group.keys())

    st.subheader("🔄 人数交換")

    col1, col2 = st.columns(2)

    with col1:
        person1 = st.selectbox(
            "交換する人①",
            all_members,
            key="swap1"
        )

    with col2:
        person2 = st.selectbox(
            "交換する人②",
            all_members,
            key="swap2"
        )

    if st.button("🔄 交換実行", use_container_width=True):
        if person1 in true_leaders or person2 in true_leaders:
            st.error(
                "班長は交換できません"
            )
            st.stop()

        if person1 == person2:
            st.warning("同じ人は選べません")

        else:

            g1 = member_to_group[person1]
            g2 = member_to_group[person2]

            idx1 = next(
                i for i, m in enumerate(groups[g1])
                if m["名前"] == person1
            )

            idx2 = next(
                i for i, m in enumerate(groups[g2])
                if m["名前"] == person2
            )
            temp_g1 = groups[g1].copy()
            temp_g2 = groups[g2].copy()

            temp_g1[idx1] = groups[g2][idx2]
            temp_g2[idx2] = groups[g1][idx1]
            ng1, pair1 = check_ng_in_group(temp_g1)
            ng2, pair2 = check_ng_in_group(temp_g2)

            if ng1:
                st.error(
                    f"⚠ 交換後NG発生: {pair1[0]} × {pair1[1]}"
                )
                st.stop()

            if ng2:
                st.error(
                    f"⚠ 交換後NG発生: {pair2[0]} × {pair2[1]}"
                )
                st.stop()

            groups[g1][idx1], groups[g2][idx2] = (
                groups[g2][idx2],
                groups[g1][idx1]
            )

            st.session_state["groups"] = groups

            st.success(
                f"{person1} ⇔ {person2} を交換しました"
            )

            st.rerun()

    st.divider()

    st.subheader("🚚 単独移動")

    move_person = st.selectbox(
        "移動する人",
        all_members,
        key="move_person"
    )

    target_group = st.selectbox(
        "移動先",
        [f"{i+1}班" for i in range(len(groups))],
        key="move_target"
    )

    if st.button("🚚 移動実行", use_container_width=True):
        if move_person in true_leaders:
            st.error(
                "班長は単独移動できません"
            )
            st.stop()

        source_group = member_to_group[move_person]
        target_group_id = int(
            target_group.replace("班", "")
        ) - 1

        if source_group == target_group_id:
            st.warning("同じ班です")

        else:

            person_data = None

            for m in groups[source_group]:
                if m["名前"] == move_person:
                    person_data = m
                    break

            groups[source_group] = [
                m
                for m in groups[source_group]
                if m["名前"] != move_person
            ]
            # 移動後の仮想班
            temp_group = groups[target_group_id] + [person_data]

            ng_found, ng_pair = check_ng_in_group(temp_group)

            if ng_found:
                st.error(
                    f"⚠ NGペア発生: {ng_pair[0]} × {ng_pair[1]}"
                )
                st.stop()
            
            groups[target_group_id].append(person_data)

            st.session_state["groups"] = groups

            st.success(
                f"{move_person} を "
                f"{source_group+1}班 → {target_group_id+1}班 "
                "へ移動しました"
            )

            st.rerun()


with tab_export:
    if groups is None:
        st.info("先に『班分け実行』を押してください")
        st.stop()
    # -------------------------
    # 出力（CSV / Excel / テキスト）
    # -------------------------
    st.header("📥 出力")

    # CSV 出力用データ作成
    output_rows = []
    for g_id, members in groups.items():
        for m in members:
            output_rows.append({
                "班": f"{g_id+1}班",
                "名前": m["名前"],
                "属性": m["属性"],
                "性別": m["性別"]
            })

    output_df = pd.DataFrame(output_rows)

    # CSV ダウンロード
    csv_data = output_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📄 CSV をダウンロード",
        data=csv_data,
        file_name="班分け結果.csv",
        mime="text/csv"
    )

    # Excel ダウンロード
    import io
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        for g_id, members in groups.items():
            df_group = pd.DataFrame(members)[["名前", "属性", "性別"]]
            df_group.to_excel(writer, sheet_name=f"{g_id+1}班", index=False)

    st.download_button(
        label="📘 Excel をダウンロード",
        data=excel_buffer.getvalue(),
        file_name="班分け結果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # テキスト出力（LINE用）
    text_output = ""
    for g_id, members in groups.items():
        text_output += f"【{g_id+1}班】\n"
        for m in members:
            text_output += f"- {m['名前']}（{m['属性']}・{m['性別']}）\n"
        text_output += "\n"

    st.text_area("📱 LINE用テキスト", text_output, height=300)
