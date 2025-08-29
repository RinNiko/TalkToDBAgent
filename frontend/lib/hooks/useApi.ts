"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "../api";
import { notify } from "../toast";

export function useApiGet<T = any>(url: string, deps: any[] = [], opts?: { immediate?: boolean; withToast?: boolean }) {
  const { immediate = true, withToast = true } = opts || {};
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiGet<T>(url);
      setData(res);
      return res;
    } catch (e: any) {
      const msg = String(e?.message || e);
      setError(msg);
      if (withToast) notify.error(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [url, withToast]);

  useEffect(() => {
    if (immediate) { reload(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return useMemo(() => ({ data, setData, loading, error, reload }), [data, loading, error, reload]);
}
