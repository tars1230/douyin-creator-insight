# Creator Insight v1.2.2 发布计划

1. [完成] 补首次安装配置：`scripts/setup.py` 明确选择 `cloud` / `local` / `index`，只保存非敏感偏好。
2. [完成] 补两类用户路径：纯首次用户安全引导申请 `DASHSCOPE_API_KEY`；已安装收藏 skill 的用户复用登录 profile/ASR 偏好但隔离状态、输出与定时任务。
3. [完成] 缺云端 Key 时真实运行安全停止：不下载视频，不静默切本地 Whisper。
4. [进行中] 运行单元测试、发布预检、首次配置 smoke、缺 Key 阻断 smoke 和 Claude Review Gate。
5. [待做] 发布 `v1.2.2`：GitHub → Gitee 镜像 → ClawHub，并做全新安装与哈希验收。
6. [待做] 更新共享记录与 session trace。
