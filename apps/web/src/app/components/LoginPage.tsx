import { Shield } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';

interface LoginPageProps {
  onLogin: () => void;
  authError?: string | null;
}

/**
 * Login page. Cloudflare Access handles all authentication.
 * There is no username/password page inside the app.
 * Users sign in through the configured Cloudflare Access identity provider.
 *
 * In dev mode (VITE_DEV_AUTH=true), clicking the SSO button simulates
 * a dev-auth session by calling /api/v1/me with dev headers.
 */
export function LoginPage({ onLogin, authError }: LoginPageProps) {
  const { theme } = useTheme();

  const handleSSOLogin = () => {
    // In production: Cloudflare Access intercepts this domain.
    // users never reach this page because CF Access gates the entire site.
    // In dev mode: simulate login by calling /api/v1/me with dev headers.
    onLogin();
  };

  return (
    <div className={`h-full w-full flex items-center justify-center overflow-hidden ${
      theme === 'dark'
        ? 'bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950'
        : 'bg-gradient-to-br from-slate-50 via-orange-50/30 to-amber-50/20'
    }`}>
      {/* Animated Background Grid */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className={`absolute inset-0 ${theme === 'dark' ? 'opacity-10' : 'opacity-5'}`}>
          <div className="grid grid-cols-12 grid-rows-12 h-full w-full">
            {Array.from({ length: 144 }).map((_, i) => (
              <motion.div
                key={i}
                className={`border ${theme === 'dark' ? 'border-orange-500/30' : 'border-orange-600/20'}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.1, 0.3, 0.1] }}
                transition={{ duration: 3, repeat: Infinity, delay: i * 0.02 }}
              />
            ))}
          </div>
        </div>
        <motion.div
          className={`absolute top-1/4 left-1/4 w-64 h-64 rounded-full blur-3xl ${
            theme === 'dark' ? 'bg-orange-500/10' : 'bg-orange-400/15'
          }`}
          animate={{ x: [0, 100, 0], y: [0, -50, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className={`absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full blur-3xl ${
            theme === 'dark' ? 'bg-amber-500/10' : 'bg-amber-400/15'
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
          <motion.img
            src="/logo.png"
            alt="Panoptix"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-block w-20 h-20 rounded-2xl mb-6 shadow-2xl shadow-orange-500/50"
          />
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
                Sign in through Cloudflare Access to access the CCTV dashboard.
              </p>
            </div>

            {authError === 'user-disabled' && (
              <div className="p-3 bg-red-500/10 border border-red-500/25 rounded-lg text-sm text-red-400">
                This Panoptix account is disabled. Contact an administrator; signing in through Cloudflare Access will not re-enable it.
              </div>
            )}

            {/* Cloudflare Access button. In production, users normally see the Access page before the app. */}
            <button
              type="button"
              onClick={handleSSOLogin}
              className="w-full flex items-center justify-center gap-3 px-4 py-3.5 bg-white hover:bg-gray-50 rounded-lg transition-all border border-gray-200 shadow-sm hover:shadow-md"
            >
              <Shield className="w-5 h-5 text-orange-600" />
              <span className="font-semibold text-gray-700">Continue with Cloudflare Access</span>
            </button>

            {/* Requirements Info */}
            <div className={`space-y-3 text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-orange-500 flex-shrink-0" />
                <span>Identity provider and MFA policy enforced by Cloudflare Access</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-orange-500 flex-shrink-0" />
                <span>Identity verified by Cloudflare Access</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-orange-500 flex-shrink-0" />
                <span>No self-registration - admin must add your account</span>
              </div>
            </div>
          </div>

          {/* Security Notice */}
          <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="text-emerald-400 font-medium mb-1">Secure Authentication</p>
                <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>
                  Protected by Cloudflare Access. Password-only application login is not available.
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
