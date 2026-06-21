# 实验室人脸签到系统 — PPT 大纲（25页）

> 演讲时长：约 25-30 分钟 | 项目：Homework-of-face-detector  
> 技术栈：Python FastAPI + InsightFace + SQLite + HTML/CSS/JS

---

## 第1页 — 封面
- **标题**: 实验室人脸签到系统 — 设计与实现
- 副标题: 基于 InsightFace 的精准定位 + 人脸识别签到方案
- 作者 / 日期 / 学校/单位 Logo

---

## 第2页 — 目录
1. 项目背景与意义
2. 可行性研究
3. 需求分析
4. 系统架构设计
5. 核心模块实现
6. 测试与验证
7. 部署运维
8. 总结与展望

---

## 第3页 — 背景：实验室考勤的痛点
- 传统纸质签到：代签、补签无法杜绝
- 刷卡/指纹：设备成本高，需专用硬件
- 现有App：操作繁琐，学生抵触
- **核心矛盾**: 教师需要准确考勤 vs 学生追求便捷体验

---

## 第4页 — 项目目标
- 人脸识别防代签，确保本人到场
- GPS 围栏验证，确保人在实验室
- 扫码即签，3秒完成（无需安装App）
- 管理后台一键导出 Excel 考勤报表
- 支持视频批量签到，适配大课场景
- **一句话**: 安全、便捷、低成本的实验室考勤方案

---

## 第5页 — 可行性研究：技术可行性
| 维度 | 分析 |
|------|------|
| 人脸识别 | InsightFace (buffalo_l) 开源模型，识别准确率 >99% |
| GPS 定位 | 浏览器 Geolocation API + 高德地图 SDK |
| 后端框架 | FastAPI 异步高性能，100并发下 956 QPS |
| 前端 | 纯 HTML/CSS/JS，零依赖框架，移动端适配 |
| 数据库 | SQLite，零配置，单文件部署 |
| **结论** | 技术栈成熟稳定，无技术障碍 |

---

## 第6页 — 可行性研究：经济可行性
- **硬件成本**: 0元（利用学生手机 + 现有服务器）
- **软件成本**: 0元（全部开源技术栈）
- **运维成本**: 1台 8C16G 服务器（约200-400元/月）即可支撑 500+ 并发
- vs 指纹打卡机 2000-5000元/台 + 维护
- vs 商业 SaaS 考勤系统 5000-20000元/年
- **结论**: 成本极低，适合高校实验室推广

---

## 第7页 — 可行性研究：操作可行性
- 学生端：浏览器扫码 -> 输入姓名 -> 确认签到（3步，30秒）
- 教师端：登录后台 -> 创建任务 -> 查看统计 -> 导出Excel
- 移动端完全适配，无需安装任何 App
- 自动签退 + 视频批量签到，大幅降低人工成本
- **结论**: 操作流程自然，学习成本为零

---

## 第8页 — 需求分析：功能模块总览
```
                ┌──────────────────────┐
                │   实验室人脸签到系统    │
                └──────────┬───────────┘
          ┌────────┬───────┼───────┬────────┐
    用户管理   签到任务   二维码   签到记录   数据导出
    .CRUD     .创建     .生成    .查询     .Excel
    .人脸注册  .时间窗口  .验证    .修正     .已签到Sheet
    .角色权限  .重复规则  .签到/退 .统计     .未签到Sheet
              .目标人员           .按天分析
```
- 三级角色：管理员 / 教师 / 学生
- 多签到任务并行，支持不同课程独立管理

---

## 第9页 — 需求分析：核心业务流程
```
教师创建签到任务 -> 设置时间/地点/人员 -> 生成二维码
    ↓
学生扫码 -> 浏览器获取GPS -> 验证位置范围
    ↓
输入姓名 -> 人脸识别验证 -> 签到成功
    ↓
教师后台 -> 实时统计 -> 导出Excel报表
    ↓
到时自动签退 / 学生手动签退
```

---

