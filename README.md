# 王丞业 · 三维交互作品集

面向游戏策划与 AI 游戏运营（内容方向）的个人作品集。基于 Andrew Woan 的 [Sooah Room Folio](https://github.com/andrewwoan/sooahs-room-folio) 开发，使用 Vite、Three.js 和 GSAP。

## 当前网站

- 终端机欢迎首页：姓名、专业、求职方向与简介；静音加载页等待三个场景与 GPU 预热完成。
- 房间：独立资产交互、机器人巡游、连续的自动昼夜变化。
- 作品长廊：游戏原型、三维建模、特效和 AI 软件项目，展示视频与图文说明。
- 关于我：书桌场景中的简历书，包含游戏策划、运营内容方向、软件技能和联系方式。
- 支持减少动态效果偏好与移动端布局。

当前运行资源为房间 V20、长廊 V5、终端 V3 和关于我 V3；对照资源及历史网页资源一并保留。具体路径以 `src/material-release.js` 和场景模块为准，历史版本文档不代表当前状态。

## 本地运行

需要 Node.js 20.19+ 或 22.12+、pnpm 10、Git LFS。普通网页资源在 Git 中；可编辑 Blender 源文件使用 Git LFS。

```sh
git clone https://github.com/baonainiu-lab/wcy-room-portfolio.git
cd wcy-room-portfolio
git lfs install
git lfs pull
pnpm install --frozen-lockfile
pnpm dev
```

开发服务默认仅监听本机，地址通常是 `http://127.0.0.1:5173/`。

```sh
pnpm build
pnpm preview
```

构建结果在 `dist/`，由源码与 `public/` 重新生成，不提交重复构建产物。仅运行网站时不需要 Blender 源文件；若希望跳过这些大文件下载，可以先用 `GIT_LFS_SKIP_SMUDGE=1 git clone ...` 克隆，编辑模型前再运行 `git lfs pull`。

## 文件范围

- `src/`、`index.html`、`works/`：完整网站源码与作品页。
- `public/`：完整网页模型、贴图、字体、作品视频、图片、简历及授权文件，包含历史对照资源。
- `assets/`：制作脚本、资产清单、来源说明和十三份当前可编辑 Blender 场景。历史二进制试作、自动备份和下载压缩包保留在原设备，没有上传。
- `scripts/`：制作和校验脚本；部分历史 Blender 检查需要原设备上的历史源文件。
- `docs/`：版本记录、设计决策、第三方素材台账和文案依据。
- `material-review/`：开发期材质比较页面，当前不是正式构建入口。

`node_modules/`、`dist/`、本机工具、临时文件和截图渲染输出不提交。早期 README 保存在 `docs/README_V14_ARCHIVE.md`，仅供历史查阅。

## 校验与发布

```sh
pnpm build
node scripts/check-startup-loader-c.mjs
node scripts/check-startup-readiness.mjs
```

CPU 检查使用模拟 DOM / GPU 环境，不能替代浏览器视觉和帧率验证。本仓库上传不包含网站部署，域名与部署位置另行确定。

## 来源与许可

原模板 [LICENSE.md](LICENSE.md) 原样保留。开场编排参考 Abigail Bloom 项目，许可与来源在 `public/licenses/abigail-bloom/`；加载标志动效来源见 `public/loader-review-v1/source/ATTRIBUTION.md`。

个人作品、简历、模型、字体与第三方素材不应一概视为模板的 MIT 授权；具体参见 [第三方素材台账](docs/THIRD_PARTY_ASSETS.md)、各资源目录的来源和许可证。场景制作记录如实区分 Blender MCP 操作、脚本辅助及 AI 概念生成。
