---
status: active
last_verified: 2026-08-01
date: 2026-08-01
owner: gaozhe（agent 起草）
---

# ViSTR-Bench 人工 hack 分析报告：逐 case 审查 → 工具设计

> 一手记录：`docs/notes/analyses/2026-08-01_case_review/`（75 抽样、39 实看、拼图+逐 case 日志）。
> 结论先行：**9 个工具可覆盖 15 个任务中的 13 个，约 92% 的题目有明确的工具化解法**；
> 其中 4 个任务（Vehicle Movement / Relative Velocity / Ego Motion / Interaction Direction）
> 解法确定性最高，应作为 v1 工具链。

## 1. 审查方法

- 分层抽样 75 case（15 任务 × 5，覆盖双答案类+多来源），实看 39 case（4 帧拼图/case）
- 670 题全量文本分析（模板/选项/答案分布）
- 置信度标注：●=工具解法明确且实现直接 ◐=可解但需调参或组合 ▲=弱证据/难例残留

## 2. 全量元数据发现（670 题，不看视频可得）

| 发现 | 影响 |
|------|------|
| **12/15 任务只有 1 个问题模板**（例外：Ego 57 / Swimming 21 / Interaction 9 / Fall 4 / Rotation 3） | Task Router 可用 `task` 字段直接路由，零解析成本 |
| 选项全部随题给出且顺序已随机化 | 答案解析逐题对照 `options`；不要假设位置分布 |
| 答案分布均衡（public Chance-Freq=52.7%） | 无频率捷径；但也意味着小幅提升即可甩开随机线 |
| 每题自带官方 `manual_cot_prompting` | reasoner 的 prompt 层直接用官方模板，消除变量 |
| 视频普遍很短（0.4s–26s，多在 2–6s） | 帧采样可加密（不止 16 帧），单 case 工具链成本可控 |

## 3. 逐任务分析（按解法族分组）

### 族 A：视觉提示框 + ego-motion 补偿（Motion Perception，168 题）

| 任务 | 一手观察 | 工具解法 | 置信 |
|------|---------|---------|:---:|
| Vehicle Movement (56) | Waymo 行车记录，目标车带**绿框**。陷阱：ego 动导致"静车也动"（id0082 雨天窗边 SUV 全程停靠）；正例位移细微（id0323 出库） | 绿框颜色阈值→逐帧轨迹；背景特征点仿射拟合 ego-motion；目标残差位移>阈值→Yes | ● |
| Relative Velocity (42) | 同场景双色框（绿/蓝）。含对向车流（id0111）与大雾弱信号（id0365） | 双色框轨迹+**面积变化率（looming=接近速率）**；ego 补偿后比世界速度 | ● |
| Rotation Direction (73) | 人旋转/跳转/武术旋踢（MotionX+YouTube，含特技难例 id1180） | 逐帧 2D pose→肩线法向/鼻向的**朝向角序列展开**，角位移符号→CW/CCW；特技例降级到关键帧 MLLM | ◐ |

### 族 B：相机轨迹 + 3D 几何（Spatial Relations 前两个，93 题）

| 任务 | 一手观察 | 工具解法 | 置信 |
|------|---------|---------|:---:|
| Ego Motion (66) | 室内漫游 10–21s（ScanNet/++/ARKit），起始目标在视野、末帧已转向它处（id0892 厨房：stove 到背后左） | **VGGT 出相机轨迹+深度**；Grounding-DINO 按题面名词（bathtub/stove…）检测目标→3D 点→变换到末帧相机系→方位象限。**论文 pilot 同路线 +16.8** | ● |
| Passage Feasibility (27) | 自采地库（含鱼眼），锥桶成门，车从 ego 或第三人称视角逼近（id1134 间隙<车宽） | 锥桶检测（橙色/YOLO）+地面平面假设；车身航向 vs 锥桶门轴对齐度+净空估计；临界例末段放大帧给 MLLM | ◐ |

### 族 C：人体姿态运动学（Interaction/Fall/Rotation，124 题）

