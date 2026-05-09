from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from phone_agent.adb_tools import ARTIFACTS_DIR, DEFAULT_SCREENSHOT_PATH
from phone_agent.config import debug_log


NORMALIZED_SIZE = 1000
NORMALIZED_SCREENSHOT_PATH = ARTIFACTS_DIR / "phone-screen-1000.png"


@dataclass(frozen=True)
class ScreenScale:
    source_width: int
    source_height: int
    normalized_width: int = NORMALIZED_SIZE
    normalized_height: int = NORMALIZED_SIZE

    def to_real_point(self, x: int, y: int) -> tuple[int, int]:
        real_x = round(x / self.normalized_width * self.source_width)
        real_y = round(y / self.normalized_height * self.source_height)
        return clamp(real_x, 0, self.source_width - 1), clamp(real_y, 0, self.source_height - 1)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def create_normalized_screenshot(
    source_path: Path = DEFAULT_SCREENSHOT_PATH,
    normalized_path: Path = NORMALIZED_SCREENSHOT_PATH,
) -> ScreenScale:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    with Image.open(source_path) as image:
        source_width, source_height = image.size
        normalized = image.convert("RGB").resize(
            (NORMALIZED_SIZE, NORMALIZED_SIZE),
            Image.Resampling.LANCZOS,
        )
        normalized.save(normalized_path)

    scale = ScreenScale(source_width=source_width, source_height=source_height)
    debug_log(
        "screen.scale",
        source=f"{scale.source_width}x{scale.source_height}",
        normalized=f"{scale.normalized_width}x{scale.normalized_height}",
    )
    return scale


def current_screen_scale(source_path: Path = DEFAULT_SCREENSHOT_PATH) -> ScreenScale:
    if not source_path.exists():
        raise FileNotFoundError(f"Screenshot not found: {source_path}")
    with Image.open(source_path) as image:
        source_width, source_height = image.size
    return ScreenScale(source_width=source_width, source_height=source_height)


def normalized_to_real_point(x: int, y: int, source_path: Path = DEFAULT_SCREENSHOT_PATH) -> tuple[int, int]:
    return current_screen_scale(source_path).to_real_point(x, y)
