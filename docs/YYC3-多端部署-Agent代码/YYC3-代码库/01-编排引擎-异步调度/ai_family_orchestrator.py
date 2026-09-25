# ==============================================================
# AI FAmily 全链路协同编排引擎 v2.0（完整版）
# 整合全部 8 位 Agent + 公共 RAG，实现 ReAct-C 九步全链路闭环
# 链路：输入安全→意图路由→知识检索→任务执行→润色→汇总
#       →质量校验→输出审计→个性化补充
# 部署：与各 Agent 目录代码置于同一包目录（共享 base_agent 等模块）
# ==============================================================
from base_agent import BaseAgent
from yuanqi_tianshu_agent import YuanQiTianShuAgent
from zhiyun_shouhu_agent import ZhiYunShouHuAgent
from gewu_zongshi_agent import GeWuZongShiAgent
from chuangxiang_lingyun_agent import ChuangXiangLingYunAgent
from yanqi_qianhang_agent import YanQiQianHangAgent
from yushu_wanwu_agent import YuShuWanWuAgent
from yujian_xianzhi_agent import YuJianXianZhiAgent
from zhiyu_bole_agent import ZhiYuBoLeAgent
from milvus_retriever import MilvusRetriever


class AIFamilyOrchestrator:
    """AI FAmily 全链路协同编排引擎 v2.0（完整版）"""

    def __init__(self):
        # ===== 第一层：决策中枢 =====
        self.yuanqi = YuanQiTianShuAgent()

        # ===== 第二层：核心保障 =====
        self.zhiyun = ZhiYunShouHuAgent()            # 安全官
        self.gewu = GeWuZongShiAgent()               # 质量官
        self.chuangxiang = ChuangXiangLingYunAgent() # 创意官

        # ===== 第三层：业务执行 =====
        self.yanqi = YanQiQianHangAgent()            # 导航员·意图识别
        self.yushu = YuShuWanWuAgent()               # 思考者·数据分析
        self.yujian = YuJianXianZhiAgent()           # 预言家·趋势预测
        self.zhiyu = ZhiYuBoLeAgent()                # 伯乐·个性化推荐

        # ===== 公共能力 =====
        self.retriever = MilvusRetriever()           # 知识库检索

    def _get_knowledge(self, query: str, top_k: int = 5, category: str = None) -> list:
        """统一知识检索入口，返回带来源标识的格式化上下文（Step3）"""
        docs = self.retriever.search(query, top_k=top_k, category_filter=category)
        return [f"[来源：{d['source']}] {d['content']}" for d in docs]

    def execute(self, user_input: str, user_id: str = "default_user") -> dict:
        """完整全链路执行入口（ReAct-C 九步闭环）

        :param user_input: 用户请求
        :param user_id: 用户标识，用于个性化推荐（Step9）
        """
        print("=" * 60)
        print(f"[系统] 用户[{user_id}]请求：{user_input}")
        print("=" * 60)

        result = {
            "user_id": user_id,
            "user_input": user_input,
            "steps": [],            # 全链路步骤记录（审计依据）
            "agent_outputs": {},
            "final_output": "",
            "status": "success",
        }

        # ========== Step1：智云·守护 输入安全三级过滤 ==========
        print("\n[Step1] 输入安全三级过滤...")
        safety_check = self.zhiyun.check_input(user_input)
        result["steps"].append({"step": "input_safety", "result": safety_check})
        if not safety_check["safe"]:
            result["status"] = "blocked"
            result["final_output"] = f"请求已拦截：{safety_check['risk']}"
            return result

        # ========== Step2：言启·千行 意图识别与任务路由 ==========
        print("\n[Step2] 言启·千行 意图识别与任务路由...")
        route_result = self.yanqi.run(user_input)
        result["steps"].append({"step": "intent_routing", "result": route_result})
        intent = route_result["intent"]
        complexity = route_result["complexity"]
        need_rag = route_result["need_rag"]

        # ========== Step3：公共RAG 知识检索与上下文注入 ==========
        knowledge = []
        if need_rag:
            print("\n[Step3] 知识库语义检索...")
            knowledge = self._get_knowledge(user_input)
            result["steps"].append({"step": "rag_retrieve",
                                    "result_count": len(knowledge)})

        # ========== Step4：分场景任务执行（语枢+预见 等） ==========
        print("\n[Step4] 任务执行...")
        outputs = result["agent_outputs"]

        # —— 场景A：纯数据分析 ——
        if intent == "data_analysis":
            outputs["yushu_analysis"] = self.yushu.analyze(user_input, knowledge)

        # —— 场景B：趋势预测（语枢打底 + 预见定量预测） ——
        elif intent == "trend_forecast":
            outputs["yushu_analysis"] = self.yushu.analyze(user_input, knowledge)
            # 示例营收序列，生产环境可从数据库提取真实历史数据
            historical_data = [120, 135, 150, 168, 192, 220]
            forecast_res = self.yujian.full_forecast(
                "核心指标", historical_data, 3, "基准", knowledge)
            outputs["yujian_forecast"] = forecast_res["analysis_report"]

        # —— 场景C：报告润色（语枢生成 + 创想润色） ——
        elif intent == "report_polish":
            raw_content = self.yushu.analyze(user_input, knowledge)
            outputs["raw_analysis"] = raw_content
            outputs["polished_report"] = self.chuangxiang.polish_report(
                raw_content, style="商务正式", audience="管理层",
                knowledge_context=knowledge)

        # —— 场景D：创意策划/营销文案 ——
        elif intent == "creative_brainstorm":
            outputs["creative_ideas"] = self.chuangxiang.brainstorm_ideas(
                user_input, direction_count=3, knowledge_context=knowledge)

        # —— 场景E：人才发展/个性化推荐 ——
        elif intent == "personnel_development":
            outputs["user_profile"] = self.zhiyu.build_user_profile(
                user_id, {}, user_input)
            outputs["growth_plan"] = self.zhiyu.plan_growth_path(
                user_id, user_input, "3个月")

        # —— 场景F：综合复杂任务（元启·天枢总指挥调度全团队） ——
        elif complexity == "multi_agent" or intent == "multi_agent_comprehensive":
            print("[Step4.1] 元启·天枢 启动多Agent协同调度...")
            outputs["yushu_analysis"] = self.yushu.analyze(user_input, knowledge)
            outputs["yujian_forecast"] = self.yujian.qualitative_analysis(
                user_input, knowledge)
            outputs["creative_optimize"] = self.chuangxiang.polish_report(
                outputs["yushu_analysis"], knowledge_context=knowledge)
            outputs["yuanqi_summary"] = self.yuanqi.synthesize(user_input, outputs)

        # —— 默认：通用问答 ——
        else:
            outputs["general_answer"] = self.yushu.analyze(user_input, knowledge)

        # ========== Step5：创想·灵韵 润色（场景F已含则跳过） ==========
        if intent in ("data_analysis", "trend_forecast"):
            core_for_polish = outputs.get("yushu_analysis", "")
            if intent == "trend_forecast":
                core_for_polish += f"\n\n预测补充：{outputs.get('yujian_forecast', '')}"
            outputs["polished_report"] = self.chuangxiang.polish_report(
                core_for_polish, style="商务正式", audience="管理层",
                knowledge_context=knowledge)

        # ========== Step6：元启·天枢 全局汇总（场景F已含则跳过） ==========
        if "yuanqi_summary" not in outputs and "polished_report" in outputs:
            outputs["yuanqi_summary"] = self.yuanqi.synthesize(
                user_input, outputs)

        # ========== Step7：格物·宗师 质量校验与事实核查 ==========
        print("\n[Step7] 格物·宗师 质量校验...")
        core_content = (outputs.get("polished_report")
                        or outputs.get("yuanqi_summary")
                        or outputs.get("yushu_analysis", ""))
        quality_result = self.gewu.validate(core_content, knowledge)
        result["steps"].append({"step": "quality_check", "result": quality_result})

        # 质量不达标 → 创想·灵韵执行二次优化
        if not quality_result["passed"]:
            print("[Step7.1] 质量不达标，执行二次优化...")
            optimize_prompt = (f"请根据以下建议修正内容：\n"
                               f"{quality_result['suggestions']}\n\n原内容：\n{core_content}")
            core_content = self.chuangxiang.polish_report(
                optimize_prompt, knowledge_context=knowledge)
            outputs["optimized_content"] = core_content

        # ========== Step8：智云·守护 输出审计与脱敏 ==========
        print("\n[Step8] 输出安全审计...")
        audit_result = self.zhiyun.audit(core_content)
        result["steps"].append({"step": "output_audit", "result": audit_result})

        if not audit_result["safe"]:
            result["status"] = "blocked"
            result["final_output"] = "输出内容未通过安全合规审计"
            return result

        # ========== Step9：知遇·伯乐 个性化收尾 ==========
        if user_id != "default_user":
            print("\n[Step9] 知遇·伯乐 用户画像更新与个性化补充...")
            profile = self.zhiyu.build_user_profile(
                user_id, {"查询主题": [user_input[:50]]})
            recommendations = self.zhiyu.recommend_content(
                user_id, scene="学习提升", knowledge_pool=knowledge, top_n=2)
            result["agent_outputs"]["user_profile"] = profile
            result["agent_outputs"]["personalized_recs"] = recommendations

        # 最终输出（已脱敏）
        result["final_output"] = audit_result["desensitized_content"]

        print("\n" + "=" * 60)
        print("[系统] 全链路任务执行完成")
        print("=" * 60)
        return result


# -------------------------- 端到端场景演示 --------------------------
if __name__ == "__main__":
    orchestrator = AIFamilyOrchestrator()

    user_query = "生成本季度经营分析报告，包含数据解读、趋势预测、风险提示和可视化建议"
    result = orchestrator.execute(user_query, user_id="manager_001")

    print("\n" + "=" * 60)
    print("📌 最终经营报告")
    print("=" * 60)
    print(result["final_output"])

    print("\n🔍 全链路执行节点：")
    for step in result["steps"]:
        print(f"  - {step['step']}")