## 第10页 — 系统架构：总体设计
```
┌──────────────────────────────────────────────┐
│                    前端层                     │
│  login.html  admin.html  student.html        │
│  index.html (扫码页)                          │
│  纯 HTML5 + CSS3 + Vanilla JS                │
└──────────────────┬───────────────────────────┘
                   │ HTTP/HTTPS
┌──────────────────▼───────────────────────────┐
│                FastAPI 后端层                   │
│  ┌─────────┬──────────┬────────┬──────────┐ │
│  │ auth    │ admin    │ check  │ qrcode   │ │
│  │ 认证模块 │ 管理模块  │ 签到模块│ 二维码模块│ │
│  └─────────┴──────────┴────────┴──────────┘ │
│  ┌──────────────────────────────────────┐   │
│  │      Services 服务层                   │   │
│  │  face_service / qr_service /          │   │
│  │  location_service / video_service     │   │
│  └──────────────────────────────────────┘   │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              数据层                           │
│  SQLite (aiosqlite) + InsightFace ONNX       │
│  高德地图 API (定位/逆地理编码)                 │
└──────────────────────────────────────────────┘
```

---

## 第11页 — 数据库设计
```
┌──────────────┐    ┌──────────────┐
│    users     │    │  locations   │
├──────────────┤    ├──────────────┤
│ id (PK)      │    │ id (PK)      │
│ username     │    │ name         │
│ password_hash│    │ latitude     │
│ name         │    │ longitude    │
│ role         │    │ radius_meters│
│ face_embedding (BLOB) │           │
│ is_active    │    └──────┬───────┘
└──────┬───────┘           │
       │           ┌───────▼──────────┐
       │           │  checkin_sessions │
       │           ├──────────────────┤
       │           │ id (PK)          │
       │           │ name             │
       │           │ start_date/end   │
       │           │ recurring_days   │
       │           │ target_user_ids  │
       │           └──────┬───────────┘
       │                  │
┌──────▼──────────────────▼──────┐
│           checkins              │
├────────────────────────────────┤
│ id (PK) / user_id (FK)         │
│ check_in_time / check_out_time │
│ location_id / lat / lng        │
│ status (active/completed)      │
│ check_in_photo / check_out_photo│
└────────────────────────────────┘
```
- 人脸特征向量 512维 float32 -> BLOB 存储
- 签到任务支持日期范围 + 每日时间段 + 每周重复天
- 目标人员支持 null=所有人 / 逗号分隔ID

---

## 第12页 — 编码过程：人脸识别模块
**技术选型**: InsightFace (buffalo_l) + ONNX Runtime
- 人脸检测: `det_10g.onnx` (SCRFD)
- 人脸识别: `w600k_r50.onnx` (ArcFace, 512维特征)
- 活体检测: `2d106det.onnx` (106点关键点)

**核心代码**:
```python
def _ensure_app():
    app = FaceAnalysis(name="buffalo_l",
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app

def match_face(embedding, candidates):
    # 余弦相似度匹配，阈值 0.25
    best_sim = max(np.dot(embedding, stored_emb)
                   for stored_emb in candidates)
    return best_id if best_sim >= 0.25 else None
```

**自学习机制**: 每次成功签到，新特征与存储特征做移动平均融合(alpha=0.15)，模型随使用越来越准

---

## 第13页 — 编码过程：GPS 围栏验证
- 前端: 高德 JS SDK (GCJ-02) + 浏览器 Geolocation API (WGS-84)
- 后端: Haversine 公式计算球面距离

```python
def is_within_range(lat1, lng1, lat2, lng2, max_m, source):
    if source == "amap":  # GCJ-02 坐标系
        d = haversine_gcj02(lat1, lng1, lat2, lng2)
    else:  # WGS-84 坐标系
        d = haversine_wgs84(lat1, lng1, lat2, lng2)
    return d <= max_m, d
```

- 双坐标系支持：高德 GCJ-02 / GPS WGS-84
- 签到点可配置半径范围 (默认100m)
- 定位失败引导用户开启高精度模式

