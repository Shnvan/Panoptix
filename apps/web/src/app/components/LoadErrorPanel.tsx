import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useTheme } from '../../lib/theme';

interface LoadErrorPanelProps {
  title: string;
  message: string;
  onRetry: () => void;
}

export function LoadErrorPanel({ title, message, onRetry }: LoadErrorPanelProps) {
  const { theme } = useTheme();
  const d = theme === 'dark';

  return (
    <div
      role="alert"
      className={`flex flex-col items-start gap-3 border p-5 sm:flex-row sm:items-center sm:justify-between ${
        d ? 'border-red-500/30 bg-red-500/10' : 'border-red-200 bg-red-50'
      }`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
        <div className="min-w-0">
          <h3 className={`font-semibold ${d ? 'text-red-300' : 'text-red-800'}`}>{title}</h3>
          <p className={`mt-1 break-words text-sm ${d ? 'text-red-200/80' : 'text-red-700'}`}>{message}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className={`inline-flex shrink-0 items-center gap-2 px-3 py-2 text-sm font-medium ${
          d ? 'bg-red-500/20 text-red-200 hover:bg-red-500/30' : 'bg-white text-red-700 hover:bg-red-100'
        }`}
      >
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </div>
  );
}
