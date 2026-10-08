"""
script_creator.py

Creates a concise narration script from a source article produced by
the article_fetcher stage of the AI Content Pipeline.

Responsibilities:
    - Load a source article from the workspace.
    - Send the source material to an AI model.
    - Create a neutral, fact-based narration script.
    - Save the finished script for later pipeline stages.

This module can be run independently or called by the full pipeline runner.
"""

import datetime
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Source articles created by article_fetcher.py
ARTICLE_DIR = Path("workspace") / "source_articles"

# Finished scripts created by this module
SCRIPTS_DIR = Path("workspace") / "scripts"

# Load the API key from the environment rather than storing it in the code.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# The model can be changed through an environment variable without
# modifying the script creator itself.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured. "
        "Add it to your environment before running script_creator.py."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_article_path() -> Optional[Path]:
    """
    Find the newest source article in the workspace.

    This allows script_creator.py to run independently without requiring
    an article path to be provided manually.

    Returns:
        Path to the newest source article, or None if no articles exist.
    """

    if not ARTICLE_DIR.exists():
        return None

    article_files = list(ARTICLE_DIR.glob("*.txt"))

    if not article_files:
        return None

    return max(
        article_files,
        key=lambda path: path.stat().st_mtime
    )


def load_article(article_path: Path) -> str:
    """
    Load source article text from disk.

    Args:
        article_path:
            Path to an article created by article_fetcher.py.

    Returns:
        The source article as a cleaned string.
    """

    with article_path.open("r", encoding="utf-8") as file:
        return file.read().strip()


# ---------------------------------------------------------------------------
# Prompt creation
# ---------------------------------------------------------------------------

def build_script_prompt(article_text: str) -> str:
    """
    Build the instructions used by the AI model to create the script.

    The model is instructed to remain grounded in the supplied source
    material and avoid adding unsupported information.

    Args:
        article_text:
            Source material retrieved by article_fetcher.py.

    Returns:
        Complete prompt for script creation.
    """

    return f"""
Convert the supplied source material into concise narration for a
short-form informational video.

STYLE

- Report the information directly using clear, neutral, professional language.
- Lead with the most important fact.
- Keep the narration concise.
- Use only the words necessary to communicate the available information.
- End when the available facts run out.
- No conclusion is required.

ACCURACY

- Use only facts explicitly supported by the supplied source material.
- Never invent, assume, infer, or speculate.
- Preserve attribution when information is presented as a claim or report.
- Missing information is not information. Do not fill gaps.
- Preserve names, numbers, organizations, locations, and factual details.

WRITING

- Write the narration naturally rather than copying source sentence structure.
- Every sentence should communicate useful factual information.
- Do not add analysis, opinions, implications, takeaways, filler,
  engagement hooks, or calls to action.

OUTPUT

Return only the finished narration.
Do not include headings, explanations, notes, or formatting instructions.

SOURCE MATERIAL

{article_text}
""".strip()


# ---------------------------------------------------------------------------
# Script creation
# ---------------------------------------------------------------------------

def create_script(
    article_path: Optional[str] = None
) -> Optional[str]:
    """
    Create a narration script from a source article.

    If no article path is supplied, script_creator.py automatically uses
    the newest article available in workspace/source_articles/.

    Args:
        article_path:
            Optional path to a specific source article.

    Returns:
        Path to the newly created script file.
        Returns None if script creation cannot be completed.
    """

    # -----------------------------------------------------------------------
    # Locate the source article.
    # -----------------------------------------------------------------------

    if article_path:
        source_path = Path(article_path)

    else:
        source_path = get_latest_article_path()

        if source_path is None:
            print(
                "[SCRIPT] No source articles found in "
                "workspace/source_articles/"
            )
            return None

    if not source_path.exists():
        print(f"[SCRIPT] Source article not found: {source_path}")
        return None

    # -----------------------------------------------------------------------
    # Load the source material.
    # -----------------------------------------------------------------------

    article_text = load_article(source_path)

    if not article_text:
        print("[SCRIPT] Source article is empty.")
        return None

    print(
        f"[SCRIPT] Creating script from: "
        f"{source_path.name}"
    )

    # Build the prompt using the source article.
    prompt = build_script_prompt(article_text)

    # -----------------------------------------------------------------------
    # Request the script from the AI model.
    # -----------------------------------------------------------------------

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
        )

        script = response.choices[0].message.content.strip()

    except Exception as error:
        print(f"[SCRIPT] Script creation failed: {error}")
        return None

    if not script:
        print("[SCRIPT] AI model returned an empty script.")
        return None

    # -----------------------------------------------------------------------
    # Save the finished script.
    # -----------------------------------------------------------------------

    SCRIPTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        SCRIPTS_DIR /
        f"script_{timestamp}.txt"
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:
        file.write(script + "\n")

    print(
        f"[SCRIPT] Script saved: "
        f"{output_path}"
    )

    return str(output_path)


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    created_script = create_script()

    if created_script:
        print(
            f"[SCRIPT] Complete: "
            f"{created_script}"
        )

    else:
        print(
            "[SCRIPT] No script was created."
        )