---
name: mm-character-assets
description: 从单人人物头像规划、生成、检查和续做同一角色的全身三视图或多视角资产板。用于 AI 真人剧、古装、MV、制服、奇幻和科幻角色资产；当用户只需捏脸、动态表情或多人群像时不要使用。
metadata:
  short-description: 固定人物多视角资产
---

# 定妆谱

把一张清晰的单人人物头像转化为可追溯的固定人物资产：同一身份、同一造型、同一场次状态的全身视角、面部参考和必要细节，最终组合为一张资产板。

## 不可破坏的约束

- 原头像只证明可见内容。看不见的侧面、身体、背面和服装结构必须标为 `design_completion`，不能称为真实还原。
- 身份、身体、造型和场次分别版本化。换衣服不递增 `identity_version`；湿发或战损使用新的 `condition_id`。
- 用户明确指定的视角数量、角度和 `body_only` 优先于自动规划。纯三视图必须恰好三张全身图。
- 左右始终以角色自身为准。`left_profile` 的鼻尖朝画面左侧；禁止镜像冒充另一侧。
- 自动视觉检查、设计补全和用户批准分开记录。没有视觉能力时只能交付 `prompt_package_ready`，不能宣称图片已验收。
- 默认 `detail_level=enhanced`：现代简单角色也要有正面/3⁄4/侧面面部、眉眼、鼻唇和鞋履斜前/侧面。只有用户明确说轻量版时才用 `compact`；纯三视图仍遵守 `body_only`。
- 主交付默认横向 16:9，画布内部四周约短边 2% 的等宽不透明 `#FFFFFF` 白框，内区 `#F4F5F6`；上方左侧排全身、上方右侧排面部，底部横排局部细节。内容与标签不得侵入白框。
- 分区标题和每格中文名称默认开启，文字由确定性组合器写入独立留白区；没有可显示中文的真实字体时必须标记未完成，不能交付乱码或伪文字。
- 所有生成和修复共用预算。增强版默认最多 24 次图像请求、6 次总修复、每单元 2 次修复；轻量版可用 16/4 预设，已有更低预算不得被升级覆盖。
- 拼版只允许已检查裁片、等比缩放、留白、白框、标签和色板；不能在拼版阶段重画脸、五官、鞋、材质或配饰。

## 工作流

1. **检查输入。** 必须有可访问的身份参考。多人、无法辨认主要五官或互相冲突且未指定优先级时进入 `blocked`。受限参考继续执行时记录遮挡、滤镜和未知项。
2. **建立规格。** 记录 `reference_registry`，提取可见身份事实，选择题材与表现风格，补全身体和造型，给部件稳定 ID，并建立 `part_coverage`。
3. **规划板式。** 运行 `scripts/plan_board.py`。`auto` 根据实际结构复杂度选择 3 或 4 个全身视角；三视图和自定义模式不得被覆盖。除 `compact` 或 `body_only` 外，必须规划增强版面部、五官和鞋履。
4. **锁定规格。** 运行 `scripts/validate_spec.py --target-state spec_locked`。未解决的必需结构、无覆盖的必需部件或超预算计划不得进入生成。
5. **选择生成路径。** 能分次生成时默认采用“正面基准 → 其他视角 → 细节 → 拼版”；简单造型或只能单次生成时可用快速总图。先读取 [适配器契约](references/adapter-contract.md)。
6. **编译提示词并生成。** 按任务只加载需要的题材规则和 [提示词模板](references/prompt-templates.md)。每张参考都要声明角色与作用范围。不要发出工具不支持的 seed、权重或尺寸参数。
7. **逐格验收。** 依据 [质量验收](references/quality-review.md) 检查身份、视角、服装、左右、完整性和有效细节。失败只修复受影响单元；所有调用写入账本。
8. **组合与交付。** 仅使用已通过且匹配当前 `spec_revision` 的单格，运行 `scripts/compose_board.py`。保存布局清单，脚本检查 16:9、四边白框、图片/标签矩形、中文名称绑定和来源资产；最终再做身份与结构视觉检查。
9. **恢复或修改。** 先读取 [覆盖与续做](references/coverage-and-resume.md)，核对文件和指纹，复用未失效的通过单元。

状态主线：`received → analyzed → spec_locked → anchor_ready → views_ready → assembled → delivered`。终止状态还包括 `blocked`、`needs_review`、`draft_failed`、`prompt_package_ready` 和 `cancelled`。

## 按需读取

- 每次都读 [身份锁定](references/identity-lock.md)、[输入质量与风格](references/input-quality-and-style.md) 和 [质量验收](references/quality-review.md)。
- 题材识别或冲突处理读 [路由规则](references/routing.md)。
- 现代日常读 [现代规则](references/profiles-modern.md)；古装或年代读 [古装规则](references/profiles-historical.md)；制服、战术、奇幻或科幻读 [特殊规则](references/profiles-special.md)。不要同时加载无关题材全文。
- 自动选择细节读 [复杂度与细节](references/complexity-and-details.md)；视角、像素预算和板式读 [视角与布局](references/view-and-layout.md)。
- 调用图像工具前读 [适配器契约](references/adapter-contract.md)；中断恢复或局部修改读 [覆盖与续做](references/coverage-and-resume.md)。

## 项目文件

每个项目使用独立目录保存 `character-spec.json`、输入参考、提示词、单格图、检查结果、调用账本和总图。规格遵循 `assets/character-spec.schema.json`；版式定义在 `assets/board-layouts.json`；中文映射与侧别约定来自 `assets/label-catalog.json`。不要把运行数据写回 Skill 目录中的参考文档。

用户主交付是一张 PNG，以及简短的造型、视角、补全项和验收状态说明。若状态不是 `delivered`，必须直说剩余问题。
