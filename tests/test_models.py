"""Tests for SQLAlchemy models."""

import pytest

from codestory.models import (
    APIKey,
    Base,
    NarrativeStyle,
    Repository,
    Story,
    StoryChapter,
    StoryIntent,
    StoryStatus,
    User,
)


class TestModelImports:
    """Test that all models import correctly."""

    def test_base_metadata_tables(self) -> None:
        """Test that all tables are registered in Base.metadata."""
        expected_tables = {
            "users",
            "api_keys",
            "repositories",
            "stories",
            "story_chapters",
            "story_intents",
        }
        actual_tables = set(Base.metadata.tables.keys())
        assert expected_tables == actual_tables

    def test_user_model_attributes(self) -> None:
        """Test User model has expected attributes."""
        assert hasattr(User, "id")
        assert hasattr(User, "email")
        assert hasattr(User, "hashed_password")
        assert hasattr(User, "is_active")
        assert hasattr(User, "is_superuser")
        assert hasattr(User, "subscription_tier")
        assert hasattr(User, "usage_quota")
        assert hasattr(User, "preferences")
        assert hasattr(User, "created_at")
        assert hasattr(User, "updated_at")
        # Relationships
        assert hasattr(User, "stories")
        assert hasattr(User, "api_keys")

    def test_api_key_model_attributes(self) -> None:
        """Test APIKey model has expected attributes."""
        assert hasattr(APIKey, "id")
        assert hasattr(APIKey, "user_id")
        assert hasattr(APIKey, "key_hash")
        assert hasattr(APIKey, "name")
        assert hasattr(APIKey, "permissions")
        assert hasattr(APIKey, "rate_limit")
        assert hasattr(APIKey, "is_active")
        assert hasattr(APIKey, "last_used_at")
        assert hasattr(APIKey, "expires_at")
        assert hasattr(APIKey, "created_at")
        # Relationships
        assert hasattr(APIKey, "user")

    def test_repository_model_attributes(self) -> None:
        """Test Repository model has expected attributes."""
        assert hasattr(Repository, "id")
        assert hasattr(Repository, "url")
        assert hasattr(Repository, "name")
        assert hasattr(Repository, "owner")
        assert hasattr(Repository, "default_branch")
        assert hasattr(Repository, "description")
        assert hasattr(Repository, "language")
        assert hasattr(Repository, "analysis_cache")
        assert hasattr(Repository, "last_analyzed_at")
        assert hasattr(Repository, "created_at")
        # Relationships
        assert hasattr(Repository, "stories")

    def test_story_model_attributes(self) -> None:
        """Test Story model has expected attributes."""
        assert hasattr(Story, "id")
        assert hasattr(Story, "user_id")
        assert hasattr(Story, "repository_id")
        assert hasattr(Story, "intent_id")
        assert hasattr(Story, "title")
        assert hasattr(Story, "status")
        assert hasattr(Story, "narrative_style")
        assert hasattr(Story, "focus_areas")
        assert hasattr(Story, "error_message")
        assert hasattr(Story, "audio_url")
        assert hasattr(Story, "transcript")
        assert hasattr(Story, "duration_seconds")
        assert hasattr(Story, "created_at")
        assert hasattr(Story, "updated_at")
        assert hasattr(Story, "completed_at")
        # Relationships
        assert hasattr(Story, "user")
        assert hasattr(Story, "repository")
        assert hasattr(Story, "intent")
        assert hasattr(Story, "chapters")

    def test_story_chapter_model_attributes(self) -> None:
        """Test StoryChapter model has expected attributes."""
        assert hasattr(StoryChapter, "id")
        assert hasattr(StoryChapter, "story_id")
        assert hasattr(StoryChapter, "order")
        assert hasattr(StoryChapter, "title")
        assert hasattr(StoryChapter, "script")
        assert hasattr(StoryChapter, "audio_url")
        assert hasattr(StoryChapter, "start_time")
        assert hasattr(StoryChapter, "duration_seconds")
        assert hasattr(StoryChapter, "created_at")
        # Relationships
        assert hasattr(StoryChapter, "story")

    def test_story_intent_model_attributes(self) -> None:
        """Test StoryIntent model has expected attributes."""
        assert hasattr(StoryIntent, "id")
        assert hasattr(StoryIntent, "user_id")
        assert hasattr(StoryIntent, "repository_url")
        assert hasattr(StoryIntent, "conversation_history")
        assert hasattr(StoryIntent, "identified_goals")
        assert hasattr(StoryIntent, "generated_plan")
        assert hasattr(StoryIntent, "preferences")
        assert hasattr(StoryIntent, "created_at")
        assert hasattr(StoryIntent, "updated_at")
        # Relationships
        assert hasattr(StoryIntent, "story")


class TestEnums:
    """Test enum definitions."""

    def test_story_status_values(self) -> None:
        """Test StoryStatus enum values."""
        assert StoryStatus.PENDING.value == "pending"
        assert StoryStatus.ANALYZING.value == "analyzing"
        assert StoryStatus.GENERATING.value == "generating"
        assert StoryStatus.SYNTHESIZING.value == "synthesizing"
        assert StoryStatus.COMPLETE.value == "complete"
        assert StoryStatus.FAILED.value == "failed"

    def test_narrative_style_values(self) -> None:
        """Test NarrativeStyle enum values."""
        assert NarrativeStyle.TECHNICAL.value == "technical"
        assert NarrativeStyle.STORYTELLING.value == "storytelling"
        assert NarrativeStyle.EDUCATIONAL.value == "educational"
        assert NarrativeStyle.CASUAL.value == "casual"
        assert NarrativeStyle.EXECUTIVE.value == "executive"

    def test_story_status_is_str_enum(self) -> None:
        """Test StoryStatus inherits from str for JSON serialization."""
        assert isinstance(StoryStatus.PENDING, str)
        # .value gives the actual string value for JSON serialization
        assert StoryStatus.PENDING.value == "pending"

    def test_narrative_style_is_str_enum(self) -> None:
        """Test NarrativeStyle inherits from str for JSON serialization."""
        assert isinstance(NarrativeStyle.TECHNICAL, str)
        # .value gives the actual string value for JSON serialization
        assert NarrativeStyle.TECHNICAL.value == "technical"


class TestRelationships:
    """Test model relationships are correctly defined."""

    def test_user_stories_relationship(self) -> None:
        """Test User -> Stories relationship."""
        rel = User.stories.property
        assert rel.mapper.class_ == Story
        assert rel.back_populates == "user"

    def test_user_api_keys_relationship(self) -> None:
        """Test User -> APIKeys relationship."""
        rel = User.api_keys.property
        assert rel.mapper.class_ == APIKey
        assert rel.back_populates == "user"

    def test_story_chapters_relationship(self) -> None:
        """Test Story -> Chapters relationship."""
        rel = Story.chapters.property
        assert rel.mapper.class_ == StoryChapter
        assert rel.back_populates == "story"

    def test_story_repository_relationship(self) -> None:
        """Test Story -> Repository relationship."""
        rel = Story.repository.property
        assert rel.mapper.class_ == Repository
        assert rel.back_populates == "stories"

    def test_story_intent_relationship(self) -> None:
        """Test Story -> Intent relationship."""
        rel = Story.intent.property
        assert rel.mapper.class_ == StoryIntent
        assert rel.back_populates == "story"
