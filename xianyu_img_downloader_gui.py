# =============================================
# 🎨 闲鱼图片下载器 - 暗色扁平化GUI版
# 设计参考：yyl.ncet.top 深色主题
# =============================================

import tkinter as tk
from tkinter import ttk
import re
import os
import time
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ===== 暗色主题配色 =====
COLORS = {
    'bg': '#0d0d0d',
    'card': '#141414',
    'card_border': '#1a1a1a',
    'primary': '#409eff',
    'primary_hover': '#66b1ff',
    'success': '#67c23a',
    'warning': '#d4af37',
    'danger': '#f56c6c',
    'text': '#e0e0e0',
    'text_secondary': '#606266',
    'text_muted': '#4a4a4a',
    'input_bg': '#1a1a1a',
    'input_border': '#303133',
    'input_focus': '#409eff',
}

# ===== HTTP配置 =====
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

def is_product_link(url):
    patterns = [r'goofish\.com/item', r'2\.taobao\.com/item', r'm\.2\.taobao\.com/item',
                r'闲鱼\.cn/item', r'idlefish-f2e\.goofish\.com/item',
                r'market\.m\.taobao\.com/app/idleFish-F2e']
    return any(re.search(p, url, re.I) for p in patterns)

def is_image_link(url):
    return bool(re.search(r'img\.alicdn\.com|alipic\.com|taobaopic\.com', url, re.I))

def convert_to_original(url):
    original = url.strip()
    original = re.sub(r'\?x-oss-process=.*', '', original)
    original = re.sub(r'_\d+x\d+\.jpg', '.jpg', original)
    original = re.sub(r'_\.webp$', '.jpg', original)
    original = re.sub(r'\.jpg_\.webp$', '.jpg', original)
    if original.endswith('.webp'):
        original = original[:-5] + '.jpg'
    original = re.sub(r'_\d+x\d+\.jpg', '.jpg', original)
    return original

def fetch_images_from_product(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except:
        return []
    
    image_urls = []
    patterns = [r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?})</script>',
                r'<script[^>]*>window\.__NUXT__\s*=\s*({.*?})</script>']
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                found = set()
                def find_images(obj, depth=0):
                    if depth > 10: return
                    if isinstance(obj, dict):
                        for v in obj.values():
                            if isinstance(v, str) and 'alicdn.com' in v and re.search(r'\.(jpg|jpeg|png|webp)', v):
                                found.add(v)
                            else:
                                find_images(v, depth + 1)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_images(item, depth + 1)
                find_images(data)
                if found: return list(found)
            except: pass
    
    img_patterns = [
        r'https?://img\.alicdn\.com/imgextra/[^"\'<\s]+\.(?:jpg|jpeg|png|webp)',
        r'https?://img\.alicdn\.com/[^"\'<\s]+\.(?:jpg|jpeg|png|webp)',
    ]
    for p in img_patterns:
        matches = re.findall(p, html)
        for m in matches:
            clean = m.split('?')[0].split('!')[0]
            if clean not in image_urls:
                image_urls.append(clean)
    return image_urls

def download_single(args):
    url, save_path = args
    try:
        h = {**HEADERS, 'Referer': 'https://www.goofish.com/'}
        resp = requests.get(url, headers=h, timeout=30, stream=True)
        resp.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
        return True
    except:
        return False


# ===== 暗色主题按钮 =====
class DarkButton(tk.Frame):
    def __init__(self, master, text, command=None, width=120, height=38,
                 bg=COLORS['primary'], fg='#ffffff', font_size=11, bold=False):
        super().__init__(master, width=width, height=height, bg=COLORS['bg'])
        self.command = command
        self.pack_propagate(False)
        
        font_style = ('微软雅黑', font_size, 'bold' if bold else 'normal')
        
        self.btn = tk.Label(self, text=text, font=font_style,
                           fg=fg, bg=bg, cursor='hand2',
                           relief='flat', bd=0)
        self.btn.pack(fill='both', expand=True)
        
        self.btn.bind('<Button-1>', lambda e: self.command() if self.command else None)
        self.btn.bind('<Enter>', lambda e: self.btn.config(bg=COLORS['primary_hover'] if bg == COLORS['primary'] else bg))
        self.btn.bind('<Leave>', lambda e: self.btn.config(bg=bg))


