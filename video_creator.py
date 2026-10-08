"""
video_creator.py

Creates the final video from a timeline produced by timeline.py.

Responsibilities:
    - Load a timeline describing visual and audio assets.
    - Prepare the image sequence for FFmpeg.
    - Combine generated visuals with the voiceover.
    - Render the completed video to the configured output path.

This module can be run independently or called by the full pipeline runner.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path("workspace")

# Timeline files created by timeline.py
TIMELINE_DIR = WORKSPACE_DIR / "timelines"

# Temporary files used during video creation
TEMP_DIR = WORKSPACE_DIR / "temp"


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_timeline_path() -> Optional[Path]:
    """
    Find the newest timestamped timeline in the workspace.

    This allows video_creator.py to run independently without requiring
    a timeline path to be supplied manually.

    Returns:
        Path to the newest timeline file, or None if none exist.
    """

    if not TIMELINE_DIR.exists():
        return None

    timeline_files = list(
        TIMELINE_DIR.glob("timeline_*.json")
    )

    if not timeline_files:
        return None

    return max(
        timeline_files,
        key=lambda path: path.stat().st_mtime
    )


def load_timeline(timeline_path: Path) -> dict:
    """
    Load timeline data from disk.

    Args:
        timeline_path:
            Path to a JSON timeline created by timeline.py.

    Returns:
        Parsed timeline dictionary.
    """

    with timeline_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ---------------------------------------------------------------------------
# FFmpeg utilities
# ---------------------------------------------------------------------------

def create_concat_file(
    video_clips: list,
    concat_path: Path
) -> None:
    """
    Create the temporary FFmpeg concat file used to sequence images.

    Each image is assigned the duration specified by timeline.py.

    Args:
        video_clips:
            Video clip definitions from the timeline.

        concat_path:
            Temporary file path used by FFmpeg.
    """

    concat_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with concat_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        for clip in video_clips:

            asset_path = Path(
                clip["asset"]
            ).resolve().as_posix()

            duration = clip["duration"]

            file.write(
                f"file '{asset_path}'\n"
            )

            file.write(
                f"duration {duration}\n"
            )

        # FFmpeg's concat demuxer requires the final image to be repeated
        # so that the duration of the last frame is respected.
        last_asset = Path(
            video_clips[-1]["asset"]
        ).resolve().as_posix()

        file.write(
            f"file '{last_asset}'\n"
        )


# ---------------------------------------------------------------------------
# Video creation
# ---------------------------------------------------------------------------

def create_video(
    timeline_path: Optional[str] = None
) -> Optional[str]:
    """
    Create the final video from a generated timeline.

    If no timeline path is supplied, video_creator.py automatically uses
    the newest timestamped timeline in workspace/timelines/.

    Args:
        timeline_path:
            Optional path to a specific timeline JSON file.

    Returns:
        Path to the completed MP4 file.
        Returns None if video creation cannot be completed.
    """

    # -----------------------------------------------------------------------
    # Locate the timeline.
    # -----------------------------------------------------------------------

    if timeline_path:
        source_path = Path(timeline_path)

    else:
        source_path = get_latest_timeline_path()

        if source_path is None:
            print(
                "[VIDEO] No timelines found in "
                "workspace/timelines/"
            )
            return None

    if not source_path.exists():
        print(
            f"[VIDEO] Timeline not found: "
            f"{source_path}"
        )
        return None

    print(
        f"[VIDEO] Using timeline: "
        f"{source_path.name}"
    )

    # -----------------------------------------------------------------------
    # Load and validate timeline data.
    # -----------------------------------------------------------------------

    try:
        timeline = load_timeline(
            source_path
        )

        output_path = Path(
            timeline["output"]
        )

        video_clips = (
            timeline["tracks"][0]["clips"]
        )

        audio_path = Path(
            timeline["tracks"][1]["clips"][0]["asset"]
        )

        resolution = timeline.get(
            "resolution",
            {
                "width": 1080,
                "height": 1920,
            }
        )

        fps = timeline.get(
            "fps",
            30
        )

    except (
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError
    ) as error:

        print(
            f"[VIDEO] Invalid timeline: "
            f"{error}"
        )

        return None

    if not video_clips:
        print(
            "[VIDEO] Timeline contains no visual clips."
        )
        return None

    if not audio_path.exists():
        print(
            f"[VIDEO] Voiceover not found: "
            f"{audio_path}"
        )
        return None

    # -----------------------------------------------------------------------
    # Validate visual assets.
    # -----------------------------------------------------------------------

    for clip in video_clips:

        image_path = Path(
            clip["asset"]
        )

        if not image_path.exists():
            print(
                f"[VIDEO] Visual asset not found: "
                f"{image_path}"
            )
            return None

    # -----------------------------------------------------------------------
    # Prepare output and temporary directories.
    # -----------------------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    concat_path = (
        TEMP_DIR /
        "image_sequence.txt"
    )

    create_concat_file(
        video_clips,
        concat_path
    )

    width = resolution.get(
        "width",
        1080
    )

    height = resolution.get(
        "height",
        1920
    )

    # -----------------------------------------------------------------------
    # Build the FFmpeg command.
    # -----------------------------------------------------------------------

    ffmpeg_command = [
        "ffmpeg",
        "-y",

        # Image sequence.
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),

        # Narration audio.
        "-i",
        str(audio_path),

        # Stop rendering when the shortest media stream finishes.
        "-shortest",

        # Match the requested output resolution.
        "-vf",
        (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        ),

        # Output frame rate.
        "-r",
        str(fps),

        # Video encoding.
        "-c:v",
        "libx264",

        # Widely compatible pixel format.
        "-pix_fmt",
        "yuv420p",

        # Audio encoding.
        "-c:a",
        "aac",

        # Improve playback compatibility for web/video platforms.
        "-movflags",
        "+faststart",

        str(output_path),
    ]

    # -----------------------------------------------------------------------
    # Render the final video.
    # -----------------------------------------------------------------------

    print(
        f"[VIDEO] Creating video: "
        f"{output_path}"
    )

    try:
        subprocess.run(
            ffmpeg_command,
            check=True,
        )

    except FileNotFoundError:

        print(
            "[VIDEO] FFmpeg was not found. "
            "Make sure FFmpeg is installed and available in PATH."
        )

        return None

    except subprocess.CalledProcessError as error:

        print(
            f"[VIDEO] FFmpeg rendering failed: "
            f"{error}"
        )

        return None

    finally:

        # The concat file is only needed while FFmpeg is running.
        if concat_path.exists():
            concat_path.unlink()

    print(
        f"[VIDEO] Video created successfully: "
        f"{output_path}"
    )

    return str(output_path)


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    video = create_video()

    if video:
        print(
            f"[VIDEO] Complete: "
            f"{video}"
        )

    else:
        print(
            "[VIDEO] Video creation failed."
        )