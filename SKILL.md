---
name: wedding-decor-blueprint-poster
description: >-
  该技能在用户上传婚礼布置图并要求工程图、布置示意图、物料拆解、搭建顺序或婚礼海报时，把原图与正立面、平面、物料表、六个组件及五步布置顺序合成为竖版展板。 Creates a wedding decor blueprint, wedding setup diagram or materials breakdown poster from one wedding decor reference image.
---

# 婚礼场布蓝图海报

交付一张 3:4 竖版 PNG。主图区使用用户提供的原图，正立面、平面、六张核心部件和五张搭建步骤采用同一场景的示意插画。标题、所有标注、尺寸线、品牌顶栏和卡片由 Pillow 排版。默认完整显示主图，只有用户要求满铺裁切时才用 `--hero-fit cover`。[版式和成品核对](references/layout.md)

## 确认输入和输出

- 查看一张可以辨认场布主体的原图。用户提交多张图时，使用已指定的主图；主图不明确时请用户选定。缺图、场景主体无法辨认或宿主无法查看图像时，说明缺少的输入或能力，并请用户提供可查看的场布图或可核对的现有分析。生成所用的唯一场景参照始终是该原图。
- 优先使用用户或项目指定的交付目录。记录原图、规格、素材目录、输出文件和实际使用的可选文件相对于运行目录的位置。建议成品名 `board.png`，规格名 `decor-spec.json`，提示词包名 `image-prompts.md`，子图存入同一交付目录下的 `assets/`。
- 脚本需要 Python 3.9+ 和 Pillow 9.1+，离线完成文件读取、切图、校验和排版。Codex、Claude 和 WorkBuddy 按当前会话的工具能力选择路径。可查看原图、调用支持参考图输入及文件导出的生图工具并执行脚本时，可运行完整流程。

## 写入并校验规格

按可见证据填写 `decor-spec.json`。先收录用户提供的场地和测量数据，再记录图中可辨认的结构、位置、配色和材质特征。实测缺失的尺寸使用 `null`，默认显示「待实测」。缺少可画证据的 `prompt_detail` 使用 `null`，该插画位置使用占位。默认 `zh-CN`，标题和全部标签跟随成品语言。未指定主题时，根据场景拟题，中文约四字。品牌名和 Logo 取自用户指定的资料，两项均缺省时顶栏留白。省略 `palette` 时，排版脚本从原图取深强调色。[场布分析和字段填写](references/decor-analysis.md) · [规格定义](assets/decor-spec.schema.json) · [示例规格](assets/example/decor-spec.json)

在技能根目录执行下列命令，替换相对路径为本次文件位置。Windows 等环境也可用已安装的 Python 3.9+ 命令 `python` 执行。

```sh
python3 scripts/validate_spec.py --spec "task-output/decor-spec.json"
```

## 生成子图或准备占位版

**完整路径。** 使用宿主的参考图生图能力，逐张生成正立面和平面。核心部件及搭建步骤可逐张生成，也可分别生成一张三列两行的网格。每次只附同一原图，按规格生成无字插画。`prompt_detail` 为 `null` 的位置跳过。发现网格会令模型补造不可见的内容时，改用有依据的单图提示词。[子图和网格提示词](references/image-prompts.md)

**单次整版路径。** 适合一次试生成候选整版，且全部 13 张子图都有可画依据的情况。将候选整版的所有文字与规格和版式规定的拼接结果逐字核对。发现错字、增删、顺序漂移，或任一子图无法干净提取时，退回完整路径。候选通过后，提取 13 张只含插画的子图，按下列文件名保存。最终仍由 Pillow 使用同一原图重新排版。[整版提示词和提取验收](references/image-prompts.md#单次整版提示词)

**降级路径。** 宿主缺少支持参考图输入的生图能力时，展开全部单图槽位与两份网格提示词，保存为交付目录里的 `image-prompts.md`。标明跳过的单图和受限的网格，并用原图、规格和可用子图渲染占位版。宿主缺少 Python 或 Pillow 执行能力时，交付规格、完整提示词和已取得的子图，给出以本次实际输入路径替换后的校验、切图（如适用）和排版命令，说明目前的文件完成状态。[生成可直接复制的提示词包](references/image-prompts.md#提示词包)

将通过验收的 PNG 存入 `task-output/assets/`，文件名如下。

| 素材 | 文件名 |
| --- | --- |
| 正立面与平面 | `elevation.png`、`plan.png` |
| 六张核心部件 | `component-01.png` 至 `component-06.png`，与 `components` 顺序一致 |
| 五张搭建步骤 | `step-01.png` 至 `step-05.png`，与 `steps` 顺序一致 |

网格从左至右、从上至下排列，步骤图的最后一格留白。检查网格完整后运行对应命令。

```sh
python3 scripts/slice_grid.py --input "task-output/components-grid.png" --output-dir "task-output/assets" --kind components
python3 scripts/slice_grid.py --input "task-output/steps-grid.png" --output-dir "task-output/assets" --kind steps
```

脚本默认 `--rows 2 --cols 3`。不同规则网格用 `--rows N --cols N` 显式传入行列数，仍需满足可切出对应数量的图。`--inset PX` 将每格向内收边，适用于边缘留白充足的图纸。重新切割并替换本次同名文件时，确认目标后加 `--overwrite`。切图后逐张检查位置、边缘、内容和槽位顺序。

## 排版与交付

```sh
python3 scripts/compose_board.py --spec "task-output/decor-spec.json" --original "scene.jpg" --assets "task-output/assets" --output "task-output/board.png"
```

默认尺寸为 2160 × 2880。用 `--logo` 指向用户提供的 Logo，用 `--font` 指向覆盖成品文字的字体文件。用户有明确导出尺寸或裁切要求时，可传入脚本支持的尺寸，格式如 `--size 2160x2880`；主图可选择 `--hero-fit contain` 或 `--hero-fit cover`。子图缺失或损坏时使用占位。`prompt_detail` 为 `null` 的槽位保持占位。

打开 PNG，核对原图、标题与各区文案、尺寸待实测状态、插画顺序、裁切和字形。核对平面图的通道标线是否贴合可见近端。文字按规格修正后重新校验和排版。图稿缺证或未通过时，留占位并列出对应文件名。将本次实际使用或用于补作的提示词写入 `image-prompts.md`。交付成品、规格、提示词及子图目录；主题由画面拟定时，告知用户可修改 `theme` 后重排。

补作时用同一份原图调用已展开的对应提示词。按文件名替换通过检查的子图；如新增证据，先补写相应 `prompt_detail` 或尺寸，再校验规格、用原命令重新排版并回读成品。[版式和成品核对](references/layout.md)

## 常见失败

- **乱码或字体报错**。改用覆盖全部文案的字体文件，传入 `--font` 后重排。
- **子图错位、跨格或带字**。按格重验，缺陷槽位按对应单张提示词补作，保存前检查画面和命名。
- **图片格式无法读取**。保留源文件，另存为 PNG 或 JPEG 后重新提交路径。
- **文字虽然装得下但预览难读**。优先缩短配置、步骤或标签的措辞，保留用户给定信息，再排版回读。
