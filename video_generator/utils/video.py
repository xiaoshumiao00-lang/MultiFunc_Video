"""
视频合成模块 - 使用MoviePy和FFmpeg合成最终视频
支持图片+音频+字幕的同步合成
"""

import os
from pathlib import Path
from typing import Optional, List, Dict
import subprocess


def create_video_with_subtitles(image_path: str, audio_path: str,
                                 subtitle_path: Optional[str],
                                 output_path: str,
                                 watermark_text: str = "大学学业篇",
                                 video_settings: Dict = None,
                                 subtitle_settings: Dict = None,
                                 watermark_settings: Dict = None) -> str:
    """
    使用FFmpeg合成视频：图片 + 音频 + 字幕 + 水印

    Args:
        image_path: 图片路径
        audio_path: 音频路径
        subtitle_path: SRT字幕文件路径
        output_path: 输出视频路径
        watermark_text: 右上角水印文字
        video_settings: 视频设置
        subtitle_settings: 字幕设置
        watermark_settings: 水印设置

    Returns:
        输出视频路径
    """
    # 默认设置
    if video_settings is None:
        video_settings = {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "bitrate": "10M"
        }
    if subtitle_settings is None:
        subtitle_settings = {
            "font_size": 42,
            "color": "white",
            "outline_color": "black",
        }
    if watermark_settings is None:
        watermark_settings = {
            "font_size": 36,
            "color": "white",
            "outline_color": "black",
        }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 获取音频时长
    duration = get_audio_duration(audio_path)

    # 计算字幕文件的相对路径（FFmpeg在Windows上必须使用相对路径）
    # 切换工作目录到字幕文件所在目录
    import os
    original_cwd = os.getcwd()

    # 将路径转换为绝对路径（在切换工作目录前）
    abs_image_path = str(Path(image_path).resolve())
    abs_audio_path = str(Path(audio_path).resolve())
    abs_output_path = str(Path(output_path).resolve())

    if subtitle_path and Path(subtitle_path).exists():
        subtitle_dir = Path(subtitle_path).parent
        os.chdir(subtitle_dir)

    # 构建FFmpeg命令（使用绝对路径）
    # 使用 -t 参数明确指定视频时长，确保视频和音频时长一致
    # 音频音量增大400% (volume=5.0)
    cmd = [
        "ffmpeg", "-y",  # 覆盖输出文件
        "-loop", "1",    # 图片循环
        "-i", abs_image_path,
        "-i", abs_audio_path,
        "-t", str(duration),  # 明确指定输出时长（与音频相同）
        "-vf", build_video_filter(abs_image_path, duration, watermark_text,
                                  video_settings, subtitle_settings, watermark_settings,
                                  subtitle_path),
        "-af", "volume=5.0",  # 音频音量增大400%
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        abs_output_path
    ]

    # 执行命令（处理Windows编码问题）
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    except Exception as e:
        # 如果UTF-8失败，尝试使用系统默认编码
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg错误: {result.stderr[:2000] if result.stderr else '未知错误'}")

    return output_path


def build_video_filter(image_path: str, duration: float,
                       watermark_text: str,
                       video_settings: Dict,
                       subtitle_settings: Dict,
                       watermark_settings: Dict,
                       subtitle_path: Optional[str]) -> str:
    """构建FFmpeg视频滤镜链"""

    width = video_settings["width"]
    height = video_settings["height"]

    filters = []

    # 1. 缩放图片到目标分辨率（保持比例，填充白色背景）
    # 使用pad滤镜实现白色背景填充
    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=increase")
    filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:white")

    # 2. 添加水印（右上角）
    # 使用drawtext滤镜 - 处理颜色格式（可能是字符串或RGB元组）
    font_color = color_to_drawtext(watermark_settings.get('color', 'white'))
    outline_color = color_to_drawtext(watermark_settings.get('outline_color', 'black'))

    watermark_filter = (
        f"drawtext=text='{watermark_text}':"
        f"fontsize={watermark_settings.get('font_size', 48)}:"  # 放大字体适应横屏
        f"fontcolor={font_color}:"
        f"borderw=2:bordercolor={outline_color}:"
        f"x=w-text_w-{watermark_settings.get('margin_x', 50)}:"
        f"y={watermark_settings.get('margin_y', 50)}"
    )
    filters.append(watermark_filter)

    # 3. 添加字幕（如果有）
    # FFmpeg字幕滤镜在Windows上必须使用相对路径，不能使用绝对路径如C:/...
    # 注意：此函数假设当前工作目录已经是字幕文件所在目录
    if subtitle_path and Path(subtitle_path).exists():
        # 直接使用文件名（因为工作目录已切换到字幕所在目录）
        sub_path = Path(subtitle_path)
        rel_path_str = sub_path.name

        subtitle_filter = f"subtitles={rel_path_str}"
        filters.append(subtitle_filter)

    return ",".join(filters)


