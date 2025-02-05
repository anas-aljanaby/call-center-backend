-- Create organizations table
CREATE TABLE organizations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name text NOT NULL,
    description text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Create roles table
CREATE TABLE roles (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name text NOT NULL CHECK (name IN ('admin', 'agent', 'user')),
    description text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Create user_roles table
CREATE TABLE user_roles (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid REFERENCES auth.users(id),
    role_id uuid REFERENCES roles(id),
    organization_id uuid REFERENCES organizations(id),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(user_id, role_id, organization_id)
);

-- Create agents table
CREATE TABLE agents (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid REFERENCES auth.users(id),
    organization_id uuid REFERENCES organizations(id),
    email text NOT NULL,
    full_name text NOT NULL,
    avatar_url text,
    status varchar CHECK (status IN ('online', 'offline', 'busy')),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Create calls table
CREATE TABLE calls (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    organization_id uuid REFERENCES organizations(id),
    agent_id uuid REFERENCES agents(id),
    recording_url text,
    duration int4,
    started_at timestamptz,
    ended_at timestamptz,
    resolution_status text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    processed boolean DEFAULT false
);

-- Create call_analytics table
CREATE TABLE call_analytics (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    call_id uuid REFERENCES calls(id),
    sentiment_score numeric,
    transcription jsonb,
    transcript_highlights jsonb,
    topics text[],
    flags text[],
    call_type text CHECK (call_type IN ('billing', 'technical', 'account', 'other')),
    summary text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Add indexes for foreign keys and common queries
CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_org_id ON user_roles(organization_id);
CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_agents_org_id ON agents(organization_id);
CREATE INDEX idx_calls_agent_id ON calls(agent_id);
CREATE INDEX idx_calls_org_id ON calls(organization_id);
CREATE INDEX idx_call_analytics_call_id ON call_analytics(call_id);