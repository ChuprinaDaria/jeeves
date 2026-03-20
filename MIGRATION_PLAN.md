# Nexelin AI — Full Architecture & Migration Plan

## Vision

Production-ready multi-agent AI platform where:
- **Orchestrator** receives any request and decides which agents to invoke
- **Agents are added at runtime** — paste an API URL + JSON schema in admin, agent is live
- **Agents self-improve** — analyze their own logs, adjust prompts/config, learn from feedback
- **A2A ready** — agents communicate with each other and with external agent systems
- **MCP standard** — every agent is an MCP server, orchestrator is MCP client
- **Django monolith** handles config, admin, auth, billing — microservices handle AI work

**Supported languages:** en, de, fr, es, it, nl, da

---

## Architecture Overview

```
                         +-------------------+
                         |    API Gateway     |
                         |     (nginx)        |
                         +---------+---------+
                                   |
                    +--------------+--------------+
                    |                             |
          +---------v---------+         +---------v---------+
          |   Django Monolith  |         |   Agent Mesh       |
          |                    |         |                    |
          |  - Admin panel     |         |  Orchestrator      |
          |  - Auth / Users    |         |    |               |
          |  - Client config   |  <--->  |    +-- SearchAgent |
          |  - Agent registry  |  Redis  |    +-- RerankAgent |
          |  - Billing / Stats |  Queue  |    +-- LLMAgent    |
          |  - Channel gateway |         |    +-- HITLAgent   |
          |  - Audit log       |         |    +-- EmailAgent  |
          |                    |         |    +-- CalendarAgent|
          +--------+-----------+         |    +-- CustomAgent |
                   |                     |    +-- ... (any)   |
          +--------v-----------+         +---------+----------+
          |   PostgreSQL       |                   |
          |   - config         |         +---------v----------+
          |   - users          |         |   Vector Store      |
          |   - conversations  |         |   (Qdrant)          |
          |   - agent cards    |         +--------------------+
          |   - agent logs     |
          |   - audit trail    |
          +--------------------+
          |   Redis            |
          |   - cache          |
          |   - Celery broker  |
          |   - agent comms    |
          +--------------------+
```

---

## Core Concept: Agent as a Service

Every agent in the system — internal or external — follows one contract:

```
INPUT:  AgentRequest  (JSON-RPC 2.0 / MCP compatible)
OUTPUT: AgentResponse (JSON-RPC 2.0 / MCP compatible)
CONFIG: AgentCard     (stored in DB, editable in admin)
LOGS:   AgentLog      (every call logged for self-tuning)
```

Adding a new agent = creating an AgentCard record in admin:
1. Name, description
2. Input JSON schema
3. Output JSON schema
4. Endpoint URL (internal or external)
5. System prompt (if LLM-based)
6. Config (temperature, top_k, etc.)

No code changes. No deployment. The orchestrator discovers it and can route to it.

---

## PART 1 — AGENT SYSTEM (the core)

### 1.1 AgentCard — Agent Definition

```python
class AgentCard(models.Model):
    """
    Single source of truth for every agent in the system.
    Add a record here = add an agent. No code needed.
    """
    # Identity
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    version = models.CharField(max_length=20, default='1.0')

    # Contract (JSON Schema)
    input_schema = models.JSONField(default=dict,
        help_text="JSON Schema defining expected input format")
    output_schema = models.JSONField(default=dict,
        help_text="JSON Schema defining output format")

    # Execution
    agent_type = models.CharField(max_length=20, choices=[
        ('internal', 'Internal Python class'),
        ('http', 'External HTTP endpoint'),
        ('celery', 'Celery async task'),
        ('mcp', 'MCP server'),
    ])
    endpoint = models.CharField(max_length=500, blank=True,
        help_text="URL for http/mcp agents, task path for celery agents")
    internal_class = models.CharField(max_length=200, blank=True,
        help_text="Python dotted path for internal agents: agents.builtin.SearchAgent")
    http_method = models.CharField(max_length=10, default='POST')
    http_headers = models.JSONField(default=dict, blank=True,
        help_text="Custom headers for HTTP agents (auth tokens, etc.)")
    timeout_seconds = models.IntegerField(default=30)

    # AI Configuration (editable in admin — this is what self-tuning changes)
    system_prompt = models.TextField(blank=True)
    config = models.JSONField(default=dict,
        help_text="Agent-specific config: temperature, top_k, model, weights, etc.")

    # Orchestration
    priority = models.IntegerField(default=0,
        help_text="Higher priority = preferred when multiple agents can handle a task")
    capabilities = models.JSONField(default=list,
        help_text="List of capability tags: ['search', 'translate', 'rerank']")
    depends_on = models.ManyToManyField('self', blank=True, symmetrical=False,
        help_text="Agents that must run before this one")
    max_concurrent = models.IntegerField(default=10,
        help_text="Max parallel executions")

    # Health
    is_active = models.BooleanField(default=True)
    health_check_url = models.CharField(max_length=500, blank=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_status = models.CharField(max_length=20, default='unknown', choices=[
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('unhealthy', 'Unhealthy'),
        ('unknown', 'Unknown'),
    ])
    consecutive_failures = models.IntegerField(default=0)
    fallback_agent = models.ForeignKey('self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fallback_for',
        help_text="Agent to use if this one fails")

    # Self-tuning metadata
    tuning_enabled = models.BooleanField(default=False,
        help_text="Allow self-tuning to modify this agent's config")
    tuning_config = models.JSONField(default=dict,
        help_text="What can be tuned: {'temperature': [0.1, 1.0], 'top_k': [3, 20]}")
    last_tuned_at = models.DateTimeField(null=True, blank=True)

    # Versioning (for rollback)
    config_history = models.JSONField(default=list,
        help_text="History of config changes: [{date, config, reason, score_before, score_after}]")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'agent_type']),
            models.Index(fields=['health_status']),
        ]
```

### 1.2 AgentLog — Every Call Logged

```python
class AgentLog(models.Model):
    """
    Every agent invocation is logged.
    This is the data source for self-tuning and analytics.
    """
    agent = models.ForeignKey(AgentCard, on_delete=models.CASCADE, related_name='logs')
    task_id = models.UUIDField(db_index=True,
        help_text="Shared across all agents in one orchestration chain")
    parent_task_id = models.UUIDField(null=True, blank=True,
        help_text="Task that spawned this one (for tracing)")
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE)

    # Request/Response
    input_data = models.JSONField()
    output_data = models.JSONField(null=True)
    context = models.JSONField(default=dict,
        help_text="Orchestration context: language, channel, session_id, etc.")

    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('fallback', 'Fell back to another agent'),
    ])
    error_message = models.TextField(blank=True)
    fallback_agent = models.ForeignKey(AgentCard, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fallback_logs')

    # Performance
    latency_ms = models.IntegerField(null=True)
    tokens_used = models.IntegerField(null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    model_used = models.CharField(max_length=100, blank=True)

    # Feedback (for self-tuning)
    feedback_score = models.FloatField(null=True, blank=True,
        help_text="-1.0 to 1.0 — negative=bad, positive=good")
    feedback_source = models.CharField(max_length=20, blank=True, choices=[
        ('user', 'User explicit feedback'),
        ('implicit', 'Implicit — escalation triggered = bad'),
        ('auto', 'Automated quality check'),
    ])

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['agent', 'created_at']),
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['task_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['feedback_score']),
        ]
```

