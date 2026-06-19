# Plan: 任务签到增强 — 任务选择、视频识别优化与会话详情弹窗

**Source**: 用户需求（对话模式）
**Complexity**: Large
**日期**: 2026-06-19

## Summary

对学生扫码签到、管理员视频识别、进行中任务管理三个核心流程进行增强：
1. 学生扫码签到时先选择签到任务，自动对应位置
2. 管理员视频识别时先选择任务，按任务目标人员匹配
3. 进行中任务点击弹出详情弹窗，支持编辑和按任务导出已签到/未签到 Excel

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `backend/routes/admin.py:814` | 路由函数使用 `snake_case`，端点路径 `/api/admin/sessions` |
| Errors | `backend/routes/admin.py:825` | `HTTPException(status_code=404, detail="...")` |
| Data access | `backend/routes/admin.py:856-858` | `selectinload` 预加载关系，`scalar_one_or_none()` 获取单条 |
| Excel export | `backend/routes/admin.py:463-752` | openpyxl Workbook，双 Sheet（已签到/未签到），StreamingResponse |
| Frontend modals | `frontend/admin.html:245-259` | `modal-overlay hidden` + `modal` 容器，`classList.remove('hidden')` 打开 |
| Frontend API calls | `frontend/admin.html:346-352` | `api()` 辅助函数注入 Bearer token，处理 401 |
| Session response | `backend/routes/admin.py:793-811` | `_session_to_response()` 字典构建模式 |

## Files to Change

| File | Action | Why |
|---|---|---|
| `backend/schemas.py` | UPDATE | 新增 `SessionUpdate` 请求体、扩展 `QRGenerateRequest` 加 `session_id` |
| `backend/routes/qrcode.py` | UPDATE | QR 生成支持 `session_id`，URL 中包含任务信息 |
| `backend/routes/checkin.py` | UPDATE | 签到/视频批量签到支持 `session_id`，按任务目标用户过滤 |
| `backend/routes/admin.py` | UPDATE | 新增 PUT 更新会话端点，新增按会话导出端点 |
| `frontend/admin.html` | UPDATE | QR 生成卡片加任务选择器，视频卡片加任务选择器，会话列表点击弹窗（详情+编辑+导出） |
| `frontend/index.html` | UPDATE | 扫码签到页面解析并显示任务信息，选择任务流程 |

## Tasks

### Task 1: 环境配置确认
- **Action**: 检查 Python 依赖是否安装完整，数据库迁移是否正常，前端静态文件服务配置
- **Mirror**: 使用 `run.py` 或 `start.bat` 启动方式
- **Validate**: `python run.py` 成功启动，访问 `http://localhost:8000` 正常

### Task 2: 后端 Schema 扩展
- **Action**: 在 `schemas.py` 中新增 `SessionUpdate`（可更新字段均为可选），在 `QRGenerateRequest` 中新增可选 `session_id` 字段
- **Mirror**: `SessionCreate` 的模式风格（`schemas.py:149-157`）
- **Validate**: 导入无错误

### Task 3: 后端会话更新 API
- **Action**: 在 `admin.py` 新增 `PUT /api/admin/sessions/{id}` 端点，支持修改名称、时间窗口、日期范围、重复规则、目标用户
- **Mirror**: `create_session` 的验证逻辑（`admin.py:814-845`）
- **Validate**: Swagger UI 可测试 PUT 端点

### Task 4: 后端按会话导出 API
- **Action**: 在 `admin.py` 新增 `GET /api/admin/sessions/{id}/export` 端点，复用现有 Excel 导出逻辑，按 `session_id` 过滤签到记录和缺勤计算
- **Mirror**: `export_checkins` 的双 Sheet 格式（`admin.py:463-752`）
- **Validate**: 导出文件包含正确格式的已签到/未签到 Sheet

### Task 5: 后端 QR 生成关联任务
- **Action**: 修改 `POST /api/qr/generate`，接受 `session_id` 参数，QR URL 包含 `session_id`；修改 `GET /api/qr/validate/{token}` 返回关联的会话信息
- **Mirror**: 现有 QR 生成逻辑（`qrcode.py:30-62`）
- **Validate**: 生成的 QR URL 包含 `session_id` 参数，验证接口返回会话名称

