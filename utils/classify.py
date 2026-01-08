def classify_item(title, description, tags):
    """
    商品のカテゴリを自動分類する。
    - 「立ち絵」が含まれる場合は絶対に除外しない（最優先）
    - ロゴ / UI / 背景 は除外
    - タグも補助的に使用
    """

    title = title or ""
    description = description or ""
    tags = tags or []

    text = f"{title} {description}".lower()
    tags_lower = [t.lower() for t in tags]

    # -----------------------------
    # ① 最優先：立ち絵が含まれていたら絶対に除外しない
    # -----------------------------
    if "立ち絵" in title or "立ち絵" in description:
        return "立ち絵"

    # -----------------------------
    # ② 除外カテゴリ（ロゴ / UI / 背景）
    # -----------------------------
    logo_keywords = ["ロゴ", "logo", "タイトルロゴ", "ロゴデザイン", "ロゴ制作"]
    ui_keywords = ["ui", "配信素材", "overlay", "フレーム", "hud", "ウィジェット"]
    bg_keywords = ["背景", "background", "scenery", "風景", "背景素材", "背景イラスト"]

    # ロゴ除外
    if any(k in text for k in logo_keywords):
        return "除外"

    # UI除外
    if any(k in text for k in ui_keywords):
        return "除外"

    # 背景除外
    if any(k in text for k in bg_keywords):
        return "除外"

    # タグによる背景補助除外
    if any(k in tags_lower for k in bg_keywords):
        return "除外"

    # -----------------------------
    # ③ 立ち絵・アイコン・SDなどの分類（必要なら拡張可能）
    # -----------------------------
    if any(word in text for word in ["アイコン", "icon"]):
        return "アイコン"

    if any(word in text for word in ["sd", "デフォルメ", "ちび"]):
        return "sd"

    # -----------------------------
    # ④ ここまで除外されていなければ通知対象
    # -----------------------------
    return "通知対象"