### 1.3 Agent Executor — Unified Invocation

```python
# agents/executor.py
class AgentExecutor:
    """
    Executes any agent regardless of type.
    Handles: internal class, HTTP call, Celery task, MCP server.
    """

    @staticmethod
    async def execute(agent: AgentCard, request: AgentRequest) -> AgentResponse:
        log = AgentLog.objects.create(
            agent=agent,
            task_id=request.id,
            parent_task_id=request.params.get('parent_task_id'),
            client_id=request.params['context']['client_id'],
            input_data=request.params,
            context=request.params.get('context', {}),
            status='running',
        )

        start = time.monotonic()
        try:
            if agent.agent_type == 'internal':
                result = await _execute_internal(agent, request)
            elif agent.agent_type == 'http':
                result = await _execute_http(agent, request)
            elif agent.agent_type == 'celery':
                result = await _execute_celery(agent, request)
            elif agent.agent_type == 'mcp':
                result = await _execute_mcp(agent, request)

            log.output_data = result
            log.status = 'completed'
            log.latency_ms = int((time.monotonic() - start) * 1000)
            log.save()
            return AgentResponse(result=result, id=request.id)

        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            log.latency_ms = int((time.monotonic() - start) * 1000)
            log.save()

            # Fallback
            if agent.fallback_agent and agent.fallback_agent.is_active:
                log.status = 'fallback'
                log.fallback_agent = agent.fallback_agent
                log.save()
                return await AgentExecutor.execute(agent.fallback_agent, request)

            return AgentResponse(error={'code': -1, 'message': str(e)}, id=request.id)


    @staticmethod
    async def _execute_http(agent: AgentCard, request: AgentRequest) -> dict:
        """Call any external agent via HTTP — this is how you add agents from admin"""
        async with httpx.AsyncClient(timeout=agent.timeout_seconds) as client:
            response = await client.request(
                method=agent.http_method,
                url=agent.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": "agent/execute",
                    "params": request.params,
                    "id": str(request.id),
                },
                headers=agent.http_headers,
            )
            response.raise_for_status()
            return response.json().get('result', response.json())


    @staticmethod
    async def _execute_mcp(agent: AgentCard, request: AgentRequest) -> dict:
        """Call MCP-compatible server"""
        async with httpx.AsyncClient(timeout=agent.timeout_seconds) as client:
            response = await client.post(
                agent.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": request.params.get('method', 'agent/execute'),
                    "params": request.params,
                    "id": str(request.id),
                },
                headers={**agent.http_headers, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            body = response.json()
            if 'error' in body:
                raise Exception(body['error'].get('message', 'MCP error'))
            return body.get('result', body)


    @staticmethod
    async def _execute_internal(agent: AgentCard, request: AgentRequest) -> dict:
        """Call internal Python agent class"""
        module_path, class_name = agent.internal_class.rsplit('.', 1)
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)
        instance = agent_class(config=agent.config, system_prompt=agent.system_prompt)
        return await instance.execute(request.params)


    @staticmethod
    async def _execute_celery(agent: AgentCard, request: AgentRequest) -> dict:
        """Dispatch to Celery for long-running tasks"""
        from celery import current_app
        task = current_app.send_task(
            agent.endpoint,  # e.g. 'agents.tasks.process_document'
            kwargs={'params': request.params},
        )
        result = task.get(timeout=agent.timeout_seconds)
        return result
```

### 1.4 Orchestrator — The Brain