# ===== 暗色输入框 =====
class DarkInput(tk.Frame):
    def __init__(self, master, height=150, **kwargs):
        super().__init__(master, bg=COLORS['bg'])
        
        # 边框
        self.border_frame = tk.Frame(self, bg=COLORS['input_border'], bd=0, highlightthickness=0)
        self.border_frame.pack(fill='both', expand=True)
        
        # 文本框
        self.text = tk.Text(self.border_frame, 
                           font=('微软雅黑', 10),
                           bg=COLORS['input_bg'],
                           fg=COLORS['text'],
                           relief='flat', bd=0,
                           padx=14, pady=10,
                           wrap='word',
                           insertbackground=COLORS['primary'],
                           selectbackground=COLORS['primary'],
                           selectforeground='#ffffff')
        self.text.pack(fill='both', expand=True, padx=1, pady=1)
        
        # 占位文字
        self.placeholder = tk.Label(self, text="📎 请粘贴链接...",
                                   font=('微软雅黑', 10),
                                   bg=COLORS['input_bg'],
                                   fg=COLORS['text_muted'])
        self.placeholder.place(x=18, y=12)
        self.placeholder.tkraise()
        
        # 事件绑定
        self.text.bind('<FocusIn>', self._on_focus_in)
        self.text.bind('<FocusOut>', self._on_focus_out)
        self.text.bind('<Key>', self._on_key)
    
    def _on_focus_in(self, e):
        self.placeholder.place_forget()
        self.border_frame.config(bg=COLORS['input_focus'])
    
    def _on_focus_out(self, e):
        self.border_frame.config(bg=COLORS['input_border'])
        if not self.text.get('1.0', 'end-1c').strip():
            self.placeholder.place(x=18, y=12)
    
    def _on_key(self, e):
        if self.text.get('1.0', 'end-1c').strip():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=18, y=12)
    
    def get_text(self):
        return self.text.get('1.0', 'end-1c').strip()
    
    def clear(self):
        self.text.delete('1.0', 'end')
        self.placeholder.place(x=18, y=12)
    
    def insert(self, text):
        self.text.insert('1.0', text)
        self.placeholder.place_forget()


