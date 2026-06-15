# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Teaching Video Composer Service

Orchestrates:
- Teaching script generation from PPT/PDF (via LLM)
- TTS audio generation per short segment
- Slide background video creation with precise narration timing
- Digital human overlay with chained reference frames
- Precise duration control
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import ffmpeg
from loguru import logger
from pydantic import BaseModel, Field

from multifunc_video.services.ppt_service import SlideInfo, PPTService
from multifunc_video.utils.os_util import ensure_dir, get_resource_path


class SlideSegment(BaseModel):
    """A narration segment aligned with a single slide (legacy)"""
    slide_index: int = Field(..., description="Index of the slide this segment belongs to")
    text: str = Field(..., description="Narration text for this segment")
    start_time: float = Field(0.0, description="Start time in seconds")
    end_time: float = Field(0.0, description="End time in seconds")


class ScriptSegmentResponse(BaseModel):
    """Structured response for slide segment splitting (legacy)"""
    segments: List[SlideSegment]


class Segment(BaseModel):
    """
    A narration segment with flexible slide mapping.
    A segment may span multiple slides, and a slide may be covered by
    multiple consecutive segments.
    """
    text: str = Field(..., description="Narration text for this segment")
    slide_start: int = Field(..., description="Index of the first slide covered by this segment")
    slide_end: int = Field(..., description="Index of the last slide covered by this segment (inclusive)")
    audio_path: Optional[str] = Field(None, description="Path to generated TTS audio")
    duration: float = Field(0.0, description="Real audio duration in seconds")


class SegmentSplitResponse(BaseModel):
    """Structured response for flexible segment splitting"""
    segments: List[Segment]


@dataclass
class TeachingCompositionParams:
    """Parameters for teaching video composition"""
    character_image_path: str
    teaching_file_path: str
    task_dir: str
    # Script (optional)
    teaching_script: str = ""
    # Digital human position
    human_scale: float = 1/6  # width ratio relative to canvas
    human_offset_x: float = 0.02  # distance from right edge as ratio
    human_offset_y: float = 0.02  # distance from bottom edge as ratio
    human_anchor: str = "bottom-right"
    # Duration control
    duration_mode: str = "auto"  # "auto" or "fixed"
    target_duration: float = 0.0
    # Video settings
    width: int = 1920
    height: int = 1080
    fps: int = 30
    slide_fit_mode: str = "fit"  # "fit" or "cover"
    # Optional prompt for digital human (e.g. hand gestures)
    human_prompt: str = ""
    # Workflow source (runninghub / selfhost)
    workflow_source: str = "runninghub"
    # TTS parameters
    tts_inference_mode: str = "local"
    tts_voice: Optional[str] = None
    tts_speed: Optional[float] = None
    tts_workflow: Optional[str] = None
    ref_audio: Optional[str] = None
    # Final output audio volume multiplier (1.0 = original, >1 louder, <1 quieter)
    audio_volume: float = 1.0


