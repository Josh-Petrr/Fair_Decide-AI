-- FairDecide AI - PostgreSQL 17 + pgvector schema
-- Rebuilds everything from scratch: run only against the project's own database.

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS audit_log, notifications, assignment_decisions, recommendation_candidates,
    recommendation_requests, employee_profile_embeddings, project_embeddings, skill_embeddings,
    rating_adjustments, assignment_feedback, assignments, project_role_certifications, project_role_skills, project_roles,
    projects, app_users, employee_leaves, employee_certifications, employee_skills, employees, clients,
    policies, certification_skills, certifications, skill_aliases, skills, app_settings, baseline_role_status CASCADE;
DROP FUNCTION IF EXISTS fd_as_of(), fd_block_modification() CASCADE;
DROP SCHEMA IF EXISTS restricted CASCADE;
CREATE SCHEMA restricted;   -- protected attributes: fairness audits only, never model features

-- ============================================================ settings
CREATE TABLE app_settings (
    setting_key   text PRIMARY KEY,
    setting_value text NOT NULL
);
-- The synthetic data is a snapshot; views evaluate "today" as this date so demos are reproducible.
INSERT INTO app_settings VALUES ('as_of_date', '2026-10-26');

CREATE FUNCTION fd_as_of() RETURNS date LANGUAGE sql STABLE AS
$$ SELECT COALESCE((SELECT setting_value::date FROM app_settings WHERE setting_key = 'as_of_date'), current_date) $$;

-- ============================================================ reference data
CREATE TABLE skills (
    skill_id             text PRIMARY KEY,
    skill_name           text NOT NULL UNIQUE,
    category             text NOT NULL,
    available_since_year smallint
);

CREATE TABLE skill_aliases (
    skill_id text NOT NULL REFERENCES skills,
    alias    text NOT NULL,
    PRIMARY KEY (skill_id, alias)
);

CREATE TABLE certifications (
    cert_id         text PRIMARY KEY,
    cert_name       text NOT NULL,
    vendor          text NOT NULL,
    exam_code       text,
    level           text,
    validity_months smallint,          -- NULL = does not expire
    available_from  date,
    retired_on      date
);

CREATE TABLE certification_skills (
    cert_id  text REFERENCES certifications,
    skill_id text REFERENCES skills,
    PRIMARY KEY (cert_id, skill_id)
);

CREATE TABLE policies (
    policy_id          text PRIMARY KEY,
    policy_name        text NOT NULL,
    rule_key           text NOT NULL UNIQUE,
    rule_value         text NOT NULL,
    is_hard_constraint boolean NOT NULL,
    description        text
);

-- ============================================================ workforce
CREATE TABLE employees (
    employee_id            text PRIMARY KEY,
    first_name             text NOT NULL,
    last_name              text NOT NULL,
    full_name              text NOT NULL,
    email                  text UNIQUE,
    designation            text NOT NULL,
    job_level              text NOT NULL CHECK (job_level IN ('L1','L2','L3','L4','L5','L6')),
    practice               text NOT NULL,
    role_family            text NOT NULL,
    primary_skill          text,
    location               text NOT NULL,
    work_mode              text,
    date_of_joining        date NOT NULL,
    prior_experience_years numeric(4,1),
    total_experience_years numeric(4,1),
    highest_qualification  text,
    career_break_months    smallint DEFAULT 0,
    reporting_manager_id   text REFERENCES employees DEFERRABLE INITIALLY DEFERRED,
    employment_status      text NOT NULL CHECK (employment_status IN ('Active','Serving Notice','On Long Leave','Exited')),
    exit_date              date,
    last_appraisal_rating  smallint CHECK (last_appraisal_rating BETWEEN 1 AND 5),
    appraisal_cycle        text
);

CREATE TABLE restricted.employee_sensitive_attributes (
    employee_id   text PRIMARY KEY REFERENCES employees,
    gender        text,
    date_of_birth date,
    age_band      text
);

CREATE TABLE employee_skills (
    employee_id         text REFERENCES employees,
    skill_id            text REFERENCES skills,
    proficiency         smallint CHECK (proficiency BETWEEN 1 AND 5),   -- NULL = not filled in
    proficiency_label   text,
    years_used          numeric(4,1),
    last_used_date      date,
    is_manager_verified boolean NOT NULL DEFAULT false,
    acquired_on         date,               -- when the skill was first gained (enables point-in-time features)
    PRIMARY KEY (employee_id, skill_id)
);

CREATE TABLE employee_certifications (
    employee_cert_id    text PRIMARY KEY,
    employee_id         text NOT NULL REFERENCES employees,
    cert_id             text NOT NULL REFERENCES certifications,
    credential_id       text,
    issue_date          date,
    last_renewed_on     date,
    expiry_date         date,
    verification_status text
);

