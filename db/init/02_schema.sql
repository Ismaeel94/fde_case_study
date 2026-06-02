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
    'Intermittent webhook delivery failures',
    'Customer reports that some outbound webhooks are not being delivered reliably.',
    'open',
    'high',
    3,
    NOW() - INTERVAL '4 days',
    NOW() - INTERVAL '6 hours'
),
(
    1,
    'Missing audit log entries for admin actions',
    'Customer reports that some administrator changes are not appearing in the audit log.',
    'open',
    'medium',
    3,
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '12 hours'
),
(
    2,
    'Shipment status updates delayed',
    'Customer reports delays in shipment status updates appearing in the platform.',
    'open',
    'medium',
    3,
    NOW() - INTERVAL '6 days',
    NOW() - INTERVAL '1 day'
),
(
    2,
    'Bulk export fails for large shipment reports',
    'Customer reports that exporting large shipment reports sometimes fails before completion.',
    'in_progress',
    'high',
    3,
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '8 hours'
);

INSERT INTO issue_updates
(issue_id, updated_by, update_type, update_text, created_at)
VALUES
(5, 3, 'triage', 'Initial triage completed. Delivery failures appear intermittent.', NOW() - INTERVAL '3 days'),
(5, 3, 'investigation', 'Webhook retry logs show failures for a subset of endpoints.', NOW() - INTERVAL '1 day'),
(5, 3, 'technical_note', 'Engineering is reviewing timeout handling in the webhook worker.', NOW() - INTERVAL '6 hours'),

(6, 3, 'customer_update', 'Customer provided examples of missing audit log records.', NOW() - INTERVAL '1 day'),
(6, 3, 'investigation', 'Audit events are being generated but not consistently persisted.', NOW() - INTERVAL '12 hours'),

(7, 3, 'triage', 'Initial triage completed. Delays confirmed for shipment status ingestion.', NOW() - INTERVAL '5 days'),
(7, 3, 'investigation', 'Queue backlog observed during high-volume shipment updates.', NOW() - INTERVAL '2 days'),
(7, 3, 'customer_update', 'Customer informed that investigation is ongoing.', NOW() - INTERVAL '1 day'),

(8, 3, 'triage', 'Initial triage completed. Failures reproduced with large export payloads.', NOW() - INTERVAL '4 days'),
(8, 3, 'investigation', 'Export worker memory usage increases sharply for large reports.', NOW() - INTERVAL '2 days'),
(8, 3, 'technical_note', 'Pagination and streaming export options are being reviewed.', NOW() - INTERVAL '8 hours');

INSERT INTO next_actions
(issue_id, owner_id, status, action_text, due_date)
VALUES
(1, 3, 'pending', 'Review query execution plans and confirm indexing recommendations.', CURRENT_DATE + 1),
(1, 2, 'pending', 'Provide customer-facing progress update.', CURRENT_DATE + 1),
(2, 3, 'in_progress', 'Validate pricing synchronisation configuration.', CURRENT_DATE + 2),
(4, 3, 'pending', 'Collect detailed reporting requirements from customer.', CURRENT_DATE + 3);