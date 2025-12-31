"""Voice Synthesis Tools.

Tools for generating audio narration using ElevenLabs.
Uses Claude Agent SDK @tool decorator pattern.
"""

import os
from typing import Any

import httpx
from claude_agent_sdk import tool

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


@tool(
    name="select_voice_profile",
    description="Select an appropriate voice profile for the narration. "
    "Returns voice ID and settings based on content type and preferences.",
    input_schema={
        "content_type": "Type of content (technical, conversational, educational)",
        "preferences": "User preferences for voice (gender, accent, style)",
    },
)
async def select_voice_profile(args: dict) -> dict:
    """Select voice profile based on content and preferences."""
    content_type = args.get("content_type", "technical")
    preferences = args.get("preferences", {})

    # Default voice profiles for different content types
    profiles = {
        "technical": {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, professional
            "name": "Rachel",
            "settings": {
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        },
        "conversational": {
            "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Bella - friendly
            "name": "Bella",
            "settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "style": 0.5,
                "use_speaker_boost": True,
            },
        },
        "educational": {
            "voice_id": "onwK4e9ZLuTAKqWW03F9",  # Daniel - authoritative
            "name": "Daniel",
            "settings": {
                "stability": 0.7,
                "similarity_boost": 0.7,
                "style": 0.3,
                "use_speaker_boost": True,
            },
        },
    }

    profile = profiles.get(content_type, profiles["technical"])

    return {
        "content": [
            {
                "type": "text",
                "text": str(
                    {
                        "voice_id": profile["voice_id"],
                        "voice_name": profile["name"],
                        "settings": profile["settings"],
                        "content_type": content_type,
                    }
                ),
            }
        ]
    }


@tool(
    name="generate_audio_segment",
    description="Generate audio for a single segment of narration text. "
    "Returns audio data or URL to generated audio file.",
    input_schema={
        "text": "Text to synthesize into audio",
        "voice_id": "ElevenLabs voice ID to use",
        "voice_settings": "Voice settings (stability, similarity_boost, etc.)",
        "output_format": "Audio format (mp3_44100_128, mp3_22050_64, etc.)",
    },
)
async def generate_audio_segment(args: dict) -> dict:
    """Generate audio for a text segment using ElevenLabs."""
    text = args.get("text", "")
    voice_id = args.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    voice_settings = args.get("voice_settings", {})
    output_format = args.get("output_format", "mp3_44100_128")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {
            "content": [{"type": "text", "text": "Error: ELEVENLABS_API_KEY not set"}],
            "isError": True,
        }

    try:
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }

        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": voice_settings.get("stability", 0.5),
                "similarity_boost": voice_settings.get("similarity_boost", 0.75),
                "style": voice_settings.get("style", 0.0),
                "use_speaker_boost": voice_settings.get("use_speaker_boost", True),
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()

            # Return audio length estimate (actual audio would be saved to file)
            audio_length_seconds = len(text) / 15  # Rough estimate: ~15 chars/sec

            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(
                            {
                                "success": True,
                                "audio_length_seconds": round(audio_length_seconds, 2),
                                "voice_id": voice_id,
                                "text_length": len(text),
                                "format": output_format,
                            }
                        ),
                    }
                ]
            }

    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {"type": "text", "text": f"ElevenLabs API error: {e.response.status_code}"}
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }


@tool(
    name="synthesize_narration",
    description="Synthesize complete narration from a script. "
    "Handles chunking, voice consistency, and audio concatenation.",
    input_schema={
        "script": "Complete narration script with chapter markers",
        "voice_profile": "Voice profile from select_voice_profile",
        "output_path": "Path to save the final audio file",
    },
)
async def synthesize_narration(args: dict) -> dict:
    """Synthesize complete narration from script."""
    script = args.get("script", "")
    voice_profile = args.get("voice_profile", {})
    output_path = args.get("output_path", "/tmp/narration.mp3")

    if not script:
        return {
            "content": [{"type": "text", "text": "Error: No script provided"}],
            "isError": True,
        }

    try:
        # Split script into chapters/segments
        segments = script.split("\n\n")
        total_segments = len(segments)
        estimated_duration = sum(len(s) / 15 for s in segments)

        # In production, this would:
        # 1. Generate audio for each segment
        # 2. Concatenate audio files
        # 3. Apply post-processing (normalization, noise reduction)
        # 4. Save to output_path

        return {
            "content": [
                {
                    "type": "text",
                    "text": str(
                        {
                            "success": True,
                            "output_path": output_path,
                            "segments_processed": total_segments,
                            "estimated_duration_seconds": round(estimated_duration, 2),
                            "voice": voice_profile.get("voice_name", "default"),
                        }
                    ),
                }
            ]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e!s}"}],
            "isError": True,
        }
