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
- TTS audio generation
- Slide background video creation with narration timing
- Digital human overlay with configurable position/scale
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

from pixelle_video.services.ppt_service import SlideInfo, PPTService
from pixelle_video.utils.os_util import ensure_dir


class SlideSegment(BaseModel):
    """A narration segment aligned with a slide"""
    slide_index: int = Field(..., description="Index of the slide this segment belongs to")
    text: str = Field(..., description="Narration text for this segment")
    start_time: float = Field(0.0, description="Start time in seconds")
    end_time: float = Field(0.0, description="End time in seconds")


class ScriptSegmentResponse(BaseModel):
    """Structured response for slide segment splitting"""
    segments: List[SlideSegment]


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


class TeachingComposer:
    """
    Composes a teaching video from PPT/PDF, narration, and digital human.
    """
    
    def __init__(self, pixelle_video: Any, llm_service: Any):
        """
        Args:
            pixelle_video: PixelleVideoCore instance (for TTS, ComfyKit)
            llm_service: LLMService instance for script generation
        """
        self.pixelle_video = pixelle_video
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
        total_steps = 7
        
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
        
        # Step 3: Split script into slide-aligned segments
        report(3, "对齐口播与课件页...")
        segments = await self._split_script_into_segments(full_script, slides)
        
        # Step 4: Generate TTS audio
        report(4, "合成配音音频...")
        audio_path = os.path.join(params.task_dir, "narration.mp3")
        await self._generate_audio(full_script, audio_path, params)
        audio_duration = self._get_audio_duration(audio_path)
        logger.info(f"音频时长: {audio_duration:.2f}s")
        
        # Step 5: Apply duration control
        target_duration = audio_duration
        if params.duration_mode == "fixed" and params.target_duration > 0:
            target_duration = params.target_duration
            # Adjust TTS speed to match target duration
            speed_ratio = audio_duration / target_duration
            if abs(speed_ratio - 1.0) > 0.05:
                adjusted_speed = (params.tts_speed or 1.2) * speed_ratio
                adjusted_speed = max(0.5, min(2.0, adjusted_speed))
                logger.info(f"调整 TTS 语速以匹配目标时长: {params.tts_speed} -> {adjusted_speed}")
                await self._generate_audio(full_script, audio_path, params, speed_override=adjusted_speed)
                audio_duration = self._get_audio_duration(audio_path)
                target_duration = audio_duration
        
        # Step 6: Create background video from slides
        report(5, "生成课件背景视频...")
        background_video = await self._create_background_video(
            slides, segments, target_duration, params
        )
        
        # Step 7: Generate digital human talking video
        report(6, "生成数字人口型视频...")
        human_video = await self._generate_human_video(params, audio_path)
        
        # Step 8: Overlay human onto background
        report(7, "合成最终教学视频...")
        final_video = self._compose_final_video(
            background_video=background_video,
            human_video=human_video,
            audio_path=audio_path,
            params=params,
            target_duration=target_duration
        )
        
        logger.success(f"教学视频合成完成: {final_video}")
        return final_video
    
    async def _generate_script(self, slides: List[SlideInfo]) -> str:
        """Generate teaching script from slide contents using LLM"""
        from pixelle_video.prompts.teaching_script_generation import build_teaching_script_prompt
        
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
    ) -> List[SlideSegment]:
        """Split full script into segments aligned with slides"""
        from pixelle_video.prompts.teaching_script_generation import build_slide_segment_prompt
        
        if len(slides) == 1:
            return [SlideSegment(slide_index=0, text=full_script, start_time=0.0, end_time=0.0)]
        
        slide_dicts = [{"index": s.index, "title": s.title, "text": s.text} for s in slides]
        prompt = build_slide_segment_prompt(full_script, slide_dicts)
        
        try:
            response = await self.llm_service(
                prompt=prompt,
                temperature=0.3,
                max_tokens=4000,
                response_type=ScriptSegmentResponse
            )
            segments = response.segments
        except Exception as e:
            logger.warning(f"LLM 切分文案失败，使用平均切分: {e}")
            segments = self._fallback_split_script(full_script, len(slides))
        
        # Validate and normalize segments
        segments = self._normalize_segments(segments, full_script, len(slides))
        return segments
    
    def _fallback_split_script(self, full_script: str, num_slides: int) -> List[SlideSegment]:
        """Fallback: split script evenly by character count"""
        total_chars = len(full_script)
        chars_per_slide = total_chars // num_slides
        segments = []
        
        for i in range(num_slides):
            start = i * chars_per_slide
            end = start + chars_per_slide if i < num_slides - 1 else total_chars
            # Try to break at sentence boundary
            if i < num_slides - 1:
                for sep in ["\n", "。", "；", "!", "?"]:
                    pos = full_script.rfind(sep, start, end + 20)
                    if pos > start + chars_per_slide // 2:
                        end = pos + 1
                        break
            segments.append(SlideSegment(slide_index=i, text=full_script[start:end].strip()))
        
        return segments
    
    def _normalize_segments(
        self,
        segments: List[SlideSegment],
        full_script: str,
        num_slides: int
    ) -> List[SlideSegment]:
        """Validate and normalize segments to cover all slides"""
        # Ensure we have exactly num_slides segments
        if len(segments) != num_slides:
            logger.warning(f"片段数量 ({len(segments)}) 与幻灯片数量 ({num_slides}) 不一致，使用回退切分")
            segments = self._fallback_split_script(full_script, num_slides)
        
        # Sort by slide_index
        segments = sorted(segments, key=lambda x: x.slide_index)
        
        # Ensure slide indices are valid
        for i, seg in enumerate(segments):
            seg.slide_index = i
            seg.text = seg.text.strip()
        
        return segments
    
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
        
        await self.pixelle_video.tts(**tts_kwargs)
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds"""
        try:
            probe = ffmpeg.probe(audio_path)
            return float(probe["format"]["duration"])
        except Exception as e:
            logger.warning(f"获取音频时长失败: {e}")
            return 0.0
    
    async def _create_background_video(
        self,
        slides: List[SlideInfo],
        segments: List[SlideSegment],
        target_duration: float,
        params: TeachingCompositionParams
    ) -> str:
        """Create background video from slides with narration timing"""
        # Calculate segment durations based on text length ratios
        total_text_length = sum(max(1, len(seg.text)) for seg in segments)
        segment_durations = []
        
        for seg in segments:
            ratio = max(1, len(seg.text)) / total_text_length
            duration = target_duration * ratio
            segment_durations.append(duration)
        
        # Adjust last segment to exactly match target duration
        total = sum(segment_durations)
        if total > 0 and abs(total - target_duration) > 0.01:
            segment_durations[-1] += (target_duration - total)
            segment_durations[-1] = max(0.5, segment_durations[-1])
        
        # Update segment times
        current_time = 0.0
        for seg, duration in zip(segments, segment_durations):
            seg.start_time = current_time
            seg.end_time = current_time + duration
            current_time += duration
        
        # Build ffmpeg concat demuxer file list with durations
        ensure_dir(params.task_dir)
        output_path = os.path.join(params.task_dir, "background.mp4")
        
        # Use concat demuxer: each slide shown for its segment duration
        filelist_path = os.path.join(params.task_dir, "slide_filelist.txt")
        with open(filelist_path, "w", encoding="utf-8") as f:
            for seg, duration in zip(segments, segment_durations):
                slide_image = slides[seg.slide_index].image_path
                abs_path = Path(slide_image).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                # Write each slide with its duration
                f.write(f"file '{escaped_path}'\n")
                f.write(f"duration {duration:.3f}\n")
            # Repeat last file (required by concat demuxer)
            if segments:
                last_slide = slides[segments[-1].slide_index].image_path
                abs_path = Path(last_slide).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        # Scale slides to target resolution
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
    
    async def _generate_human_video(
        self,
        params: TeachingCompositionParams,
        audio_path: str
    ) -> str:
        """Generate digital human talking video using existing workflow"""
        kit = await self.pixelle_video._get_or_create_comfykit()
        
        # Use the same second workflow as digital_human (image + audio -> talking head)
        workflow_source = params.workflow_source
        second_workflow_path = Path(f"workflows/{workflow_source}/digital_combination.json")
        
        if not second_workflow_path.exists():
            raise FileNotFoundError(f"数字人工作流文件不存在: {second_workflow_path}")
        
        with open(second_workflow_path, "r", encoding="utf-8") as f:
            workflow_config = json.load(f)
        
        workflow_params = {
            "videoimage": params.character_image_path,
            "audio": audio_path
        }
        
        # Add optional prompt if workflow supports it
        if params.human_prompt:
            # Some workflows may accept a prompt parameter
            workflow_params["prompt"] = params.human_prompt
        
        if workflow_config.get("source") == "runninghub" and "workflow_id" in workflow_config:
            workflow_input = workflow_config["workflow_id"]
        else:
            workflow_input = str(second_workflow_path)
        
        # Log workflow execution details for debugging
        logger.info(f"执行数字人工作流: source={workflow_source}, workflow_id={workflow_config.get('workflow_id', 'N/A')}")
        logger.info(f"工作流输入参数: {workflow_params}")
        
        result = await kit.execute(workflow_input, workflow_params)
        
        # Save raw result for debugging
        try:
            result_debug_path = os.path.join(params.task_dir, "human_workflow_result.json")
            with open(result_debug_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump() if hasattr(result, "model_dump") else dict(result), f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"工作流执行结果已保存: {result_debug_path}")
        except Exception as dump_err:
            logger.warning(f"保存工作流结果调试文件失败: {dump_err}")
        
        # Check workflow execution status
        result_status = getattr(result, "status", "unknown")
        result_msg = getattr(result, "msg", None)
        if result_status != "completed":
            logger.error(f"数字人工作流执行未成功: status={result_status}, msg={result_msg}")
            raise RuntimeError(
                f"数字人工作流执行失败 (status={result_status})。"
                f"{f' 详情: {result_msg}' if result_msg else ''}"
                "请检查 ComfyUI 节点、模型是否已正确安装，或查看日志中的 human_workflow_result.json。"
            )
        
        # Extract video URL
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
        
        human_video_path = os.path.join(params.task_dir, "human_raw.mp4")
        
        # Handle both local paths and URLs
        if os.path.exists(generated_video_url):
            # Local file path
            shutil.copy(generated_video_url, human_video_path)
        elif generated_video_url.startswith("http://") or generated_video_url.startswith("https://"):
            # URL: download
            import httpx
            timeout = httpx.Timeout(300.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(generated_video_url)
                response.raise_for_status()
                with open(human_video_path, "wb") as f:
                    f.write(response.content)
        else:
            raise RuntimeError(f"数字人工作流返回的视频路径格式无法识别: {generated_video_url}")
        
        return human_video_path
    
    def _prepare_human_video(
        self,
        human_video: str,
        target_duration: float,
        output_path: str
    ) -> str:
        """Scale and pad/trim human video to match target duration"""
        human_duration = self._get_video_duration(human_video)
        pad_duration = max(0, target_duration - human_duration)
        
        try:
            if pad_duration > 0.1:
                # Pad with frozen last frame
                (
                    ffmpeg
                    .input(human_video)
                    .filter("tpad", stop_mode="clone", stop_duration=pad_duration)
                    .output(
                        output_path,
                        t=target_duration,
                        vcodec="libx264",
                        pix_fmt="yuv420p",
                        preset="fast",
                        crf=23
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            elif human_duration > target_duration + 0.1:
                # Trim to target duration
                (
                    ffmpeg
                    .input(human_video, t=target_duration)
                    .output(
                        output_path,
                        vcodec="copy",
                        acodec="copy"
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # Already matching, just copy
                shutil.copy(human_video, output_path)
            
            return output_path
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"准备数字人视频失败: {error_msg}")
            raise RuntimeError(f"准备数字人视频失败: {error_msg}")
    
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
        
        # Prepare human video to match target duration
        prepared_human_video = os.path.join(params.task_dir, "human_prepared.mp4")
        self._prepare_human_video(human_video, target_duration, prepared_human_video)
        
        # Calculate human overlay size and position
        human_width = int(params.width * params.human_scale)
        
        # Use ffmpeg overlay variables: W/H = canvas, w/h = scaled overlay
        if params.human_anchor == "bottom-right":
            x_expr = f"W-w-{params.width * params.human_offset_x}"
            y_expr = f"H-h-{params.height * params.human_offset_y}"
        else:
            x_expr = f"W-w-{params.width * params.human_offset_x}"
            y_expr = f"H-h-{params.height * params.human_offset_y}"
        
        try:
            filter_complex = (
                f"[1:v]scale={human_width}:-1:flags=lanczos[human];"
                f"[0:v][human]overlay={x_expr}:{y_expr}:format=auto[video]"
            )
            
            cmd = [
                "ffmpeg",
                "-y",
                "-i", background_video,
                "-i", prepared_human_video,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[video]",
                "-map", "2:a",
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


# Type hint for pixelle_video
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pixelle_video.core import PixelleVideoCore
