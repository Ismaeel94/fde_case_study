CREATE TYPE user_role AS ENUM (
    'admin_user',
    'sales_user',
    'support_user'
);

CREATE TYPE customer_status AS ENUM (
    'active',
    'inactive'
);

CREATE TYPE issue_status AS ENUM (
    'open',
    'in_progress',
    'blocked',
    'resolved',
    'closed'
);

CREATE TYPE issue_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE issue_update_type AS ENUM (
    'triage',
    'investigation',
    'customer_update',
    'internal_note',
    'technical_note',
    'resolution'
);

CREATE TYPE next_action_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'cancelled'
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    support_owner_id INT REFERENCES users(id),
    status customer_status NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status issue_status NOT NULL DEFAULT 'open',
    priority issue_priority NOT NULL DEFAULT 'medium',
    assigned_to INT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE issue_updates (
    id SERIAL PRIMARY KEY,
    issue_id INT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    updated_by INT REFERENCES users(id),
    update_type issue_update_type NOT NULL,
    update_text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE next_actions (
    id SERIAL PRIMARY KEY,
    issue_id INT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    owner_id INT REFERENCES users(id),
    status next_action_status NOT NULL DEFAULT 'pending',
    action_text TEXT NOT NULL,
    due_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_name
ON customers(name);

CREATE INDEX idx_issues_customer_status
ON issues(customer_id, status);

CREATE INDEX idx_issues_assigned_to
ON issues(assigned_to);

CREATE INDEX idx_issue_updates_issue_created
ON issue_updates(issue_id, created_at DESC);

CREATE INDEX idx_next_actions_issue_status
ON next_actions(issue_id, status);