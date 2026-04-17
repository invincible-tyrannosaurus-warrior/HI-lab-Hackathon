# Student Agent Testing MVP

This workspace contains a hackathon MVP implementation for the Durham AI Education System Upgrade Student Agent Testing module.

## Structure

```text
backend/
  app.py
  aggregation.py
  llm_adapter.py
  models.py
  parsing.py
  profiles.py
  prompting.py
  runner.py
  storage.py
  tasks.py
frontend/
  StudentAgentDashboard.jsx
tests/
  test_student_agent_testing.py
```

## Backend

Run the FastAPI app with:

```bash
uvicorn backend.app:app --reload
```

The backend supports:

- `POST /evaluation/run`
- `POST /deck/ingest/pptx`
- `POST /evaluation/run-pptx`
- `POST /evaluation/qa-improvement`
- `GET /evaluation/qa-improvement/{benchmark_id}`
- `GET /evaluation/{job_id}`
- `GET /evaluation/results/{run_id}`
- `GET /evaluation/summary/{deck_id}`
- `GET /`

Mock mode is enabled by request payload and is intended for repeatable MVP demos and tests.

## PPTX Input

The MVP now supports `.pptx` ingestion into the structured `LectureDeck` JSON shape.

Example request:

```json
{
  "pptx_path": "/absolute/path/to/lecture.pptx",
  "deck_id": "deck_demo_002",
  "module_tag": "intro_ai",
  "week_tag": "week_2",
  "topic_tags": ["supervised learning"]
}
```

Use:

- `POST /deck/ingest/pptx` to convert the file into deck JSON
- `POST /evaluation/run-pptx` to ingest and run the evaluation flow in one step

## QA Improvement

The backend now supports a before/after QA benchmark flow for measuring whether support content improves the student's accuracy.

The result includes:

- `before_pass`
- `after_pass`
- `improvement_delta`
- `collaborator_handoff`
- `model_used`

In mock mode, the weak-profile benchmark is shaped to support the example pattern of improving from `2/10` to `8/10`, with the remaining `2` unresolved items packed into the collaborator handoff payload.

When `use_mock=false`, the QA benchmark uses OpenRouter's OpenAI-compatible chat completions API through the configured small model. The request accepts:

- `llm_model`
- `provider_order`
- `allow_fallbacks`
- `target_collaborator`

The default model is `qwen/qwen-2.5-7b-instruct`.

If OpenRouter reports that a provider routing preference is causing failures, you can override routing per request.
For example, if `together` is listed as available for the model, set:

```json
{
  "llm_model": "qwen/qwen-2.5-7b-instruct",
  "provider_order": ["together"],
  "allow_fallbacks": true
}
```

The collaborator handoff payload is now a formal envelope with:

- `schema_version`
- `handoff_type`
- `source_stage`
- `source_system`
- `target_collaborator`
- `items`

Each unresolved item includes both the question content and structured collaboration fields such as:

- `priority`
- `target_type`
- `target_ref`
- `issue_types`
- `affected_profiles`
- `reason`
- `suggestion`

## Spec Alignment Notes

The current backend now exposes spec-friendly fields for downstream analytics and governance consumers:

- individual runs include `answer_text`
- individual runs include `confusion_tags`, `missed_prerequisites`, `misconception_flags`
- individual runs include `evidence_refs`
- aggregated summaries include `governance_trace`
- aggregated summaries include `evidence_refs`

This keeps the original structured `answer` object while also surfacing flatter fields for easier downstream consumption.

## Enabling Real LLM Calls

The only required user-side setup for real model calls is to set your OpenRouter API key in the shell before starting the backend.

In `zsh`, run:

```bash
export OPENROUTER_API_KEY="your_openrouter_api_key_here"
```

Then start the backend in the same terminal session:

```bash
cd "/Users/test/Documents/New project"
source .venv/bin/activate
uvicorn backend.app:app --reload
```

To make the key persist across terminal sessions, add the same `export OPENROUTER_API_KEY=...` line to your `~/.zshrc`, then reload it:

```bash
echo 'export OPENROUTER_API_KEY="your_openrouter_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

Optional OpenRouter headers can also be configured through environment variables:

```bash
export OPENROUTER_HTTP_REFERER="http://localhost:5173"
export OPENROUTER_APP_TITLE="Student Agent Testing MVP"
```

When calling `POST /evaluation/qa-improvement`, set:

- `use_mock` to `false`
- optionally `llm_model` to another OpenRouter model id
- optionally `provider_order` to force OpenRouter to try a provider such as `together`

Example:

```json
{
  "deck": { "...": "LectureDeck" },
  "questions": [{ "...": "QAQuestion" }],
  "profile_name": "weak",
  "qa_support_content": ["Explain with one worked example."],
  "target_collaborator": "content_revision_collaborator",
  "llm_model": "qwen/qwen-2.5-7b-instruct",
  "provider_order": ["together"],
  "allow_fallbacks": true,
  "use_mock": false
}
```

## Frontend

The frontend now includes a lightweight Vite scaffold:

- `frontend/StudentAgentDashboard.jsx`
- `frontend/package.json`
- `frontend/index.html`
- `frontend/src/main.jsx`
- `frontend/vite.config.js`

To run it after Node is installed:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies API requests to `http://127.0.0.1:8000`.

## Tests

The tests cover:

- end-to-end mock pipeline execution
- `coverage_check` restriction to the `strong` profile
- distinguishable output patterns across profiles
- FastAPI endpoint response validation with `TestClient`
- PPTX ingestion into deck JSON
- QA improvement uplift and remaining-error handoff generation
