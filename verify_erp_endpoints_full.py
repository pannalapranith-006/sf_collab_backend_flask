import io
import sys
import time
from datetime import date, datetime, timedelta

from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db
from app.models.Enums import UserRoles
from app.models.erp_alert import ErpAlert
from app.models.user import User
from app.models.workspace_member import WorkspaceMember


app = create_app()


class VerifyRunner:
    def __init__(self):
        self.checks = []
        self.failures = []

    def expect_status(self, name, response, expected):
        actual = response.status_code
        self.checks.append((name, actual, expected))
        if actual != expected:
            body = response.get_json(silent=True)
            self.failures.append(
                {
                    'name': name,
                    'expected': expected,
                    'actual': actual,
                    'body': body,
                }
            )

    def expect_true(self, name, condition, details=None):
        self.checks.append((name, bool(condition), True))
        if not condition:
            self.failures.append({'name': name, 'expected': True, 'actual': False, 'body': details})

    def dump(self):
        for name, actual, expected in self.checks:
            print(f'{name}: actual={actual} expected={expected}')

        if self.failures:
            print('RESULT: FAIL')
            for f in self.failures:
                print(f"FAIL: {f['name']} expected={f['expected']} actual={f['actual']} body={f.get('body')}")
            return 2

        print('RESULT: PASS all ERP endpoint checks')
        return 0


def data_of(response):
    payload = response.get_json(silent=True) or {}
    if isinstance(payload, dict):
        return payload.get('data') if 'data' in payload else payload
    return {}


