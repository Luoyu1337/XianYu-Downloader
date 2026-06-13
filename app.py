# =============================================APP_VERSION = 'v1.0.0'

# 🎨 闲鱼图片/视频下载器 - Web后端
# 版本: v1.0.0 🎉
# 更新日志见 /api/changelog
# =============================================

import os
import re
import json
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB支持视频

# 下载目录
DOWNLOAD_DIR = Path(__file__).parent / 'downloads'
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 任务状态存储
tasks = {}


# ===== 工具函数 =====

def is_product_link(url):
    patterns = [r'goofish\.com/item', r'2\.taobao\.com/item', r'm\.2\.taobao\.com/item',
                r'闲鱼\.cn/item', r'idlefish-f2e\.goofish\.com/item',
                r'market\.m\.taobao\.com/app/idleFish-F2e']
    return any(re.search(p, url, re.I) for p in patterns)

def is_image_link(url):
    return bool(re.search(r'img\.alicdn\.com|alipic\.com|taobaopic\.com', url, re.I))

def is_video_link(url):
    return bool(re.search(r'video\.goofish\.com|goofish.*\.mp4|goofish.*video|\.mp4\?', url, re.I))

def convert_to_original(url):
    original = url.strip()
    original = re.sub(r'\?x-oss-process=.*', '', original)
    
    # 规则1: xxx.jpg_790x10000Q90.jpg_.webp → xxx.jpg_Q90.jpg（两层压缩+质量参数）
    original = re.sub(r'_\d+x\d+(Q\d+)\.jpg_\.webp$', r'_\1.jpg', original)
    
    # 规则2: xxx.jpg_310x310.jpg_.webp → xxx.jpg（尺寸+webp）
    original = re.sub(r'_\d+x\d+\.jpg_\.webp$', '.jpg', original)
    
    # 规则3: xxx.jpg_310x310.jpg → xxx.jpg（纯尺寸）
    original = re.sub(r'_\d+x\d+\.jpg$', '.jpg', original)
    
    # 规则4: xxx.jpg_.webp → xxx.jpg
    original = re.sub(r'_?\.webp$', '.jpg', original)
    
    # 规则5: xxx.webp → xxx.jpg
    if original.endswith('.webp'):
        original = original[:-5] + '.jpg'
    
    # 清理可能残留的 .jpg.jpg
    original = re.sub(r'\.jpg\.jpg$', '.jpg', original)
    
    return original

def fetch_images_from_product(url):
    """从闲鱼商品链接抓取图片（多种策略）"""
    image_urls = []
    
    # 策略1: 直接请求页面
    try:
        headers = {
            **HEADERS,
            'Referer': 'https://www.goofish.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': 'cna=; miid=;'
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return []
    
    # 策略2: 从 JSON 数据中提取
    json_patterns = [
        r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?})</script>',
        r'<script[^>]*>window\.__NUXT__\s*=\s*({.*?})</script>',
        r'<script[^>]*>window\.__DATA__\s*=\s*({.*?})</script>',
        r'<script[^>]*>window\.__preloadedState__\s*=\s*({.*?})</script>',
        r'<script[^>]*>window\.__PRELOADED_STATE__\s*=\s*({.*?})</script>',
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>({.*?})</script>',
        r'<script[^>]*>window\.__INITIAL_PROPS__\s*=\s*({.*?})</script>',
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                found = set()
                def find_images(obj, depth=0):
                    if depth > 15: return
                    if isinstance(obj, dict):
                        for v in obj.values():
                            if isinstance(v, str) and ('alicdn.com' in v or 'alipic.com' in v) and re.search(r'\.(jpg|jpeg|png|webp)', v):
                                # 清理URL
                                clean = v.split('?')[0].split('!')[0].split('_360x360')[0].split('_310x310')[0]
                                if clean not in found:
                                    found.add(clean)
                            else:
                                find_images(v, depth + 1)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_images(item, depth + 1)
                find_images(data)
                if found:
                    return list(found)
            except:
                pass
    
    # 策略3: 从 HTML 中提取所有 alicdn 图片链接
    # 先找所有 script 标签里的图片URL
    script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for script in script_matches:
        urls = re.findall(r'https?://img\.alicdn\.com[^"\'\\,\s<>]*\.(?:jpg|jpeg|png|webp)', script)
        for u in urls:
            clean = u.split('?')[0].split('!')[0].split('_360x360')[0].split('_310x310')[0].split('_60x60')[0]
            if clean not in image_urls:
                image_urls.append(clean)
    
    # 策略4: 从 HTML 标签属性中提取
    attr_patterns = [
        r'(?:src|data-src|data-original|data-img|img-url)=["\'](https?://[^"\']*alicdn[^"\']*\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
        r'(?:src|data-src|data-original)=["\'](https?://[^"\']*taobaopic[^"\']*\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
    ]
    for p in attr_patterns:
        matches = re.findall(p, html, re.IGNORECASE)
        for m in matches:
            clean = m.split('?')[0].split('!')[0].split('_360x360')[0].split('_310x310')[0]
            if clean not in image_urls:
                image_urls.append(clean)
    
    # 策略5: 直接全文搜图片URL
    img_urls = re.findall(r'https?://img\.alicdn\.com/imgextra/[^"\'<\s,;\)]+\.(?:jpg|jpeg|png|webp)', html)
    for u in img_urls:
        clean = u.split('?')[0].split('!')[0].split('_360x360')[0].split('_310x310')[0]
        if clean not in image_urls:
            image_urls.append(clean)
    
    return image_urls