---

## 第14页 — 编码过程：二维码生成与验证
- 生成: `qrcode` 库 -> PNG 图片，5分钟有效期
- 验证: 数据库 token 校验 + 过期检查
- 签到/签退双类型，同一页面根据 `type` 参数切换

```python
# QR URL 结构
https://域名/checkin.html?
  token=uuid          # 一次性令牌
  &type=checkout       # checkin/checkout
  &location_id=1       # 签到点
  &session_id=8        # 签到任务
  &session_name=周一实验室签到  # 任务名（前端显示）
```

- Student 页面扫码签到用 `api/qr/self` 获取个人专属码
- 视频批量签到复用同一 QR token 机制

---

## 第15页 — 编码过程：签到任务调度
**多任务并行模型**:
```
任务A: 周一-周五 08:00-12:00  目标: [张三,李四]
任务B: 周六     14:00-18:00  目标: [所有人]
任务C: 周一-周日 19:00-22:00  目标: [王五,赵六]
```

**时间有效性判断**:
1. 当前日期在 start_date ~ end_date 范围内
2. 今天是 recurring_days 中指定的星期几
3. 当前时间在 checkin_start_time ~ checkin_end_time 范围内
4. 学生在 target_user_ids 列表中 (或 null=全体)

**防冲突**: 同名学生不可同时有多个进行中的签到

---

## 第16页 — 编码过程：Excel 导出引擎
- 使用 `openpyxl` 生成原生 .xlsx 文件
- **双 Sheet 结构**:
  - Sheet 1 "已签到": 序号/姓名/签到时间/签退时间/地点/时长/状态
  - Sheet 2 "未签到": 按日期分组，每日列出缺勤人员

**关键优化**:
- 每人独立颜色标记，便于区分
- 未签到日期范围截止到今天 (不含未来日期)
- 支持任务级导出 (按 session_id) 和全局导出 (按日期范围)
- 文件名含任务名+日期范围，一目了然

---

## 第17页 — 编码过程：视频批量签到
```
上传视频 -> 逐帧人脸检测 -> 去重追踪 -> 批量匹配 -> 批量签到
```
```python
def process_video(video_path, user_embeddings, ...):
    cap = cv2.VideoCapture(video_path)
    while cap.read():
        faces = app.get(frame)
        for face in faces:
            track_id = tracker.track(face)  # 去重
            matched_user = match_face(face.embedding, candidates)
    return {"frames_processed": 1500, "unique_faces_found": 23, ...}
```
- 逐帧检测 + DeepSORT 追踪去重，避免同一人多次签到
- 仅在 session 目标用户范围内匹配
- 已签到用户自动跳过

---

## 第18页 — 编码过程：前后端分离与权限控制
**三级权限模型**:
```
未登录 -> 401 (仅可访问 /login.html, /checkin.html)
  |
学生    -> 可查看自己签到状态 + 签到/签退
  |
教师/管理员 -> 全部管理功能 (用户/地点/任务/记录/导出)
```

**JWT 认证流程**:
1. 前端登录 -> POST /api/auth/login -> 返回 JWT Token
2. 后续请求携带 `Authorization: Bearer <token>`
3. 后端 decode -> 校验过期 + 提取 sub(用户ID) + role(角色)
4. 管理接口额外检查 role 属于 {admin, instructor}

---

## 第19页 — 测试内容：接口测试
- **测试工具**: Python requests + 自定义断言框架
- **用例数**: 29 条
- **覆盖率**: 12 个模块 (auth/admin/check/qrcode/...)
- **通过率**: 100% (29/29)

| 模块 | 用例数 | 通过 |
|------|--------|------|
| 健康检查 | 1 | 1 |
| 认证模块 | 4 | 4 |
| 用户管理 | 2 | 2 |
| 签到点 | 1 | 1 |
| 统计看板 | 1 | 1 |
| 二维码 | 3 | 3 |
| 签到任务 | 7 | 7 |
| 签到流程 | 2 | 2 |
| 签到记录 | 2 | 2 |
| Excel导出 | 3 | 3 |
| 位置验证 | 1 | 1 |
| 权限控制 | 2 | 2 |

