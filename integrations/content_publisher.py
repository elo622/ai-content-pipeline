"""
content_publisher.py

Optional publishing integration for the AI Content Pipeline.

Responsibilities:
    - Locate or accept a completed video.
    - Locate or accept the script associated with that video.
    - Generate publishing metadata.
    - Load the selected publishing provider.
    - Hand the completed content package to that provider.
    - Record successful publishing activity.

This module is NOT required by the core AI Content Pipeline.

Core pipeline:
    article_fetcher
        ↓
    script_creator
        ↓
    visual_creator
        ↓
    voiceover_creator
        ↓
    timeline
        ↓
    video_creator
        ↓
    Final MP4

Optional:
    Final MP4
        ↓
    content_publisher.py
        ↓
    User-selected publishing provider
"""

import datetime
import importlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path("workspace")

VIDEO_DIR = WORKSPACE_DIR / "videos"
SCRIPT_DIR = WORKSPACE_DIR / "scripts"
REPORTS_DIR = WORKSPACE_DIR / "reports"

PUBLISH_LOG = (
    REPORTS_DIR /
    "publishing" /
    "publish_log.txt"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

# The metadata model can be changed without modifying this file.
METADATA_MODEL = os.getenv(
    "OPENAI_METADATA_MODEL",
    "gpt-4o-mini"
)


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured. "
        "Add it to your environment before running content_publisher.py."
    )

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_video_path() -> Optional[Path]:
    """
    Find the newest completed MP4 produced by video_creator.py.

    Returns:
        Path to the newest video, or None if no videos exist.
    """

    if not VIDEO_DIR.exists():
        return None

    videos = list(
        VIDEO_DIR.glob("video_*.mp4")
    )

    if not videos:
        return None

    return max(
        videos,
        key=lambda path: path.stat().st_mtime
    )


def get_latest_script_path() -> Optional[Path]:
    """
    Find the newest narration script produced by script_creator.py.

    Returns:
        Path to the newest script, or None if no scripts exist.
    """

    if not SCRIPT_DIR.exists():
        return None

    scripts = list(
        SCRIPT_DIR.glob("script_*.txt")
    )

    if not scripts:
        return None

    return max(
        scripts,
        key=lambda path: path.stat().st_mtime
    )


def load_script(
    script_path: Path
) -> str:
    """
    Load a narration script from disk.
    """

    with script_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return file.read().strip()


# ---------------------------------------------------------------------------
# Metadata generation
# ---------------------------------------------------------------------------

def clean_metadata_line(
    line: str
) -> str:
    """
    Remove unnecessary labels and surrounding quotation marks.
    """

    line = line.strip()

    lower_line = line.lower()

    if (
        lower_line.startswith("title:")
        or lower_line.startswith("description:")
    ):
        line = line.split(
            ":",
            1
        )[1].strip()

    if (
        len(line) >= 2
        and line[0] == line[-1]
        and line[0] in {'"', "'"}
    ):
        line = line[1:-1].strip()

    return line


