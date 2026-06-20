# -*- coding: utf-8 -*-
"""
图文视频服务模块

集成本地 video-generator 引擎（AutoVideo 技能使用的视频生成引擎）。
源码已迁移到 MultiFunc_Video/video_generator/，运行时通过 wrapper 脚本调用
具有完整依赖（torch/cv2/edge-tts 等）的外部 Python 解释器执行。
支持：文案输入、参考音频音色克隆、可选背景音乐、视频风格、语速控制、
自动生成标题/摘要、一键上传到飞书多维表格。
"""

import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Callable
from datetime import datetime

from loguru import logger

from multifunc_video.utils.os_util import create_task_output_dir, get_temp_path

# video-generator 源码现在位于本项目内部
# __file__: MultiFunc_Video/multifunc_video/services/image_text_video_service.py
# parent x4 -> 项目根目录 MultiFunc_Video
DEFAULT_VIDEO_GENERATOR_PATH = Path(__file__).parent.parent.parent.parent / "video_generator"

# wrapper 脚本模板：在本项目 video_generator 目录内运行
# 参数通过 --params-json 传入的 JSON 文件传递
WRAPPER_SCRIPT = r'''# -*- coding: utf-8 -*-
"""
Auto-generated wrapper for MultiFunc_Video image-text-video pipeline.
Runs inside the embedded video_generator package to reuse its source code.
"""

import argparse
import json
import sys
from pathlib import Path

# 确保 wrapper 运行时能找到 video_generator 包内的模块
# __file__ 位于 MultiFunc_Video/video_generator/_multifunc_wrapper_*.py
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 动态修改配置（不修改 config.py 文件）
import config

parser = argparse.ArgumentParser()
parser.add_argument("--params-json", required=True, help="Path to params JSON file")
parser.add_argument("--result-json", required=True, help="Path to write result JSON file")
args = parser.parse_args()

with open(args.params_json, "r", encoding="utf-8") as f:
    params = json.load(f)

# 如果指定了输出目录，覆盖 config 中的输出路径
if params.get("output_root"):
    output_root = Path(params["output_root"])
    config.OUTPUTS_DIR = output_root / "outputs"
    config.IMAGES_DIR = config.OUTPUTS_DIR / "images"
    config.AUDIO_DIR = config.OUTPUTS_DIR / "audio"
    config.VIDEOS_DIR = config.OUTPUTS_DIR / "videos"
    for d in [config.OUTPUTS_DIR, config.IMAGES_DIR, config.AUDIO_DIR, config.VIDEOS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# 设置参考音频与语速（根据当前 TTS 模式）
print(f"[Wrapper] TTS_MODE: {config.TTS_MODE}")
print(f"[Wrapper] ref_audio param: {params.get('ref_audio')}")
print(f"[Wrapper] prompt_text param: {params.get('prompt_text')}")
if config.TTS_MODE == "gpt_sovits" and params.get("ref_audio"):
    config.GPT_SOVITS_SETTINGS["ref_audio_path"] = params["ref_audio"]
    if params.get("prompt_text") is not None:
        config.GPT_SOVITS_SETTINGS["prompt_text"] = params["prompt_text"]
    if params.get("speed") is not None:
        config.GPT_SOVITS_SETTINGS["speed"] = params["speed"]
elif config.TTS_MODE == "qwen_tts" and params.get("ref_audio"):
    config.QWEN_TTS_SETTINGS["ref_audio_path"] = params["ref_audio"]
    if params.get("prompt_text") is not None:
        config.QWEN_TTS_SETTINGS["prompt_text"] = params["prompt_text"]
    if params.get("speed") is not None:
        config.QWEN_TTS_SETTINGS["speed"] = params["speed"]
print(f"[Wrapper] QWEN_TTS ref_audio_path: {config.QWEN_TTS_SETTINGS.get('ref_audio_path')}")
print(f"[Wrapper] QWEN_TTS prompt_text: {config.QWEN_TTS_SETTINGS.get('prompt_text', '')[:100]}")

# Edge-TTS 使用 rate 字段控制语速
if config.TTS_MODE == "edge" and params.get("speed") is not None:
    speed = params["speed"]
    rate_percent = int(round((speed - 1.0) * 100))
    sign = "+" if rate_percent >= 0 else ""
    config.EDGE_TTS_SETTINGS["rate"] = f"{sign}{rate_percent}%"
    config.EDGE_TTS_SETTINGS["speed"] = speed

# 设置视频尺寸：默认竖屏 1080x1920，用户选择横屏则改为 1920x1080
if params.get("orientation") == "landscape":
    config.VIDEO_SETTINGS["width"] = 1920
    config.VIDEO_SETTINGS["height"] = 1080
else:
    config.VIDEO_SETTINGS["width"] = 1080
    config.VIDEO_SETTINGS["height"] = 1920

from utils.smart_video import SmartVideoGenerator

generator = SmartVideoGenerator(
    theme=params.get("theme") or None,
    tts_mode=config.TTS_MODE,
    use_comfyui=True,
    use_local_llm=True,
    local_llm_model=params.get("llm_model", "qwen3.5:9b"),
    auto_classify=params.get("theme") is None
)

print("[Progress] 1/10: 启动 video-generator")
result = generator.generate_sync(
    content=params["text"],
    output_name=params.get("output_name"),
    positive_prompt=params.get("image_prompt")
)

# 将结果转为可序列化格式
output = {
    "video_path": result.get("video_path"),
    "cover_path": result.get("cover_path"),
    "summary_path": result.get("summary_path"),
    "subtitle_path": result.get("subtitle_path"),
    "total_duration": result.get("total_duration", 0),
    "shots_count": len(result.get("shots", []))
}

# 将结果写入 JSON 文件（避免 Windows 控制台 GBK/UTF-8 编码问题）
with open(args.result_json, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# 同时打印到 stdout 便于调试
print("\n" + "=" * 60)
print("MULTIFUNC_RESULT_JSON_START")
print(json.dumps(output, ensure_ascii=False))
print("MULTIFUNC_RESULT_JSON_END")
print("=" * 60)
print(f"Result also written to: {args.result_json}")

# 生成完成后统一释放 GPU 显存
print("\n[Cleanup] Releasing GPU memory...")
try:
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        print(f"[Cleanup] Torch CUDA cache cleared")
except Exception as e:
    print(f"[Cleanup] Torch cleanup skipped: {e}")

try:
    import requests
    comfyui_url = config.IMAGE_SETTINGS.get("api_url", "http://127.0.0.1:8188")
    resp = requests.post(
        f"{comfyui_url}/free",
        json={"unload_models": True, "free_memory": True},
        timeout=10
    )
    if resp.status_code in (200, 204):
        print(f"[Cleanup] ComfyUI memory freed")
    else:
        print(f"[Cleanup] ComfyUI free returned {resp.status_code}")
except Exception as e:
    print(f"[Cleanup] ComfyUI cleanup skipped: {e}")

try:
    import requests
    ollama_url = "http://127.0.0.1:11434"
    llm_model = params.get("llm_model", "qwen3.5:9b")
    resp = requests.post(
        f"{ollama_url}/api/generate",
        json={"model": llm_model, "prompt": "", "keep_alive": 0},
        timeout=10
    )
    if resp.status_code == 200:
        print(f"[Cleanup] Ollama model unloaded")
    else:
        print(f"[Cleanup] Ollama unload returned {resp.status_code}")
except Exception as e:
    print(f"[Cleanup] Ollama cleanup skipped: {e}")
'''