def color_to_bgr(color) -> str:
    """将颜色名或RGB转换为BGR hex格式（FFmpeg用）"""
    color_map = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "red": (0, 0, 255),
        "green": (0, 255, 0),
        "blue": (255, 0, 0),
    }

    if isinstance(color, str):
        color = color_map.get(color.lower(), (255, 255, 255))

    # 转换为BGR并生成FFmpeg格式
    bgr = (color[2], color[1], color[0])
    return "".join(f"{c:02X}" for c in bgr)


def color_to_drawtext(color) -> str:
    """将颜色名或RGB元组转换为FFmpeg drawtext滤镜格式 (0xRRGGBB)"""
    # 颜色名称映射
    color_map = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
    }

    # 如果是字符串，先查找映射
    if isinstance(color, str):
        rgb = color_map.get(color.lower(), (255, 255, 255))
    elif isinstance(color, tuple) and len(color) == 3:
        rgb = color
    else:
        rgb = (255, 255, 255)

    # 转换为0xRRGGBB格式
    return f"0x{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def get_audio_duration(audio_path: str) -> float:
    """获取音频文件时长（秒）"""
    # 优先使用pydub（如果有ffprobe会更快）
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception as e:
        pass

    # 回退到ffprobe
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.stdout.strip():
        return float(result.stdout.strip())

    # 最后回退到ffmpeg自带功能
    cmd2 = [
        'ffmpeg', '-i', audio_path,
        '-f', 'null', '-'
    ]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    # 从stderr中提取时长
    import re
    match = re.search(r'Time: (\d+):(\d+):(\d+\.\d+)', result2.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)

    raise Exception(f"无法获取音频时长: {audio_path}")


def create_video_moviepy(image_path: str, audio_path: str,
                         subtitle_path: Optional[str],
                         output_path: str,
                         watermark_text: str = "大学学业篇",
                         duration: Optional[float] = None) -> str:
    """
    使用MoviePy合成视频（Python原生方案）

    Args:
        image_path: 图片路径
        audio_path: 音频路径
        subtitle_path: SRT字幕文件路径
        output_path: 输出视频路径
        watermark_text: 水印文字
        duration: 指定时长（默认使用音频时长）

    Returns:
        输出视频路径
    """
    from moviepy.editor import (
        ImageClip, AudioFileClip, TextClip, CompositeVideoClip
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 加载音频获取时长
    audio = AudioFileClip(audio_path)
    duration = duration or audio.duration

    # 创建图片剪辑
    img_clip = ImageClip(image_path).set_duration(duration)
    img_clip = img_clip.resize(height=1920)  # 调整高度
    img_clip = img_clip.on_color(
        size=(1080, 1920),  # 9:16竖屏
        color=(0, 0, 0)     # 黑色背景
    )

    # 添加水印
    watermark = (TextClip(watermark_text, fontsize=36, color='white',
                          font='SimHei.ttf')
                 .set_duration(duration)
                 .set_position(('right', 'top'), margin=(30, 30)))

    # 合成视频
    video = CompositeVideoClip([img_clip, watermark], size=(1080, 1920))
    video = video.set_audio(audio)
    video = video.set_duration(duration)

    # 导出
    video.write_videofile(
        output_path,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        bitrate='10M'
    )

    # 清理
    audio.close()
    video.close()

    return output_path


def create_simple_video(image_path: str, audio_path: str, output_path: str,
                        watermark_text: str = "大学学业篇") -> str:
    """
    简化版视频合成：直接使用FFmpeg，不依赖MoviePy

    Args:
        image_path: 图片路径
        audio_path: 音频路径
        output_path: 输出路径
        watermark_text: 水印文字

    Returns:
        输出路径
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 获取音频时长
    duration = get_audio_duration(audio_path)

    # FFmpeg命令
    # 音频音量增大400% (volume=5.0)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
               f"drawtext=text='{watermark_text}':fontsize=36:fontcolor=white:"
               f"borderw=2:bordercolor=black:x=w-text_w-30:y=30",
        "-af", "volume=5.0",  # 音频音量增大400%
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

    if result.returncode != 0:
        raise RuntimeError(f"视频合成失败: {result.stderr}")

    return output_path


if __name__ == "__main__":
    # 测试代码
    print("视频合成模块测试")
    print("需要FFmpeg已安装并添加到PATH")
