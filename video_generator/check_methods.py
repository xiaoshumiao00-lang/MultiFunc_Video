#!/usr/bin/env python3
import os
os.environ['QUIET'] = '1'
from qwen_tts import Qwen3TTSModel
methods = [m for m in dir(Qwen3TTSModel) if not m.startswith('_')]
print('可用方法:', methods)