"""
مسارات المصادقة وحسابات المستخدمين لتطبيق «استشراف المستقبل»
"""

from flask import Blueprint, request, jsonify
from ..models.user import UserStore, issue_auth_token, get_current_user

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    try:
        user = UserStore.create_user(
            name=data.get('name', ''),
            email=data.get('email', ''),
            password=data.get('password', ''),
        )
        token = issue_auth_token(user)
        used_today = UserStore.count_today_usage(user['id'])
        return jsonify({
            'success': True,
            'data': {
                'token': token,
                'user': {
                    **user,
                    'used_today': used_today,
                }
            }
        })
    except ValueError as err:
        return jsonify({'success': False, 'error': str(err)}), 400
    except Exception as err:
        return jsonify({'success': False, 'error': f'تعذر إنشاء الحساب: {err}'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    try:
        user = UserStore.authenticate(
            email=data.get('email', ''),
            password=data.get('password', ''),
        )
    except PermissionError:
        return jsonify({
            'success': False,
            'code': 'account_disabled',
            'error': 'هذا الحساب موقوف من قبل الإدارة. تواصل مع مدير المنصة.',
        }), 403
    if not user:
        return jsonify({
            'success': False,
            'error': 'البريد الإلكتروني أو كلمة المرور غير صحيحة'
        }), 401

    token = issue_auth_token(user)
    used_today = UserStore.count_today_usage(user['id'])
    return jsonify({
        'success': True,
        'data': {
            'token': token,
            'user': {
                **user,
                'used_today': used_today,
            }
        }
    })


def _first_registration_becomes_admin() -> bool:
    """هل سيصبح أول مسجّل مديرًا فعلًا؟

    يصبح كذلك فقط إذا لم يكن ADMIN_EMAIL مضبوطًا؛ وإن كان مضبوطًا فالإدارة
    محصورة بذلك البريد، وإخبار الزائر بالعكس مضلّل.
    """
    import os
    if (os.environ.get('ADMIN_EMAIL') or '').strip():
        return False
    return UserStore.count_users() == 0


@auth_bp.route('/me', methods=['GET'])
def me():
    user = get_current_user()
    if not user:
        return jsonify({
            'success': True,
            'data': {
                'authenticated': False,
                'user': None,
                'first_user_becomes_admin': _first_registration_becomes_admin(),
            }
        })

    used_today = UserStore.count_today_usage(user['id'])
    return jsonify({
        'success': True,
        'data': {
            'authenticated': True,
            'user': {
                **user,
                'used_today': used_today,
            },
            'first_user_becomes_admin': False,
        }
    })


@auth_bp.route('/users', methods=['GET'])
def list_all_users():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح لك بعرض قائمة المستخدمين'}), 403
    users = []
    for row in UserStore.list_users():
        try:
            used = UserStore.count_today_usage(int(row['id']))
        except Exception:
            used = 0
        users.append({**row, 'used_today': used})

    return jsonify({
        'success': True,
        'data': {
            'users': users,
            'current_user_id': int(user['id']),
        }
    })


def _admin_guard():
    """يرفض غير المدير، ويعيد (user, response) — response=None عند السماح."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return None, (
            jsonify({'success': False, 'error': 'هذه العملية للمدير فقط'}),
            403,
        )
    return user, None


def _target_user(user_id: int):
    target = UserStore.get_user_by_id(int(user_id))
    if not target:
        return None, (jsonify({'success': False, 'error': 'المستخدم غير موجود'}), 404)
    return target, None


@auth_bp.route('/users/<int:user_id>/status', methods=['POST'])
def set_user_status(user_id: int):
    """إيقاف أو تفعيل حساب."""
    from ..models.user import admin_set_active

    admin, err = _admin_guard()
    if err:
        return err

    target, err = _target_user(user_id)
    if err:
        return err

    if int(target['id']) == int(admin['id']):
        return jsonify({
            'success': False,
            'error': 'لا يمكنك إيقاف حسابك أنت — اطلب من مدير آخر فعل ذلك',
        }), 400

    if target.get('role') == 'admin' and target.get('is_active', True):
        from ..models.user import admin_count_admins

        if admin_count_admins() <= 1:
            return jsonify({
                'success': False,
                'error': 'لا يمكن إيقاف آخر مدير في المنصة',
            }), 400

    data = request.get_json(silent=True) or {}
    active = bool(data.get('active', True))
    if not admin_set_active(target['id'], active):
        return jsonify({'success': False, 'error': 'تعذر تحديث الحساب'}), 500

    return jsonify({
        'success': True,
        'data': {'user_id': int(target['id']), 'is_active': active},
        'message': 'تم تفعيل الحساب' if active else 'تم إيقاف الحساب',
    })


@auth_bp.route('/users/<int:user_id>/quota', methods=['POST'])
def set_user_quota(user_id: int):
    """تعديل الحصة اليومية (عدد المحاكاات)."""
    from ..models.user import admin_set_quota

    admin, err = _admin_guard()
    if err:
        return err

    target, err = _target_user(user_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    try:
        quota = int(data.get('daily_quota'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'أدخل رقمًا صحيحًا للحصة'}), 400
    if quota < 1 or quota > 1000:
        return jsonify({'success': False, 'error': 'الحصة بين 1 و1000'}), 400

    if not admin_set_quota(target['id'], quota):
        return jsonify({'success': False, 'error': 'تعذر تحديث الحصة'}), 500

    return jsonify({
        'success': True,
        'data': {'user_id': int(target['id']), 'daily_quota': quota},
        'message': f'صارت الحصة اليومية {quota}',
    })


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id: int):
    """حذف حساب نهائيًا (تبقى موارده في قاعدة البيانات للمدير)."""
    from ..models.user import admin_count_admins, admin_delete_user

    admin, err = _admin_guard()
    if err:
        return err

    target, err = _target_user(user_id)
    if err:
        return err

    if int(target['id']) == int(admin['id']):
        return jsonify({'success': False, 'error': 'لا يمكنك حذف حسابك أنت'}), 400

    if target.get('role') == 'admin' and admin_count_admins() <= 1:
        return jsonify({
            'success': False,
            'error': 'لا يمكن حذف آخر مدير في المنصة',
        }), 400

    if not admin_delete_user(target['id']):
        return jsonify({'success': False, 'error': 'تعذر حذف الحساب'}), 500

    return jsonify({
        'success': True,
        'data': {'user_id': int(target['id'])},
        'message': 'تم حذف الحساب',
    })
