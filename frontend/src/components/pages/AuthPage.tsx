/**
 * 認證頁面 - 登入 / 註冊 / 忘記密碼
 * 使用 Tailwind CSS 深色主題，與現有頁面風格一致
 */
import React, { useState } from 'react';

// ── 類型定義 ────────────────────────────────────────────────────────────────

type AuthMode = 'login' | 'register' | 'forgot';

interface FormFields {
  email: string;
  password: string;
  confirmPassword: string;
  username: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  username?: string;
  general?: string;
}

// ── 驗證函式 ────────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const validateLogin = (fields: FormFields): FormErrors => {
  const errs: FormErrors = {};
  if (!fields.email.trim()) errs.email = '請輸入 Email';
  else if (!EMAIL_RE.test(fields.email)) errs.email = 'Email 格式不正確';
  if (!fields.password) errs.password = '請輸入密碼';
  return errs;
};

const validateRegister = (fields: FormFields): FormErrors => {
  const errs: FormErrors = {};
  if (!fields.username.trim()) errs.username = '請輸入使用者名稱';
  else if (fields.username.trim().length < 2) errs.username = '使用者名稱至少 2 個字元';
  if (!fields.email.trim()) errs.email = '請輸入 Email';
  else if (!EMAIL_RE.test(fields.email)) errs.email = 'Email 格式不正確';
  if (!fields.password) errs.password = '請輸入密碼';
  else if (fields.password.length < 8) errs.password = '密碼至少 8 個字元';
  if (!fields.confirmPassword) errs.confirmPassword = '請再次輸入密碼';
  else if (fields.password !== fields.confirmPassword) errs.confirmPassword = '兩次密碼不相符';
  return errs;
};

const validateForgot = (fields: FormFields): FormErrors => {
  const errs: FormErrors = {};
  if (!fields.email.trim()) errs.email = '請輸入 Email';
  else if (!EMAIL_RE.test(fields.email)) errs.email = 'Email 格式不正確';
  return errs;
};

// ── Input 元件 ─────────────────────────────────────────────────────────────

interface InputProps {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  placeholder?: string;
  autoComplete?: string;
}

const Input: React.FC<InputProps> = ({
  label, type = 'text', value, onChange, error, placeholder, autoComplete,
}) => (
  <div className="space-y-1">
    <label className="block text-xs text-gray-400 font-medium">{label}</label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={autoComplete}
      className={`w-full bg-slate-700 border rounded px-3 py-2 text-white placeholder-gray-500
        focus:outline-none focus:ring-2 focus:ring-yellow-500/50 transition text-sm
        ${error ? 'border-red-500' : 'border-slate-600'}`}
    />
    {error && <p className="text-red-400 text-xs">{error}</p>}
  </div>
);

// ── 主元件 ──────────────────────────────────────────────────────────────────

const AuthPage: React.FC = () => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false); // 忘記密碼 email 送出
  const [errors, setErrors] = useState<FormErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  const [fields, setFields] = useState<FormFields>({
    email: '',
    password: '',
    confirmPassword: '',
    username: '',
  });

  const set = (key: keyof FormFields) => (v: string) => {
    setFields((f) => ({ ...f, [key]: v }));
    setErrors((e) => ({ ...e, [key]: undefined }));
    setGeneralError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setGeneralError(null);

    let errs: FormErrors = {};
    if (mode === 'login') errs = validateLogin(fields);
    else if (mode === 'register') errs = validateRegister(fields);
    else errs = validateForgot(fields);

    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setLoading(true);
    try {
      // ── 預留：替換為真實 API 調用 ──────────────────────────────────────
      // await authApi.login(fields.email, fields.password);
      // await authApi.register(fields.username, fields.email, fields.password);
      // await authApi.forgotPassword(fields.email);
      await new Promise((r) => setTimeout(r, 1000)); // mock delay
      // ─────────────────────────────────────────────────────────────────
      if (mode === 'forgot') { setSent(true); }
      else {
        // 登入/註冊成功後可 redirect，這裡僅示意
        console.log(`${mode} success`, fields.email);
      }
    } catch (err: any) {
      setGeneralError(err?.message ?? '操作失敗，請稍後再試');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (m: AuthMode) => {
    setMode(m);
    setErrors({});
    setGeneralError(null);
    setSent(false);
  };

  const btnCls = (active: boolean) =>
    `px-4 py-1.5 rounded text-sm font-medium transition-colors ${
      active
        ? 'bg-yellow-600 text-white'
        : 'bg-slate-700 text-gray-400 hover:bg-slate-600'
    }`;

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">

        {/* Logo / Title */}
        <div className="text-center">
          <div className="text-4xl mb-2">🥇</div>
          <h1 className="text-2xl font-bold text-white">黃金分析系統</h1>
          <p className="text-gray-400 text-sm mt-1">專業黃金價格分析與決策輔助</p>
        </div>

        {/* Mode Tabs */}
        <div className="flex bg-slate-800 rounded-lg p-1">
          {(['login', 'register', 'forgot'] as AuthMode[]).map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={btnCls(mode === m)}
            >
              {m === 'login' ? '登入' : m === 'register' ? '註冊' : '忘記密碼'}
            </button>
          ))}
        </div>

        {/* Form Card */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">

          {/* 忘記密碼成功 */}
          {sent ? (
            <div className="text-center space-y-4">
              <div className="text-5xl">📧</div>
              <h2 className="text-lg font-semibold text-white">重置郵件已發送</h2>
              <p className="text-gray-400 text-sm">
                我們已將密碼重置連結發送至<br />
                <span className="text-yellow-400">{fields.email}</span>
              </p>
              <button
                onClick={() => switchMode('login')}
                className="w-full bg-yellow-600 hover:bg-yellow-500 text-white py-2 rounded-lg text-sm font-medium transition-colors"
              >
                返回登入
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>

              {/* 一般錯誤 */}
              {generalError && (
                <div className="bg-red-900/30 text-red-400 p-3 rounded-lg text-sm">
                  ⚠️ {generalError}
                </div>
              )}

              {/* 登入 */}
              {mode === 'login' && (
                <>
                  <Input
                    label="Email"
                    type="email"
                    value={fields.email}
                    onChange={set('email')}
                    error={errors.email}
                    placeholder="your@email.com"
                    autoComplete="email"
                  />
                  <Input
                    label="密碼"
                    type="password"
                    value={fields.password}
                    onChange={set('password')}
                    error={errors.password}
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => switchMode('forgot')}
                      className="text-xs text-gray-400 hover:text-yellow-400 transition-colors"
                    >
                      忘記密碼？
                    </button>
                  </div>
                </>
              )}

              {/* 註冊 */}
              {mode === 'register' && (
                <>
                  <Input
                    label="使用者名稱"
                    value={fields.username}
                    onChange={set('username')}
                    error={errors.username}
                    placeholder="輸入使用者名稱"
                    autoComplete="username"
                  />
                  <Input
                    label="Email"
                    type="email"
                    value={fields.email}
                    onChange={set('email')}
                    error={errors.email}
                    placeholder="your@email.com"
                    autoComplete="email"
                  />
                  <Input
                    label="密碼"
                    type="password"
                    value={fields.password}
                    onChange={set('password')}
                    error={errors.password}
                    placeholder="至少 8 個字元"
                    autoComplete="new-password"
                  />
                  <Input
                    label="確認密碼"
                    type="password"
                    value={fields.confirmPassword}
                    onChange={set('confirmPassword')}
                    error={errors.confirmPassword}
                    placeholder="再次輸入密碼"
                    autoComplete="new-password"
                  />
                </>
              )}

              {/* 忘記密碼 */}
              {mode === 'forgot' && (
                <>
                  <p className="text-gray-400 text-sm">
                    輸入您的註冊 Email，我們會寄送密碼重置連結給您。
                  </p>
                  <Input
                    label="Email"
                    type="email"
                    value={fields.email}
                    onChange={set('email')}
                    error={errors.email}
                    placeholder="your@email.com"
                    autoComplete="email"
                  />
                </>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full py-2.5 rounded-lg text-white text-sm font-semibold transition-colors
                  ${loading
                    ? 'bg-slate-600 cursor-not-allowed'
                    : 'bg-yellow-600 hover:bg-yellow-500'
                  }`}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    處理中...
                  </span>
                ) : (
                  mode === 'login' ? '登入' : mode === 'register' ? '建立帳戶' : '發送重置連結'
                )}
              </button>
            </form>
          )}
        </div>

        {/* Footer hint */}
        {mode !== 'forgot' && (
          <p className="text-center text-gray-500 text-xs">
            {mode === 'login' ? '還沒有帳戶？' : '已有帳戶？'}
            {' '}
            <button
              onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
              className="text-yellow-400 hover:text-yellow-300 transition-colors"
            >
              {mode === 'login' ? '立即註冊' : '返回登入'}
            </button>
          </p>
        )}
      </div>
    </div>
  );
};

export default AuthPage;
