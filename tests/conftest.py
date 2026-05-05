"""
Pytest configuration and fixtures for testing.
"""
import pytest
import os
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.post import Post
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import scoped_session, sessionmaker


@pytest.fixture(scope='session')
def app():
    """
    Create and configure a test Flask application.
    Scope: session - created once per test session.
    """
    # Set testing environment
    os.environ['FLASK_ENV'] = 'testing'
    
    # Create app with testing config
    app = create_app('testing')
    
    # Establish application context
    with app.app_context():
        yield app


@pytest.fixture(scope='session')
def _db_setup(app):
    """
    Create database tables once per test session.
    """
    _db.create_all()
    yield _db
    _db.drop_all()


@pytest.fixture(scope='function')
def db(_db_setup, app):
    """
    Provide a clean database for each test function.
    Rolls back any changes after each test.
    """
    with app.app_context():
        # Begin a nested transaction
        connection = _db.engine.connect()
        transaction = connection.begin()
        
        # Bind a scoped session to this test connection.
        # Flask-SQLAlchemy 3.x removed create_scoped_session.
        session = scoped_session(sessionmaker(bind=connection, autoflush=False, autocommit=False))
        _db.session = session
        
        yield _db
        
        # Rollback transaction and close
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture(scope='function')
def client(app, db):
    """
    Provide a test client for making requests.
    """
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """
    Provide a test CLI runner.
    """
    return app.test_cli_runner()


@pytest.fixture
def sample_user(db):
    """
    Create a sample user for testing.
    """
    user = User(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        role='member'
    )
    user.set_password('testpassword123')
    db.session.add(user)
    db.session.commit()
    db.session.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    """
    Create an admin user for testing.
    """
    user = User(
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    user.set_password('adminpassword123')
    db.session.add(user)
    db.session.commit()
    db.session.refresh(user)
    return user


@pytest.fixture
def auth_token(app, sample_user):
    """
    Generate a JWT token for the sample user.
    """
    with app.app_context():
        token = create_access_token(identity=sample_user.id)
        return token


@pytest.fixture
def admin_token(app, admin_user):
    """
    Generate a JWT token for the admin user.
    """
    with app.app_context():
        token = create_access_token(identity=admin_user.id)
        return token


@pytest.fixture
def auth_headers(auth_token):
    """
    Provide authorization headers with JWT token.
    """
    return {
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def admin_headers(admin_token):
    """
    Provide authorization headers with admin JWT token.
    """
    return {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def sample_post(db, sample_user):
    """
    Create a sample post for testing.
    """
    post = Post(
        user_id=sample_user.id,
        author_id=sample_user.id,
        author_first_name=sample_user.first_name,
        author_last_name=sample_user.last_name,
        content='This is a test post',
        type='professional'
    )
    db.session.add(post)
    db.session.commit()
    db.session.refresh(post)
    return post


@pytest.fixture
def multiple_posts(db, sample_user):
    """
    Create multiple posts for pagination/filtering tests.
    """
    posts = []
    for i in range(5):
        post = Post(
            user_id=sample_user.id,
            author_id=sample_user.id,
            author_first_name=sample_user.first_name,
            author_last_name=sample_user.last_name,
            content=f'Test post number {i}',
            type='professional' if i % 2 == 0 else 'casual',
            tags=['test', f'tag{i}']
        )
        db.session.add(post)
        posts.append(post)
    
    db.session.commit()
    for post in posts:
        db.session.refresh(post)
    return posts
