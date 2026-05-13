import { Shield, FileText } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';

interface PrivacyNoticeModalProps {
  title: string;
  body: string;
  version: string;
  onAccept: () => void;
  loading?: boolean;
}

export function PrivacyNoticeModal({ title, body, version, onAccept, loading }: PrivacyNoticeModalProps) {
  const { theme } = useTheme();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{
      backgroundColor: theme === 'dark' ? 'rgba(0,0,0,0.9)' : 'rgba(0,0,0,0.6)'
    }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`max-w-lg w-full border rounded-2xl shadow-2xl overflow-hidden ${
          theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        }`}
      >
        <div className="p-8 text-center">
          <div className="w-20 h-20 mx-auto bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-xl shadow-cyan-500/30">
            <Shield className="w-10 h-10 text-white" />
          </div>
          <h2 className={`text-2xl font-bold mb-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>{title}</h2>
          <p className={`text-sm mb-6 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Version: {version}</p>
        </div>

        <div className={`px-8 pb-6 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
          <div className={`p-4 rounded-xl border mb-6 ${
            theme === 'dark' ? 'bg-slate-800/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'
          }`}>
            <div className="flex items-start gap-3">
              <FileText className={`w-5 h-5 flex-shrink-0 mt-0.5 ${theme === 'dark' ? 'text-cyan-400' : 'text-cyan-600'}`} />
              <p className="text-sm leading-relaxed">{body}</p>
            </div>
          </div>
          <ul className="space-y-2 text-sm mb-8">
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-cyan-500 rounded-full" /> Access is logged and audited</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-cyan-500 rounded-full" /> Recording or sharing views is prohibited</li>
            <li className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-cyan-500 rounded-full" /> Sessions expire after idle timeout</li>
          </ul>
          <button
            onClick={onAccept}
            disabled={loading}
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold py-3 rounded-xl shadow-lg shadow-cyan-500/30 transition-all disabled:opacity-50"
          >
            {loading ? 'Accepting...' : 'I Accept & Understand'}
          </button>
          <p className={`text-center text-xs mt-4 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
            You must accept this notice to use the system. This acceptance is logged.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