def run_download(task_id, lines):
    """后台下载任务"""
    task = tasks[task_id]
    task['status'] = 'processing'
    task['logs'] = []
    task['start_time'] = time.time()
    
    def add_log(msg, level='info'):
        task['logs'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'msg': msg,
            'level': level
        })
    
    try:
        product_links = [l for l in lines if is_product_link(l)]
        image_links = [l for l in lines if is_image_link(l)]
        video_links = [l for l in lines if is_video_link(l) and not is_image_link(l) and not is_product_link(l)]
        
        all_images = []
        all_videos = []
        
        if product_links:
            add_log(f'📦 检测到 {len(product_links)} 个商品链接', 'info')
            for i, link in enumerate(product_links, 1):
                short = link[:50] + ('...' if len(link) > 50 else '')
                add_log(f'  [{i}/{len(product_links)}] 解析: {short}', 'info')
                images = fetch_images_from_product(link)
                if images:
                    add_log(f'  ✅ 找到 {len(images)} 张图片', 'success')
                    for j, img in enumerate(images[:2], 1):
                        add_log(f'    📸 [{j}] {img[:50]}...', 'info')
                    for img in images:
                        all_images.append((convert_to_original(img), img))
                else:
                    add_log(f'  ⚠️ 未找到图片', 'warning')
                    add_log(f'  💡 建议直接粘贴图片链接试试', 'info')
        
        if image_links:
            add_log(f'🖼️ 检测到 {len(image_links)} 个图片链接', 'info')
            for link in image_links:
                all_images.append((convert_to_original(link), link))
            add_log(f'  ✅ 转换完成', 'success')
        
        if video_links:
            add_log(f'🎬 检测到 {len(video_links)} 个视频链接', 'info')
            for link in video_links:
                all_videos.append((link, link))
            add_log(f'  ✅ 视频链接已就绪', 'success')
        
        seen = set()
        deduped = []
        for converted, original in all_images:
            if converted not in seen:
                seen.add(converted)
                deduped.append((converted, original))
        all_images = deduped
        
        if not all_images and not all_videos:
            add_log('❌ 没有获取到任何图片或视频', 'error')
            task['status'] = 'failed'
            return
        
        if all_images:
            add_log(f'📸 图片: {len(all_images)} 张', 'info')
        if all_videos:
            add_log(f'🎬 视频: {len(all_videos)} 个', 'info')
        
        save_dir = DOWNLOAD_DIR
        add_log(f'📁 保存到: {save_dir}', 'info')
        
        def dl(url, path, original_url=None, is_video=False):
            timeout = 300 if is_video else 30
            try:
                h = {**HEADERS, 'Referer': 'https://www.goofish.com/'}
                r = requests.get(url, headers=h, timeout=timeout, stream=True)
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        if chunk: f.write(chunk)
                return True, ''
            except Exception as e:
                if original_url and original_url != url:
                    try:
                        h2 = {**HEADERS, 'Referer': 'https://www.goofish.com/'}
                        r2 = requests.get(original_url, headers=h2, timeout=timeout, stream=True)
                        r2.raise_for_status()
                        with open(path, 'wb') as f2:
                            for chunk2 in r2.iter_content(8192):
                                if chunk2: f2.write(chunk2)
                        return True, '(使用原始链接)'
                    except Exception as e2:
                        return False, f'原始链接: {str(e2)[:60]}'
                return False, str(e)[:60]
        
        tasks_list = []
        for i, (converted_url, original_url) in enumerate(all_images):
            name = converted_url.split('/')[-1].split('?')[0]
            if not name or len(name) < 5:
                name = f'图片_{i+1}.jpg'
            if name.endswith('.webp'):
                name = name[:-5] + '.jpg'
            if not name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                name += '.jpg'
            tasks_list.append((converted_url, str(save_dir / name), original_url, False))
        
        for i, (video_url, original_video_url) in enumerate(all_videos):
            name = video_url.split('/')[-1].split('?')[0]
            if not name or len(name) < 5:
                name = f'视频_{i+1}.mp4'
            if not name.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                name += '.mp4'
            tasks_list.append((video_url, str(save_dir / name), original_video_url, True))
        
        success = failed = 0
        total = len(tasks_list)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(dl, u, p, o, v): (u, p, o, v) for u, p, o, v in tasks_list}
            from concurrent.futures import as_completed
            for future in as_completed(futures):
                ok, err = future.result()
                if ok:
                    success += 1
                else:
                    failed += 1
                    add_log(f'  ❌ 下载失败: {err[:80]}', 'error')
                task['progress'] = f'{success+failed}/{total}'
        
        if all_videos and all_images:
            add_log(f'✅ 下载完成！图片 {len([t for t in tasks_list if not t[3]])} 张, 视频 {len([t for t in tasks_list if t[3]])} 个 🎉', 'success')
        elif all_videos:
            add_log(f'✅ 视频下载完成！成功 个 🎉', 'success')
        else:
            add_log(f'✅ 图片下载完成！成功 张 🎉', 'success')
        if failed > 0:
            add_log(f'⚠️ 失败 个', 'warning')
        add_log(f'📁 保存位置: {save_dir}', 'info')
        
        task['status'] = 'completed'
        task['success'] = success
        task['failed'] = failed
        
    except Exception as e:
        add_log(f'❌ 错误: {str(e)}', 'error')
        task['status'] = 'failed'