class TeachingComposer:
    """
    Composes a teaching video from PPT/PDF, narration, and digital human.

    Uses segmented generation:
    - Narration is split into short segments (~10s, max 15s).
    - Each segment gets its own TTS and real duration is validated.
    - Slide display durations are derived from segment-to-slide mapping.
    - Digital human videos are generated per segment with chained reference frames.
    """

    def __init__(self, multifunc_video: Any, llm_service: Any):
        """
        Args:
            multifunc_video: MultiFuncVideoCore instance (for TTS, ComfyKit)
            llm_service: LLMService instance for script generation
        """
        self.multifunc_video = multifunc_video
        self.llm_service = llm_service
        self.ppt_service = PPTService()

    async def compose(self, params: TeachingCompositionParams, progress_callback=None) -> str:
        """
        Compose the full teaching video.

        Args:
            params: TeachingCompositionParams
            progress_callback: Optional callable(current_step, total_steps, message)

        Returns:
            Path to final video file
        """
        total_steps = 8

        def report(step: int, message: str):
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")

        # Step 1: Parse teaching material
        report(1, "解析教学课件...")
        slides = self.ppt_service.parse(params.teaching_file_path, output_dir=params.task_dir)
        if not slides:
            raise ValueError("未能从课件中解析出任何幻灯片")

        # Step 2: Generate or use teaching script
        if params.teaching_script and params.teaching_script.strip():
            full_script = params.teaching_script.strip()
            report(2, "使用用户提供的口播文案")
        else:
            report(2, "根据课件内容生成口播文案...")
            full_script = await self._generate_script(slides)

        logger.info(f"教学口播文案长度: {len(full_script)} 字符")

        # Step 3: Split script into segments with flexible slide mapping
        report(3, "分段并对齐课件页...")
        segments = await self._split_script_into_segments(full_script, slides)
        logger.info(f"文案已分为 {len(segments)} 个片段")

        # Duration mode check
        if params.duration_mode == "fixed" and params.target_duration > 0:
            logger.warning(
                "固定时长模式在分段链式生成方案下无法精确保证，"
                "将按自动模式处理（以音频真实时长为基准）"
            )

        # Step 4: Generate TTS for each segment and validate durations
        report(4, "逐段合成配音并校验时长...")
        segments = await self._generate_segment_audios(segments, slides, params)
        total_duration = sum(seg.duration for seg in segments)
        logger.info(f"所有片段音频总时长: {total_duration:.2f}s")

        # Build full narration audio by concatenating segment audios
        full_audio_path = os.path.join(params.task_dir, "narration.mp3")
        self._concat_audios([seg.audio_path for seg in segments], full_audio_path)

        # Step 5: Compute precise slide durations
        report(5, "计算每页课件展示时长...")
        slide_durations = self._compute_slide_durations(segments, len(slides))
        for i, d in enumerate(slide_durations):
            logger.debug(f"Slide {i} duration: {d:.2f}s")

        # Step 6: Create background video from slides
        report(6, "生成课件背景视频...")
        background_video = await self._create_background_video(
            slides, slide_durations, params
        )

        # Step 7: Generate digital human talking video segments with chained references
        report(7, "链式生成数字人口型视频...")
        human_video = await self._generate_human_video_segments(params, segments)

        # Step 8: Overlay human onto background
        report(8, "合成最终教学视频...")
        final_video = self._compose_final_video(
            background_video=background_video,
            human_video=human_video,
            audio_path=full_audio_path,
            params=params,
            target_duration=total_duration
        )

        logger.success(f"教学视频合成完成: {final_video}")
        return final_video

    async def _generate_script(self, slides: List[SlideInfo]) -> str:
        """Generate teaching script from slide contents using LLM"""
        from multifunc_video.prompts.teaching_script_generation import build_teaching_script_prompt

        slide_dicts = [{"index": s.index, "title": s.title, "text": s.text} for s in slides]
        prompt = build_teaching_script_prompt(slide_dicts)

        script = await self.llm_service(prompt=prompt, temperature=0.7, max_tokens=4000)
        script = script.strip()

        # Clean up common LLM artifacts
        script = self._clean_script(script)
        return script

    def _clean_script(self, script: str) -> str:
        """Clean up LLM output artifacts"""
        # Remove markdown code blocks
        if script.startswith("```"):
            lines = script.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            script = "\n".join(lines).strip()

        # Remove common prefixes
        for prefix in ["口播文案：", "教学口播文案：", "文案："]:
            if script.startswith(prefix):
                script = script[len(prefix):].strip()

        return script

    async def _split_script_into_segments(
        self,
        full_script: str,
        slides: List[SlideInfo]
    ) -> List[Segment]:
        """
        Split full script into short segments with flexible slide mapping.
        Each segment is annotated with the slide range it covers.
        """
        from multifunc_video.prompts.teaching_script_generation import build_free_segment_prompt

        if len(slides) == 1:
            return [Segment(text=full_script, slide_start=0, slide_end=0)]

        slide_dicts = [{"index": s.index, "title": s.title, "text": s.text} for s in slides]
        prompt = build_free_segment_prompt(full_script, slide_dicts)

        try:
            response = await self.llm_service(
                prompt=prompt,
                temperature=0.3,
                max_tokens=4000,
                response_type=SegmentSplitResponse
            )
            segments = response.segments
        except Exception as e:
            logger.warning(f"LLM 分段失败，尝试用简化 prompt 重试: {e}")
            response = await self.llm_service(
                prompt=prompt + "\n\n注意：必须严格输出 JSON 格式，不要包含任何其他文字。",
                temperature=0.1,
                max_tokens=4000,
                response_type=SegmentSplitResponse
            )
            segments = response.segments

        segments = self._normalize_segments(segments, full_script, len(slides))
        return segments

    def _normalize_segments(
        self,
        segments: List[Segment],
        full_script: str,
        num_slides: int
    ) -> List[Segment]:
        """Validate and normalize segments"""
        if not segments:
            raise ValueError("LLM 返回的片段为空")

        normalized = []
        for seg in segments:
            slide_start = max(0, min(seg.slide_start, num_slides - 1))
            slide_end = max(slide_start, min(seg.slide_end, num_slides - 1))
            normalized.append(Segment(
                text=seg.text.strip(),
                slide_start=slide_start,
                slide_end=slide_end
            ))

        concatenated = "".join(seg.text for seg in normalized)
        if abs(len(concatenated) - len(full_script)) > len(full_script) * 0.05 + 10:
            logger.warning(
                f"片段拼接长度 ({len(concatenated)}) 与原文案长度 ({len(full_script)}) 差异较大"
            )

        for i in range(1, len(normalized)):
            if normalized[i].slide_start < normalized[i - 1].slide_start:
                logger.warning(f"片段 {i} 的 slide_start 小于前一片段，强制修正")
                normalized[i].slide_start = normalized[i - 1].slide_start
            if normalized[i].slide_end < normalized[i].slide_start:
                normalized[i].slide_end = normalized[i].slide_start

        return normalized

    async def _generate_audio(
        self,
        text: str,
        output_path: str,
        params: TeachingCompositionParams,
        speed_override: Optional[float] = None
    ):
        """Generate TTS audio"""
        tts_kwargs = {
            "text": text,
            "output_path": output_path,
            "inference_mode": params.tts_inference_mode
        }

        if params.tts_inference_mode == "local":
            tts_kwargs["voice"] = params.tts_voice
            tts_kwargs["speed"] = speed_override if speed_override is not None else params.tts_speed
        elif params.tts_inference_mode == "comfyui":
            if params.tts_workflow:
                tts_kwargs["workflow"] = params.tts_workflow
            if params.ref_audio:
                tts_kwargs["ref_audio"] = params.ref_audio

        await self.multifunc_video.tts(**tts_kwargs)

    async def _generate_segment_audios(
        self,
        segments: List[Segment],
        slides: List[SlideInfo],
        params: TeachingCompositionParams,
        max_duration: float = 15.0,
        depth: int = 0
    ) -> List[Segment]:
        """
        Generate TTS audio for each segment and validate real durations.
        If a segment exceeds max_duration, re-split it recursively.
        """
        from multifunc_video.prompts.teaching_script_generation import build_free_segment_prompt

        if depth > 3:
            raise RuntimeError(
                f"片段音频时长多次超过 {max_duration}s 且无法有效切分，"
                "请检查文案是否单句过长或 TTS 语速过慢"
            )

        result: List[Segment] = []

        for i, seg in enumerate(segments):
            seg_audio_path = os.path.join(params.task_dir, f"segment_{depth}_{i:03d}.mp3")
            await self._generate_audio(seg.text, seg_audio_path, params)
            duration = self._get_audio_duration(seg_audio_path)

            if duration > max_duration:
                logger.warning(
                    f"片段 {i} 音频时长 {duration:.2f}s 超过 {max_duration}s，重新切分"
                )
                slide_dicts = [{"index": s.index, "title": s.title, "text": s.text} for s in slides]
                sub_prompt = build_free_segment_prompt(seg.text, slide_dicts)
                sub_prompt += f"\n\n注意：该片段过长，请将其切分为每个不超过 {max_duration} 秒的子片段。"

                try:
                    sub_response = await self.llm_service(
                        prompt=sub_prompt,
                        temperature=0.2,
                        max_tokens=4000,
                        response_type=SegmentSplitResponse
                    )
                    sub_segments = sub_response.segments
                except Exception as e:
                    raise RuntimeError(f"片段 {i} 重新切分失败: {e}")

                sub_segments = self._normalize_segments(sub_segments, seg.text, len(slides))

                # Clamp sub-segment slide ranges to parent segment's range
                for sub in sub_segments:
                    sub.slide_start = max(sub.slide_start, seg.slide_start)
                    sub.slide_end = min(sub.slide_end, seg.slide_end)
                    if sub.slide_end < sub.slide_start:
                        sub.slide_end = sub.slide_start

                processed_subs = await self._generate_segment_audios(
                    sub_segments, slides, params, max_duration, depth=depth + 1
                )
                result.extend(processed_subs)
            else:
                result.append(Segment(
                    text=seg.text,
                    slide_start=seg.slide_start,
                    slide_end=seg.slide_end,
                    audio_path=seg_audio_path,
                    duration=duration
                ))

        return result

    def _concat_audios(self, audio_paths: List[str], output_path: str):
        """Concatenate multiple audio files into one using ffmpeg concat demuxer"""
        if len(audio_paths) == 1:
            shutil.copy(audio_paths[0], output_path)
            return

        ensure_dir(os.path.dirname(output_path))
        filelist_path = output_path + ".txt"
        with open(filelist_path, "w", encoding="utf-8") as f:
            for path in audio_paths:
                abs_path = Path(path).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        try:
            (
                ffmpeg
                .input(filelist_path, format="concat", safe=0)
                .output(output_path, acodec="copy")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"拼接音频失败: {error_msg}")
            raise RuntimeError(f"拼接音频失败: {error_msg}")

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds"""
        try:
            probe = ffmpeg.probe(audio_path)
            return float(probe["format"]["duration"])
        except Exception as e:
            logger.warning(f"获取音频时长失败: {e}")
            return 0.0

    def _compute_slide_durations(
        self,
        segments: List[Segment],
        num_slides: int
    ) -> List[float]:
        """
        Compute total display duration for each slide based on segment durations.
        Each segment's duration is distributed evenly across the slides it covers.
        """
        slide_weights = [0.0] * num_slides

        for seg in segments:
            duration = seg.duration
            if duration <= 0:
                continue

            slide_count = seg.slide_end - seg.slide_start + 1
            if slide_count <= 0:
                slide_count = 1

            weight_per_slide = len(seg.text) / slide_count
            for idx in range(seg.slide_start, seg.slide_end + 1):
                if 0 <= idx < num_slides:
                    slide_weights[idx] += weight_per_slide

        total_weight = sum(slide_weights)
        total_duration = sum(seg.duration for seg in segments)

        if total_weight <= 0:
            return [total_duration / num_slides] * num_slides

        slide_durations = [
            (weight / total_weight) * total_duration for weight in slide_weights
        ]

        min_duration = 1.5
        self._enforce_min_duration(slide_durations, total_duration, min_duration)
        return slide_durations

    def _enforce_min_duration(
        self,
        durations: List[float],
        total_duration: float,
        min_duration: float
    ):
        """Ensure each duration is at least min_duration by borrowing from others."""
        num = len(durations)
        if num * min_duration > total_duration:
            logger.warning(
                f"总时长 {total_duration:.2f}s 不足以让每页都显示 {min_duration}s，"
                "将按比例分配"
            )
            return

        deficits = [max(0, min_duration - d) for d in durations]
        while max(deficits) > 0.001:
            for i in range(num):
                if deficits[i] <= 0.001:
                    continue
                deficit = deficits[i]
                for j in range(num):
                    if i == j:
                        continue
                    available = durations[j] - min_duration
                    if available > 0:
                        transfer = min(deficit, available)
                        durations[j] -= transfer
                        durations[i] += transfer
                        deficit -= transfer
                        if deficit <= 0.001:
                            break
                deficits[i] = max(0, deficit)

        current_sum = sum(durations)
        if current_sum > 0 and abs(current_sum - total_duration) > 0.001:
            scale = total_duration / current_sum
            for i in range(num):
                durations[i] *= scale

    async def _create_background_video(
        self,
        slides: List[SlideInfo],
        slide_durations: List[float],
        params: TeachingCompositionParams
    ) -> str:
        """
        Create background video from slides using precise per-slide durations.
        Total duration equals the sum of all segment audio durations.
        """
        if len(slides) != len(slide_durations):
            raise ValueError(
                f"幻灯片数量 ({len(slides)}) 与时长数量 ({len(slide_durations)}) 不一致"
            )

        ensure_dir(params.task_dir)
        output_path = os.path.join(params.task_dir, "background.mp4")

        filelist_path = os.path.join(params.task_dir, "slide_filelist.txt")
        with open(filelist_path, "w", encoding="utf-8") as f:
            for slide, duration in zip(slides, slide_durations):
                abs_path = Path(slide.image_path).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
                f.write(f"duration {duration:.3f}\n")
            if slides:
                last_abs_path = Path(slides[-1].image_path).absolute()
                escaped_path = str(last_abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        scale_filter = self._build_scale_filter(params.width, params.height, params.slide_fit_mode)

        try:
            (
                ffmpeg
                .input(filelist_path, format="concat", safe=0)
                .output(
                    output_path,
                    vf=scale_filter,
                    r=params.fps,
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    preset="medium",
                    crf=23,
                    **{"b:v": "4M"}
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"生成背景视频失败: {error_msg}")
            raise RuntimeError(f"生成背景视频失败: {error_msg}")

    def _build_scale_filter(self, width: int, height: int, fit_mode: str) -> str:
        """Build ffmpeg scale filter for slide fitting"""
        if fit_mode == "cover":
            return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        else:  # fit
            return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"

    async def _generate_human_video_segments(
        self,
        params: TeachingCompositionParams,
        segments: List[Segment]
    ) -> str:
        """
        Generate digital human video segments with chained reference frames.
        The last frame of segment n is used as the start image for segment n+1.
        """
        segment_video_paths: List[str] = []
        start_image = params.character_image_path

        for i, seg in enumerate(segments):
            seg_output_path = os.path.join(params.task_dir, f"human_segment_{i:03d}.mp4")
            logger.info(f"生成数字人片段 {i+1}/{len(segments)}，时长 {seg.duration:.2f}s")

            await self._generate_single_human_video(
                params=params,
                start_image=start_image,
                audio_path=seg.audio_path,
                output_path=seg_output_path
            )
            segment_video_paths.append(seg_output_path)

            # Extract last frame for next segment's start image
            if i < len(segments) - 1:
                last_frame_path = os.path.join(params.task_dir, f"human_segment_{i:03d}_last_frame.jpg")
                self._extract_last_frame(seg_output_path, last_frame_path)
                start_image = last_frame_path

        full_human_path = os.path.join(params.task_dir, "human_full.mp4")
        self._concat_videos(segment_video_paths, full_human_path)
        return full_human_path

    async def _generate_single_human_video(
        self,
        params: TeachingCompositionParams,
        start_image: str,
        audio_path: str,
        output_path: str
    ):
        """Generate one digital human talking video segment using the existing workflow."""
        kit = await self.multifunc_video._get_or_create_comfykit()

        workflow_source = params.workflow_source
        try:
            second_workflow_path_str = get_resource_path(
                "workflows", workflow_source, "digital_combination.json"
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"数字人工作流文件不存在: workflows/{workflow_source}/digital_combination.json"
            ) from e

        second_workflow_path = Path(second_workflow_path_str)

        with open(second_workflow_path, "r", encoding="utf-8") as f:
            workflow_config = json.load(f)

        workflow_params = {
            "videoimage": start_image,
            "audio": audio_path
        }

        if params.human_prompt:
            workflow_params["prompt"] = params.human_prompt

        if workflow_config.get("source") == "runninghub" and "workflow_id" in workflow_config:
            workflow_input = workflow_config["workflow_id"]
        else:
            workflow_input = str(second_workflow_path)

        logger.info(
            f"执行数字人工作流: source={workflow_source}, "
            f"path={second_workflow_path}, "
            f"workflow_id={workflow_config.get('workflow_id', 'N/A')}"
        )
        logger.info(f"工作流输入参数: videoimage={start_image}, audio={audio_path}")

        result = await kit.execute(workflow_input, workflow_params)

        try:
            result_debug_path = os.path.join(params.task_dir, f"human_workflow_result_{Path(output_path).stem}.json")
            with open(result_debug_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump() if hasattr(result, "model_dump") else dict(result), f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"工作流执行结果已保存: {result_debug_path}")
        except Exception as dump_err:
            logger.warning(f"保存工作流结果调试文件失败: {dump_err}")

        result_status = getattr(result, "status", "unknown")
        result_msg = getattr(result, "msg", None)
        if result_status != "completed":
            logger.error(f"数字人工作流执行未成功: status={result_status}, msg={result_msg}")
            raise RuntimeError(
                f"数字人工作流执行失败 (status={result_status})。"
                f"{f' 详情: {result_msg}' if result_msg else ''}"
                "请检查 ComfyUI 节点、模型是否已正确安装，或查看日志中的 human_workflow_result 文件。"
            )

        generated_video_url = None
        if hasattr(result, "videos") and result.videos:
            generated_video_url = result.videos[0]
        elif hasattr(result, "outputs") and result.outputs:
            for node_id, node_output in result.outputs.items():
                if isinstance(node_output, dict) and "videos" in node_output:
                    videos = node_output["videos"]
                    if videos and len(videos) > 0:
                        generated_video_url = videos[0]
                        break

        if not generated_video_url:
            logger.error(
                f"数字人工作流未返回视频。result.status={result_status}, "
                f"result.videos={getattr(result, 'videos', [])}, "
                f"result.outputs={getattr(result, 'outputs', None)}"
            )
            raise RuntimeError(
                "数字人工作流未返回视频，请检查工作流配置。"
                "可能原因：1) 工作流缺少输出节点；2) ComfyUI 自定义节点或模型缺失导致执行失败。"
            )

        if os.path.exists(generated_video_url):
            shutil.copy(generated_video_url, output_path)
        elif generated_video_url.startswith("http://") or generated_video_url.startswith("https://"):
            import httpx
            timeout = httpx.Timeout(300.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(generated_video_url)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
        else:
            raise RuntimeError(f"数字人工作流返回的视频路径格式无法识别: {generated_video_url}")

    def _extract_last_frame(self, video_path: str, output_path: str):
        """Extract the last frame of a video to use as a reference image."""
        try:
            (
                ffmpeg
                .input(video_path, sseof="-0.5")
                .output(
                    output_path,
                    vf="select=eq(n\\,0)",
                    vframes=1,
                    **{"q:v": "2"}
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"提取尾帧失败: {error_msg}")
            raise RuntimeError(f"提取尾帧失败: {error_msg}")

    def _concat_videos(self, video_paths: List[str], output_path: str):
        """Concatenate multiple video files using ffmpeg concat demuxer."""
        if len(video_paths) == 1:
            shutil.copy(video_paths[0], output_path)
            return

        ensure_dir(os.path.dirname(output_path))
        filelist_path = output_path + ".txt"
        with open(filelist_path, "w", encoding="utf-8") as f:
            for path in video_paths:
                abs_path = Path(path).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        try:
            (
                ffmpeg
                .input(filelist_path, format="concat", safe=0)
                .output(output_path, c="copy")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"拼接数字人视频失败: {error_msg}")
            raise RuntimeError(f"拼接数字人视频失败: {error_msg}")

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        try:
            probe = ffmpeg.probe(video_path)
            return float(probe["format"]["duration"])
        except Exception as e:
            logger.warning(f"获取视频时长失败: {e}")
            return 0.0

    def _compose_final_video(
        self,
        background_video: str,
        human_video: str,
        audio_path: str,
        params: TeachingCompositionParams,
        target_duration: float
    ) -> str:
        """Compose final video by overlaying human onto background with narration audio"""
        ensure_dir(params.task_dir)
        output_path = os.path.join(params.task_dir, "final.mp4")

        human_width = int(params.width * params.human_scale)

        if params.human_anchor == "bottom-right":
            x_expr = f"W-w-{params.width * params.human_offset_x}"
            y_expr = f"H-h-{params.height * params.human_offset_y}"
        else:
            x_expr = f"W-w-{params.width * params.human_offset_x}"
            y_expr = f"H-h-{params.height * params.human_offset_y}"

        try:
            audio_volume = max(0.0, min(params.audio_volume, 5.0))
            filter_complex = (
                f"[1:v]scale={human_width}:-1:flags=lanczos[human];"
                f"[0:v][human]overlay={x_expr}:{y_expr}:format=auto[video];"
                f"[2:a]volume={audio_volume}[aout]"
            )

            cmd = [
                "ffmpeg",
                "-y",
                "-i", background_video,
                "-i", human_video,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[video]",
                "-map", "[aout]",
                "-t", str(target_duration),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                check=True
            )

            return output_path
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            logger.error(f"合成最终视频失败: {stderr}")
            raise RuntimeError(f"合成最终视频失败: {stderr}")
        except Exception as e:
            logger.error(f"合成最终视频失败: {e}")
            raise RuntimeError(f"合成最终视频失败: {e}")


# Type hint for multifunc_video
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from multifunc_video.core import MultiFuncVideoCore
