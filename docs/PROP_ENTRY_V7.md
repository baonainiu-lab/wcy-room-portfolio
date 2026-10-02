# 房间小资产入场 V7

2026-09-25：按用户“每个小资产都要有不同入场动效，参考原开源网站”的要求更新。仅动画现有 Blender 对象，未新增/替换几何、贴图或材质。

## 参考与改编

参考本地保存的 `assets/references/abigail-bloom/Preloader.js` 中 `secondIntro`：采用顺次重叠、弹性展开、椅子旋转收尾的编排原则。未套用原模型的坐标/比例，也未照搬其超过最终尺寸的 back.out；当前项目的每个变换基于本模型原始 TRS 与实际顶点包围计算。原许可及来源记录保留。

## 每个资产的动作

36 个独立 root 每个都有单独的中文动作名、三轴生长曲线、旋转轴及时间窗口、空间路径、二次俯仰/侧摆和受限回弹。回弹仅在原始尺寸之内收缩回稳，旋转全程继续经过现有包围约束。支持桌面物件仍在承托桌面到位后进入；同组动作错峰交叠，较大的家具保持更慢的展开节奏。

| 组 | 独立资产 | 动作 |
| --- | --- | --- |
| wall | `c_archive_dock` | 档案匣侧抽・转正扣合 |
| wall | `kinetic_three_petal_flower` | 三瓣花旋开・花茎回弹 |
| wall | `glass_bonsai_terrarium` | 玻璃盆景弧降・微摆停驻 |
| wall | `trailing_wall_plant` | 垂叶纵展・枝叶轻摇 |
| wall | `v5_orbital_clock` | 轨道钟拨转・刻度归零 |
| wall | `v5_mechanical_data_panel` | 机械面板掀起・下沿锁定 |
| wall | `v8_window_light_bar` | 窗灯单向延展・端点轻收 |
| furniture | `furniture.desk` | 工作台横展・桌腿稳落 |
| furniture | `furniture.lounge` | 休闲椅弧落・坐垫缓回 |
| furniture | `furniture.coffee_table` | 茶几托升・台面归平 |
| furniture | `furniture.rug` | 地毯前后铺展・织边舒平 |
| furniture | `black_ceramic_floor_planter` | 落地花盆抽长・叶冠回摆 |
| furniture | `v5_geometric_floor_lamp` | 几何落地灯立起・灯头轻摆 |
| desktop | `thermal_cup` | 杯子轻跳・杯底缓弹 |
| desktop | `table_notebook_group` | 手帐斜掀・书页铺平 |
| desktop | `studio_reference_books` | 参考书错步滑入・书脊归齐 |
| desktop | `geometric_specimen_cloche` | 标本罩螺旋浮降・底座吸合 |
| desktop | `ceramic_mobius_study` | 莫比乌斯旋生・弧面定格 |
| desktop | `glass_cutting_planter` | 水培瓶反旋・植株舒展 |
| desktop | `v5_magnetic_pen_dock` | 磁吸笔座弹起・笔尖轻点 |
| desktop | `v5_energy_capsule_rack` | 能源架后滑・胶囊列队 |
| desktop | `v8_reading_puck` | 阅读灯反转・磁盘贴合 |
| equipment | `main_display` | 主屏竖展・仰角归位 |
| equipment | `compute_core` | 主机托升・机身回正 |
| equipment | `robot_companion` | 机器人跃出・侧身招呼 |
| equipment | `folding_drawing_terminal` | 绘图终端翻启・铰链缓停 |
| equipment | `headphones_on_stand` | 耳机架伸展・耳罩侧摆 |
| equipment | `ceramic_ring_speaker` | 环形音箱旋起・环面轻倾 |
| equipment | `split_keyboard` | 分体键盘横铺・边角归齐 |
| equipment | `compact_camera` | 相机斜翻・镜头抬正 |
| equipment | `portable_fold_communicator` | 通讯器反掀・立边轻弹 |
| equipment | `v5_portable_projector` | 投影仪弯道滑入・镜头校准 |
| equipment | `v5_modular_equipment_cases` | 设备箱纵叠・锁扣缓合 |
| equipment | `v5_scout_drone_display` | 探测艇掠弧・机翼回平 |
| equipment | `v8_desk_glow_lamp` | 桌灯抽升・灯帽点头 |
| chair | `furniture.work_chair` | 工作椅旋落・椅背轻摆 |

## 控制器衔接接口

- `createRoomEntry({ externalIds })`：事先声明由场景控制器独立控制的 root，不进行初始隐藏、入场 tween 或每帧 apply，仍保存原始变换。
- `setExternalControl(id, enabled=true)`：允许在 prepared 阶段调整归属；开启时立即恢复原始 TRS 供主控制器开始连续运动。
- `setExternalProgress(id, value)`：只更新外控资产诊断进度，不与主控制器争夺变换。
- `restore()`：普通与外控 root 都精确恢复原始位置、旋转及比例；正常结束、跳过与减少动态效果共用此路径。
- `getState().assets[]` 保留原 gesture 标签，并新增 `motionName`、`motionProfile`（包括三阶段 beats）及 `externalControlled`。

绘图终端保留独立翻启档案作为非外控回退；最终欢迎终端落桌衔接由主控制器负责，可用 externalIds 排除此 root 的重复入场。

## 验证

- `scripts/check-prop-entry-profiles.mjs`：5/5 通过。对真实 GLB root、原有贴图关联附件和生产 GSAP 时间线，在 6 个相同展开进度取样，排除尺寸、最终姿态和 delay 的影响后比较 630 对轨迹，36 个实际运动轨迹均不重复。最接近的一对归一化差值为 0.144（门槛 0.06）。实际顶点包围最大越界仅浮点误差 4.44e-16。
- 同一检查覆盖完成/中途恢复原始 TRS、外控终端零竞争变换、外控进度及准备阶段控制归属切换。报告 `docs/validation/prop-entry-profiles-v7.json`。
- 既有六类动效强度检查 9/9、贴图附件完整性/防穿模检查 3/3 通过；整段控制器浏览器验收由本次主任务验证记录补充。
- 不新增 draw call，不增加动画帧内临时对象分配；本检查不代表 120 FPS 硬件实测或像素级观感验收。
