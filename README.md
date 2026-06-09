# 人脸识别签到签退系统 v1.0

基于 InsightFace 的实验室人脸识别签到签退系统。支持 QR 码扫码签到、高德地图定位校验、视频批量签到、三级角色管理、超时自动签退。

## 功能特性

- **QR 码签到/签退** — 管理员生成二维码，学生手机扫码完成签到/签退
- **高德定位校验** — 手机 GPS + 基站 + Wi-Fi 融合定位，强制 100m 范围内签到
- **人脸识别** — InsightFace SCRFD-10GF 检测 + ResNet50@WebFace600K 识别，GPU 加速
- **视频批量签到** — 上传视频自动检测所有人脸，去重后批量签到
- **自动签退** — 超时（默认 4 小时）自动签退，无需手动操作
- **三级角色** — 管理员 / 实验室指导教师 / 学生，不同权限
- **统计报表** — 签到率、平均时长、签到记录查询
- **cpolar 穿透** — 一键生成 HTTPS 公网 URL，手机远程访问
- **现代化 UI** — impeccable 设计系统，移动端优先，桌面端管理后台

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI (Python 3.10, async) |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) |
| 人脸识别 | InsightFace buffalo_l (SCRFD + ResNet50) |
| 推理加速 | ONNX Runtime GPU (CUDA + cuDNN 9) |
| 定位 | 高德 Web JS API + Haversine 距离算法 |
| QR 码 | qrcode + Pillow |
| 认证 | JWT + bcrypt |
| 前端 | 原生 HTML/CSS/JS，impeccable 设计 |
| HTTPS | cpolar 隧道 |

## 快速开始

### 环境要求