---

## 第20页 — 测试内容：并发性能测试
- **测试工具**: Python ThreadPoolExecutor (10/50/100 并发)
- **场景**: Health、Statistics、QR生成、Check Status 等

| 场景 | 并发 | QPS | P95延迟 | 错误 |
|------|------|-----|---------|------|
| Health Check | 100 | **956** | 115ms | 0 |
| Check Status | 100 | **849** | 138ms | 0 |
| Statistics | 50 | 319 | 263ms | 0 |
| QR Generate | 10 | 35 | 591ms | 0 |

**结论**: 8C16G 服务器可支撑 **500+ 并发用户**，远超预期

---

## 第21页 — 测试内容：安全测试
- **测试工具**: Python requests (40项攻击载荷)
- **通过率**: 100% (40/40)

| 类别 | 测试项 | 结果 |
|------|--------|------|
| SQL注入 | 5种载荷 x 3接口 | 全部拦截 |
| XSS攻击 | 5种载荷 x 2接口 | 全部拦截 |
| 认证绕过 | 5种手法 (空Token/伪造/篡改JWT) | 全部拦截 |
| 路径遍历 | 3种载荷 x 2路径 | 全部404 |
| 敏感信息泄露 | 堆栈跟踪/密钥/密码哈希 | 无泄露 |
| 输入边界 | 超长输入/负数/特殊字符 | 无崩溃 |

**防护机制**: SQLAlchemy参数化查询 + FastAPI自动JSON转义 + JWT签名校验 + StaticFiles沙箱

---

## 第22页 — 部署架构
```
用户浏览器 (HTTPS)
    |
    v
nginx (443端口, Let's Encrypt SSL)
    |
    +-- /frontend/*   -> 静态文件
    +-- /static/*     -> 照片/QR图片
    +-- /api/*        -> 反向代理 uvicorn (127.0.0.1:8080)
                            |
                    FastAPI (4 workers)
                            |
                    SQLite + InsightFace ONNX
```
**一键启动**: `systemctl start face-detector`  
**公网访问**: https://face.twosmallcats.asia/

---

## 第23页 — 项目总结：成果
| 指标 | 数据 |
|------|------|
| 代码规模 | ~2000行 Python + ~2000行 HTML/JS |
| API 端点 | 29 个 |
| 接口测试通过率 | 100% |
| 安全测试通过率 | 100% |
| 并发性能 | 956 QPS @ 100并发 |
| 部署成本 | 1台云服务器 + 免费SSL |
| 用户学习成本 | 零（浏览器扫码即用） |

- 人脸识别防代签
- GPS 围栏防远程签到
- 3秒完成签到，无需安装App
- Excel 一键导出考勤报表
- 完整的安全防护体系

---

## 第24页 — 项目总结：创新点
1. **自学习人脸模型**: 每次签到融合特征，越用越准
2. **双坐标系 GPS 校准**: 同时支持 GCJ-02 和 WGS-84
3. **多任务并行调度**: 支持不同课程独立签到窗口
4. **视频批量签到**: 大课场景一次处理全班
5. **零前端框架**: 纯 HTML/JS，极致轻量
6. **任务级 Excel 导出**: 双Sheet（已签到+未签到），按天分析

---

## 第25页 — 展望与致谢
**后续改进方向**:
- 微信小程序端，提升体验
- PostgreSQL 替代 SQLite，支持更大规模
- Docker 容器化部署，一键拉起
- 活体检测加强 (IR+RGB 双目)
- 数据看板可视化 (图表仪表盘)

**致谢**:
- InsightFace 开源人脸识别模型
- FastAPI 高性能 Python Web 框架
- 所有开源社区贡献者

**Q&A**: 欢迎提问

---

*大纲生成时间: 2026-06-20 | 项目地址: github.com/2024zht/Homework-of-face-detector*