def generate_title_and_description(
    script_path: str
) -> Tuple[str, str]:
    """
    Generate general publishing metadata from a narration script.

    The metadata is intentionally platform-neutral so individual provider
    integrations can adapt it to their own requirements.

    Args:
        script_path:
            Path to the narration script.

    Returns:
        Tuple containing:
            title
            description
    """

    source_path = Path(
        script_path
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Script not found: {source_path}"
        )

    script_text = load_script(
        source_path
    )

    if not script_text:
        raise ValueError(
            "Script is empty."
        )

    prompt = f"""
Create publishing metadata for the supplied informational video.

SCRIPT

\"\"\"
{script_text}
\"\"\"

TITLE

- Clearly state the subject of the video.
- Use neutral, professional language.
- Include important people, organizations, technologies,
  products, locations, or events when relevant.
- Keep the title concise.
- Do not use misleading clickbait.
- Do not exaggerate.
- Do not add information not present in the script.

DESCRIPTION

- Write one concise sentence.
- Summarize the content directly.
- Use only information supported by the script.
- Do not add commentary or opinion.
- Do not include a call to action.

OUTPUT

Return exactly two lines.

Line 1: title
Line 2: description

Do not label the lines.
Do not use hashtags.
Do not use emojis.
""".strip()

    response = client.chat.completions.create(
        model=METADATA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    raw_output = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    lines = [
        clean_metadata_line(line)
        for line in raw_output.splitlines()
        if line.strip()
    ]

    title = (
        lines[0]
        if lines
        else "Generated Video"
    )

    description = (
        lines[1]
        if len(lines) > 1
        else ""
    )

    return (
        title,
        description
    )


def generate_tags(
    script_path: str,
    max_tags: int = 8
) -> List[str]:
    """
    Generate platform-neutral metadata tags.

    Args:
        script_path:
            Path to the narration script.

        max_tags:
            Maximum number of tags to return.

    Returns:
        Ordered list of unique tags.
    """

    source_path = Path(
        script_path
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Script not found: {source_path}"
        )

    script_text = load_script(
        source_path
    )

    prompt = f"""
Generate metadata tags for the supplied informational video.

SCRIPT

\"\"\"
{script_text}
\"\"\"

Return up to {max_tags} accurate, content-specific tags.

Useful tags may include:

- people
- companies
- organizations
- technologies
- locations
- products
- subjects
- specific events

RULES

- Every tag must be supported by the script.
- Do not invent missing information.
- Avoid generic tags such as viral, trending, or video.
- Do not use hashtags.
- Do not create duplicates.
- Use between 1 and 4 words per tag.

Return only a JSON array of strings.
""".strip()

    response = client.chat.completions.create(
        model=METADATA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    raw_output = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    def clean_tag(
        tag: str
    ) -> str:
        """
        Normalize generated metadata tags.
        """

        tag = tag.strip()
        tag = tag.strip('"')
        tag = tag.strip("'")
        tag = tag.lstrip("#")

        return re.sub(
            r"\s+",
            " ",
            tag
        )

    tags: List[str] = []

    try:
        parsed = json.loads(
            raw_output
        )

        if isinstance(
            parsed,
            list
        ):
            tags = [
                clean_tag(tag)
                for tag in parsed
                if isinstance(tag, str)
            ]

    except json.JSONDecodeError:

        candidates = re.findall(
            r'"([^"]+)"',
            raw_output
        )

        if not candidates:
            candidates = re.split(
                r"[\n,]+",
                raw_output
            )

        tags = [
            clean_tag(tag)
            for tag in candidates
            if clean_tag(tag)
        ]

    # Remove duplicates while preserving ordering.
    seen = set()
    final_tags = []

    for tag in tags:

        normalized = tag.lower()

        if (
            normalized
            and normalized not in seen
        ):
            seen.add(
                normalized
            )

            final_tags.append(
                tag
            )

    return final_tags[:max_tags]


# ---------------------------------------------------------------------------
# Provider loading
# ---------------------------------------------------------------------------

def load_provider(
    provider_name: str
):
    """
    Dynamically load a publishing provider.

    Provider modules should be placed inside:

        integrations/providers/

    Example:

        integrations/providers/youtube.py
        integrations/providers/webhook.py
        integrations/providers/custom_api.py

    Each provider must expose a function named:

        publish(...)

    Args:
        provider_name:
            Name of the provider module.

    Returns:
        Imported provider module.
    """

    module_name = (
        f"integrations.providers."
        f"{provider_name}"
    )

    try:
        provider = importlib.import_module(
            module_name
        )

    except ImportError as error:

        raise RuntimeError(
            f"Publishing provider '{provider_name}' "
            f"could not be loaded."
        ) from error

    if not hasattr(
        provider,
        "publish"
    ):
        raise RuntimeError(
            f"Publishing provider '{provider_name}' "
            "does not define a publish() function."
        )

    return provider


# ---------------------------------------------------------------------------
# Publishing log
# ---------------------------------------------------------------------------

def log_publish(
    provider_name: str,
    title: str,
    video_path: str,
    result: Any
) -> None:
    """
    Record a successful publishing operation.
    """

    PUBLISH_LOG.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with PUBLISH_LOG.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"{timestamp} | "
            f"{provider_name} | "
            f"{title.strip()} | "
            f"{Path(video_path).name} | "
            f"{result}\n"
        )


# ---------------------------------------------------------------------------
# Content package creation
# ---------------------------------------------------------------------------

def create_content_package(
    video_path: str,
    script_path: str
) -> Dict[str, Any]:
    """
    Build a platform-neutral content package.

    A publishing provider receives this package and decides how to
    translate it into the requirements of its own API.

    Args:
        video_path:
            Path to the completed video.

        script_path:
            Path to the narration script.

    Returns:
        Dictionary containing the video and generated metadata.
    """

    title, description = (
        generate_title_and_description(
            script_path
        )
    )

    tags = generate_tags(
        script_path
    )

    return {
        "video_path": video_path,
        "script_path": script_path,
        "title": title,
        "description": description,
        "tags": tags,
    }


# ---------------------------------------------------------------------------
# Publishing workflow
# ---------------------------------------------------------------------------

def publish_content(
    provider_name: str,
    video_path: Optional[str] = None,
    script_path: Optional[str] = None,
    **provider_options
):
    """
    Publish completed content using a selected provider integration.

    The core publishing workflow does not know how individual platforms
    authenticate or upload files. Those responsibilities belong to the
    provider module.

    Args:
        provider_name:
            Publishing provider to use.

            Examples:
                youtube
                webhook
                custom_api

        video_path:
            Optional path to a completed MP4.

        script_path:
            Optional path to the associated narration script.

        **provider_options:
            Additional settings passed directly to the selected provider.

    Returns:
        Whatever result is returned by the provider.
    """

    # -----------------------------------------------------------------------
    # Locate completed video.
    # -----------------------------------------------------------------------

    if video_path:
        final_video = Path(
            video_path
        )

    else:
        final_video = (
            get_latest_video_path()
        )

    if (
        final_video is None
        or not final_video.exists()
    ):

        print(
            "[PUBLISH] No completed video found."
        )

        return None

    # -----------------------------------------------------------------------
    # Locate narration script.
    # -----------------------------------------------------------------------

    if script_path:
        source_script = Path(
            script_path
        )

    else:
        source_script = (
            get_latest_script_path()
        )

    if (
        source_script is None
        or not source_script.exists()
    ):

        print(
            "[PUBLISH] No script found."
        )

        return None

    # -----------------------------------------------------------------------
    # Build publishing metadata.
    # -----------------------------------------------------------------------

    print(
        "[PUBLISH] Preparing content package..."
    )

    content_package = (
        create_content_package(
            video_path=str(final_video),
            script_path=str(source_script),
        )
    )

    print(
        f"[PUBLISH] Title: "
        f"{content_package['title']}"
    )

    # -----------------------------------------------------------------------
    # Load selected publishing provider.
    # -----------------------------------------------------------------------

    print(
        f"[PUBLISH] Loading provider: "
        f"{provider_name}"
    )

    provider = load_provider(
        provider_name
    )

    # -----------------------------------------------------------------------
    # Hand content to the provider.
    # -----------------------------------------------------------------------

    print(
        f"[PUBLISH] Publishing with "
        f"{provider_name}..."
    )

    result = provider.publish(
        content_package=content_package,
        **provider_options
    )

    if result is None:

        print(
            "[PUBLISH] Provider returned no result."
        )

        return None

    # -----------------------------------------------------------------------
    # Record successful publishing activity.
    # -----------------------------------------------------------------------

    log_publish(
        provider_name=provider_name,
        title=content_package["title"],
        video_path=str(final_video),
        result=result,
    )

    print(
        "[PUBLISH] Publishing complete."
    )

    return result


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print(
        "content_publisher.py requires a publishing provider."
    )

    print(
        "Example usage:"
    )

    print(
        'publish_content("youtube")'
    )