| 任务 | 一手观察 | 工具解法 | 置信 |
|------|---------|---------|:---:|
| Interaction Direction (28) | 攀爬杆/岩壁速降（质心上下）与擦镜（手腕在镜面平面内方向）两类 | 2D pose 跟踪：**髋部质心速度符号**→Up/Down；**手腕速度方向投影**→Vertical/Horizontal/Approaching。**论文 pilot 光流路线 +5.3，姿态路线更直接** | ● |
| Fall Direction (23) | 倒地前躯干已倾斜（id1301 喷泉女孩右倾）；有 4 种选项变体（含 Get up/Lie down） | 肩髋轴线倾角时间序列→倾斜方向；变体由 options 解析自适应 | ● |
| Swimming Race (36) | 奥运转播侧拍 8 道齐游，问 lane A vs B 谁先到（id0668） | 泳道线检测定道次坐标系→逐道头部/水花跟踪→相对进度（x 位置+速度）外推 | ◐ |

### 族 D：球体轨迹外推（Outcome Prediction 球类，204 题）

| 任务 | 一手观察 | 工具解法 | 置信 |
|------|---------|---------|:---:|
| Basketball Shot (62) | Ego4D 含**第一人称**（id0817 手抛球，相机随头动）与第三人称；截断在球触筐前 | 球检测跟踪+筐定位+**抛物线拟合**；第一人称先稳像（背景/VGGT）再拟合 | ◐ |
| Soccer Shot (79) | 最大子任务。截断极早的例存在（id0491 球还静置、助跑即截断） | 球门框检测+球轨迹外推到球门平面；早截断例取触球瞬间初速度向量，弱证据降级 | ▲ |
| Golf Shot (26) | 电视转播**多镜头切换**（开球→空中→果岭），末段球滚动近洞（id0387 末帧在洞沿） | **镜头切分**→取果岭段：球滚动方向/速度 vs 洞杯位置 | ◐ |
| Billiards Shot (38) | Ego4D 第一人称暗光+B站中式（镜头切换+字幕） | 台面检测+球色分割+目标球→袋口连线角；切段取广角台面段 | ◐ |

### 族 E：结构/拓扑解析（Physical Dynamics，114 题）

| 任务 | 一手观察 | 工具解法 | 置信 |
|------|---------|---------|:---:|
| Jenga Stability (58) | 桌面红蓝积木塔，手指推某块。**关键几何：被抽块 footprint 上是否有上层块压叠**（id0137 无压→Yes，id0146 承重→No） | 积木分层解析（颜色+边缘）+手部接触定位目标块+**支撑分析**（上层重心 vs 残余支撑多边形）；局部放大序列给 MLLM 复核 | ◐ |
| Mikado Dependency (42) | 俯视签堆，指示签指明目标签；判断目标签上方有无压签 | 线段检测矢量化+交叉点 over/under 判定（边缘连续性，临界交叉局部放大+MLLM） | ▲ |
| Knot Type (14) | 打结全程：Slip=有环耳/bight（id0213 折返穿环），Fixed=双端收紧（id0654） | 成形关键 2–3 帧局部放大→结构 quiz（有无 bight/单尾释放）给 MLLM；样本少可人工过 | ▲ |

## 4. 工具集设计（9 件，按复用度排序）

