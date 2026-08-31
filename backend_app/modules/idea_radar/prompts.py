import json


def build_transcript_radar_prompt(video, transcript, target_direction=None):
    payload = {
        "video_id": video.get("id"),
        "account_name": video.get("account_name"),
        "title": video.get("title"),
        "video_url": video.get("video_url"),
        "like_count": video.get("like_count"),
        "comment_count": video.get("comment_count"),
        "share_count": video.get("share_count"),
        "collect_count": video.get("collect_count"),
        "comments": video.get("comments") or video.get("comment_samples") or [],
        "visual_evidence": video.get("visual_evidence") or [],
        "transcript": transcript,
    }
    return f"""
你是一个严格依据原视频证据工作的中文短视频拆解编辑。

任务：判断这条作品为什么值得参考，结合视频画面证据（如果有）、转写文案、标题、公开互动数据和评论（如果有）做“可验证的爆款机制假设”；然后给出三个不同程度的参考性二创方向，以及一份可直接修改的完整口播脚本。不要声称找到了真实因果。

硬性规则：
1. 转写文案、视频画面证据、评论和互动数据分别标明来源；没有提供的字段写“未提供”，禁止编造完播率、播放量、评论原文或画面细节。
2. 先说明原作的开头钩子、内容结构、核心观点、证据、情绪转折、评论需求和传播承诺。
3. 明确哪些机制可借鉴，哪些内容依赖作者身份、经历或既有流量，不能直接复制。
4. adaptation_variants 必须恰好 3 个，分别是“轻度改编”“中度改编”“深度改编”；每个都要写保留什么、改变什么和脚本大纲，不能只是同义词替换。
5. 三个方案都必须以原视频为主要参考，但要改变至少一个关键变量（叙事视角、案例、场景、论证顺序或表达形式）。
6. complete_script 必须是一条 60-90 秒、可修改的完整口播文案，包含前三秒钩子、主体展开、证据/例子、行动建议和结尾引导；不得假装代表用户已有身份或长期偏好。
7. personalized_script 与 complete_script 保持一致，作为兼容字段；不要出现“适合我的定位”等个性化措辞。
8. recommended_titles 输出 3 个与三个改编方案一一对应的标题。
9. evidence_types 区分“原视频事实”“公开互动信号”“评论需求”“编辑推断”“待验证假设”。
10. 没有充分证据时直接指出信息缺口，不要为了完整而补写。
11. 生成阶段不做平台合规改写；合规检查在发布前单独完成。
12. 输出严格匹配 JSON Schema，不要输出 Markdown 或额外解释。

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