CREATE TABLE employee_leaves (
    leave_id    text PRIMARY KEY,
    employee_id text NOT NULL REFERENCES employees,
    leave_type  text NOT NULL,
    start_date  date NOT NULL,
    end_date    date NOT NULL,
    status      text NOT NULL CHECK (status IN ('Approved','Pending','Rejected','Cancelled'))
);

-- ============================================================ clients & projects
CREATE TABLE clients (
    client_id                   text PRIMARY KEY,
    client_name                 text NOT NULL,
    industry                    text NOT NULL,
    industry_code               text NOT NULL,
    sub_industry                text,
    hq_city                     text,
    country                     text,
    relationship_since          smallint,
    account_delivery_manager_id text REFERENCES employees
);

CREATE TABLE projects (
    project_id          text PRIMARY KEY,
    project_code        text NOT NULL UNIQUE,
    project_name        text NOT NULL,
    client_id           text NOT NULL REFERENCES clients,
    industry            text,
    project_type        text,
    engagement_model    text,
    description         text,
    tech_stack          text,
    start_date          date NOT NULL,
    end_date            date NOT NULL,
    status              text NOT NULL CHECK (status IN ('Pipeline','Active','Completed','On Hold','Cancelled')),
    priority            text CHECK (priority IN ('Critical','High','Medium','Low')),
    delivery_location   text,
    project_manager_id  text REFERENCES employees,
    delivery_manager_id text REFERENCES employees,
    planned_team_size   smallint,
    created_on          date,
    outcome             text,
    client_csat         numeric(2,1)
);

-- A staffing demand: one role/position on a project (headcount may be > 1)
CREATE TABLE project_roles (
    project_role_id      text PRIMARY KEY,
    project_id           text NOT NULL REFERENCES projects,
    role_title           text NOT NULL,
    role_family          text NOT NULL,
    headcount            smallint NOT NULL DEFAULT 1,
    min_experience_years numeric(4,1) DEFAULT 0,
    allocation_pct       smallint NOT NULL DEFAULT 100 CHECK (allocation_pct BETWEEN 1 AND 100),
    start_date           date NOT NULL,
    end_date             date NOT NULL,
    demand_type          text NOT NULL DEFAULT 'Initial',      -- Initial / Ramp-up / Backfill
    demand_status        text NOT NULL DEFAULT 'Open',         -- Open / Partially Filled / Filled / Closed / Cancelled
    created_on           date
);

CREATE TABLE project_role_skills (
    project_role_id text REFERENCES project_roles ON DELETE CASCADE,
    skill_id        text REFERENCES skills,
    min_proficiency smallint CHECK (min_proficiency BETWEEN 1 AND 5),
    importance      text NOT NULL CHECK (importance IN ('Mandatory','Preferred')),
    PRIMARY KEY (project_role_id, skill_id)
);

CREATE TABLE project_role_certifications (
    project_role_id text REFERENCES project_roles ON DELETE CASCADE,
    cert_id         text REFERENCES certifications,
    importance      text NOT NULL CHECK (importance IN ('Mandatory','Preferred')),
    PRIMARY KEY (project_role_id, cert_id)
);

CREATE TABLE assignments (
    assignment_id      text PRIMARY KEY,
    employee_id        text NOT NULL REFERENCES employees,
    project_id         text NOT NULL REFERENCES projects,
    project_role_id    text REFERENCES project_roles,
    role_title         text,
    allocation_pct     smallint NOT NULL CHECK (allocation_pct BETWEEN 1 AND 100),
    start_date         date NOT NULL,
    end_date           date NOT NULL,
    status             text NOT NULL CHECK (status IN ('Upcoming','Active','Completed','Cancelled')),
    billable           boolean DEFAULT true,
    assigned_by        text REFERENCES employees,
    assigned_on        date,
    release_reason     text,
    performance_rating smallint CHECK (performance_rating BETWEEN 1 AND 5),
    CHECK (end_date >= start_date)
);
CREATE INDEX ix_assignments_employee ON assignments (employee_id, start_date, end_date);
CREATE INDEX ix_assignments_project ON assignments (project_id);

CREATE TABLE assignment_feedback (
    feedback_id   text PRIMARY KEY,
    assignment_id text NOT NULL REFERENCES assignments,
    given_by      text REFERENCES employees,
    feedback_date date,
    rating        smallint CHECK (rating BETWEEN 1 AND 5),
    comments      text
);

