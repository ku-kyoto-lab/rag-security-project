# documents.py

# 製造業を想定したサンプル文書（実際の文書はPDF等だが、ここではstr形式で代替）
SAMPLE_DOCS = [
    {
        "id": "doc_001",
        "text": (
            "冷却システム点検手順書（ラインA）: 本手順書はラインAの冷却システムに関する定期点検手順を定めたものである。"
            "点検開始前に必ず保護具（耐熱手袋・安全靴）を着用すること。"
            "手順1: メインバルブが閉じていることを確認する。"
            "手順2: 冷却弁を徐々に開放し、流量計が規定値（毎分50リットル）であることを確認する。"
            "手順3: 温度計が規定値（60℃以下）であることを確認する。"
            "手順4: 異常音・異常振動がないことを目視および触診で確認する。"
            "異常時は直ちに緊急停止ボタンを押し、保守リーダーおよび工場長に連絡すること。"
            "点検頻度は週1回（毎週月曜日の始業前）。記録は点検台帳に記入し3年間保管すること。"
        ),
        "metadata": {
            "doc_type": "SOP",
            "department": "製造部",
            "equipment": "冷却システム",
            "line": "line_a",
            "allowed_groups": ["maintenance_line_a", "plant_manager"],
        },
    },
    {
        "id": "doc_002",
        "text": "非常停止手順書（全ライン共通）: 火災・重傷事故発生時は赤い非常停止ボタンを押す。"
        "その後、工場内放送で避難指示を出し、119番通報を行うこと。",
        "metadata": {
            "doc_type": "SOP",
            "department": "製造部",
            "equipment": "全設備",
            "line": "all",
            "allowed_groups": ["all_staff"],
        },
    },
    {
        "id": "doc_003",
        "text": "工場別収益レポートQ1 2026: A工場の営業利益は前年比+12%。"
        "人員計画として2026年度下期にライン増設を予定。詳細は経営会議資料を参照。",
        "metadata": {
            "doc_type": "経営資料",
            "department": "経営企画部",
            "allowed_groups": ["executive", "plant_manager"],
        },
    },
    {
        "id": "doc_004",
        "text": "試作品X-200 CAD設計仕様書: 外形寸法 150mm×80mm×40mm、材質SUS304。"
        "試作フェーズのため、外部共有禁止。設計変更履歴はGitで管理。",
        "metadata": {
            "doc_type": "設計図面",
            "department": "開発部",
            "allowed_groups": ["dev_team", "plant_manager"],
        },
    },
]

# モック: ユーザーとグループのマッピング（実環境ではIdPに問い合わせる）
USER_GROUPS = {
    "tanaka": ["maintenance_line_a", "all_staff"],  # ラインA保守員
    "suzuki": ["executive", "plant_manager", "all_staff"],  # 工場長
    "yamada": ["all_staff"],  # 一般スタッフ
}
