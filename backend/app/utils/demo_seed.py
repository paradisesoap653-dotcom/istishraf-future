"""
توليد المحاكاة العربية التجريبية الجاهزة تلقائياً عند أول تشغيل للخادم السحابي
"""

import os
import json
import csv
from ..config import Config
from ..models.project import Project, ProjectStatus, ProjectManager
from ..services.simulation_manager import SimulationState, SimulationStatus
from ..services.oasis_profile_generator import OasisAgentProfile
from ..services.report_agent import Report, ReportStatus, ReportOutline, ReportSection, ReportManager


def seed_arabic_demo_if_missing() -> None:
    sim_id = "sim_demo_ar_001"
    sim_state_file = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sim_id, "state.json")
    if os.path.exists(sim_state_file):
        return

    now_iso = "2026-11-12T08:30:00"
    proj_id = "proj_demo_ar_001"
    graph_id = "graph_demo_ar_001"
    report_id = "report_demo_ar_001"
    sim_req = (
        "توقّع ردود فعل السكان، وأصحاب الأعمال التجارية، وشركات التوصيل، والخبراء الاقتصاديين "
        "تجاه مبادرة تطبيق النقل الكهربائي الذكي والتعرفة المرنة لأوقات الذروة ودعم الطاقة الشمسية المنزلية خلال الأسابيع الأولى من الإعلان."
    )

    graphs_dir = os.path.join(Config.UPLOAD_FOLDER, "graphs")
    os.makedirs(graphs_dir, exist_ok=True)

    nodes = [
        {"uuid": "n1", "name": "هيئة التطوير الحضري", "labels": ["Entity", "جهة_حكومية"], "summary": "الجهة المشرفة على إطلاق مبادرة النقل الكهربائي الذكي ودعم الطاقة الشمسية المنزلية.", "created_at": now_iso},
        {"uuid": "n2", "name": "د. طارق المنصور", "labels": ["Entity", "خبير_اقتصادي"], "summary": "محلل اقتصادي متخصص في سياسات الطاقة والنقل الحضري وتأثير التسعير المرن على التضخم.", "created_at": now_iso},
        {"uuid": "n3", "name": "م. سارة العتيبي", "labels": ["Entity", "رائدة_أعمال"], "summary": "مؤسسة شركة ناشئة لحلول الألواح الشمسية المنزلية وتخزين الطاقة الذكية.", "created_at": now_iso},
        {"uuid": "n4", "name": "خالد الدوسري", "labels": ["Entity", "صاحب_متجر"], "summary": "يمتلك سلسلة متاجر تجزئة في وسط المدينة ويعتمد على حركة المتسوقين وشركات التوصيل.", "created_at": now_iso},
        {"uuid": "n5", "name": "منصة برق للتوصيل", "labels": ["Entity", "شركة_لوجستية"], "summary": "شركة توصيل سريعة تدير أسطولاً من 3500 مندوب وتدرس التحول التدريجي للمركبات الكهربائية.", "created_at": now_iso},
        {"uuid": "n6", "name": "ليلى الحسن", "labels": ["Entity", "مواطنة_موظفة"], "summary": "موظفة قطاع خاص تتنقل يومياً في ساعات الذروة الصباحية والمسائية وتهتم بتكلفة المعيشة.", "created_at": now_iso},
        {"uuid": "n7", "name": "يوسف الكناني", "labels": ["Entity", "صحفي_تقني"], "summary": "كاتب ومؤثر تقني يغطي أخبار المدن الذكية والتحول الرقمي على منصتي إكس وريديت.", "created_at": now_iso},
        {"uuid": "n8", "name": "مبادرة النقل الذكي 2027", "labels": ["Entity", "سياسة_عامة"], "summary": "خطة متكاملة تشمل حافلات كهربائية ترددية، تعرفة مرنة للذروة، ومنح 35% للطاقة الشمسية المنزلية.", "created_at": now_iso},
    ]

    edges = [
        {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n8", "name": "أطلقت_مبادرة", "fact": "أطلقت هيئة التطوير الحضري مبادرة النقل الذكي 2027 لتخفيف الازدحام بنسبة 28%.", "created_at": now_iso},
        {"uuid": "e2", "source_node_uuid": "n2", "target_node_uuid": "n8", "name": "يحلل_أثر", "fact": "يرى د. طارق المنصور أن نجاح التعرفة المرنة مشروط بجهوزية بدائل النقل العام قبل التطبيق.", "created_at": now_iso},
        {"uuid": "e3", "source_node_uuid": "n3", "target_node_uuid": "n8", "name": "تستفيد_من", "fact": "تتوقع م. سارة العتيبي تضاعف الطلب على أنظمة الطاقة الشمسية المنزلية بفضل منحة الـ 35%.", "created_at": now_iso},
        {"uuid": "e4", "source_node_uuid": "n4", "target_node_uuid": "n5", "name": "يعتمد_على", "fact": "يعتمد خالد الدوسري على منصة برق للتوصيل في 45% من مبيعات متاجره اليومية.", "created_at": now_iso},
        {"uuid": "e5", "source_node_uuid": "n5", "target_node_uuid": "n8", "name": "تطالب_باستثناء", "fact": "تطالب منصة برق للتوصيل بإعفاء مركبات التوصيل الكهربائية من رسوم الذروة.", "created_at": now_iso},
        {"uuid": "e6", "source_node_uuid": "n6", "target_node_uuid": "n8", "name": "تتحفظ_على", "fact": "تخشى ليلى الحسن من ارتفاع تكلفة التنقل الصباحي قبل اكتمال خطوط الحافلات السريعة.", "created_at": now_iso},
        {"uuid": "e7", "source_node_uuid": "n7", "target_node_uuid": "n2", "name": "يناقش_تحليلات", "fact": "ينشر يوسف الكناني مقارنات رقمية تستند إلى تحليلات د. طارق المنصور حول تجارب المدن العالمية.", "created_at": now_iso},
        {"uuid": "e8", "source_node_uuid": "n3", "target_node_uuid": "n6", "name": "تقدم_حلولاً_لـ", "fact": "تعرض شركة سارة العتيبي باقات تقسيط ميسّرة للأسر لخفض فاتورة الكهرباء وشحن المركبات منزلياً.", "created_at": now_iso},
    ]

    with open(os.path.join(graphs_dir, f"{graph_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"graph_id": graph_id, "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}, f, ensure_ascii=False, indent=2)

    proj_dir = os.path.join(Config.UPLOAD_FOLDER, "projects", proj_id)
    proj_files_dir = os.path.join(proj_dir, "files")
    os.makedirs(proj_files_dir, exist_ok=True)
    sample_doc_path = os.path.join(proj_files_dir, "مبادرة_المدن_الذكية_والنقل_2027.md")
    sample_doc_text = (
        "# وثيقة مبادرة المدن الذكية والطاقة النظيفة 2027\n"
        "1. تشغيل شبكة حافلات كهربائية ترددية سريعة تغطي المحاور الرئيسية كل 6 دقائق.\n"
        "2. تطبيق تعرفة مرنة لأوقات الذروة الصباحية مع إعفاء المركبات الكهربائية المشتركة.\n"
        "3. تقديم منحة حكومية بنسبة 35% لتركيب الألواح الشمسية المنزلية.\n"
    )
    with open(sample_doc_path, "w", encoding="utf-8") as f:
        f.write(sample_doc_text)
    with open(os.path.join(proj_dir, "extracted_text.txt"), "w", encoding="utf-8") as f:
        f.write(sample_doc_text)

    project = Project(
        project_id=proj_id,
        name="محاكاة مبادرة النقل الذكي والطاقة النظيفة (نموذج استشراف)",
        status=ProjectStatus.GRAPH_COMPLETED,
        created_at=now_iso,
        updated_at=now_iso,
        files=[{"filename": "مبادرة_المدن_الذكية_والنقل_2027.md", "path": sample_doc_path, "size": str(len(sample_doc_text.encode("utf-8")))}],
        total_text_length=len(sample_doc_text),
        ontology={
            "entity_types": [
                {"name": "جهة_حكومية", "description": "الهيئات التنظيمية والحكومية"},
                {"name": "خبير_اقتصادي", "description": "المحللون الاقتصاديون"},
                {"name": "رائدة_أعمال", "description": "رواد شركات الطاقة النظيفة"},
                {"name": "شركة_لوجستية", "description": "منصات التوصيل والنقل التجاري"},
                {"name": "مواطنة_موظفة", "description": "السكان والمتنقلون يومياً"}
            ],
            "relation_types": [
                {"name": "أطلقت_مبادرة", "description": "إطلاق سياسة عامة"},
                {"name": "يحلل_أثر", "description": "تقييم اقتصادي واجتماعي"},
                {"name": "تستفيد_من", "description": "الاستفادة من الحوافز"},
                {"name": "تتحفظ_على", "description": "إبداء تحفظات عملية"}
            ]
        },
        analysis_summary="تحليل أثر حزمة النقل الكهربائي الذكي والتسعير المرن ومنح الطاقة الشمسية.",
        graph_id=graph_id,
        simulation_requirement=sim_req,
    )
    ProjectManager.save_project(project)

    sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sim_id)
    os.makedirs(sim_dir, exist_ok=True)

    profiles_data = [
        OasisAgentProfile(user_id=0, user_name="tariq_econ", name="د. طارق المنصور", bio="أستاذ الاقتصاد الحضري ومستشار سياسات النقل المستدام.", persona="محلل موضوعي يركز على الأرقام والتدرج في تطبيق الرسوم المرنة.", karma=4200, friend_count=310, follower_count=18500, statuses_count=640, age=46, gender="male", mbti="INTJ", country="العالم العربي", profession="خبير اقتصادي", interested_topics=["الاقتصاد الحضري", "النقل المستدام"], source_entity_uuid="n2", source_entity_type="خبير_اقتصادي", created_at=now_iso),
        OasisAgentProfile(user_id=1, user_name="sara_solar", name="م. سارة العتيبي", bio="مهندسة طاقة متجددة ومؤسسة شركة شمس المستقبل.", persona="متحمسة للتحول الأخضر وتشارك دراسات جدوى الألواح الشمسية.", karma=3150, friend_count=420, follower_count=9400, statuses_count=410, age=33, gender="female", mbti="ENTP", country="العالم العربي", profession="رائدة أعمال طاقة نظيفة", interested_topics=["الطاقة الشمسية", "المركبات الكهربائية"], source_entity_uuid="n3", source_entity_type="رائدة_أعمال", created_at=now_iso),
        OasisAgentProfile(user_id=2, user_name="laila_commuter", name="ليلى الحسن", bio="محاسبة في شركة خاصة تتنقل يومياً وسط المدينة.", persona="تهتم بمواعيد الحافلات الترددية وتكلفة التنقل الشهرية.", karma=1280, friend_count=190, follower_count=820, statuses_count=215, age=31, gender="female", mbti="ISFJ", country="العالم العربي", profession="موظفة قطاع خاص", interested_topics=["تكلفة المعيشة", "المواصلات العامة"], source_entity_uuid="n6", source_entity_type="مواطنة_موظفة", created_at=now_iso),
        OasisAgentProfile(user_id=3, user_name="khalid_retail", name="خالد الدوسري", bio="تاجر تجزئة وعضو لجنة التجار بوسط المدينة.", persona="يبحث عن التوازن بين تخفيف الزحام وسهولة وصول الزبائن والتوريد.", karma=1890, friend_count=260, follower_count=3100, statuses_count=180, age=49, gender="male", mbti="ESTJ", country="العالم العربي", profession="صاحب متاجر تجزئة", interested_topics=["التجارة المحلية", "الخدمات اللوجستية"], source_entity_uuid="n4", source_entity_type="صاحب_متجر", created_at=now_iso),
        OasisAgentProfile(user_id=4, user_name="barq_logistics", name="منصة برق للتوصيل", bio="الحساب الرسمي لقطاع العمليات في منصة برق للتوصيل.", persona="يطالب بإعفاء كامل لأسطول الدراجات والسيارات الكهربائية التجارية.", karma=2750, friend_count=140, follower_count=24000, statuses_count=520, age=35, gender="other", mbti="ENTJ", country="العالم العربي", profession="شركة خدمات لوجستية", interested_topics=["التوصيل السريع", "الأساطيل الكهربائية"], source_entity_uuid="n5", source_entity_type="شركة_لوجستية", created_at=now_iso),
        OasisAgentProfile(user_id=5, user_name="yousef_tech", name="يوسف الكناني", bio="صحفي تقني وصانع محتوى متخصص في المدن الذكية.", persona="ينقل التجارب العالمية ويدير استطلاعات رأي تفاعلية.", karma=5600, friend_count=510, follower_count=42000, statuses_count=1290, age=29, gender="male", mbti="ENFP", country="العالم العربي", profession="صحفي تقني", interested_topics=["المدن الذكية", "الرأي العام"], source_entity_uuid="n7", source_entity_type="صحفي_تقني", created_at=now_iso),
    ]

    with open(os.path.join(sim_dir, "reddit_profiles.json"), "w", encoding="utf-8") as f:
        json.dump([p.to_reddit_format() for p in profiles_data], f, ensure_ascii=False, indent=2)

    tw_rows = [p.to_twitter_format() for p in profiles_data]
    with open(os.path.join(sim_dir, "twitter_profiles.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(tw_rows[0].keys()))
        writer.writeheader()
        for row in tw_rows:
            writer.writerow(row)

    sim_config = {
        "simulation_id": sim_id,
        "project_id": proj_id,
        "graph_id": graph_id,
        "simulation_requirement": sim_req,
        "time_config": {"total_simulation_hours": 48, "minutes_per_round": 60, "agents_per_hour_min": 3, "agents_per_hour_max": 6, "peak_hours": [8, 9, 19, 20, 21], "off_peak_hours": [1, 2, 3, 4, 5], "morning_hours": [6, 7, 8], "work_hours": [9, 10, 11, 12, 13, 14, 15, 16]},
        "agent_configs": [{"agent_id": p.user_id, "entity_uuid": p.source_entity_uuid, "entity_name": p.name, "entity_type": p.source_entity_type, "activity_level": 0.82, "posts_per_hour": 0.6, "comments_per_hour": 1.4, "active_hours": [8, 9, 13, 19, 20, 21], "response_delay_min": 5, "response_delay_max": 25, "sentiment_bias": 0.15, "stance": "متوازن وتحليلي", "influence_weight": 1.4} for p in profiles_data],
        "event_config": {"initial_posts": [{"poster_agent_id": 5, "platform": "twitter", "content": "الإعلان عن مبادرة النقل الذكي 2027.. حافلات كهربائية كل 6 دقائق ومنحة 35% للطاقة الشمسية المنزلية."}], "scheduled_events": [], "hot_topics": ["#النقل_الذكي_2027", "#الطاقة_الشمسية_المنزلية", "#تعرفة_الذروة"], "narrative_direction": "تفاعل يبدأ بقلق المتنقلين من رسوم الذروة، ثم يتحول نحو المطالبة بفترة تجريبية للحافلات الكهربائية مع ترحيب واسع بمنحة الطاقة الشمسية."},
        "twitter_config": {"platform": "twitter", "recency_weight": 0.45, "popularity_weight": 0.35, "relevance_weight": 0.20, "viral_threshold": 10, "echo_chamber_strength": 0.45},
        "reddit_config": {"platform": "reddit", "recency_weight": 0.30, "popularity_weight": 0.35, "relevance_weight": 0.35, "viral_threshold": 12, "echo_chamber_strength": 0.35},
        "llm_model": "Istishraf-Engine",
        "llm_base_url": "https://api.openai.com/v1",
        "generated_at": now_iso,
        "generation_reasoning": "توزيع متوازن لساعات الذروة الصباحية والمسائية لمحاكاة أوقات التنقل ونقاشات المساء.",
    }
    with open(os.path.join(sim_dir, "simulation_config.json"), "w", encoding="utf-8") as f:
        json.dump(sim_config, f, ensure_ascii=False, indent=2)

    sim_state = SimulationState(
        simulation_id=sim_id, project_id=proj_id, graph_id=graph_id, enable_twitter=True, enable_reddit=True,
        status=SimulationStatus.COMPLETED, entities_count=8, profiles_count=len(profiles_data),
        entity_types=["جهة_حكومية", "خبير_اقتصادي", "رائدة_أعمال", "صاحب_متجر", "شركة_لوجستية", "مواطنة_موظفة", "صحفي_تقني"],
        profiles_generated=True, config_generated=True, config_reasoning=sim_config["generation_reasoning"],
        current_round=24, twitter_status="completed", reddit_status="completed", created_at=now_iso, updated_at=now_iso,
    )
    with open(os.path.join(sim_dir, "state.json"), "w", encoding="utf-8") as f:
        json.dump(sim_state.to_dict(), f, ensure_ascii=False, indent=2)

    with open(os.path.join(sim_dir, "run_state.json"), "w", encoding="utf-8") as f:
        json.dump({"simulation_id": sim_id, "runner_status": "completed", "current_round": 24, "total_rounds": 24, "simulated_hours": 24, "total_simulation_hours": 48, "twitter_running": False, "reddit_running": False, "twitter_actions_count": 68, "reddit_actions_count": 54, "total_actions_count": 122, "started_at": "2026-11-12T08:35:00", "completed_at": "2026-11-12T08:55:00"}, f, ensure_ascii=False, indent=2)

    sec1_title = "1. الملخص التنفيذي واتجاهات الرأي العام"
    sec1_body = f"## {sec1_title}\n\nأظهرت المحاكاة المتوازية على مدار **24 جولة زمنية** تأييداً مشروطاً بنسبة **68%** مقابل تحفّظ عملي بنسبة **32%**، حيث حصدت منحة الـ **35% للطاقة الشمسية المنزلية** قبولاً بنسبة **84%** بينما تركزت التحفظات حول توقيت بدء تعرفة الذروة.\n\n"
    sec2_title = "2. تحليل مواقف الشرائح الفاعلة خلال المحاكاة"
    sec2_body = f"## {sec2_title}\n\nأبدى الموظفون استعداداً للتحول للنقل العام بشرط توفير مواقف مجانية عند المحطات، بينما طالبت شركات التوصيل والمتاجر بإعفاء المركبات الكهربائية التجارية من رسوم الذروة لمنع ارتفاع تكاليف التوصيل.\n\n"
    sec3_title = "3. المخاطر المتوقعة والتوصيات الاستراتيجية لصنّاع القرار"
    sec3_body = f"## {sec3_title}\n\nيوصي محرك **استشراف المستقبل** بتطبيق فترة تجريبية مجانية للحافلات الكهربائية لمدة **90 يوماً** قبل تفعيل رسوم الذروة، مع إعفاء أساطيل التوصيل الخضراء، مما يرفع القبول المتوقع إلى **89%**.\n"

    outline = ReportOutline(
        title="التقرير التنبؤي لمحاكاة مبادرة النقل الذكي والطاقة النظيفة 2027",
        summary="استشراف تفاعلات الرأي العام والقطاعات الاقتصادية تجاه حزمة النقل الكهربائي الذكي والتعرفة المرنة ومنح الطاقة الشمسية.",
        sections=[ReportSection(title=sec1_title, content=sec1_body), ReportSection(title=sec2_title, content=sec2_body), ReportSection(title=sec3_title, content=sec3_body)],
    )
    full_md = f"# {outline.title}\n\n> {outline.summary}\n\n---\n\n{sec1_body}\n{sec2_body}\n{sec3_body}"
    report = Report(report_id=report_id, simulation_id=sim_id, graph_id=graph_id, simulation_requirement=sim_req, status=ReportStatus.COMPLETED, outline=outline, markdown_content=full_md, created_at=now_iso, completed_at="2026-11-12T09:00:00")
    ReportManager.save_report(report)
    rep_folder = ReportManager._ensure_report_folder(report_id)
    for idx, body in enumerate([sec1_body, sec2_body, sec3_body], start=1):
        with open(os.path.join(rep_folder, f"section_{idx:02d}.md"), "w", encoding="utf-8") as f:
            f.write(body)
    ReportManager.update_progress(report_id=report_id, status="completed", progress=100, message="اكتمل توليد التقرير التنبؤي بنجاح", current_section=None, completed_sections=[sec1_title, sec2_title, sec3_title])