```python
# agents/orchestrator.py
class Orchestrator:
    """
    Receives a user request.
    Decides which agents to call and in what order.
    Handles parallel execution, dependencies, result aggregation.

    The orchestrator itself is an AgentCard in the DB — its behavior
    is configurable from admin (system_prompt, routing rules).
    """

    def __init__(self):
        self.executor = AgentExecutor()

    async def process(self, request: dict) -> dict:
        """
        Main entry point. Called from PublicRAGChatView.

        request = {
            'query': str,
            'client_id': int,
            'language': str,
            'session_id': str,
            'channel': str,
            'attachments': list,
        }
        """
        task_id = str(uuid4())
        context = {
            'client_id': request['client_id'],
            'language': request.get('language', 'en'),
            'session_id': request.get('session_id'),
            'channel': request.get('channel', 'api'),
            'task_id': task_id,
        }

        # Step 1: Build execution plan
        plan = await self._build_plan(request, context)

        # Step 2: Execute plan (respects dependencies, parallelizes where possible)
        results = await self._execute_plan(plan, context)

        # Step 3: Compose final response
        return await self._compose_response(results, context)


    async def _build_plan(self, request: dict, context: dict) -> list[dict]:
        """
        Determine which agents to call based on:
        1. Request content (query, attachments, intent)
        2. Client configuration
        3. Agent capabilities and dependencies
        4. Orchestrator's own system_prompt (configurable in admin)

        Returns execution plan:
        [
            {'step': 1, 'agents': ['search'], 'parallel': False},
            {'step': 2, 'agents': ['rerank'], 'parallel': False},
            {'step': 3, 'agents': ['response', 'translation'], 'parallel': True},
        ]
        """
        # Load orchestrator config from DB
        orch_card = await self._get_orchestrator_card()
        routing_rules = orch_card.config.get('routing_rules', {})

        # Default RAG pipeline
        plan = [
            {'step': 1, 'agents': ['search'], 'parallel': False},
            {'step': 2, 'agents': ['rerank'], 'parallel': False, 'optional': True},
            {'step': 3, 'agents': ['response'], 'parallel': False},
        ]

        # Check if escalation agent should be added
        client = await self._get_client(context['client_id'])
        if hasattr(client, 'hitl_config') and client.hitl_config.enabled:
            plan.append({
                'step': 4, 'agents': ['escalation'], 'parallel': False,
                'condition': 'response.requires_escalation'
            })

        # Check for custom routing rules from admin config
        for rule in routing_rules.get('rules', []):
            if self._matches_rule(request, rule):
                plan = rule['plan']
                break

        return plan


    async def _execute_plan(self, plan: list[dict], context: dict) -> dict:
        """Execute plan step by step. Parallel steps run concurrently."""
        results = {}

        for step in plan:
            # Check condition
            if 'condition' in step:
                if not self._evaluate_condition(step['condition'], results):
                    continue

            agents = []
            for slug in step['agents']:
                card = await self._get_agent_card(slug)
                if card and card.is_active and card.health_status != 'unhealthy':
                    agents.append(card)

            if not agents:
                if not step.get('optional', False):
                    raise Exception(f"No active agents for step {step['step']}: {step['agents']}")
                continue

            if step.get('parallel', False) and len(agents) > 1:
                # Run in parallel
                tasks = [
                    self.executor.execute(
                        agent,
                        AgentRequest(
                            params={
                                'input': self._prepare_input(agent, results, context),
                                'context': context,
                            },
                            id=f"{context['task_id']}-{agent.slug}",
                        )
                    )
                    for agent in agents
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                for agent, response in zip(agents, responses):
                    if isinstance(response, Exception):
                        results[agent.slug] = {'error': str(response)}
                    else:
                        results[agent.slug] = response.result
            else:
                # Run sequentially
                for agent in agents:
                    response = await self.executor.execute(
                        agent,
                        AgentRequest(
                            params={
                                'input': self._prepare_input(agent, results, context),
                                'context': context,
                            },
                            id=f"{context['task_id']}-{agent.slug}",
                        )
                    )
                    results[agent.slug] = response.result if response.result else response.error

        return results


    async def _compose_response(self, results: dict, context: dict) -> dict:
        """Assemble final response from agent results"""
        response = {
            'task_id': context['task_id'],
            'answer': '',
            'sources': [],
            'language': context.get('language', 'en'),
            'agents_used': list(results.keys()),
        }

        if 'response' in results and results['response']:
            response['answer'] = results['response'].get('answer', '')
            response['sources'] = results['response'].get('sources', [])
            response['tokens_used'] = results['response'].get('tokens_used', 0)

        if 'escalation' in results and results['escalation']:
            response['requires_escalation'] = results['escalation'].get('requires_escalation', False)
            response['escalation_summary'] = results['escalation'].get('summary', '')

        return response


    def _prepare_input(self, agent: AgentCard, previous_results: dict, context: dict) -> dict:
        """
        Wire agent inputs from previous agent outputs.
        SearchAgent output -> RerankAgent input -> ResponseAgent input
        """
        input_data = {}

        # Auto-wire based on dependencies
        for dep in agent.depends_on.all():
            if dep.slug in previous_results:
                input_data[dep.slug] = previous_results[dep.slug]

        # Add query from context
        input_data['query'] = context.get('query', '')
        input_data['language'] = context.get('language', 'en')

        return input_data
```

### 1.5 Health Monitor

```python
# agents/health.py  (Celery beat task)

@shared_task
def check_agent_health():
    """
    Runs every 60 seconds via Celery beat.
    Checks health of all active agents with health_check_url.
    Updates health_status and consecutive_failures.
    Disables agents after 5 consecutive failures.
    """
    agents = AgentCard.objects.filter(is_active=True).exclude(health_check_url='')

    for agent in agents:
        try:
            response = httpx.get(agent.health_check_url, timeout=5)
            if response.status_code == 200:
                agent.health_status = 'healthy'
                agent.consecutive_failures = 0
            else:
                agent.health_status = 'degraded'
                agent.consecutive_failures += 1
        except Exception:
            agent.health_status = 'unhealthy'
            agent.consecutive_failures += 1

        if agent.consecutive_failures >= 5:
            agent.is_active = False
            # TODO: notify admin

        agent.last_health_check = timezone.now()
        agent.save(update_fields=[
            'health_status', 'consecutive_failures',
            'last_health_check', 'is_active',
        ])
```

### 1.6 Self-Tuning Engine

```python
# agents/tuning.py  (Celery beat task — runs daily)

@shared_task
def self_tune_agents():
    """
    Analyzes agent logs from the last 7 days.
    Identifies patterns in failures and low scores.
    Adjusts agent config (temperature, prompts, weights) automatically.
    Saves config history for rollback.
    """
    agents = AgentCard.objects.filter(tuning_enabled=True, is_active=True)

    for agent in agents:
        logs = AgentLog.objects.filter(
            agent=agent,
            created_at__gte=timezone.now() - timedelta(days=7),
        )

        total = logs.count()
        if total < 50:  # Not enough data to tune
            continue

        # Calculate metrics
        metrics = _calculate_metrics(logs)

        # Decide adjustments
        adjustments = _decide_adjustments(agent, metrics)

        if adjustments:
            _apply_adjustments(agent, adjustments, metrics)


def _calculate_metrics(logs) -> dict:
    """Aggregate log data into tuning metrics"""
    return {
        'total_calls': logs.count(),
        'failure_rate': logs.filter(status='failed').count() / max(logs.count(), 1),
        'timeout_rate': logs.filter(status='timeout').count() / max(logs.count(), 1),
        'avg_latency_ms': logs.filter(latency_ms__isnull=False).aggregate(
            avg=Avg('latency_ms'))['avg'] or 0,
        'avg_feedback': logs.filter(feedback_score__isnull=False).aggregate(
            avg=Avg('feedback_score'))['avg'] or 0,
        'escalation_rate': logs.filter(
            output_data__requires_escalation=True).count() / max(logs.count(), 1),
        'fallback_rate': logs.filter(status='fallback').count() / max(logs.count(), 1),
        'feedback_distribution': {
            'positive': logs.filter(feedback_score__gt=0).count(),
            'negative': logs.filter(feedback_score__lt=0).count(),
            'neutral': logs.filter(feedback_score=0).count(),
        },
    }


def _decide_adjustments(agent: AgentCard, metrics: dict) -> dict:
    """
    Rule-based tuning decisions.
    Later: replace with LLM-based analysis of failure patterns.
    """
    adjustments = {}
    tunable = agent.tuning_config  # e.g. {'temperature': [0.1, 1.0], 'top_k': [3, 20]}
    current = agent.config

    # High failure rate -> lower temperature (more conservative)
    if metrics['failure_rate'] > 0.15 and 'temperature' in tunable:
        min_val, max_val = tunable['temperature']
        current_temp = current.get('temperature', 0.7)
        adjustments['temperature'] = max(min_val, current_temp - 0.1)

    # Low feedback score -> adjust system prompt
    if metrics['avg_feedback'] < -0.3:
        adjustments['_flag_prompt_review'] = True

    # High latency -> reduce max_tokens or context
    if metrics['avg_latency_ms'] > 5000 and 'max_tokens' in tunable:
        min_val, max_val = tunable['max_tokens']
        current_tokens = current.get('max_tokens', 2000)
        adjustments['max_tokens'] = max(min_val, current_tokens - 200)

    # High escalation rate -> increase top_k (more context)
    if metrics['escalation_rate'] > 0.3 and 'top_k' in tunable:
        min_val, max_val = tunable['top_k']
        current_k = current.get('top_k', 5)
        adjustments['top_k'] = min(max_val, current_k + 2)

    # Low timeout rate but high latency -> increase timeout
    if metrics['timeout_rate'] > 0.1:
        adjustments['timeout_increase'] = True

    return adjustments


def _apply_adjustments(agent: AgentCard, adjustments: dict, metrics: dict):
    """Apply adjustments and save history for rollback"""
    old_config = agent.config.copy()

    for key, value in adjustments.items():
        if key.startswith('_flag_'):
            continue  # Flags are for admin notification, not direct changes
        agent.config[key] = value

    # Save history (for rollback)
    history_entry = {
        'date': timezone.now().isoformat(),
        'old_config': old_config,
        'new_config': agent.config.copy(),
        'adjustments': adjustments,
        'metrics_snapshot': metrics,
        'reason': 'auto_tuning',
    }
    if not agent.config_history:
        agent.config_history = []
    agent.config_history.append(history_entry)

    # Keep only last 20 entries
    agent.config_history = agent.config_history[-20:]
    agent.last_tuned_at = timezone.now()
    agent.save()
```

