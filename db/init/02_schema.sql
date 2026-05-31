INSERT INTO users
(username, email, full_name, role)
VALUES
('admin_user', 'admin@example.com', 'Admin User', 'admin_user'),
('sales_user', 'sales@example.com', 'Sales User', 'sales_user'),
('support_user', 'support@example.com', 'Support User', 'support_user');

INSERT INTO customers
(name, support_owner_id, status, notes)
VALUES
(
    'Client X',
    3,
    'active',
    'Strategic customer. Escalated concerns around platform performance.'
),
(
    'Northstar Logistics',
    3,
    'active',
    'Growing account with several feature requests.'
),
(
    'Legacy Industries',
    3,
    'inactive',
    'Former customer retained for historical reporting purposes.'
);

INSERT INTO issues
(
    customer_id,
    title,
    description,
    status,
    priority,
    assigned_to,
    created_at,
    updated_at
)
VALUES
(
    1,
    'Delayed API responses during peak hours',
    'Customer reports significant latency during morning business hours.',
    'open',
    'high',
    3,
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '4 hours'
),
(
    1,
    'Incorrect renewal pricing shown in dashboard',
    'Dashboard is displaying outdated renewal pricing.',
    'in_progress',
    'medium',
    3,
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '1 day'
),
(
    1,
    'SSO login failures',
    'Users experienced login failures after identity provider certificate changes.',
    'resolved',
    'high',
    3,
    NOW() - INTERVAL '12 days',
    NOW() - INTERVAL '8 days'
),
(
    2,
    'Additional reporting fields requested',
    'Customer requested extra shipment reporting attributes.',
    'open',
    'low',
    3,
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '10 hours'
);

INSERT INTO issue_updates
(issue_id, updated_by, update_type, update_text, created_at)
VALUES
(1, 3, 'triage', 'Initial triage completed. Latency spikes confirmed.', NOW() - INTERVAL '4 days'),
(1, 3, 'investigation', 'Database CPU usage increases significantly during reporting windows.', NOW() - INTERVAL '2 days'),
(1, 3, 'technical_note', 'Potential missing indexes identified on reporting queries.', NOW() - INTERVAL '4 hours'),

(2, 3, 'customer_update', 'Customer confirmed the issue affects several enterprise accounts.', NOW() - INTERVAL '2 days'),
(2, 3, 'investigation', 'Pricing synchronisation job appears to be using stale configuration.', NOW() - INTERVAL '1 day'),

(3, 3, 'resolution', 'Updated identity provider configuration and validated successful login.', NOW() - INTERVAL '8 days'),

(4, 3, 'customer_update', 'Awaiting clarification regarding required report fields.', NOW() - INTERVAL '10 hours');

INSERT INTO next_actions
(issue_id, owner_id, status, action_text, due_date)
VALUES
(1, 3, 'pending', 'Review query execution plans and confirm indexing recommendations.', CURRENT_DATE + 1),
(1, 2, 'pending', 'Provide customer-facing progress update.', CURRENT_DATE + 1),
(2, 3, 'in_progress', 'Validate pricing synchronisation configuration.', CURRENT_DATE + 2),
(4, 3, 'pending', 'Collect detailed reporting requirements from customer.', CURRENT_DATE + 3);