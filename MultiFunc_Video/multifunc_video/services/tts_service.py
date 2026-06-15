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
TTS (Text-to-Speech) Service - Supports local, ComfyUI, and GPT-SoVITS inference
"""

import asyncio
import os
import uuid
import time
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from comfykit import ComfyKit
from loguru import logger

from multifunc_video.services.comfy_base_service import ComfyBaseService
from multifunc_video.services.qwen3_tts_service import Qwen3TTSService, get_qwen3_tts_service
from multifunc_video.utils.tts_util import edge_tts
from multifunc_video.tts_voices import speed_to_rate


class TTSService(ComfyBaseService):
    """
    TTS (Text-to-Speech) service - Workflow-based
    
    Uses ComfyKit to execute TTS workflows.
    
    Usage:
        # Use default workflow
        audio_path = await multifunc_video.tts(text="Hello, world!")
        
        # Use specific workflow
        audio_path = await multifunc_video.tts(
            text="你好，世界！",
            workflow="tts_edge.json"
        )
        
        # List available workflows
        workflows = multifunc_video.tts.list_workflows()
    """
    
    WORKFLOW_PREFIX = "tts_"
    DEFAULT_WORKFLOW = None  # No hardcoded default, must be configured
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        Initialize TTS service
        
        Args:
            config: Full application config dict
            core: MultiFuncVideoCore instance (for accessing shared ComfyKit)
        """
        super().__init__(config, service_name="tts", core=core)
    
    
    async def __call__(
        self,
        text: str,
        workflow: Optional[str] = None,
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        # TTS parameters
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        # Inference mode override
        inference_mode: Optional[str] = None,
        # Output path
        output_path: Optional[str] = None,
        # GPT-SoVITS parameters
        gpt_sovits_project_path: Optional[str] = None,
        gpt_sovits_api_url: Optional[str] = None,
        gpt_sovits_ref_audio: Optional[str] = None,
        gpt_sovits_prompt_text: Optional[str] = None,
        gpt_sovits_prompt_lang: Optional[str] = None,
        gpt_sovits_text_lang: Optional[str] = None,
        # Qwen3-TTS parameters
        qwen3_tts_model_path: Optional[str] = None,
        qwen3_tts_device: Optional[str] = None,
        qwen3_tts_ref_audio: Optional[str] = None,
        qwen3_tts_prompt_text: Optional[str] = None,
        qwen3_tts_speaker: Optional[str] = None,
        qwen3_tts_language: Optional[str] = None,
        # Lifecycle control (mainly for GPT-SoVITS / Qwen3-TTS batch usage)
        auto_shutdown: bool = True,
        **params
    ) -> str:
        """
        Generate speech using local Edge TTS, ComfyUI workflow, GPT-SoVITS, or Qwen3-TTS.

        Args:
            text: Text to convert to speech
            workflow: Workflow filename (for ComfyUI mode, default: from config)
            comfyui_url: ComfyUI URL (optional, overrides config)
            runninghub_api_key: RunningHub API key (optional, overrides config)
            voice: Voice ID (for local mode: Edge TTS voice ID; for ComfyUI: workflow-specific)
            speed: Speech speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)
            inference_mode: Override inference mode ("local", "comfyui", "gpt_sovits", or "qwen3_tts", default: from config)
            output_path: Custom output path (auto-generated if None)
            gpt_sovits_project_path: GPT-SoVITS project root path (overrides config)
            gpt_sovits_api_url: GPT-SoVITS API URL (overrides config)
            gpt_sovits_ref_audio: Reference audio path for voice cloning
            gpt_sovits_prompt_text: Reference audio transcription text
            gpt_sovits_prompt_lang: Reference audio language
            gpt_sovits_text_lang: Synthesis text language
            qwen3_tts_model_path: Qwen3-TTS model root path (overrides config)
            qwen3_tts_device: Device to run Qwen3-TTS on (overrides config)
            qwen3_tts_ref_audio: Reference audio path for Qwen3-TTS voice cloning
            qwen3_tts_prompt_text: Reference audio transcription for Qwen3-TTS
            qwen3_tts_speaker: Predefined speaker name for Qwen3-TTS CustomVoice models
            qwen3_tts_language: Language for Qwen3-TTS synthesis
            auto_shutdown: If False, keep GPT-SoVITS API / Qwen3-TTS model loaded after this call
                (caller is responsible for shutting it down)
            **params: Additional workflow parameters

        Returns:
            Generated audio file path
        """
        # Determine inference mode (param > config)
        mode = inference_mode or self.config.get("inference_mode", "local")
        
        # Route to appropriate implementation
        if mode == "local":
            return await self._call_local_tts(
                text=text,
                voice=voice,
                speed=speed,
                output_path=output_path
            )
        elif mode == "gpt_sovits":
            return await self._call_gpt_sovits_tts(
                text=text,
                speed=speed,
                output_path=output_path,
                project_path=gpt_sovits_project_path,
                api_url=gpt_sovits_api_url,
                ref_audio=gpt_sovits_ref_audio,
                prompt_text=gpt_sovits_prompt_text,
                prompt_lang=gpt_sovits_prompt_lang,
                text_lang=gpt_sovits_text_lang,
                auto_shutdown=auto_shutdown,
            )
        elif mode == "qwen3_tts":
            return await self._call_qwen3_tts(
                text=text,
                speed=speed,
                output_path=output_path,
                model_path=qwen3_tts_model_path,
                device=qwen3_tts_device,
                ref_audio=qwen3_tts_ref_audio,
                prompt_text=qwen3_tts_prompt_text,
                speaker=qwen3_tts_speaker,
                language=qwen3_tts_language,
                auto_shutdown=auto_shutdown,
            )
        else:  # comfyui
            # 1. Resolve workflow (returns structured info)
            workflow_info = self._resolve_workflow(workflow=workflow)
            
            # 2. Execute ComfyUI workflow
            return await self._call_comfyui_workflow(
                workflow_info=workflow_info,
                text=text,
                comfyui_url=comfyui_url,
                runninghub_api_key=runninghub_api_key,
                voice=voice,
                speed=speed,
                output_path=output_path,
                **params
            )
    
    async def _call_local_tts(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate speech using local Edge TTS
        
        Args:
            text: Text to convert to speech
            voice: Edge TTS voice ID (default: from config)
            speed: Speech speed multiplier (default: from config)
            output_path: Custom output path (auto-generated if None)
        
        Returns:
            Generated audio file path
        """
        # Get config defaults
        local_config = self.config.get("local", {})
        
        # Determine voice and speed (param > config)
        final_voice = voice or local_config.get("voice", "zh-CN-YunjianNeural")
        final_speed = speed if speed is not None else local_config.get("speed", 1.2)
        
        # Convert speed to rate parameter
        rate = speed_to_rate(final_speed)
        
        logger.info(f"🎙️  Using local Edge TTS: voice={final_voice}, speed={final_speed}x (rate={rate})")
        
        # Generate output path if not provided
        if not output_path:
            # Generate unique filename
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.mp3"
            
            # Ensure output directory exists
            Path("output").mkdir(parents=True, exist_ok=True)
        
        # Call Edge TTS
        try:
            audio_bytes = await edge_tts(
                text=text,
                voice=final_voice,
                rate=rate,
                output_path=output_path
            )
            
            logger.info(f"✅ Generated audio (local Edge TTS): {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"Local TTS generation error: {e}")
            raise
    
    async def _call_comfyui_workflow(
        self,
        workflow_info: dict,
        text: str,
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_path: Optional[str] = None,
        **params
    ) -> str:
        """
        Generate speech using ComfyUI workflow
        
        Args:
            workflow_info: Workflow info dict from _resolve_workflow()
            text: Text to convert to speech
            comfyui_url: ComfyUI URL
            runninghub_api_key: RunningHub API key
            voice: Voice ID (workflow-specific)
            speed: Speech speed multiplier (workflow-specific)
            output_path: Custom output path (downloads if URL returned)
            **params: Additional workflow parameters
        
        Returns:
            Generated audio file path (local if output_path provided, otherwise URL)
        """
        logger.info(f"🎙️  Using workflow: {workflow_info['key']}")
        
        # 1. Build workflow parameters (ComfyKit config is now managed by core)
        workflow_params = {"text": text}
        
        # Add optional TTS parameters (only if explicitly provided and not None)
        if voice is not None:
            workflow_params["voice"] = voice
        if speed is not None and speed != 1.0:
            workflow_params["speed"] = speed
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 3. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "runninghub" and "workflow_id" in workflow_info:
                # RunningHub: pass workflow_id
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing RunningHub TTS workflow: {workflow_input}")
            else:
                # Selfhost: pass file path
                workflow_input = workflow_info["path"]
                logger.info(f"Executing selfhost TTS workflow: {workflow_input}")
            
            result = await kit.execute(workflow_input, workflow_params)
            
            # 4. Handle result
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"TTS generation failed: {error_msg}")
                raise Exception(f"TTS generation failed: {error_msg}")
            
            # ComfyKit result can have audio files in different output types
            # Try to get audio file path from result
            audio_path = None
            
            # Check for audio files in result.audios (if available)
            if hasattr(result, 'audios') and result.audios:
                audio_path = result.audios[0]
                logger.debug(f"✅ Found audio in result.audios: {audio_path}")
            # Check for files in result.files
            elif hasattr(result, 'files') and result.files:
                audio_path = result.files[0]
                logger.debug(f"✅ Found audio in result.files: {audio_path}")
            # Check in outputs dictionary
            elif hasattr(result, 'outputs') and result.outputs:
                logger.debug(f"Searching for audio file in result.outputs: {result.outputs}")
                # Try to find audio file in outputs
                for key, value in result.outputs.items():
                    if isinstance(value, str) and any(value.endswith(ext) for ext in ['.mp3', '.wav', '.flac']):
                        audio_path = value
                        logger.debug(f"✅ Found audio in result.outputs[{key}]: {audio_path}")
                        break
            
            if not audio_path:
                logger.error("No audio file generated")
                logger.error(f"❌ Result analysis:")
                logger.error(f"   - result.audios: {getattr(result, 'audios', 'NOT_FOUND')}")
                logger.error(f"   - result.files: {getattr(result, 'files', 'NOT_FOUND')}")
                logger.error(f"   - result.outputs: {getattr(result, 'outputs', 'NOT_FOUND')}")
                logger.error(f"   - Full __dict__: {result.__dict__}")
                raise Exception("No audio file generated by workflow")
            
            # If output_path provided and audio_path is URL, download to local
            if output_path and audio_path.startswith(('http://', 'https://')):
                import httpx
                import os
                
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                logger.info(f"Downloading audio from {audio_path} to {output_path}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_path)
                    response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                
                logger.info(f"✅ Generated audio (ComfyUI): {output_path}")
                return output_path
            
            logger.info(f"✅ Generated audio (ComfyUI): {audio_path}")
            return audio_path
        
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            raise

    # ========================================================================
    # Qwen3-TTS
    # ========================================================================

    _qwen3_tts_service: Optional[Qwen3TTSService] = None

    async def _call_qwen3_tts(
        self,
        text: str,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        ref_audio: Optional[str] = None,
        prompt_text: Optional[str] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        auto_shutdown: bool = True,
    ) -> str:
        """
        Generate speech using local Qwen3-TTS (auto-load model, auto-unload after).

        Args:
            text: Text to convert to speech
            speed: Speech speed multiplier
            output_path: Custom output path (auto-generated if None)
            model_path: Qwen3-TTS model root path (overrides config)
            device: Device to run the model on (overrides config)
            ref_audio: Reference audio path for voice cloning
            prompt_text: Reference audio transcription
            speaker: Predefined speaker name (for CustomVoice models)
            language: Synthesis language
            auto_shutdown: If False, keep the model loaded for subsequent calls
                (caller must call unload_qwen3_tts_model later)

        Returns:
            Generated audio file path
        """
        qwen_config = self.config.get("qwen3_tts", {})
        final_model_path = model_path or qwen_config.get("model_path", "")
        final_device = device or qwen_config.get("device", "cuda")
        final_ref_audio = ref_audio or qwen_config.get("default_ref_audio") or None
        final_prompt_text = prompt_text or qwen_config.get("default_prompt_text", "")
        final_speaker = speaker or qwen_config.get("speaker") or None
        final_language = language or qwen_config.get("language", "Auto")
        final_speed = speed if speed is not None else qwen_config.get("speed", 1.0)

        if not final_model_path:
            raise ValueError(
                "Qwen3-TTS 模型路径未配置，请在设置中填写 model_path"
            )

        if not output_path:
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.wav"
            Path("output").mkdir(parents=True, exist_ok=True)

        if not output_path.endswith(".wav"):
            output_path = output_path.rsplit(".", 1)[0] + ".wav"

        try:
            service = self._ensure_qwen3_tts_service(
                model_path=final_model_path,
                device=final_device,
                ref_audio_path=final_ref_audio,
                prompt_text=final_prompt_text,
                speaker=final_speaker,
                language=final_language,
                speed=final_speed,
            )

            logger.info(
                f"🎙️  Using Qwen3-TTS: model_path={final_model_path}, "
                f"ref_audio={final_ref_audio}, speed={final_speed}"
            )

            # Run blocking inference in a thread pool to keep the event loop responsive
            import functools
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None,
                functools.partial(
                    service.synthesize,
                    text=text,
                    output_path=output_path,
                    ref_audio_path=final_ref_audio,
                    prompt_text=final_prompt_text,
                    speaker=final_speaker,
                    language=final_language,
                    speed=final_speed,
                ),
            )

            logger.info(f"✅ Generated audio (Qwen3-TTS): {audio_path}")
            return audio_path

        finally:
            if auto_shutdown:
                self.unload_qwen3_tts_model()

    def _ensure_qwen3_tts_service(
        self,
        model_path: str,
        device: str,
        ref_audio_path: Optional[str],
        prompt_text: str,
        speaker: Optional[str],
        language: str,
        speed: float,
    ) -> Qwen3TTSService:
        """Return the existing Qwen3-TTS service or create and load a new one."""
        if TTSService._qwen3_tts_service is not None:
            service = TTSService._qwen3_tts_service
            # If the model path changed, unload and recreate
            if service.model_path != model_path:
                logger.info("Qwen3-TTS model path changed, reloading")
                Qwen3TTSService.unload()
                TTSService._qwen3_tts_service = None
            else:
                return service

        service = Qwen3TTSService(
            model_path=model_path,
            device=device,
            ref_audio_path=ref_audio_path,
            prompt_text=prompt_text,
            speaker=speaker,
            language=language,
            speed=speed,
        )
        service.load()
        TTSService._qwen3_tts_service = service
        return service

    def unload_qwen3_tts_model(self) -> None:
        """Unload the Qwen3-TTS model and release GPU memory."""
        Qwen3TTSService.unload()
        TTSService._qwen3_tts_service = None

    async def start_qwen3_tts_model(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
    ) -> bool:
        """
        Ensure Qwen3-TTS model is loaded for batch TTS calls.

        Returns:
            True if the model was loaded by this call, False if already loaded.
        """
        qwen_config = self.config.get("qwen3_tts", {})
        final_model_path = model_path or qwen_config.get("model_path", "")
        final_device = device or qwen_config.get("device", "cuda")

        if TTSService._qwen3_tts_service is not None:
            if TTSService._qwen3_tts_service.model_path == final_model_path:
                return False
            Qwen3TTSService.unload()
            TTSService._qwen3_tts_service = None

        service = Qwen3TTSService(
            model_path=final_model_path,
            device=final_device,
        )
        service.load()
        TTSService._qwen3_tts_service = service
        return True

    async def stop_qwen3_tts_model(self) -> None:
        """Shutdown Qwen3-TTS model and release GPU memory."""
        self.unload_qwen3_tts_model()

    # ========================================================================
    # GPT-SoVITS TTS
    # ========================================================================

    # Class-level tracking for GPT-SoVITS subprocess
    _gpt_sovits_process: Optional[subprocess.Popen] = None
    _gpt_sovits_api_base_url: Optional[str] = None

    async def _call_gpt_sovits_tts(
        self,
        text: str,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
        project_path: Optional[str] = None,
        api_url: Optional[str] = None,
        ref_audio: Optional[str] = None,
        prompt_text: Optional[str] = None,
        prompt_lang: Optional[str] = None,
        text_lang: Optional[str] = None,
        auto_shutdown: bool = True,
    ) -> str:
        """
        Generate speech using GPT-SoVITS (auto-start API if needed, auto-shutdown after)

        Args:
            text: Text to convert to speech
            speed: Speech speed multiplier
            output_path: Custom output path (auto-generated if None)
            project_path: GPT-SoVITS project root path
            api_url: GPT-SoVITS API URL
            ref_audio: Reference audio path for voice cloning
            prompt_text: Reference audio transcription
            prompt_lang: Reference audio language
            text_lang: Synthesis text language
            auto_shutdown: If False, leave the API running for subsequent calls
                (caller must call stop_gpt_sovits_api later)

        Returns:
            Generated audio file path
        """
        # Get config defaults
        sovits_config = self.config.get("gpt_sovits", {})
        final_project_path = project_path or sovits_config.get("project_path", "")
        final_api_url = api_url or sovits_config.get("api_url", "http://127.0.0.1:9880")
        final_text_lang = text_lang or sovits_config.get("text_lang", "zh")
        final_prompt_lang = prompt_lang or sovits_config.get("prompt_lang", "zh")
        final_speed = speed if speed is not None else sovits_config.get("speed_factor", 1.0)
        top_k = sovits_config.get("top_k", 15)
        top_p = sovits_config.get("top_p", 1.0)
        temperature = sovits_config.get("temperature", 1.0)

        # Validate reference audio (required by GPT-SoVITS v2 API)
        if not ref_audio:
            raise ValueError(
                "GPT-SoVITS 合成需要提供参考音频（ref_audio），"
                "请在配音设置中上传参考音频文件"
            )

        # Generate output path if not provided
        if not output_path:
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.wav"
            Path("output").mkdir(parents=True, exist_ok=True)

        # Ensure output is wav (GPT-SoVITS outputs wav by default)
        if not output_path.endswith(".wav"):
            output_path = output_path.rsplit(".", 1)[0] + ".wav"

        # Pre-convert reference audio to WAV at a clean path.
        # GPT-SoVITS uses torchaudio.load / librosa.load internally, which
        # can fail with [Errno 22] Invalid argument on Windows when the path
        # contains Chinese characters or the file is MP3.
        clean_ref_audio = self._prepare_ref_audio_for_sovits(ref_audio)

        # Step 1: Ensure GPT-SoVITS API is running
        api_started_by_us = False
        max_retries = 3
        last_exception = None

        try:
            for attempt in range(max_retries):
                try:
                    # Give the API a short breath between consecutive calls
                    if attempt > 0:
                        await asyncio.sleep(2 ** attempt)

                    api_started_by_us = await self._ensure_gpt_sovits_api_running(
                        final_project_path, final_api_url
                    )

                    # Step 2: Call GPT-SoVITS /tts API (v2)
                    logger.info(
                        f"🎙️  Using GPT-SoVITS (attempt {attempt + 1}/{max_retries}): "
                        f"ref_audio={clean_ref_audio}, speed={final_speed}"
                    )

                    request_payload = {
                        "text": text,
                        "text_lang": final_text_lang,
                        "ref_audio_path": clean_ref_audio,
                        "prompt_text": prompt_text or "",
                        "prompt_lang": final_prompt_lang,
                        "top_k": top_k,
                        "top_p": top_p,
                        "temperature": temperature,
                        "text_split_method": "cut5",
                        "speed_factor": final_speed,
                        "batch_size": 1,
                        "media_type": "wav",
                        "streaming_mode": False,
                    }

                    logger.debug(f"GPT-SoVITS request payload: text={text!r}, "
                                 f"text_lang={final_text_lang}, ref_audio_path={clean_ref_audio}")

                    timeout = httpx.Timeout(
                        connect=10.0, read=600.0, write=10.0, pool=10.0
                    )
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{final_api_url}/tts",
                            json=request_payload,
                        )

                    if response.status_code != 200:
                        error_msg = f"GPT-SoVITS API error: HTTP {response.status_code}"
                        try:
                            error_detail = response.json()
                            error_msg = f"{error_msg} - {error_detail}"
                        except Exception:
                            error_msg = f"{error_msg} - {response.text[:500]}"
                        raise Exception(error_msg)

                    # Save audio to output path
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(response.content)

                    logger.info(f"✅ Generated audio (GPT-SoVITS): {output_path}")
                    return output_path

                except (httpx.ReadTimeout, httpx.ConnectError, httpx.TimeoutException) as e:
                    last_exception = e
                    logger.warning(
                        f"GPT-SoVITS TTS request failed (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt == max_retries - 1:
                        raise last_exception
                except Exception as e:
                    # Also retry on API-level errors (HTTP 400 etc.)
                    # GPT-SoVITS may have internal state corruption — fully
                    # restart the API to get a clean state.
                    error_str = str(e)
                    if "HTTP 400" in error_str or "tts failed" in error_str or "Invalid argument" in error_str:
                        last_exception = e
                        logger.warning(
                            f"GPT-SoVITS TTS API error (attempt {attempt + 1}/{max_retries}): {e}"
                            f" — restarting API"
                        )
                        # Fully restart the API to clear corrupted internal state
                        try:
                            await self._shutdown_gpt_sovits_api(final_api_url)
                        except Exception:
                            pass
                        await asyncio.sleep(3.0)
                        TTSService._gpt_sovits_process = None
                        TTSService._gpt_sovits_api_base_url = None
                        api_started_by_us = False
                        if attempt == max_retries - 1:
                            raise last_exception
                    else:
                        raise

        finally:
            # Step 3: Auto-shutdown API if we started it and caller requested it
            if auto_shutdown and api_started_by_us:
                await self._shutdown_gpt_sovits_api(final_api_url)

    def _prepare_ref_audio_for_sovits(self, ref_audio_path: str) -> str:
        """
        Prepare reference audio for GPT-SoVITS by converting to WAV
        and saving to a clean ASCII-only path.

        GPT-SoVITS uses torchaudio.load / librosa.load internally, which
        can fail with ``[Errno 22] Invalid argument`` on Windows when the
        path contains Chinese characters or the file is MP3.

        Returns:
            Path to the prepared WAV file (may be the original if already
            a clean WAV).
        """
        if not ref_audio_path or not os.path.isfile(ref_audio_path):
            return ref_audio_path

        # If the path is already ASCII-only AND the file is WAV, use as-is
        try:
            ref_audio_path.encode("ascii")
            if ref_audio_path.lower().endswith(".wav"):
                return ref_audio_path
        except UnicodeEncodeError:
            pass

        # Convert to WAV at a clean temp path
        import hashlib
        import ffmpeg as _ffmpeg

        # Stable filename based on original path hash so we don't re-convert
        path_hash = hashlib.md5(ref_audio_path.encode("utf-8")).hexdigest()[:12]
        temp_dir = os.path.join(tempfile.gettempdir(), "multifunc_sovits_ref")
        os.makedirs(temp_dir, exist_ok=True)
        wav_path = os.path.join(temp_dir, f"ref_{path_hash}.wav")

        if os.path.isfile(wav_path):
            logger.debug(f"Reusing cached ref audio: {wav_path}")
            return wav_path

        logger.info(f"Converting ref audio to clean WAV: {ref_audio_path} -> {wav_path}")
        try:
            (
                _ffmpeg
                .input(ref_audio_path)
                .output(wav_path, acodec="pcm_s16le", ar=16000, ac=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except _ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Failed to convert ref audio: {error_msg}")
            # Fall back to original path — the API call might still work
            return ref_audio_path

        return wav_path

    async def _ensure_gpt_sovits_api_running(
        self, project_path: str, api_url: str
    ) -> bool:
        """
        Check if GPT-SoVITS API is running; start it if not.

        Returns:
            True if API was started by us (caller should shut it down after use),
            False if API was already running.
        """
        # Check if API is already running
        # Note: GPT-SoVITS api_v2.py does not define a root route (/).
        # FastAPI's auto-generated /docs endpoint is used as a lightweight health check.
        health_url = f"{api_url}/docs"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info("GPT-SoVITS API is already running")
                    return False
        except (httpx.ConnectError, httpx.TimeoutException):
            pass  # API not running, need to start it

        # Validate project path
        if not project_path or not os.path.isdir(project_path):
            raise FileNotFoundError(
                f"GPT-SoVITS 项目路径不存在: {project_path}\n"
                "请在配音设置中配置正确的 GPT-SoVITS 项目路径"
            )

        api_v2_path = os.path.join(project_path, "api_v2.py")
        if not os.path.isfile(api_v2_path):
            raise FileNotFoundError(
                f"在 {project_path} 下未找到 api_v2.py\n"
                "请确认 GPT-SoVITS 项目路径正确"
            )

        # Find runtime python
        runtime_python = os.path.join(project_path, "runtime", "python.exe")
        if not os.path.isfile(runtime_python):
            # Fall back to system python
            import sys
            runtime_python = sys.executable
            logger.warning(f"GPT-SoVITS runtime/python.exe not found, using: {runtime_python}")

        # Parse port from api_url
        from urllib.parse import urlparse
        parsed = urlparse(api_url)
        port = parsed.port or 9880
        host = parsed.hostname or "127.0.0.1"

        logger.info(f"🚀 Starting GPT-SoVITS API server on {host}:{port}...")
        logger.info(f"   Project path: {project_path}")

        # Start api_v2.py as a subprocess
        # IMPORTANT: Do NOT use subprocess.PIPE for stdout/stderr on Windows.
        # GPT-SoVITS uses tqdm which calls sys.stdout.flush(); when stdout is
        # a pipe with gbk encoding this raises OSError: [Errno 22] Invalid argument
        # and crashes the API worker in the middle of a TTS request. Instead,
        # redirect both streams to a log file so tqdm has a valid file descriptor.
        log_dir = os.path.join(project_path, "runtime_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(
            log_dir,
            f"multifunc_api_{time.strftime('%Y%m%d_%H%M%S')}.log"
        )

        try:
            # Build a clean environment for the GPT-SoVITS process:
            # - PYTHONPATH = project_path so that GPT_SoVITS modules are importable
            # - PATH is inherited (runtime python needs its own DLLs on the path)
            sovits_env = os.environ.copy()
            sovits_env["PYTHONPATH"] = project_path

            log_file = open(log_path, "w", encoding="utf-8", errors="replace")
            process = subprocess.Popen(
                [runtime_python, "api_v2.py", "-a", host, "-p", str(port)],
                cwd=project_path,
                env=sovits_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            TTSService._gpt_sovits_process = process
            TTSService._gpt_sovits_api_base_url = api_url
            TTSService._gpt_sovits_log_file = log_file

            # Wait for API to become ready (with timeout)
            # GPT-SoVITS can take a while to load T2S/VITS/BERT/HuBERT weights on first start.
            max_wait = 300  # seconds - model loading can take time
            start_time = time.time()
            while time.time() - start_time < max_wait:
                # Check if the process crashed before bothering the API
                poll_result = process.poll()
                if poll_result is not None:
                    log_tail = ""
                    try:
                        log_file.flush()
                        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                            log_tail = f.read()[-2000:]
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"GPT-SoVITS API 启动失败（进程已退出，退出码: {poll_result}）\n"
                        f"日志文件: {log_path}\n"
                        f"日志尾部: {log_tail}"
                    )

                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                        response = await client.get(health_url)
                        if response.status_code == 200:
                            elapsed = time.time() - start_time
                            logger.info(
                                f"✅ GPT-SoVITS API started successfully "
                                f"(took {elapsed:.1f}s)"
                            )
                            return True
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass

                time.sleep(2)

            # Timeout - kill the process
            try:
                process.terminate()
            except Exception:
                pass
            raise TimeoutError(
                f"GPT-SoVITS API 启动超时（等待了 {max_wait}s）。"
                f"可能原因：模型首次加载较慢、磁盘 I/O 瓶颈或 GPU 初始化耗时。"
                f"建议：1) 先手动运行 '{runtime_python} api_v2.py -a {host} -p {port}' 观察加载进度；"
                f"2) 检查 {project_path}/runtime_logs 下的日志；"
                f"3) 确认 models/ 下的预训练模型文件完整。"
            )

        except (FileNotFoundError, RuntimeError, TimeoutError):
            raise
        except Exception as e:
            raise RuntimeError(f"GPT-SoVITS API 启动异常: {e}")

    async def _shutdown_gpt_sovits_api(self, api_url: str) -> None:
        """
        Gracefully shutdown GPT-SoVITS API and release GPU memory.
        """
        logger.info("🔄 Shutting down GPT-SoVITS API to release GPU memory...")

        # Try graceful shutdown via API
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                await client.get(f"{api_url}/control", params={"command": "exit"})
                logger.info("✅ Sent exit command to GPT-SoVITS API")
        except Exception as e:
            logger.debug(f"Could not send exit command: {e}")

        # Wait briefly, then force-kill if still running
        time.sleep(2)

        process = TTSService._gpt_sovits_process
        if process is not None:
            poll_result = process.poll()
            if poll_result is None:
                # Process still running - force kill
                try:
                    if os.name == "nt":
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    process.wait(timeout=10)
                    logger.info("✅ GPT-SoVITS API process terminated")
                except Exception as e:
                    try:
                        process.kill()
                        logger.warning(f"Force-killed GPT-SoVITS process: {e}")
                    except Exception:
                        pass

            TTSService._gpt_sovits_process = None
            TTSService._gpt_sovits_api_base_url = None

        log_file = getattr(TTSService, "_gpt_sovits_log_file", None)
        if log_file is not None:
            try:
                log_file.close()
            except Exception:
                pass
            TTSService._gpt_sovits_log_file = None

        logger.info("✅ GPT-SoVITS GPU memory released")

    async def start_gpt_sovits_api(
        self,
        project_path: Optional[str] = None,
        api_url: Optional[str] = None,
    ) -> bool:
        """
        Ensure GPT-SoVITS API is running for batch TTS calls.

        Returns:
            True if the API was started by this call, False if already running.
        """
        sovits_config = self.config.get("gpt_sovits", {})
        final_project_path = project_path or sovits_config.get("project_path", "")
        final_api_url = api_url or sovits_config.get("api_url", "http://127.0.0.1:9880")
        return await self._ensure_gpt_sovits_api_running(
            final_project_path, final_api_url
        )

    async def stop_gpt_sovits_api(self, api_url: Optional[str] = None) -> None:
        """
        Shutdown GPT-SoVITS API and release GPU memory.

        Call this once after a batch of TTS calls when auto_shutdown=False.
        """
        sovits_config = self.config.get("gpt_sovits", {})
        final_api_url = api_url or sovits_config.get("api_url", "http://127.0.0.1:9880")
        await self._shutdown_gpt_sovits_api(final_api_url)
