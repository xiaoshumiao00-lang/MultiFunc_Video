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
TTS API schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


class TTSSynthesizeRequest(BaseModel):
    """TTS synthesis request"""
    text: str = Field(..., description="Text to synthesize")
    inference_mode: Optional[str] = Field(
        None,
        description="TTS inference mode: 'local', 'comfyui', or 'gpt_sovits'. If not specified, uses default from config."
    )
    workflow: Optional[str] = Field(
        None, 
        description="TTS workflow key (e.g., 'runninghub/tts_edge.json' or 'selfhost/tts_edge.json'). If not specified, uses default workflow from config."
    )
    ref_audio: Optional[str] = Field(
        None, 
        description="Reference audio path for voice cloning (optional). Can be a local file path or URL."
    )
    voice_id: Optional[str] = Field(
        None, 
        description="Voice ID (deprecated, use workflow instead)"
    )
    # GPT-SoVITS parameters
    gpt_sovits_project_path: Optional[str] = Field(None, description="GPT-SoVITS project root path")
    gpt_sovits_api_url: Optional[str] = Field(None, description="GPT-SoVITS API URL")
    gpt_sovits_ref_audio: Optional[str] = Field(None, description="GPT-SoVITS reference audio path for voice cloning")
    gpt_sovits_prompt_text: Optional[str] = Field(None, description="GPT-SoVITS reference audio transcription")
    gpt_sovits_prompt_lang: Optional[str] = Field(None, description="GPT-SoVITS reference audio language")
    gpt_sovits_text_lang: Optional[str] = Field(None, description="GPT-SoVITS synthesis text language")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, welcome to MultiFunc_Video!",
                "inference_mode": "local",
                "workflow": "runninghub/tts_edge.json",
                "ref_audio": None
            }
        }


class TTSSynthesizeResponse(BaseModel):
    """TTS synthesis response"""
    success: bool = True
    message: str = "Success"
    audio_path: str = Field(..., description="Path to generated audio file")
    duration: float = Field(..., description="Audio duration in seconds")