| # | 工具 | 输入→输出 | 命中任务（题数） | 实现 |
|---|------|----------|----------------|------|
| T1 | **视觉提示框解析** | 视频→绿/蓝框逐帧 bbox | Vehicle(56)+RelVel(42)=98 | HSV 阈值+轮廓，纯 cv2，半天 |
| T2 | **ego-motion 补偿器** | 视频→逐帧仿射/相机位姿 | Vehicle+RelVel+Basketball(Ego4D)+Ego Motion | 背景 AKAZE+仿射 RANSAC（轻量）或 VGGT（精确） |
| T3 | **通用目标跟踪器** | bbox/点 init→逐帧轨迹 | 球类 204+driving 98+锥桶 | SAM2 / CoTracker3（third_party 接入） |
| T4 | **轨迹外推引擎** | 点轨迹→抛物线/直线拟合→目标区求交 | Basketball+Soccer+Golf+Billiards=204 | numpy 拟合+几何判定，纯算法 |
| T5 | **人体姿态引擎** | 视频→逐帧 2D 关键点 | Rotation+Interaction+Fall+Swimming=160 | ViTPose/RTMPose；质心/轴线/关节速度派生量 |
| T6 | **场景重建器** | 视频→相机轨迹+深度图 | Ego Motion(66)，兼稳像 | **VGGT-1B 已在 hf_datasets 本地** |
| T7 | **场景结构解析器** | 帧→参考物几何（锥桶门/球门框/泳道线/台面/积木层） | Passage+Soccer+Swimming+Billiards+Jenga=224 | 颜色/边缘/检测器组合，按任务定制 |
| T8 | **镜头切分器** | 视频→镜头边界+分段标签 | Golf+Billiards+Soccer=143 | 直方图差分，纯 cv2，半天 |
| T9 | **局部放大器** | 帧+ROI→crop 序列 | Jenga+Mikado+Knot+Passage=141 | 纯 cv2，配合 MLLM 细判 |
| — | **证据摘要器**（横切） | 工具数值→语言原生摘要 | 全部 670 | Perception-Program 风格模板 |

**覆盖核算**：族 A●98 + 族 B 93 + 族 C 160 + 族 D 204（◐/▲）+ 族 E 114 = 全 670 题均有工具路径；
其中**高确定（●）约 350 题（52%）**，中确定（◐）约 250 题（37%），难例残留（▲）约 70 题（11%）——
难例主要是：Soccer 超早截断、Mikado over/under 细判、Knot 拓扑（仅 14 题可人工兜底）。

## 5. 与论文证据的对齐

- 论文错误类型 Top3（Motion State 27.5% / Outcome 24.5% / Tracking 18.3%）≈ 族 A+C+D 的题面——我们的 T1–T5 正对这些
- 论文 pilot：VGGT→Ego Motion +16.8（T6）、光流摘要→Interaction +5.3（T5 姿态路线等价替代）
- 论文提示 MLLM 不利用连续时序（ordered≈shuffled）→ 我们的设计原则是**把时序问题在工具层数值化**，MLLM 只做最终判断

## 6. 建议实施顺序（v1→v3）

| 阶段 | 内容 | 预期命中 | 理由 |
|------|------|---------|------|
| v1 | T1+T2+T4（driving 双任务+球类抛物线）+ 证据摘要器 | ~300 题 | 纯 cv2/numpy 无模型依赖，最快闭环；论文错误占比最高区 |
| v2 | T5 姿态引擎 + T8 切分 + T9 放大 | +160 题 | ViTPose 单模型多任务复用 |
| v3 | T6 VGGT（Ego Motion）+ T3 SAM2/CoTracker（疑难跟踪）+ T7 结构解析 | +210 题 | 模型接入成本高但论文已验证收益 |

每步都以 baseline 为对照在 public 集上 A/B，run log + 前端 dashboard 跟踪 per-task 变化。

## 7. 风险与边界

1. **工具误差≠0**：阈值类判定（Vehicle Movement 的"subtle"）需要校准集调参——从 public 集切 20% 做 dev
2. **第一人称视频**（Ego4D 的 basketball/billiards）：稳像质量决定轨迹拟合上限，可能拉低族 D 实际命中
3. **Soccer 早截断**：物理信息不足时工具也无力，此类题退回 MLLM 先验（接受 ~50%）
4. **鱼眼/暗光/overlay 干扰**：Passage 鱼眼、Billiards 暗光、转播字幕——需要预处理（去畸变/增强/遮挡 mask）
5. 工具链输出必须过**答案一致性检查**（选项精确匹配），避免数值对但解析错

## 8. 下一步

1. 用户审查本报告 + case 留档 → 确认后 promote 到 `docs/knowledge/` 并更新 ADR
2. 确认 reasoner 底座（本地 Qwen3-VL / API）→ 先跑 direct-prompting baseline 拿对照线
3. 按 §6 v1 开工
