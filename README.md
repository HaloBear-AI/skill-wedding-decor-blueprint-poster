# Wedding Decor Blueprint Poster

将一张婚礼布置效果图或实拍照转成 3:4 竖版工程示意展板，便于策划师与新人沟通方案、向团队交底和分享。展板包含原图、正立面和平面、H/W/D/A 尺寸标注、5 至 8 行物料、6 个组件和 5 步布置顺序。成果同时包含可编辑的 `decor-spec.json` 和按槽位命名的子图。

## 安装

使用交付的 `wedding-decor-blueprint-poster.zip`，或将仓库检出到同名目录。

```sh
git clone https://github.com/HaloBear-AI/skill-wedding-decor-blueprint-poster.git wedding-decor-blueprint-poster
```

| 宿主 | 安装与调用 |
| --- | --- |
| Codex | 将整个 `wedding-decor-blueprint-poster/` 放进项目 `.agents/skills/` 或个人目录 `~/.agents/skills/`。在输入框选择技能，或输入 `$wedding-decor-blueprint-poster`。[Codex 技能文档](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | 把技能目录放进项目 `.claude/skills/` 或个人目录 `~/.claude/skills/`。输入 `/wedding-decor-blueprint-poster`，必要时用 `/reload-skills` 刷新。[Claude Code 技能文档](https://code.claude.com/docs/en/skills) |
| Claude 网页 | 启用 Code execution and file creation。在 **Customize → Skills → Create skill → Upload a skill** 导入 ZIP，启用技能后附图提出请求。[自定义技能安装文档](https://support.claude.com/en/articles/12512180-use-skills-in-claude) |
| 腾讯 WorkBuddy | **专家·技能·连接器 → 技能 → 添加技能 → 上传技能**，选择 ZIP。新建任务时在输入框的技能选择器启用，再附上原图。按项目安装时可把技能目录放在项目 `.codebuddy/skills/`。[WorkBuddy 上传技能](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market) · [项目路径](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project) |

Claude 网页与 WorkBuddy 的 ZIP 第一层为 `wedding-decor-blueprint-poster/`，直接包含 `SKILL.md`、`scripts/`、`references/` 和 `assets/`。从 GitHub 下载源码后，请先解压并改成该目录名，再将整个技能目录压成 ZIP。[Claude ZIP 格式](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) · [WorkBuddy 技能目录格式](https://open.workbuddy.cn/docs/skill)

## 运行条件

- 脚本需要 Python 3.9+ 和 Pillow 9.1+。如果宿主运行环境已安装 Pillow，可以直接离线执行三个脚本。需安装时运行 `python3 -m pip install "Pillow>=9.1"`，Windows 等环境可用 `python`。
- 支持 Pillow 可读的栅格输入，优先用 PNG、JPEG 或 WebP。可选 Logo 建议透明 PNG。包含简体中文常用字符的 Noto Sans SC 随包提供。可用 `--font` 指定其他覆盖所需文字的字体。
- 文本和版式由 Pillow 排版。支持参考图生图且可导出素材的宿主可生成全部子图。只有读图能力的宿主可输出规格、可复用的提示词及占位展板。宿主也可使用人工准备的同名素材。三个脚本离线运行，无需 API 密钥。

## 最小使用示例

安装后附上一张场布图，向宿主提出请求。

> 用 wedding-decor-blueprint-poster 把这张场布图做成中文工程示意展板。主题用「雾野初晴」。请同时给我 PNG、decor-spec.json 和可替换的子图。

也可以在技能根目录用本包中的原创示例素材自测。

```sh
python3 scripts/validate_spec.py --spec assets/example/decor-spec.json
python3 scripts/compose_board.py --spec assets/example/decor-spec.json --original assets/example/scene.png --assets assets/example/subimages --output output/board.png
```

每次运行可指定 `--logo`、`--font`、`--size 1080x1440` 或 `--hero-fit cover` 等选项，用 `--help` 查看参数。更换同名子图后重用合成命令。

## 目录

| 路径 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent 入口、三种运行路径和复作方法 |
| [scripts/compose_board.py](scripts/compose_board.py) | 等比适配、文字排版、标线和占位，输出 PNG |
| [scripts/slice_grid.py](scripts/slice_grid.py) | 网格等分，按行切出 6 张组件或 5 张步骤 |
| [scripts/validate_spec.py](scripts/validate_spec.py) | 校验 JSON 结构、字段长度、数量及尺寸值 |
| [references/decor-analysis.md](references/decor-analysis.md) | 场布拆解、字段填写和婚礼术语 |
| [references/image-prompts.md](references/image-prompts.md) | 无字单图、网格以及可选整版提示词 |
| [references/layout.md](references/layout.md) | 版式坐标、文案拼接规则与验收 |
| [assets/decor-spec.schema.json](assets/decor-spec.schema.json) | 机器可读的规格定义 |
| [assets/example/](assets/example/) | 原创示例主图、可校验规格和 13 张示例插画 |
| [assets/fonts/](assets/fonts/) | 离线字体及其 OFL 许可 |
| [LICENSE.txt](LICENSE.txt) | Skill 文档、脚本和原创示例的 MIT 许可 |

示意图用于方案沟通。单张照片能确立的空间关系有限，实际尺寸以现场实测为准。随包字体来自 Google Fonts，按 OFL 许可使用。[字体来源](https://github.com/google/fonts/tree/main/ofl/notosanssc) · [OFL 许可](assets/fonts/OFL.txt)
