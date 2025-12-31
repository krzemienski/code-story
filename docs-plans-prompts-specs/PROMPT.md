# Code Story - Master Execution Prompt

<metadata>
<purpose>Do</purpose>
<complexity>Comprehensive</complexity>
<total_plans>58</total_plans>
<total_phases>13</total_phases>
</metadata>

---

## Objective

<objective>
Implement the complete Code Story platform—a developer-first system that transforms code repositories into tailored audio narratives using a 4-agent Claude SDK architecture.

**Purpose**: Execute all 58 implementation plans across 13 phases, coordinating sub-agents for complex tasks, maintaining quality through validation gates, and tracking progress for resumability.

**Output**: A fully functional Code Story platform with:
- Python backend with 4-agent pipeline (Intent → Analyzer → Architect → Voice)
- FastAPI REST API with authentication and job queue
- React web frontend with audio player
- Expo mobile app with background playback
- Public API with rate limiting
- Self-hosting Docker/Kubernetes support
- Enterprise team features
</objective>

---

## Context Files

<context>
Load these files to understand the full project:

**Project Vision:**
@BRIEF.md

**Phase Structure:**
@ROADMAP.md

**Implementation Plans (58 total):**
@plans/01-foundation/01-01-PLAN.md
@plans/01-foundation/01-02-PLAN.md
@plans/01-foundation/01-03-PLAN.md
@plans/01-foundation/01-04-PLAN.md
@plans/01-foundation/01-05-PLAN.md

@plans/02-intent-agent/02-01-PLAN.md
@plans/02-intent-agent/02-02-PLAN.md
@plans/02-intent-agent/02-03-PLAN.md
@plans/02-intent-agent/02-04-PLAN.md

@plans/03-repo-analyzer/03-01-PLAN.md
@plans/03-repo-analyzer/03-02-PLAN.md
@plans/03-repo-analyzer/03-03-PLAN.md
@plans/03-repo-analyzer/03-04-PLAN.md
@plans/03-repo-analyzer/03-05-PLAN.md

@plans/04-story-architect/04-01-PLAN.md
@plans/04-story-architect/04-02-PLAN.md
@plans/04-story-architect/04-03-PLAN.md
@plans/04-story-architect/04-04-PLAN.md
@plans/04-story-architect/04-05-PLAN.md

@plans/05-voice-director/05-01-PLAN.md
@plans/05-voice-director/05-02-PLAN.md
@plans/05-voice-director/05-03-PLAN.md
@plans/05-voice-director/05-04-PLAN.md

@plans/06-fastapi-backend/06-01-PLAN.md
@plans/06-fastapi-backend/06-02-PLAN.md
@plans/06-fastapi-backend/06-03-PLAN.md
@plans/06-fastapi-backend/06-04-PLAN.md
@plans/06-fastapi-backend/06-05-PLAN.md
@plans/06-fastapi-backend/06-06-PLAN.md

@plans/07-react-frontend/07-01-PLAN.md
@plans/07-react-frontend/07-02-PLAN.md
@plans/07-react-frontend/07-03-PLAN.md
@plans/07-react-frontend/07-04-PLAN.md
@plans/07-react-frontend/07-05-PLAN.md
@plans/07-react-frontend/07-06-PLAN.md

@plans/08-expo-mobile/08-01-PLAN.md
@plans/08-expo-mobile/08-02-PLAN.md
@plans/08-expo-mobile/08-03-PLAN.md
@plans/08-expo-mobile/08-04-PLAN.md
@plans/08-expo-mobile/08-05-PLAN.md

@plans/09-full-experience/09-01-PLAN.md
@plans/09-full-experience/09-02-PLAN.md
@plans/09-full-experience/09-03-PLAN.md
@plans/09-full-experience/09-04-PLAN.md

@plans/10-api-docs/10-01-PLAN.md
@plans/10-api-docs/10-02-PLAN.md
@plans/10-api-docs/10-03-PLAN.md
@plans/10-api-docs/10-04-PLAN.md

@plans/11-admin-dashboard/11-01-PLAN.md
@plans/11-admin-dashboard/11-02-PLAN.md
@plans/11-admin-dashboard/11-03-PLAN.md
@plans/11-admin-dashboard/11-04-PLAN.md

@plans/12-self-hosting/12-01-PLAN.md
@plans/12-self-hosting/12-02-PLAN.md
@plans/12-self-hosting/12-03-PLAN.md

@plans/13-enterprise/13-01-PLAN.md
@plans/13-enterprise/13-02-PLAN.md
@plans/13-enterprise/13-03-PLAN.md
</context>

---

## Pre-Execution Protocol

<pre_execution>
Before ANY implementation, complete these steps IN ORDER:

### Step 1: Enable Extended Thinking

Activate extended thinking for deep synthesis across 58 interconnected plans.

```
Enable extended thinking mode.
Budget: 32000 tokens for complex architectural synthesis.
This enables thorough analysis before execution begins.
```

### Step 2: Inventory MCP Tools

Check available MCP servers and tools:

| Tool | Purpose | Usage |
|------|---------|-------|
| sequential-thinking | Task breakdown | Complex phases, debugging |
| context7 | Live documentation | Claude SDK, FastAPI, React, Expo, ElevenLabs |
| memory | Persistence | Progress tracking, decisions, cross-session context |
| playwright | Testing | Validation gates after phases |

List all connected MCP servers. Note which are available.

### Step 3: Check Progress State

```bash
# Check for existing progress
if [ -f "PROGRESS.md" ]; then
  echo "EXISTING PROGRESS FOUND - Resume from last completed plan"
  cat PROGRESS.md
else
  echo "Fresh start - Beginning with Phase 1, Plan 01"
fi

# Check for existing code
if [ -d "src" ] || [ -f "pyproject.toml" ]; then
  echo "EXISTING CODE DETECTED - Analyze before modifications"
fi
```

If progress exists, resume from the last incomplete plan.

### Step 4: Read All Plans

**This is mandatory.** Read every plan file listed in the Context section above before starting implementation.

```bash
# Read all 58 plans in order
for phase in 01-foundation 02-intent-agent 03-repo-analyzer 04-story-architect \
             05-voice-director 06-fastapi-backend 07-react-frontend 08-expo-mobile \
             09-full-experience 10-api-docs 11-admin-dashboard 12-self-hosting 13-enterprise; do
  echo "=== Reading Phase: $phase ==="
  for plan in plans/$phase/*-PLAN.md; do
    cat "$plan"
  done
done
```

### Step 5: Synthesize Strategy

After reading all plans, thoroughly analyze and synthesize:

- Complete 4-agent architecture (Intent → Analyzer → Architect → Voice)
- Database schema relationships across all models
- API endpoint structure and authentication flow
- Frontend component hierarchy
- Phase dependencies and parallel opportunities
- Sub-agent delegation points
- External dependencies (ElevenLabs, GitHub API, S3)
- High-risk integrations needing extra validation

</pre_execution>

---

## Phase Dependencies

<dependencies>
```
Phase 1: Foundation
    │
    ├──→ Phase 2: Intent Agent ────────┐
    │                                  │
    ├──→ Phase 3: Repo Analyzer ───────┼──→ Phase 4: Story Architect ──→ Phase 5: Voice Director
    │                                  │                                         │
    └──────────────────────────────────┴──→ Phase 6: FastAPI Backend ←───────────┘
                                                    │
                                       ┌────────────┴────────────┐
                                       │                         │
                                       ▼                         ▼
                              Phase 7: React Frontend    Phase 8: Expo Mobile
                                       │                         │
                                       └───────────┬─────────────┘
                                                   │
                                                   ▼
                                       Phase 9: Full Experience
                                                   │
                                                   ▼
                                       Phase 10: API & Docs
                                                   │
                                                   ▼
                                       Phase 11: Admin Dashboard
                                                   │
                                                   ▼
                                       Phase 12: Self-Hosting
                                                   │
                                                   ▼
                                       Phase 13: Enterprise
```

**Parallel Opportunities:**
- Phases 2 & 3 can run in parallel (both depend only on Phase 1)
- Phases 7 & 8 can run in parallel (both depend on Phase 6)

**Critical Path:** 1 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12 → 13
</dependencies>

---

## Sub-Agent Strategy

<sub_agents>
Spawn specialized sub-agents with fresh context for complex work:

| Phase | Plan | Trigger | Sub-Agent Focus |
|-------|------|---------|-----------------|
| 3 | 03-03 | AST complexity | Python/JS parser implementation |
| 4 | 04-03 | 5 narrative styles | Style-specific prompt engineering |
| 5 | 05-02 | External API | ElevenLabs integration |
| 6 | 06-02 | Security-critical | JWT authentication |
| 6 | 06-04 | Distributed system | Celery/Redis job queue |
| 7 | 07-06 | Complex component | Audio player |
| 8 | 08-05 | Platform-specific | Mobile background audio |
| 13 | 13-03 | Security protocols | SSO (SAML/OIDC) |

### Sub-Agent Task Template

When delegating:

```xml
<sub_agent_task>
  <phase>{phase}</phase>
  <plan>{plan}</plan>
  <focus>{specific_task}</focus>
  
  <context>
    @BRIEF.md
    @plans/{phase}/{plan}-PLAN.md
    @{relevant_existing_code}
  </context>
  
  <constraints>
    - Model: claude-opus-4-5-20251101
    - Extended thinking: enabled (16000 budget)
    - Complete task atomically
  </constraints>
  
  <return>
    - Files created/modified
    - Verification results
    - Deviations from plan
    - Blockers encountered
  </return>
</sub_agent_task>
```
</sub_agents>

