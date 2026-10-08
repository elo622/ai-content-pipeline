"""
timeline.py

Creates the media timeline used by the final rendering stage of the
AI Content Pipeline.

Responsibilities:
    - Locate generated visual assets.
    - Locate the corresponding voiceover.
    - Measure the voiceover duration.
    - Distribute visual assets across the narration.
    - Create a structured timeline JSON file for the renderer.

This module can be run independently or called by the full pipeline runner.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from mutagen.mp3 import MP3


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path("workspace")

# Visuals created by visual_creator.py
IMAGES_DIR = WORKSPACE_DIR / "images"

# Voiceovers created by voiceover_creator.py
VOICEOVER_DIR = WORKSPACE_DIR / "voiceovers"

# Timeline files created by this module
TIMELINE_DIR = WORKSPACE_DIR / "timelines"

# Final rendered videos will be written here by the renderer.
VIDEO_DIR = WORKSPACE_DIR / "videos"

# Default video settings.
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_image_folder() -> Optional[Path]:
    """
    Find the most recently modified image directory.

    Each script receives its own image folder from visual_creator.py.

    Returns:
        Path to the newest image directory, or None if none exist.
    """

    if not IMAGES_DIR.exists():
        return None

    folders = [
        path
        for path in IMAGES_DIR.iterdir()
        if path.is_dir()
    ]

    if not folders:
        return None

    return max(
        folders,
        key=lambda path: path.stat().st_mtime
    )


def get_latest_voiceover() -> Optional[Path]:
    """
    Find the most recently created voiceover.

    Returns:
        Path to the newest MP3 file, or None if none exist.
    """

    if not VOICEOVER_DIR.exists():
        return None

    voiceovers = list(
        VOICEOVER_DIR.glob("voiceover_*.mp3")
    )

    if not voiceovers:
        return None

    return max(
        voiceovers,
        key=lambda path: path.stat().st_mtime
    )


def get_image_files(image_dir: Path) -> list[Path]:
    """
    Return image files from a visual directory in numerical order.

    Expected naming:
        image_1.png
        image_2.png
        image_3.png

    Args:
        image_dir:
            Directory containing generated visual assets.

    Returns:
        Ordered list of image paths.
    """

    supported_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
    }

    image_files = [
        path
        for path in image_dir.iterdir()
        if path.suffix.lower() in supported_extensions
    ]

    def image_number(path: Path) -> int:
        """
        Extract the numeric portion from names such as image_3.png.
        """

        try:
            return int(path.stem.split("_")[-1])

        except ValueError:
            return 0

    return sorted(
        image_files,
        key=image_number
    )


# ---------------------------------------------------------------------------
# Timeline creation
# ---------------------------------------------------------------------------

def create_timeline(
    image_dir: Optional[str] = None,
    voiceover_path: Optional[str] = None,
) -> Optional[str]:
    """
    Create a timeline describing how visuals and audio should be assembled.

    If explicit paths are not supplied, timeline.py automatically uses
    the newest visual directory and newest voiceover in the workspace.

    Args:
        image_dir:
            Optional path to a directory containing visual assets.

        voiceover_path:
            Optional path to a specific MP3 voiceover.

    Returns:
        Path to the generated timeline JSON file.
        Returns None if timeline creation cannot be completed.
    """

    # -----------------------------------------------------------------------
    # Locate the visual assets.
    # -----------------------------------------------------------------------

    if image_dir:
        visual_dir = Path(image_dir)

    else:
        visual_dir = get_latest_image_folder()

        if visual_dir is None:
            print(
                "[TIMELINE] No image directories found in "
                "workspace/images/"
            )
            return None

    if not visual_dir.exists():
        print(
            f"[TIMELINE] Image directory not found: "
            f"{visual_dir}"
        )
        return None

    # -----------------------------------------------------------------------
    # Locate the voiceover.
    # -----------------------------------------------------------------------

    if voiceover_path:
        audio_path = Path(voiceover_path)

    else:
        audio_path = get_latest_voiceover()

        if audio_path is None:
            print(
                "[TIMELINE] No voiceovers found in "
                "workspace/voiceovers/"
            )
            return None

    if not audio_path.exists():
        print(
            f"[TIMELINE] Voiceover not found: "
            f"{audio_path}"
        )
        return None

    print(
        f"[TIMELINE] Using visuals: "
        f"{visual_dir}"
    )

    print(
        f"[TIMELINE] Using voiceover: "
        f"{audio_path.name}"
    )

    # -----------------------------------------------------------------------
    # Load visual assets.
    # -----------------------------------------------------------------------

    image_files = get_image_files(
        visual_dir
    )

    if not image_files:
        print(
            "[TIMELINE] No supported image files found."
        )
        return None

    # -----------------------------------------------------------------------
    # Measure narration duration.
    # -----------------------------------------------------------------------

    try:
        audio = MP3(audio_path)

        total_audio_duration = (
            audio.info.length
        )

    except Exception as error:
        print(
            f"[TIMELINE] Could not read voiceover duration: "
            f"{error}"
        )
        return None

    if total_audio_duration <= 0:
        print(
            "[TIMELINE] Voiceover duration is invalid."
        )
        return None

    print(
        f"[TIMELINE] Voiceover duration: "
        f"{total_audio_duration:.2f} seconds"
    )

    # -----------------------------------------------------------------------
    # Divide the narration across the available visuals.
    # -----------------------------------------------------------------------

    duration_per_image = (
        total_audio_duration /
        len(image_files)
    )

    video_clips = []

    start_time = 0.0

    for index, image_path in enumerate(
        image_files
    ):

        # Give the final visual any remaining duration so rounding does not
        # cause the visual track to end before the narration.
        if index == len(image_files) - 1:

            clip_duration = (
                total_audio_duration -
                start_time
            )

        else:
            clip_duration = (
                duration_per_image
            )

        video_clips.append(
            {
                "asset": image_path.as_posix(),
                "start": round(
                    start_time,
                    3
                ),
                "duration": round(
                    clip_duration,
                    3
                ),
            }
        )

        start_time += clip_duration

    # -----------------------------------------------------------------------
    # Create the audio track.
    # -----------------------------------------------------------------------

    audio_clip = {
        "asset": audio_path.as_posix(),
        "start": 0,
    }

    # -----------------------------------------------------------------------
    # Define the eventual rendered video path.
    # -----------------------------------------------------------------------

    VIDEO_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        VIDEO_DIR /
        f"video_{timestamp}.mp4"
    )

    # -----------------------------------------------------------------------
    # Build the timeline structure.
    # -----------------------------------------------------------------------

    timeline = {
        "output": output_path.as_posix(),

        "resolution": {
            "width": VIDEO_WIDTH,
            "height": VIDEO_HEIGHT,
        },

        "fps": VIDEO_FPS,

        "duration": round(
            total_audio_duration,
            3
        ),

        "tracks": [
            {
                "type": "video",
                "clips": video_clips,
            },
            {
                "type": "audio",
                "clips": [
                    audio_clip
                ],
            },
        ],
    }

    # -----------------------------------------------------------------------
    # Save the timeline.
    # -----------------------------------------------------------------------

    TIMELINE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    versioned_path = (
        TIMELINE_DIR /
        f"timeline_{timestamp}.json"
    )

    default_path = (
        TIMELINE_DIR /
        "timeline.json"
    )

    # Save a timestamped version for history.
    with versioned_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            timeline,
            file,
            indent=2
        )

    # Save a predictable filename for the renderer.
    with default_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            timeline,
            file,
            indent=2
        )

    print(
        f"[TIMELINE] Timeline saved: "
        f"{versioned_path}"
    )

    print(
        f"[TIMELINE] Video output: "
        f"{output_path}"
    )

    return str(
        versioned_path
    )


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    timeline_path = create_timeline()

    if timeline_path:
        print(
            f"[TIMELINE] Complete: "
            f"{timeline_path}"
        )

    else:
        print(
            "[TIMELINE] Timeline creation failed."
        )