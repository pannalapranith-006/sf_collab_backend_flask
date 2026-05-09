"""
SF Collab Task Routes
Updated with notification triggers for task events
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from app.models.task import Task
from app.models.user import User
from app.models.startUpMember import StartupMember
from app.services.achievement_service import AchievementService
from app.extensions import db
from app.utils.helper import error_response, success_response, paginate
from app.utils.plans_utils import can_create_task_or_milestone
# ===== NOTIFICATION IMPORTS =====
from app.notifications.helpers import (
    notify_task_assigned,
    notify_task_updated,
    notify_task_completed,
    notify_task_overdue,
    notify_task_reassigned,
    notify_task_deadline_approaching
)

tasks_bp = Blueprint('tasks', __name__)


def has_startup_access(user_id, startup_id):
    """Check if user has access to startup data"""
    current_user = User.query.get(user_id)
    if current_user and current_user.role == 'admin':
        return True
    
    membership = StartupMember.query.filter_by(
        user_id=user_id, 
        startup_id=startup_id
    ).first()
    
    return membership is not None

def has_task_visibility_access(user_id, task):
    """Check if user has visibility access to task based on visibility settings"""
    # Admin always has access
    if task.parent_startup.creator_id == int(user_id):
        return True
    # Owner always has access

    if int(task.user_id) == int(user_id):
        return True

    # Assigned user always has access
    if task.assigned_to == int(user_id):
        return True
    
    # Check visibility settings
    if task.visible_by == 'private':
        return False
    
    if task.visible_by == 'team' and task.startup_id:
        # Check if user is part of the startup team
        return is_user_on_startup_team(user_id, task.startup_id)
    
    if task.visible_by == 'all' or task.visible_by == 'public':
        return True
    
    return False
def is_user_on_startup_team(user_id, startup_id):
    """Check if user is a member of the startup team"""
    
    membership = StartupMember.query.filter_by(
        user_id=user_id,
        startup_id=startup_id
    ).first()
    return membership is not None
def get_user_full_name(user_id):
    """Get user's full name"""
    user = User.query.get(user_id)
    if user:
        return f"{user.first_name} {user.last_name}"
    return "Unknown User"


@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """Get all tasks with filtering"""
    current_user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    user_id = request.args.get('user_id', type=int) # This can be other user's ID to check their tasks
    startup_id = request.args.get('startup_id', type=int)
    status = request.args.get('status', type=str)

    priority = request.args.get('priority', type=str)
    search = request.args.get('search', type=str)
    assigned_to = request.args.get('assigned_to', type=int)
    show_overdue_only = request.args.get('show_overdue_only', 'false').lower() == 'true'
    
    if not user_id:
        user_id = current_user_id

    query = None
    if startup_id:
        query = Task.query.filter(
            Task.startup_id == startup_id
        )
    else:
        query = Task.query.filter(
            (Task.user_id == user_id) | (Task.assigned_to == user_id)
        )
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))
    if status and status != 'all':
        query = query.filter(Task.status == status)
    if priority and priority != 'all':
        query = query.filter(Task.priority == priority)
    if assigned_to and assigned_to != 'all':
        query = query.filter(Task.assigned_to == assigned_to)
    if show_overdue_only:
        query = query.filter(Task.due_date < datetime.utcnow(), Task.status != 'completed')
    paginated = paginate(
        query.order_by(Task.created_at.desc()),
        page,
        per_page
    )
    # visible_tasks = [
    #     task for task in paginated['items']
    #     if has_task_visibility_access(current_user_id, task)
    # ]
    filtered_tasks = []
    for task in paginated['items']:
        if has_task_visibility_access(current_user_id, task):
            filtered_tasks.append(task)

    return success_response({
        'tasks': [task.to_dict() for task in filtered_tasks],
        'pagination': {
            'page': paginated['page'],
            'per_page': paginated['per_page'],
            'total': paginated['total'],
            'pages': paginated['pages']
        }
    })



@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """Get single task by ID"""
    current_user_id = get_jwt_identity()
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    if task.user_id != int(current_user_id):
        if task.startup_id:
            if not has_startup_access(int(current_user_id), task.startup_id):
                return error_response('Unauthorized to view this task', 403)
        else:
            return error_response('Unauthorized to view this task', 403)
    
    return success_response({'task': task.to_dict()})


