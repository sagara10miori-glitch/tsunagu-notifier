# tsunagu-notifier

つなぐ（https://tsunagu.cloud）に出品された  
**新着アイテムを自動で検出し、Discord に通知するボット**です。

- 既存販売 / オークション 両対応  
- Cloudflare 対策済み（UA + retry + proxy）  
- 深夜帯は通知せず、朝 6 時にまとめて送信  
- seller_id キャッシュで高速化  
- URL 正規化により二重通知ゼロ  
- GitHub Actions で毎分自動実行  

---

## 🚀 機能一覧

### ✔ 新着アイテムの自動検出
つなぐの以下 2 種類を監視します：

- 既存販売（exist_products）
- オークション（auctions）

### ✔ Discord 通知（最大 10 件）
- 価格帯に応じて通知デザインを変更  
- サムネイル画像付き  
- 短縮 URL で見やすい  

### ✔ 深夜帯（2:00〜5:59）は通知しない
- 深夜に検出したアイテムは pending に保存  
- 朝 6:00 にまとめて通知  

### ✔ seller_id のキャッシュ
- 出品者ページを毎回開かず高速化  
- Cloudflare のブロックを回避  

### ✔ URL 正規化
- `/auctions/12345?sort=...`  
- `/auctions/12345/`  
- `/auctions/12345#detail`  
などを **同一商品として扱い、二重通知を防止**

---

## 📁 ディレクトリ構成
tsunagu-notifier/ ├── notify.py ├── utils/ │   ├── fetch.py │   ├── storage.py │   ├── hashgen.py │   ├── shorturl.py │   └── discord.py ├── data/ │   ├── last_all.json │   ├── seller_cache.json │   ├── pending_night_exist.json │   └── pending_night_auction.json ├── config/ │   └── exclude_users.txt └── .github/ └── workflows/ └── check.yml


---

## ⚙️ セットアップ

### 1. 依存関係をインストール
pip install -r requirements.txt


### 2. Discord Webhook を設定

GitHub Secrets に以下を追加：

- `DISCORD_WEBHOOK_URL`

必要なら：

- `PROXY_URL`（Cloudflare 対策）

---

## 🕒 GitHub Actions（自動実行）

`.github/workflows/check.yml` により **毎分自動実行**されます。

- pip キャッシュで高速  
- 一時的な失敗は自動リトライ  
- Python 3.11 で安定動作  

---

## 🧩 除外ユーザー設定

`config/exclude_users.txt` に seller_id を記述すると  
その出品者のアイテムは通知されません。

bad_seller_123 spam_account

---

## ⭐ 特別ユーザー（special_users）設定

`config/special_users.txt` に seller_id を記述すると、
そのユーザーの出品は 最優先で通知されます。
🔍 特別ユーザーの扱い
special_users に登録されたユーザーの出品は：
- 深夜帯（2:00〜5:59）でも 即通知される
- 価格が 15000 円以上でも 通知される
- 通常ユーザーより 優先的に通知される
- pending に入らない
- 除外ユーザー（exclude_users）よりも優先される
つまり、「この人の出品だけは絶対に見逃したくない」 という場合に使う機能。


---

## 🧠 仕組み（簡単な説明）

1. つなぐの HTML を取得  
2. 商品リストを解析  
3. URL を正規化してハッシュ化  
4. last_all.json と比較  
5. 新規アイテムだけ通知  
6. 深夜帯は pending に保存  
7. 朝 6 時にまとめて通知  
8. seller_cache.json に seller_id を保存  

---

## 🛡️ 安定性のための工夫

- Cloudflare に弾かれにくい UA  
- retry で一時的な失敗を吸収  
- seller_id キャッシュでアクセス最小化  
- URL 正規化で二重通知ゼロ  
- JSON 保存の例外吸収  

---

## 📜 ライセンス

MIT License

---

## 🤝 貢献

Issue / PR 歓迎です。
