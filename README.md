# XianYu-Downloader
<small>2026.6.14</small>


轻量级闲鱼图片/视频下载工具，支持商品链接自动抓图并下载原图&视频。

## 特性

- 商品链接图片提取（闲鱼 / 淘宝）
- 图片直链与视频直链下载
- 简洁 Web UI

## 环境要求

- Python 3.8+
- Windows / macOS / Linux

## 安装

```bash
cd XianYu-Downloader
pip install flask flask-cors requests
```

## 运行

```bash
python app.py
```

Windows 用户可运行：

```bat
启动服务.bat
```

打开浏览器访问： `http://localhost:5000`

## 项目结构

```
XianYu-Downloader/
├── app.py
├── app.py.bak
├── README.md
├── 启动服务.bat
├── downloads/
├── static/
└── templates/
    └── index.html
```

## 已知支持的链接

- `goofish.com/item/*`
- `2.taobao.com/item/*`
- `m.2.taobao.com/item/*`
- `闲鱼.cn/item/*`
- `img.alicdn.com/*`
- `video.goofish.com/*`

## 许可证

MIT License

---

## ⚠️ 免责声明

本项目仅供学习和研究使用，使用者需自行承担使用本工具的一切后果。

- 不涉及任何商业目的
- 遵守相关法律法规
- 尊重原创内容的版权
- 不得用于违法用途

---

<div align="center">

**Made with by DeepSeek**

如果对你有帮助，请给个 ⭐️ Star 吧！
<a href="tencent://message/?uin=407486320&Site=&Menu=yes" 
target="_blank" title="点击添加服主好友">🐧QQ:757453794</a>

[返回顶部](#-闲鱼图片下载器)

</div>