@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """Create new task"""
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    
    required_fields = ['title']
    if not all(field in data for field in required_fields):
        return error_response('Missing required fields: title')
    
    user_id = data.get('user_id', current_user_id)
    current_user = User.query.get(current_user_id)
    if user_id != current_user_id:
        
        if not current_user or current_user.role != 'admin':
            return error_response('Unauthorized to create tasks for other users', 403)
    
    startup_id = data.get('startup_id')
    if startup_id and not has_startup_access(current_user_id, startup_id):
        return error_response('Unauthorized to create tasks for this startup', 403)
    if not can_create_task_or_milestone(current_user):
        return error_response('Task creation limit reached for your plan', 403)
    try:
        due_date = None
        if data.get('due_date'):
            due_date_str = data['due_date'].replace('Z', '+00:00')
            due_date = datetime.fromisoformat(due_date_str)
        
        assigned_to = data.get('assigned_to')
        if assigned_to in ("", None):
            assigned_to = None
        print("Creating task with data:", data)
        task = Task(
            user_id=user_id,
            startup_id=startup_id,
            title=data['title'],
            description=data.get('description'),
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'today'),
            due_date=due_date,
            assigned_to=assigned_to,
            visible_by=data.get('visible_by', 'all'),
            tags= data.get('tags', []),
            labels= data.get('labels', []),
            estimated_hours= data.get('estimated_hours', 0),
            created_by= data.get('created_by', current_user_id),
            urgent= data.get('urgent', False)
        )
        
        db.session.add(task)
        db.session.commit()
        
        # ===== SEND NOTIFICATION IF ASSIGNED TO SOMEONE ELSE =====
        if assigned_to and assigned_to != current_user_id:
            try:
                assigner_name = get_user_full_name(current_user_id)
                notify_task_assigned(
                    user_id=assigned_to,
                    assigner_id=current_user_id,
                    assigner_name=assigner_name,
                    task_title=task.title,
                    task_id=task.id
                )
            except Exception as e:
                print(f"Error sending task assigned notification: {e}")
        
        return success_response({
            'task': task.to_dict()
        }, 'Task created successfully', 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create task: {str(e)}', 500)

@tasks_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_tasks_stats():
    """Get task statistics for current user"""
    current_user_id = int(get_jwt_identity())
    
    user_id = request.args.get('user_id', type=int)
    startup_id = request.args.get('startup_id', type=int)
    time_range = request.args.get('time_range', '30d')
    
    if not user_id:
        user_id = current_user_id
    
    if user_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.role != 'admin':
            return error_response('Unauthorized to view other users stats', 403)
    
    now = datetime.utcnow()
    if time_range == '7d':
        start_date = now - timedelta(days=7)
    elif time_range == '90d':
        start_date = now - timedelta(days=90)
    elif time_range == 'month':
        start_date = datetime(now.year, now.month, 1)
    else:
        start_date = now - timedelta(days=30)
    
    query = Task.query.filter(
        (Task.user_id == user_id) | (Task.assigned_to == user_id),
        Task.created_at >= start_date
    )
    
    if startup_id:
        query = query.filter(Task.startup_id == startup_id)
    
    tasks = query.all()
    
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == 'completed'])
    in_progress_tasks = len([t for t in tasks if t.status == 'in_progress'])
    overdue_tasks = len([t for t in tasks if t.due_date and t.due_date < now and t.status != 'completed'])
    
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return success_response({
        'stats': {
            'totalTasks': total_tasks,
            'completedTasks': completed_tasks,
            'inProgressTasks': in_progress_tasks,
            'overdueTasks': overdue_tasks,
            'completionRate': round(completion_rate, 1)
        }
    })