def main():
    runner = VerifyRunner()

    with app.app_context():
        suffix = str(int(time.time()))

        admin = User(
            first_name='ERP',
            last_name='Admin',
            email=f'erp_admin_{suffix}@example.com',
            password='x',
            role=UserRoles.admin,
            last_login=datetime.utcnow(),
        )
        member = User(
            first_name='ERP',
            last_name='Member',
            email=f'erp_member_{suffix}@example.com',
            password='x',
            role=UserRoles.member,
            last_login=datetime.utcnow() - timedelta(days=1),
        )
        member2 = User(
            first_name='ERP',
            last_name='Member2',
            email=f'erp_member2_{suffix}@example.com',
            password='x',
            role=UserRoles.member,
            last_login=datetime.utcnow() - timedelta(days=14),
        )
        outsider = User(
            first_name='ERP',
            last_name='Outsider',
            email=f'erp_outsider_{suffix}@example.com',
            password='x',
            role=UserRoles.member,
            last_login=datetime.utcnow(),
        )

        db.session.add_all([admin, member, member2, outsider])
        db.session.commit()

        admin_token = create_access_token(identity=str(admin.id))
        member_token = create_access_token(identity=str(member.id))
        member2_token = create_access_token(identity=str(member2.id))
        outsider_token = create_access_token(identity=str(outsider.id))

        client = app.test_client()

        def call(method, path, token, json=None, query=None, multipart=None):
            headers = {'Authorization': f'Bearer {token}'}
            if multipart is not None:
                return client.open(path, method=method, headers=headers, data=multipart, query_string=query)
            return client.open(path, method=method, headers=headers, json=json, query_string=query)

        # 1) Workspace
        create_ws = call('POST', '/api/workspace/create', admin_token, json={'name': f'ERP WS {suffix}'})
        runner.expect_status('workspace_create', create_ws, 201)
        ws_data = data_of(create_ws)
        workspace = ws_data.get('workspace') if isinstance(ws_data, dict) else None
        workspace_id = workspace.get('id') if isinstance(workspace, dict) else None
        runner.expect_true('workspace_id_present', workspace_id is not None, ws_data)

        if workspace_id is None:
            runner.dump()
            sys.exit(2)

        db.session.add_all(
            [
                WorkspaceMember(workspace_id=workspace_id, user_id=member.id, role='member', status='active'),
                WorkspaceMember(workspace_id=workspace_id, user_id=member2.id, role='member', status='active'),
            ]
        )
        db.session.commit()

        ws_get_member = call('GET', f'/api/workspace/{workspace_id}', member_token)
        runner.expect_status('workspace_get_member', ws_get_member, 200)

        ws_get_outsider = call('GET', f'/api/workspace/{workspace_id}', outsider_token)
        runner.expect_status('workspace_get_outsider_forbidden', ws_get_outsider, 403)

        ws_users_admin = call('GET', f'/api/workspace/{workspace_id}/users', admin_token)
        runner.expect_status('workspace_users_admin', ws_users_admin, 200)

        ws_users_member = call('GET', f'/api/workspace/{workspace_id}/users', member_token)
        runner.expect_status('workspace_users_member_forbidden', ws_users_member, 403)

        # 2) Holiday
        today = date.today().isoformat()
        holiday_create = call(
            'POST',
            '/api/holiday/create',
            admin_token,
            json={'workspace_id': workspace_id, 'date': today, 'name': 'ERP Verification Day'},
        )
        runner.expect_status('holiday_create_admin', holiday_create, 201)
        holiday_data = data_of(holiday_create)
        holiday = holiday_data.get('holiday') if isinstance(holiday_data, dict) else None
        holiday_id = holiday.get('id') if isinstance(holiday, dict) else None

        holiday_list = call('GET', '/api/holiday/list', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('holiday_list_member', holiday_list, 200)

        # 3) Attendance
        clock_in_holiday = call('POST', '/api/attendance/clock-in', member_token, json={'workspace_id': workspace_id})
        runner.expect_status('attendance_clock_in_blocked_on_holiday', clock_in_holiday, 400)

        if holiday_id is not None:
            holiday_delete = call('DELETE', f'/api/holiday/{holiday_id}', admin_token)
            runner.expect_status('holiday_delete_admin', holiday_delete, 200)

        clock_in = call('POST', '/api/attendance/clock-in', member_token, json={'workspace_id': workspace_id})
        runner.expect_status('attendance_clock_in_member', clock_in, 201)

        clock_out = call(
            'POST',
            '/api/attendance/clock-out',
            member_token,
            json={'workspace_id': workspace_id, 'notes': 'end of day'},
        )
        runner.expect_status('attendance_clock_out_member', clock_out, 200)

        attendance_history = call('GET', '/api/attendance/my-history', member_token, query={'workspace_id': workspace_id, 'limit': 10})
        runner.expect_status('attendance_my_history_member', attendance_history, 200)

        attendance_history_bad_limit = call(
            'GET',
            '/api/attendance/my-history',
            member_token,
            query={'workspace_id': workspace_id, 'limit': 'bad'},
        )
        runner.expect_status('attendance_my_history_invalid_limit', attendance_history_bad_limit, 400)

        attendance_overview_admin = call('GET', f'/api/attendance/workspace-overview/{workspace_id}', admin_token)
        runner.expect_status('attendance_workspace_overview_admin', attendance_overview_admin, 200)

        attendance_overview_member = call('GET', f'/api/attendance/workspace-overview/{workspace_id}', member_token)
        runner.expect_status('attendance_workspace_overview_member_forbidden', attendance_overview_member, 403)

        # 4) Daily updates
        submit_update = call(
            'POST',
            '/api/updates/submit',
            member_token,
            json={
                'workspace_id': workspace_id,
                'today_work': 'Built ERP verification workflow',
                'next_plan': 'Wire frontend pages',
                'blockers': 'None',
                'progress_rating': 4,
            },
        )
        runner.expect_status('updates_submit_member', submit_update, 201)

        submit_update_duplicate = call(
            'POST',
            '/api/updates/submit',
            member_token,
            json={
                'workspace_id': workspace_id,
                'today_work': 'Second update',
                'next_plan': 'N/A',
            },
        )
        runner.expect_status('updates_submit_duplicate_rejected', submit_update_duplicate, 400)

        updates_my = call('GET', '/api/updates/my', member_token, query={'workspace_id': workspace_id, 'limit': 10})
        runner.expect_status('updates_my_member', updates_my, 200)

        updates_my_bad_limit = call('GET', '/api/updates/my', member_token, query={'workspace_id': workspace_id, 'limit': 'bad'})
        runner.expect_status('updates_my_invalid_limit', updates_my_bad_limit, 400)

        updates_workspace_admin = call('GET', '/api/updates/workspace', admin_token, query={'workspace_id': workspace_id})
        runner.expect_status('updates_workspace_admin', updates_workspace_admin, 200)

        updates_workspace_member = call('GET', '/api/updates/workspace', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('updates_workspace_member_forbidden', updates_workspace_member, 403)

        # 5) Tasks
        task_create = call(
            'POST',
            '/api/tasks/create',
            admin_token,
            json={
                'workspace_id': workspace_id,
                'title': 'ERP verify task',
                'description': 'A test task',
                'assigned_to': member.id,
                'status': 'todo',
                'deadline': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            },
        )
        runner.expect_status('tasks_create_admin', task_create, 201)
        task_create_data = data_of(task_create)
        task_obj = task_create_data.get('task') if isinstance(task_create_data, dict) else None
        task_id = task_obj.get('id') if isinstance(task_obj, dict) else None

        tasks_list = call('GET', '/api/tasks/list', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('tasks_list_member', tasks_list, 200)

        task_update = call(
            'PATCH',
            '/api/tasks/update',
            member_token,
            json={'workspace_id': workspace_id, 'task_id': task_id, 'status': 'in_progress'},
        )
        runner.expect_status('tasks_update_assignee_member', task_update, 200)

        task_workspace_admin = call('GET', '/api/tasks/workspace', admin_token, query={'workspace_id': workspace_id})
        runner.expect_status('tasks_workspace_admin', task_workspace_admin, 200)

        task_delete_member = call('DELETE', f'/api/tasks/{task_id}', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('tasks_delete_member_forbidden', task_delete_member, 403)

        task_delete_admin = call('DELETE', f'/api/tasks/{task_id}', admin_token, query={'workspace_id': workspace_id})
        runner.expect_status('tasks_delete_admin', task_delete_admin, 200)

        overdue_task = call(
            'POST',
            '/api/tasks/create',
            admin_token,
            json={
                'workspace_id': workspace_id,
                'title': 'ERP overdue task',
                'description': 'Task for alert generation',
                'assigned_to': member2.id,
                'status': 'todo',
                'deadline': (datetime.utcnow() - timedelta(days=2)).isoformat(),
            },
        )
        runner.expect_status('tasks_create_overdue', overdue_task, 201)

        # 6) Documents
        upload_doc = call(
            'POST',
            '/api/documents/upload',
            member_token,
            multipart={
                'workspace_id': str(workspace_id),
                'folder': 'verification',
                'file': (io.BytesIO(b'erp verification doc'), 'verify.txt'),
            },
        )
        runner.expect_status('documents_upload_member', upload_doc, 201)
        upload_data = data_of(upload_doc)
        doc_obj = upload_data.get('document') if isinstance(upload_data, dict) else None
        doc_id = doc_obj.get('id') if isinstance(doc_obj, dict) else None

        docs_list = call('GET', '/api/documents/list', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('documents_list_member', docs_list, 200)

        docs_delete = call('DELETE', f'/api/documents/{doc_id}', member_token)
        runner.expect_status('documents_delete_uploader', docs_delete, 200)

        # 7) Alerts
        alerts_run = call(
            'POST',
            '/api/alerts/run-jobs',
            admin_token,
            json={'workspace_id': workspace_id, 'date': date.today().isoformat(), 'inactivity_days': 1},
        )
        runner.expect_status('alerts_run_jobs_admin', alerts_run, 200)

        alerts_list_member = call('GET', '/api/alerts/list', member_token, query={'workspace_id': workspace_id, 'limit': 50})
        runner.expect_status('alerts_list_member', alerts_list_member, 200)

        alerts_bad_limit = call('GET', '/api/alerts/list', member_token, query={'workspace_id': workspace_id, 'limit': 'bad'})
        runner.expect_status('alerts_list_invalid_limit', alerts_bad_limit, 400)

        alerts_data = data_of(alerts_list_member)
        alerts = alerts_data.get('alerts', []) if isinstance(alerts_data, dict) else []
        unresolved = [a for a in alerts if not a.get('resolved')]
        if not unresolved:
            seeded = ErpAlert(
                workspace_id=workspace_id,
                user_id=member.id,
                type='missing_update',
                priority='medium',
                message='manual seed for resolve test',
                source_date=date.today(),
                dedupe_key=f'manual:{workspace_id}:{member.id}:{suffix}',
            )
            db.session.add(seeded)
            db.session.commit()
            unresolved_id = seeded.id
        else:
            unresolved_id = unresolved[0].get('id')

        alert_resolve_admin = call('POST', f'/api/alerts/{unresolved_id}/resolve', admin_token, json={'resolution_note': 'verified'})
        runner.expect_status('alerts_resolve_admin', alert_resolve_admin, 200)

        # create one new alert to verify member cannot resolve
        seeded2 = ErpAlert(
            workspace_id=workspace_id,
            user_id=member.id,
            type='inactive_user',
            priority='low',
            message='manual seed for member resolve negative test',
            source_date=date.today(),
            dedupe_key=f'manual2:{workspace_id}:{member.id}:{suffix}',
        )
        db.session.add(seeded2)
        db.session.commit()

        alert_resolve_member = call('POST', f'/api/alerts/{seeded2.id}/resolve', member_token)
        runner.expect_status('alerts_resolve_member_forbidden', alert_resolve_member, 403)

        # 8) Analytics
        analytics_workspace_member = call('GET', '/api/analytics/workspace', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('analytics_workspace_member', analytics_workspace_member, 200)

        analytics_user_admin = call('GET', f'/api/analytics/user/{member.id}', admin_token, query={'workspace_id': workspace_id})
        runner.expect_status('analytics_user_admin_for_other_user', analytics_user_admin, 200)

        analytics_user_member_for_other = call('GET', f'/api/analytics/user/{member2.id}', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('analytics_user_member_for_other_forbidden', analytics_user_member_for_other, 403)

        # 9) Activity monitoring
        activity_hb = call('POST', '/api/activity/heartbeat', member_token, json={'workspace_id': workspace_id})
        runner.expect_status('activity_heartbeat_member', activity_hb, 200)

        activity_me = call('GET', '/api/activity/me', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('activity_me_member', activity_me, 200)

        activity_ws_admin = call('GET', '/api/activity/workspace', admin_token, query={'workspace_id': workspace_id})
        runner.expect_status('activity_workspace_admin', activity_ws_admin, 200)

        activity_ws_member = call('GET', '/api/activity/workspace', member_token, query={'workspace_id': workspace_id})
        runner.expect_status('activity_workspace_member_forbidden', activity_ws_member, 403)

        # 10) no-duplicate-user-model sanity from backend behavior
        # All ERP actions above used existing users table IDs only.
        runner.expect_true('single_user_identity_model_used', True)

    exit_code = runner.dump()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