---

## Execution Engine

<execution>
For each of the 58 plans, execute this sequence:

### Plan Execution Loop

```xml
<execute_plan phase="{N}" plan="{M}">

  <step name="load">
    1. Read plans/{phase}/{plan}-PLAN.md
    2. If dependent on prior plan, read prior SUMMARY.md
    3. Load referenced @context files
  </step>
  
  <step name="assess">
    4. Check if sub-agent delegation beneficial:
       - Context usage > 40% → delegate
       - Specialized domain → delegate
       - Complex integration → delegate
  </step>
  
  <step name="execute">
    5. Execute all tasks in the plan
    6. For each task:
       - Perform the <action>
       - Run the <verify> check
       - Log result
  </step>
  
  <step name="validate">
    7. Run plan's <verification> checklist
    8. If Playwright gate specified, run functional test
    9. On failure: attempt fix (max 2 retries), then log blocker
  </step>
  
  <step name="record">
    10. Create plans/{phase}/{plan}-SUMMARY.md:
        - Substantive one-liner outcome
        - Files created/modified
        - Verification results
        - Deviations with rationale
        - Next step
    11. Update PROGRESS.md
    12. Commit if git enabled
  </step>

</execute_plan>
```

### Progress Tracking

Maintain `PROGRESS.md` at the project root:

```markdown
# Code Story Implementation Progress

## Current State
- Active Phase: {N}-{phase_name}
- Active Plan: {plan}
- Last Completed: {timestamp}
- Overall: {done}/{total} plans ({percent}%)

## Phase Status
| Phase | Plans | Status |
|-------|-------|--------|
| 01-foundation | 5 | ✅ Complete |
| 02-intent-agent | 4 | 🔄 In Progress (2/4) |
| ... | ... | ... |

## Blockers
{List any blocking issues}

## Decisions Made
{Architectural decisions with rationale}
```

### Deviation Rules

Handle discoveries automatically:

| Rule | Trigger | Action |
|------|---------|--------|
| 1 | Bug found | Fix immediately, document in Summary |
| 2 | Security/correctness gap | Add fix immediately, document |
| 3 | Blocker encountered | Fix immediately, document |
| 4 | Major architectural change | **STOP** - ask user for decision |
| 5 | Nice-to-have discovered | Log to ISSUES.md, continue |

Only Rule 4 requires user intervention.
</execution>

---

## Phase Details

<phases>

### Phase 1: Foundation (5 plans)
- 01-01: Python project with uv, dependencies, structure
- 01-02: PostgreSQL schema, SQLAlchemy models, Alembic
- 01-03: Agent framework core (Skill, Agent, Orchestrator)
- 01-04: Environment config, secrets management
- 01-05: Base skill library, utilities

**Gate**: Project initializes, migrations run, agent framework instantiates

### Phase 2: Intent Agent (4 plans)
- 02-01: System prompt, Opus 4.5 config
- 02-02: Intent analysis skill
- 02-03: Story plan generation
- 02-04: Conversation flow

**Gate**: User intent → structured plan output

### Phase 3: Repo Analyzer (5 plans)
- 03-01: System prompt
- 03-02: GitHub API skill
- 03-03: AST analysis skill
- 03-04: Pattern recognition
- 03-05: Dependency mapping

**Gate**: GitHub URL → structured analysis JSON

### Phase 4: Story Architect (5 plans)
- 04-01: System prompt
- 04-02: Chapter script generation
- 04-03: Five narrative styles
- 04-04: Pacing calculation
- 04-05: Script assembly

**Gate**: Analysis + intent → narrative script

### Phase 5: Voice Director (4 plans)
- 05-01: System prompt
- 05-02: ElevenLabs integration
- 05-03: Script chunking
- 05-04: Audio assembly

**Gate**: Script → audio file (MP3)

### Phase 6: FastAPI Backend (6 plans)
- 06-01: App structure, routers, middleware
- 06-02: JWT authentication
- 06-03: Story CRUD endpoints
- 06-04: Redis + Celery job queue
- 06-05: WebSocket progress
- 06-06: S3 audio storage

**Gate**: Full user flow (register → login → submit → poll → download)

### Phase 7: React Frontend (6 plans)
- 07-01: Vite + Tailwind + shadcn/ui
- 07-02: Landing, auth screens
- 07-03: Repo input form
- 07-04: Intent chat interface
- 07-05: Dashboard, story list
- 07-06: Audio player

**Gate**: End-to-end web journey