### 1.7 Self-Learning — Prompt Evolution

```python
# agents/learning.py  (Celery beat task — runs weekly)

@shared_task
def evolve_agent_prompts():
    """
    Uses LLM to analyze failure patterns and suggest prompt improvements.
    Only for agents with tuning_enabled=True and enough negative feedback.

    Flow:
    1. Collect last 7 days of negative-feedback logs
    2. Group by failure pattern (similar inputs, similar errors)
    3. Ask LLM to suggest prompt modifications
    4. Store suggestion in AgentCard.config['pending_prompt_suggestions']
    5. Admin reviews and approves (or auto-apply if configured)
    """
    agents = AgentCard.objects.filter(tuning_enabled=True, is_active=True)

    for agent in agents:
        negative_logs = AgentLog.objects.filter(
            agent=agent,
            created_at__gte=timezone.now() - timedelta(days=7),
            feedback_score__lt=0,
        ).order_by('-created_at')[:50]

        if negative_logs.count() < 10:
            continue

        # Build analysis prompt
        analysis_prompt = _build_analysis_prompt(agent, negative_logs)

        # Call LLM for analysis (using default LLM provider)
        suggestion = _get_llm_suggestion(analysis_prompt)

        if suggestion:
            # Store for admin review
            pending = agent.config.get('pending_prompt_suggestions', [])
            pending.append({
                'date': timezone.now().isoformat(),
                'suggestion': suggestion,
                'based_on_logs': negative_logs.count(),
                'current_avg_feedback': AgentLog.objects.filter(
                    agent=agent,
                    feedback_score__isnull=False,
                    created_at__gte=timezone.now() - timedelta(days=7),
                ).aggregate(avg=Avg('feedback_score'))['avg'],
            })
            agent.config['pending_prompt_suggestions'] = pending[-5:]  # Keep last 5
            agent.save(update_fields=['config'])

            # If auto-apply is enabled
            if agent.tuning_config.get('auto_apply_prompts', False):
                _auto_apply_prompt_suggestion(agent, suggestion)


def _build_analysis_prompt(agent: AgentCard, logs) -> str:
    """Build prompt for LLM to analyze failure patterns"""
    examples = []
    for log in logs[:20]:
        examples.append({
            'input': log.input_data.get('input', {}).get('query', ''),
            'output': str(log.output_data)[:200] if log.output_data else 'None',
            'error': log.error_message[:200] if log.error_message else '',
            'feedback': log.feedback_score,
        })

    return f"""Analyze these failed/low-rated interactions for agent "{agent.name}".

Current system prompt:
{agent.system_prompt}

Current config:
{json.dumps(agent.config, indent=2)}

Failed interactions:
{json.dumps(examples, indent=2)}

Suggest specific improvements to the system prompt that would prevent these failures.
Return JSON: {{"improved_prompt": "...", "reasoning": "...", "expected_improvement": "..."}}"""
```

---

## PART 2 — A2A & MCP PROTOCOL

### 2.1 A2A Endpoints

```python
# agents/api.py — public endpoints for agent discovery and execution

# GET /api/agents/
# Returns list of all active agents (A2A discovery)
class AgentListView(APIView):
    def get(self, request):
        agents = AgentCard.objects.filter(is_active=True)
        return Response([{
            'name': a.name,
            'slug': a.slug,
            'description': a.description,
            'version': a.version,
            'capabilities': a.capabilities,
            'endpoint': f'/api/agents/{a.slug}/execute',
            'card': f'/api/agents/{a.slug}/card',
        } for a in agents])


# GET /api/agents/{slug}/card
# Returns full agent card (A2A agent descriptor)
class AgentCardView(APIView):
    def get(self, request, slug):
        agent = get_object_or_404(AgentCard, slug=slug, is_active=True)
        return Response({
            'name': agent.name,
            'description': agent.description,
            'version': agent.version,
            'input_schema': agent.input_schema,
            'output_schema': agent.output_schema,
            'capabilities': agent.capabilities,
            'endpoint': f'/api/agents/{slug}/execute',
            'health': agent.health_status,
        })


# POST /api/agents/{slug}/execute
# Execute an agent (A2A invocation)
class AgentExecuteView(APIView):
    authentication_classes = [ClientAPIKeyAuthentication]

    async def post(self, request, slug):
        agent = get_object_or_404(AgentCard, slug=slug, is_active=True)

        # Validate input against schema
        validate_json_schema(request.data.get('params', {}), agent.input_schema)

        agent_request = AgentRequest(
            method='agent/execute',
            params=request.data.get('params', {}),
            id=request.data.get('id', str(uuid4())),
        )

        response = await AgentExecutor.execute(agent, agent_request)
        return Response(asdict(response))
```

### 2.2 MCP Server Wrapper

Each internal agent can be exposed as MCP server:

