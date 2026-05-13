import { Shield } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';

interface LoginPageProps {
  onLogin: () => void;
}

/**
 * Login page — Cloudflare Access handles all authentication.
 * There is NO username/password page inside the app (per core-functionality-features.md §3).
 * Users log in with Google Workspace through Cloudflare Access.
 * Passkey or hardware security key is required — password-only login is not allowed.
 *
 * In dev mode (VITE_DEV_AUTH=true), clicking the SSO button simulates
 * a dev-auth session by calling /api/v1/me with dev headers.
 */
export function LoginPage({ onLogin }: LoginPageProps) {
  const { theme } = useTheme();

  const handleSSOLogin = () => {
    // In production: Cloudflare Access intercepts this domain —
    // users never reach this page because CF Access gates the entire site.
    // In dev mode: simulate login by calling /api/v1/me with dev headers.
    onLogin();
  };

  return (
    <div className={`h-full w-full flex items-center justify-center overflow-hidden ${
      theme === 'dark'
        ? 'bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950'
        : 'bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50'
    }`}>
      {/* Animated Background Grid */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className={`absolute inset-0 ${theme === 'dark' ? 'opacity-10' : 'opacity-5'}`}>
          <div className="grid grid-cols-12 grid-rows-12 h-full w-full">
            {Array.from({ length: 144 }).map((_, i) => (
              <motion.div
                key={i}
                className={`border ${theme === 'dark' ? 'border-cyan-500/30' : 'border-cyan-600/20'}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.1, 0.3, 0.1] }}
                transition={{ duration: 3, repeat: Infinity, delay: i * 0.02 }}
              />
            ))}
          </div>
        </div>
        <motion.div
          className={`absolute top-1/4 left-1/4 w-64 h-64 rounded-full blur-3xl ${
            theme === 'dark' ? 'bg-cyan-500/10' : 'bg-cyan-400/15'
          }`}
          animate={{ x: [0, 100, 0], y: [0, -50, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className={`absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full blur-3xl ${
            theme === 'dark' ? 'bg-blue-500/10' : 'bg-blue-400/15'
          }`}
          animate={{ x: [0, -100, 0], y: [0, 50, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>

      {/* Login Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-flex w-20 h-20 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl items-center justify-center mb-6 shadow-2xl shadow-cyan-500/50"
          >
            <Shield className="w-10 h-10 text-white" />
          </motion.div>
          <h1 className={`text-3xl font-bold mb-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
            Panoptix
          </h1>
          <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>
            Secure CCTV Monitoring System
          </p>
        </div>

        {/* Login Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className={`backdrop-blur-xl border rounded-2xl p-8 shadow-2xl ${
            theme === 'dark'
              ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50'
              : 'bg-white/80 border-slate-200/80'
          }`}
        >
          <div className="space-y-6">
            {/* Info */}
            <div className="text-center">
              <p className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
                Sign in with your school Google Workspace account to access the CCTV dashboard.
              </p>
            </div>

            {/* Google SSO Button — the only login method */}
            <button
              type="button"
              onClick={handleSSOLogin}
              className="w-full flex items-center justify-center gap-3 px-4 py-3.5 bg-white hover:bg-gray-50 rounded-xl transition-all border border-gray-200 shadow-sm hover:shadow-md"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              <span className="font-semibold text-gray-700">Continue with Google Workspace</span>
            </button>

            {/* Requirements Info */}
            <div className={`space-y-3 text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 flex-shrink-0" />
                <span>Passkey or hardware security key required</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 flex-shrink-0" />
                <span>Identity verified by Cloudflare Access</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 flex-shrink-0" />
                <span>No self-registration — admin must add your account</span>
              </div>
            </div>
          </div>

          {/* Security Notice */}
          <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="text-emerald-400 font-medium mb-1">Secure Authentication</p>
                <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>
                  Protected by Cloudflare Access with Google Workspace SSO. Password-only login is not allowed.
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Footer */}
        <p className={`text-center text-sm mt-6 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
          Authorized personnel only. All access is logged and monitored.
        </p>
      </motion.div>
    </div>
  );
}