### Task 6: 后端签到/视频批量签到关联任务
- **Action**: 修改 `POST /api/check/in` 和 `POST /api/check/batch-video`，支持接收 `session_id`，按任务目标用户过滤匹配候选人
- **Mirror**: 现有 `_get_best_session` 和 `_get_active_sessions` 过滤逻辑（`checkin.py:40-71`）
- **Validate**: 签到记录关联正确的任务

### Task 7: 前端 QR 生成卡片 — 加任务选择器
- **Action**: 在 `admin.html` QR 生成卡片中增加任务（CheckInSession）下拉选择器；选择任务后自动填入对应的签到点；生成 QR 时传递 `session_id`
- **Mirror**: 现有 `loadVideoLocationSelect()` 的下拉填充模式（`admin.html:645-649`）
- **Validate**: UI 正确显示任务列表，选择任务后签到点自动联动

### Task 8: 前端视频批量签到卡片 — 加任务选择器
- **Action**: 在 `admin.html` 视频卡片中增加任务选择器，替代独立的签到点选择器（签到点从任务自动获取）；上传时传递 `session_id`
- **Mirror**: 现有 `uploadVideo()` 的逻辑（`admin.html:652-711`）
- **Validate**: 视频签到按任务目标用户匹配

### Task 9: 前端会话列表 — 点击弹窗（详情+编辑+导出）
- **Action**: 新增会话详情模态框，包含：
  - 任务详细信息展示（名称、签到点、时间窗口、日期、重复规则、目标人数、状态）
  - 编辑按钮切换为编辑模式（可修改名称、时间、日期、重复规则、目标用户）
  - 导出按钮：导出已签到 Excel + 导出未签到 Excel（调用按会话导出 API）
  - 会话列表项绑定 `onclick` 打开弹窗
- **Mirror**: 现有模态框样式（`admin.html:245-283`），导出下载逻辑（`admin.html:518-561`）
- **Validate**: 弹窗正确展示，编辑保存生效，导出文件正确

### Task 10: 前端扫码签到页 — 任务选择与显示
- **Action**: 在 `index.html` 扫码签到流程中解析 `session_id` URL 参数，显示当前任务名称，验证 QR 时显示关联任务；若无 `session_id` 但有多个活跃任务，让用户先选择
- **Mirror**: 现有 token 解析模式（`index.html:69-84`），学生端会话显示（`student.html:137-163`）
- **Validate**: 扫码后显示正确任务名，签到关联正确任务

## Validation

```bash
# 启动后端验证无错误
cd backend && python -c "from main import app; print('OK')"

# 验证 Excel 导出
curl -H "Authorization: Bearer <token>" "http://localhost:8000/api/admin/sessions/1/export" -o test.xlsx

# 验证前端页面加载
# 浏览器访问 http://localhost:8000/admin.html
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| QR URL 过长（加了 session_id） | Low | session_id 为整数，URL 长度增加有限 |
| 视频签到按任务过滤后匹配人数过少 | Low | 无目标用户限制时回退到全部活跃用户 |
| 会话编辑可能破坏进行中数据一致性 | Medium | 只允许编辑元数据字段，不允许修改 location_id |
| 前端 JS 代码量增大（admin.html 已 ~580 行） | Medium | 提取公共逻辑为辅助函数，保持可维护性 |
| 旧 QR 码（无 session_id）兼容性 | Low | 签到接口 `session_id` 保持可选，无值时回退到现有自动匹配逻辑 |

## Acceptance

- [ ] 环境正常启动，所有页面可访问
- [ ] 管理员生成 QR 时可选择任务，学生扫码后显示任务名
- [ ] 管理员视频识别时可选择任务，按任务目标用户匹配
- [ ] 进行中任务点击弹出详情弹窗，支持编辑和导出已签到/未签到 Excel
- [ ] 导出的 Excel 格式与现有导出功能一致（双 Sheet 结构）
- [ ] 旧流程（无任务选择的 QR/视频签到）仍然兼容