```python
# agents/mcp_wrapper.py
class MCPAgentServer:
    """
    Wraps any AgentCard as an MCP-compatible server.
    Handles: initialize, tools/list, tools/call
    """

    def __init__(self, agent: AgentCard):
        self.agent = agent

    async def handle_request(self, request: dict) -> dict:
        method = request.get('method', '')

        if method == 'initialize':
            return {
                'jsonrpc': '2.0',
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {'tools': {}},
                    'serverInfo': {
                        'name': self.agent.name,
                        'version': self.agent.version,
                    },
                },
                'id': request.get('id'),
            }

        elif method == 'tools/list':
            return {
                'jsonrpc': '2.0',
                'result': {
                    'tools': [{
                        'name': self.agent.slug,
                        'description': self.agent.description,
                        'inputSchema': self.agent.input_schema,
                    }],
                },
                'id': request.get('id'),
            }

        elif method == 'tools/call':
            params = request.get('params', {})
            agent_request = AgentRequest(
                method='agent/execute',
                params={'input': params.get('arguments', {}), 'context': {}},
                id=request.get('id', str(uuid4())),
            )
            response = await AgentExecutor.execute(self.agent, agent_request)
            return {
                'jsonrpc': '2.0',
                'result': {
                    'content': [{'type': 'text', 'text': json.dumps(response.result)}],
                },
                'id': request.get('id'),
            }
```

### 2.3 MCP Client — Call External MCP Servers

```python
# agents/mcp_client.py
class MCPClient:
    """
    Orchestrator uses this to call external MCP servers.
    Registered via AgentCard with agent_type='mcp'.
    """

    def __init__(self, endpoint: str, headers: dict = None):
        self.endpoint = endpoint
        self.headers = headers or {}

    async def initialize(self) -> dict:
        return await self._call('initialize', {})

    async def list_tools(self) -> list[dict]:
        response = await self._call('tools/list', {})
        return response.get('tools', [])

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return await self._call('tools/call', {
            'name': tool_name,
            'arguments': arguments,
        })

    async def _call(self, method: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.endpoint,
                json={'jsonrpc': '2.0', 'method': method, 'params': params, 'id': str(uuid4())},
                headers={**self.headers, 'Content-Type': 'application/json'},
            )
            response.raise_for_status()
            body = response.json()
            if 'error' in body:
                raise Exception(body['error'].get('message', 'MCP error'))
            return body.get('result', body)
```

---

## PART 3 — BUILT-IN AGENTS

These are the initial internal agents. Each follows the same contract.

### 3.1 Base Agent Class

```python
# agents/base.py
class BaseAgent(ABC):
    """All internal agents inherit from this"""

    def __init__(self, config: dict = None, system_prompt: str = ''):
        self.config = config or {}
        self.system_prompt = system_prompt

    @abstractmethod
    async def execute(self, params: dict) -> dict:
        """
        params = {
            'input': {...},      # Agent-specific input
            'context': {         # Shared context
                'client_id': int,
                'language': str,
                'session_id': str,
                'channel': str,
                'task_id': str,
            }
        }
        Returns: dict matching agent's output_schema
        """
        ...
```

### 3.2 SearchAgent

```python
# agents/builtin/search.py
class SearchAgent(BaseAgent):
    """Vector search across knowledge base"""

    async def execute(self, params: dict) -> dict:
        query = params['input']['query']
        client_id = params['context']['client_id']
        top_k = self.config.get('top_k', 5)

        client = await Client.objects.select_related(
            'branch', 'specialization', 'embedding_model'
        ).aget(id=client_id)

        # Create embedding
        embedding_service = EmbeddingService()
        embedding = await embedding_service.create_embedding(
            query, client.get_embedding_model())

        # Search via VectorStore abstraction
        store = get_vector_store()  # PgVectorStore or QdrantStore
        results = await store.search(
            query_vector=embedding['vector'],
            filters={
                'client_id': client_id,
                'branch_id': client.branch_id,
                'specialization_id': client.specialization_id,
            },
            top_k=top_k,
        )

        return {
            'chunks': [asdict(r) for r in results],
            'query_embedding_tokens': embedding['token_count'],
        }
```

### 3.3 RerankAgent

```python
# agents/builtin/rerank.py
class RerankAgent(BaseAgent):
    """Cohere rerank of search results"""

    async def execute(self, params: dict) -> dict:
        query = params['input'].get('query', '')
        chunks = params['input'].get('search', {}).get('chunks', [])
        top_n = self.config.get('top_n', 5)

        if not chunks:
            return {'ranked_chunks': []}

        # Call Cohere rerank
        co = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
        try:
            results = await co.rerank(
                query=query,
                documents=[c['content'] for c in chunks],
                top_n=top_n,
                model=self.config.get('model', 'rerank-multilingual-v3.0'),
            )
            ranked = []
            for r in results.results:
                chunk = chunks[r.index]
                chunk['rerank_score'] = r.relevance_score
                ranked.append(chunk)
            return {'ranked_chunks': ranked}
        except Exception:
            # Fallback: return original order, top_n
            return {'ranked_chunks': chunks[:top_n]}
```

### 3.4 ResponseAgent (LLM)

```python
# agents/builtin/response.py
class ResponseAgent(BaseAgent):
    """LLM response generation"""

    async def execute(self, params: dict) -> dict:
        query = params['input']['query']
        language = params['context'].get('language', 'en')
        client_id = params['context']['client_id']

        # Get chunks from previous agents
        chunks = (
            params['input'].get('rerank', {}).get('ranked_chunks') or
            params['input'].get('search', {}).get('chunks') or
            []
        )

        # Build context from chunks
        context_text = self._build_context(chunks)

        # Get LLM provider for this client
        client = await Client.objects.select_related('llm_provider_model').aget(id=client_id)
        provider = self._get_provider(client)

        # Generate response
        system_prompt = self.system_prompt or client.custom_system_prompt or ''
        result = await provider.generate_response(
            user_query=query,
            context=context_text,
            system_prompt=system_prompt,
            language=language,
            temperature=self.config.get('temperature', 0.7),
            max_tokens=self.config.get('max_tokens', 2000),
        )

        return {
            'answer': result['text'],
            'sources': [c['metadata'] for c in chunks if 'metadata' in c],
            'tokens_used': result.get('tokens_used', 0),
            'model_used': result.get('model', ''),
        }
```

### 3.5 EscalationAgent

```python
# agents/builtin/escalation.py
class EscalationAgent(BaseAgent):
    """
    Detects if LLM response indicates need for human help.
    Triggers HITL escalation if needed.
    """

    async def execute(self, params: dict) -> dict:
        answer = params['input'].get('response', {}).get('answer', '')
        client_id = params['context']['client_id']

        # Check for escalation markers
        requires_escalation = False
        reason = ''

        # 1. Explicit marker from LLM
        if '[[ESCALATE_TO_MANAGER]]' in answer:
            requires_escalation = True
            reason = 'llm_explicit_marker'
            answer = answer.replace('[[ESCALATE_TO_MANAGER]]', '').strip()

        # 2. Refusal phrase detection (from SystemMessage, not hardcoded)
        if not requires_escalation:
            refusal_phrases = SystemMessage.get('refusal_phrases', 'en')
            if refusal_phrases:
                phrases = [p.strip() for p in refusal_phrases.split('\n') if p.strip()]
                answer_lower = answer.lower()
                for phrase in phrases:
                    if phrase.lower() in answer_lower:
                        requires_escalation = True
                        reason = f'refusal_phrase: {phrase}'
                        break

        # 3. Low confidence from search results
        chunks = params['input'].get('search', {}).get('chunks', [])
        if chunks:
            avg_similarity = sum(c.get('similarity', 0) for c in chunks) / len(chunks)
            threshold = self.config.get('low_confidence_threshold', 0.3)
            if avg_similarity < threshold:
                requires_escalation = True
                reason = f'low_similarity: {avg_similarity:.2f}'

        return {
            'requires_escalation': requires_escalation,
            'reason': reason,
            'cleaned_answer': answer,
            'summary': self._build_summary(params) if requires_escalation else '',
        }
```

---

## PART 4 — CLEANUP & REFACTORING (from original plan)

### 4.1 Credentials and Secrets

- [ ] `.env.example` — replace real Meta credentials with `YOUR_*` placeholders
- [ ] Rotate Meta tokens (already leaked in git history)
- [ ] `.gitignore`: `.env`, `*.pem`, `*.signing.key`, `matrix-stack/`
- [ ] Remove `matrix-stack/synapse/grot.de.signing.key` from repo

### 4.2 Dev Artifacts

- [ ] Remove all `print()` — replace with `logging`
- [ ] Delete one-time scripts: `fix_bootstrap.py`, `fix_indexes.py`, `fix_static.py`, `check_password.py`
- [ ] Delete `MASTER/clients/views_temp.py`
- [ ] Remove ngrok domains from `ALLOWED_HOSTS`
- [ ] Delete `MASTER/quick_admin.py` if dev-only

### 4.3 Language Cleanup

Supported: **en, de, fr, es, it, nl, da** — nothing else.

Full list of files and line numbers to change:

```
clients/models.py:232-241        — NOTIFICATION_LANGUAGE_CHOICES: remove uk, ru
clients/tasks.py:50,54,59        — Cyrillic fallback logic: remove
clients/tasks.py:204,219         — uk/ru word lists for detection: remove
clients/tasks.py:248             — uk feedback prompt: remove
clients/tasks.py:1415,1417       — uk/ru language name map: remove
clients/tasks.py:1660            — supported set: remove uk, ru
clients/tasks.py:2959-2960       — uk/ru escalation labels: remove
clients/tasks.py:3029-3038       — uk/ru context labels: remove
clients/tasks.py:3466-3467       — uk/ru timeout messages: remove
clients/views_telegram.py:56     — uk welcome messages: remove
clients/views_telegram.py:1069-1070  — uk/ru timeout messages: remove
clients/views_telegram.py:1098-1099  — uk/ru waiting messages: remove
clients/views_telegram.py:1206,1210  — uk error/default messages: remove
clients/views_telegram.py:1424   — uk welcome template: remove
clients/views_whatsapp.py:411-412    — uk/ru timeout: remove
clients/views_whatsapp.py:438-439    — uk/ru waiting: remove
clients/views_meta_whatsapp.py:469-470  — uk/ru timeout: remove
clients/views_meta_whatsapp.py:496-497  — uk/ru waiting: remove
clients/news_utils.py:24-25      — uk/ru language name map: remove
clients/serializers.py:438-439,476-477  — uk/ua mapping: remove
clients/admin.py:975             — uk lang display: remove
rag/response_generator.py:453-454  — uk/ru escalation msg: remove
rag/response_generator.py:518,543  — uk/ru in supported sets: remove
rag/response_generator.py:528-529  — uk no-info message: remove
rag/response_generator.py:553-554  — uk low-confidence: remove
rag/llm_client.py:183-184        — uk/ru language name map: remove
api/views.py:289                 — uk/ru in supported_langs: remove
api/views.py:487-488             — uk/ru waiting message: remove
api/views.py:1685,1692,1718      — uk label translations: remove
restaurant/models.py:184,426,589 — default='uk' -> default='en'
restaurant/tasks.py:51           — language='uk' -> language='en'
restaurant/serializers.py:300,315 — default='uk' -> default='en'
restaurant/views.py:742,745,747  — uk/ru error messages: remove
```

All hardcoded translated strings move to `SystemMessage` model (see Part 5).

### 4.4 Remove Legacy LLM Fields

```
Client.llm_provider (CharField)        -> DELETE
Client.llm_model_name (CharField)      -> DELETE
Client.llm_provider_model (FK)         -> KEEP
```

### 4.5 Remove Hardcoded Config from settings.py

| Currently in settings.py | Move to |
|--------------------------|---------|
| `OLLAMA_MAIN_ENDPOINT` | `LLMProvider.api_endpoint` (already in DB) |
| `OLLAMA_LIGHT_ENDPOINT` | `LLMProvider.api_endpoint` |
| `OLLAMA_*_MODEL` | `LLMProvider.model_name` (already in DB) |
| `RAG_CONFIG` | `RAGConfiguration` model |
| `VECTOR_SEARCH_CONFIG` | `RAGConfiguration` model |
| `LLM_CONFIG` | `LLMProvider` model (already exists) |
| `MG_AI_USAGE_URL` | ENV var |
| `SYSTEM_PROMPTS` | `AgentCard.system_prompt` |
| Refusal phrases | `SystemMessage` model |

---

## PART 5 — MODULAR ARCHITECTURE

### 5.1 Split Client Model

Current: 2024 lines. Target: ~200 lines + OneToOne configs.

```
Client (core only)
    +-- TelegramChannelConfig (OneToOne)
    +-- WhatsAppChannelConfig (OneToOne)
    +-- WebWidgetConfig (OneToOne)
    +-- HITLConfig (OneToOne)
    +-- EmailConfig (OneToOne)
    +-- BrandingConfig (OneToOne)
    +-- RAGConfiguration (OneToOne)
```

### 5.2 Django App Structure

```
MASTER/
+-- core/settings/               # Split settings
|   +-- base.py, ai.py, security.py, celery.py, integrations.py
+-- accounts/                    # User, auth
+-- branches/                    # Branch hierarchy
+-- specializations/             # Specialization hierarchy
+-- clients/                     # Client core (~200 lines)
+-- channels/                    # NEW: telegram/, whatsapp/, webwidget/, gateway.py
+-- hitl/                        # NEW: escalation, detection, Matrix integration
+-- rag/                         # RAG pipeline + VectorStore abstraction
|   +-- stores/pgvector.py       # Current implementation
|   +-- stores/qdrant.py         # Stub for future
+-- agents/                      # NEW: AgentCard, AgentLog, Orchestrator, Executor
|   +-- builtin/                 # SearchAgent, RerankAgent, ResponseAgent, etc.
|   +-- tuning.py                # Self-tuning engine
|   +-- learning.py              # Prompt evolution
|   +-- health.py                # Health monitor
|   +-- mcp_wrapper.py           # MCP server wrapper
|   +-- mcp_client.py            # MCP client
+-- processing/                  # Document processing
+-- EmbeddingModel/              # EmbeddingModel, LLMProvider
+-- restaurant/                  # Restaurant-specific
+-- i18n/                        # NEW: SystemMessage (centralized translations)
+-- audit/                       # NEW: AuditEntry, middleware, signals
+-- api/                         # Public API endpoints
```

### 5.3 SystemMessage — Centralized Translations

```python
class SystemMessage(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    translations = models.JSONField(default=dict)
    description = models.TextField(blank=True)

    @classmethod
    def get(cls, key: str, lang: str = 'en') -> str:
        cache_key = f'sysmsg:{key}:{lang}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        msg = cls.objects.filter(key=key).first()
        if not msg:
            return ''
        text = msg.translations.get(lang) or msg.translations.get('en', '')
        cache.set(cache_key, text, 300)
        return text
```

### 5.4 RAGConfiguration — Per-Client Search Config

```python
class RAGConfiguration(models.Model):
    client = models.OneToOneField('clients.Client', null=True, blank=True,
        on_delete=models.CASCADE)
    branch = models.OneToOneField('branches.Branch', null=True, blank=True,
        on_delete=models.CASCADE)

    similarity_threshold = models.FloatField(default=0.1)
    max_results_per_level = models.IntegerField(default=5)
    branch_weight = models.FloatField(default=0.3)
    specialization_weight = models.FloatField(default=0.5)
    client_weight = models.FloatField(default=0.8)
    chunk_context_window = models.IntegerField(default=1)
    max_context_chunks = models.IntegerField(default=5)
    max_context_tokens = models.IntegerField(default=2000)
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)
```

Fallback: client -> branch -> ENV defaults.

### 5.5 VectorStore Abstraction

```python
class VectorStore(ABC):
    @abstractmethod
    def search(self, query_vector, filters, top_k) -> list[SearchResult]: ...
    @abstractmethod
    def upsert(self, id, vector, payload) -> None: ...
    @abstractmethod
    def delete(self, ids) -> None: ...
    @abstractmethod
    def count(self, filters) -> int: ...
```

### 5.6 Channel Gateway

```python
@dataclass
class IncomingMessage:
    channel: str          # 'telegram' | 'whatsapp' | 'webwidget' | 'email'
    client_id: int
    sender_id: str
    text: str
    language: str | None
    attachments: list[dict]
    metadata: dict
    timestamp: datetime

@dataclass
class OutgoingMessage:
    channel: str
    recipient_id: str
    text: str
    attachments: list[dict]
    metadata: dict
```

---

## PART 6 — DATA MIGRATIONS

### Migration Order

```
# Schema: new models
0001_create_system_message.py
0002_create_rag_configuration.py
0003_create_telegram_channel_config.py
0004_create_whatsapp_channel_config.py
0005_create_webwidget_config.py
0006_create_hitl_config.py
0007_create_email_config.py
0008_create_branding_config.py
0009_create_agent_card.py
0010_create_agent_log.py
0011_create_audit_entry.py

# Data: populate new models from existing data
0012_seed_system_messages.py
0013_seed_agent_cards.py
0014_migrate_telegram_config.py
0015_migrate_whatsapp_config.py
0016_migrate_hitl_config.py
0017_migrate_email_config.py
0018_migrate_branding_config.py
0019_migrate_legacy_llm.py
0020_migrate_rag_config_from_settings.py
0021_fix_language_defaults.py

# Cleanup: remove old fields (only after verification)
0022_remove_client_telegram_fields.py
0023_remove_client_whatsapp_fields.py
0024_remove_client_hitl_fields.py
0025_remove_client_email_fields.py
0026_remove_client_branding_fields.py
0027_remove_client_legacy_llm_fields.py
0028_remove_language_uk_ru.py
```

Rules:
- Every data migration: `RunPython(forward, reverse)` — reversible
- Batch processing: `iterator(chunk_size=500)`
- Test on production database copy before running on prod

---

## PART 7 — DOCKER & INFRASTRUCTURE

### docker-compose.yml

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
    # Port NOT exposed externally

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    # Port NOT exposed externally

  web:
    build: .
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]

  celery_worker:
    build: .
    command: celery -A MASTER worker -l info --concurrency=${CELERY_CONCURRENCY:-4}
    env_file: .env

  celery_beat:
    build: .
    command: celery -A MASTER beat -l info
    env_file: .env

  integration-service:
    build: ../services/integration-service
    env_file: .env.integration
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on:
      web: { condition: service_healthy }
```

### .env.example

```env
# === REQUIRED ===
SECRET_KEY=change-me-in-production
DB_NAME=nexelin
DB_USER=nexelin
DB_PASSWORD=change-me
REDIS_URL=redis://redis:6379/0

# === AI Providers (at least one) ===
OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# COHERE_API_KEY=

# === External Services ===
MG_AI_USAGE_URL=
MG_PACKAGE_URL=
INTEGRATION_SERVICE_URL=http://integration-service:8080

# === Security ===
ALLOWED_HOSTS=api.nexelin.com,app.nexelin.com
CORS_ALLOWED_ORIGINS=https://app.nexelin.com

# === Optional ===
CELERY_CONCURRENCY=4
SENTRY_DSN=
```

### Celery Beat Schedule

```python
CELERY_BEAT_SCHEDULE = {
    # Existing
    'check-inactive-chats':      {'task': '...', 'schedule': 60.0},
    'check-escalation-timeouts': {'task': '...', 'schedule': 300.0},
    'send-daily-digest':         {'task': '...', 'schedule': crontab(hour=17, minute=0)},

    # New: Agent infrastructure
    'agent-health-check':        {'task': 'agents.health.check_agent_health',
                                  'schedule': 60.0},
    'agent-self-tune':           {'task': 'agents.tuning.self_tune_agents',
                                  'schedule': crontab(hour=3, minute=0)},  # Daily 3 AM
    'agent-prompt-evolution':    {'task': 'agents.learning.evolve_agent_prompts',
                                  'schedule': crontab(day_of_week=1, hour=4)},  # Weekly Mon 4 AM
}
```

---

## PART 8 — MERGE & DEPLOY

### Strategy

1. Create `feature/clean-architecture` from `dev`
2. All work in this branch
3. Squash merge into `main`
4. Tag: `v2.0.0`

### Pre-Merge Checklist

```
# Cleanup
[ ] Zero hardcoded values — everything ENV or admin
[ ] Zero uk/ru references — only en,de,fr,es,it,nl,da
[ ] .env.example has no real credentials
[ ] No print() statements — only logging

