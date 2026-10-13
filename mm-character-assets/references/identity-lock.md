# 身份锁定

## 观察与补全

Identity Spec 的每项使用 `id / description / source / visibility / lock_policy / reference_id`。`source` 只允许 `user`、`reference_visible`、`design_completion`、`unresolved`。被遮挡的五官不得写成可见事实。

原头像始终是身份依据，文字摘要不能替代图片。只记录脸型轮廓、眼眉关系、鼻唇、可见皮肤特征、发际线、年龄感和可见不对称。不要把“漂亮”“高级”等审美判断当作身份特征。

## 基准

正面基准由正面全身造型和足够清晰的正面面部共同构成。全身脸过小时，另外生成同 look 的面部基准；两者必须核对发际线、妆容、头饰、耳饰和衣领。通过后将 `identity.lock_status` 从 `provisional` 改为 `verified_anchor`，并写入真实的 `review_method`。

跨角度不可唯一确定的鼻侧、耳形、后脑等可形成一致的设计补全。已通过的侧面能成为项目内辅助参考，但每次仍保留原头像，避免逐代漂移。

## 版本

- 调整脸型、五官或替换身份参考：递增 `identity_version`，重新检查全部可见面部视角。
- 换服装、发型或头饰：递增 `look_version`，不改变身份版本。
- 湿发、战损等：新建 `condition_id`，不要混在同一资产板。
- 仅加视角或改排版：递增 `board_version`。

`user_approved` 只能由用户明确确认后设为 true，自动检查通过不能代替用户批准。
