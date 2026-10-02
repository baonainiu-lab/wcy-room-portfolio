# 人物动画基准与身份锁定

本次实际动作图按 2dimg2motion 制作：每段 14 帧，四个关键姿态 02/05/08/11，八张由 image_gen 绘制的补间。00/13 使用同一透明基准，输出 GIF 与 RGBA 序列。没有骨骼建模或首页接入。

## 固定特征
- 原创成年卡通青年，修长体型、窄肩、浅肤色；浅金棕侧分发、前额卷翘发束、灰蓝眼、雀斑、轻微不对称笑容。
- 象牙白短夹克，墨蓝内搭与工装裤，橙色拉链/少量点缀，银色五金；同一肩带、胸前徽章、吊坠和腕表。
- 一头、两臂、两腿；脚位和镜头固定，允许颈、肩、肘、腕、表情及附着挂件做动作导致的小幅变化。
- 屏幕左侧手（人物右手）从底部持续托住同一蓝银色翻盖终端；屏幕橙蓝画面和橙色旋钮保持一致，不换手、不悬浮、不变尺寸。
- 屏幕右侧手（人物左手）为空闲活动手，带腕表；点触时从同一右侧肩连到食指，终端仍由左侧手承托。
- 皮包在屏幕左侧腰；细笔卡匣与机器人挂件在屏幕右侧腰；附着点不交换。
- 人物背部及被设备遮挡的掌心并不完全可见，不把推断细节当已确定模型结构。

## 坐标/道具记录
coordinateSpace: screen-space
activeLimb: screen-right arm
activeShoulder: screen-right shoulder
anchorLimb: screen-left arm
carriedProp: blue-silver terminal
propHand: screen-left hand
activeWeapon: none
detachedProp: none
passiveAccessory: robot charm, pouch, memory cartridges, strap, necklace, wristwatch

## 背景与处理
人物主要颜色为金棕、浅肤色、象牙白、墨蓝、橙、银，选择无冲突的 #FF00FF 品红去底。
image_gen 负责全部动作画面；本地工具只去底、整格拆分、共同比例规范、图集合成、GIF编码和验证，禁止脚本扭曲/切肢/合成姿态。
最终目录每动作仅含 keyframe-prompts.md、keyframe/、fullframe/、spritesheet.png、contact-sheet.png、preview.gif、manifest.json。临时生成原图与质检材料分别放 tmp/avatar-motion-v2 和 renders/avatar-motion-v2。

