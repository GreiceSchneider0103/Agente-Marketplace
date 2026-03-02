"""Configuration module for the YouTube Analyst agent."""

import logging
import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AgentModel(BaseModel):
    """Agent model settings."""

    name: str = Field(default="youtube_analyst")
    # Using Gemini 3.0 as default
    model: str = Field(default="gemini-3-flash-preview")


class Config(BaseSettings):
    """Configuration settings for the YouTube Analyst agent."""

    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "../.env"
        ),
        env_prefix="GOOGLE_",
        case_sensitive=True,
        extra="ignore",
    )

    agent_settings: AgentModel = Field(default=AgentModel())
    app_name: str = "youtube_analyst_app"

    # Cloud & Auth Config
    CLOUD_PROJECT: str = Field(
        default="", description="Google Cloud Project ID"
    )
    CLOUD_LOCATION: str = Field(default="global")
    GENAI_USE_VERTEXAI: str = Field(default="1")

    # YouTube Specific
    API_KEY: str = Field(
        default="", description="Google API Key for YouTube Data API"
    )

    # Original Constants (can be moved to constants.py or kept here as defaults)
    YOUTUBE_AGENT_MAX_OUTPUT_TOKENS: int = 8000
    VISUALIZATION_AGENT_MAX_OUTPUT_TOKENS: int = 30000


config = Config()
