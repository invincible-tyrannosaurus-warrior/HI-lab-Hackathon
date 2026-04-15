import React, { useState, useEffect, useRef } from 'react';
import { Database, PlayCircle, StopCircle, CheckCircle, XCircle, AlertCircle, FileText, Network, ChevronRight, Download, Loader2 } from 'lucide-react';
import { Language } from '../types';

/* ── types (local) ──────────────────────────────────────────── */

interface StepInfo {
  name: string;
  script_name: string;
  status: string;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

interface BuildStatusRes {
  ok: boolean;
  build_id: string | null;
  dataset_name?: string;
  status: string;
  current_step: string | null;
  progress: number;
  steps: StepInfo[];
  error: string | null;
}

interface LogEntry {
  timestamp: string;
  level: string;
  step: string;
  message: string;
}

interface EstimateInfo {
  paper_count: number;
  estimated_minutes: number;
  estimated_display: string;
}

/* ── i18n ────────────────────────────────────────────────────── */

const STEP_LABELS: Record<string, Record<string, string>> = {
  en: {
    extract_patterns: 'Extract Research Patterns',
    generate_clusters: 'Generate Clusters',
    build_entities: 'Build Graph Entities',
    build_edges: 'Build Graph Edges',
  },
  zh: {
    extract_patterns: '提取研究套路',
    generate_clusters: '聚类分析',
    build_entities: '构建图谱节点',
    build_edges: '构建关系边',
  },
};

const T = {
  en: {
    title: 'Knowledge Graph Builder',
    subtitle: 'Build a custom knowledge graph from your paper dataset',
    dataset_name: 'Dataset File',
    dataset_name_ph: 'Select a dataset...',
    dataset_name_hint: 'JSONL files found in Paper-KG-Pipeline/data/',
    dataset_name_empty: 'No .jsonl files found. Please add files to Paper-KG-Pipeline/data/ first.',
    dataset_path: 'Dataset Path (JSONL)',
    dataset_path_hint: 'Auto-computed from selected file (read-only)',
    api_key: 'LLM API Key',
    api_key_ph: 'sk-...',
    api_key_hint: 'Leave blank to use server-side env variable',
    llm_model: 'LLM Model',
    llm_model_ph: 'e.g. gpt-4o, deepseek-chat',
    llm_api_url: 'LLM API URL (Base URL)',
    llm_api_url_ph: 'e.g. https://api.openai.com/v1',
    llm_api_url_hint: 'Base URL only, without /chat/completions',
    validate: 'Validate Dataset',
    validating: 'Validating...',
    start: 'Start Build',
    cancel: 'Cancel Build',
    papers: 'Papers',
    est_time: 'Estimated Time',
    progress: 'Build Progress',
    logs: 'Build Logs',
    no_logs: 'Waiting for logs...',
    completed: 'Build Completed!',
    completed_hint: 'Your knowledge graph is ready. You can now run the pipeline.',
    already_running: 'A build is already in progress.',
    idle: 'No build running.',
    config: 'Build Configuration',
    data_notice_pre: 'Please place your JSONL dataset file under the project directory: ',
    data_notice_path: 'Paper-KG-Pipeline/data/',
    data_notice_post: '. Each line must be a JSON object containing at least: title, abstract, id (or paper_id). For format reference, see:',
    data_notice_link: 'Paper-Review-Dataset on HuggingFace',
    control: 'Build Control',
    download_logs: 'Download Logs',
  },
  zh: {
    title: '知识图谱构建器',
    subtitle: '使用自有论文数据集构建定制化知识图谱',
    dataset_name: '数据集文件',
    dataset_name_ph: '请选择数据集...',
    dataset_name_hint: 'Paper-KG-Pipeline/data/ 目录下的 JSONL 文件',
    dataset_name_empty: '未找到 .jsonl 文件，请先将文件放入 Paper-KG-Pipeline/data/ 目录。',
    dataset_path: '数据集路径 (JSONL)',
    dataset_path_hint: '根据所选文件自动生成（只读）',
    api_key: 'LLM API Key',
    api_key_ph: 'sk-...',
    api_key_hint: '留空则使用服务器环境变量',
    llm_model: 'LLM 模型',
    llm_model_ph: '例如 gpt-4o, deepseek-chat',
    llm_api_url: 'LLM API URL（Base URL）',
    llm_api_url_ph: '例如 https://api.openai.com/v1',
    llm_api_url_hint: '仅填写 Base URL，不含 /chat/completions',
    validate: '验证数据集',
    validating: '验证中...',
    start: '开始构建',
    cancel: '取消构建',
    papers: '论文数',
    est_time: '预估时间',
    progress: '构建进度',
    logs: '构建日志',
    no_logs: '等待日志...',
    completed: '构建完成！',
    completed_hint: '知识图谱已生成，可以运行 pipeline 了。',
    already_running: '已有构建任务正在运行。',
    idle: '暂无构建任务。',
    config: '构建配置',
    data_notice_pre: '请将 JSONL 格式的数据集文件放置到项目目录下：',
    data_notice_path: 'Paper-KG-Pipeline/data/',
    data_notice_post: '。每行须为一个 JSON 对象，至少包含：title、abstract、id（或 paper_id）字段。数据格式可参考：',
    data_notice_link: 'HuggingFace 上的 Paper-Review-Dataset',
    control: '构建控制',
    download_logs: '下载日志',
  },
};

/* ── API helpers ──────────────────────────────────────────────── */

const BASE = '';   // same-origin (proxied by vite or served by app.py)

async function apiPost(url: string, body: any) {
  const res = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}
async function apiGet(url: string) {
  const res = await fetch(BASE + url);
  return res.json();
}
async function apiDelete(url: string) {
  const res = await fetch(BASE + url, { method: 'DELETE' });
  return res.json();
}

/* ── localStorage persistence ─────────────────────────────── */

const KG_CONFIG_KEY = 'kg_builder_config';

function loadKgConfig(): { apiKey: string; llmModel: string; llmApiUrl: string; datasetName: string } {
  try {
    const raw = localStorage.getItem(KG_CONFIG_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { apiKey: '', llmModel: 'gpt-4o', llmApiUrl: '', datasetName: '' };
}

function saveKgConfig(cfg: { apiKey: string; llmModel: string; llmApiUrl: string; datasetName: string }) {
  try { localStorage.setItem(KG_CONFIG_KEY, JSON.stringify(cfg)); } catch { /* ignore */ }
}

/* ── component ────────────────────────────────────────────────── */

interface Props {
  lang: Language;
  t: any;            // global translation dict (unused here – we use local T)
  config: any;       // global AppConfig
}

export const KGBuilderPage: React.FC<Props> = ({ lang, config: appConfig }) => {
  const t = T[lang] || T.en;
  const stepLabels = STEP_LABELS[lang] || STEP_LABELS.en;

  /* form state (initialized from localStorage) */
  const saved = loadKgConfig();
  const [datasetName, setDatasetName] = useState(saved.datasetName);
  const [datasetFiles, setDatasetFiles] = useState<string[]>([]);
  const [apiKey, setApiKey] = useState(saved.apiKey);
  const [llmModel, setLlmModel] = useState(saved.llmModel);
  const [llmApiUrl, setLlmApiUrl] = useState(saved.llmApiUrl);

  /* persist config to localStorage on change */
  useEffect(() => {
    saveKgConfig({ apiKey, llmModel, llmApiUrl, datasetName });
  }, [apiKey, llmModel, llmApiUrl, datasetName]);

  /* computed dataset path (read-only) */
  const datasetPath = datasetName
    ? `Paper-KG-Pipeline/data/${datasetName}`
    : '';

  /* validation */
  const [isValidating, setIsValidating] = useState(false);
  const [validErr, setValidErr] = useState<string | null>(null);
  const [estimate, setEstimate] = useState<EstimateInfo | null>(null);

  /* build */
  const [buildStatus, setBuildStatus] = useState<BuildStatusRes | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [buildErr, setBuildErr] = useState<string | null>(null);
  const logIdx = useRef(0);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const isBuilding = buildStatus && ['starting', 'running'].includes(buildStatus.status);

  /* scroll logs */
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  /* poll status + logs when building */
  useEffect(() => {
    if (!isBuilding) return;
    const iv = setInterval(async () => {
      try {
        const [st, lg] = await Promise.all([
          apiGet('/api/kg/build/status'),
          apiGet(`/api/kg/build/logs?since=${logIdx.current}`),
        ]);
        if (st.ok) setBuildStatus(st);
        if (lg.ok && lg.logs.length) {
          setLogs(prev => [...prev, ...lg.logs]);
          logIdx.current = lg.total;
        }
        if (st.status === 'completed' || st.status === 'failed' || st.status === 'cancelled') {
          if (st.status === 'failed') setBuildErr(st.error || 'Build failed');
        }
      } catch { /* ignore transient errors */ }
    }, 2000);
    return () => clearInterval(iv);
  }, [isBuilding]);

  /* check for an existing running build on mount + fetch dataset file list */
  useEffect(() => {
    (async () => {
      try {
        const [st, ds] = await Promise.all([
          apiGet('/api/kg/build/status'),
          apiGet('/api/kg/datasets'),
        ]);
        if (st.ok && st.build_id) {
          setBuildStatus(st);
          if (['starting', 'running'].includes(st.status)) {
            logIdx.current = 0;
          }
        }
        if (ds.ok && ds.files) {
          setDatasetFiles(ds.files);
        }
      } catch { /* server not ready */ }
    })();
  }, []);

  /* handlers */
  const handleValidate = async () => {
    if (!datasetPath) { setValidErr('Please select a dataset file first.'); return; }
    setIsValidating(true); setValidErr(null); setEstimate(null);
    try {
      const res = await apiPost('/api/kg/validate', { dataset_path: datasetPath });
      if (res.valid) setEstimate(res.estimate);
      else setValidErr(res.error || 'Invalid dataset');
    } catch (e: any) { setValidErr(e.message); }
    finally { setIsValidating(false); }
  };

  const handleStart = async () => {
    if (!datasetName) { setBuildErr('Please select a dataset file.'); return; }
    setBuildErr(null); setLogs([]); logIdx.current = 0;
    const name = datasetName.replace(/\.jsonl$/, '');
    try {
      const res = await apiPost('/api/kg/build', {
        dataset_path: datasetPath,
        dataset_name: name,
        config: { llm_api_key: apiKey, llm_model: llmModel, llm_api_url: llmApiUrl },
      });
      if (!res.ok) { setBuildErr(res.error); return; }
      setBuildStatus(res);
    } catch (e: any) { setBuildErr(e.message); }
  };

  const handleCancel = async () => {
    try { await apiDelete('/api/kg/build'); } catch { /* ignore */ }
  };

  const handleDownloadLogs = () => {
    const text = logs.map(l => `[${l.timestamp}] [${l.step}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `kg_build_${buildStatus?.build_id || 'log'}.txt`;
    a.click(); URL.revokeObjectURL(url);
  };

  /* step icon */
  const stepIcon = (s: StepInfo) => {
    if (s.status === 'completed') return <CheckCircle size={20} className="text-green-500" />;
    if (s.status === 'failed')    return <XCircle size={20} className="text-red-500" />;
    if (s.status === 'running')   return <Loader2 size={20} className="text-blue-500 animate-spin" />;
    if (s.status === 'cancelled') return <AlertCircle size={20} className="text-yellow-500" />;
    return <Database size={20} className="text-slate-400 dark:text-slate-600" />;
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">{t.title}</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1 font-medium">{t.subtitle}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* ── Left: Config ──────────────────────────────────── */}
        <div className="space-y-6">
          {/* Dataset config card */}
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-5">
            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">{t.config}</h2>

            {/* Data placement notice */}
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-300 leading-relaxed">
              <div className="flex gap-2">
                <AlertCircle size={18} className="shrink-0 mt-0.5" />
                <div>
                  {t.data_notice_pre}
                  <code className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 font-mono text-xs">{t.data_notice_path}</code>
                  {t.data_notice_post}{' '}
                  <a
                    href="https://huggingface.co/datasets/AgentAlphaAGI/Paper-Review-Dataset"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline font-semibold hover:text-amber-600 dark:hover:text-amber-200 transition-colors"
                  >
                    {t.data_notice_link}
                  </a>
                </div>
              </div>
            </div>

            {/* Dataset File (dropdown) */}
            <div>
              <label className="block text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1.5">{t.dataset_name}</label>
              {datasetFiles.length > 0 ? (
                <select
                  value={datasetName}
                  onChange={e => { setDatasetName(e.target.value); setEstimate(null); setValidErr(null); }}
                  disabled={!!isBuilding}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-violet-200 dark:focus:ring-violet-900 focus:border-violet-400 outline-none transition-all disabled:opacity-50"
                >
                  <option value="">{t.dataset_name_ph}</option>
                  {datasetFiles.map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              ) : (
                <div className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-100 dark:bg-slate-900/60 text-slate-400 dark:text-slate-500 text-sm">
                  {t.dataset_name_empty}
                </div>
              )}
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{t.dataset_name_hint}</p>
            </div>

            {/* API Key */}
            <div>
              <label className="block text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1.5">{t.api_key}</label>
              <input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={t.api_key_ph}
                disabled={!!isBuilding}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-violet-200 dark:focus:ring-violet-900 focus:border-violet-400 outline-none transition-all disabled:opacity-50"
              />
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{t.api_key_hint}</p>
            </div>

            {/* Model */}
            <div>
              <label className="block text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1.5">{t.llm_model}</label>
              <input
                type="text"
                value={llmModel}
                onChange={e => setLlmModel(e.target.value)}
                placeholder={t.llm_model_ph}
                disabled={!!isBuilding}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-violet-200 dark:focus:ring-violet-900 focus:border-violet-400 outline-none transition-all disabled:opacity-50"
              />
            </div>

            {/* LLM API URL */}
            <div>
              <label className="block text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1.5">{t.llm_api_url}</label>
              <input
                type="text"
                value={llmApiUrl}
                onChange={e => setLlmApiUrl(e.target.value)}
                placeholder={t.llm_api_url_ph}
                disabled={!!isBuilding}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-violet-200 dark:focus:ring-violet-900 focus:border-violet-400 outline-none transition-all disabled:opacity-50"
              />
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{t.llm_api_url_hint}</p>
            </div>

            {/* Validate */}
            <button
              onClick={handleValidate}
              disabled={isValidating || !!isBuilding}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 font-semibold text-sm transition-colors disabled:opacity-50"
            >
              {isValidating ? t.validating : t.validate}
            </button>

            {/* Validation error */}
            {validErr && (
              <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm">{validErr}</div>
            )}

            {/* Estimate */}
            {estimate && (
              <div className="p-4 rounded-xl bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 space-y-1.5 text-sm">
                <div className="flex justify-between text-slate-600 dark:text-slate-300">
                  <span>{t.papers}</span>
                  <span className="font-bold">{estimate.paper_count.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-slate-600 dark:text-slate-300">
                  <span>{t.est_time}</span>
                  <span className="font-bold">{estimate.estimated_display}</span>
                </div>
              </div>
            )}
          </div>

          {/* Build control card */}
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">{t.control}</h2>

            {!isBuilding ? (
              <button
                onClick={handleStart}
                disabled={!estimate || !datasetName}
                className="w-full px-6 py-3 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <PlayCircle size={20} /> {t.start}
              </button>
            ) : (
              <button
                onClick={handleCancel}
                className="w-full px-6 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white font-semibold flex items-center justify-center gap-2 transition-colors"
              >
                <StopCircle size={20} /> {t.cancel}
              </button>
            )}

            {buildErr && (
              <div className="p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm">{buildErr}</div>
            )}

            {buildStatus?.status === 'completed' && (
              <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300">
                <div className="flex items-center gap-2 font-bold mb-1"><CheckCircle size={18} /> {t.completed}</div>
                <p className="text-sm opacity-80">{t.completed_hint}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Progress + Logs ─────────────────────── */}
        <div className="space-y-6">
          {/* Progress */}
          {buildStatus && buildStatus.build_id && (
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">{t.progress}</h2>
                <span className="text-sm font-mono text-slate-500 dark:text-slate-400">{Math.round(buildStatus.progress * 100)}%</span>
              </div>

              {/* Overall bar */}
              <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
                <div className="bg-violet-500 h-2 transition-all duration-500 rounded-full" style={{ width: `${buildStatus.progress * 100}%` }} />
              </div>

              {/* Steps */}
              <div className="space-y-3">
                {buildStatus.steps.map(step => (
                  <div key={step.name} className="rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-700 p-4">
                    <div className="flex items-center gap-3">
                      {stepIcon(step)}
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm text-slate-700 dark:text-slate-200 truncate">{stepLabels[step.name] || step.name}</div>
                        {step.status === 'running' && (
                          <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{Math.round(step.progress * 100)}%</div>
                        )}
                      </div>
                      {step.status === 'running' && <ChevronRight size={16} className="text-violet-500 animate-pulse" />}
                    </div>
                    {step.status === 'running' && (
                      <div className="mt-2.5 w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1 overflow-hidden">
                        <div className="bg-violet-500 h-1 transition-all duration-300 rounded-full" style={{ width: `${step.progress * 100}%` }} />
                      </div>
                    )}
                    {step.error && <div className="mt-2 text-xs text-red-500">{step.error}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Logs */}
          {buildStatus && buildStatus.build_id && (
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">{t.logs}</h2>
                {logs.length > 0 && (
                  <button onClick={handleDownloadLogs} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
                    <Download size={14} /> {t.download_logs}
                  </button>
                )}
              </div>
              <div className="bg-slate-950 rounded-xl p-4 h-96 overflow-y-auto font-mono text-xs leading-relaxed scrollbar-thin">
                {logs.length === 0 ? (
                  <div className="text-slate-600 text-center py-12">{t.no_logs}</div>
                ) : (
                  <>
                    {logs.map((l, i) => (
                      <div key={i} className={`mb-0.5 ${l.level === 'error' ? 'text-red-400' : l.level === 'warning' ? 'text-yellow-400' : 'text-slate-300'}`}>
                        <span className="text-slate-600">[{l.timestamp}]</span>{' '}
                        <span className="text-slate-500">{l.step}</span>{' '}
                        {l.message}
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
