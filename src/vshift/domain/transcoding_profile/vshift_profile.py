from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from vshift.domain.transcoding_profile.enums import (
    AudioSelectionMode,
    FramerateMode,
    FrameRateType,
    QualityMode,
    SubtitleSelectionMode,
    VideoEncoder,
)
from vshift.exception import VShiftException


class VideoProfile(BaseModel):
    codec: str = Field(description="Video codec (e.g. h264, h265, av1)")
    encoder: VideoEncoder = Field(
        default=VideoEncoder.AUTO,
        description="FFmpeg encoder; auto selects hardware when available",
    )
    color_space: str = Field(
        default="yuv420p", description="Pixel format / color space"
    )
    bit_depth: Literal[8, 10, 12] = Field(default=8, description="Output bit depth")
    frame_rate_type: FrameRateType = Field(
        default=FrameRateType.SAME_AS_SOURCE,
        description="Whether to keep source FPS or use a fixed rate",
    )
    frame_rate: float | None = Field(
        default=None, description="Target FPS when frame_rate_type is custom"
    )
    framerate_mode: FramerateMode = Field(
        default=FramerateMode.VFR, description="Variable, peak, or constant frame rate"
    )
    width: int | None = Field(default=None, description="Output width; None = auto")
    height: int | None = Field(default=None, description="Output height; None = auto")
    quality_mode: QualityMode = Field(
        default=QualityMode.CONSTANT, description="Constant quality or average bitrate"
    )
    quality: float = Field(
        default=22.0, description="Quality value for constant-quality mode (e.g. RF/CQ)"
    )
    average_bitrate: int | None = Field(
        default=None, description="Target bitrate in kbps for average-bitrate mode"
    )
    encoder_preset: str = Field(default="medium", description="Encoder speed preset")
    encoder_tune: str = Field(default="", description="Encoder tune")
    encoder_profile: str = Field(default="auto", description="Codec profile")
    encoder_level: str = Field(default="auto", description="Codec level")
    multi_pass: bool = Field(default=False, description="Enable multi-pass encoding")
    turbo_multi_pass: bool = Field(
        default=False, description="Enable turbo multi-pass (first pass faster)"
    )
    grayscale: bool = Field(default=False, description="Encode in grayscale")

    @model_validator(mode="after")
    def validate_frame_rate(self) -> Self:
        if self.frame_rate_type == FrameRateType.CUSTOM and self.frame_rate is None:
            raise VShiftException(
                "frame_rate is required when frame_rate_type is custom"
            )
        return self

    @model_validator(mode="after")
    def validate_quality(self) -> Self:
        if self.quality_mode == QualityMode.CONSTANT and self.quality < 0:
            raise VShiftException("quality must be >= 0 for constant-quality mode")
        if self.quality_mode == QualityMode.AVERAGE_BITRATE and (
            self.average_bitrate is None or self.average_bitrate <= 0
        ):
            raise VShiftException(
                "average_bitrate must be > 0 for average-bitrate mode"
            )
        return self


class AudioTrack(BaseModel):
    codec: str = Field(
        description="Audio codec (e.g. aac, ac3) or copy:* for passthrough"
    )
    bit_rate: int = Field(description="Target audio bitrate in kbps")
    sample_rate: int | None = Field(
        default=None, description="Sample rate in Hz; None = auto"
    )
    mixdown: str = Field(default="stereo", description="Channel layout / mixdown")
    copy_track: bool = Field(
        default=False, description="Passthrough source audio without re-encoding"
    )


class SubtitleTrack(BaseModel):
    language: str = Field(default="und", description="Subtitle language code")
    codec: str = Field(default="copy", description="Subtitle codec or copy")
    copy_track: bool = Field(
        default=True, description="Passthrough source subtitles without conversion"
    )
    burn_in: bool = Field(default=False, description="Burn subtitle into video")
    is_default: bool = Field(default=False, description="Mark as default subtitle")


class VshiftProfile(BaseModel):
    """vshift transcoding profile (native model)."""

    name: str = Field(description="Profile display name")
    description: str = Field(default="", description="Profile description")
    format: str = Field(description="Output container format (e.g. mp4, mkv)")
    video: VideoProfile = Field(description="Video encoding settings")
    audio_tracks: list[AudioTrack] = Field(
        default_factory=lambda: list[AudioTrack](),
        description="Audio track encoding settings",
    )
    audio_selection_mode: AudioSelectionMode = Field(
        default=AudioSelectionMode.AUTO,
        description="Automatic audio track selection strategy",
    )
    audio_language_list: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Preferred audio languages for auto selection",
    )
    audio_passthrough: bool = Field(
        default=False, description="Allow passthrough/copy for audio tracks"
    )
    subtitle_tracks: list[SubtitleTrack] = Field(
        default_factory=lambda: list[SubtitleTrack](),
        description="Subtitle track handling settings",
    )
    subtitle_selection_mode: SubtitleSelectionMode = Field(
        default=SubtitleSelectionMode.AUTO,
        description="Automatic subtitle track selection strategy",
    )
    subtitle_language_list: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Preferred subtitle languages for auto selection",
    )
    subtitle_passthrough: bool = Field(
        default=False, description="Allow subtitle passthrough/copy when possible"
    )
    chapter_markers: bool = Field(default=True, description="Include chapter markers")
    optimize: bool = Field(
        default=False, description="Optimize container for streaming"
    )

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        if not self.name.strip():
            raise VShiftException("name is required")
        if not self.format.strip():
            raise VShiftException("format is required")
        return self
