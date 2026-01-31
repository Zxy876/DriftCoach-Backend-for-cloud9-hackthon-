"""
EXPERIMENTAL / NOT_USED_IN_HACKATHON

Placeholder adapter for listing downloadable files by series_id.
No file contents are parsed or fetched.
"""

from typing import Dict, List


def list_files_for_series(series_id: str) -> List[Dict[str, str]]:
    if not series_id:
        raise ValueError("series_id is required")
    # Placeholder: in a real implementation, return remote file metadata
    return [
        {
            "series_id": series_id,
            "file_name": "placeholder.json",
            "url": "https://example.com/not-implemented",
            "status": "EXPERIMENTAL",
        }
    ]
