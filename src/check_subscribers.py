#!/usr/bin/env python3
"""
YouTube チャンネル統計監視スクリプト
登録者数が増加、または再生回数が10回増加するごとにntfyで通知を送信する
"""

import os
import re
import sys
import requests

# 設定
CHANNEL_ID = "UC-f98IWFB5drYTG5FFeP1MQ"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
NTFY_URL = "https://ntfy.sh"
SUBSCRIBER_CACHE_FILE = "subscriber_count.txt"
VIEW_THRESHOLD_FILE = "view_count_threshold.txt"
VIEW_COUNT_MILESTONE = 10  # 再生回数の通知間隔


def get_channel_stats(api_key: str) -> tuple[int, int] | None:
    """YouTube Data APIから登録者数と再生回数を取得"""
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

        stats = data["items"][0]["statistics"]
        subscriber_count = int(stats["subscriberCount"])
        view_count = int(stats["viewCount"])
        return subscriber_count, view_count

    except requests.RequestException as e:
        print(f"YouTube API エラー: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        print(f"データ解析エラー: {e}")
        return None


def get_uploads_playlist_id(api_key: str) -> str | None:
    """チャンネルのアップロード動画プレイリストIDを取得"""
    params = {
        "part": "contentDetails",
        "id": CHANNEL_ID,
        "key": api_key,
    }

    try:
        response = requests.get(YOUTUBE_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data.get("items"):
            return None

        return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    except (requests.RequestException, KeyError, IndexError):
        return None


def get_all_video_ids(api_key: str, playlist_id: str) -> list[str]:
    """プレイリストから全動画IDを取得"""
    video_ids = []
    page_token = None

    while True:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(
                YOUTUBE_PLAYLIST_ITEMS_URL, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                video_ids.append(video_id)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        except requests.RequestException:
            break

    return video_ids


def parse_duration(duration: str) -> int:
    """ISO 8601形式の再生時間を秒に変換 (例: PT1H2M3S -> 3723秒)"""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def get_videos_duration(api_key: str, video_ids: list[str]) -> int:
    """動画IDリストから総再生時間（秒）を取得"""
    total_seconds = 0

    # 50件ずつ取得（API制限）
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        params = {
            "part": "contentDetails",
            "id": ",".join(batch),
            "key": api_key,
        }

        try:
            response = requests.get(YOUTUBE_VIDEOS_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                duration = item["contentDetails"]["duration"]
                total_seconds += parse_duration(duration)

        except requests.RequestException:
            continue

    return total_seconds


def format_duration(total_seconds: int) -> str:
    """秒を「X時間Y分」形式にフォーマット"""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}時間{minutes}分"
    else:
        return f"{minutes}分"


def get_total_duration(api_key: str) -> str | None:
    """チャンネル全動画の総再生時間を取得"""
    playlist_id = get_uploads_playlist_id(api_key)
    if not playlist_id:
        return None

    video_ids = get_all_video_ids(api_key, playlist_id)
    if not video_ids:
        return None

    total_seconds = get_videos_duration(api_key, video_ids)
    return format_duration(total_seconds)


def send_notification(
    topic: str, title: str, message: str, tags: list[str]
) -> bool:
    """ntfyで通知を送信"""
    try:
        # JSON形式を使用（HTTPヘッダーはASCIIのみのため日本語不可）
        # JSON形式ではベースURLにPOSTし、topicをボディに含める
        response = requests.post(
            NTFY_URL,
            json={
                "topic": topic,
                "message": message,
                "title": title,
                "tags": tags,
            },
            timeout=30,
        )
        response.raise_for_status()
        print(f"通知を送信しました: {title}")
        return True

    except requests.RequestException as e:
        print(f"ntfy 送信エラー: {e}")
        return False


def notify_subscriber_increase(topic: str, subscriber_count: int) -> bool:
    """登録者数増加の通知を送信"""
    message = f"チャンネル登録者が増えました！\n現在 {subscriber_count:,} 人"
    return send_notification(
        topic, "📈 YouTube登録者増加", message, ["tada", "youtube"]
    )


def notify_view_milestone(
    topic: str, view_count: int, milestone: int, total_duration: str | None = None
) -> bool:
    """再生回数マイルストーン達成の通知を送信"""
    message = f"総再生回数が {milestone:,} 回を突破しました！\n現在 {view_count:,} 回"
    if total_duration:
        message += f"\n総コンテンツ時間: {total_duration}"
    return send_notification(
        topic, "🎬 YouTube再生回数", message, ["movie_camera", "youtube"]
    )


def load_previous_subscriber_count() -> int | None:
    """前回の登録者数をファイルから読み込み"""
    if not os.path.exists(SUBSCRIBER_CACHE_FILE):
        return None

    try:
        with open(SUBSCRIBER_CACHE_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None


def save_subscriber_count(count: int) -> None:
    """現在の登録者数をファイルに保存"""
    with open(SUBSCRIBER_CACHE_FILE, "w") as f:
        f.write(str(count))


def load_view_threshold() -> int | None:
    """再生回数の次の通知閾値をファイルから読み込み"""
    if not os.path.exists(VIEW_THRESHOLD_FILE):
        return None

    try:
        with open(VIEW_THRESHOLD_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None


def save_view_threshold(threshold: int) -> None:
    """再生回数の次の通知閾値をファイルに保存"""
    with open(VIEW_THRESHOLD_FILE, "w") as f:
        f.write(str(threshold))


def calculate_next_threshold(current_count: int) -> int:
    """現在の再生回数から次の通知閾値を計算（10の倍数）"""
    return ((current_count // VIEW_COUNT_MILESTONE) + 1) * VIEW_COUNT_MILESTONE


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

    # 現在のチャンネル統計を取得
    stats = get_channel_stats(api_key)
    if stats is None:
        return 1

    subscriber_count, view_count = stats
    print(f"現在の登録者数: {subscriber_count:,} 人")
    print(f"現在の総再生回数: {view_count:,} 回")

    if is_manual:
        print("手動実行: テスト通知を送信します")
        notify_subscriber_increase(ntfy_topic, subscriber_count)
        total_duration = get_total_duration(api_key)
        if total_duration:
            print(f"総コンテンツ時間: {total_duration}")
        notify_view_milestone(ntfy_topic, view_count, view_count, total_duration)
    else:
        # 登録者数のチェック
        previous_subscriber = load_previous_subscriber_count()

        if previous_subscriber is None:
            print("初回実行: 登録者数を記録します")
        elif subscriber_count > previous_subscriber:
            increase = subscriber_count - previous_subscriber
            print(f"登録者が {increase:,} 人増加しました！")
            notify_subscriber_increase(ntfy_topic, subscriber_count)
        else:
            print("登録者数に変化はありません")

        # 再生回数のチェック
        view_threshold = load_view_threshold()

        if view_threshold is None:
            # 初回実行: 次の閾値を設定
            next_threshold = calculate_next_threshold(view_count)
            print(f"初回実行: 再生回数の次の通知閾値を {next_threshold:,} 回に設定します")
            save_view_threshold(next_threshold)
        elif view_count >= view_threshold:
            # 閾値を超えた！通知を送信
            print(f"再生回数が {view_threshold:,} 回を突破しました！")
            total_duration = get_total_duration(api_key)
            if total_duration:
                print(f"総コンテンツ時間: {total_duration}")
            notify_view_milestone(ntfy_topic, view_count, view_threshold, total_duration)
            # 次の閾値を計算して保存
            next_threshold = calculate_next_threshold(view_count)
            print(f"次の通知閾値を {next_threshold:,} 回に設定します")
            save_view_threshold(next_threshold)
        else:
            print(f"再生回数は閾値 {view_threshold:,} 回に未達です")

    # 現在の登録者数を保存
    save_subscriber_count(subscriber_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