@tasks_bp.route('/<int:task_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_task(task_id):
    """Update task"""
    current_user_id = int(get_jwt_identity())
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    # Allow: task owner, assignee, any startup member, or admin
    _upd_user = User.query.get(current_user_id)
    _is_admin = bool(_upd_user and _upd_user.role == 'admin')
    _is_member = bool(task.startup_id and has_startup_access(current_user_id, task.startup_id))
    if (task.user_id != current_user_id
            and task.assigned_to != current_user_id
            and not _is_member
            and not _is_admin):
        return error_response('Unauthorized to update this task', 403)
    
    data = request.get_json()
    old_status = task.status
    old_assigned_to = task.assigned_to
    
    try:
        # Update fields
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'priority' in data:
            task.priority = data['priority']
        if 'status' in data:
            task.status = data['status']
        if 'due_date' in data:
            if data['due_date']:
                due_date_str = data['due_date'].replace('Z', '+00:00')
                task.due_date = datetime.fromisoformat(due_date_str)
            else:
                task.due_date = None
        if 'assigned_to' in data:
            task.assigned_to = data['assigned_to']
        if 'visible_by' in data:
            task.visible_by = data['visible_by']
        if 'urgent' in data:
            task.urgent = data['urgent']
        if 'tags' in data:
            task.tags = data['tags']
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        # ===== SEND NOTIFICATIONS =====
        updater_name = get_user_full_name(current_user_id)
        
        # Task completed notification
        if old_status != 'completed' and task.status == 'completed':
            # Notify task owner if different from completer
            if task.user_id != current_user_id:
                try:
                    notify_task_completed(
                        user_id=task.user_id,
                        completer_id=current_user_id,
                        completer_name=updater_name,
                        task_title=task.title,
                        task_id=task.id
                    )
                except Exception as e:
                    print(f"Error sending task completed notification: {e}")
            
            # Check achievements
            try:
                AchievementService.check_achievements(current_user_id, 'task_completed')
            except:
                pass
        
        # Task reassigned notification
        if old_assigned_to != task.assigned_to and task.assigned_to:
            try:
                new_assignee_name = get_user_full_name(task.assigned_to)
                
                # Notify new assignee
                notify_task_assigned(
                    user_id=task.assigned_to,
                    assigner_id=current_user_id,
                    assigner_name=updater_name,
                    task_title=task.title,
                    task_id=task.id
                )
                
                # Notify old assignee if exists
                if old_assigned_to:
                    notify_task_reassigned(
                        user_id=old_assigned_to,
                        task_title=task.title,
                        task_id=task.id,
                        new_assignee=new_assignee_name
                    )
            except Exception as e:
                print(f"Error sending task reassignment notifications: {e}")
        
        # Task updated notification (for assignee if not the updater)
        elif task.assigned_to and task.assigned_to != current_user_id:
            try:
                notify_task_updated(
                    user_id=task.assigned_to,
                    task_title=task.title,
                    task_id=task.id
                )
            except Exception as e:
                print(f"Error sending task updated notification: {e}")
        
        return success_response({
            'task': task.to_dict()
        }, 'Task updated successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update task: {str(e)}', 500)


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
@jwt_required()
def complete_task(task_id):
    """Mark task as completed"""
    current_user_id = int(get_jwt_identity())
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    if task.user_id != current_user_id and task.assigned_to != current_user_id:
        return error_response('Unauthorized to complete this task', 403)
    
    try:
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        # ===== SEND NOTIFICATION =====
        if task.user_id != current_user_id:
            try:
                completer_name = get_user_full_name(current_user_id)
                notify_task_completed(
                    user_id=task.user_id,
                    completer_id=current_user_id,
                    completer_name=completer_name,
                    task_title=task.title,
                    task_id=task.id
                )
            except Exception as e:
                print(f"Error sending task completed notification: {e}")
        
        # Check achievements
        try:
            AchievementService.check_achievements(current_user_id, 'task_completed')
        except:
            pass
        
        return success_response({
            'task': task.to_dict()
        }, 'Task completed successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to complete task: {str(e)}', 500)


@tasks_bp.route('/<int:task_id>/assign', methods=['PUT'])
@jwt_required()
def assign_task(task_id):
    """Assign task to user"""
    current_user_id = int(get_jwt_identity())
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    if task.user_id != current_user_id:
        if task.startup_id:
            if not has_startup_access(current_user_id, task.startup_id):
                return error_response('Unauthorized to assign this task', 403)
        else:
            return error_response('Unauthorized to assign this task', 403)
    
    data = request.get_json()
    new_assignee_id = data.get('assigned_to')
    
    if not new_assignee_id:
        return error_response('User ID is required', 400)
    
    old_assignee_id = task.assigned_to
    
    try:
        task.assigned_to = new_assignee_id
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        # ===== SEND NOTIFICATIONS =====
        assigner_name = get_user_full_name(current_user_id)
        new_assignee_name = get_user_full_name(new_assignee_id)
        
        # Notify new assignee
        if new_assignee_id != current_user_id:
            try:
                notify_task_assigned(
                    user_id=new_assignee_id,
                    assigner_id=current_user_id,
                    assigner_name=assigner_name,
                    task_title=task.title,
                    task_id=task.id
                )
            except Exception as e:
                print(f"Error sending task assigned notification: {e}")
        
        # Notify old assignee about reassignment
        if old_assignee_id and old_assignee_id != current_user_id:
            try:
                notify_task_reassigned(
                    user_id=old_assignee_id,
                    task_title=task.title,
                    task_id=task.id,
                    new_assignee=new_assignee_name
                )
            except Exception as e:
                print(f"Error sending task reassigned notification: {e}")
        
        return success_response({
            'task': task.to_dict()
        }, 'Task assigned successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to assign task: {str(e)}', 500)


@tasks_bp.route('/<int:task_id>/claim', methods=['POST'])
@jwt_required()
def claim_task(task_id):
    """Self-assign an unassigned task — any startup member can claim"""
    current_user_id = int(get_jwt_identity())

    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)

    if task.assigned_to is not None:
        return error_response('Task is already assigned', 400)

    # Allow: startup member, task creator, or admin
    _user = User.query.get(current_user_id)
    _is_admin = bool(_user and _user.role == 'admin')
    _is_member = bool(task.startup_id and has_startup_access(current_user_id, task.startup_id))
    _is_creator = task.user_id == current_user_id

    if not (_is_member or _is_admin or _is_creator):
        return error_response('You must be a member of this startup to claim tasks', 403)

    try:
        task.assigned_to = current_user_id
        task.updated_at = datetime.utcnow()
        db.session.commit()

        # Notify the task creator that someone claimed it (only if different person)
        try:
            if task.user_id and task.user_id != current_user_id:
                claimer_name = get_user_full_name(current_user_id)
                notify_task_assigned(
                    user_id=task.user_id,
                    assigner_id=current_user_id,
                    assigner_name=claimer_name,
                    task_title=task.title,
                    task_id=task.id
                )
        except Exception as e:
            print(f"Claim task notification failed: {e}")

        try:
            task_dict = task.to_dict()
        except Exception as e:
            print(f"task.to_dict() failed: {e}")
            task_dict = {
                'id': task.id,
                'title': task.title,
                'assigned_to': task.assigned_to,
                'status': task.status,
            }

        return success_response({'task': task_dict}, 'Task claimed successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to claim task: {str(e)}', 500)

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """Delete task"""
    current_user_id = int(get_jwt_identity())
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    if task.user_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user.is_admin():
            return error_response('Unauthorized to delete this task', 403)
    
    try:
        db.session.delete(task)
        db.session.commit()
        return success_response(message='Task deleted successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete task: {str(e)}', 500)





@tasks_bp.route('/my-tasks', methods=['GET'])
@jwt_required()
def get_my_tasks():
    """Get current user's tasks"""
    current_user_id = int(get_jwt_identity())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=str)
    
    query = Task.query.filter(
        (Task.user_id == current_user_id) | (Task.assigned_to == current_user_id)
    )
    
    if status:
        query = query.filter(Task.status == status)
    
    result = paginate(query.order_by(Task.created_at.desc()), page, per_page)
    
    return success_response({
        'tasks': [task.to_dict() for task in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })


@tasks_bp.route('/overdue', methods=['GET'])
@jwt_required()
def get_overdue_tasks():
    """Get current user's overdue tasks"""
    current_user_id = int(get_jwt_identity())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Task.query.filter(
        (Task.user_id == current_user_id) | (Task.assigned_to == current_user_id),
        Task.due_date < datetime.utcnow(),
        Task.status != 'completed'
    )
    
    result = paginate(query.order_by(Task.due_date.asc()), page, per_page)
    
    return success_response({
        'tasks': [task.to_dict() for task in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })