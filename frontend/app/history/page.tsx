"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, Pin, PinOff, Trash2, Play } from "lucide-react";
import { apiPost } from "../../lib/api";
import { Toaster } from "react-hot-toast";
import ThemeToggle from "../../components/ThemeToggle";
import { useApiGet } from "../../lib/hooks/useApi";
import { notify } from "../../lib/toast";

interface HistoryItem {
  id: number;
  connection_id: number;
  prompt?: string | null;
  sql: string;
  row_count: number;
  execution_time_ms: number;
  success: boolean;
  error?: string | null;
  pinned: boolean;
  created_at: string;
}

export default function HistoryPage() {
  const { data, loading, error, reload, setData } = useApiGet<{ items: HistoryItem[] }>("/api/history?limit=200", []);
  const items = data?.items || [];

  useEffect(() => { if (error) notify.error(error); }, [error]);

  async function rerun(id: number) {
    try {
      notify.loading("Rerunning...", { id: `rerun-${id}` });
      const result = await apiPost(`/api/history/${id}/rerun`, {});
      notify.success("Reran query", { id: `rerun-${id}` });
      return result;
    } catch (e: any) {
      notify.error(String(e?.message || e), { id: `rerun-${id}` });
    }
  }

  async function togglePin(id: number, pinned: boolean) {
    try {
      await apiPost(`/api/history/${id}/pin?pinned=${!pinned}`, {});
      setData((prev: any) => ({ items: (prev?.items || []).map((it: HistoryItem) => it.id === id ? { ...it, pinned: !pinned } : it) }));
    } catch (e: any) {
      notify.error(String(e?.message || e));
    }
  }

  async function remove(id: number) {
    try {
      await fetch(`/api/history/${id}`, { method: "DELETE" });
      setData((prev: any) => ({ items: (prev?.items || []).filter((it: HistoryItem) => it.id !== id) }));
    } catch (e: any) {
      notify.error(String(e?.message || e));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
      <Toaster position="top-right" />
      <header className="bg-white shadow-sm border-b border-gray-200 dark:bg-gray-800 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <Link href="/studio" className="text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white">Studio</Link>
              <span className="text-gray-300">/</span>
              <span className="text-gray-900 dark:text-gray-100 font-semibold">History</span>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button onClick={reload} disabled={loading} className="inline-flex items-center rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          {loading && (
            <div className="p-6 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2"><RefreshCw className="h-4 w-4 animate-spin"/> Loading...</div>
          )}
          {!loading && (
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Pinned</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Conn</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">SQL</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Rows</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Time (ms)</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {items.map(item => (
                  <tr key={item.id} className={!item.success ? 'bg-red-50 dark:bg-red-900/20' : ''}>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <button onClick={() => togglePin(item.id, item.pinned)} className="text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white">
                        {item.pinned ? <Pin className="h-4 w-4" /> : <PinOff className="h-4 w-4" />}
                      </button>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{item.connection_id}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 align-top">
                      <div className="max-w-xl whitespace-pre-wrap break-words line-clamp-2" title={item.sql}>{item.sql}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{item.row_count}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">{item.execution_time_ms}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                      <div className="inline-flex items-center gap-2">
                        <button onClick={() => rerun(item.id)} className="inline-flex items-center rounded-md bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 text-xs"><Play className="h-4 w-4 mr-1"/>Rerun</button>
                        <button onClick={() => remove(item.id)} className="inline-flex items-center rounded-md border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 px-2.5 py-1 text-xs"><Trash2 className="h-4 w-4 mr-1"/>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-500 dark:text-gray-400">No history yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
