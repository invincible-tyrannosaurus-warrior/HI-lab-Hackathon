import React, { useMemo, useState } from "react";

const sampleDeck = {
  deck_id: "deck_demo_001",
  module_tag: "intro_ai",
  week_tag: "week_1",
  topic_tags: ["machine learning basics", "supervised learning"],
  slides: [
    {
      slide_id: "s1",
      title: "What is Machine Learning?",
      key_points: ["ML learns patterns from data"],
      terms: ["machine learning", "data", "pattern"],
      examples: ["spam detection"],
      raw_text: "Machine learning is a method for learning patterns from data."
    },
    {
      slide_id: "s2",
      title: "Supervised Learning",
      key_points: ["Uses labelled examples", "Predicts outputs from inputs"],
      terms: ["label", "training data", "prediction"],
      examples: [],
      raw_text: "Supervised learning maps inputs to outputs using labelled training examples."
    }
  ]
};

const defaultPayload = {
  deck: sampleDeck,
  profile_names: ["weak", "average", "strong"],
  task_types: ["explain_back", "short_qa", "confusion_report", "coverage_check"],
  auto_aggregate: true,
  use_mock: true
};

function Heatmap({ items }) {
  const grouped = useMemo(() => {
    const rows = {};
    items.forEach((item) => {
      if (!rows[item.profile_name]) rows[item.profile_name] = [];
      rows[item.profile_name].push(item);
    });
    return rows;
  }, [items]);

  return (
    <div className="panel">
      <h3>Profile Confusion Heatmap</h3>
      {Object.entries(grouped).map(([profile, values]) => (
        <div key={profile} className="heatmap-row">
          <strong>{profile}</strong>
          <div className="heatmap-tags">
            {values.map((item) => (
              <span
                key={`${profile}-${item.tag}`}
                className="heatmap-cell"
                style={{ opacity: Math.min(1, 0.25 + item.count * 0.18) }}
              >
                {item.tag} ({item.count})
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function BarChart({ items }) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className="panel">
      <h3>Weak Topics</h3>
      <div className="bar-list">
        {items.map((item) => (
          <div key={item.label} className="bar-row">
            <span className="bar-label">{item.label}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
            </div>
            <span className="bar-count">{item.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function StudentAgentDashboard() {
  const [payloadText, setPayloadText] = useState(JSON.stringify(defaultPayload, null, 2));
  const [jobResponse, setJobResponse] = useState(null);
  const [jobDetails, setJobDetails] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const summary = jobResponse?.summary;
  const runs = jobDetails?.runs ?? [];

  async function submitDeck() {
    setLoading(true);
    setError("");
    try {
      const payload = JSON.parse(payloadText);
      const response = await fetch("/evaluation/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(`Run failed with ${response.status}`);
      const data = await response.json();
      setJobResponse(data);
      setSelectedRun(null);

      const jobStateResponse = await fetch(`/evaluation/${data.job.job_id}`);
      if (!jobStateResponse.ok) throw new Error(`Job fetch failed with ${jobStateResponse.status}`);
      const jobState = await jobStateResponse.json();
      setJobDetails(jobState);
    } catch (err) {
      setError(err.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function loadRun(runId) {
    const response = await fetch(`/evaluation/results/${runId}`);
    const data = await response.json();
    setSelectedRun(data);
  }

  return (
    <div className="student-agent-dashboard">
      <style>{`
        :root {
          --bg: #f5efe4;
          --panel: #fffaf2;
          --ink: #1d2a32;
          --muted: #5b6a72;
          --accent: #b95835;
          --accent-soft: #efd2b8;
          --line: #dcc9b2;
          --good: #2f6c5f;
        }
        body {
          margin: 0;
          background:
            radial-gradient(circle at top left, rgba(185, 88, 53, 0.16), transparent 28%),
            linear-gradient(180deg, #f7f1e7 0%, #f0e7d9 100%);
          color: var(--ink);
          font-family: Georgia, "Times New Roman", serif;
        }
        .student-agent-dashboard {
          max-width: 1280px;
          margin: 0 auto;
          padding: 32px 20px 64px;
        }
        h1, h2, h3 {
          margin: 0 0 12px;
          font-weight: 600;
          letter-spacing: 0.02em;
        }
        textarea, pre {
          font-family: "SFMono-Regular", Consolas, monospace;
        }
        .hero {
          margin-bottom: 24px;
          padding: 24px;
          border: 1px solid var(--line);
          border-radius: 20px;
          background: linear-gradient(135deg, rgba(255,250,242,0.98), rgba(239,210,184,0.9));
          box-shadow: 0 18px 50px rgba(60, 33, 16, 0.08);
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 18px;
        }
        .panel {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 18px;
          padding: 18px;
          box-shadow: 0 10px 30px rgba(29, 42, 50, 0.05);
        }
        textarea {
          width: 100%;
          min-height: 240px;
          border-radius: 14px;
          border: 1px solid var(--line);
          padding: 14px;
          background: #fffdf8;
          color: var(--ink);
        }
        button {
          appearance: none;
          border: none;
          border-radius: 999px;
          padding: 12px 18px;
          background: var(--accent);
          color: white;
          font-weight: 600;
          cursor: pointer;
        }
        button:disabled {
          opacity: 0.6;
          cursor: wait;
        }
        .meta {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 12px;
          color: var(--muted);
        }
        .card-list, .evidence-list {
          display: grid;
          gap: 10px;
        }
        .badge {
          display: inline-block;
          padding: 6px 10px;
          border-radius: 999px;
          background: var(--accent-soft);
          color: var(--ink);
          margin: 0 8px 8px 0;
        }
        .bar-row {
          display: grid;
          grid-template-columns: 1.2fr 2fr auto;
          gap: 10px;
          align-items: center;
          margin: 10px 0;
        }
        .bar-track {
          height: 12px;
          background: #ecdccc;
          border-radius: 999px;
          overflow: hidden;
        }
        .bar-fill {
          height: 100%;
          background: linear-gradient(90deg, var(--accent), #d98753);
        }
        .heatmap-row {
          margin-bottom: 14px;
        }
        .heatmap-tags {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 8px;
        }
        .heatmap-cell {
          padding: 8px 10px;
          border-radius: 12px;
          background: #d86e46;
          color: white;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          padding: 10px 8px;
          border-bottom: 1px solid var(--line);
          text-align: left;
          font-size: 0.95rem;
        }
        tr:hover {
          background: rgba(239, 210, 184, 0.28);
        }
        .run-button {
          background: transparent;
          color: var(--good);
          padding: 0;
          border-radius: 0;
        }
        .error {
          color: #8d2c1d;
          margin-top: 12px;
        }
        @media (max-width: 720px) {
          .student-agent-dashboard {
            padding: 20px 14px 48px;
          }
          .bar-row {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <section className="hero">
        <h1>Student Agent Testing</h1>
        <p>
          Submit a structured lecture deck, run fixed student-profile tests, and review
          cohort-style signals that point to weak topics, confusion patterns, and revision targets.
        </p>
      </section>

      <section className="panel">
        <h2>Submit Lecture Deck</h2>
        <textarea value={payloadText} onChange={(event) => setPayloadText(event.target.value)} />
        <div className="meta">
          <button onClick={submitDeck} disabled={loading}>
            {loading ? "Running evaluation..." : "Run Evaluation"}
          </button>
          <span>Mock mode is enabled by default for repeatable MVP demos.</span>
        </div>
        {error ? <div className="error">{error}</div> : null}
      </section>

      {jobResponse ? (
        <>
          <section className="grid" style={{ marginTop: 18 }}>
            <div className="panel">
              <h2>Job Overview</h2>
              <div className="meta">
                <span className="badge">Job: {jobResponse.job.job_id}</span>
                <span className="badge">Status: {jobResponse.job.status}</span>
                <span className="badge">Runs: {jobResponse.job.run_ids.length}</span>
                <span className="badge">Summary ready: {String(jobResponse.job.summary_ready)}</span>
              </div>
            </div>

            <div className="panel">
              <h2>Repeated Confusion Points</h2>
              <div className="card-list">
                {(summary?.repeated_confusion_points ?? []).map((item) => (
                  <div key={item} className="badge">{item}</div>
                ))}
              </div>
            </div>

            <div className="panel">
              <h2>Misconception Clusters</h2>
              <div className="card-list">
                {(summary?.misconception_clusters ?? []).map((item) => (
                  <div key={item} className="badge">{item}</div>
                ))}
              </div>
            </div>

            <div className="panel">
              <h2>Missing Prerequisite Patterns</h2>
              <div className="card-list">
                {(summary?.missing_prerequisite_patterns ?? []).map((item) => (
                  <div key={item} className="badge">{item}</div>
                ))}
              </div>
            </div>

            <div className="panel">
              <h2>Recommended Revision Targets</h2>
              <div className="card-list">
                {(summary?.recommended_revision_targets ?? []).map((item) => (
                  <div key={item}>{item}</div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid" style={{ marginTop: 18 }}>
            <BarChart items={summary?.weak_topic_counts ?? []} />
            <Heatmap items={summary?.confusion_by_profile ?? []} />
          </section>

          <section className="grid" style={{ marginTop: 18 }}>
            <div className="panel">
              <h2>Individual Runs</h2>
              <table>
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Profile</th>
                    <th>Task</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <button className="run-button" onClick={() => loadRun(run.run_id)}>
                          {run.run_id}
                        </button>
                      </td>
                      <td>{run.student_profile}</td>
                      <td>{run.task_type}</td>
                      <td>{run.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel">
              <h2>Selected Run Detail</h2>
              {selectedRun ? (
                <pre>{JSON.stringify(selectedRun, null, 2)}</pre>
              ) : (
                <p>Select a run from the table to inspect its structured output.</p>
              )}
            </div>
          </section>

          <section className="panel" style={{ marginTop: 18 }}>
            <h2>Representative Evidence</h2>
            <div className="evidence-list">
              {(summary?.representative_evidence ?? []).map((item) => (
                <div key={item.run_id} className="panel">
                  <div className="meta">
                    <span className="badge">{item.student_profile}</span>
                    <span className="badge">{item.task_type}</span>
                    <span className="badge">{item.run_id}</span>
                  </div>
                  <p>{item.main_answer}</p>
                  <div className="meta">
                    {item.evidence_slide_refs.map((ref) => (
                      <span key={ref} className="badge">{ref}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

