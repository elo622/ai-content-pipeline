"""
pipeline_runner.py

Runs the complete AI Content Pipeline from source retrieval through
final video creation.

Pipeline:
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

Uploader and emailer tools are intentionally excluded from the core
pipeline. They can be added later as optional downstream integrations.

This file provides the automated end-to-end version of the pipeline.
Each individual stage can still be run independently for testing,
debugging, and demonstration.
"""

import datetime
import json
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

from article_fetcher import fetch_next_article
from script_creator import create_script
from visual_creator import create_visuals
from voiceover_creator import create_voiceover
from timeline import create_timeline
from video_creator import create_video


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path("workspace")

# Pipeline execution reports
REPORTS_DIR = WORKSPACE_DIR / "reports"

ERROR_LOG = REPORTS_DIR / "errors" / "error_log.txt"
LAST_RUN_LOG = REPORTS_DIR / "last_run.json"

# Number of times a failed stage may be attempted.
MAX_RETRIES = 3

# Number of visuals generated for each video.
DEFAULT_IMAGE_COUNT = 1


# ---------------------------------------------------------------------------
# Pipeline status
# ---------------------------------------------------------------------------

def create_pipeline_status() -> dict:
    """
    Create a fresh status record for each pipeline run.

    Status values may include:
        pending
        running
        success
        skipped
        failed
    """

    return {
        "article_fetcher": "pending",
        "script_creator": "pending",
        "visual_creator": "pending",
        "voiceover_creator": "pending",
        "timeline": "pending",
        "video_creator": "pending",
    }


# ---------------------------------------------------------------------------
# Logging utilities
# ---------------------------------------------------------------------------

def log_error(message: str) -> None:
    """
    Append an error message to the pipeline error log.
    """

    ERROR_LOG.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with ERROR_LOG.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"[{timestamp}] {message}\n"
        )


def save_run_log(
    pipeline_status: dict,
    final_output: Optional[str] = None
) -> None:
    """
    Save the status of the most recent pipeline run.

    Args:
        pipeline_status:
            Status of every core pipeline stage.

        final_output:
            Optional path to the completed video.
    """

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    run_record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "status": pipeline_status,
        "final_output": final_output,
    }

    with LAST_RUN_LOG.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            run_record,
            file,
            indent=2
        )


# ---------------------------------------------------------------------------
# Stage execution
# ---------------------------------------------------------------------------

def run_stage(
    stage_name: str,
    function: Callable,
    pipeline_status: dict,
    *args,
    max_retries: int = MAX_RETRIES,
    **kwargs
) -> Any:
    """
    Run a pipeline stage with retry support.

    The stage function is expected to return a useful value when successful.
    None, False, or an empty collection is treated as a failed attempt.

    Args:
        stage_name:
            Human-readable pipeline stage identifier.

        function:
            Function that executes the stage.

        pipeline_status:
            Shared status dictionary for the current pipeline run.

        *args:
            Positional arguments passed to the stage function.

        max_retries:
            Maximum number of attempts.

        **kwargs:
            Keyword arguments passed to the stage function.

    Returns:
        The stage's returned result when successful.
        Returns None after all attempts fail.
    """

    pipeline_status[stage_name] = "running"

    for attempt in range(
        1,
        max_retries + 1
    ):

        try:

            print(
                f"\n[{stage_name.upper()}] "
                f"Attempt {attempt} of {max_retries}"
            )

            result = function(
                *args,
                **kwargs
            )

            if result:
                pipeline_status[stage_name] = "success"

                print(
                    f"[{stage_name.upper()}] "
                    "Stage completed successfully."
                )

                return result

            print(
                f"[{stage_name.upper()}] "
                "Stage returned no output."
            )

        except Exception as error:

            print(
                f"[{stage_name.upper()}] "
                f"Failed: {error}"
            )

            log_error(
                f"{stage_name} attempt {attempt} failed:\n"
                f"{traceback.format_exc()}"
            )

        # Brief pause before retrying.
        if attempt < max_retries:
            time.sleep(1)

    pipeline_status[stage_name] = "failed"

    print(
        f"[{stage_name.upper()}] "
        f"Failed after {max_retries} attempts."
    )

    return None


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

def run_pipeline(
    num_images: int = DEFAULT_IMAGE_COUNT
) -> Optional[str]:
    """
    Run the complete AI Content Pipeline.

    Each stage receives the output of the previous stage directly,
    rather than searching independently for the newest file.

    Args:
        num_images:
            Number of visual assets to create for the video.

    Returns:
        Path to the completed MP4 file.
        Returns None if the pipeline stops before completion.
    """

    pipeline_status = create_pipeline_status()

    print("\n======================================")
    print("       AI CONTENT PIPELINE")
    print("======================================\n")

    # -----------------------------------------------------------------------
    # Stage 1: Retrieve source article
    # -----------------------------------------------------------------------

    article_path = run_stage(
        "article_fetcher",
        fetch_next_article,
        pipeline_status,
    )

    if not article_path:

        pipeline_status["article_fetcher"] = "skipped"

        print(
            "\n[PIPELINE] No new source article was available."
        )

        save_run_log(
            pipeline_status
        )

        return None

    # -----------------------------------------------------------------------
    # Stage 2: Create narration script
    # -----------------------------------------------------------------------

    script_path = run_stage(
        "script_creator",
        create_script,
        pipeline_status,
        article_path,
    )

    if not script_path:
        save_run_log(
            pipeline_status
        )
        return None

    # -----------------------------------------------------------------------
    # Stage 3: Create visual assets
    # -----------------------------------------------------------------------

    visual_paths = run_stage(
        "visual_creator",
        create_visuals,
        pipeline_status,
        script_path,
        num_images=num_images,
    )

    if not visual_paths:
        save_run_log(
            pipeline_status
        )
        return None

    # All visuals created for a script are stored in the same directory.
    image_dir = str(
        Path(visual_paths[0]).parent
    )

    # -----------------------------------------------------------------------
    # Stage 4: Create narration audio
    # -----------------------------------------------------------------------

    voiceover_path = run_stage(
        "voiceover_creator",
        create_voiceover,
        pipeline_status,
        script_path,
    )

    if not voiceover_path:
        save_run_log(
            pipeline_status
        )
        return None

    # -----------------------------------------------------------------------
    # Stage 5: Build media timeline
    # -----------------------------------------------------------------------

    timeline_path = run_stage(
        "timeline",
        create_timeline,
        pipeline_status,
        image_dir=image_dir,
        voiceover_path=voiceover_path,
    )

    if not timeline_path:
        save_run_log(
            pipeline_status
        )
        return None

    # -----------------------------------------------------------------------
    # Stage 6: Create final video
    # -----------------------------------------------------------------------

    video_path = run_stage(
        "video_creator",
        create_video,
        pipeline_status,
        timeline_path,
    )

    if not video_path:
        save_run_log(
            pipeline_status
        )
        return None

    # -----------------------------------------------------------------------
    # Save final pipeline report
    # -----------------------------------------------------------------------

    save_run_log(
        pipeline_status,
        final_output=video_path
    )

    print("\n======================================")
    print("          PIPELINE REPORT")
    print("======================================")

    for stage, status in pipeline_status.items():
        print(
            f"{stage:<22} {status}"
        )

    print("\n[PIPELINE] Completed successfully.")

    print(
        f"[PIPELINE] Final video: "
        f"{video_path}"
    )

    return video_path


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_pipeline()