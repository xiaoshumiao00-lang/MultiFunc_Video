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
FastAPI Dependencies

Provides dependency injection for MultiFuncVideoCore and other services.
"""

from typing import Annotated
from fastapi import Depends
from loguru import logger

from multifunc_video.service import MultiFuncVideoCore


# Global MultiFunc_Video instance
_multifunc_video_instance: MultiFuncVideoCore = None


async def get_multifunc_video() -> MultiFuncVideoCore:
    """
    Get MultiFunc_Video core instance (dependency injection)
    
    Returns:
        MultiFuncVideoCore instance
    """
    global _multifunc_video_instance
    
    if _multifunc_video_instance is None:
        _multifunc_video_instance = MultiFuncVideoCore()
        await _multifunc_video_instance.initialize()
        logger.info("✅ MultiFunc_Video initialized for API")
    
    return _multifunc_video_instance


async def shutdown_multifunc_video():
    """Shutdown MultiFunc_Video instance and cleanup resources"""
    global _multifunc_video_instance
    if _multifunc_video_instance:
        logger.info("Shutting down MultiFunc_Video...")
        await _multifunc_video_instance.cleanup()
        _multifunc_video_instance = None


# Type alias for dependency injection
MultiFuncVideoDep = Annotated[MultiFuncVideoCore, Depends(get_multifunc_video)]