class ImageTextVideoService:
    """图文视频生成服务"""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = Path(project_path or DEFAULT_VIDEO_GENERATOR_PATH)
        if not self.project_path.exists():
            raise FileNotFoundError(f"video_generator 目录不存在: {self.project_path}")
        self.voices_dir = self.project_path / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)

    def save_uploaded_file(self, uploaded_bytes: bytes, filename: str, subfolder: str) -> str:
        """保存上传的文件到 temp 目录"""
        ext = Path(filename).suffix.lower()
        safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{Path(filename).stem}{ext}"
        safe_name = re.sub(r"[^\w\-\.\u4e00-\u9fa5]", "_", safe_name)
        save_dir = Path(get_temp_path(subfolder))
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / safe_name
        with open(save_path, "wb") as f:
            f.write(uploaded_bytes)
        return str(save_path)

    def _copy_ref_audio_to_voices(self, ref_audio_path: str) -> str:
        """把参考音频复制到 video_generator/voices/ 目录下，供 TTS 调用"""
        src = Path(ref_audio_path)
        dst = self.voices_dir / f"ref_{src.name}"
        shutil.copy2(src, dst)
        return str(dst)

    def _convert_ref_audio_to_wav(self, src_path: str) -> str:
        """使用 FFmpeg 把参考音频转换为 24kHz mono WAV，提高 TTS 克隆兼容性"""
        src = Path(src_path)
        # 统一生成带 _24k 后缀的临时 WAV，避免覆盖原文件
        dst = src.with_suffix("").with_name(f"{src.stem}_24k.wav")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(dst)
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                timeout=60
            )
            if result.returncode == 0 and dst.exists():
                return str(dst)
            else:
                stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                logger.warning(f"参考音频转 WAV 失败，使用原文件: {stderr[:300]}")
                return src_path
        except Exception as e:
            logger.warning(f"参考音频转 WAV 异常，使用原文件: {e}")
            return src_path

    def _transcribe_audio(self, audio_path: str) -> Optional[str]:
        """使用 Whisper 自动识别参考音频文本（CPU 运行，避免占用 GPU 显存）"""
        venv_python = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
        if not Path(venv_python).exists():
            logger.warning("[ImageTextVideo] 未找到 whisper venv，跳过自动识别")
            return None

        # 内联脚本：加载 whisper base 模型并识别中文
        script = r'''
import sys
import whisper

audio_path = sys.argv[1]
model = whisper.load_model("base", device="cpu")
result = model.transcribe(audio_path, language="zh", fp16=False)
print(result["text"].strip())
'''
        try:
            result = subprocess.run(
                [venv_python, "-c", script, audio_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text:
                    logger.info(f"[ImageTextVideo] Whisper 识别参考音频文本: {text[:80]}...")
                    return text
                else:
                    logger.warning("[ImageTextVideo] Whisper 识别结果为空")
                    return None
            else:
                logger.warning(f"[ImageTextVideo] Whisper ASR 失败: {result.stderr[:500]}")
                return None
        except Exception as e:
            logger.warning(f"[ImageTextVideo] Whisper ASR 异常: {e}")
            return None

    def _write_wrapper_script(self, wrapper_path: Path):
        """生成 wrapper 脚本到 video_generator 目录"""
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(WRAPPER_SCRIPT)

    def _detect_video_generator_python(self) -> str:
        """检测适合运行 video-generator 的 Python 解释器（需要具备 torch/cv2/edge_tts 等依赖）"""
        candidates = [
            r"C:\Python314\python.exe",
            r"C:\Python313\python.exe",
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
            "python3",
            "python"
        ]
        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "-c", "import edge_tts; import torch; import cv2"],
                    capture_output=True,
                    text=False,
                    timeout=15
                )
                if result.returncode == 0:
                    logger.info(f"[ImageTextVideo] 使用 Python: {candidate}")
                    return candidate
            except Exception:
                continue

        # 降级：只检查 edge_tts
        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "-c", "import edge_tts"],
                    capture_output=True,
                    text=False,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.warning(f"[ImageTextVideo] {candidate} 仅具备 edge_tts，TTS_MODE=qwen_tts/gpt_sovits 可能失败")
                    return candidate
            except Exception:
                continue

        logger.warning("[ImageTextVideo] 未找到带 edge_tts 的 Python，回退到 python")
        return "python"

    def _run_video_generator(self, wrapper_path: Path, params: Dict,
                             progress_callback: Optional[Callable[[int, int, str], None]] = None,
                             timeout: int = 3600) -> Dict:
        """运行 wrapper 脚本生成视频

        progress_callback(step, total, message) - 与数字人教学等模块保持一致的进度回调接口
        """
        # 将参数写入 JSON 文件
        params_json_path = wrapper_path.with_suffix(".json")
        result_json_path = wrapper_path.with_suffix(".result.json")
        with open(params_json_path, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        python_executable = self._detect_video_generator_python()
        cmd = [
            python_executable, str(wrapper_path),
            "--params-json", str(params_json_path),
            "--result-json", str(result_json_path)
        ]
        logger.info(f"[ImageTextVideo] 运行视频生成命令: {' '.join(cmd)}")
        logger.info(f"[ImageTextVideo] 工作目录: {self.project_path}")

        # Windows 下强制子进程使用 UTF-8 编码，避免中文路径乱码
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        # 阶段定义（与 smart_video.generate_sync 的输出关键字对应，作为 [Progress] 标记的兜底）
        phases = [
            ("启动 video-generator", ["正在启动"]),
            ("解析文案 / 自动分类", ["Auto-detecting", "[0/7]", "Classifying", "自动分类"]),
            ("生成分镜", ["Generating shots", "[1/6]", "Shot", "分镜"]),
            ("生成视频摘要", ["Generating video summary", "[2/6]", "Summary", "摘要"]),
            ("生成配音", ["Generating audio", "[3/6]", "Audio", "配音", "TTS", "edge-tts", "GPT-SoVITS", "Qwen-TTS"]),
            ("生成画面", ["Generating image", "[4/6]", "Image", "画面", "ComfyUI", "FLUX", "Z-Image"]),
            ("生成字幕", ["Generating subtitles", "[5/6]", "Subtitle", "字幕", "ASS"]),
            ("合成视频", ["Synthesizing video", "[6/6]", "Video", "合成", "ffmpeg"]),
            ("生成封面", ["Generating cover", "[7/7]", "Cover", "封面"]),
            ("收尾", ["Complete!", "完成", "finalize"]),
        ]
        PROGRESS_TOTAL = 10

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=-1,
                env=env
            )

            output_lines = []
            result_json_str = None
            capturing = False
            current_step = 0
            import re as _re

            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                output_lines.append(line)
                logger.debug(line)

                # 优先解析显式 [Progress] 标记
                if progress_callback:
                    progress_match = _re.match(r"\[Progress\]\s+(\d+)\s*/\s*(\d+)\s*:\s*(.+)", line)
                    if progress_match:
                        try:
                            step = int(progress_match.group(1))
                            total = int(progress_match.group(2))
                            message = progress_match.group(3).strip()
                            current_step = max(current_step, step)
                            progress_callback(step, total, message)
                        except ValueError:
                            pass
                    else:
                        # 兜底：关键字阶段识别
                        for step, (message, keywords) in enumerate(phases):
                            if any(kw in line for kw in keywords):
                                current_step = max(current_step, step)
                                progress_callback(current_step, PROGRESS_TOTAL, message)
                                break

                # 捕获结果 JSON
                if "MULTIFUNC_RESULT_JSON_START" in line:
                    capturing = True
                    continue
                if capturing and "MULTIFUNC_RESULT_JSON_END" in line:
                    capturing = False
                    continue
                if capturing:
                    result_json_str = line

            process.stdout.close()
            return_code = process.wait(timeout=timeout)

            if return_code != 0:
                raise RuntimeError(f"视频生成失败，返回码: {return_code}\n输出:\n" + "\n".join(output_lines[-30:]))

            # 优先从结果文件读取（避免 Windows 控制台编码导致中文路径损坏）
            if result_json_path.exists():
                try:
                    with open(result_json_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"读取结果文件失败，回退到 stdout 解析: {e}")

            if result_json_str:
                return json.loads(result_json_str)

            # 如果没有捕获到 JSON，尝试从输出目录查找最新结果
            return self._find_latest_output(params.get("output_root"))

        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            raise TimeoutError(f"视频生成超时（{timeout}秒）")
        except Exception:
            if process and process.poll() is None:
                process.kill()
            raise
        finally:
            for temp_path in [params_json_path, result_json_path]:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

    def _find_latest_output(self, output_root: Optional[str] = None) -> Dict:
        """在输出目录查找最新的生成结果"""
        if output_root:
            videos_dir = Path(output_root) / "outputs" / "videos"
        else:
            videos_dir = self.project_path / "outputs" / "videos"
        if not videos_dir.exists():
            return {}

        subdirs = [d for d in videos_dir.iterdir() if d.is_dir()]
        if not subdirs:
            return {}

        latest_subdir = max(subdirs, key=lambda d: d.stat().st_mtime)
        video_files = list(latest_subdir.glob("*.mp4"))
        cover_files = list(latest_subdir.glob("cover.png")) + list(latest_subdir.glob("*_cover.png"))
        summary_files = list(latest_subdir.glob("summary.txt"))

        return {
            "video_path": str(max(video_files, key=lambda f: f.stat().st_mtime)) if video_files else None,
            "cover_path": str(max(cover_files, key=lambda f: f.stat().st_mtime)) if cover_files else None,
            "summary_path": str(max(summary_files, key=lambda f: f.stat().st_mtime)) if summary_files else None
        }

    def _mix_background_music(self, video_path: str, bgm_path: str, bgm_volume: float,
                              output_path: str) -> str:
        """使用 FFmpeg 将背景音乐混合到视频中"""
        logger.info(f"[ImageTextVideo] 混合背景音乐: {bgm_path} -> {output_path}, 音量: {bgm_volume}")

        # 标准化音量参数到 0-1 范围
        volume_db = max(0.0, min(1.0, bgm_volume))
        # 映射到 FFmpeg 音量：0 -> -30dB, 1 -> 0dB
        db_value = -30 + 30 * volume_db

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume={db_value}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-shortest",
            output_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"背景音乐混合失败: {stderr[:500]}")

        return output_path

    def _extract_summary(self, summary_path: Optional[str]) -> str:
        """从摘要文件中读取摘要"""
        if not summary_path or not Path(summary_path).exists():
            return ""
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"读取摘要文件失败: {e}")
            return ""

    def _extract_title(self, copywriting: str, summary: str) -> str:
        """Extract title: prefer first sentence of script, fallback to summary"""
        # 从文案中提取第一句
        text = copywriting.strip()
        for sep in ["\n", "。", "！", "？"]:
            if sep in text:
                title = text.split(sep)[0].strip()
                if title:
                    return title[:60]
        if text:
            return text[:60]

        # 回退到摘要
        if summary:
            for sep in ["\n", "。", "！", "？"]:
                if sep in summary:
                    title = summary.split(sep)[0].strip()
                    if title:
                        return title[:60]
            return summary[:60]

        return "图文短视频"

    def generate(self,
                 text: str,
                 ref_audio_bytes: Optional[bytes] = None,
                 ref_audio_filename: Optional[str] = None,
                 ref_audio_path: Optional[str] = None,
                 ref_audio_text: Optional[str] = None,
                 bgm_bytes: Optional[bytes] = None,
                 bgm_filename: Optional[str] = None,
                 bgm_volume: float = 0.3,
                 theme: Optional[str] = None,
                 image_prompt: Optional[str] = None,
                 speed: float = 1.0,
                 orientation: str = "portrait",
                 llm_model: str = "qwen3.5:9b",
                 progress_callback: Optional[Callable[[int, int, str], None]] = None,
                 timeout: int = 3600) -> Dict:
        """
        生成图文视频

        Args:
            text: 视频文案
            ref_audio_bytes: 参考音频文件字节（可选，与 ref_audio_path 二选一）
            ref_audio_filename: 参考音频文件名（可选）
            ref_audio_path: 参考音频文件路径（可选，与 ref_audio_bytes 二选一，用于缓存文件）
            ref_audio_text: 参考音频文本（可选）
            bgm_bytes: 背景音乐文件字节（可选）
            bgm_filename: 背景音乐文件名（可选）
            bgm_volume: 背景音乐音量（0-1）
            theme: 视频主题/风格（可选）
            image_prompt: 自定义图片提示词（可选）
            speed: 配音语速（0.5-2.0）
            orientation: 视频方向 portrait/landscape
            llm_model: 本地 LLM 模型名称
            progress_callback: 进度回调函数，接收(step, total, message)
            timeout: 超时时间（秒）

        Returns:
            包含 video_path, cover_path, title, summary 的字典
        """
        if not text or not text.strip():
            raise ValueError("视频文案不能为空")

        # 创建本次任务输出目录
        task_dir, task_id = create_task_output_dir()

        # 处理参考音频（支持上传字节或文件路径）
        ref_audio_in_project = None
        ref_audio_for_asr = None
        if ref_audio_bytes and ref_audio_filename:
            saved_ref_path = self.save_uploaded_file(ref_audio_bytes, ref_audio_filename, "ref_audio")
            # 统一转换为 24kHz mono WAV，提高 TTS 克隆兼容性
            converted_ref_path = self._convert_ref_audio_to_wav(saved_ref_path)
            ref_audio_in_project = self._copy_ref_audio_to_voices(converted_ref_path)
            ref_audio_for_asr = converted_ref_path
            logger.info(f"[ImageTextVideo] 参考音频已复制到: {ref_audio_in_project}")
        elif ref_audio_path and Path(ref_audio_path).exists():
            # 使用缓存文件路径
            converted_ref_path = self._convert_ref_audio_to_wav(ref_audio_path)
            ref_audio_in_project = self._copy_ref_audio_to_voices(converted_ref_path)
            ref_audio_for_asr = converted_ref_path
            logger.info(f"[ImageTextVideo] 参考音频（缓存）已复制到: {ref_audio_in_project}")

        # 如果没有提供参考音频文本，自动用 Whisper 识别
        if ref_audio_in_project and ref_audio_for_asr and not ref_audio_text:
            auto_text = self._transcribe_audio(ref_audio_for_asr)
            if auto_text:
                ref_audio_text = auto_text
                logger.info(f"[ImageTextVideo] 已自动识别参考音频文本")

        # 处理背景音乐
        bgm_path = None
        if bgm_bytes and bgm_filename:
            bgm_path = self.save_uploaded_file(bgm_bytes, bgm_filename, "bgm")
            logger.info(f"[ImageTextVideo] 背景音乐已保存: {bgm_path}")

        # 构建 wrapper 参数
        output_name = f"multifunc_{task_id}"
        params = {
            "text": text.strip(),
            "ref_audio": ref_audio_in_project,
            "prompt_text": ref_audio_text if ref_audio_text else None,
            "speed": max(0.5, min(2.0, speed)),
            "theme": theme,
            "image_prompt": image_prompt or "",
            "orientation": orientation,
            "llm_model": llm_model,
            "output_name": output_name,
            "output_root": str(task_dir)
        }

        # 生成 wrapper 脚本
        wrapper_path = self.project_path / f"_multifunc_wrapper_{task_id}.py"
        self._write_wrapper_script(wrapper_path)

        try:
            # 步骤 0：准备参考音频 / 识别文本（在 generate 入口已处理，这里通知 UI）
            if progress_callback:
                progress_callback(0, 10, "准备参考音频")

            # 运行视频生成（wrapper 内部会输出 [Progress] 1/10 ~ 9/10）
            result = self._run_video_generator(wrapper_path, params, progress_callback, timeout)

            video_path = result.get("video_path")
            cover_path = result.get("cover_path")
            summary_path = result.get("summary_path")

            if not video_path or not Path(video_path).exists():
                raise FileNotFoundError(f"视频生成失败，未找到视频文件: {video_path}")

            # 步骤 10：混合背景音乐 / 最终处理
            if progress_callback:
                progress_callback(10, 10, "混合背景音乐")

            final_video_path = os.path.join(task_dir, "final.mp4")
            if bgm_path and Path(bgm_path).exists():
                self._mix_background_music(video_path, bgm_path, bgm_volume, final_video_path)
            else:
                shutil.copy2(video_path, final_video_path)

            # 复制封面到任务目录
            final_cover_path = None
            if cover_path and Path(cover_path).exists():
                final_cover_path = os.path.join(task_dir, "cover.png")
                shutil.copy2(cover_path, final_cover_path)

            # 提取摘要和标题
            summary = self._extract_summary(summary_path)
            title = self._extract_title(text, summary)

            return {
                "task_id": task_id,
                "task_dir": task_dir,
                "video_path": final_video_path,
                "cover_path": final_cover_path,
                "raw_video_path": video_path,
                "raw_cover_path": cover_path,
                "title": title,
                "summary": summary,
                "text": text.strip()
            }

        finally:
            # 清理 wrapper 脚本
            try:
                if wrapper_path.exists():
                    wrapper_path.unlink()
            except Exception as e:
                logger.warning(f"清理 wrapper 脚本失败: {e}")

    def upload_to_feishu(self, result: Dict, auto_upload: bool = True) -> Optional[Dict]:
        """上传生成结果到飞书表格"""
        if not auto_upload:
            return None

        from multifunc_video.services.feishu_uploader import FeishuUploader

        uploader = FeishuUploader()
        upload_result = uploader.upload_video_result(
            copywriting=result["text"],
            video_path=result["video_path"],
            cover_path=result.get("cover_path"),
            summary=result.get("summary"),
            title=result.get("title")
        )
        return upload_result
