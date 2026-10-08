"""
visual_creator.py

Creates visual assets from a narration script produced by script_creator.py.

Responsibilities:
    - Load a narration script from the workspace.
    - Build a visual-generation prompt from the script.
    - Generate one or more supporting images with an AI image model.
    - Save the images for later stages of the AI Content Pipeline.

This module can be run independently or called by the full pipeline runner.
"""

import base64
import os
from pathlib import Path
from typing import List, Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Narration scripts created by script_creator.py
SCRIPTS_DIR = Path("workspace") / "scripts"

# Visual assets created by this module
IMAGES_DIR = Path("workspace") / "images"

# Load credentials from the environment rather than storing them in code.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# The image model can be changed without modifying visual_creator.py.
IMAGE_MODEL = os.getenv(
    "OPENAI_IMAGE_MODEL",
    "gpt-image-2.5-flare"
)

# Default image-generation settings.
IMAGE_SIZE = "1024x1536"
IMAGE_QUALITY = "medium"


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured. "
        "Add it to your environment before running visual_creator.py."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_script_path() -> Optional[Path]:
    """
    Find the newest narration script in the workspace.

    This allows visual_creator.py to run independently without requiring
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
# Visual prompt creation
# ---------------------------------------------------------------------------

def build_visual_prompt(script_text: str) -> str:
    """
    Build the instructions used by the image model.

    The visual should represent the supplied script while avoiding
    unsupported or invented details.

    Args:
        script_text:
            Narration created by script_creator.py.

    Returns:
        Complete prompt for visual generation.
    """

    return f"""
Create a realistic editorial-style image that visually supports the
provided informational script.

SCRIPT

{script_text}

GOAL

Represent the central subject, location, institution, technology,
object, or event described in the script as clearly as possible.

VISUAL STYLE

- Professional editorial imagery
- Realistic and detailed
- Clean, modern composition
- Natural lighting
- Believable environments
- Strong visual clarity
- Vertical composition suitable for short-form video
- Serious and professional presentation

SCENE SELECTION

- Identify the most important visual subject in the script.
- Build the composition around that subject.
- Prefer concrete visual elements supported by the script.
- Use relevant environments, architecture, technology, objects,
  locations, or other contextual elements when appropriate.
- Keep the main subject immediately understandable.
- Adapt the composition naturally to the supplied content.

ACCURACY

- Do not invent events, actions, locations, people, damage, meetings,
  protests, weapons, or other details not supported by the script.
- Do not exaggerate the scale or intensity of events.
- Do not present uncertain or unverified information as confirmed.
- Avoid unnecessary symbolism when a direct representation is possible.
- If visual information is limited, create a restrained representation
  rather than inventing a dramatic scene.

TONE

- Neutral
- Serious
- Informative
- Appropriate to the subject
- Never sensational for its own sake

TEXT

- Do not include text in the image.

STRICT RULES

- No logos
- No watermarks
- No UI elements
- No social-media graphics
- No captions
- No headlines
- No random letters or numbers
- No "Breaking News" graphics

OUTPUT

Create a clean, realistic vertical visual that supports the supplied
script without introducing unsupported information.
""".strip()


# ---------------------------------------------------------------------------
# Individual image creation
# ---------------------------------------------------------------------------

def create_image(
    script_text: str,
    output_path: Path
) -> Optional[str]:
    """
    Create and save a single image from the supplied script.

    Args:
        script_text:
            Narration used to guide image generation.

        output_path:
            File path where the generated image will be stored.

    Returns:
        Path to the generated image if successful.
        Returns None if image creation fails.
    """

    visual_prompt = build_visual_prompt(script_text)

    print(f"[VISUAL] Creating image: {output_path.name}")

    try:
        response = client.images.generate(
            model=IMAGE_MODEL,
            prompt=visual_prompt,
            size=IMAGE_SIZE,
            quality=IMAGE_QUALITY,
            n=1,
        )

        image_b64 = response.data[0].b64_json

        if not image_b64:
            print("[VISUAL] Image model returned no image data.")
            return None

        image_data = base64.b64decode(image_b64)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with output_path.open("wb") as file:
            file.write(image_data)

        print(f"[VISUAL] Image saved: {output_path}")

        return str(output_path)

    except Exception as error:
        print(f"[VISUAL] Image creation failed: {error}")
        return None


# ---------------------------------------------------------------------------
# Visual creation
# ---------------------------------------------------------------------------

def create_visuals(
    script_path: Optional[str] = None,
    num_images: int = 1
) -> List[str]:
    """
    Create one or more visual assets from a narration script.

    If no script path is supplied, visual_creator.py automatically uses
    the newest script available in workspace/scripts/.

    Args:
        script_path:
            Optional path to a specific narration script.

        num_images:
            Number of images to create.

    Returns:
        List containing the paths of successfully created images.
    """

    # -----------------------------------------------------------------------
    # Validate requested image count.
    # -----------------------------------------------------------------------

    if num_images < 1:
        raise ValueError("num_images must be at least 1.")

    # -----------------------------------------------------------------------
    # Locate the narration script.
    # -----------------------------------------------------------------------

    if script_path:
        source_path = Path(script_path)

    else:
        source_path = get_latest_script_path()

        if source_path is None:
            print(
                "[VISUAL] No scripts found in "
                "workspace/scripts/"
            )
            return []

    if not source_path.exists():
        print(f"[VISUAL] Script not found: {source_path}")
        return []

    # -----------------------------------------------------------------------
    # Load the narration.
    # -----------------------------------------------------------------------

    script_text = load_script(source_path)

    if not script_text:
        print("[VISUAL] Script is empty.")
        return []

    print(
        f"[VISUAL] Creating visuals from: "
        f"{source_path.name}"
    )

    # -----------------------------------------------------------------------
    # Create a dedicated image directory for this script.
    # -----------------------------------------------------------------------

    script_name = source_path.stem

    output_dir = IMAGES_DIR / script_name

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"[VISUAL] Output directory: {output_dir}")

    # -----------------------------------------------------------------------
    # Generate the requested visual assets.
    # -----------------------------------------------------------------------

    created_images: List[str] = []

    for index in range(1, num_images + 1):

        image_path = output_dir / f"image_{index}.png"

        created_path = create_image(
            script_text,
            image_path
        )

        if created_path:
            created_images.append(created_path)

    # -----------------------------------------------------------------------
    # Confirm that at least one visual was created.
    # -----------------------------------------------------------------------

    if not created_images:
        print("[VISUAL] No images were successfully created.")
        return []

    print(
        f"[VISUAL] Complete: "
        f"{len(created_images)} image(s) created."
    )

    return created_images


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    images = create_visuals()

    if images:
        print("[VISUAL] Visual creation complete.")

        for image in images:
            print(f"[VISUAL] {image}")

    else:
        print("[VISUAL] Visual creation failed.")