"use client";

import React, { useState } from "react";
import { AlertTriangle, BellOff, ShieldAlert } from "lucide-react";

interface AlertCardProps {
  active: boolean;
  title: string;
  description: string;
  onDismiss: () => Promise<void>;
}

export const AlertCard: React.FC<AlertCardProps> = ({
  active,
  title,
  description,
  onDismiss,
}) => {
  const [submitting, setSubmitting] = useState(false);

  if (!active) return null;

  const handleDismiss = async () => {
    setSubmitting(true);
    try {
      await onDismiss();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="col-span-1 md:col-span-2 lg:col-span-3 rounded-xl border border-rose-300 bg-rose-50/90 p-5 shadow-sm transition-all duration-200 animate-pulse">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-lg bg-rose-600 text-white shrink-0">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-700 bg-rose-200/60 px-2 py-0.5 rounded">
                경보 활성화됨
              </span>
              <h3 className="text-lg font-bold text-rose-950">{title}</h3>
            </div>
            <p className="mt-1 text-sm text-rose-800 leading-relaxed">
              {description}
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={submitting}
          onClick={handleDismiss}
          className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white text-sm font-semibold shadow-sm transition-colors duration-200 shrink-0 disabled:opacity-50"
        >
          <BellOff className="w-4 h-4" />
          {submitting ? "해제 중..." : "수동 알람 해제"}
        </button>
      </div>
    </div>
  );
};

export default AlertCard;
