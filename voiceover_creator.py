"""
voiceover_creator.py

Creates spoken audio from a narration script produced by script_creator.py.

Responsibilities:
    - Load a narration script from the workspace.
    - Select an appropriate voice for the content.
    - Convert the script into spoken audio using an AI speech model.
    - Save the finished voiceover for later pipeline stages.

This module can be run independently or called by the full pipeline runner.
"""

import os
import random
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Narration scripts created by script_creator.py
SCRIPTS_DIR = Path("workspace") / "scripts"

# Voiceovers created by this module
VOICEOVER_DIR = Path("workspace") / "voiceovers"

# Load the API key from the environment rather than storing it in the code.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# The speech model can be changed without modifying voiceover_creator.py.
TTS_MODEL = os.getenv(
    "OPENAI_TTS_MODEL",
    "gpt-4o-mini-tts"
)

# Optional fixed voice.
#
# If OPENAI_TTS_VOICE is configured, that voice will always be used.
# Otherwise, the module will automatically select a voice based on
# the content of the script.
TTS_VOICE = os.getenv("OPENAI_TTS_VOICE")


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured. "
        "Add it to your environment before running voiceover_creator.py."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_script_path() -> Optional[Path]:
    """
    Find the newest narration script in the workspace.

    This allows voiceover_creator.py to run independently without requiring
    a script path to be supplied manually.

    Returns:
        Path to the newest script file, or None if no scripts exist.
    """

    if not SCRIPTS_DIR.exists():
        return None

    script_files = list(SCRIPTS_DIR.glob("*.txt"))

    if not script_files:
        return None

    return max(
        script_files,
        key=lambda path: path.stat().st_mtime
    )


def load_script(script_path: Path) -> str:
    """
    Load a narration script from disk.

    Args:
        script_path:
            Path to a script created by script_creator.py.

    Returns:
        Script text with surrounding whitespace removed.
    """

    with script_path.open("r", encoding="utf-8") as file:
        return file.read().strip()


# ---------------------------------------------------------------------------
# Voice selection
# ---------------------------------------------------------------------------

def select_voice(text: str) -> str:
    """
    Select a voice based on the subject matter of the script.

    A fixed voice can be supplied through the OPENAI_TTS_VOICE environment
    variable. If no fixed voice is configured, the module chooses from a
    small group of voices appropriate to the content.

    Args:
        text:
            Narration script that will be converted to speech.

    Returns:
        Name of the selected voice.
    """

    # Allow the pipeline user to override automatic voice selection.
    if TTS_VOICE:
        return TTS_VOICE

    normalized_text = text.lower()

    # Serious or high-stakes subjects generally benefit from a more
    # restrained delivery.
    serious_terms = [
        "conflict",
        "military",
        "emergency",
        "crisis",
        "attack",
        "disaster",
        "investigation",
        "security",
        "government",
        "economy",
    ]

    # Technology-focused subjects can use a slightly more modern or
    # energetic delivery while remaining professional.
    technology_terms = [
        "artificial intelligence",
        "ai",
        "technology",
        "cybersecurity",
        "software",
        "robot",
        "robotics",
        "chip",
        "computer",
        "startup",
    ]

    if any(term in normalized_text for term in serious_terms):
        voices = [
            "onyx",
            "cedar",
            "sage",
            "marin",
            "nova",
        ]

    elif any(term in normalized_text for term in technology_terms):
        voices = [
            "nova",
            "coral",
            "marin",
            "cedar",
            "ash",
        ]

    else:
        voices = [
            "nova",
            "onyx",
            "coral",
            "cedar",
            "marin",
            "sage",
        ]

    return random.choice(voices)


# ---------------------------------------------------------------------------
# Voiceover creation
# ---------------------------------------------------------------------------

def create_voiceover(
    script_path: Optional[str] = None
) -> Optional[str]:
    """
    Create spoken audio from a narration script.

    If no script path is supplied, voiceover_creator.py automatically uses
    the newest script available in workspace/scripts/.

    Args:
        script_path:
            Optional path to a specific narration script.

    Returns:
        Path to the created MP3 file.
        Returns None if voiceover creation cannot be completed.
    """

    # -----------------------------------------------------------------------
    # Locate the narration script.
    # -----------------------------------------------------------------------

    if script_path:
        source_path = Path(script_path)

    else:
        source_path = get_latest_script_path()

        if source_path is None:
            print(
                "[VOICEOVER] No scripts found in "
                "workspace/scripts/"
            )
            return None

    if not source_path.exists():
        print(f"[VOICEOVER] Script not found: {source_path}")
        return None

    # -----------------------------------------------------------------------
    # Load the narration.
    # -----------------------------------------------------------------------

    script_text = load_script(source_path)

    if not script_text:
        print("[VOICEOVER] Script is empty.")
        return None

    print(
        f"[VOICEOVER] Creating voiceover from: "
        f"{source_path.name}"
    )

    # -----------------------------------------------------------------------
    # Select the narration voice.
    # -----------------------------------------------------------------------

    voice = select_voice(script_text)

    print(f"[VOICEOVER] Selected voice: {voice}")

    # -----------------------------------------------------------------------
    # Prepare the output file.
    # -----------------------------------------------------------------------

    VOICEOVER_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        VOICEOVER_DIR /
        f"voiceover_{timestamp}.mp3"
    )

    # -----------------------------------------------------------------------
    # Generate the spoken narration.
    # -----------------------------------------------------------------------

    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=voice,
            input=script_text,
            instructions=(
                "Read this as professional informational narration. "
                "Use a calm, neutral, clear, measured, and natural delivery. "
                "Do not sound dramatic, theatrical, promotional, "
                "or overly conversational."
            ),
        )

        # Write the streamed audio response to disk.
        with output_path.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

    except Exception as error:
        print(
            f"[VOICEOVER] Voiceover creation failed: "
            f"{error}"
        )
        return None

    print(
        f"[VOICEOVER] Voiceover saved: "
        f"{output_path}"
    )

    return str(output_path)


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    voiceover = create_voiceover()

    if voiceover:
        print(
            f"[VOICEOVER] Complete: "
            f"{voiceover}"
        )

    else:
        print(
            "[VOICEOVER] No voiceover was created."
        )