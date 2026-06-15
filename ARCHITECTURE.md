# 实验室智能签到管理系统 — 架构与功能文档

> **Lab Check-in System** — QR码 + GPS定位 + 人脸识别 智能签到管理
>
> 版本 V1.0 | 2026-06-15

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [目录结构](#4-目录结构)
5. [数据模型](#5-数据模型)
6. [API 接口全览](#6-api-接口全览)
7. [核心功能详解](#7-核心功能详解)
8. [认证与权限](#8-认证与权限)
9. [人脸识别服务](#9-人脸识别服务)
10. [位置服务](#10-位置服务)
11. [QR码服务](#11-qr码服务)
12. [视频批量签到](#12-视频批量签到)
13. [自动签退机制](#13-自动签退机制)
14. [前端页面](#14-前端页面)
15. [配置与部署](#15-配置与部署)
16. [后台任务](#16-后台任务)
17. [自我学习机制](#17-自我学习机制)
18. [数据导出](#18-数据导出)

---

## 1. 项目概述

一套**低成本、易部署、高精度**的实验室智能签到管理系统，融合 QR 扫码、GPS 定位、人脸识别技术，实现"扫码即签到、摄像头无感签到、离场自动签退"的全流程自动化。

### 解决的痛点

| 痛点 | 传统方式 | 本系统 |
|------|----------|--------|
| 签到效率低 | 纸质签到/点名 2-3分钟/人 | 扫码或人脸识别 <10秒 |
| 代签现象 | 无法杜绝 | 人脸生物识别 + GPS 双重验证 |
| 安全管理弱 | 不知道实验室内有谁 | 实时签到状态可视化 |
| 统计繁琐 | 学期末人工汇总 | 一键导出 Excel 统计报表 |

### 项目目标

- 单次签到 ≤10 秒
- 代签率降至 0%
- 人脸识别准确率 ≥95%
- 支持 50 人以上同时签到

---

## 2. 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI (Python 3.10+) | 异步高性能 REST API，自动 OpenAPI 文档 |
| **数据库** | SQLite + SQLAlchemy 2.0 async | 零配置，ORM 支持切换至 PostgreSQL |
| **人脸检测** | InsightFace SCRFD-10GF | 轻量高精度检测 |
| **人脸识别** | InsightFace ResNet50@WebFace600K | 512 维归一化特征向量 |
| **推理引擎** | ONNX Runtime GPU | CUDAExecutionProvider + CPU fallback |
| **认证** | JWT (HS256) + bcrypt | 24h 有效期令牌 |
| **坐标转换** | WGS-84 ↔ GCJ-02 数学模型 | 解决手机GPS与高德100-500m偏差 |
| **距离计算** | Haversine 公式 | 球面距离，三坐标系自适应取最小值 |
| **地图服务** | 高德 REST API | 逆地理编码 |
| **QR码** | qrcode (Python) + UUID Token | 5分钟有效期，一次性 |
| **视频处理** | OpenCV | 逐帧检测 + 跨帧去重 |
| **前端** | 原生 HTML/CSS/JS | 无框架，移动端兼容 |
| **内网穿透** | cpolar | 公网 HTTPS 隧道 |
| **Excel** | openpyxl | 多 Sheet 样式化报表 |

---

## 3. 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    前端层 (Frontend)                          │
│  login.html · index.html · admin.html · student.html        │
│  (登录页)     (签到页)      (管理后台)     (学生面板)         │
├──────────────────────────────────────────────────────────────┤
│                  API 网关层 (FastAPI)                         │
│  /api/auth · /api/qr · /api/check · /api/admin · /static/   │
│           + CORSMiddleware + StaticFiles                     │
├──────────────────────────────────────────────────────────────┤
│                    服务层 (Services)                          │
│  face_service │ location_service │ qr_service │ video_service│
│  (InsightFace)│ (Haversine+高德) │ (QR/TUUID) │ (OpenCV)    │
├──────────────────────────────────────────────────────────────┤
│                    数据层 (Database)                          │
│  SQLite / SQLAlchemy ORM async — 4 张核心表                  │
│  users · locations · checkins · qr_sessions                  │
├──────────────────────────────────────────────────────────────┤
│                    外部服务                                    │
│  高德API · InsightFace · cpolar                              │
└──────────────────────────────────────────────────────────────┘
```

### 请求流水线

```
浏览器 ──HTTP──▶ FastAPI Router
                   │
                   ▼
             Dependency Injection (get_db, get_current_admin)
                   │
                   ▼
             Service Layer (face/location/qr/video)
                   │
                   ▼
             SQLAlchemy AsyncSession → SQLite
```

### 关键设计决策

1. **全链路 async/await**：路由 → 数据库 → HTTP 客户端均异步，不阻塞事件循环
2. **惰性加载人脸模型**：~300MB 模型首次请求时才加载，减少冷启动时间
3. **3重坐标自适应**：WGS↔WGS、WGS→GCJ、GCJ↔WGS 三种距离取最小值
4. **优先级签到策略**：姓名+人脸(1:1) > 人脸(1:N) > 姓名(精确查找)
5. **线程池隔离**：视频处理通过 `asyncio.to_thread()` 放入线程池

---

## 4. 目录结构

```
Homework-of-face-detector/
├── run.py                       # 启动入口：加载 .env → uvicorn
├── gen_report.py                # 需求分析 Word 报告生成器
├── environment.yml              # Conda 环境配置
├── README.md                    # 快速开始指南
│
├── backend/
│   ├── main.py                  # FastAPI 应用工厂、lifespan、路由挂载
│   ├── config.py                # 全局配置（密钥、阈值、路径）
│   ├── database.py              # 异步引擎、表创建、种子数据、迁移
│   ├── models.py                # ORM: User, Location, CheckIn, QRSession
│   ├── schemas.py               # Pydantic 请求/响应 DTO
│   ├── routes/
│   │   ├── auth.py              # 登录 / 注册 / 忘记密码 / 重置密码
│   │   ├── qrcode.py            # QR 生成 / 验证 / 自助获取
│   │   ├── checkin.py           # 签到 / 签退 / 视频批量 / 自动签退
│   │   └── admin.py             # 用户管理 / 签到点 / 统计 / 导出 / 更正
│   ├── services/
│   │   ├── face_service.py      # InsightFace 封装 + 自我学习
│   │   ├── location_service.py  # WGS↔GCJ 转换 + Haversine + 高德API
│   │   ├── qr_service.py        # QR 会话生成与验证
│   │   └── video_service.py     # 视频帧采样 + 去重 + 批量匹配
│   └── utils/
│       ├── security.py          # JWT 创建 / 解码
│       └── time_utils.py        # 北京时间 (UTC+8) 辅助函数
│
├── frontend/
│   ├── login.html               # 登录 + 忘记密码（人脸验证重置）
│   ├── index.html               # 移动端签到/签退（GPS + 人脸）
│   ├── admin.html               # 管理后台（6个Tab）
│   ├── student.html             # 学生面板（签到状态 + 签到方式）
│   └── css/app.css              # 设计系统样式
│
├── static/
│   ├── photos/                  # 签到照片存储
│   └── qrcodes/                 # QR 码图片存储
│
└── database/
    └── checkin.db               # SQLite 数据库文件
```

---

## 5. 数据模型

### ER 关系图

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│   User   │ 1───N │   CheckIn    │ N───1 │ Location │
│          │       │              │       │          │
│ id (PK)  │       │ id (PK)      │       │ id (PK)  │
│ username │       │ user_id (FK) │       │ name     │
│ name     │       │ location_id  │       │ lat/lng  │
│ role     │       │ check_in/out │       │ radius   │
│ face_emb │       │ lat/lng      │       └──────────┘
│ pwd_hash │       │ status       │
└──────────┘       │ corrected_by │
      │            └──────────────┘
      │ 1───N
      ▼
┌──────────────┐
│  QRSession   │
│ token (PK)   │
│ type         │
│ location_id  │
│ generated_by │
│ expires_at   │
└──────────────┘
```

### 表结构

#### `users` — 用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `username` | VARCHAR(50) UNIQUE | 登录名，索引 |
| `password_hash` | VARCHAR(128) | bcrypt 哈希 |
| `name` | VARCHAR(100) | 真实姓名 |
| `role` | VARCHAR(20) | admin / instructor / student |
| `face_embedding` | LARGEBINARY | 512维 float32 特征（numpy→bytes） |
| `face_photo_path` | VARCHAR(500) | 注册人脸照片路径 |
| `is_active` | BOOLEAN | 是否激活（软删除） |
| `created_at` | DATETIME | 创建时间（北京时间） |

#### `locations` — 签到点表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `name` | VARCHAR(200) | 签到点名称 |
| `latitude` | FLOAT | GCJ-02 纬度 |
| `longitude` | FLOAT | GCJ-02 经度 |
| `radius_meters` | INTEGER | 有效范围（默认100m） |
| `created_by` | FK→users.id | 创建者 |
| `is_active` | BOOLEAN | 是否启用 |

#### `checkins` — 签到记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `user_id` | FK→users.id | 签到用户，索引 |
| `check_in_time` | DATETIME | 签到时间，索引 |
| `check_out_time` | DATETIME | 签退时间 |
| `location_id` | FK→locations.id | 签到点 |
| `lat` / `lng` | FLOAT | 用户GPS位置 |
| `location_name` | VARCHAR(500) | 签到点名称（冗余） |
| `check_in_photo` | VARCHAR(500) | 签到照片路径 |
| `check_out_photo` | VARCHAR(500) | 签退照片路径 |
| `is_auto_checkout` | BOOLEAN | 是否自动签退 |
| `status` | VARCHAR(20) | active / completed |
| `original_user_id` | FK→users.id | 原始识别用户（更正前） |
| `corrected_by` | FK→users.id | 更正操作管理员 |
| `corrected_at` | DATETIME | 更正时间 |

#### `qr_sessions` — QR会话表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `token` | VARCHAR(64) UNIQUE | UUID 令牌，索引 |
| `type` | VARCHAR(10) | checkin / checkout |
| `location_id` | FK→locations.id | 关联签到点 |
| `generated_by` | FK→users.id | 生成者 |
| `created_at` | DATETIME | 创建时间 |
| `expires_at` | DATETIME | 过期时间（默认+5分钟） |
| `is_used` | BOOLEAN | 是否已使用（一次性） |

---

## 6. API 接口全览

### 认证 `/api/auth`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/login` | 用户名密码登录 → JWT | 公开 |
| POST | `/register` | 注册新用户 | 公开 |
| POST | `/forgot-password` | 检查用户是否可人脸重置密码 | 公开 |
| POST | `/reset-password` | 人脸验证后重置密码 | 公开（需匹配人脸） |

### QR码 `/api/qr`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/generate` | 生成签到/签退 QR码 | admin/instructor |
| GET | `/validate/{token}` | 验证 Token 有效性 | 公开 |
| POST | `/self` | 学生自助获取签到 QR | 登录用户 |
| GET | `/image/{filename}` | 获取 QR 图片 | 公开 |

### 签到 `/api/check`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/in` | 签入（QR码/摄像头直连） | 公开（需有效token或人脸） |
| POST | `/out` | 签出 | 公开（需人脸匹配） |
| GET | `/status` | 查询签到状态 | 公开 |
| POST | `/self-out` | 自助签退 | 登录用户 |
| POST | `/batch-video` | 上传视频批量签入 | 公开（需有效QR） |

### 管理 `/api/admin`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/users` | 用户列表（可按role筛选） | admin/instructor |
| POST | `/users` | 创建用户 | admin/instructor |
| POST | `/users/{id}/face` | 为用户注册人脸 | admin/instructor |
| POST | `/users/{id}/deactivate` | 停用用户 | admin/instructor |
| POST | `/users/{id}/reset-password` | 管理员重置密码 | admin/instructor |
| GET | `/locations` | 签到点列表 | admin/instructor |
| POST | `/locations` | 创建签到点 | admin/instructor |
| GET | `/statistics` | 今日统计仪表盘 | admin/instructor |
| GET | `/checkins` | 签到记录（学生仅看自己） | 登录用户 |
| POST | `/checkins/{id}/correct` | 更正签到记录 + 自我学习 | admin/instructor |
| POST | `/validate-location` | 验证位置是否在范围内 | 公开 |
| GET | `/export` | 导出 Excel 报表 | admin/instructor |

### 系统路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/` | 登录页 |
| GET | `/checkin.html` | 签到签退页 |
| GET | `/admin.html` | 管理后台 |
| GET | `/student.html` | 学生面板 |

---

## 7. 核心功能详解

### 7.1 签到流程（多因素）

```
扫码/打开签到页
     │
     ▼
┌──────────────┐
│ Step 1: GPS  │  WGS-84 → GCJ-02 转换
│   定位校验    │  Haversine 三重计算取最小值
│              │  ≤100m ✓  |  >100m ✗
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 2: 身份  │  优先级降级策略：
│   识别        │  ① 姓名+人脸 → 1:1 验证
│              │  ② 仅人脸 → 1:N 开放集匹配
│              │  ③ 仅姓名 → 精确查找
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 3: 签到  │  检查无活跃签到
│   确认        │  保存签到照片
│              │  自我学习融合 embedding
│              │  标记 QR 已使用
└──────────────┘
```

### 7.2 防重复签到

同一用户只能有 1 条 `status=active` 的记录，再次签到返回 "Already checked in" 错误。

### 7.3 签退方式

| 方式 | 触发 | 说明 |
|------|------|------|
| 手动签退 | 扫描签退QR码 + 身份验证 | 主动操作 |
| 自动签退 | 后台每5分钟扫描 | 签到超4小时自动签退 |
| 自助签退 | POST `/api/check/self-out` | 登录用户无需QR |

---

## 8. 认证与权限

### JWT 流程

```
登录 → bcrypt.checkpw() 验证密码
     → 生成 JWT: { sub: 用户ID, role: 角色, exp: 24h后 }
     → 前端存储 → 后续请求 Authorization: Bearer <token>
```

### 三级角色权限矩阵

| 功能 | admin | instructor | student |
|------|:-----:|:----------:|:-------:|
| 用户管理 (CRUD) | ✓ | ✓ | ✗ |
| 人脸注册 | ✓ | ✓ | ✗ |
| 生成QR码 | ✓ | ✓ | ✓(自助) |
| 查看所有签到记录 | ✓ | ✓ | ✗ |
| 查看自己记录 | ✓ | ✓ | ✓ |
| 签到/签退 | ✓ | ✓ | ✓ |
| 统计数据 | ✓ | ✓ | ✗ |
| Excel导出 | ✓ | ✓ | ✗ |
| 签到更正 + 自我学习 | ✓ | ✓ | ✗ |
| 重置他人密码 | ✓ | ✓ | ✗ |
| 人脸重置自己密码 | ✓ | ✓ | ✓ |

---

## 9. 人脸识别服务

### 模型架构

```
InsightFace "buffalo_l":
  ├── SCRFD-10GF        人脸检测 (640×640)
  └── ResNet50          特征提取 → 512维归一化向量
       @ WebFace600K

推理引擎: ONNX Runtime
优先级: CUDAExecutionProvider → CPUExecutionProvider (自动降级)
```

### 核心 API

```python
extract_embedding(image_data: bytes) -> np.ndarray      # (512,) float32
extract_embedding_from_base64(b64: str) -> np.ndarray   # Base64 → embedding
match_face(emb, candidates: [(id, bytes)]) -> id|None   # 1:N 余弦相似度匹配
embedding_to_bytes(emb: np.ndarray) -> bytes            # numpy → DB 存储
bytes_to_embedding(data: bytes) -> np.ndarray           # DB → numpy
save_checkin_photo(data, filename) -> str               # 保存照片
update_embedding(old_bytes, new_emb) -> bytes           # 自我学习融合
```

### 匹配策略

- **余弦相似度** = 向量内积（embedding 已 L2 归一化）
- **阈值**: 0.25 (FACE_SIMILARITY_THRESHOLD)
- 选择相似度最高且 ≥ 阈值的候选人
- 人脸注册时自动选最大人脸（按 bbox 面积）

---

## 10. 位置服务

### 坐标系兼容

手机 GPS 返回 **WGS-84**，高德使用 **GCJ-02**，国内偏移 100-500m。系统通过三重计算自适应：

```
用户坐标(?坐标系) → 签到点(GCJ-02)
    ├─ 方案1: WGS-84 vs GCJ-02 (直接)
    ├─ 方案2: 用户→GCJ-02 vs GCJ-02 (转换用户坐标)
    └─ 方案3: WGS-84 vs 签到点→GCJ-02 (转换签到点坐标)
              │
              ▼
        取最小值 → 判断 ≤ radius_meters
```

### WGS-84 → GCJ-02 转换

基于国家测绘局公开的多项式偏移模型，在国内范围外直接返回原坐标。

### 高德 API 集成

- **逆地理编码**：经纬度 → 中文地址
- **签名**：MD5(排序参数 + AMAP_SECURITY_KEY)
- **客户端**：httpx 异步，5秒超时

---

## 11. QR码服务

### 生成流程

```
管理员: 选择类型 + 签到点
         ↓
  生成 UUID Token → 存入 qr_sessions (expires = now + 5min)
         ↓
  QR内容 = {BASE_URL}/checkin.html?token={uuid}&type={type}&location_id={id}
         ↓
  qrcode 库生成 PNG → static/qrcodes/
```

### 安全机制

- **一次性**：`is_used` 标记，验证后立即标记
- **时效**：5分钟有效期
- **类型校验**：签到 QR ≠ 签退 QR
- **位置校验**：扫码后仍需 GPS

---

## 12. 视频批量签到

### 处理管道

```
上传视频 (.mp4)
     │
     ▼
┌──────────────┐
│ 帧采样        │  每0.5s一帧，跳过 ≤50px 小人脸
│ (OpenCV)      │
└──────────────┘
     │
     ▼
┌──────────────┐
│ 跨帧去重      │  余弦相似度 0.45 合并同人
│ (VideoPerson) │  每 track 保留最佳人脸
└──────────────┘
     │
     ▼
┌──────────────┐
│ 人脸匹配      │  track.embedding vs 用户库 (1:N)
│ (match_face)  │  阈值 0.25
└──────────────┘
     │
     ▼
┌──────────────┐
│ 批量签到      │  跳过已签到用户
│              │  保存人脸照片 → 创建 CheckIn
└──────────────┘
```

### 线程安全

视频处理通过 `asyncio.to_thread()` 在线程池中执行，不阻塞事件循环：

```python
result = await asyncio.to_thread(process_video, video_path=..., ...)
```

---

## 13. 自动签退机制

### 后台循环任务

在 FastAPI `lifespan` 中启动，每 5 分钟扫描：

```python
async def auto_checkout_loop():
    while True:
        # cutoff = now - 4h
        # 查找 status=active AND check_in_time ≤ cutoff
        # 设置 check_out_time, status=completed, is_auto_checkout=True
        await asyncio.sleep(300)
```

前端通过 `/api/check/status` 获取 `auto_checkout_at` 以显示倒计时。

---

## 14. 前端页面

### 页面矩阵

| 页面 | 文件 | 用户 | 功能 |
|------|------|------|------|
| 登录 | `login.html` | 所有 | 登录 + 人脸验证重置密码 |
| 签到 | `index.html` | 学生 | GPS定位 → 人脸/姓名 → 签到/签退 |
| 管理 | `admin.html` | admin/instructor | 仪表盘/QR/人员/签到点/记录/导出 6个Tab |
| 学生 | `student.html` | 学生 | 状态看板 + 扫码/摄像头/视频签到 + 自助签退 |

### 管理后台 Tab

| Tab | 功能 |
|-----|------|
| **仪表盘** | 统计卡片 + 最近记录表 + 更正按钮 + 导出入口 |
| **生成二维码** | 类型/签到点选择 → QR图片 + 签到链接 |
| **人员管理** | 用户 CRUD + 人脸注册 + 禁用 + 重置密码 |
| **签到点** | 签到点 CRUD |
| **签到记录** | 日期/用户/状态筛选 + 导出（学生仅看自己） |
| **数据导出** | 日期范围 → 带样式 Excel 报表 |

### 移动端签到页

3 步引导式 UI：
1. **验证位置** → GPS → 后端验证 → 显示距离和地址
2. **身份确认** → 摄像头拍照/输入姓名 → 人脸识别
3. **签到结果** → 成功/失败提示 + 详情

---

## 15. 配置与部署

### 环境变量 (`.env`)

```ini
CHECKIN_SECRET_KEY=your-jwt-secret        # JWT 签名密钥
AMAP_KEY=your-gaode-api-key              # 高德 Web API Key
AMAP_SECURITY_KEY=your-security-key      # 高德安全密钥（MD5签名）
CHECKIN_BASE_URL=https://xxx.cpolar.top  # 公网访问地址
LAB_LAT=36.547308                        # 实验室纬度 (GCJ-02)
LAB_LNG=116.83223                        # 实验室经度 (GCJ-02)
LAB_NAME=实验室                           # 签到点名称
```

### 关键配置常量 (`config.py`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | sqlite+aiosqlite:///database/checkin.db | 数据库 |
| `JWT_EXPIRE_MINUTES` | 1440 (24h) | Token 有效期 |
| `CHECKIN_RADIUS_METERS` | 100 | 允许签到距离 |
| `QR_EXPIRE_MINUTES` | 5 | QR 有效期 |
| `AUTO_CHECKOUT_HOURS` | 4 | 自动签退时间 |
| `FACE_SIMILARITY_THRESHOLD` | 0.25 | 人脸匹配阈值 |
| `INSIGHTFACE_MODEL` | buffalo_l | 人脸模型 |
| `PORT` | 8080 | 服务端口 |

### 启动

```bash
python run.py                                          # 一键启动
cd backend && uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 数据库初始化

- `lifespan` 启动时自动调用 `init_db()`
- 自动建表 + 增量迁移（SQLite ALTER TABLE 兼容处理）
- 种子数据：admin (admin/admin123)、测试用户 (gxf/123456)、默认签到点

---

## 16. 后台任务

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()                                   # 启动: 建表+种子
    task = asyncio.create_task(auto_checkout_loop())  # 启动: 自动签退循环
    yield                                             # 运行
    task.cancel()                                     # 关闭
```

---

## 17. 自我学习机制

每次成功的人脸匹配签到，通过**移动平均**融合新 embedding：

```python
LEARNING_RATE = 0.15
blended = 0.85 * old_embedding + 0.15 * new_embedding
blended = normalize(blended)   # L2 归一化
```

### 融合时机

1. **签到成功**：匹配后立即融合到用户 `face_embedding`
2. **管理员更正**：从签到照片提取 embedding 融合到正确目标用户

### 效果

随签到次数增加，存储的 embedding 逐渐涵盖不同角度、光照、表情，变得更鲁棒。

---

## 18. 数据导出

### Excel 报表（openpyxl）

通过 `GET /api/admin/export` 生成：

**Sheet 1 — 签到统计汇总**
- 导出时间和筛选条件
- 总记录/进行中/已完成/自动签退 统计
- 按用户分组：用户名、姓名、角色、签到次数、平均时长

**Sheet 2 — 签到明细记录**
- 序号、姓名、用户名、角色、签到时间、签退时间、签到点、时长、状态、签到方式
- 表头着色 + 交替行背景

### 筛选参数

`date` 按日期 / `user_id` 按用户 / `status` 按状态

---

## 附录 A：签到时序图

```
学生手机              FastAPI                 InsightFace           高德API
   │                    │                        │                    │
   │─POST /check/in──▶  │                        │                    │
   │ {token,face_b64,   │──validate QR──────────▶│                    │
   │  lat,lng}          │──verify location───────│────────────────▶│
   │                    │◀───距离/地址───────────│────────────────│
   │                    │──extract_embedding()──▶│                    │
   │                    │◀──(512,) array─────────│                    │
   │                    │──match_face(1:N)──────▶│                    │
   │                    │◀──best user_id─────────│                    │
   │                    │──save CheckIn──────────▶│                    │
   │                    │──update_embedding()────▶│                    │
   │◀──{id,name,status}─│                        │                    │
```

---

## 附录 B：已知限制与未来方向

### 当前限制

- SQLite 并发写入有限，高并发建议升级 PostgreSQL
- InsightFace 模型首次加载 ~2-5 秒
- 依赖手机 GPS，室内精度下降
- 无原生 App（可 PWA 缓解）

### 扩展方向

- 教务系统数据对接
- UWB/蓝牙信标室内精确定位
- PWA + 推送通知
- WebSocket 实时签到推送
- Docker 容器化
- 多校区分布式部署

---

> 文档生成：2026-06-15 | 项目：`D:\Homework-of-face-detector`
