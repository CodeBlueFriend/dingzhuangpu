# 测试报告

测试日期：2026-10-13（Asia/Shanghai）

## 自动化测试

执行环境：Python 3，依赖见 `requirements.txt`。

```bash
python -m unittest discover -s tests -v
python /path/to/skill-creator/scripts/quick_validate.py mm-character-assets
python mm-character-assets/scripts/validate_spec.py examples/specs/modern-simple.json --target-state spec_locked
python mm-character-assets/scripts/plan_board.py examples/specs/scifi-asymmetric.json
```

结果：12 项单元测试通过；三个公开示例均通过 JSON Schema；Skill 结构校验通过；三个示例的 `spec_locked` 阶段校验通过。测试覆盖：

- auto 简洁板默认三张全身视角。
- 复杂且左右不对称时增加真实右侧视角，而不是镜像。
- 用户明确三视图时，即使复杂度满分也不增加第四张全身图。
- `body_only` 清空面部和细节格。
- 基础计划超预算时在生成前拒绝。
- 重复部件 ID、错误三视图数量、必需结构未解决会阻止锁定。
- `anchor_ready` 没有清晰面部基准与真实检查方法时会失败。
- 拼版器拒绝未通过视角，且按目标比例导出 PNG。

## 实际生成测试

三张图片均通过宿主内置图像生成工具按独立提示词生成，并原样复制进 `examples/generated/`。公开样例不包含真人头像；角色均为虚构人物，所以本轮验证的是板式、视角、造型约束和信息覆盖，不是特定真人身份复现。

| 文件 | 实际尺寸 | 观察结果 | 状态 |
| --- | ---: | --- | --- |
| `modern-urban-board.png` | 1024×1536 | 正面、角色左侧、背面完整；两张面部参考可读；白衬衫与深色长裤一致；未发现耳环、项链、印花或标识 | 通过展示级检查 |
| `historical-fantasy-board.png` | 1312×1199 | 四张全身方向明确；背面未回头；发冠背面、腰封和袖层有独立细节；色彩和层序大体一致 | 通过展示级检查；明确为架空影视造型 |
| `scifi-tactical-board.png` | 1536×1024 | 正面、角色左侧、背面、角色右侧完整；背部脊柱连接清楚；左右肩结构有差异 | `needs_review`：右髋工具模块的“唯一性”和跨格严格位置一致仍需人工复核 |

SHA-256：

```text
703b8878514749397f1d338fcfe45c02a3bc4b44bf983105be6964d5f2fd0823  modern-urban-board.png
06be0b73cf31a35cab5d9672e49c2c1298f9494153f2e9d5ba47880ec84b568b  historical-fantasy-board.png
a925ee9513d3060148f9ac467273c6d3fa11246677b56a16c4df35831201d344  scifi-tactical-board.png
```

## 结论与限制

规划、阶段门槛、预算、方向、覆盖和确定性导出已经形成可运行闭环。一次生成的展示板仍不能代替“原始头像 → 分视角 → 逐格修复”的完整真人一致性实验；尤其是复杂不对称装备，需要在正式项目里保留单格图并逐项核对。本项目因此不声称像素级身份一致，也不把科幻样例的可疑项标为通过。
