-- Database Schema for SF Collab Backend
-- Updated: May 14, 2026
-- This file contains the complete database schema and initial data

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

-- Ensure user exists with correct host
CREATE USER IF NOT EXISTS 'sfcollab'@'%' IDENTIFIED BY 'sfcollab_pass';

-- Always reset privileges
GRANT ALL PRIVILEGES ON sf_collab_db.* TO 'sfcollab'@'%';

FLUSH PRIVILEGES;

-- Users table
CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role ENUM('founder','contributor','investor','advisor','mentor','partner','admin','moderator','member','technical_lead','engineering_manager','influencer','content_creator','community_manager','hr_specialist','backend_engineer','frontend_engineer','fullstack_engineer','mobile_engineer','software_architect','qa_engineer','test_automation_engineer','devops_engineer','cloud_engineer','sre','infrastructure_engineer','platform_engineer','cybersecurity_engineer','data_scientist','data_engineer','machine_learning_engineer','ai_engineer','mlops_engineer','data_analyst','ai_researcher','product_manager','product_owner','ux_designer','ui_designer','product_designer','ux_researcher','growth_engineer','growth_marketer','seo_specialist','content_strategist') DEFAULT 'member',
    status ENUM('active','deleted','banned') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (email)
);

-- Startups table
CREATE TABLE startups (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100) NOT NULL,
    location VARCHAR(255),
    description TEXT,
    stage ENUM('idea','validation','early','growth','scale') DEFAULT 'idea',
    revenue FLOAT DEFAULT 0.0,
    funding_amount FLOAT DEFAULT 0.0,
    funding_round VARCHAR(50) DEFAULT 'pre-seed',
    burn_rate FLOAT DEFAULT 0.0,
    runway_months INTEGER DEFAULT 0,
    valuation FLOAT DEFAULT 0.0,
    financial_notes TEXT,
    logo_path VARCHAR(500),
    logo_content_type VARCHAR(100),
    banner_path VARCHAR(500),
    banner_content_type VARCHAR(100),
    logo_url VARCHAR(500),
    banner_url VARCHAR(500),
    tech_stack JSON NOT NULL DEFAULT ('[]'),
    positions INTEGER DEFAULT 0,
    roles JSON DEFAULT ('{}'),
    creator_id INTEGER NOT NULL,
    creator_first_name VARCHAR(100),
    creator_last_name VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    member_count INTEGER DEFAULT 1,
    views INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (name),
    FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Startup Members table
CREATE TABLE startup_members (
    id INTEGER NOT NULL AUTO_INCREMENT,
    startup_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role ENUM('founder','contributor','investor','advisor','mentor','partner','admin','moderator','member','technical_lead','engineering_manager','influencer','content_creator','community_manager','hr_specialist','backend_engineer','frontend_engineer','fullstack_engineer','mobile_engineer','software_architect','qa_engineer','test_automation_engineer','devops_engineer','cloud_engineer','sre','infrastructure_engineer','platform_engineer','cybersecurity_engineer','data_scientist','data_engineer','machine_learning_engineer','ai_engineer','mlops_engineer','data_analyst','ai_researcher','product_manager','product_owner','ux_designer','ui_designer','product_designer','ux_researcher','growth_engineer','growth_marketer','seo_specialist','content_strategist') DEFAULT 'member',
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY(startup_id) REFERENCES startups (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Join Requests table
CREATE TABLE join_requests (
    id INTEGER NOT NULL AUTO_INCREMENT,
    startup_id INTEGER NOT NULL,
    startup_name VARCHAR(255),
    user_id INTEGER NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    message TEXT,
    role VARCHAR(100) DEFAULT 'member',
    status ENUM('pending','approved','rejected','cancelled') DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY(startup_id) REFERENCES startups (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- analytics_events table 
CREATE TABLE analytics_events (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_id VARCHAR(100) NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    user_id INTEGER NULL,
    startup_id INTEGER NULL,
    workspace_id INTEGER NULL,
    entity_type VARCHAR(100) NULL,
    entity_id INTEGER NULL,
    event_timestamp DATETIME NOT NULL,
    event_source VARCHAR(100) NOT NULL,
    event_version VARCHAR(20) DEFAULT 'v1',
    idempotency_key VARCHAR(255) NULL,
    metadata JSON NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_analytics_event_id (event_id),
    UNIQUE KEY uq_analytics_idempotency_key (idempotency_key),
    INDEX ix_analytics_event_name (event_name),
    INDEX ix_analytics_user_id (user_id),
    INDEX ix_analytics_startup_id (startup_id),
    INDEX ix_analytics_workspace_id (workspace_id),
    INDEX ix_analytics_event_timestamp (event_timestamp),
    INDEX ix_analytics_event_name_timestamp (event_name, event_timestamp),
    INDEX ix_analytics_workspace_event_time (workspace_id, event_name, event_timestamp),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (startup_id) REFERENCES startups(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX ix_users_email ON users (email);
CREATE INDEX ix_startups_creator_id ON startups (creator_id);
CREATE INDEX ix_startup_members_startup_id ON startup_members (startup_id);
CREATE INDEX ix_startup_members_user_id ON startup_members (user_id);
CREATE INDEX ix_join_requests_startup_id ON join_requests (startup_id);
CREATE INDEX ix_join_requests_user_id ON join_requests (user_id);
CREATE INDEX ix_join_requests_status ON join_requests (status);

-- Insert sample data
INSERT INTO users (email, password_hash, first_name, last_name, role, status) VALUES
('chinmayabharadwajhs@gmail.com', 'hashed_password', 'Chinmaya', 'Bharadwaj H S', 'member', 'active'),
('test@example.com', 'hashed_password', 'Test', 'User', 'founder', 'active');

INSERT INTO startups (name, industry, location, description, stage, creator_id, creator_first_name, creator_last_name, status, member_count) VALUES
('SFCollab Starter', 'Technology', 'San Francisco', 'A collaborative platform for startups', 'idea', 2, 'Test', 'User', 'active', 1);

INSERT INTO startup_members (startup_id, user_id, first_name, last_name, role) VALUES
(1, 2, 'Test', 'User', 'founder');

-- Schema update notes:
-- - Fixed permission checks to properly handle UserRoles enum values
-- - Updated DELETE endpoint to use can_manage_members() for consistent authorization
-- - Changed join requests default filter to 'all' for better visibility
-- - Added debug logging to DELETE endpoint for troubleshooting
-- - Added analytics_events table 

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