# Architecture
[ ] Client model < 300 lines
[ ] Each channel is a separate app
[ ] VectorStore abstraction in place
[ ] Channel Gateway with unified message format

# Agent system
[ ] AgentCard model with all fields
[ ] AgentLog model with indexes
[ ] AgentExecutor handles: internal, http, celery, mcp
[ ] Orchestrator routes requests through agent pipeline
[ ] Health monitor runs every 60s
[ ] Self-tuning task runs daily
[ ] Self-learning task runs weekly
[ ] A2A endpoints: /api/agents/, /api/agents/{slug}/card, /api/agents/{slug}/execute
[ ] MCP wrapper can expose any agent as MCP server
[ ] MCP client can call external MCP servers
[ ] 5 built-in agents seeded: search, rerank, response, escalation, translation

# Admin
[ ] SystemMessage — all translations editable
[ ] RAGConfiguration — per-client/per-branch
[ ] AgentCard — full CRUD with config editing
[ ] AgentLog — viewable with filtering
[ ] Audit log — who changed what

# Infrastructure
[ ] Docker: DB/Redis ports closed
[ ] Celery concurrency configurable
[ ] Health checks on all services
[ ] All migrations reversible

# Functional
[ ] RAG chat works end-to-end through Orchestrator
[ ] Telegram webhook works
[ ] WhatsApp webhook works
[ ] Web widget works
[ ] HITL escalation works
[ ] Agent health monitoring works
[ ] Adding agent via admin works (paste URL + schema)
```

### Deploy

```bash
# 1. Backup
pg_dump -Fc nexelin > backup_$(date +%Y%m%d_%H%M).dump

# 2. Deploy
git pull origin main
docker-compose build
docker-compose run web python manage.py migrate
docker-compose up -d

# 3. Verify
docker-compose exec web python manage.py check --deploy
curl -f https://api.nexelin.com/health/
curl -f https://api.nexelin.com/api/agents/
```

---

## How Adding a New Agent Works (Admin Flow)

### Example: Adding a CalendarAgent

1. Open Django Admin -> Agent Cards -> Add
2. Fill in:
   - Name: `CalendarAgent`
   - Slug: `calendar`
   - Description: `Books meetings via Google Calendar API`
   - Agent type: `http`
   - Endpoint: `https://calendar-service.internal/api/execute`
   - HTTP headers: `{"Authorization": "Bearer xxx"}`
   - Input schema:
     ```json
     {
       "type": "object",
       "properties": {
         "title": {"type": "string"},
         "date": {"type": "string", "format": "date"},
         "duration_minutes": {"type": "integer"},
         "attendees": {"type": "array", "items": {"type": "string"}}
       },
       "required": ["title", "date"]
     }
     ```
   - Output schema:
     ```json
     {
       "type": "object",
       "properties": {
         "event_id": {"type": "string"},
         "meeting_link": {"type": "string"}
       }
     }
     ```
   - Capabilities: `["calendar", "booking", "scheduling"]`
   - Health check URL: `https://calendar-service.internal/health`
   - Timeout: `10`
3. Save. Agent is immediately available at `/api/agents/calendar/execute`
4. Orchestrator can route to it based on capabilities

### Example: Adding an External MCP Server

1. Open Django Admin -> Agent Cards -> Add
2. Fill in:
   - Name: `ExternalRAGService`
   - Slug: `external-rag`
   - Agent type: `mcp`
   - Endpoint: `https://partner-company.com/mcp/v1`
   - HTTP headers: `{"Authorization": "Bearer partner-api-key"}`
   - Input/output schemas from partner documentation
3. Save. MCP client handles protocol automatically.

---

## Self-Improvement Flow (Diagram)

```
User interacts with AI
        |
        v
Orchestrator -> SearchAgent -> RerankAgent -> ResponseAgent
        |                                          |
        v                                          v
   AgentLog created                          AgentLog created
   (input, output,                           (input, output,
    latency, status)                          latency, status)
        |                                          |
        v                                          v
User gives feedback (thumbs up/down)     Implicit feedback
        |                                 (escalation = negative)
        v                                          |
   AgentLog.feedback_score updated                 |
        |                                          |
        +------------------------------------------+
        |
        v (daily at 3 AM)
   self_tune_agents() Celery task
        |
        +-- Calculate metrics per agent
        |   (failure_rate, avg_feedback, latency, escalation_rate)
        |
        +-- Rule-based adjustments
        |   (lower temperature, increase top_k, adjust timeout)
        |
        +-- Apply to AgentCard.config
        |   (save history for rollback)
        |
        v (weekly on Monday 4 AM)
   evolve_agent_prompts() Celery task
        |
        +-- Collect negative-feedback logs
        |
        +-- Ask LLM to analyze failure patterns
        |
        +-- Generate prompt improvement suggestions
        |
        +-- Store in AgentCard.config['pending_prompt_suggestions']
        |
        +-- Admin reviews OR auto-apply
```

---

## Timeline

| Part | Duration | What |
|------|----------|------|
| Part 4 — Cleanup | 2 days | Credentials, dev artifacts, languages |
| Part 5 — Modular architecture | 4-5 days | Split Client, new apps, VectorStore |
| Part 1 — Agent system | 5-6 days | AgentCard, Executor, Orchestrator, built-in agents |
| Part 2 — A2A & MCP | 2-3 days | Endpoints, MCP wrapper/client |
| Part 3 — Built-in agents | 3-4 days | Search, Rerank, Response, Escalation, Translation |
| Self-tuning & learning | 2-3 days | Tuning engine, prompt evolution, health monitor |
| Part 6 — Migrations | 2 days | 28 migrations, test on prod copy |
| Part 7 — Docker/infra | 1-2 days | Secure docker-compose, Celery beat |
| Part 8 — Merge & deploy | 1 day | Squash merge, deploy, verify |
| **Total** | **~23-27 days** | |

### Execution Order

```
Week 1:  Part 4 (cleanup) + Part 5 (modular architecture)
Week 2:  Part 5 (finish) + Part 1 (agent models, executor)
Week 3:  Part 1 (orchestrator) + Part 3 (built-in agents)
Week 4:  Part 2 (A2A/MCP) + Self-tuning
Week 5:  Part 6 (migrations) + Part 7 (docker) + Part 8 (merge)
```
