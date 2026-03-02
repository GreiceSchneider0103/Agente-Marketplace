import os

from google import genai
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

from .config import config
from .tools import (
    analyze_sentiment_heuristic,
    calculate_engagement_metrics,
    calculate_match_score,
    get_channel_details,
    get_current_date_time,
    get_date_range,
    get_video_comments,
    get_video_details,
    render_html,
    search_youtube,
)
from .utils import load_prompt
from .visualization_agent import visualization_agent

youtube_agent = Agent(
    model=config.agent_settings.model,
    name="youtube_agent",
    description="Agent for YouTube analysis and data retrieval",
    instruction=load_prompt(os.path.dirname(__file__), "youtube_agent.txt"),
    sub_agents=[visualization_agent],
    tools=[
        search_youtube,
        get_video_details,
        get_channel_details,
        get_video_comments,
        calculate_engagement_metrics,
        calculate_match_score,
        analyze_sentiment_heuristic,
        get_current_date_time,
        get_date_range,
        render_html,
        load_artifacts,
    ],
    generate_content_config=genai.types.GenerateContentConfig(
        max_output_tokens=config.YOUTUBE_AGENT_MAX_OUTPUT_TOKENS,
    ),
)

root_agent = youtube_agent