# ===== 主应用 =====
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('闲鱼图片下载器')
        self.root.geometry('760x700')
        self.root.configure(bg=COLORS['bg'])
        self.root.minsize(640, 580)
        
        # 居中
        self.root.update_idletasks()
        w, h = 760, 700
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')
        
        self._build_ui()
        self.root.bind('<Control-Return>', lambda e: self.start())
    
    def _build_ui(self):
        # ===== 顶部 =====
        header = tk.Frame(self.root, bg=COLORS['bg'])
        header.pack(fill='x', padx=32, pady=(28, 0))
        
        # 标题
        title_frame = tk.Frame(header, bg=COLORS['bg'])
        title_frame.pack(anchor='w')
        
        title_icon = tk.Label(title_frame, text='🎨', font=('微软雅黑', 24), bg=COLORS['bg'])
        title_icon.pack(side='left')
        
        title_text = tk.Label(title_frame, text='闲鱼图片下载器',
                              font=('微软雅黑', 22, 'bold'),
                              fg=COLORS['text'], bg=COLORS['bg'])
        title_text.pack(side='left', padx=(10, 0))
        
        # 副标题
        subtitle = tk.Label(header, text='支持商品链接自动抓图 / 图片链接直接转换下载',
                           font=('微软雅黑', 9), fg=COLORS['text_secondary'], bg=COLORS['bg'])
        subtitle.pack(anchor='w', pady=(4, 0))
        
        # 分隔线
        divider = tk.Frame(self.root, height=1, bg=COLORS['card_border'])
        divider.pack(fill='x', padx=32, pady=(16, 0))
        
        # ===== 快捷键提示 =====
        tips = tk.Frame(self.root, bg=COLORS['bg'])
        tips.pack(fill='x', padx=32, pady=(10, 0))
        
        shortcut_frame = tk.Frame(tips, bg=COLORS['card'], bd=0, highlightthickness=0)
        shortcut_frame.pack(fill='x')
        
        # 快捷键标签
        keys = [
            ('Ctrl+Enter', '开始抓取'),
            ('Ctrl+V', '粘贴'),
            ('Ctrl+A', '全选'),
        ]
        for i, (key, desc) in enumerate(keys):
            k = tk.Label(shortcut_frame, text=key, font=('微软雅黑', 9),
                        fg=COLORS['primary'], bg=COLORS['card'])
            k.pack(side='left', padx=(16 if i == 0 else 20, 4), pady=6)
            d = tk.Label(shortcut_frame, text=desc, font=('微软雅黑', 9),
                        fg=COLORS['text_secondary'], bg=COLORS['card'])
            d.pack(side='left', pady=6)
        
        # ===== 输入卡片 =====
        input_card = tk.Frame(self.root, bg=COLORS['card'], bd=0, highlightthickness=0)
        input_card.pack(fill='both', expand=True, padx=32, pady=(10, 0))
        
        # 标题行
        input_header = tk.Frame(input_card, bg=COLORS['card'])
        input_header.pack(fill='x', padx=16, pady=(14, 4))
        
        input_label = tk.Label(input_header, text='📎 输入链接',
                               font=('微软雅黑', 12, 'bold'),
                               fg=COLORS['text'], bg=COLORS['card'])
        input_label.pack(side='left')
        
        input_count = tk.Label(input_header, text='支持批量',
                               font=('微软雅黑', 9),
                               fg=COLORS['text_muted'], bg=COLORS['card'])
        input_count.pack(side='right')
        
        input_desc = tk.Label(input_card, text='每行一个，商品链接或图片链接均可',
                             font=('微软雅黑', 9),
                             fg=COLORS['text_secondary'], bg=COLORS['card'])
        input_desc.pack(anchor='w', padx=16)
        
        # 输入框
        self.input = DarkInput(input_card, height=5)
        self.input.pack(fill='both', expand=True, padx=12, pady=(8, 14))
        
        # ===== 按钮区 =====
        btn_area = tk.Frame(self.root, bg=COLORS['bg'])
        btn_area.pack(fill='x', padx=32, pady=(10, 0))
        
        self.start_btn = DarkButton(btn_area, '🚀 开始抓取', self.start,
                                    width=130, height=40, font_size=12, bold=True)
        self.start_btn.pack(side='left')
        
        self.clear_btn = DarkButton(btn_area, '🗑️ 清空', self.clear,
                                    width=90, height=40, bg=COLORS['text_muted'], font_size=10)
        self.clear_btn.pack(side='left', padx=(10, 0))
        
        # 状态
        self.status_label = tk.Label(btn_area, text='就绪',
                                     font=('微软雅黑', 9),
                                     fg=COLORS['text_muted'], bg=COLORS['bg'])
        self.status_label.pack(side='right', padx=8)
        
        # ===== 日志卡片 =====
        log_card = tk.Frame(self.root, bg=COLORS['card'], bd=0, highlightthickness=0)
        log_card.pack(fill='both', expand=True, padx=32, pady=(10, 20))
        
        log_header = tk.Frame(log_card, bg=COLORS['card'])
        log_header.pack(fill='x', padx=16, pady=(14, 4))
        
        log_label = tk.Label(log_header, text='📋 运行日志',
                             font=('微软雅黑', 12, 'bold'),
                             fg=COLORS['text'], bg=COLORS['card'])
        log_label.pack(side='left')
        
        # 日志框
        self.log_text = tk.Text(log_card, height=9,
                                font=('Consolas', 9),
                                bg=COLORS['input_bg'],
                                fg=COLORS['text'],
                                relief='flat', bd=0,
                                padx=14, pady=10,
                                state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=12, pady=(4, 14))
        
        # 滚动条
        scrollbar = tk.Scrollbar(self.log_text, command=self.log_text.yview,
                                 bg=COLORS['card'], troughcolor=COLORS['input_bg'],
                                 bd=0, relief='flat')
        scrollbar.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # ===== 底部 =====
        footer = tk.Frame(self.root, bg=COLORS['bg'])
        footer.pack(fill='x', side='bottom', pady=(0, 10))
        
        footer_text = tk.Label(footer, text='闲鱼图片下载器 v3.0  ·  暗色主题',
                               font=('微软雅黑', 8),
                               fg=COLORS['text_muted'], bg=COLORS['bg'])
        footer_text.pack()
    
    def log(self, msg, color='text'):
        self.log_text.config(state='normal')
        tag = color
        self.log_text.insert('end', f'[{datetime.now().strftime("%H:%M:%S")}] ', 'time')
        self.log_text.insert('end', f'{msg}\n', tag)
        self.log_text.tag_config('time', foreground=COLORS['text_muted'])
        self.log_text.tag_config('text', foreground=COLORS['text'])
        self.log_text.tag_config('green', foreground=COLORS['success'])
        self.log_text.tag_config('red', foreground=COLORS['danger'])
        self.log_text.tag_config('blue', foreground=COLORS['primary'])
        self.log_text.tag_config('yellow', foreground=COLORS['warning'])
        self.log_text.tag_config('gray', foreground=COLORS['text_secondary'])
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.root.update_idletasks()
    
    def set_status(self, text, color='muted'):
        colors = {'muted': COLORS['text_muted'], 'primary': COLORS['primary'],
                  'success': COLORS['success'], 'danger': COLORS['danger']}
        self.status_label.config(text=text, fg=colors.get(color, COLORS['text_muted']))
        self.root.update_idletasks()
    
    def clear(self):
        self.input.clear()
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        self.set_status('已清空')
    
    def start(self):
        text = self.input.get_text()
        if not text:
            self.log('⚠️ 请先粘贴链接～', 'yellow')
            return
        
        self.start_btn.btn.config(state='disabled')
        self.set_status('处理中...', 'primary')
        
        thread = threading.Thread(target=self._process, args=(text,), daemon=True)
        thread.start()
    
    def _process(self, text):
        try:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            product_links = [l for l in lines if is_product_link(l)]
            image_links = [l for l in lines if is_image_link(l)]
            
            all_images = []
            
            if product_links:
                self.log(f'📦 检测到 {len(product_links)} 个商品链接，正在抓取...', 'blue')
                for i, link in enumerate(product_links, 1):
                    self.log(f'  [{i}/{len(product_links)}] 解析商品链接...', 'gray')
                    images = fetch_images_from_product(link)
                    if images:
                        self.log(f'  ✅ 找到 {len(images)} 张图片', 'green')
                        all_images.extend(images)
                    else:
                        self.log(f'  ⚠️ 未找到图片（可能需登录）', 'yellow')
            
            if image_links:
                self.log(f'🖼️ 检测到 {len(image_links)} 个图片链接，正在转换...', 'blue')
                for link in image_links:
                    all_images.append(convert_to_original(link))
                self.log(f'  ✅ 转换完成', 'green')
            
            all_images = list(dict.fromkeys(all_images))
            
            if not all_images:
                self.log('❌ 没有获取到任何图片', 'red')
                self.set_status('失败', 'danger')
                return
            
            self.log(f'📸 共获取 {len(all_images)} 张图片，开始下载...', 'blue')
            
            download_dir = Path(__file__).parent / 'downloads'
            download_dir.mkdir(exist_ok=True)
            save_dir = download_dir / time.strftime('%Y-%m-%d_%H-%M-%S')
            save_dir.mkdir(exist_ok=True)
            
            self.log(f'📁 保存到: {save_dir}', 'gray')
            
            tasks = []
            for i, url in enumerate(all_images):
                name = url.split('/')[-1].split('?')[0]
                if not name or len(name) < 5:
                    name = f'图片_{i+1}.jpg'
                if name.endswith('.webp'):
                    name = name[:-5] + '.jpg'
                if not name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    name += '.jpg'
                tasks.append((url, str(save_dir / name)))
            
            success = failed = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(download_single, t): t for t in tasks}
                for future in as_completed(futures):
                    if future.result():
                        success += 1
                    else:
                        failed += 1
                    self.set_status(f'下载中... {success+failed}/{len(tasks)}', 'primary')
            
            self.log(f'✅ 下载完成！成功 {success} 张', 'green')
            if failed > 0:
                self.log(f'⚠️ 失败 {failed} 张', 'yellow')
            self.log(f'📁 保存位置: {save_dir}', 'gray')
            self.set_status(f'✅ 完成 (成功{success}|失败{failed})', 'success')
            
        except Exception as e:
            self.log(f'❌ 错误: {str(e)}', 'red')
            self.set_status('出错', 'danger')
        finally:
            self.start_btn.btn.config(state='normal')
    
    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = App()
    app.run()
