import datetime
import logging
import math
import os

from google.adk.tools import ToolContext
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import config

logger = logging.getLogger(__name__)


def get_youtube_client():
    """Builds and returns the YouTube Data API client."""
    return build("youtube", "v3", developerKey=config.API_KEY)


def search_youtube(
    query: str, max_results: int = 10, published_after: str = ""
):
    """
    Searches YouTube for videos matching the query.

    Args:
        query: The search term.
        max_results: Maximum number of results to return (default 10).
        published_after: Filter for videos published after this date (RFC 3339 format, e.g., '2023-01-01T00:00:00Z').

    Returns:
        A list of dictionaries containing video title, videoId, and channelTitle.
    """
    try:
        youtube = get_youtube_client()
        kwargs = {
            "q": query,
            "type": "video",
            "part": "id,snippet",
            "maxResults": max_results,
        }
        if published_after:
            kwargs["publishedAfter"] = published_after

        search_response = youtube.search().list(**kwargs).execute()

        results = []
        for search_result in search_response.get("items", []):
            if search_result["id"]["kind"] == "youtube#video":
                results.append(
                    {
                        "title": search_result["snippet"]["title"],
                        "videoId": search_result["id"]["videoId"],
                        "channelTitle": search_result["snippet"][
                            "channelTitle"
                        ],
                        "description": search_result["snippet"]["description"],
                    }
                )
        return results
    except HttpError as e:
        logger.error(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return []


def get_video_details(video_ids: list):
    """
    Retrieves statistics and snippet details for a list of video IDs.

    Args:
        video_ids: A list of video ID strings.

    Returns:
        A list of dictionaries containing video statistics and details.
    """
    if not video_ids:
        return []

    try:
        youtube = get_youtube_client()
        # Join video IDs with comma
        ids_string = ",".join(video_ids)

        video_response = (
            youtube.videos()
            .list(id=ids_string, part="snippet,statistics,contentDetails")
            .execute()
        )

        results = []
        for video_result in video_response.get("items", []):
            stats = video_result["statistics"]
            snippet = video_result["snippet"]
            results.append(
                {
                    "videoId": video_result["id"],
                    "title": snippet["title"],
                    "channelTitle": snippet["channelTitle"],
                    "viewCount": stats.get("viewCount", 0),
                    "likeCount": stats.get("likeCount", 0),
                    "commentCount": stats.get("commentCount", 0),
                    "publishedAt": snippet["publishedAt"],
                    "tags": snippet.get("tags", []),
                }
            )
        return results
    except HttpError as e:
        logger.error(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return []


def get_channel_details(channel_ids: list):
    """
    Retrieves statistics and snippet details for a list of channel IDs.

    Args:
        channel_ids: A list of channel ID strings.

    Returns:
        A list of dictionaries containing channel statistics and details.
    """
    if not channel_ids:
        return []

    try:
        youtube = get_youtube_client()
        ids_string = ",".join(channel_ids)

        channel_response = (
            youtube.channels()
            .list(id=ids_string, part="snippet,statistics")
            .execute()
        )

        results = []
        for channel_result in channel_response.get("items", []):
            stats = channel_result["statistics"]
            snippet = channel_result["snippet"]
            results.append(
                {
                    "channelId": channel_result["id"],
                    "title": snippet["title"],
                    "description": snippet["description"],
                    "subscriberCount": stats.get("subscriberCount", 0),
                    "videoCount": stats.get("videoCount", 0),
                    "viewCount": stats.get("viewCount", 0),
                }
            )
        return results
    except HttpError as e:
        logger.error(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return []


def get_video_comments(video_id: str, max_results: int = 20):
    """
    Retrieves top-level comments for a specific video.

    Args:
        video_id: The ID of the video.
        max_results: Maximum number of comments to return.

    Returns:
        A list of comment strings.
    """
    try:
        youtube = get_youtube_client()
        comment_response = (
            youtube.commentThreads()
            .list(
                videoId=video_id,
                part="snippet",
                maxResults=max_results,
                textFormat="plainText",
            )
            .execute()
        )

        comments = []
        for item in comment_response.get("items", []):
            comment = item["snippet"]["topLevelComment"]["snippet"][
                "textDisplay"
            ]
            comments.append(comment)
        return comments
    except HttpError as e:
        logger.error(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return []


def calculate_engagement_metrics(
    view_count: int, like_count: int, comment_count: int, subscriber_count: int
):
    """
    Calculates engagement rate and active rate based on video statistics.

    Args:
        view_count: Number of views.
        like_count: Number of likes.
        comment_count: Number of comments.
        subscriber_count: Number of subscribers.

    Returns:
        Dictionary containing 'engagement_rate' and 'active_rate' as percentages.
    """
    view_count = int(view_count) if view_count else 0
    like_count = int(like_count) if like_count else 0
    comment_count = int(comment_count) if comment_count else 0
    subscriber_count = int(subscriber_count) if subscriber_count else 0

    engagement_rate = (
        ((like_count + comment_count) / view_count * 100)
        if view_count > 0
        else 0
    )
    active_rate = (
        (view_count / subscriber_count * 100) if subscriber_count > 0 else 0
    )

    return {
        "engagement_rate": round(engagement_rate, 2),
        "active_rate": round(active_rate, 2),
    }


def calculate_match_score(
    subscribers: int,
    engagement_rate: float,
    active_rate: float,
    sentiment_score: float = 0.0,
):
    """
    Calculates a composite match score for a channel/video.

    Args:
        subscribers: Number of subscribers.
        engagement_rate: Engagement rate percentage (0-100).
        active_rate: Active rate percentage (0-100).
        sentiment_score: Sentiment score (-1 to 1).

    Returns:
        A float representing the match score (0-100).
    """
    # Log-normalize subscribers (assuming base 10, offset to avoid log(0))
    sub_log = math.log10(max(subscribers, 1))
    # Normalize sub score: loosely based on 10k-1M+ range mapping to 0-1
    # Original: Math.min(Math.max((subLog - 3) / 4, 0), 1) * 100;
    sub_score = min(max((sub_log - 3) / 4, 0), 1) * 100

    # Cap engagement and active scores at decent thresholds (e.g., 10% eng is great, 100% active is great)
    eng_score = min((engagement_rate / 10), 1) * 100
    active_score = min((active_rate / 100), 1) * 100

    # Normalize sentiment (-1 to 1 -> 0 to 1)
    sent_score = ((sentiment_score + 1) / 2) * 100

    # Weights: Subs(40%) + Eng(30%) + Active(20%) + Sentiment(10%)
    total_score = (
        (sub_score * 0.4)
        + (eng_score * 0.3)
        + (active_score * 0.2)
        + (sent_score * 0.1)
    )

    return round(total_score, 1)


def analyze_sentiment_heuristic(text: str):
    """
    Simple heuristic sentiment analysis based on keyword matching.

    Args:
        text: The text to analyze.

    Returns:
        A score between -1 (negative) and 1 (positive).
    """
    if not text:
        return 0

    positives = [
        "great",
        "good",
        "love",
        "amazing",
        "best",
        "nice",
        "helpful",
        "excellent",
        "wow",
    ]
    negatives = [
        "bad",
        "hate",
        "worst",
        "terrible",
        "awful",
        "boring",
        "useless",
        "poor",
    ]

    lower_text = text.lower()
    score = 0

    for word in positives:
        if word in lower_text:
            score += 0.2

    for word in negatives:
        if word in lower_text:
            score -= 0.2

    return max(-1, min(1, score))


def get_current_date_time():
    """
    Returns the current date and time in UTC (RFC 3339 format).
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_date_range(time_span: str):
    """
    Calculates the date for the start of a time span relative to now.

    Args:
        time_span: The time span to calculate. Options: 'week', 'month', '3month', 'year'.

    Returns:
        A string representing the date in RFC 3339 format (e.g., '2023-01-01T00:00:00Z').
        Returns empty string if time_span is not recognized.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    if time_span == "week":
        delta = datetime.timedelta(weeks=1)
    elif time_span == "month":
        delta = datetime.timedelta(days=30)
    elif time_span == "3month":
        delta = datetime.timedelta(days=90)
    elif time_span == "year":
        delta = datetime.timedelta(days=365)
    else:
        return ""

    past_date = now - delta
    return past_date.isoformat()


async def render_html(
    html_content: str, filename: str, tool_context: ToolContext
):
    """
    Saves HTML content to a file and optionally registers it as an artifact.

    Args:
        html_content: The raw HTML string.
        filename: The output filename.
        tool_context: The ADK tool context (automatically injected if available).

    Returns:
        The path to the saved file.
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filepath = os.path.join(output_dir, filename)

        # Save to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Try to save artifact if context is available
        try:
            await tool_context.save_artifact(
                filename.replace(".", "_"),  # Simple artifact name
                types.Part.from_bytes(
                    data=html_content.encode("utf-8"), mime_type="text/html"
                ),
            )
            logger.info("Successfully saved HTML to tool context")
        except Exception as e:
            logger.warning(f"Warning: Failed to save artifact: {e}")

        return f"HTML saved to {filename}"
    except Exception as e:
        return f"Error saving HTML: {e!s}"
