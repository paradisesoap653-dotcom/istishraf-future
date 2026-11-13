"""
حراسة مسارات الـAPI لتطبيق «استشراف المستقبل».

الأهداف:
1. منع أي وصول مجهول إلى مسارات المشاريع والمحاكاة والتقارير.
2. عزل الموارد بين المستخدمين: لا يقرأ مستخدم موردًا يملكه غيره (404 لا 403
   حتى لا نكشف وجود المورد).
3. إبقاء الموارد التجريبية (demo) متاحة للعرض العام للقراءة فقط.

قاعدة تصميمية مهمة: لا تعتمد هذه الحراسة إطلاقًا على ``UserStore.count_users()``.
الاعتماد السابق على عدد المستخدمين كان يعني أن أي نسخة serverless بقاعدة
مؤقتة فارغة (وهو الوضع الافتراضي بعد كل cold start) تصبح مفتوحة بالكامل
للزوار المجهولين، بما في ذلك تغيير إعدادات مزوّد الذكاء الاصطناعي.
"""

from __future__ import annotations

from flask import current_app, jsonify, request

from ..models.user import UserStore, get_current_user

# موارد العرض التجريبي: قراءة عامة مسموحة، والكتابة تبقى محمية.
DEMO_ID_PREFIXES = (
    "proj_demo_",
    "graph_demo_",
    "sim_demo_",
    "report_demo_",
)

# اسم الوسيط في المسار/الجسم -> نوع المورد في جدول الملكية.
RESOURCE_ARGS = {
    "project_id": "project",
    "simulation_id": "simulation",
    "report_id": "report",
}


def _request_resource_ids() -> dict:
    """اجمع معرّفات الموارد من مسار الطلب ومن جسم JSON."""
    values = dict(request.view_args or {})

    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            for key in ("project_id", "simulation_id", "report_id", "graph_id"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    values.setdefault(key, value.strip())
    return values


def _is_demo_id(value) -> bool:
    return isinstance(value, str) and value.startswith(DEMO_ID_PREFIXES)


def _is_demo_request(values: dict) -> bool:
    return any(_is_demo_id(v) for v in values.values())


def _graph_owner_ids(graph_id: str) -> set:
    """مالكو المشاريع المرتبطة بهذا الرسم المعرفي."""
    try:
        from ..models.project import ProjectManager

        projects = ProjectManager.find_projects_by_graph_id(graph_id)
    except Exception:  # pragma: no cover - قراءة المشاريع قد تفشل قبل التهيئة
        return set()

    owners = set()
    for project in projects:
        owner_id = UserStore.get_owner_id("project", project.project_id)
        if owner_id is not None:
            owners.add(int(owner_id))
    return owners


def _user_can_access(user: dict, values: dict) -> bool:
    """تحقق من ملكية كل مورد مُشار إليه في الطلب."""
    if user.get("role") == "admin":
        return True

    user_id = int(user.get("id"))

    for arg_name, resource_type in RESOURCE_ARGS.items():
        resource_id = values.get(arg_name)
        if not isinstance(resource_id, str) or not resource_id:
            continue
        if _is_demo_id(resource_id):
            continue
        owner_id = UserStore.get_owner_id(resource_type, resource_id)
        if owner_id is None:
            # تقرير قديم بلا سجل ملكية يرث مالك محاكاته
            from ..models.user import _inherited_owner_id

            owner_id = _inherited_owner_id(resource_type, resource_id)
        # مورد بلا سجل ملكية = مورد عام/قديم؛ يبقى السلوك كما هو (متاح)،
        # لكن كل مورد يُنشأ بعد هذا الإصلاح يُسجّل مالكه.
        if owner_id is None:
            continue
        if int(owner_id) != user_id:
            return False

    graph_id = values.get("graph_id")
    if isinstance(graph_id, str) and graph_id and not _is_demo_id(graph_id):
        owners = _graph_owner_ids(graph_id)
        if owners and int(user_id) not in owners:
            return False

    return True


def _enforce_auth_in_testing() -> bool:
    return bool(current_app.config.get("ENFORCE_AUTH_IN_TESTING"))


def guard_api_request():
    """before_request مشترك لكل أزرقية (blueprint) خاصة بالـAPI."""
    if request.method == "OPTIONS":
        return None

    values = _request_resource_ids()
    user = get_current_user()

    if user is None:
        # اختبارات الوحدة القديمة تستدعي المسارات بلا هوية؛ نحافظ على ذلك
        # إلا إذا فُعّل الإعداد صراحةً.
        if current_app.testing and not _enforce_auth_in_testing():
            return None
        if request.method == "GET" and _is_demo_request(values):
            return None
        return (
            jsonify(
                {
                    "success": False,
                    "code": "auth_required",
                    "error": "مطلوب تسجيل الدخول للوصول إلى هذه الخدمة",
                }
            ),
            401,
        )

    if not _user_can_access(user, values):
        return (
            jsonify({"success": False, "code": "not_found", "error": "المورد غير موجود"}),
            404,
        )

    return None


def install_api_guards(*blueprints) -> None:
    """تثبيت الحراسة على أزرقيات الـAPI دفعة واحدة."""
    for blueprint in blueprints:
        blueprint.before_request(guard_api_request)


def filter_owned(items, resource_type: str, id_key: str, user) -> list:
    """احتفظ فقط بالموارد التي يملكها المستخدم (أو موارد عامة بلا مالك).

    تُستخدم في مسارات القوائم التي كانت تُرجع كل موارد كل المستخدمين.
    """
    from ..models.user import UserStore as _Users

    if not user:
        return []
    if user.get("role") == "admin":
        return list(items)

    kept = []
    for item in items:
        if isinstance(item, dict):
            resource_id = item.get(id_key)
        else:
            resource_id = getattr(item, id_key, None)
        if not resource_id:
            kept.append(item)
            continue
        if _Users.can_access(resource_type, str(resource_id), user):
            kept.append(item)
    return kept
