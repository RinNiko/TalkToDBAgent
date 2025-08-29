"use client";

import { toast } from "react-hot-toast";

export const notify = {
  success: (msg: string, opts?: any) => toast.success(msg, opts),
  error: (msg: string, opts?: any) => toast.error(msg, opts),
  loading: (msg: string, opts?: any) => toast.loading(msg, opts),
  dismiss: (id?: string) => toast.dismiss(id),
};
