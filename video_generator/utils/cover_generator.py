"""
封面生成器 - 9:16竖屏封面
严格参照模板图片样式：
- 顶部纯黑区域
- 红色分类标题"大学xx篇之"（"之"为黑色）
- 黑色超粗体主标题（位于图片中央）
- 水彩插画风格背景
"""

import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from config import VIDEOS_DIR


class CoverGenerator:
    """封面生成器 - 严格匹配模板样式"""

    WIDTH = 1080
    HEIGHT = 1920

    COLOR_BLACK = (0, 0, 0)
    COLOR_RED = (229, 57, 53)
    COLOR_WHITE = (255, 255, 255)

    HEADER_HEIGHT = 220
    CATEGORY_Y = 590              # 大学xx篇之往上移80
    TITLE_CENTER_Y = 960
    GRADIENT_START_Y = 570         # 白色背景起始位置（从610上移到570）
    GRADIENT_END_Y = 900           # 白色背景结束位置

    FONT_SIZE_CATEGORY = 76
    FONT_SIZE_TITLE = 96

    def __init__(self, theme: str = "大学学业篇"):
        self.theme = theme

    def create_cover(self,
                     background_image: str,
                     category: str = None,
                     main_title: str = None,
                     output_path: str = None) -> str:
        """创建封面图片"""
        category = category or self.theme
        main_title = main_title or ""

        # 创建画布
        img = Image.new('RGB', (self.WIDTH, self.HEIGHT), self.COLOR_WHITE)

        # 加载字体
        font_category, font_title = self._load_fonts()

        # 绘制背景图片
        self._draw_background(img, background_image)

        # 叠加所有图层
        img = self._overlay_all_layers(img, font_category, font_title, category, main_title)

        # 保存
        if output_path is None:
            output_path = str(VIDEOS_DIR / f"cover_{Path(background_image).stem}.png")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG", quality=95)
        return output_path

    def _load_fonts(self) -> Tuple:
        """加载字体 - 主标题使用粗体"""
        font_category = None
        font_title = None

        # 普通字体（用于分类标题）
        normal_font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simfang.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]

        # 粗体字体（用于主标题）
        bold_font_paths = [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simheibd.ttf",
            "C:/Windows/Fonts/simfang.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]

        # 加载普通字体
        for font_path in normal_font_paths:
            if os.path.exists(font_path):
                try:
                    font_category = ImageFont.truetype(font_path, self.FONT_SIZE_CATEGORY)
                    break
                except:
                    continue

        # 加载粗体字体（主标题）
        for font_path in bold_font_paths:
            if os.path.exists(font_path):
                try:
                    font_title = ImageFont.truetype(font_path, self.FONT_SIZE_TITLE)
                    break
                except:
                    continue

        if font_category is None:
            font_category = ImageFont.load_default()
        if font_title is None:
            font_title = ImageFont.load_default()

        return font_category, font_title

    def _draw_background(self, img: Image.Image, background_image: str):
        """绘制背景图片"""
        if not background_image or not Path(background_image).exists():
            return

        try:
            bg = Image.open(background_image)

            if bg.mode != 'RGB':
                bg = bg.convert('RGB')

            bg_width, bg_height = bg.size
            target_ratio = self.WIDTH / self.HEIGHT
            source_ratio = bg_width / bg_height

            if source_ratio > target_ratio:
                new_height = self.HEIGHT
                new_width = int(bg_width * (new_height / bg_height))
            else:
                new_width = self.WIDTH
                new_height = int(bg_height * (new_width / bg_width))

            bg = bg.resize((new_width, new_height), Image.Resampling.LANCZOS)

            left = (new_width - self.WIDTH) // 2
            top = (new_height - self.HEIGHT) // 2
            bg = bg.crop((left, top, left + self.WIDTH, top + self.HEIGHT))

            bg = bg.filter(ImageFilter.GaussianBlur(radius=2))

            enhancer = ImageEnhance.Brightness(bg)
            bg = enhancer.enhance(1.1)

            img.paste(bg, (0, 0))

        except Exception as e:
            print(f"  [WARNING] Background processing failed: {e}")

    def _overlay_all_layers(self, bg_img: Image.Image,
                          font_category, font_title,
                          category: str, main_title: str) -> Image.Image:
        """
        叠加所有图层（图层顺序从下到上）：
        1. 背景图片
        2. 白色渐变图层（y=860到底部）
        3. 顶部黑色区域
        4. 文字图层（置顶）
        """
        result = bg_img.convert('RGBA')

        # 1. 白色渐变图层（上下渐变）
        gradient_layer = Image.new('RGBA', (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient_layer)

        gradient_top = 0
        gradient_bottom = self.HEIGHT

        # 绘制白色背景矩形（y=570-1160，60%不透明度）
        if 570 < 1160:
            gradient_draw.rectangle(
                [(0, 570), (self.WIDTH, 1160)],
                fill=(255, 255, 255, 153)  # 60%不透明度 = 153
            )

        # 2. 顶部黑色区域
        header_layer = Image.new('RGBA', (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
        header_draw = ImageDraw.Draw(header_layer)
        header_draw.rectangle([(0, 0), (self.WIDTH, self.HEADER_HEIGHT)], fill=(0, 0, 0, 255))

        # 3. 文字图层（置顶）
        text_layer = Image.new('RGBA', (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        # 绘制分类标题（红色"大学xx篇" + 黑色"之"）
        self._draw_category_rgba(text_draw, font_category, category, self.CATEGORY_Y)

        # 绘制主标题
        self._draw_main_title_rgba(text_draw, font_title, main_title)

        # 合成所有图层
        result = Image.alpha_composite(result, gradient_layer)
        result = Image.alpha_composite(result, header_layer)
        result = Image.alpha_composite(result, text_layer)

        return result.convert('RGB')

    def _draw_category_rgba(self, draw: ImageDraw.Draw, font, category: str, y: int):
        """绘制分类标题（RGBA）"""
        if not category.endswith("之"):
            text = f"{category}之"
        else:
            text = category

        if text.endswith("之"):
            category_part = text[:-1]
            zhi_part = "之"
        else:
            category_part = text
            zhi_part = ""

        bbox = draw.textbbox((0, 0), text, font=font)
        total_width = bbox[2] - bbox[0]
        x = (self.WIDTH - total_width) // 2 - 160

        draw.text((x, y), category_part, fill=(229, 57, 53, 255), font=font)

        bbox_cat = draw.textbbox((0, 0), category_part, font=font)
        cat_width = bbox_cat[2] - bbox_cat[0]
        draw.text((x + cat_width, y), zhi_part, fill=(0, 0, 0, 255), font=font)

    def _draw_main_title_rgba(self, draw: ImageDraw.Draw, font, main_title: str):
        """绘制主标题（RGBA）"""
        if not main_title:
            return

        main_title = main_title.strip()
        for punct in '。！？，、；：""''（）':
            main_title = main_title.replace(punct, '')

        lines = self._wrap_text(main_title, font)

        try:
            ascent = font.getmetrics()[0]
            descent = font.getmetrics()[1]
        except:
            bbox = draw.textbbox((0, 0), "测试", font=font)
            ascent = -bbox[1]
            descent = 0
        line_height = ascent + descent + 0

        total_height = len(lines) * line_height
        start_y = self.TITLE_CENTER_Y - total_height // 2

        y = start_y
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (self.WIDTH - text_width) // 2
            draw.text((x, y), line, fill=(0, 0, 0, 255), font=font)
            y += line_height

    def _wrap_text(self, text: str, font) -> List[str]:
        """文字换行"""
        if not text:
            return [""]

        lines = []
        current_line = ""
        max_width = self.WIDTH - 80

        dummy_img = Image.new('RGB', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)

        for char in text:
            test_line = current_line + char
            bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        if len(lines) == 1 and len(lines[0]) > 6:
            mid = len(lines[0]) // 2
            for i in range(mid, min(mid + 5, len(lines[0]))):
                if lines[0][i] in '的地得着了过':
                    mid = i + 1
                    break
            lines = [lines[0][:mid], lines[0][mid:]]

        return lines if lines else [""]


def create_video_cover(background_image: str,
                      theme: str,
                      output_path: str = None) -> str:
    """快捷函数"""
    generator = CoverGenerator(theme=theme)
    return generator.create_cover(
        background_image=background_image,
        category=theme,
        output_path=output_path
    )


if __name__ == "__main__":
    print("Cover Generator - Template Style")