# -*- coding=utf-8 -*-
"""
Google utility functions.
"""
from typing import Optional

from django.conf import settings

from google_auth_oauthlib.flow import Flow


def create_flow(redirect_uri: Optional[str] = None) -> Flow:
    """Returns a Google Flow from client configuration."""
    return Flow.from_client_config(
        settings.GOOGLE_FLOW,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/docs",
            "https://www.googleapis.com/auth/drive.file",
            "https://docs.google.com/feeds/",
            "https://spreadsheets.google.com/feeds/",
        ],
        redirect_uri=redirect_uri or settings.GOOGLE_STEP2_URI,
    )