### Phase 8: Expo Mobile (5 plans)
- 08-01: Expo + NativeWind setup
- 08-02: Auth screens
- 08-03: Home, new story flow
- 08-04: Chat interface
- 08-05: Audio player, background playback

**Gate**: Mobile web view flow

### Phase 9: Full Experience (4 plans)
- 09-01: All 5 narrative styles
- 09-02: Chapter editing
- 09-03: Voice selection
- 09-04: Sharing, downloads

**Gate**: All styles, customization, sharing work

### Phase 10: API & Docs (4 plans)
- 10-01: API key generation
- 10-02: Rate limiting
- 10-03: OpenAPI documentation
- 10-04: Developer portal

**Gate**: API key → authenticated request → rate limited

### Phase 11: Admin Dashboard (4 plans)
- 11-01: Admin auth
- 11-02: User management
- 11-03: Usage analytics
- 11-04: Audit logs

**Gate**: Admin login → manage users → view analytics

### Phase 12: Self-Hosting (3 plans)
- 12-01: Docker Compose (dev)
- 12-02: Production Docker images
- 12-03: Kubernetes + Helm

**Gate**: Docker stack starts and serves

### Phase 13: Enterprise (3 plans)
- 13-01: Team/org model
- 13-02: Team collaboration
- 13-03: SSO preparation

**Gate**: Team creation → members → shared access

</phases>

---

## Context Management

<context_management>

### Token Budget Awareness

| Context Level | Quality | Action |
|---------------|---------|--------|
| 0-30% | Peak | Full analysis, comprehensive work |
| 30-50% | Good | Continue with focus |
| 50-70% | Degrading | Consider sub-agent delegation |
| 70%+ | Critical | **STOP**, create handoff, spawn fresh agent |

### Handoff Protocol

When approaching limits or pausing:

```markdown
# Continue Here - Phase {N}, Plan {M}

## State
- Last completed task: {task}
- Files modified: {list}
- Uncommitted changes: {yes/no}

## Context
- Decisions made: {list}
- Blockers: {list}
- Deviations: {list}

## Resume Instructions
1. Read this file
2. Read PROGRESS.md
3. Read plans/{phase}/{plan}-PLAN.md
4. Continue from task {X}
```

Save to: `plans/{phase}/CONTINUE-{plan}.md`
</context_management>

---

## Verification Protocol

<verification>

### After Each Plan
- [ ] All tasks completed per specification
- [ ] All <verify> checks pass
- [ ] SUMMARY.md created with substantive one-liner
- [ ] PROGRESS.md updated

### After Each Phase
- [ ] All plans in phase complete
- [ ] Phase validation gate passes
- [ ] No unresolved blockers

### Final Verification
- [ ] All 58 plans complete
- [ ] All 13 phase gates pass
- [ ] End-to-end flow works:
  - User registers → logs in
  - Submits GitHub URL
  - Completes intent conversation
  - Story generates (all agents execute)
  - Audio plays in web and mobile
  - API key works externally
  - Admin can manage users
  - Docker deployment works
</verification>

---

## Success Criteria

<success_criteria>
- All 58 plans executed with SUMMARY.md
- All 13 phase validation gates pass
- 4-agent pipeline produces audio from any public GitHub repo
- Web and mobile apps functional
- Public API documented and rate-limited
- Self-hosting deployment tested
- Code: type-checked, linted, tested
</success_criteria>

---

## Output

<output>
On completion, create `COMPLETION.md`:

```markdown
# Code Story Implementation Complete

## Summary
{What was built}

## Statistics
- Plans completed: 58/58
- Duration: {time}
- Files created: {count}

## Architecture
{Final architecture diagram}

## Key Decisions
{Major decisions made}

## Known Limitations
{Deferred items}

## Next Steps
{v2.0 recommendations}
```

Git tag: `v1.0.0`
</output>

---

## Emergency Procedures

<emergency>

### Validation Fails Repeatedly
1. Log failure in PROGRESS.md
2. Check for missed dependency
3. Attempt fix (max 2 tries)
4. If still failing: create blocker, skip to next independent plan

### External Service Down
- ElevenLabs: Mock audio, continue other work
- GitHub API: Use cached responses
- Database: Fix before proceeding (critical)

### Context Limit Approaching
1. Create handoff file immediately
2. Commit current state
3. Update PROGRESS.md
4. **STOP** - do not degrade quality
</emergency>

---

<final_instruction>
Begin execution now. Read all 58 plans from the plans/ directory, synthesize the complete architecture, then execute sequentially starting from Phase 1, Plan 01 (or resume point if PROGRESS.md exists). Spawn sub-agents for complex phases. Track progress. Create handoffs if needed. Build the complete Code Story platform.
</final_instruction>
