#!/usr/bin/env python3
"""
知乎头像生成器
生成专业的数字货币交易平台头像
"""

from PIL import Image, ImageDraw, ImageFont
import math
import os

def create_zhihu_avatar():
    # 头像尺寸 (知乎推荐 200x200)
    size = 200
    img = Image.new('RGB', (size, size), color='white')
    draw = ImageDraw.Draw(img)
    
    # 背景渐变色 (深蓝到浅蓝)
    for y in range(size):
        ratio = y / size
        r = int(20 + (100 - 20) * ratio)
        g = int(50 + (150 - 50) * ratio) 
        b = int(120 + (255 - 120) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    # 绘制圆形边框
    border_width = 8
    draw.ellipse([border_width//2, border_width//2, size-border_width//2, size-border_width//2], 
                outline='white', width=border_width)
    
    # 绘制中心图标 - 加密货币符号
    center_x, center_y = size // 2, size // 2
    
    # 绘制比特币符号 ₿
    # 主要的B字母
    font_size = 60
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # 绘制 "₿" 符号
    symbol = "₿"
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = center_x - text_width // 2
    text_y = center_y - text_height // 2
    
    # 添加阴影效果
    shadow_offset = 2
    draw.text((text_x + shadow_offset, text_y + shadow_offset), symbol, 
              font=font, fill=(0, 0, 0, 128))
    
    # 主要文本
    draw.text((text_x, text_y), symbol, font=font, fill='white')
    
    # 添加装饰性元素 - 小圆点
    dot_positions = [
        (30, 30), (170, 30), (30, 170), (170, 170),
        (100, 20), (20, 100), (180, 100), (100, 180)
    ]
    
    for x, y in dot_positions:
        draw.ellipse([x-3, y-3, x+3, y+3], fill='white')
    
    return img

def create_article_cover():
    # 文章封面尺寸 (知乎推荐 1200x628)
    width, height = 1200, 628
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 创建渐变背景
    for y in range(height):
        ratio = y / height
        r = int(15 + (30 - 15) * ratio)
        g = int(25 + (60 - 25) * ratio)
        b = int(50 + (120 - 50) * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))
    
    # 添加网格背景图案
    grid_size = 40
    grid_color = (255, 255, 255, 20)
    
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)
    
    # 主标题
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 72)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 36)
        small_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
    except:
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    
    # 标题文本
    title = "Trademe"
    subtitle = "AI驱动的数字货币策略交易平台"
    description = "集成Claude AI • 智能策略生成 • 专业级回测分析"
    
    # 计算文本位置
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    title_y = height // 3
    
    # 绘制标题阴影
    shadow_offset = 4
    draw.text((title_x + shadow_offset, title_y + shadow_offset), title, 
              font=title_font, fill=(0, 0, 0, 150))
    
    # 绘制主标题
    draw.text((title_x, title_y), title, font=title_font, fill='white')
    
    # 副标题
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (width - subtitle_width) // 2
    subtitle_y = title_y + 90
    
    draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=(200, 220, 255))
    
    # 描述文本
    desc_bbox = draw.textbbox((0, 0), description, font=small_font)
    desc_width = desc_bbox[2] - desc_bbox[0]
    desc_x = (width - desc_width) // 2
    desc_y = subtitle_y + 60
    
    draw.text((desc_x, desc_y), description, font=small_font, fill=(180, 200, 255))
    
    # 装饰性元素 - 加密货币图标
    icon_size = 60
    icons_y = height - 120
    
    # 绘制几个加密货币符号
    crypto_symbols = ["₿", "Ξ", "⟐"]  # Bitcoin, Ethereum, Litecoin风格
    icon_spacing = 150
    start_x = (width - (len(crypto_symbols) * icon_spacing)) // 2
    
    for i, symbol in enumerate(crypto_symbols):
        x = start_x + i * icon_spacing
        
        # 圆形背景
        circle_radius = 35
        draw.ellipse([x - circle_radius, icons_y - circle_radius, 
                     x + circle_radius, icons_y + circle_radius], 
                    fill=(255, 255, 255, 30), outline='white', width=2)
        
        # 符号
        symbol_bbox = draw.textbbox((0, 0), symbol, font=subtitle_font)
        symbol_width = symbol_bbox[2] - symbol_bbox[0]
        symbol_height = symbol_bbox[3] - symbol_bbox[1]
        
        symbol_x = x - symbol_width // 2
        symbol_y = icons_y - symbol_height // 2
        
        draw.text((symbol_x, symbol_y), symbol, font=subtitle_font, fill='white')
    
    # 添加URL水印
    watermark = "github.com/trademe"
    watermark_x = width - 200
    watermark_y = height - 40
    draw.text((watermark_x, watermark_y), watermark, font=small_font, fill=(150, 170, 200))
    
    return img

def main():
    # 创建assets目录
    assets_dir = '/root/trademe/assets'
    os.makedirs(assets_dir, exist_ok=True)
    
    print("🎨 生成知乎头像...")
    avatar = create_zhihu_avatar()
    avatar_path = os.path.join(assets_dir, 'zhihu_avatar.png')
    avatar.save(avatar_path, 'PNG', quality=95)
    print(f"✅ 头像已保存: {avatar_path}")
    
    print("🎨 生成文章封面...")
    cover = create_article_cover()
    cover_path = os.path.join(assets_dir, 'zhihu_article_cover.png')
    cover.save(cover_path, 'PNG', quality=95)
    print(f"✅ 封面已保存: {cover_path}")
    
    print("\n📊 文件信息:")
    print(f"头像尺寸: {avatar.size}")
    print(f"封面尺寸: {cover.size}")
    
    return avatar_path, cover_path

if __name__ == "__main__":
    main()