# 实验室智能签到管理系统 — 架构与功能文档

> **Lab Check-in System** — QR码 + GPS定位 + 人脸识别 + 点名任务 智能签到管理
>
> 版本 V3.0 | 2026-06-16

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
12. [签到任务（Session）](#12-签到任务session)
13. [视频批量签到](#13-视频批量签到)
14. [自动签退机制](#14-自动签退机制)
15. [前端页面](#15-前端页面)
16. [配置与部署](#16-配置与部署)
17. [后台任务](#17-后台任务)
18. [自我学习机制](#18-自我学习机制)
19. [数据导出](#19-数据导出)

---

## 1. 项目概述

一套**低成本、易部署、高精度**的实验室智能签到管理系统，融合 QR 扫码、GPS 定位、人脸识别技术，V3.0 新增点名任务（Session）机制，支持教师按日期范围、时间段、周期发布签到任务并指定目标学生。

### V3.0 新增特性

- **点名任务 (CheckInSession)** — 教师/管理员发布签到任务，指定签到点、时间段、日期范围、周期规则、目标学生
- **时间段控制** — 支持日期范围 (2026-06-16~06-20) + 每日时间段 (08:00-20:00) + 每周重复 (周一至周五/每周六)
- **多任务并行** — 支持同时发布多个签到任务，学生可选择特定任务签到
- **用户精准指定** — 管理员可勾选哪些学生需要参与某个任务，未指定者无法签到
- **学生任务选择** — 学生页面展示可签到的任务列表，点击任务选择扫码或拍照签到
- **签到方式弹窗** — 二维码签到与摄像头签到的双栏选择器
- **签到点删除** — 软删除签到点 (is_active=False)

### 解决的痛点

| 痛点 | 传统方式 | 本系统 |
|------|----------|--------|
| 签到效率低 | 纸质签到/点名 2-3分钟/人 | 扫码或人脸识别 <10秒 |
| 代签现象 | 无法杜绝 | 人脸生物识别 + GPS 双重验证 |
| 安全管理弱 | 不知道实验室内有谁 | 实时签到状态可视化 |
| 统计繁琐 | 学期末人工汇总 | 一键导出 Excel 统计报表 |
| 无任务机制 | 学生随时可签到 | 教师发布点名任务，限定时间+地点+人员 |

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
| **前端** | 原生 HTML/CSS/JS | 无框架，移动端兼容，impeccable 设计系统 |
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
│  SQLite / SQLAlchemy ORM async — 5 张核心表                  │
│  users · locations · checkins · qr_sessions · checkin_sessions│
├──────────────────────────────────────────────────────────────┤
│                    外部服务                                    │
│  高德API · InsightFace · cpolar                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. 目录结构

```
Homework-of-face-detector/
├── run.py                       # 启动入口
├── README.md                    # 快速开始指南
├── ARCHITECTURE.md              # 架构文档（本文件）
├── environment.yml              # Conda 环境配置
│
├── backend/
│   ├── main.py                  # FastAPI 应用工厂、lifespan、路由挂载
│   ├── config.py                # 全局配置（密钥、阈值、路径）
│   ├── database.py              # 异步引擎、表创建、种子数据、增量迁移
│   ├── models.py                # ORM: User, Location, CheckIn, QRSession, CheckInSession
│   ├── schemas.py               # Pydantic 请求/响应 DTO
│   ├── routes/
│   │   ├── auth.py              # 登录 / 注册 / 忘记密码 / 人脸重置密码
│   │   ├── qrcode.py            # QR 生成 / 验证 / 自助获取
│   │   ├── checkin.py           # 签到/签退/视频批量/自动签退/任务查询
│   │   └── admin.py             # 用户管理/签到点/统计/导出/更正/任务管理
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
│   ├── admin.html               # 管理后台（仪表盘/QR/人员/签到点/记录）
│   ├── student.html             # 学生面板（任务列表 + 签到方式选择）
│   └── css/app.css              # impeccable 设计系统
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
│ pwd_hash │       │ status       │            ▲
└──────────┘       │ corrected_by │            │
     │ 1───N       └──────────────┘            │
     ▼                                         │
┌──────────────┐                               │
│  QRSession   │                               │
│ token (PK)   │                               │
│ type         │                               │
│ location_id ─┼───────────────────────────────┘
│ generated_by │
│ expires_at   │
└──────────────┘

┌──────────────────┐
│ CheckInSession   │  ← V3.0 新增
│ id (PK)          │
│ location_id (FK)─┼──▶ Location
│ created_by (FK)──┼──▶ User
│ status           │     active / ended
│ start_date       │     日期范围起始
│ end_date         │     日期范围结束
│ checkin_start_time│    每日签到开始时间
│ checkin_end_time │     每日签到结束时间
│ recurring_days   │     周期重复 (0=Mon...6=Sun)
│ target_user_ids  │     目标学生ID列表
└──────────────────┘
```

### 新增表 checkin_sessions (V3.0)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `location_id` | FK→locations.id | 签到点 |
| `created_by` | FK→users.id | 发布者 |
| `status` | VARCHAR(20) | active / ended |
| `created_at` | DATETIME | 创建时间 |
| `ended_at` | DATETIME | 结束时间 |
| `start_date` | DATE | 有效期起始 (null=不限) |
| `end_date` | DATE | 有效期结束 (null=不限) |
| `checkin_start_time` | TIME | 每日签到开始时间 (null=不限) |
| `checkin_end_time` | TIME | 每日签到结束时间 (null=不限) |
| `recurring_days` | VARCHAR(20) | 逗号分隔星期数 "0,1,2,3,4" |
| `target_user_ids` | TEXT | 逗号分隔用户ID (null=所有人) |

### 任务时间校验逻辑

```python
def is_session_time_valid(session):
    now = beijing_now_naive()
    if session.start_date and now.date() < session.start_date: return False
    if session.end_date   and now.date() > session.end_date:   return False
    if session.recurring_days and str(now.weekday()) not in session.recurring_days.split(','): return False
    if session.checkin_start_time and now.time() < session.checkin_start_time: return False
    if session.checkin_end_time   and now.time() > session.checkin_end_time:   return False
    return True
```

### 表结构一览

#### `users` — 用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `username` | VARCHAR(50) UNIQUE | 登录名 |
| `password_hash` | VARCHAR(128) | bcrypt 哈希 |
| `name` | VARCHAR(100) | 真实姓名 |
| `role` | VARCHAR(20) | admin / instructor / student |
| `face_embedding` | LARGEBINARY | 512维 float32 特征向量 |
| `face_photo_path` | VARCHAR(500) | 注册人脸照片路径 |
| `is_active` | BOOLEAN | 软删除标记 |
| `created_at` | DATETIME | 创建时间（北京时间） |

#### `locations` — 签到点表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `name` | VARCHAR(200) | 名称 |
| `latitude` / `longitude` | FLOAT | GCJ-02 坐标 |
| `radius_meters` | INTEGER | 有效范围 (默认100m) |
| `created_by` | FK→users.id | 创建者 |
| `is_active` | BOOLEAN | 软删除标记 |

#### `checkins` — 签到记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 |
| `user_id` | FK→users.id | 签到用户 |
| `check_in_time` / `check_out_time` | DATETIME | 签到/签退时间 |
| `location_id` | FK→locations.id | 签到点 |
| `lat` / `lng` | FLOAT | 用户GPS位置 |
| `location_name` | VARCHAR(500) | 签到点名称（冗余快照） |
| `check_in_photo` / `check_out_photo` | VARCHAR(500) | 签到/签退照片路径 |
| `is_auto_checkout` | BOOLEAN | 是否自动签退 |
| `status` | VARCHAR(20) | active / completed |
| `original_user_id` | FK→users.id | 原始识别用户（更正前） |
| `corrected_by` | FK→users.id | 更正操作管理员 |
| `corrected_at` | DATETIME | 更正时间 |

---

## 6. API 接口全览

### 认证 `/api/auth`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/login` | 用户名密码登录 → JWT | 公开 |
| POST | `/register` | 注册新用户 | 公开 |
| POST | `/forgot-password` | 检查用户是否可人脸重置密码 | 公开 |
| POST | `/reset-password` | 人脸验证后重置密码 | 公开 |

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
| POST | `/in` | 签入 (支持 session_id 指定任务) | 公开 |
| POST | `/out` | 签出 | 公开 |
| GET | `/status` | 查询签到状态 | 公开 |
| POST | `/self-out` | 自助签退 | 登录用户 |
| POST | `/batch-video` | 上传视频批量签入 | 公开 |
| GET | `/session/active` | 获取当前可签到的任务列表 | 登录用户 |

### 管理 `/api/admin`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/users` | 用户列表 | admin/instructor |
| POST | `/users` | 创建用户 | admin/instructor |
| POST | `/users/{id}/face` | 注册人脸 | admin/instructor |
| POST | `/users/{id}/deactivate` | 停用用户 | admin/instructor |
| POST | `/users/{id}/reset-password` | 重置密码 | admin/instructor |
| GET | `/locations` | 签到点列表 | admin/instructor |
| POST | `/locations` | 创建签到点 | admin/instructor |
| DELETE | `/locations/{id}` | 删除签到点 (软删除) | admin/instructor |
| GET | `/statistics` | 今日统计仪表盘 | admin/instructor |
| GET | `/checkins` | 签到记录查询 | 登录用户 |
| POST | `/checkins/{id}/correct` | 更正记录 + 自我学习 | admin/instructor |
| POST | `/validate-location` | 验证位置 | 公开 |
| GET | `/export` | 导出 Excel 报表 | admin/instructor |
| POST | `/sessions` | 创建签到任务 | admin/instructor |
| POST | `/sessions/{id}/end` | 结束签到任务 | admin/instructor |
| GET | `/sessions/active` | 查看所有进行中任务 | admin/instructor |

---

## 7. 核心功能详解

### 7.1 签到流程（V3.0 含任务门控）

```
扫码/打开签到页
     │
     ▼
┌──────────────┐
│ Step 0: 任务  │  检查活跃签到任务
│   检查        │  无任务→拒绝 / 非签到时间→提示
│              │  支持 session_id 指定特定任务
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 1: GPS  │  WGS-84 → GCJ-02，Haversine 三重计算
│   定位校验    │
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 2: 身份  │  ① 姓名+人脸→1:1 ② 仅人脸→1:N ③ 仅姓名
│   识别        │
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 3: 用户  │  验证用户是否在任务 target_user_ids 中
│   目标校验    │
└──────────────┘
     │
     ▼
┌──────────────┐
│ Step 4: 签到  │  防重复签到 + 保存照片 + 自我学习
│   确认        │
└──────────────┘
```

### 7.2 学生签到方式选择

```
学生点击任务 [签到] → 弹窗
      ┌─────────────┐
      │ 选择签到方式  │
      │ 实验室 08-20 │
      │             │
      │ ┌────┐┌────┐│
      │ │扫码││拍照││
      │ └────┘└────┘│
      └─────────────┘
```

---

## 8. 认证与权限

### 三级角色权限矩阵

| 功能 | admin | instructor | student |
|------|:-----:|:----------:|:-------:|
| 用户管理 (CRUD) | ✓ | ✓ | ✗ |
| 人脸注册 | ✓ | ✓ | ✗ |
| 签到点管理 (含删除) | ✓ | ✓ | ✗ |
| 发布/结束签到任务 | ✓ | ✓ | ✗ |
| 指定任务目标学生 | ✓ | ✓ | ✗ |
| 查看可签到任务列表 | ✓ | ✓ | ✓ |
| 签到/签退 | ✓ | ✓ | ✓ |
| 查看自己记录 | ✓ | ✓ | ✓ |
| Excel导出 | ✓ | ✓ | ✗ |
| 签到更正 + 自我学习 | ✓ | ✓ | ✗ |

---

## 9-11. 服务层（人脸/位置/QR）

- InsightFace buffalo_l: SCRFD-10GF 检测 + ResNet50 512维特征，ONNX GPU推理
- 坐标准换: WGS-84 ↔ GCJ-02，Haversine三坐标系自适应取最小值
- QR码: UUID token + qrcode生成PNG，5分钟有效期，一次性标记

详见 V1.0 文档。

---

## 12. 签到任务（Session）

V3.0 核心新增模块。

### 任务字段

| 字段 | 示例 | 说明 |
|------|------|------|
| 签到点 | 实验室 | 从已配置签到点中选择 |
| 开始/结束日期 | 2026-06-16 ~ 06-20 | 任务有效日期范围 |
| 每日开始/结束时间 | 08:00 ~ 20:00 | 每天允许签到的时间窗口 |
| 重复规则 | 周一至周五 / 每周六 | 周期模式 |
| 目标学生 | 张三,李四,王五 | 空 = 所有人 |

### 典型场景

- **单次实验课**: 日期 06-16 ~ 06-16, 时间 14:00-16:00
- **每周例会**: 重复 每周六, 时间 08:00-20:00
- **持续课程**: 日期 06-16 ~ 06-20, 周一至周五, 选择15名学生

### 管理界面

双栏布局：左侧创建表单（签到点/日期/时间/人员勾选网格/发布按钮），右侧进行中任务列表（每项含状态badge、详情、结束按钮）。

---

## 13. 视频批量签到

上传视频 → 0.5s帧采样 → 跨帧去重(cos 0.45) → 1:N人脸匹配 → 批量创建CheckIn记录。通过 `asyncio.to_thread()` 线程池执行。

---

## 14. 自动签退

FastAPI lifespan后台任务，每5分钟扫描超4小时的active签到并自动签退。

---

## 15. 前端页面

| 页面 | 用户 | 功能 |
|------|------|------|
| `login.html` | 所有 | 登录 + 人脸验证重置密码 |
| `index.html` | 学生 | GPS定位 + 人脸/姓名 → 签到/签退 |
| `admin.html` | admin/instructor | 仪表盘(含任务管理) / QR / 人员 / 签到点 / 记录 |
| `student.html` | 学生 | 任务列表 + 签到方式选择弹窗(扫码/拍照) |

---

## 16. 配置与部署

关键配置: `JWT_EXPIRE_MINUTES`=1440, `CHECKIN_RADIUS_METERS`=100, `QR_EXPIRE_MINUTES`=5, `AUTO_CHECKOUT_HOURS`=4, `FACE_SIMILARITY_THRESHOLD`=0.25, `PORT`=8080。

启动时自动建表 + 增量迁移 (checkin_sessions + 新增列)。种子数据: admin/admin123, gxf/123456, 默认实验室签到点。

---

## 17. 自我学习机制

移动平均融合: `blended = 0.85 * old + 0.15 * new`，L2归一化。触发时机: 签到成功时 + 管理员更正记录时。

---

## 18. 数据导出

openpyxl 双Sheet Excel报表 (汇总统计 + 明细记录)，支持日期/用户/状态筛选，带样式表头和交替行背景。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-06-14 | 初始版本: QR签到、人脸识别、GPS定位、视频批量 |
| V2.0 | 2026-06-15 | 管理员修正、导出Excel、忘记密码(人脸重置) |
| V3.0 | 2026-06-16 | 点名任务(Session)、时间段/周期控制、多任务并行、用户精准指定、签到方式选择弹窗、签到点删除、视频签到bug修复、UI全面重构 |

---

> 文档生成：2026-06-16 | 项目：`D:\Homework-of-face-detector`
