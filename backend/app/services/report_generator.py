from typing import List, Dict, Any

class RealisticReportGenerator:
    """
    محرك توليد التقارير الواقعية لبيئة استشراف المحلية
    """
    
    @staticmethod
    def build_contextual_prompt(environment_context: Dict[str, Any]) -> str:
        entities: List[Dict] = environment_context.get("entities", [])
        relations: List[Dict] = environment_context.get("relations", [])
        domain: str = environment_context.get("domain", "التجارة والخدمات المحلية")
        
        entities_summary = ", ".join([f"{e.get('name')} ({e.get('type')})" for e in entities])
        relations_summary = ", ".join([f"{r.get('source')} -> {r.get('relation')} -> {r.get('target')}" for r in relations])

        prompt = f"""
أنت خبير تحليل واستشراف تشغيلي ميداني لمجال ({domain}).
يجب أن يكون التقرير واقعياً جداً ومتوافقاً 100% مع بيئة العمل الحقيقية الموصوفة أدناه، ودون استعراض نظريات عامة.

بيانات البيئة المدخلة:
- الكيانات النشطة: {entities_summary}
- شبكة العلاقات الفعلية: {relations_summary}

التعليمات الإلزامية لكتابة التقرير:
1. صغ التقرير بناءً على طبيعة السوق والعمليات الميدانية الفعلية لهذه الكيانات (مثل التعاملات بين التجار، المنصات الخدمية، والعملاء).
2. حدد الاختناقات والمخاطر التشغيلية المباشرة الناجمة عن العلاقات الموضحة في الشبكة.
3. قدم خطة عمل وتوصيات فورية قابلة للتطبيق الواقعي على أرض الواقع لتجاوز السلبيات وتحسين الاستشراف المستقبلية.
4. تجنب تماماً المصطلحات الأكاديمية المبهمة أو التعميمات السطحية.
        """
        return prompt.strip()
