from dataclasses import dataclass

from vshift.domain.transcoding_profile.enums import QualityMode, VideoEncoder
from vshift.domain.transcoding_profile.vshift_profile import VideoProfile, VshiftProfile


@dataclass(frozen=True, slots=True)
class MappedFfmpegCommand:
    maps: list[str]
    video_args: list[str]
    video_filter: str | None
    audio_args: list[str]
    output_args: list[str]
    input_args: list[str]


class ProfileMapper:
    """Maps a vshift profile to FFmpeg argument groups."""

    def map_profile(
        self,
        profile: VshiftProfile,
        *,
        video_encoder: VideoEncoder,
    ) -> MappedFfmpegCommand:
        video = profile.video
        maps = ["-map", "0:v:0"]
        audio_args: list[str] = []

        if profile.audio_selection_mode.value != "none" and profile.audio_tracks:
            for index, track in enumerate(profile.audio_tracks):
                maps.extend(["-map", f"0:a:{index}"])
                if track.copy_track:
                    audio_args.extend([f"-c:a:{index}", "copy"])
                else:
                    audio_args.extend([f"-c:a:{index}", track.codec])
                    audio_args.extend([f"-b:a:{index}", f"{track.bit_rate}k"])
                    if track.sample_rate is not None:
                        audio_args.extend([f"-ar:a:{index}", str(track.sample_rate)])
        elif profile.audio_selection_mode.value != "none":
            maps.extend(["-map", "0:a:0?"])
            audio_args.extend(["-c:a", "aac", "-b:a", "160k"])

        video_args = ["-c:v", video_encoder.value]
        video_args.extend(_video_quality_args(video_encoder, video))
        video_args.extend(_video_encoder_tuning_args(video_encoder, video))

        if video.encoder_profile not in ("", "auto"):
            video_args.extend(["-profile:v", video.encoder_profile])
        if video.encoder_level not in ("", "auto"):
            video_args.extend(["-level:v", video.encoder_level])

        if video.grayscale:
            video_args.extend(["-pix_fmt", "gray"])
        elif video.bit_depth == 10 and video.codec.lower() in {"h265", "hevc", "av1"}:
            video_args.extend(["-pix_fmt", "yuv420p10le"])
        else:
            video_args.extend(["-pix_fmt", video.color_space])

        video_filter = _build_video_filter(video)
        input_args: list[str] = []
        if video_encoder in {VideoEncoder.H264_VAAPI, VideoEncoder.HEVC_VAAPI}:
            input_args.extend(["-vaapi_device", "/dev/dri/renderD128"])
            video_filter = _append_filter(video_filter, "format=nv12,hwupload")

        output_args: list[str] = []
        if profile.format == "mp4" and profile.optimize:
            output_args.extend(["-movflags", "+faststart"])

        return MappedFfmpegCommand(
            maps=maps,
            video_args=video_args,
            video_filter=video_filter,
            audio_args=audio_args,
            output_args=output_args,
            input_args=input_args,
        )


def _video_quality_args(
    video_encoder: VideoEncoder,
    video: VideoProfile,
) -> list[str]:
    if video.quality_mode == QualityMode.AVERAGE_BITRATE:
        bitrate = video.average_bitrate or 0
        return ["-b:v", f"{bitrate}k"]

    quality = str(int(video.quality))
    if video_encoder in {
        VideoEncoder.LIBX264,
        VideoEncoder.LIBX265,
        VideoEncoder.LIBSVTAV1,
    }:
        return ["-crf", quality]

    if video_encoder in {
        VideoEncoder.H264_NVENC,
        VideoEncoder.HEVC_NVENC,
        VideoEncoder.AV1_NVENC,
    }:
        return ["-rc:v", "constqp", "-qp:v", quality]

    if video_encoder in {VideoEncoder.H264_QSV, VideoEncoder.HEVC_QSV}:
        return ["-global_quality", quality]

    if video_encoder in {
        VideoEncoder.H264_VIDEOTOOLBOX,
        VideoEncoder.HEVC_VIDEOTOOLBOX,
    }:
        return ["-q:v", quality]

    if video_encoder in {VideoEncoder.H264_VAAPI, VideoEncoder.HEVC_VAAPI}:
        return ["-qp:v", quality]

    return ["-crf", quality]


def _video_encoder_tuning_args(
    video_encoder: VideoEncoder,
    video: VideoProfile,
) -> list[str]:
    args: list[str] = []
    if video_encoder == VideoEncoder.LIBX264:
        args.extend(["-preset", video.encoder_preset])
        if video.encoder_tune:
            args.extend(["-tune", video.encoder_tune])
    elif video_encoder == VideoEncoder.LIBX265:
        args.extend(["-preset", video.encoder_preset])
    elif video_encoder in {
        VideoEncoder.H264_NVENC,
        VideoEncoder.HEVC_NVENC,
        VideoEncoder.AV1_NVENC,
    }:
        args.extend(["-preset", _map_nvenc_preset(video.encoder_preset)])

    if video.frame_rate_type.value == "custom" and video.frame_rate is not None:
        args.extend(["-r", str(video.frame_rate)])

    return args


def _build_video_filter(video: VideoProfile) -> str | None:
    filters: list[str] = []
    if video.width is not None and video.height is not None:
        filters.append(f"scale={video.width}:{video.height}")
    elif video.width is not None:
        filters.append(f"scale={video.width}:-2")
    elif video.height is not None:
        filters.append(f"scale=-2:{video.height}")

    if not filters:
        return None
    return ",".join(filters)


def _append_filter(existing: str | None, extra: str) -> str:
    if existing is None:
        return extra
    return f"{existing},{extra}"


def _map_nvenc_preset(preset: str) -> str:
    mapping = {
        "ultrafast": "p1",
        "superfast": "p2",
        "veryfast": "p3",
        "faster": "p4",
        "fast": "p5",
        "medium": "p6",
        "slow": "p7",
        "slower": "p8",
        "veryslow": "p9",
    }
    return mapping.get(preset, "p6")
