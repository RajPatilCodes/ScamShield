from typing import Final


DEFAULT_JURISDICTION: Final = "IN"
SUPPORTED_JURISDICTIONS: Final = frozenset({DEFAULT_JURISDICTION})
DEFAULT_LANGUAGE: Final = "en"
SUPPORTED_LANGUAGES: Final = frozenset({"en", "hi"})

DEFAULT_PAGE_SIZE: Final = 20
MAX_PAGE_SIZE: Final = 50
MAX_CURSOR_LENGTH: Final = 256
MAX_SEARCH_LENGTH: Final = 100
MAX_CATALOG_RESPONSE_BYTES: Final = 2 * 1024 * 1024

REQUIRED_GUIDE_IDS: Final = tuple(f"SC-{number:03d}" for number in range(1, 34))

PUBLISHED_STATUS: Final = "published"
DRAFT_STATUS: Final = "draft"
WITHDRAWN_STATUS: Final = "withdrawn"
PUBLICATION_STATUSES: Final = frozenset({PUBLISHED_STATUS, DRAFT_STATUS})

GUIDE_REVIEW_PENDING: Final = "pending_editorial_review"
GUIDE_REVIEWED: Final = "reviewed"
RESOURCE_UNVERIFIED: Final = "unverified"
RESOURCE_VERIFIED: Final = "verified"
RESOURCE_WITHDRAWN: Final = "withdrawn"
