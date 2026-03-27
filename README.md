# IPTV 直播源收藏库

自动化采集、验证、按地区分类的 IPTV 直播源库。

## 频道分类

- [中国频道](./sources/china/) - CCTV、省级卫视、港澳台
- [亚洲频道](./sources/asia/) - 日本、韩国、东南亚
- [欧洲频道](./sources/europe/) - BBC、德法俄等
- [美洲频道](./sources/america/) - 美国、拉丁美洲
- [其他频道](./sources/other/) - 非洲、澳洲、体育等

## 使用方法

### 下载直播源

直接下载对应的 `.m3u` 文件：
- [中国频道列表](./sources/china/live.m3u)
- [亚洲频道列表](./sources/asia/live.m3u)
- [欧洲频道列表](./sources/europe/live.m3u)
- [美洲频道列表](./sources/america/live.m3u)
- [其他频道列表](./sources/other/live.m3u)

### 播放器使用

支持以下播放器：
- VLC
- PotPlayer
- IINA (macOS)
- IPTV Master

直接用播放器打开 `.m3u` 文件即可播放。

## 本地运行

```bash
git clone https://github.com/你的用户名/iptv-library.git
cd iptv-library
pip install -r requirements.txt

python main.py run      # 完整流程：采集+检查+分类
python main.py fetch    # 仅采集
python main.py check    # 仅检查
python main.py stats    # 查看统计
```

## 添加新源

编辑 `bloggers.json` 添加博主/仓库链接：

```json
{
  "name": "博主名称",
  "description": "描述",
  "level": 1,
  "urls": [
    "https://raw.githubusercontent.com/xxx/iptv/main/channels.m3u"
  ]
}
```

## 自动更新

GitHub Actions 每天凌晨 3:00 (UTC) 自动检查所有源，并更新可用列表。

## 项目结构

```
.
├── .github/workflows/   # GitHub Actions
├── src/
│   ├── fetcher.py       # 采集直播源
│   ├── checker.py       # 检查可用性
│   ├── classifier.py   # 按地区分类
│   └── storage.py       # 数据存储
├── sources/             # 可用直播源
│   ├── china/          # 中国频道
│   ├── asia/           # 亚洲频道
│   ├── europe/         # 欧洲频道
│   ├── america/        # 美洲频道
│   └── other/          # 其他频道
├── raw/                # 原始采集数据
├── logs/               # 检查日志
├── main.py             # 主程序
└── config.py           # 配置文件
```

## 协议说明

| 协议 | 说明 |
|------|------|
| http/https | 推荐，兼容性好 |
| rtmp | 稳定源保留，需特定播放器 |
| rtsp | 稳定源保留 |

## 注意事项

1. 所有源均为公开免费的直播源
2. 仅收录外网可直接访问的地址
3. 每天自动检查，失效源自动移除
4. 分类基于频道名称关键词匹配

## License

MIT License
