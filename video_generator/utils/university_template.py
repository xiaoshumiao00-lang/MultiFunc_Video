"""
大学视频模板 - 双栏布局
- 纯白背景
- 左上角：老学长聊大学 + logo
- 右上角：主题标题（可变）
- 中间：左右两栏交替显示图片+关键词
- 底部：分镜标题
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_SETTINGS, IMAGES_DIR, VIDEOS_DIR


class UniversityVideoTemplate:
    """大学视频模板生成器"""

    # 布局常量
    HEADER_HEIGHT = 120      # 顶部标题区高度
    FOOTER_HEIGHT = 100      # 底部标题区高度
    CONTENT_MARGIN = 40      # 内容区边距
    IMAGE_WIDTH = 840        # 图片宽度（4:3比例）
    IMAGE_HEIGHT = 630       # 图片高度（4:3比例）
    KEYWORD_FONT_SIZE = 48   # 关键词字体大小
    HEADER_FONT_SIZE = 72    # 顶部标题字体大小（调大）
    SUBTITLE_FONT_SIZE = 48  # 底部字幕字体大小

    def __init__(self, theme: str = "大学学业篇"):
        self.theme = theme
        self.width = VIDEO_SETTINGS.get("width", 1080)
        self.height = VIDEO_SETTINGS.get("height", 1920)

        # 计算内容区域
        self.content_top = self.HEADER_HEIGHT + 50
        self.content_bottom = self.height - self.FOOTER_HEIGHT - 50
        self.content_height = self.content_bottom - self.content_top

        # 左右半屏中心点（视频宽1080，左半屏中心270，右半屏中心810）
        self.half_width = self.width // 2  # 540
        self.left_center = self.half_width // 2  # 270
        self.right_center = self.half_width + self.half_width // 2  # 810

        # 图片位置（中心点对齐，向下偏移）
        self.left_x = self.left_center - self.IMAGE_WIDTH // 2
        self.right_x = self.right_center - self.IMAGE_WIDTH // 2
        self.center_y = self.content_top + self.content_height // 2 - self.IMAGE_HEIGHT // 2 + 60  # 向下偏移60px

    def create_frame(self, image_path: str, keyword: str, subtitle: str,
                    position: str = "left", title: str = None) -> Image.Image:
        """
        创建单帧画面

        Args:
            image_path: 图片路径
            keyword: 关键词（如"尽早实习"）
            subtitle: 底部标题（如"第一件事"）
            position: 图片位置 "left" 或 "right"
            title: 右侧显示的标题（仅左侧图片时显示）

        Returns:
            PIL Image
        """
        # 创建纯白背景
        img = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            font_header = ImageFont.truetype("simhei.ttf", self.HEADER_FONT_SIZE)
            font_medium = ImageFont.truetype("simhei.ttf", self.SUBTITLE_FONT_SIZE)
            font_keyword = ImageFont.truetype("simhei.ttf", self.KEYWORD_FONT_SIZE)
        except:
            try:
                font_header = ImageFont.truetype("msyh.ttc", self.HEADER_FONT_SIZE)
                font_medium = ImageFont.truetype("msyh.ttc", self.SUBTITLE_FONT_SIZE)
                font_keyword = ImageFont.truetype("msyh.ttc", self.KEYWORD_FONT_SIZE)
            except:
                font_header = ImageFont.load_default()
                font_medium = font_header
                font_keyword = font_header

        # 1. 绘制顶部标题区
        self._draw_header(img, draw, font_header, font_medium)

        # 2. 绘制中间内容区
        self._draw_content(img, draw, image_path, keyword, position, font_keyword)

        # 3. 绘制右侧标题（仅左侧图片且有标题时）
        if position == "left" and title:
            self._draw_right_title(img, draw, title, font_header)

        # 4. 绘制底部标题
        self._draw_footer(img, draw, subtitle, font_medium)

        return img

    def _draw_header(self, img: Image.Image, draw: ImageDraw.Draw, font_header, font_medium):
        """绘制顶部标题区"""
        # 左上角：logo + "老学长聊大学"
        logo_text = "老学长聊大学"

        # 获取字体高度用于居中对齐
        bbox = draw.textbbox((0, 0), logo_text, font=font_header)
        text_height = bbox[3] - bbox[1]

        # logo高度与文字高度一致，两者中心点对齐
        logo_height = text_height
        logo_center_offset = 0  # 高度一致，无需偏移

        # 加载并绘制logo图片
        logo_x, logo_y = 40, 30 + logo_center_offset
        self._draw_logo_image(img, logo_x, logo_y, logo_height)

        # 绘制文字（与logo垂直居中）
        draw.text((logo_x + logo_height + 15, 30), logo_text,
                 fill=(51, 51, 51), font=font_header)

        # 右上角：主题标题（如"大学就业篇"）
        theme_text = self.theme
        bbox = draw.textbbox((0, 0), theme_text, font=font_header)
        text_width = bbox[2] - bbox[0]
        draw.text((self.width - text_width - 40, 30), theme_text,
                 fill=(255, 0, 0), font=font_header)  # 标准红

    def _draw_logo_image(self, img: Image.Image, x: int, y: int, target_height: int):
        """加载并绘制学位帽logo图片
        
        Args:
            img: 主图像
            x: 左上角x坐标
            y: 左上角y坐标
            target_height: 目标高度（与文字高度一致）
        """
        try:
            # 加载logo图片
            logo_path = Path(__file__).parent.parent / "assets" / "logo_cap.png"
            if not logo_path.exists():
                # 如果图片不存在，回退到绘制模式
                self._draw_logo_fallback(img, x, y)
                return
            
            logo_img = Image.open(logo_path)
            
            # 转换为RGBA模式以支持透明背景
            if logo_img.mode != 'RGBA':
                logo_img = logo_img.convert('RGBA')
            
            # 计算缩放后的尺寸（保持宽高比）
            orig_width, orig_height = logo_img.size
            scale = target_height / orig_height
            new_width = int(orig_width * scale)
            new_height = target_height
            
            # 缩放图片
            logo_resized = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 粘贴到主图像（使用alpha通道）
            img.paste(logo_resized, (x, y), logo_resized)
            
        except Exception as e:
            print(f"  [WARNING] Logo image load failed: {e}, using fallback")
            self._draw_logo_fallback(img, x, y)

    def _draw_logo_fallback(self, img: Image.Image, x: int, y: int):
        """备用绘制方法（当图片加载失败时使用）"""
        draw = ImageDraw.Draw(img)
        cap_color = (255, 0, 0)   # 标准红
        gold_color = (255, 200, 0)  # 金色

        w = 50
        h = 38
        cx = x + w // 2
        top_y = y

        # 菱形帽顶板
        board_h = 14
        board_w = w
        draw.polygon([
            (cx, top_y),
            (cx + board_w // 2, top_y + board_h // 2),
            (cx, top_y + board_h),
            (cx - board_w // 2, top_y + board_h // 2),
        ], fill=cap_color)

        # 帽筒
        tube_top = top_y + board_h
        draw.rectangle([cx-10, tube_top, cx+10, tube_top+10], fill=cap_color)

        # 宽帽沿
        brim_top = tube_top + 10
        draw.rectangle([x-2, brim_top, x+w+2, brim_top+6], fill=cap_color)

        # 流苏
        tassel_x = cx + board_w // 2 - 2
        tassel_y = top_y + board_h // 2
        draw.ellipse([tassel_x-4, tassel_y-4, tassel_x+4, tassel_y+4], fill=gold_color)
        draw.line([(tassel_x, tassel_y+4), (tassel_x+3, tassel_y+14)], fill=gold_color, width=2)

    def _draw_content(self, img: Image.Image, draw: ImageDraw.Draw, image_path: str,
                     keyword: str, position: str, font_keyword):
        """绘制中间内容区"""
        # 确定图片位置
        if position == "left":
            img_x = self.left_x
            center_x = self.left_center
        else:
            img_x = self.right_x
            center_x = self.right_center

        img_y = self.center_y

        # 绘制占位框（默认）
        draw.rectangle([img_x, img_y,
                      img_x + self.IMAGE_WIDTH, img_y + self.IMAGE_HEIGHT],
                     fill=(245, 245, 245), outline=(220, 220, 220), width=2)

        # 加载并绘制图片
        if image_path and Path(image_path).exists():
            try:
                content_img = Image.open(image_path)
                # 缩放图片（保持比例，完整显示）
                content_img.thumbnail(
                    (self.IMAGE_WIDTH, self.IMAGE_HEIGHT),
                    Image.Resampling.LANCZOS
                )
                # 计算居中位置（图片小于设定尺寸时居中）
                paste_x = img_x + (self.IMAGE_WIDTH - content_img.width) // 2
                paste_y = img_y + (self.IMAGE_HEIGHT - content_img.height) // 2
                # 粘贴到主图
                if content_img.mode != 'RGB':
                    content_img = content_img.convert('RGB')
                img.paste(content_img, (paste_x, paste_y))
            except Exception as e:
                print(f"  [WARNING] Image paste failed: {e}")

        # 绘制关键词（图片正上方：圆形图标 + 关键词）
        if keyword:
            # 关键词位于图片正上方，向上移动更多
            keyword_y = img_y - 100  # 图片上方留出空间（向上移）

            # 获取文字宽度和高度
            bbox = draw.textbbox((0, 0), keyword, font=font_keyword)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 蓝色圆点（左侧，紧贴文字），圆心与文字视觉中心对齐
            dot_radius = 12
            dot_x = center_x - text_width // 2 - 35  # 圆点在文字左侧35px处
            dot_y = keyword_y + text_height // 2     # 圆心与文字中心同一水平线
            draw.ellipse([dot_x - dot_radius, dot_y - dot_radius,
                         dot_x + dot_radius, dot_y + dot_radius],
                        fill=(70, 130, 180))

            # 关键词文字（居中显示）
            text_x = center_x - text_width // 2
            text_y = keyword_y  # baseline = keyword_y
            draw.text((text_x, text_y),
                     keyword, fill=(51, 51, 51), font=font_keyword)

    def _draw_footer(self, img: Image.Image, draw: ImageDraw.Draw, subtitle: str, font_medium):
        """绘制底部标题 - 支持2行显示，预留足够空间避免超出屏幕"""
        if not subtitle:
            return

        # 获取字体高度
        bbox = draw.textbbox((0, 0), "测试", font=font_medium)
        line_height = bbox[3] - bbox[1] + 15  # 增大行间距

        # 字幕区域宽度限制（左右各留40px边距）
        max_text_width = self.width - 80

        # 字幕位置向下移动1.1倍字体高度，避免覆盖图片
        base_y_offset = int(line_height * 1.1)

        # 字幕区域高度（预留2行 + 安全边距）
        subtitle_area_height = line_height * 2 + 20  # 2行 + 20px安全边距
        # 字幕起始Y位置：距离底部一定距离，向上预留2行空间
        base_y = self.height - self.FOOTER_HEIGHT - subtitle_area_height + 30 + base_y_offset

        def truncate_text(text, font, max_width):
            """截断超长文本，确保不超出宽度"""
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_width:
                return text, font
            # 缩小字号
            scale = max_width / text_width
            new_size = int(self.SUBTITLE_FONT_SIZE * scale * 0.9)
            try:
                font_scaled = ImageFont.truetype("simhei.ttf", new_size)
            except:
                try:
                    font_scaled = ImageFont.truetype("msyh.ttc", new_size)
                except:
                    font_scaled = font
            return text, font_scaled

        # 检测是否需要换行（按标点或字数判断）
        if len(subtitle) <= 12:
            # 单行字幕，显示在中间位置
            display_text, used_font = truncate_text(subtitle, font_medium, max_text_width)
            bbox = draw.textbbox((0, 0), display_text, font=used_font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
            text_y = base_y + line_height // 2
            draw.text((text_x, text_y), display_text, fill=(51, 51, 51), font=used_font)
        else:
            # 长字幕，分两行显示
            # 找合适的断点（逗号、句号附近）
            mid = len(subtitle) // 2
            breakpoints = [i for i, c in enumerate(subtitle) if c in '，、。；：']
            if breakpoints:
                # 选择最接近中点的断点
                bp = min(breakpoints, key=lambda x: abs(x - mid))
                line1 = subtitle[:bp+1]
                line2 = subtitle[bp+1:]
            else:
                line1 = subtitle[:len(subtitle)//2]
                line2 = subtitle[len(subtitle)//2:]

            # 第一行（上方）
            line1, font1 = truncate_text(line1, font_medium, max_text_width)
            bbox1 = draw.textbbox((0, 0), line1, font=font1)
            text1_width = bbox1[2] - bbox1[0]
            text1_x = (self.width - text1_width) // 2
            draw.text((text1_x, base_y), line1, fill=(51, 51, 51), font=font1)

            # 第二行（下方）
            line2, font2 = truncate_text(line2, font_medium, max_text_width)
            bbox2 = draw.textbbox((0, 0), line2, font=font2)
            text2_width = bbox2[2] - bbox2[0]
            text2_x = (self.width - text2_width) // 2
            draw.text((text2_x, base_y + line_height), line2, fill=(51, 51, 51), font=font2)

    def _draw_right_title(self, img: Image.Image, draw: ImageDraw.Draw, title: str, font_title,
                           anim_progress: float = 1.0, anim_type: str = "bounce_in",
                           char_delays: List[float] = None):
        """
        在右侧半屏居中显示标题文字（用于第一张图片时）
        支持弹跳入场动画和淡出出场动画
        固定68号字体，长了自动换行2-3行，换行居中对齐

        Args:
            img: 图像
            draw: 绘图对象
            title: 标题文字
            font_title: 标题字体
            anim_progress: 动画进度 (0-1)，1.0表示完全显示
            anim_type: 动画类型 "bounce_in"(弹跳入场), "fade_out"(淡出)
            char_delays: 每个字符的延迟时间列表（秒），用于逐字随机弹跳动画
        """
        import re
        import random

        # 右侧区域：从中间分隔线到右边缘
        # 视频宽度1080，中间分隔线在540
        # 右半边可用区域：540到1040（预留40px边距）
        right_area_left = self.half_width + 20  # 560
        right_area_width = self.half_width - 40  # 500px可用宽度

        # 固定68号字体
        fixed_font_size = 68

        # 标题中去除标点符号，用空格替代
        punct_pattern = re.compile(r'[\u300a\u300b\u3010\u3011\[\]]+')  # 中文引号和方括号
        other_punct = re.compile(r'[，。、；：！？""''（）]+')
        title_clean = punct_pattern.sub(' ', title)
        title_clean = other_punct.sub(' ', title_clean)
        title_clean = ' '.join(title_clean.split())  # 合并多余空格
        title = title_clean

        # 使用固定字号
        try:
            final_font = ImageFont.truetype("simhei.ttf", fixed_font_size)
        except:
            try:
                final_font = ImageFont.truetype("msyh.ttc", fixed_font_size)
            except:
                final_font = font_title

        # 获取行高（单行居中，多行1.25倍行距）
        bbox_test = draw.textbbox((0, 0), "测试", font=final_font)
        base_line_height = bbox_test[3] - bbox_test[1] + 8

        # 计算单行是否能放下
        bbox = draw.textbbox((0, 0), title, font=final_font)
        text_width = bbox[2] - bbox[0]

        # 自动分词函数：在合适位置断行
        def split_text(text: str, num_lines: int) -> List[str]:
            """将文本分成num_lines行，尽量在标点或助词处断开，保持语义完整"""
            if num_lines == 1 or len(text) <= 8:
                return [text]

            # 估算每行字符数
            chars_per_line = len(text) / num_lines
            lines = []

            # 优先断点符号：逗号、顿号、句号等
            # 辅助断点：的地得等了过（助词）
            aux_punct = '的地得年了过'

            if num_lines == 2:
                # 两行：找最佳断点
                mid = len(text) // 2
                breakpoints = [i for i, c in enumerate(text) if c in '，、。；：!? ,-']
                if breakpoints:
                    bp = min(breakpoints, key=lambda x: abs(x - mid))
                    lines = [text[:bp+1].strip(), text[bp+1:].strip()]
                else:
                    # 没有标点，在助词处找断点
                    bp = -1
                    for i in range(max(0, mid - 5), min(len(text) - 1, mid + 5)):
                        if text[i] in aux_punct:
                            bp = i
                            break
                    if bp > 0:
                        lines = [text[:bp+1].strip(), text[bp+1:].strip()]
                    else:
                        lines = [text[:mid], text[mid:]]
            elif num_lines == 3:
                # 三行：找两个最佳断点
                mid1 = len(text) // 3
                mid2 = 2 * len(text) // 3
                breakpoints1 = [i for i, c in enumerate(text[:mid1*2]) if c in '，、。；：!? ,-']
                breakpoints2 = [i for i, c in enumerate(text[mid1:]) if c in '，、。；：!? ,-']

                if breakpoints1 and breakpoints2:
                    bp1 = breakpoints1[min(range(len(breakpoints1)), key=lambda x: abs(breakpoints1[x] - mid1))]
                    bp2 = mid1 + breakpoints2[min(range(len(breakpoints2)), key=lambda x: abs(breakpoints2[x] - (len(text) - mid1)//2))]
                    lines = [text[:bp1+1].strip(), text[bp1+1:bp2+1].strip(), text[bp2+1:].strip()]
                else:
                    lines = [text[:mid1], text[mid1:mid2], text[mid2:]]
            else:
                lines = [text]

            # 过滤空行
            lines = [l for l in lines if l]
            return lines if lines else [text]

        # 尝试单行、两行、三行
        lines = []
        max_lines = 3

        for num_lines in range(1, max_lines + 1):
            candidate_lines = split_text(title, num_lines)

            # 检查所有行是否都能放下
            all_fit = True
            for line in candidate_lines:
                bbox_line = draw.textbbox((0, 0), line, font=final_font)
                w = bbox_line[2] - bbox_line[0]
                if w > right_area_width:
                    all_fit = False
                    break

            if all_fit:
                lines = candidate_lines
                break

        # 如果3行都放不下，取前3行 + 省略号
        if not lines or any(draw.textbbox((0, 0), l, font=final_font)[2] > right_area_width for l in lines):
            # 强制截断成3行
            words = title.split()
            if len(words) <= 6:
                part_len = max(1, len(words) // 3)
                lines = [' '.join(words[:part_len]), ' '.join(words[part_len:part_len*2]), ' '.join(words[part_len*2:])]
            else:
                # 按字符数强制分段
                chars_per_line = len(title) // 3
                lines = [title[:chars_per_line], title[chars_per_line:chars_per_line*2], title[chars_per_line*2:]]
            # 最后一行加省略号
            if lines and len(lines[-1]) < len(title):
                lines[-1] = lines[-1][:min(len(lines[-1]), 8)] + '...'
            lines = [l.strip() for l in lines if l.strip()] or [title[:8]+'...']

        # 计算动画参数
        if anim_type == "bounce_in":
            # 弹跳入场动画
            scale, offset_y, alpha = self._calculate_bounce_animation(anim_progress)
        elif anim_type == "fade_out":
            # 淡出动画
            scale = 1.0
            offset_y = 0
            alpha = int(255 * anim_progress)
        else:
            # 无动画
            scale = 1.0
            offset_y = 0
            alpha = 255

        # 计算内容区域中心
        content_center_y = (self.content_top + self.content_bottom) // 2

        # 根据行数确定行高和起始位置
        if len(lines) >= 2:
            # 多行：1.25倍行距
            line_height = int(base_line_height * 1.25)
            total_height = line_height * len(lines)
            start_y = content_center_y - total_height // 2 + offset_y
        else:
            # 单行：居中显示
            line_height = base_line_height
            total_height = line_height * len(lines)
            start_y = content_center_y - total_height // 2 + offset_y

        # 绘制每一行
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=final_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 计算位置（居中）
            text_x = right_area_left + (right_area_width - text_width) // 2
            text_y = start_y + i * line_height

            # 检查是否启用逐字随机弹跳模式
            if char_delays and anim_type == "bounce_in" and anim_progress < 1.0:
                # 逐字随机弹跳模式
                self._draw_char_by_char_animation(
                    img, draw, line, text_x, text_y, final_font,
                    anim_progress, char_delays, base_line_height
                )
            else:
                # 原有整体动画模式
                # 应用缩放动画（仅在动画阶段缩放，正常显示时固定68号）
                if scale != 1.0:
                    # 创建临时图像来绘制缩放后的文字
                    scaled_size = int(fixed_font_size * scale)
                    try:
                        scaled_font = ImageFont.truetype("simhei.ttf", scaled_size)
                    except:
                        try:
                            scaled_font = ImageFont.truetype("msyh.ttc", scaled_size)
                        except:
                            scaled_font = final_font

                    # 重新计算缩放后的文字尺寸
                    bbox_scaled = draw.textbbox((0, 0), line, font=scaled_font)
                    scaled_width = bbox_scaled[2] - bbox_scaled[0]
                    scaled_height = bbox_scaled[3] - bbox_scaled[1]

                    # 居中调整
                    scaled_x = right_area_left + (right_area_width - scaled_width) // 2
                    scaled_y = text_y + (text_height - scaled_height) // 2

                    # 绘制文字（带透明度）
                    self._draw_text_with_alpha(img, draw, line, (scaled_x, scaled_y), scaled_font, alpha)
                else:
                    # 正常绘制（固定68号，每行居中对齐）
                    self._draw_text_with_alpha(img, draw, line, (text_x, text_y), final_font, alpha)

    def _calculate_bounce_animation(self, progress: float) -> tuple:
        """
        计算弹跳动画参数（增强版，更明显的弹跳效果）

        Args:
            progress: 动画进度 (0-1)

        Returns:
            (scale, offset_y, alpha) - 缩放比例、Y轴偏移、透明度
        """
        if progress <= 0:
            return 0.15, -100, 0
        elif progress >= 1:
            return 1.0, 0, 255

        # 弹跳动画关键帧（增强版）
        # 0%: 缩放0.15，向上偏移100px，透明度0
        # 30%: 缩放1.35，向下偏移20px，透明度255（强烈过冲）
        # 50%: 缩放0.9，向上偏移10px（大幅回弹）
        # 70%: 缩放1.1（再次下落）
        # 85%: 缩放0.98（轻微回弹）
        # 100%: 缩放1.0，位置正常

        if progress < 0.3:
            # 第一阶段：快速放大并下落
            t = progress / 0.3
            eased = self._ease_out_back(t)
            scale = 0.15 + 1.2 * eased  # 从0.15到1.35
            offset_y = int(-100 + 120 * eased)  # 向上偏移100px
            alpha = int(255 * self._ease_out_cubic(t))
        elif progress < 0.5:
            # 第二阶段：大幅回弹上升
            t = (progress - 0.3) / 0.2
            scale = 1.35 - 0.45 * t  # 从1.35到0.9
            offset_y = int(20 - 30 * t)  # 从+20到-10
            alpha = 255
        elif progress < 0.7:
            # 第三阶段：再次下落
            t = (progress - 0.5) / 0.2
            scale = 0.9 + 0.2 * t  # 从0.9到1.1
            offset_y = int(-10 + 20 * t)  # 从-10到+10
            alpha = 255
        elif progress < 0.85:
            # 第四阶段：轻微回弹
            t = (progress - 0.7) / 0.15
            scale = 1.1 - 0.12 * t  # 从1.1到0.98
            offset_y = int(10 - 20 * t)  # 从+10到-10
            alpha = 255
        else:
            # 第五阶段：最终稳定
            t = (progress - 0.85) / 0.15
            scale = 0.98 + 0.02 * t  # 从0.98到1.0
            offset_y = int(-10 + 10 * t)  # 从-10到0
            alpha = 255

        return scale, offset_y, alpha

    def _ease_out_back(self, t: float) -> float:
        """
        回弹缓动函数
        产生过冲和回弹效果
        """
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

    def _calculate_char_delays(self, text: str, max_delay: float = 0.15) -> List[float]:
        """
        为每个字符计算随机延迟时间，用于逐字弹跳动画

        Args:
            text: 文字内容
            max_delay: 最大延迟时间（秒）

        Returns:
            每个字符的延迟时间列表
        """
        import random
        # 汉字占位宽度估算（中文比英文宽）
        delays = []
        for char in text:
            if char.strip() == '':
                delays.append(0)
            else:
                # 随机延迟 0.02 到 max_delay 秒
                delay = random.uniform(0.02, max_delay)
                delays.append(delay)
        return delays

    def _draw_char_by_char_animation(self, img: Image.Image, draw: ImageDraw.Draw,
                                      text: str, base_x: int, base_y: int,
                                      font, anim_progress: float,
                                      char_delays: List[float], line_height: int):
        """
        逐字绘制带随机弹跳动画的文字

        Args:
            img: 目标图像
            draw: 绘图对象
            text: 文字内容
            base_x: 基础X坐标（居中起始位置）
            base_y: 基础Y坐标
            font: 字体
            anim_progress: 整体动画进度 (0-1)
            char_delays: 每个字符的延迟时间列表
            line_height: 行高
        """
        import random

        # 动画总时长（与 title_anim_in_duration 对应）
        total_anim_duration = 0.8  # 秒

        # 累加字符宽度，计算每个字符的位置
        char_x = base_x
        max_char_height = 0

        for idx, char in enumerate(text):
            if char.strip() == '':
                # 空格，累加宽度
                bbox = draw.textbbox((0, 0), ' ', font=font)
                char_width = bbox[2] - bbox[0]
                char_x += char_width
                continue

            # 获取该字符的延迟时间
            char_delay = char_delays[idx] if idx < len(char_delays) else 0

            # 计算该字符的实际动画进度
            # 字符在延迟时间之后才开始动画
            char_start_time = char_delay
            char_anim_progress = max(0, min(1,
                (anim_progress * total_anim_duration - char_start_time) / (total_anim_duration * 0.5)
            ))

            # 计算弹跳动画参数
            if char_anim_progress <= 0:
                # 还没开始，不绘制
                bbox = draw.textbbox((0, 0), char, font=font)
                char_width = bbox[2] - bbox[0]
                char_x += char_width
                max_char_height = max(max_char_height, bbox[3] - bbox[1])
                continue

            # 计算该字符的弹跳参数
            char_scale, char_offset_y, char_alpha = self._calculate_bounce_animation(char_anim_progress)

            # 获取字符尺寸
            bbox = draw.textbbox((0, 0), char, font=font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]
            max_char_height = max(max_char_height, char_height)

            # 计算缩放后的尺寸和位置
            if char_scale != 1.0:
                scaled_size = int(68 * char_scale)  # 基于68号字体
                try:
                    scaled_font = ImageFont.truetype("simhei.ttf", scaled_size)
                except:
                    try:
                        scaled_font = ImageFont.truetype("msyh.ttc", scaled_size)
                    except:
                        scaled_font = font

                bbox_scaled = draw.textbbox((0, 0), char, font=scaled_font)
                scaled_width = bbox_scaled[2] - bbox_scaled[0]
                scaled_height = bbox_scaled[3] - bbox_scaled[1]

                # 居中对齐
                draw_x = char_x + (char_width - scaled_width) // 2
                draw_y = base_y + char_offset_y + (char_height - scaled_height) // 2
            else:
                draw_x = char_x
                draw_y = base_y + char_offset_y
                scaled_font = font

            # 绘制字符（带透明度）
            self._draw_text_with_alpha(img, draw, char, (draw_x, draw_y), scaled_font, char_alpha)

            # 移动到下一个字符位置
            char_x += char_width

    def _draw_text_with_alpha(self, img: Image.Image, draw: ImageDraw.Draw,
                               text: str, position: tuple, font, alpha: int):
        """
        绘制带透明度的文字

        Args:
            img: 目标图像
            draw: 绘图对象
            text: 文字内容
            position: 位置 (x, y)
            font: 字体
            alpha: 透明度 (0-255)
        """
        if alpha >= 255:
            # 完全不透明，直接绘制
            draw.text(position, text, fill=(0, 0, 0), font=font)
            return

        if alpha <= 0:
            # 完全透明，不绘制
            return

        # 获取文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if text_width <= 0 or text_height <= 0:
            return

        # 创建临时图像绘制文字
        text_img = Image.new('RGBA', (text_width + 4, text_height + 4), (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(text_img)
        text_draw.text((2, 2), text, fill=(0, 0, 0, alpha), font=font)

        # 粘贴到主图像
        x, y = position
        img.paste(text_img, (x - 2, y - 2), text_img)

    def create_shot_sequence(self, shots: List[Dict], output_dir: str,
                            main_title: str = None) -> Tuple[List[str], List[Dict]]:
        """
        创建分镜序列帧

        Args:
            shots: 分镜列表，每个包含 image_path, keyword, subtitle
            output_dir: 输出目录
            main_title: 主标题（仅在第一张图片时显示）

        Returns:
            (生成的帧文件路径列表, 分镜信息列表)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        frame_paths = []
        shot_info = []  # 保存每帧的位置信息供动画使用

        for i, shot in enumerate(shots):
            # 交替左右位置
            position = "left" if i % 2 == 0 else "right"

            # 只有第一张图片（i=0）时传递标题
            title = main_title if i == 0 else None

            frame = self.create_frame(
                image_path=shot.get("image_path"),
                keyword=shot.get("keyword", ""),
                subtitle=shot.get("subtitle", ""),
                position=position,
                title=title
            )

            # 保存帧
            frame_path = output_path / f"frame_{i:03d}.png"
            frame.save(frame_path, quality=95)
            frame_paths.append(str(frame_path))

            # 保存图片位置信息（供动画使用）
            if position == "left":
                img_x = self.left_x
                center_x = self.left_center
            else:
                img_x = self.right_x
                center_x = self.right_center

            shot_info.append({
                "index": i,
                "position": position,
                "img_x": img_x,
                "img_y": self.center_y,
                "img_width": self.IMAGE_WIDTH,
                "img_height": self.IMAGE_HEIGHT,
                "center_x": center_x,
                "keyword": shot.get("keyword", ""),
                "subtitle": shot.get("subtitle", ""),
                "image_path": shot.get("image_path"),
                "main_title": main_title if i == 0 else None  # 只在第一张图片保存主标题
            })

        return frame_paths, shot_info

    def create_video_from_frames(self, frame_paths: List[str],
                                durations: List[float],
                                audio_path: str,
                                output_path: str,
                                shot_info: List[Dict] = None) -> str:
        """
        从帧序列创建视频（带随机出场动画）
        优化：左边图片在下一张左边图片出现时才消失，右边同理

        Args:
            frame_paths: 帧文件路径列表
            durations: 每帧显示时长列表
            audio_path: 音频文件路径
            output_path: 输出视频路径
            shot_info: 每帧的图片位置信息列表（包含keyword, subtitle, image_path等）

        Returns:
            输出视频路径
        """
        import random
        if not frame_paths or not durations:
            raise ValueError("No frames or durations provided")

        # 创建临时目录存放帧序列
        temp_dir = Path(output_path).parent / "temp_frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        fps = 30
        frame_count = 0

        # 计算每个分镜的时间轴（累积时间）
        shot_timeline = []
        current_time = 0.0
        for i, duration in enumerate(durations):
            position = shot_info[i]['position'] if shot_info and i < len(shot_info) else ('left' if i % 2 == 0 else 'right')
            shot_timeline.append({
                'index': i,
                'start': current_time,
                'end': current_time + duration,
                'duration': duration,
                'position': position,
                'info': shot_info[i] if shot_info and i < len(shot_info) else None
            })
            current_time += duration

        # 计算每个分镜的实际显示结束时间（下一张同位置图片出现时才消失）
        for i, shot in enumerate(shot_timeline):
            position = shot['position']
            next_same_position_start = shot['end']  # 默认结束时间
            for j in range(i + 1, len(shot_timeline)):
                if shot_timeline[j]['position'] == position:
                    next_same_position_start = shot_timeline[j]['start']
                    break
            shot['display_end'] = next_same_position_start

        # 按时间点生成帧
        import math
        total_duration = sum(durations)
        total_frames = math.ceil(total_duration * fps)

        # 定期释放内存，避免大帧序列合成时内存耗尽
        import gc

        for frame_idx in range(total_frames):
            current_time = frame_idx / fps

            # 找到当前时间应该显示的图片（左右各一张）
            left_shot = None
            right_shot = None

            for shot in shot_timeline:
                if shot['start'] <= current_time < shot['display_end']:
                    if shot['position'] == 'left':
                        left_shot = shot
                    else:
                        right_shot = shot

            # 创建合成帧
            composite_frame = self._create_composite_frame_v2(
                left_shot, right_shot, current_time, fps
            )

            dest = temp_dir / f"frame_{frame_count:05d}.png"
            # 确保目录存在（某些 Windows 环境下大帧序列保存时可能偶发丢失父目录）
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                composite_frame.save(dest, "PNG")
            except Exception as save_err:
                print(f"  [WARNING] Failed to save frame {frame_count}: {save_err}")
                raise
            frame_count += 1

            # 每 30 帧释放一次内存
            if frame_count % 30 == 0:
                gc.collect()

        # 使用FFmpeg从帧序列创建视频
        # 音频音量增大200% (volume=3.0)
        # 注意：不使用-shortest，确保音频完整播放
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(temp_dir / "frame_%05d.png"),
            "-i", audio_path,
            "-af", "volume=5.0",  # 音频音量增大400%
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            # 使用 -shortest 保证视频与音频时长严格一致，避免声画不同步
            "-shortest",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        if result.returncode != 0:
            raise RuntimeError(f"Video creation failed: {result.stderr}")

        return output_path

    def _create_composite_frame_v2(self, left_shot: Dict, right_shot: Dict,
                                   current_time: float, fps: int) -> Image.Image:
        """
        创建合成帧，将左右图片合并到一帧中

        Args:
            left_shot: 当前应该显示的左边分镜（None表示没有）
            right_shot: 当前应该显示的右边分镜（None表示没有）
            current_time: 当前时间
            fps: 帧率

        Returns:
            合成后的帧
        """
        import random

        # 创建白色背景
        composite = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(composite)

        # 加载字体
        try:
            font_header = ImageFont.truetype("simhei.ttf", self.HEADER_FONT_SIZE)
            font_medium = ImageFont.truetype("simhei.ttf", self.SUBTITLE_FONT_SIZE)
            font_keyword = ImageFont.truetype("simhei.ttf", self.KEYWORD_FONT_SIZE)
        except:
            try:
                font_header = ImageFont.truetype("msyh.ttc", self.HEADER_FONT_SIZE)
                font_medium = ImageFont.truetype("msyh.ttc", self.SUBTITLE_FONT_SIZE)
                font_keyword = ImageFont.truetype("msyh.ttc", self.KEYWORD_FONT_SIZE)
            except:
                font_header = ImageFont.load_default()
                font_medium = font_header
                font_keyword = font_header

        # 1. 绘制顶部标题区（固定）
        self._draw_header(composite, draw, font_header, font_medium)

        # 2. 绘制左边内容（如果有）
        if left_shot and left_shot['info']:
            info = left_shot['info']
            self._draw_shot_content_v2(
                composite, draw, info, 'left', font_keyword,
                current_time, left_shot['start'], fps
            )

            # 如果是第一张图片且右边还没有图片出现，绘制右侧标题
            # 右侧标题在第2张图片（右边第一张）出现时消失
            if left_shot['index'] == 0 and right_shot is None:
                main_title = info.get('main_title', '')
                if main_title:
                    # 为每个字生成随机延迟（用于逐字弹跳动画）
                    char_delays = self._calculate_char_delays(main_title)

                    # 计算标题动画进度
                    # 入场动画：前0.8秒
                    # 停留：直到右边图片出现前0.6秒
                    # 出场动画：最后0.6秒淡出
                    title_start_time = left_shot['start']
                    title_anim_in_duration = 0.8  # 入场动画0.8秒
                    title_anim_out_duration = 0.6  # 出场动画0.6秒

                    # 计算右边图片何时出现
                    right_appears_time = left_shot['end']  # 第一张左边图片结束时间

                    time_in_title = current_time - title_start_time

                    if time_in_title < title_anim_in_duration:
                        # 入场弹跳动画阶段（逐字随机弹跳）
                        anim_progress = time_in_title / title_anim_in_duration
                        self._draw_right_title(composite, draw, main_title, font_header,
                                               anim_progress=anim_progress, anim_type="bounce_in",
                                               char_delays=char_delays)
                    elif current_time < right_appears_time - title_anim_out_duration:
                        # 正常显示阶段
                        self._draw_right_title(composite, draw, main_title, font_header,
                                               anim_progress=1.0, anim_type="bounce_in",
                                               char_delays=char_delays)
                    else:
                        # 出场淡出阶段
                        time_to_end = right_appears_time - current_time
                        if time_to_end > 0:
                            anim_progress = time_to_end / title_anim_out_duration
                            self._draw_right_title(composite, draw, main_title, font_header,
                                                   anim_progress=anim_progress, anim_type="fade_out")
                        # 否则不绘制（已完全淡出）

        # 3. 绘制右边内容（如果有）
        if right_shot and right_shot['info']:
            info = right_shot['info']
            self._draw_shot_content_v2(
                composite, draw, info, 'right', font_keyword,
                current_time, right_shot['start'], fps
            )

        # 4. 绘制底部字幕（显示最新的分镜字幕）
        current_shot = None
        for shot in [left_shot, right_shot]:
            if shot and (current_shot is None or shot['start'] > current_shot['start']):
                current_shot = shot

        if current_shot and current_shot['info']:
            subtitle = current_shot['info'].get('subtitle', '')
            self._draw_footer(composite, draw, subtitle, font_medium)

        return composite

    def _draw_shot_content_v2(self, composite: Image.Image, draw: ImageDraw.Draw,
                              shot_info: Dict, position: str, font_keyword,
                              current_time: float, shot_start: float, fps: int):
        """
        绘制分镜内容（图片+关键词）

        Args:
            composite: 合成帧
            draw: 绘图对象
            shot_info: 分镜信息（包含image_path, keyword等）
            position: 'left' 或 'right'
            font_keyword: 关键词字体
            current_time: 当前时间
            shot_start: 分镜开始时间
            fps: 帧率
        """
        import random

        # 确定位置
        if position == 'left':
            img_x = self.left_x
            center_x = self.left_center
        else:
            img_x = self.right_x
            center_x = self.right_center

        img_y = self.center_y
        img_width = self.IMAGE_WIDTH
        img_height = self.IMAGE_HEIGHT

        # 加载并绘制图片
        image_path = shot_info.get('image_path')
        if image_path and Path(image_path).exists():
            try:
                content_img = Image.open(image_path)
                # 缩放图片（保持比例，完整显示）
                content_img.thumbnail((img_width, img_height), Image.Resampling.LANCZOS)

                # 计算动画（入场动画）
                time_in_shot = current_time - shot_start
                anim_duration = 0.3  # 动画持续0.3秒

                if time_in_shot < anim_duration:
                    progress = time_in_shot / anim_duration
                    eased = self._ease_out_cubic(progress)

                    # 随机选择动画类型
                    anim_choices = ["slide_left", "slide_right", "slide_up", "fade",
                                  "zoom_in", "slide_left_slow", "fade_slow"]
                    anim_type = anim_choices[shot_info.get('index', 0) % len(anim_choices)]

                    # 应用动画
                    content_img = self._apply_animation_to_image(
                        content_img, anim_type, eased, img_width, img_height
                    )

                # 计算居中位置
                paste_x = img_x + (img_width - content_img.width) // 2
                paste_y = img_y + (img_height - content_img.height) // 2

                # 粘贴到合成帧
                if content_img.mode != 'RGB':
                    content_img = content_img.convert('RGB')
                composite.paste(content_img, (paste_x, paste_y))
            except Exception as e:
                print(f"  [WARNING] Image paste failed: {e}")

        # 绘制关键词（图片正上方：圆形图标 + 关键词）
        keyword = shot_info.get('keyword', '')
        if keyword:
            keyword_y = img_y - 100  # 图片上方留出空间

            # 获取文字宽度和高度
            bbox = draw.textbbox((0, 0), keyword, font=font_keyword)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 蓝色圆点（左侧，紧贴文字），圆心与文字视觉中心对齐
            dot_radius = 12
            dot_x = center_x - text_width // 2 - 35  # 圆点在文字左侧35px处
            dot_y = keyword_y + text_height // 2     # 圆心与文字中心同一水平线
            draw.ellipse([dot_x - dot_radius, dot_y - dot_radius,
                         dot_x + dot_radius, dot_y + dot_radius],
                        fill=(70, 130, 180))

            # 关键词文字（居中显示）
            text_x = center_x - text_width // 2
            text_y = keyword_y
            draw.text((text_x, text_y), keyword, fill=(51, 51, 51), font=font_keyword)

    def _apply_animation_to_image(self, img: Image.Image, anim_type: str,
                                  progress: float, target_width: int, target_height: int) -> Image.Image:
        """
        对图片应用动画效果

        Args:
            img: 原始图片
            anim_type: 动画类型
            progress: 动画进度 (0-1)
            target_width: 目标宽度
            target_height: 目标高度

        Returns:
            应用动画后的图片
        """
        # 确保图片是RGBA模式
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        img_width, img_height = img.size

        # 创建白色背景
        result = Image.new('RGBA', (target_width, target_height), (255, 255, 255, 255))

        # 计算居中位置
        paste_x = (target_width - img_width) // 2
        paste_y = (target_height - img_height) // 2

        if anim_type == "slide_left":
            # 从右侧滑入
            offset = int((1 - progress) * img_width)
            result.paste(img, (paste_x + offset, paste_y))
        elif anim_type == "slide_right":
            # 从左侧滑入
            offset = int((1 - progress) * img_width)
            result.paste(img, (paste_x - offset, paste_y))
        elif anim_type == "slide_up":
            # 从下方滑入
            offset = int((1 - progress) * img_height)
            result.paste(img, (paste_x, paste_y - offset))
        elif anim_type == "fade":
            # 淡入
            alpha = int(255 * progress)
            img_copy = img.copy()
            img_copy.putalpha(alpha)
            result.paste(img_copy, (paste_x, paste_y), img_copy)
            return result.convert('RGB')
        elif anim_type == "zoom_in":
            # 缩放淡入
            scale = 0.9 + 0.1 * progress
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            scaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            new_paste_x = (target_width - new_width) // 2
            new_paste_y = (target_height - new_height) // 2
            alpha = int(255 * progress)
            scaled.putalpha(alpha)
            result.paste(scaled, (new_paste_x, new_paste_y), scaled)
            return result.convert('RGB')
        elif anim_type == "slide_left_slow":
            # 缓慢从右侧滑入
            offset = int((1 - progress) * img_width * 0.3)
            result.paste(img, (paste_x + offset, paste_y))
        elif anim_type == "fade_slow":
            # 缓慢淡入（配合轻微放大）
            scale = 0.95 + 0.05 * progress
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            scaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            new_paste_x = (target_width - new_width) // 2
            new_paste_y = (target_height - new_height) // 2
            alpha = int(255 * progress)
            scaled.putalpha(alpha)
            result.paste(scaled, (new_paste_x, new_paste_y), scaled)
            return result.convert('RGB')
        else:
            result.paste(img, (paste_x, paste_y))

        return result.convert('RGB')

    def _generate_animation_frames(self, frame_path: str, duration: float,
                                  fps: int, anim_type: str,
                                  shot_info: Dict = None,
                                  is_first_shot: bool = False) -> List[Image.Image]:
        """
        生成单帧的动画序列（只对图片区域做动画）

        Args:
            frame_path: 原帧路径
            duration: 显示时长
            fps: 帧率
            anim_type: 动画类型
            shot_info: 图片位置信息
            is_first_shot: 是否是第一张图片（需要标题动画）

        Returns:
            动画帧列表
        """
        base_frame = Image.open(frame_path)
        total_frames = int(duration * fps)
        anim_frames_count = int(fps * 0.3)  # 动画持续约0.3秒
        fade_frames_count = int(fps * 0.2)  # 淡出动画持续约0.2秒

        frames = []
        for i in range(total_frames):
            is_animating = i < anim_frames_count and shot_info
            is_fading_out = (total_frames - i) <= fade_frames_count and is_first_shot

            if is_animating:
                # 图片入场动画阶段
                progress = i / anim_frames_count
                eased = self._ease_out_cubic(progress)

                frame = self._apply_image_animation(base_frame, anim_type, eased, shot_info)

                # 如果是第一张图片，同时做标题淡入动画
                if is_first_shot:
                    frame = self._apply_title_animation(frame, progress, "in")
                frames.append(frame)
            elif is_fading_out:
                # 第一张图片出场时标题淡出
                progress = (total_frames - i) / fade_frames_count
                eased = self._ease_out_cubic(progress)
                frame = self._apply_title_animation(base_frame.copy(), progress, "out")
                frames.append(frame)
            else:
                # 正常显示
                frame = base_frame.copy()
                # 如果是第一张图片且不是淡出阶段，保持标题可见
                if is_first_shot:
                    # 移除标题区域的动画效果，显示完整标题
                    pass
                frames.append(frame)

        return frames

    def _apply_image_animation(self, base_frame: Image.Image, anim_type: str,
                               progress: float, shot_info: Dict) -> Image.Image:
        """
        只对图片区域应用动画效果 - 保留顶部和底部标题区域不变

        Args:
            base_frame: 基础帧
            anim_type: 动画类型
            progress: 动画进度 (0-1)
            shot_info: 图片位置信息

        Returns:
            应用动画后的帧
        """
        # 创建白色背景帧
        frame = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))

        # 保留顶部标题区域（0 到 content_top）
        content_top = self.HEADER_HEIGHT + 50
        header_region = base_frame.crop((0, 0, self.width, content_top))
        frame.paste(header_region, (0, 0))

        # 保留底部标题区域（content_bottom 到视频底部）
        content_bottom = self.height - self.FOOTER_HEIGHT - 50
        footer_region = base_frame.crop((0, content_bottom, self.width, self.height))
        frame.paste(footer_region, (0, content_bottom))

        # 对图片区域应用动画
        if base_frame.mode != "RGBA":
            base_frame_rgba = base_frame.convert("RGBA")
        else:
            base_frame_rgba = base_frame

        # 获取图片区域
        img_x = shot_info.get("img_x", 0)
        img_y = shot_info.get("img_y", 0)
        img_width = shot_info.get("img_width", self.IMAGE_WIDTH)
        img_height = shot_info.get("img_height", self.IMAGE_HEIGHT)

        # 获取原始图片（从base_frame裁剪）
        original_img = base_frame.crop((img_x, img_y, img_x + img_width, img_y + img_height))

        # 根据动画类型计算图片位置
        if anim_type == "slide_left":
            # 从右侧滑入：图片从右侧外进入
            offset = int((1 - progress) * img_width)
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            result.paste(original_img, (offset, 0))
        elif anim_type == "slide_right":
            # 从左侧滑入：图片从左侧外进入
            offset = int((1 - progress) * img_width)
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            result.paste(original_img, (-offset, 0))
        elif anim_type == "slide_up":
            # 从下方滑入：图片从下方外进入
            offset = int((1 - progress) * img_height)
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            result.paste(original_img, (0, -offset))
        elif anim_type == "fade":
            # 淡入
            result = original_img.copy()
            alpha = int(255 * progress)
            result.putalpha(alpha)
        elif anim_type == "zoom_in":
            # 缩放淡入：从中心放大
            scale = 0.9 + 0.1 * progress
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            scaled = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # 创建透明背景
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            paste_x = (img_width - new_width) // 2
            paste_y = (img_height - new_height) // 2
            result.paste(scaled, (paste_x, paste_y))
            # 淡入
            alpha = int(255 * progress)
            result.putalpha(alpha)
        elif anim_type == "slide_left_slow":
            # 缓慢从右侧滑入
            offset = int((1 - progress) * img_width * 0.3)
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            result.paste(original_img, (offset, 0))
        elif anim_type == "fade_slow":
            # 缓慢淡入（配合轻微放大）
            result = original_img.copy()
            scale = 0.95 + 0.05 * progress
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            scaled = result.resize((new_width, new_height), Image.Resampling.LANCZOS)
            result = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255))
            paste_x = (img_width - new_width) // 2
            paste_y = (img_height - new_height) // 2
            result.paste(scaled, (paste_x, paste_y))
            alpha = int(255 * progress)
            result.putalpha(alpha)
        else:
            result = original_img.convert('RGBA')

        # 把动画后的图片区域贴回帧
        if result.mode == "RGBA":
            frame.paste(result, (img_x, img_y), result)
        else:
            frame.paste(result, (img_x, img_y))
            frame.paste(result, (img_x, img_y))

        return frame

    def _apply_title_animation(self, base_frame: Image.Image, progress: float,
                              anim_direction: str = "in") -> Image.Image:
        """
        对标题区域应用淡入淡出动画

        Args:
            base_frame: 基础帧
            progress: 动画进度 (0-1)
            anim_direction: "in" 入场动画, "out" 出场动画

        Returns:
            应用动画后的帧
        """
        # 创建帧副本
        frame = base_frame.copy()

        # 标题区域：右半边 (560 到 1040)
        title_left = self.half_width + 20
        title_right = self.width - 20
        title_top = self.content_top
        title_bottom = self.content_bottom

        # 裁剪标题区域
        title_region = frame.crop((title_left, title_top, title_right, title_bottom))

        # 根据动画方向计算透明度
        if anim_direction == "in":
            # 入场动画：淡入
            alpha = int(255 * progress)
        else:
            # 出场动画：淡出
            alpha = int(255 * (1 - progress))

        # 应用透明度
        if title_region.mode != "RGBA":
            title_region = title_region.convert("RGBA")
        title_region.putalpha(alpha)

        # 贴回帧
        frame.paste(title_region, (title_left, title_top), title_region)

        return frame

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        """缓出立方动画曲线"""
        return 1 - (1 - t) ** 3


