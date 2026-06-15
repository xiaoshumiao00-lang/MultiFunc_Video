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
TTS (Text-to-Speech) endpoints
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import MultiFuncVideoDep
from api.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from multifunc_video.utils.tts_util import get_audio_duration

router = APIRouter(prefix="/tts", tags=["Basic Services"])


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def tts_synthesize(
    request: TTSSynthesizeRequest,
    multifunc_video: MultiFuncVideoDep
):
    """
    Text-to-Speech synthesis endpoint
    
    Convert text to speech audio using ComfyUI workflows.
    
    - **text**: Text to synthesize
    - **workflow**: TTS workflow key (optional, uses default if not specified)
    - **ref_audio**: Reference audio for voice cloning (optional)
    - **voice_id**: (Deprecated) Voice ID for legacy compatibility
    
    Returns path to generated audio file and duration.
    
    Examples:
    ```json
    {
        "text": "Hello, welcome to MultiFunc_Video!",
        "workflow": "runninghub/tts_edge.json"
    }
    ```
    
    With voice cloning:
    ```json
    {
        "text": "Hello, this is a cloned voice",
        "workflow": "runninghub/tts_index2.json",
        "ref_audio": "path/to/reference.wav"
    }
    ```
    """
    try:
        logger.info(f"TTS synthesis request: {request.text[:50]}...")
        
        # Build TTS parameters
        tts_params = {"text": request.text}
        
        # Add inference_mode if specified
        if request.inference_mode:
            tts_params["inference_mode"] = request.inference_mode
        
        # Add workflow if specified
        if request.workflow:
            tts_params["workflow"] = request.workflow
        
        # Add ref_audio if specified
        if request.ref_audio:
            tts_params["ref_audio"] = request.ref_audio
        
        # Legacy voice_id support (deprecated)
        if request.voice_id and not request.workflow:
            logger.warning("voice_id parameter is deprecated, please use workflow instead")
            tts_params["voice"] = request.voice_id
        
        # GPT-SoVITS parameters
        sovits_fields = {
            "gpt_sovits_project_path": request.gpt_sovits_project_path,
            "gpt_sovits_api_url": request.gpt_sovits_api_url,
            "gpt_sovits_ref_audio": request.gpt_sovits_ref_audio,
            "gpt_sovits_prompt_text": request.gpt_sovits_prompt_text,
            "gpt_sovits_prompt_lang": request.gpt_sovits_prompt_lang,
            "gpt_sovits_text_lang": request.gpt_sovits_text_lang,
        }
        for key, value in sovits_fields.items():
            if value is not None:
                tts_params[key] = value

        # Qwen3-TTS parameters
        qwen3_fields = {
            "qwen3_tts_model_path": request.qwen3_tts_model_path,
            "qwen3_tts_device": request.qwen3_tts_device,
            "qwen3_tts_ref_audio": request.qwen3_tts_ref_audio,
            "qwen3_tts_prompt_text": request.qwen3_tts_prompt_text,
            "qwen3_tts_speaker": request.qwen3_tts_speaker,
            "qwen3_tts_language": request.qwen3_tts_language,
        }
        for key, value in qwen3_fields.items():
            if value is not None:
                tts_params[key] = value

        # Call TTS service
        audio_path = await multifunc_video.tts(**tts_params)
        
        # Get audio duration
        duration = get_audio_duration(audio_path)
        
        return TTSSynthesizeResponse(
            audio_path=audio_path,
            duration=duration
        )
        
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

