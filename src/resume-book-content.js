// Expanded from the two final résumé DOCX files, not inferred proficiency scores.
// Fact mapping: docs/RESUME_BOOK_EXPANDED_COPY_SOURCES.md.
export const resumePages = [
  {
    id: 'overview', title: '个人与学习', label: 'PROFILE / 01',
    content: `<div class="resume-page__name"><span>王丞业</span><small>游戏策划 / AI 游戏运营 · 内容方向</small></div>
      <p class="resume-page__intro">数字媒体艺术本科在读，结合玩法设计、三维美术与 AI 辅助开发实践，把规则、资产和交互整合成可玩版本，也将概念整理为完整视觉内容。</p>
      <section class="resume-page__section"><h4>教育背景</h4><p>浙江广厦建设职业技术大学<br>数字媒体艺术 · 本科 · 2023—2027</p></section>
      <section class="resume-page__section"><h4>学习与实践</h4><p>主修用户体验设计、人工智能、数字图像处理、影视制作与合成。参与学院数字媒体工作室，承担三维资源制作、场景与镜头整理、后期剪辑及团队协作。</p></section>
      <section class="resume-page__section"><h4>关注方向</h4><p>游戏策划侧重玩法与系统；游戏运营侧重内容表达、视觉素材制作与 AI 工作流应用。</p></section>`,
  },
  {
    id: 'game-design', title: '玩法与系统设计', label: 'GAME DESIGN / 02',
    content: `<p class="resume-page__intro">从玩家要做什么、如何作出选择，到反馈怎样影响下一步，围绕清晰的规则、引导与成长循环展开设计。</p>
      <section class="resume-page__section"><h4>规则与内容组织</h4><p>将收银、观察取证、身份判断和延迟后果串成经营循环；用有限检查次数约束信息获取，通过异常线索、任务推进与分支结局组织递进体验。</p></section>
      <section class="resume-page__section"><h4>成长与数值选择</h4><p>组织战斗吸收、随机道具、永久强化与工坊扩建；配置进化阶梯、升级成本与开箱三选一，让长期积累与单局构筑形成区别。</p></section>
      <section class="resume-page__section"><h4>战斗反馈与边界</h4><p>细化蓄压、前冲、落地和收势阶段，设置完美释放窗口，按动画接触点结算伤害，并校验暂停、取消技能与重复结算等边界。</p></section>`,
  },
  {
    id: 'game-engines', title: '游戏引擎与原型', label: 'ENGINE PRACTICE / 03',
    content: `<p class="resume-page__intro">以可玩原型验证规则和交互。将场景、资产、界面与逻辑放进同一流程，结合构建和实机检查持续迭代。</p>
      <section class="resume-page__software"><strong>Unity 2022.3</strong><small>第一人称交互 / 可玩切片</small><p>在《夜班便利店》中整合场景资产、第一人称交互、顾客路径、收银 UI 与自动存档；完成 Windows 构建，并通过自动逻辑校验检查顾客结账流程。</p></section>
      <section class="resume-page__software"><strong>Godot 4</strong><small>动作原型 / AI 辅助开发</small><p>在开发中的《糖壳暴食兽》中整合角色、工厂与交互物，处理碰撞、敌人绕行及落点可达性，持续验证成长与战斗系统。</p></section>
      <section class="resume-page__software"><strong>Unity · UE5 · Godot</strong><small>引擎与资产整合</small><p>地编、场景特效、资产导入、碰撞与导航，以及交互和 UI 整合。</p></section>`,
  },
  {
    id: 'three-dimensional', title: '三维制作与材质', label: '3D & MATERIAL / 04',
    content: `<p class="resume-page__intro">兼顾模型结构、材质表现与引擎接入。三维制作既服务于视觉表达，也用于可玩场景中的角色、设备与交互物。</p>
      <section class="resume-page__software"><strong>Maya · Blender</strong><small>建模 / 拓扑 / UV</small><p>熟练运用两款软件进行硬表面建模、拓扑与 UV 处理；具备基础角色绑定及动作验证能力。关注资产从制作到实际使用的完整过程。</p></section>
      <section class="resume-page__software"><strong>Substance · Arnold</strong><small>PBR 材质 / 灯光 / 渲染</small><p>制作 PBR 贴图，调试材质与灯光，通过多视角渲染检查模型、表面质感及画面表现。</p></section>
      <section class="resume-page__section"><h4>接入与检查</h4><p>采用 AI 辅助 Blender 资产制作与整合流程，将角色、场景、设备和交互物导入引擎；结合实机截图与检查修正特效表现问题。</p></section>`,
  },
  {
    id: 'visual-post', title: '视觉与后期软件', label: 'VISUAL TOOLKIT / 05',
    content: `<p class="resume-page__intro">从静态界面素材到动态影像，围绕清晰的视觉信息、合适的节奏和最终输出组织制作。</p>
      <section class="resume-page__software"><strong>Photoshop · Illustrator</strong><small>图像 / 矢量 / 视觉排版</small><p>图像处理、矢量图形、界面素材与视觉排版。将平面制作能力用于内容表达及游戏界面素材的整理。</p></section>
      <section class="resume-page__software"><strong>After Effects · Premiere</strong><small>剪辑 / MG 动画 / 跟踪合成</small><p>完成人物片头、广告短片与动态图形作品；处理标题排版、节奏转场、跟踪合成及音画节奏，组织素材形成完整影像。</p></section>
      <section class="resume-page__software"><strong>FFmpeg</strong><small>视频处理 / 格式导出</small><p>配合后期制作完成视频格式导出。结合剪辑与合成流程整理最终输出，服务于短片和作品内容交付。</p></section>`,
  },
  {
    id: 'content-workflow', title: 'AI 内容与运营方向', label: 'CONTENT WORKFLOW / 06',
    content: `<p class="resume-page__intro">将 AI 游戏运营定位在内容方向，关注玩法卖点怎样被看见，以及概念、生成素材和后期制作如何形成一致的表达。</p>
      <section class="resume-page__section"><h4>概念与镜头组织</h4><p>进行提示词设计、概念与分镜整理。已完成香水、口红、运动手环和服装四组产品主题短片，将概念、视觉母版、镜头关键帧与后期剪辑组织为完整作品。</p></section>
      <section class="resume-page__section"><h4>一致性与筛选</h4><p>通过产品母版、角色身份板和场景参考统一视觉；围绕动作、材质和转场筛选生成素材，结合人工检查持续修正镜头表现。</p></section>
      <section class="resume-page__section"><h4>游戏理解与内容表达</h4><p>体验覆盖开放世界、竞技对战、动作 Roguelite 与模拟经营等品类，关注玩法卖点、引导反馈及成长循环。</p></section>`,
  },
  {
    id: 'delivery-practice', title: '制作协作与交付', label: 'PRACTICE & DELIVERY / 07',
    content: `<p class="resume-page__intro">把制作推进到能够体验、检查和展示的版本。关注资源整理、流程衔接，以及内容落地后的实际表现。</p>
      <section class="resume-page__section"><h4>工作室协作</h4><p>参与学院数字媒体工作室，承担三维资源制作、场景与镜头整理、后期剪辑及团队协作，连接三维制作与影像输出环节。</p></section>
      <section class="resume-page__section"><h4>版本与内容交付</h4><p>个人项目已形成 Unity Windows 可玩垂直切片，并持续迭代 Godot 动作原型。视觉内容实践保留成片与制作过程，通过实机截图、逻辑校验和人工检查修正问题。</p></section>
      <section class="resume-page__section"><h4>荣誉与认证</h4><ul class="resume-page__list"><li>2025 第八届纸质媒体艺术创作大赛 · 全国三等奖</li><li>计算机二级 · 大学英语四级</li><li>SYB 创业培训合格证书</li></ul></section>`,
  },
  {
    id: 'contact', title: '求职方向与联系', label: 'CONTACT / 08',
    content: `<p class="resume-page__intro">希望将玩法设计、三维美术和视觉内容制作实践，运用到游戏相关岗位。以完整简历和实际作品说明自己的能力。</p>
      <section class="resume-page__section"><h4>游戏策划 · 玩法 / 系统</h4><p>关注规则、反馈、成长与原型验证，将玩法想法落实为可玩的交互流程，结合引擎与美术整合经验推进场景落地。</p></section>
      <section class="resume-page__section"><h4>AI 游戏运营 · 内容方向</h4><p>关注游戏卖点表达、AIGC 视觉内容与素材迭代，串联概念、生成筛选、后期制作和内容交付。</p></section>
      <address class="resume-page__contact"><span>王丞业 · 2027 届本科 · 意向杭州</span><a href="mailto:3151109516@qq.com">3151109516@qq.com <i>↗</i></a><a href="tel:18970843804">189 7084 3804</a><p>作品集 <span>wcy90.cn</span></p></address>
      <p class="resume-page__note">完整简历可在书本上方下载，分别对应游戏策划与 AI 游戏运营内容方向，便于保存和进一步了解。</p>`,
  },
];
