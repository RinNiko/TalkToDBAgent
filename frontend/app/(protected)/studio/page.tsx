"use client";

import { useEffect, useState } from 'react';
import { Send, Database, Settings, History, Play, Eye, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { apiGet, apiPost } from '../../../lib/api';
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, RadialLinearScale } from 'chart.js';
import { Pie, Bar, Doughnut, PolarArea, Radar, Line, Scatter } from 'react-chartjs-2';
import { Toaster, toast } from 'react-hot-toast';
import ThemeToggle from '../../../components/ThemeToggle';

ChartJS.register(ArcElement, ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, PointElement, LineElement, RadialLinearScale);

type Connection = { id: number; name: string };
type NormalizedSchema = {
  tables: Array<{
    name: string;
    columns: Array<{
      name: string;
      type?: string;
      nullable?: boolean;
      primary_key?: boolean;
      unique?: boolean;
    }>;
  }>;
};

type ChartDataset = { label: string; data: number[]; backgroundColor?: string; borderColor?: string };

export default function StudioPage() {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini');
  const [showSqlPreview, setShowSqlPreview] = useState(false);
  const [generatedSql, setGeneratedSql] = useState('');
  const [queryResults, setQueryResults] = useState<any[]>([]);
  const [schema, setSchema] = useState<NormalizedSchema | null>(null);
  const [isRefreshingSchema, setIsRefreshingSchema] = useState<boolean>(false);
  const [quickExamples, setQuickExamples] = useState<string[]>([]);
  const [isRefreshingExamples, setIsRefreshingExamples] = useState<boolean>(false);
  const [examplesDebug, setExamplesDebug] = useState<string | null>(null);
  const [showExamplesDebug, setShowExamplesDebug] = useState<boolean>(false);
  const [examplesRaw, setExamplesRaw] = useState<string | null>(null);
  const [showExamplesRaw, setShowExamplesRaw] = useState<boolean>(false);
  const [isFetchingRaw, setIsFetchingRaw] = useState<boolean>(false);
  const [chartConfig, setChartConfig] = useState<{ type: 'pie' | 'doughnut' | 'bar' | 'line' | 'radar' | 'polarArea' | 'scatter'; labels: string[]; datasets: ChartDataset[]; xKey?: string; yKey?: string; yKeys?: string[]; title?: string } | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [lastColumns, setLastColumns] = useState<string[]>([]);
  const [lastSql, setLastSql] = useState<string>('');
  const [overrideType, setOverrideType] = useState<string>('');
  const [overrideX, setOverrideX] = useState<string>('');
  const [overrideY, setOverrideY] = useState<string>('');
  // Auto-sort charts by first series descending for better readability
  const AUTO_SORT_ORDER: 'asc' | 'desc' = 'desc';
  // Removed advanced overrides (multi-series/time bucket) per request

  type ChartPreset = { type: string; xKey: string; yKey?: string };
  function loadPresetForSql(sql: string): ChartPreset | null {
    try {
      const raw = localStorage.getItem('ttdb_chart_presets') || '{}';
      const map = JSON.parse(raw);
      return map[sql] || null;
    } catch { return null; }
  }
  function savePresetForSql(sql: string, preset: ChartPreset) {
    try {
      const raw = localStorage.getItem('ttdb_chart_presets') || '{}';
      const map = JSON.parse(raw);
      map[sql] = preset;
      localStorage.setItem('ttdb_chart_presets', JSON.stringify(map));
    } catch {}
  }
  function sortChart(labels: string[], datasets: ChartDataset[], order: 'none'|'asc'|'desc') {
    if (order === 'none' || !datasets.length) return { labels, datasets };
    const idx = 0;
    const pairs = labels.map((l, i) => ({ l, vals: datasets.map(ds => Number(ds.data[i] ?? 0)) }));
    pairs.sort((a, b) => (order === 'asc' ? a.vals[idx] - b.vals[idx] : b.vals[idx] - a.vals[idx]));
    const sortedLabels = pairs.map(p => p.l);
    const sortedDatasets = datasets.map((ds, di) => ({
      ...ds,
      data: pairs.map(p => p.vals[di])
    }));
    return { labels: sortedLabels, datasets: sortedDatasets };
  }
  function applyOverrideToRows(rows: any[], columns: string[]) {
    if (!rows || rows.length === 0) return;
    const xKey = overrideX && columns.includes(overrideX) ? overrideX : columns[0];
    const yKey = overrideY && columns.includes(overrideY) ? overrideY : (columns.find(c => typeof rows[0]?.[c] === 'number' || !Number.isNaN(Number(rows[0]?.[c])) ) || columns[1] || columns[0]);
    const labels = rows.map(r => String(r[xKey]));
    let datasets: ChartDataset[] = [{ label: yKey, data: rows.map(r => Number(r[yKey])) }];
    const sorted = sortChart(labels, datasets, AUTO_SORT_ORDER);
    const ctype = (overrideType as any) || (chartConfig?.type || 'bar');
    setChartConfig({ type: ctype as any, labels: sorted.labels.slice(0,200), datasets: sorted.datasets.map(ds=>({ ...ds, data: ds.data.slice(0,200) })), xKey, yKey, yKeys: undefined, title: chartConfig?.title });
  }
  function handleApplyOverride() {
    if (queryResults.length === 0 || lastColumns.length === 0) {
      toast.error('No results to apply chart on. Execute a query first.');
      return;
    }
    applyOverrideToRows(queryResults, lastColumns);
  }
  function handleSavePreset() {
    if (!lastSql) { toast.error('No SQL context to save preset.'); return; }
    const preset: ChartPreset = { type: overrideType || chartConfig?.type || 'bar', xKey: overrideX || chartConfig?.xKey || lastColumns[0], yKey: overrideY || chartConfig?.yKey };
    savePresetForSql(lastSql, preset);
    toast.success('Chart preset saved for this SQL');
  }

  async function refreshExamples(connectionId: string) {
    if (!connectionId) return;
    try {
      setIsRefreshingExamples(true);
      const ts = Date.now();
      const resp = await apiGet<{ examples: string[] }>(`/api/schema/${connectionId}/quick-examples?_=${ts}`);
      setQuickExamples(resp.examples || []);
    } catch {
      // keep old examples on failure
    } finally {
      setIsRefreshingExamples(false);
    }
  }

  async function fetchExamplesRaw(connectionId: string) {
    if (!connectionId) return;
    try {
      setIsFetchingRaw(true);
      const ts = Date.now();
      const res = await fetch(`/api/schema/${connectionId}/quick-examples?raw=true&_=${ts}`);
      const text = await res.text();
      setExamplesRaw(text || '');
      setShowExamplesRaw(true);
    } catch (e: any) {
      setExamplesRaw(String(e?.message || e));
      setShowExamplesRaw(true);
    } finally {
      setIsFetchingRaw(false);
    }
  }

  async function loadSchema(connectionId: string, opts: { allowAutoRefresh?: boolean } = {}) {
    if (!connectionId) return;
    try {
      const s = await apiGet<NormalizedSchema>(`/api/schema/${connectionId}`);
      setSchema(s);
    } catch (_) {
      try {
        await apiPost(`/api/schema/${connectionId}/discover`, {});
        const s2 = await apiGet<NormalizedSchema>(`/api/schema/${connectionId}`);
        setSchema(s2);
      } catch {
        setSchema(null);
      }
    }
    await refreshExamples(connectionId);
  }

  async function loadConnections() {
    try {
      const items = await apiGet<Connection[]>(`/api/connections`);
      setConnections(items);
      const veh = items.find(c => c.name.toLowerCase().includes('vehicle')) || items[0];
      if (veh) {
        const idStr = String(veh.id);
        setSelectedConnection(idStr);
        await loadSchema(idStr);
      }
    } catch (e) {
      console.error('Failed to load connections', e);
    }
  }

  useEffect(() => {
    loadConnections();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || !selectedConnection) return;

    setIsGenerating(true);

    try {
      const response = await fetch('/api/query/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          connection_id: parseInt(selectedConnection, 10),
          provider: 'openai',
          model: selectedModel,
          temperature: 0.1,
          include_schema: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        setApiError(null);
        // Only set SQL; do not execute here
        setGeneratedSql(result.sql);
        setShowSqlPreview(true);
        // Clear previous results/chart to reflect new draft
        setQueryResults([]);
        setChartConfig(null);
      } else {
        const text = await response.text();
        const msg = text || 'Failed to generate SQL';
        setApiError(msg);
        toast.error(msg);
      }
    } catch (error: any) {
      const msg = String(error?.message || error);
      setApiError(msg);
      toast.error(msg);
      console.error('Error generating SQL:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExecute = async () => {
    if (!generatedSql || !selectedConnection) return;

    try {
      const response = await fetch('/api/query/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sql: generatedSql,
          connection_id: parseInt(selectedConnection, 10),
          require_approval: false
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result && result.success === false && result.error) {
          const msg = String(result.error);
          setApiError(msg);
          toast.error(msg);
        } else {
          setApiError(null);
        }
        setQueryResults(result.rows || []);
        setLastColumns(result.columns || Object.keys((result.rows || [])[0] || {}));
        setLastSql(result.sql_executed || generatedSql || '');

        // Suggest chart after execution
        const preRows: any[] = result.rows || [];
        const preCols: string[] = result.columns || Object.keys((preRows[0] || {}));
        const isSingleCell = preRows.length === 1 && preCols.length === 1;
        const isSingleColumn = preCols.length === 1;
        if (isSingleCell || isSingleColumn) {
          setChartConfig(null);
          return;
        }
        try {
          const suggestion = await apiPost<{ type: string; xKey?: string; yKey?: string; yKeys?: string[]; title?: string; groupBy?: string; agg?: 'count'|'sum'|'avg'; valueKey?: string }>(`/api/query/suggest-chart`, {
            columns: result.columns || Object.keys((result.rows || [])[0] || {}),
            rows: result.rows || [],
            prompt,
          });

          const rows: any[] = result.rows || [];
          const cols: string[] = result.columns || Object.keys(rows[0] || {});

          let labels: string[] = [];
          let values: number[] = [];

          if (suggestion.groupBy && suggestion.agg) {
            const g = suggestion.groupBy;
            const agg = suggestion.agg as 'count'|'sum'|'avg';
            const valKey = suggestion.valueKey as string | undefined;
            const grouped = new Map<string, number[]>();
            for (const r of rows) {
              const key = String(r[g]);
              if (!grouped.has(key)) grouped.set(key, []);
              if (valKey) grouped.get(key)!.push(Number(r[valKey])); else grouped.get(key)!.push(1);
            }
            labels = Array.from(grouped.keys());
            values = labels.map(k => {
              const arr = grouped.get(k)!;
              if (agg === 'count') return arr.length;
              if (agg === 'sum') return arr.reduce((a,b)=>a+Number(b||0),0);
              if (agg === 'avg') return arr.reduce((a,b)=>a+Number(b||0),0) / Math.max(arr.length,1);
              return arr.length;
            });
          } else {
            const xKey = (suggestion.xKey && cols.includes(suggestion.xKey)) ? suggestion.xKey : cols[0];
            const yKey = (suggestion.yKey && cols.includes(suggestion.yKey)) ? suggestion.yKey : (cols[1] || cols[0]);
            labels = rows.map(r => String(r[xKey]));
            values = rows.map(r => Number(r[yKey]));
          }

          const clipped = {
            labels: labels.slice(0, 200),
            datasets: [{ label: (suggestion.yKey || (suggestion as any).valueKey || 'value'), data: values.slice(0, 200) }]
          };
          const sorted = sortChart(clipped.labels, clipped.datasets, AUTO_SORT_ORDER);
          setChartConfig({ type: (suggestion.type as any) || 'bar', labels: sorted.labels, datasets: sorted.datasets, xKey: suggestion.xKey, yKey: suggestion.yKey, yKeys: suggestion.yKeys || undefined, title: suggestion.title || undefined });

          // Soft-sync UI controls with suggested config if valid
          try {
            const suggestedType = (suggestion.type as any) || 'bar';
            setOverrideType(suggestedType);
            const colsSet = new Set(cols);
            const suggestedX = (suggestion.xKey || (suggestion as any).groupBy || '') as string;
            const suggestedY = (suggestion.yKey || (suggestion as any).valueKey || '') as string;
            if (suggestedX && colsSet.has(suggestedX)) {
              setOverrideX(suggestedX);
            }
            if (suggestedY && colsSet.has(suggestedY)) {
              setOverrideY(suggestedY);
            }
          } catch { /* ignore sync issues */ }

          // Apply user preset if exists
          if (result.sql_executed) {
            const preset = loadPresetForSql(result.sql_executed);
            if (preset) {
              setOverrideType(preset.type);
              setOverrideX(preset.xKey);
              setOverrideY(preset.yKey || '');
              applyOverrideToRows(rows, cols);
            }
          }
        } catch (e) {
          console.error('Chart suggestion failed', e);
          // Fallback simple inference
          inferChart(result.rows || [], result.columns || []);
        }
      } else {
        const text = await response.text();
        const msg = text || 'Failed to execute SQL';
        setApiError(msg);
        toast.error(msg);
      }
    } catch (error: any) {
      const msg = String(error?.message || error);
      setApiError(msg);
      toast.error(msg);
      console.error('Error executing SQL:', error);
    }
  };

  function inferChart(rows: any[], columns: string[]) {
    setChartConfig(null);
    if (!rows || rows.length === 0) return;

    const sample = rows[0] || {};
    const keys = Array.isArray(columns) && columns.length ? columns : Object.keys(sample);

    const isNumeric = (v: any) => {
      if (typeof v === 'number') return Number.isFinite(v);
      if (typeof v === 'string') {
        const n = Number(v);
        return Number.isFinite(n);
      }
      return false;
    };

    const preferred = keys.find(k => /count|total|sum|qty|quantity/i.test(k));
    const numericKey = preferred || keys.find(k => isNumeric(sample[k]));
    const labelKey = keys.find(k => k !== numericKey);

    if (numericKey && labelKey) {
      const labels = rows.map(r => String(r[labelKey]));
      const values = rows.map(r => Number(r[numericKey]));
      const max = 12;
      const lbl = labels.slice(0, max);
      const val = values.slice(0, max);
      setChartConfig({ type: lbl.length <= 8 ? 'pie' : 'bar', labels: lbl, datasets: [{ label: String(numericKey), data: val }] });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-[#0b0f14] dark:text-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 dark:bg-[#0f141a] dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Database className="h-8 w-8 text-primary-600" />
              <span className="ml-2 text-xl font-bold text-gray-900 dark:text-gray-100">Talk to DB</span>
            </div>
            <nav className="flex space-x-4 items-center">
              <Link href="/settings" className="text-gray-600 hover:text-gray-900 p-2 rounded-md dark:text-gray-300 dark:hover:text-white">
                <Settings className="h-5 w-5" />
              </Link>
              <Link href="/history" className="text-gray-600 hover:text-gray-900 p-2 rounded-md dark:text-gray-300 dark:hover:text-white">
                <History className="h-5 w-5" />
              </Link>
              <ThemeToggle />
            </nav>
          </div>
        </div>
      </header>

      <Toaster position="top-right" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Sidebar - Database Connection & Settings */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-[#0f141a] rounded-lg shadow p-6 border border-gray-200 dark:border-gray-800">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Database Connection</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Connection
                  </label>
                  <select
                    value={selectedConnection}
                    onChange={(e) => { setSelectedConnection(e.target.value); loadSchema(e.target.value); }}
                    className="input-field dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700"
                  >
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    AI Model
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="input-field dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700"
                  >
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                    <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                  </select>
                </div>

                <div className="pt-4">
                  <button
                    onClick={() => window.open('/settings', '_blank')}
                    className="w-full btn-secondary dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700"
                  >
                    Manage Connections
                  </button>
                </div>
              </div>
            </div>

            {/* Schema Explorer */}
            <div className="bg-white dark:bg-[#0f141a] rounded-lg shadow p-6 mt-6 border border-gray-200 dark:border-gray-800">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Database Schema</h3>
              <div className="space-y-2 text-gray-700 dark:text-gray-300">
                {!schema && (
                  <div className="text-sm text-gray-500 dark:text-gray-400">No schema available yet.</div>
                )}
                {schema?.tables?.map((t, idx) => (
                  <div key={idx} className="text-sm">
                    <div className="font-medium text-gray-800 dark:text-gray-200">{t.name}</div>
                    <div className="mt-1 space-y-0.5">
                      {t.columns?.map((c, i) => {
                        const flags: string[] = [];
                        if (c.primary_key) flags.push('PK');
                        if (c.unique) flags.push('UQ');
                        flags.push(c.nullable ? 'NULL' : 'NOT NULL');
                        return (
                          <div key={i} className="text-xs text-gray-600 dark:text-gray-400">
                            <span className="font-mono text-gray-800 dark:text-gray-200">{c.name}</span>
                            {c.type ? <span className="text-gray-500 dark:text-gray-400">: {c.type}</span> : null}
                            {flags.length ? <span className="text-gray-500 dark:text-gray-500"> ({flags.join('/')})</span> : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Main Content - Query Interface */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-[#0f141a] rounded-lg shadow border border-gray-200 dark:border-gray-800">
              {/* Query Input */}
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Ask about your data
                    </label>
                    <textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="e.g., Show me the top 10 customers by order value in the last 30 days"
                      className="input-field h-24 resize-none dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700"
                      disabled={isGenerating}
                    />
                  </div>

                  <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-500">
                      {prompt.length} characters
                    </div>
                    <button
                      type="submit"
                      disabled={!prompt.trim() || isGenerating || !selectedConnection}
                      className="btn-primary inline-flex items-center whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isGenerating ? 'Generating...' : (
                        <>
                          <Send className="h-4 w-4 mr-2" />
                          Generate SQL
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* SQL Preview */}
              {showSqlPreview && (
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-900">Generated SQL</h4>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setShowSqlPreview(!showSqlPreview)}
                        className="text-gray-600 hover:text-gray-900 p-1"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        onClick={handleExecute}
                        className="btn-primary inline-flex items-center whitespace-nowrap text-sm py-1 px-3"
                        disabled={!selectedConnection}
                      >
                        <Play className="h-4 w-4 mr-1" />
                        Execute
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={generatedSql}
                    onChange={(e) => setGeneratedSql(e.target.value)}
                    className="input-field h-40 font-mono text-sm dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700"
                  />
                </div>
              )}

              {/* Query Results */}
              {queryResults.length > 0 && (
                <div className="p-6">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">Query Results</h4>
                  {chartConfig && (
                    <div className="mb-6 bg-white dark:bg-[#0b0f14] border border-gray-200 dark:border-gray-800 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="text-sm text-gray-700 dark:text-gray-300 mr-3 sm:mr-4">Visualization</div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <select value={overrideType} onChange={(e)=>setOverrideType(e.target.value)} className="input-field py-1 text-xs w-28 sm:w-32">
                            {['pie','doughnut','bar','line','radar','polarArea','scatter'].map(t=>(<option key={t} value={t}>{t}</option>))}
                          </select>
                          <select value={overrideX} onChange={(e)=>setOverrideX(e.target.value)} className="input-field py-1 text-xs w-32 sm:w-40">
                            <option value="">X column</option>
                            {lastColumns.map(c=> (<option key={c} value={c}>{c}</option>))}
                          </select>
                          <select value={overrideY} onChange={(e)=>setOverrideY(e.target.value)} className="input-field py-1 text-xs w-32 sm:w-40">
                            <option value="">Y column</option>
                            {lastColumns.map(c=> (<option key={c} value={c}>{c}</option>))}
                          </select>
                          <button onClick={handleApplyOverride} className="inline-flex items-center rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-600">Apply</button>
                          <button onClick={handleSavePreset} className="inline-flex items-center rounded-md bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 text-xs">Save</button>
                        </div>
                      </div>
                      {chartConfig.type === 'pie' && (
                        <Pie data={{ labels: chartConfig.labels, datasets: [{ data: chartConfig.datasets[0]?.data || [], backgroundColor: chartConfig.labels.map((_, i) => `hsl(${(i*57)%360} 70% 65%)`) }] }} />
                      )}
                      {chartConfig.type === 'doughnut' && (
                        <Doughnut data={{ labels: chartConfig.labels, datasets: [{ data: chartConfig.datasets[0]?.data || [], backgroundColor: chartConfig.labels.map((_, i) => `hsl(${(i*57)%360} 70% 65%)`) }] }} />
                      )}
                      {chartConfig.type === 'polarArea' && (
                        <PolarArea data={{ labels: chartConfig.labels, datasets: [{ data: chartConfig.datasets[0]?.data || [], backgroundColor: chartConfig.labels.map((_, i) => `hsl(${(i*57)%360} 70% 65%)`) }] }} />
                      )}
                      {chartConfig.type === 'radar' && (
                        <Radar data={{ labels: chartConfig.labels, datasets: (chartConfig.datasets.length ? chartConfig.datasets : [{ label: chartConfig.title || 'Value', data: [] }]).map((ds, idx) => ({ ...ds, backgroundColor: `hsl(${(idx*57)%360} 80% 70% / 0.3)`, borderColor: `hsl(${(idx*57)%360} 80% 50%)` })) }} />
                      )}
                      {chartConfig.type === 'bar' && (
                        <Bar data={{ labels: chartConfig.labels, datasets: (chartConfig.datasets.length ? chartConfig.datasets : [{ label: chartConfig.title || 'Value', data: [] }]).map((ds, idx) => ({ ...ds, backgroundColor: ds.backgroundColor || `hsl(${(idx*57)%360} 70% 65%)` })) }} options={{ responsive: true, plugins: { legend: { display: true } } }} />
                      )}
                      {chartConfig.type === 'line' && (
                        <Line data={{ labels: chartConfig.labels, datasets: (chartConfig.datasets.length ? chartConfig.datasets : [{ label: chartConfig.title || 'Value', data: [] }]).map((ds, idx) => ({ ...ds, borderColor: ds.borderColor || `hsl(${(idx*57)%360} 80% 50%)`, backgroundColor: ds.backgroundColor || `hsl(${(idx*57)%360} 80% 70% / 0.25)` })) }} />
                      )}
                      {chartConfig.type === 'scatter' && (
                        <Scatter data={{ datasets: (chartConfig.datasets.length ? chartConfig.datasets : [{ label: chartConfig.title || 'Value', data: [] }]).map((ds, idx) => ({ label: ds.label, data: (ds.data || []).map((y: number, i: number) => ({ x: i, y })), backgroundColor: `hsl(${(idx*57)%360} 70% 65%)` })) }} />
                      )}
                    </div>
                  )}
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-[#0b0f14]">
                        <tr>
                          {Object.keys(queryResults[0] || {}).map((key) => (
                            <th
                              key={key}
                              className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                            >
                              {key}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-[#0f141a] divide-y divide-gray-200 dark:divide-gray-800">
                        {queryResults.map((row, index) => (
                          <tr key={index}>
                            {Object.values(row).map((value: any, cellIndex) => (
                              <td
                                key={cellIndex}
                                className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100"
                              >
                                {String(value)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Examples */}
            <div className="mt-6">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Quick Examples</h3>
                <button
                  className="text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white p-2"
                  title="Refresh examples"
                  onClick={() => refreshExamples(selectedConnection)}
                  disabled={isRefreshingExamples || !selectedConnection}
                >
                  <RefreshCw className={`h-5 w-5 ${isRefreshingExamples ? 'animate-spin' : ''}`} />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(quickExamples.length ? quickExamples : [
                  'Top 10 vehicles by price',
                  'Average mileage by make',
                  'Vehicles newer than 2018 with mileage under 30,000',
                  'Count vehicles per fuel type',
                  'Monthly vehicle counts last 12 months',
                  'Average price by transmission'
                ]).map((example, index) => (
                  <button
                    key={index}
                    onClick={() => setPrompt(example)}
                    className="text-left p-4 bg-white dark:bg-[#0f141a] rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 hover:border-primary-300 dark:hover:border-gray-700 hover:shadow-md transition-all text-gray-900 dark:text-gray-100"
                  >
                    <div className="text-sm text-gray-900 dark:text-gray-100">{example}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
