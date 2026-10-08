"""
email_delivery.py

Optional email-delivery integration for the AI Content Pipeline.

Responsibilities:
    - Locate or accept completed pipeline assets.
    - Authenticate with an email provider.
    - Package the video, visual, and script as attachments.
    - Deliver the completed content package by email.

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
    Final MP4 + supporting assets
        ↓
    email_delivery.py
"""

import base64
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path("workspace")

VIDEO_DIR = WORKSPACE_DIR / "videos"
IMAGE_DIR = WORKSPACE_DIR / "images"
SCRIPT_DIR = WORKSPACE_DIR / "scripts"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

CLIENT_SECRET_FILE = Path("client_secrets.json")
TOKEN_FILE = Path("gmail_token.json")

# Optional defaults for standalone use.
DEFAULT_RECIPIENT = os.getenv("DELIVERY_EMAIL")
DEFAULT_SUBJECT = os.getenv(
    "DELIVERY_SUBJECT",
    "AI Content Pipeline Output"
)


# ---------------------------------------------------------------------------
# Gmail authentication
# ---------------------------------------------------------------------------

def authenticate_email():
    """
    Authenticate with Gmail using OAuth.

    Existing credentials are reused and refreshed when possible.
    If no valid credentials exist, browser authorization is requested.

    Returns:
        Authenticated Gmail API service.
    """

    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE),
            SCOPES
        )

    if not credentials or not credentials.valid:

        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
            credentials.refresh(
                Request()
            )

        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    "client_secrets.json was not found."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE),
                SCOPES
            )

            credentials = flow.run_local_server(
                port=0
            )

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_latest_video_path() -> Optional[Path]:
    """
    Find the newest video created by video_creator.py.
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


def get_latest_image_path() -> Optional[Path]:
    """
    Find the newest generated visual asset.

    Searches all visual directories created by visual_creator.py.
    """

    if not IMAGE_DIR.exists():
        return None

    supported_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    images = [
        path
        for path in IMAGE_DIR.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower() in supported_extensions
        )
    ]

    if not images:
        return None

    return max(
        images,
        key=lambda path: path.stat().st_mtime
    )


def get_latest_script_path() -> Optional[Path]:
    """
    Find the newest narration script created by script_creator.py.
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


# ---------------------------------------------------------------------------
# Attachment utilities
# ---------------------------------------------------------------------------

def attach_file(
    message: MIMEMultipart,
    file_path: Path,
    main_type: str,
    sub_type: str
) -> None:
    """
    Attach a file to an email message.

    Args:
        message:
            Email message being constructed.

        file_path:
            Path to the file.

        main_type:
            MIME main type such as video, image, or text.

        sub_type:
            MIME subtype such as mp4, png, or plain.
    """

    with file_path.open(
        "rb"
    ) as file:

        attachment = MIMEBase(
            main_type,
            sub_type
        )

        attachment.set_payload(
            file.read()
        )

    encoders.encode_base64(
        attachment
    )

    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=file_path.name
    )

    message.attach(
        attachment
    )


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

def send_content_email(
    service,
    recipient: str,
    subject: str,
    video_path: str,
    image_path: str,
    script_path: str
):
    """
    Send generated pipeline assets as email attachments.

    Args:
        service:
            Authenticated Gmail API service.

        recipient:
            Destination email address.

        subject:
            Email subject.

        video_path:
            Path to completed MP4.

        image_path:
            Path to generated visual asset.

        script_path:
            Path to narration script.

    Returns:
        Gmail API response.
    """

    video = Path(
        video_path
    )

    image = Path(
        image_path
    )

    script = Path(
        script_path
    )

    for file_path in (
        video,
        image,
        script
    ):
        if not file_path.exists():
            raise FileNotFoundError(
                f"Attachment not found: {file_path}"
            )

    message = MIMEMultipart()

    message["to"] = recipient
    message["from"] = "me"
    message["subject"] = subject

    # -----------------------------------------------------------------------
    # Attach final video.
    # -----------------------------------------------------------------------

    attach_file(
        message,
        video,
        "video",
        "mp4"
    )

    # -----------------------------------------------------------------------
    # Attach generated visual.
    # -----------------------------------------------------------------------

    image_subtype = (
        image.suffix
        .lower()
        .replace(".", "")
    )

    if image_subtype == "jpg":
        image_subtype = "jpeg"

    attach_file(
        message,
        image,
        "image",
        image_subtype
    )

    # -----------------------------------------------------------------------
    # Attach narration script.
    # -----------------------------------------------------------------------

    attach_file(
        message,
        script,
        "text",
        "plain"
    )

    # -----------------------------------------------------------------------
    # Encode and send message.
    # -----------------------------------------------------------------------

    raw_message = (
        base64
        .urlsafe_b64encode(
            message.as_bytes()
        )
        .decode("utf-8")
    )

    response = (
        service
        .users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": raw_message
            }
        )
        .execute()
    )

    print(
        "[EMAIL] Content delivered successfully."
    )

    return response


# ---------------------------------------------------------------------------
# Delivery workflow
# ---------------------------------------------------------------------------

def deliver_content(
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    video_path: Optional[str] = None,
    image_path: Optional[str] = None,
    script_path: Optional[str] = None,
):
    """
    Deliver pipeline output and supporting assets by email.

    Explicit file paths may be supplied by another program.
    When run independently, the newest available files are used.

    Args:
        recipient:
            Destination email address.

        subject:
            Email subject.

        video_path:
            Optional path to completed video.

        image_path:
            Optional path to generated visual.

        script_path:
            Optional path to narration script.

    Returns:
        Gmail API response.
        Returns None if required information cannot be found.
    """

    recipient = (
        recipient
        or DEFAULT_RECIPIENT
    )

    subject = (
        subject
        or DEFAULT_SUBJECT
    )

    if not recipient:
        print(
            "[EMAIL] No recipient configured."
        )
        return None

    # -----------------------------------------------------------------------
    # Locate pipeline assets.
    # -----------------------------------------------------------------------

    video = (
        Path(video_path)
        if video_path
        else get_latest_video_path()
    )

    image = (
        Path(image_path)
        if image_path
        else get_latest_image_path()
    )

    script = (
        Path(script_path)
        if script_path
        else get_latest_script_path()
    )

    if video is None:
        print(
            "[EMAIL] No completed video found."
        )
        return None

    if image is None:
        print(
            "[EMAIL] No visual asset found."
        )
        return None

    if script is None:
        print(
            "[EMAIL] No narration script found."
        )
        return None

    # -----------------------------------------------------------------------
    # Authenticate and deliver.
    # -----------------------------------------------------------------------

    print(
        "[EMAIL] Authenticating..."
    )

    service = authenticate_email()

    print(
        f"[EMAIL] Delivering content to: "
        f"{recipient}"
    )

    return send_content_email(
        service=service,
        recipient=recipient,
        subject=subject,
        video_path=str(video),
        image_path=str(image),
        script_path=str(script),
    )


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    result = deliver_content()

    if result:
        print(
            "[EMAIL] Delivery workflow complete."
        )

    else:
        print(
            "[EMAIL] Delivery workflow did not complete."
        )