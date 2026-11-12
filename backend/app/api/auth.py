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
    user = UserStore.authenticate(
        email=data.get('email', ''),
        password=data.get('password', ''),
    )
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
    return jsonify({
        'success': True,
        'data': {
            'users': UserStore.list_users()
        }
    })