# ===== API 路由 =====

@app.route('/')
def index():
    resp = render_template('index.html')
    # 禁止浏览器缓存，确保每次加载最新页面
    from flask import make_response
    response = make_response(resp)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/submit', methods=['POST'])
def submit():
    """提交链接"""
    data = request.get_json()
    if not data or 'links' not in data:
        return jsonify({'error': '请提供链接'}), 400
    
    text = data['links'].strip()
    if not text:
        return jsonify({'error': '链接不能为空'}), 400
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return jsonify({'error': '链接不能为空'}), 400
    
    task_id = str(int(time.time() * 1000))
    tasks[task_id] = {
        'status': 'pending',
        'logs': [],
        'progress': '0/0',
        'success': 0,
        'failed': 0,
        'save_dir': '',
        'start_time': None,
    }
    
    # 后台运行
    thread = threading.Thread(target=run_download, args=(task_id, lines), daemon=True)
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """获取任务状态"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({
        'status': task['status'],
        'logs': task['logs'],
        'progress': task['progress'],
        'success': task['success'],
        'failed': task['failed'],
        'save_dir': task['save_dir'],
    })

@app.route('/api/files/<path:filename>')
def download_file(filename):
    """下载文件"""
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)


@app.route('/api/changelog')
def get_changelog():
    return jsonify({
        'version': 'v1.0.0',
        'logs': [
            {'ver': 'v1.0.0', 'date': '2026-05-06', 'items': [
                '🎉 首个正式版本发布',
                '🖼️ 支持闲鱼图片链接转换下载',
                '🎬 支持闲鱼视频链接下载',
                '📦 支持商品链接自动抓取图片',
                '🔍 链接完整性实时检测',
                '🔄 下载失败自动回退原始链接',
                '🐛 修复图片两层压缩转换问题',
                '🐛 修复 .jpg.jpg 重复后缀问题',
                '⚡ 视频下载超时300秒',
                '📁 保存路径简化为 downloads 目录',
            ]}
        ]
    })


if __name__ == '__main__':
    print('🚀 闲鱼图片下载器 Web服务启动中...')
    print(f'📁 下载目录: {DOWNLOAD_DIR}')
    print(f'🌐 访问地址: http://127.0.0.1:5000')
    print()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