-- Written by the offline fairness job: ratings corrected for gaps not explained by qualifications
CREATE TABLE rating_adjustments (
    assignment_id   text PRIMARY KEY REFERENCES assignments,
    raw_rating      smallint NOT NULL,
    adjusted_rating numeric(4,2) NOT NULL,
    method          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_users (
    user_id     text PRIMARY KEY,
    employee_id text REFERENCES employees,
    full_name   text NOT NULL,
    email       text NOT NULL UNIQUE,
    app_role    text NOT NULL CHECK (app_role IN ('manager','hr_admin','auditor','admin')),
    is_active   boolean NOT NULL DEFAULT true
);

-- ============================================================ written by the application (empty at load)
CREATE TABLE recommendation_requests (
    request_id          bigserial PRIMARY KEY,
    project_role_id     text REFERENCES project_roles,
    requested_by        text REFERENCES app_users,
    requested_at        timestamptz NOT NULL DEFAULT now(),
    query_text          text,                 -- manager's natural-language request, if any
    parsed_requirements jsonb,                -- structured requirements the manager confirmed
    model_version       text
);

CREATE TABLE recommendation_candidates (
    request_id       bigint REFERENCES recommendation_requests ON DELETE CASCADE,
    employee_id      text REFERENCES employees,
    rank             smallint NOT NULL,
    match_score      numeric(5,4),
    confidence       text,
    evidence_score   numeric(5,4),
    explanation      jsonb,                   -- factor contributions (SHAP) and rule results
    explanation_text text,                    -- plain-language explanation shown to the manager
    flags            jsonb,                   -- missing / conflicting data, workload and fairness warnings
    PRIMARY KEY (request_id, employee_id)
);

CREATE TABLE assignment_decisions (           -- human-in-the-loop decision record (append-only)
    decision_id           bigserial PRIMARY KEY,
    request_id            bigint REFERENCES recommendation_requests,
    project_role_id       text REFERENCES project_roles,
    decided_by            text NOT NULL REFERENCES app_users,
    decided_at            timestamptz NOT NULL DEFAULT now(),
    decision              text NOT NULL CHECK (decision IN ('approved','rejected','modified')),
    selected_employee_ids text[] NOT NULL DEFAULT '{}',
    decision_reason       text NOT NULL,
    notes                 text
);

CREATE TABLE notifications (
    notification_id bigserial PRIMARY KEY,
    decision_id     bigint REFERENCES assignment_decisions,
    assignment_id   text REFERENCES assignments,
    employee_id     text REFERENCES employees,
    channel         text NOT NULL DEFAULT 'email',
    recipient       text,
    subject         text,
    body            text,
    status          text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','failed')),
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    sent_at         timestamptz
);

CREATE TABLE audit_log (
    audit_id   bigserial PRIMARY KEY,
    event_type text NOT NULL,
    actor      text,
    entity     text,
    entity_id  text,
    payload    jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION fd_block_modification() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END $$;
CREATE TRIGGER trg_audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION fd_block_modification();
CREATE TRIGGER trg_decisions_append_only BEFORE UPDATE OR DELETE ON assignment_decisions
    FOR EACH ROW EXECUTE FUNCTION fd_block_modification();

-- ============================================================ embeddings (all-MiniLM-L6-v2 = 384 dims)
CREATE TABLE skill_embeddings (
    skill_id   text PRIMARY KEY REFERENCES skills,
    model      text NOT NULL,
    embedding  vector(384) NOT NULL
);
CREATE TABLE project_embeddings (
    project_id  text PRIMARY KEY REFERENCES projects,
    model       text NOT NULL,
    source_text text,
    embedding   vector(384) NOT NULL
);
CREATE TABLE employee_profile_embeddings (
    employee_id text PRIMARY KEY REFERENCES employees,
    model       text NOT NULL,
    source_text text,
    embedding   vector(384) NOT NULL
);
CREATE INDEX ix_skill_emb ON skill_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_project_emb ON project_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_employee_emb ON employee_profile_embeddings USING hnsw (embedding vector_cosine_ops);

-- ============================================================ views
CREATE VIEW v_employee_current_load AS
SELECT e.employee_id,
       COALESCE(SUM(a.allocation_pct), 0)::int  AS current_allocation_pct,
       COUNT(DISTINCT a.project_id)::int        AS active_project_count
FROM employees e
LEFT JOIN assignments a
       ON a.employee_id = e.employee_id
      AND a.status <> 'Cancelled'
      AND fd_as_of() BETWEEN a.start_date AND a.end_date
WHERE e.employment_status <> 'Exited'
GROUP BY e.employee_id;

CREATE VIEW v_employee_certification_status AS
SELECT ec.*, c.cert_name, c.vendor,
       (ec.issue_date <= fd_as_of() AND (ec.expiry_date IS NULL OR ec.expiry_date >= fd_as_of())) AS is_valid,
       (ec.expiry_date IS NOT NULL AND ec.issue_date > ec.expiry_date)                            AS has_date_error
FROM employee_certifications ec
JOIN certifications c USING (cert_id);

CREATE VIEW v_open_demands AS
SELECT pr.*, p.project_name, p.client_id, p.status AS project_status, p.priority, p.project_manager_id
FROM project_roles pr
JOIN projects p USING (project_id)
WHERE pr.demand_status IN ('Open', 'Partially Filled');