- Windows 10/11 + NVIDIA GPU（推荐 RTX 3060+，8GB 显存）
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda
- [cpolar](https://www.cpolar.com/)（HTTPS 穿透，手机扫码必需）

### 一键部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/2024zht/Homework-of-face-detector.git
cd Homework-of-face-detector

# 2. 从 environment.yml 创建完全一致的 conda 环境
conda env create -f environment.yml
conda activate facedetector

# 3. 安装 insightface（需从 GitHub 获取）
git clone https://github.com/deepinsight/insightface.git
cd insightface/python-package
pip install -e .
cd ../../Homework-of-face-detector

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入高德 API Key 和 cpolar URL

# 5. 启动
python run.py
```

### 手动安装（如果 environment.yml 不可用）

```bash
# 1. 创建环境
conda create -n facedetector python=3.10 -y
conda activate facedetector

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 GPU 推理环境（CUDA + cuDNN）
pip install onnxruntime-gpu==1.20.2 nvidia-cudnn-cu12 nvidia-cublas-cu12 nvidia-cuda-nvrtc-cu12
# Windows 需要手动复制 cuDNN DLL
python -c "
import shutil, os, sys
site = os.path.join(os.path.dirname(sys.executable), 'lib', 'site-packages')
src = os.path.join(site, 'nvidia', 'cudnn', 'bin', 'cudnn64_9.dll')
dst = os.path.join(site, 'onnxruntime', 'capi', 'cudnn64_9.dll')
if os.path.exists(src) and not os.path.exists(dst):
    shutil.copy2(src, dst); print('cuDNN DLL installed')
"

# 4. 安装 insightface
git clone https://github.com/deepinsight/insightface.git
cd insightface/python-package && pip install -e . && cd ../..

# 5. 配置并启动
cp .env.example .env
python run.py
```

### 配置 .env

```bash
CHECKIN_SECRET_KEY=随机字符串               # JWT 签名密钥
AMAP_KEY=你的高德Key                        # 高德 Web端(JS API)
AMAP_SECURITY_KEY=你的高德安全密钥           # 高德安全密钥
CHECKIN_BASE_URL=https://xxx.cpolar.top     # cpolar HTTPS URL
LAB_LAT=36.547308                           # 实验室纬度 (GCJ-02)
LAB_LNG=116.83223                           # 实验室经度 (GCJ-02)
LAB_NAME=实验室                             # 签到点名称
```

## 部署架构

```
手机浏览器 (HTTPS)
    │
    ▼
cpolar 隧道 (https://xxx.cpolar.top)
    │
    ▼
localhost:8080 (FastAPI + uvicorn)
    │
    ├── SQLite (checkin.db)
    ├── insightface GPU (人脸识别)
    └── 高德 API (逆地理编码)
```

### 启动 cpolar 隧道

```bash
# 下载: https://www.cpolar.com/download
.\cpolar http 8080
# 复制输出的 HTTPS URL 到 .env 的 CHECKIN_BASE_URL
```

### 首次使用步骤

1. `python run.py` 启动服务器
2. 浏览器打开 `http://localhost:8080` → 自动跳转登录页
3. 管理员 `admin` / `admin123` 登录
4. "签到点" → 添加实验室坐标（[高德坐标拾取器](https://lbs.amap.com/tools/picker)）
5. "人员管理" → 添加学生 → 上传正面照注册人脸
6. "生成二维码" → 展示在大屏上
7. 学生手机扫码 → 定位校验 → 输入姓名 → 签到成功

### 生产环境部署

```bash
# Linux (gunicorn)
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080

# Windows (uvicorn)
python -m uvicorn main:app --host 0.0.0.0 --port 8080
```

### 环境变量完整列表

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CHECKIN_SECRET_KEY` | JWT 签名密钥 | change-me-in-production |
| `AMAP_KEY` | 高德 Web JS API Key | — |
| `AMAP_SECURITY_KEY` | 高德安全密钥 | — |
| `CHECKIN_BASE_URL` | cpolar HTTPS URL | http://localhost:8080 |
| `LAB_LAT` | 实验室纬度 (GCJ-02) | 36.547308 |
| `LAB_LNG` | 实验室经度 (GCJ-02) | 116.83223 |
| `LAB_NAME` | 签到点名称 | 实验室 |

### 坐标系统说明

手机 GPS 返回 WGS-84 坐标，高德地图使用 GCJ-02（国测局加密）。系统会自动转换，无需手动处理。在[高德坐标拾取器](https://lbs.amap.com/tools/picker)上获取的坐标直接填入 `.env` 即可。

## 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 入口 + 自动签退后台任务
│   ├── config.py            # 配置（从环境变量读取密钥）
│   ├── database.py          # 数据库初始化 + 默认数据种子
│   ├── models.py            # ORM 模型 (User, Location, CheckIn, QRSession)
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── routes/
│   │   ├── auth.py          # 登录/注册 (bcrypt + JWT)
│   │   ├── qrcode.py        # QR 码生成/验证
│   │   ├── checkin.py       # 签到/签退/视频批量签到
│   │   └── admin.py         # 用户管理/签到点/统计
│   ├── services/
│   │   ├── face_service.py       # InsightFace 人脸检测+识别
│   │   ├── location_service.py   # Haversine 距离 + 高德逆地理编码
│   │   ├── qr_service.py         # QR 码生成
│   │   └── video_service.py      # 视频帧提取+人脸去重+批量匹配
│   └── utils/
│       └── security.py      # JWT 令牌工具
├── frontend/
│   ├── index.html           # 学生扫码签到页 (mobile-first)
│   ├── admin.html           # 管理后台 (仪表盘/QR/人员/签到点/记录)
│   ├── login.html           # 登录页
│   └── css/app.css          # impeccable 设计系统
├── static/                  # QR 码图片 + 签到照片 (运行时生成)
├── database/                # SQLite 数据库文件 (运行时生成)
├── .env.example             # 环境变量模板
├── requirements.txt
├── run.py                   # 启动脚本
└── start.bat                # Windows 一键启动
```

## API 文档

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 用户名密码登录 → JWT |
| POST | `/api/auth/register` | 注册新用户 |

### QR 码

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/qr/generate` | 生成签到/签退二维码 |
| GET | `/api/qr/validate/{token}` | 验证 QR token 有效性 |

### 签到签退

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/check/in` | 人脸签到（需 QR token + 定位 + 人脸照片） |
| POST | `/api/check/out` | 人脸签退 |
| POST | `/api/check/batch-video` | 上传视频批量人脸签到 |
| GET | `/api/check/status?user_id=` | 查询用户当前签到状态 |

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users` | 人员列表 |
| POST | `/api/admin/users` | 添加用户 |
| POST | `/api/admin/users/{id}/face` | 注册用户人脸 |
| POST | `/api/admin/users/{id}/deactivate` | 禁用用户 |
| GET | `/api/admin/locations` | 签到点列表 |
| POST | `/api/admin/locations` | 添加签到点 |
| GET | `/api/admin/statistics?date=` | 每日统计报表 |
| GET | `/api/admin/checkins?date=&user_id=` | 签到记录查询 |
| POST | `/api/admin/validate-location` | 验证位置是否在范围内 |

## 使用流程

### 管理员

1. 登录 `http://localhost:8080/login.html`（默认 admin / admin123）
2. **签到点** → 添加实验室坐标（去[高德坐标拾取器](https://lbs.amap.com/tools/picker)获取经纬度）
3. **人员管理** → 添加学生/教师 → 上传正面照注册人脸
4. **生成二维码** → 选择类型和签到点 → 点击生成
5. 将 QR 码展示在实验室大屏上

### 学生

1. 手机扫描大屏上的 QR 码
2. 浏览器自动打开签到页面
3. 授权位置 → 验证在实验室 100m 范围内
4. 打开摄像头 → 拍照 → 人脸识别 → 签到成功

### 签退

- **手动签退**：扫描签退 QR 码 + 人脸识别
- **自动签退**：签到 4 小时后系统自动签退

### 视频批量签到

管理员在后台 → 生成二维码 → 视频批量签到 → 上传视频文件 → 系统自动识别所有人脸并签到。

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

**首次使用请立即修改密码。**

## 高德 API Key 申请

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册 → 控制台 → 应用管理 → 创建应用
3. 添加 Key，服务平台选择 **"Web端(JS API)"**
4. 将 Key 和安全密钥填入 `.env` 文件

免费额度：每天 30 万次调用。

## License

MIT
