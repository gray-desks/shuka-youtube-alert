# YouTube 登録者通知システム

YouTubeチャンネルの登録者数が増加したときに、ntfyでスマホに通知を送信するシステムです。

## 機能

- 15分ごとにYouTube Data APIで登録者数をチェック
- 登録者が増えたらntfyで通知
- 通知内容: 「チャンネル登録者が増えました！現在 ○○ 人」

## セットアップ

### 1. ntfyアプリの設定

1. スマホにntfyアプリをインストール
2. アプリを開き、トピック `shuka-notify-a3b8c1` を購読
3. 「Dozeモードでの即時配信」をオンに設定（推奨）

### 2. GitHub Secretsの設定

リポジトリの **Settings** → **Secrets and variables** → **Actions** で以下を設定:

| Name | Value |
|------|-------|
| `YOUTUBE_API_KEY` | YouTube Data APIキー |
| `NTFY_TOPIC` | `shuka-notify-a3b8c1` |

### 3. GitHub Actionsの有効化

1. リポジトリの **Actions** タブを開く
2. ワークフローが有効になっていることを確認
3. 手動実行でテストする場合は「Run workflow」をクリックする

## ファイル構成

```
├── .github/
│   └── workflows/
│       └── check-subscribers.yml   # GitHub Actions ワークフロー
├── src/
│   └── check_subscribers.py        # メインスクリプト
├── requirements.txt                # Python依存関係
└── README.md
```

## コスト

完全無料で運用できます:
- GitHub Actions: 無料枠内
- YouTube Data API: 無料枠内（1日10,000クォータ）
- ntfy.sh: 無料

## ローカルでのテスト

```bash
export YOUTUBE_API_KEY="your-api-key"
export NTFY_TOPIC="shuka-notify-a3b8c1"
python src/check_subscribers.py
```