# 快捷函数
def create_university_video(shots: List[Dict], theme: str,
                           audio_path: str, output_path: str,
                           main_title: str = None) -> str:
    """
    创建大学风格视频

    Args:
        shots: 分镜列表 [{image_path, keyword, subtitle, duration}]
        theme: 主题标题
        audio_path: 音频路径
        output_path: 输出路径
        main_title: 主标题（显示在第一张图片的右侧）

    Returns:
        输出视频路径
    """
    template = UniversityVideoTemplate(theme=theme)

    # 创建帧序列（返回帧路径和位置信息）
    frame_paths, shot_info = template.create_shot_sequence(
        shots, str(IMAGES_DIR / "frames"), main_title=main_title
    )

    # 提取时长
    durations = [s.get("duration", 3.0) for s in shots]

    # 创建视频（传递位置信息用于动画）
    return template.create_video_from_frames(
        frame_paths, durations, audio_path, output_path, shot_info
    )


if __name__ == "__main__":
    # 测试
    template = UniversityVideoTemplate(theme="大学就业篇")

    # 创建测试帧
    test_shots = [
        {
            "image_path": None,
            "keyword": "尽早实习",
            "subtitle": "第一件事",
            "duration": 3.0
        },
        {
            "image_path": None,
            "keyword": "信息来源",
            "subtitle": "第二件事",
            "duration": 3.0
        }
    ]

    frame_paths = template.create_shot_sequence(test_shots, "test_output")
    print(f"Created {len(frame_paths)} frames")