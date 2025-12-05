#!/usr/bin/env python3
"""
YouTube チャンネル登録者数監視スクリプト
登録者数が増加したらntfyで通知を送信する
"""

import os
import sys
import requests

# 設定
CHANNEL_ID = "UC-f98IWFB5drYTG5FFeP1MQ"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"
NTFY_URL = "https://ntfy.sh"
CACHE_FILE = "subscriber_count.txt"


def get_subscriber_count(api_key: str) -> int | None:
    """YouTube Data APIから登録者数を取得"""
    params = {
        "part": "statistics",
        "id": CHANNEL_ID,
        "key": api_key,
    }

    try:
        response = requests.get(YOUTUBE_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data.get("items"):
            print(f"エラー: チャンネルが見つかりません (ID: {CHANNEL_ID})")
            return None

        subscriber_count = int(data["items"][0]["statistics"]["subscriberCount"])
        return subscriber_count

    except requests.RequestException as e:
        print(f"YouTube API エラー: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        print(f"データ解析エラー: {e}")
        return None


def send_notification(topic: str, subscriber_count: int) -> bool:
    """ntfyで通知を送信"""
    try:
        response = requests.post(
            f"{NTFY_URL}/{topic}",
            json={
                "message": f"チャンネル登録者が増えました！\n現在 {subscriber_count:,} 人",
                "title": "YouTube登録者増加",
                "tags": ["tada", "youtube"],
            },
            timeout=30,
        )
        response.raise_for_status()
        print(f"通知を送信しました: 現在 {subscriber_count:,} 人")
        return True

    except requests.RequestException as e:
        print(f"ntfy 送信エラー: {e}")
        return False


def load_previous_count() -> int | None:
    """前回の登録者数をファイルから読み込み"""
    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None


def save_current_count(count: int) -> None:
    """現在の登録者数をファイルに保存"""
    with open(CACHE_FILE, "w") as f:
        f.write(str(count))


def main() -> int:
    # 環境変数から設定を取得
    api_key = os.environ.get("YOUTUBE_API_KEY")
    ntfy_topic = os.environ.get("NTFY_TOPIC")
    trigger_event = os.environ.get("TRIGGER_EVENT", "")
    is_manual = trigger_event == "workflow_dispatch"

    if not api_key:
        print("エラー: YOUTUBE_API_KEY が設定されていません")
        return 1

    if not ntfy_topic:
        print("エラー: NTFY_TOPIC が設定されていません")
        return 1

    # 現在の登録者数を取得
    current_count = get_subscriber_count(api_key)
    if current_count is None:
        return 1

    print(f"現在の登録者数: {current_count:,} 人")

    if is_manual:
        print("手動実行: テスト通知を送信します")
        send_notification(ntfy_topic, current_count)
    else:
        # 前回の登録者数と比較
        previous_count = load_previous_count()

        if previous_count is None:
            print("初回実行: 登録者数を記録します")
        elif current_count > previous_count:
            increase = current_count - previous_count
            print(f"登録者が {increase:,} 人増加しました！")
            send_notification(ntfy_topic, current_count)
        else:
            print("登録者数に変化はありません")

    # 現在の登録者数を保存
    save_current_count(current_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
