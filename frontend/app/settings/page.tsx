'use client';

import { useState, useEffect } from 'react';
import { KeyRound, Server, Save } from 'lucide-react';

export default function SettingsPage() {
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [apiVersion, setApiVersion] = useState('');

  // Defaults to Vehicle Database
  const [dbName, setDbName] = useState('Vehicle Database');
  const [dbType, setDbType] = useState('postgresql');
  const [connString, setConnString] = useState('postgresql+psycopg2://postgres:postgres@localhost:5432/vehicles');
  const [isTesting, setIsTesting] = useState(false);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Auto-detect DB type from connection string
  useEffect(() => {
    if (!connString) return;
    const lower = connString.toLowerCase();
    if (lower.startsWith('postgres://') || lower.startsWith('postgresql://') || lower.startsWith('postgresql+')) {
      setDbType('postgresql');
      return;
    }
    if (lower.startsWith('mysql://') || lower.startsWith('mysql+')) {
      setDbType('mysql');
      return;
    }
    if (lower.startsWith('mssql://') || lower.startsWith('sqlserver://') || lower.startsWith('mssql+')) {
      setDbType('sqlserver');
      return;
    }
    if (lower.startsWith('sqlite://')) {
      setDbType('sqlite');
      return;
    }
  }, [connString]);

  const saveApiKey = async () => {
    // TODO: wire to backend /api/keys
    console.log('Save API key', { provider, apiKey, endpoint, apiVersion });
  };

  const saveConnection = async () => {
    // TODO: wire to backend /api/connections
    console.log('Save connection', { dbName, dbType, connString });
  };

  const testConnection = async () => {
    if (!connString.trim()) {
      setTestSuccess(false);
      setTestMessage('Please enter a connection string');
      return;
    }
    setIsTesting(true);
    setTestMessage(null);
    setTestSuccess(null);
    try {
      const res = await fetch('/api/connections/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_string: connString, timeout_seconds: 5 }),
      });
      let data: any = null;
      try { data = await res.json(); } catch { /* non-JSON error */ }
      if (res.ok) {
        setTestSuccess(true);
        setTestMessage((data && data.message) ? data.message : 'Connection successful');
      } else {
        const text = data?.detail || data?.message || (await res.text().catch(() => '')) || 'Connection failed';
        setTestSuccess(false);
        setTestMessage(text);
      }
    } catch (err: any) {
      setTestSuccess(false);
      setTestMessage(err?.message || 'Connection failed');
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

        {/* API Keys */}
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6 mb-8">
          <div className="flex items-center mb-4">
            <KeyRound className="h-5 w-5 text-primary-600" />
            <h2 className="ml-2 text-lg font-semibold text-gray-900">LLM API Keys</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)} className="input-field">
                <option value="openai">OpenAI</option>
                <option value="azure_openai">Azure OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
                <option value="groq">Groq</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
              <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type="password" className="input-field" placeholder="sk-..." />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Endpoint (optional)</label>
              <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} type="text" className="input-field" placeholder="https://..." />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">API Version (optional)</label>
              <input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} type="text" className="input-field" placeholder="2024-02-15-preview" />
            </div>
          </div>

          <div className="mt-4">
            <button onClick={saveApiKey} className="btn-primary">
              <Save className="h-4 w-4 mr-2 inline" /> Save API Key
            </button>
          </div>
        </div>

        {/* DB Connections */}
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <div className="flex items-center mb-4">
            <Server className="h-5 w-5 text-primary-600" />
            <h2 className="ml-2 text-lg font-semibold text-gray-900">Database Connections</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
              <input value={dbName} onChange={(e) => setDbName(e.target.value)} type="text" className="input-field" placeholder="Vehicle Database" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type (auto-detected)</label>
              <select value={dbType} onChange={(e) => setDbType(e.target.value)} className="input-field" disabled>
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="sqlserver">SQL Server</option>
                <option value="sqlite">SQLite</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Connection String</label>
              <input value={connString} onChange={(e) => setConnString(e.target.value)} type="text" className="input-field" placeholder="postgresql+psycopg2://postgres:postgres@localhost:5432/vehicles" />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button onClick={saveConnection} className="btn-primary">
              <Save className="h-4 w-4 mr-2 inline" /> Save Connection
            </button>
            <button onClick={testConnection} className="btn-secondary" disabled={isTesting}>
              {isTesting ? 'Testing...' : 'Test Connection'}
            </button>
            {testMessage && (
              <span className={testSuccess ? 'text-green-600 text-sm' : 'text-red-600 text-sm'}>
                {testMessage}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
