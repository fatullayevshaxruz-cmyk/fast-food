import React, { useState, useEffect, useCallback } from 'react';

/**
 * Telegram Mini App (WebApp) — iOS Style UI
 * Primary Accent: Crimson Red (#E50914)
 * Stack: React 18 + Tailwind CSS + Telegram WebApp SDK
 */

// ─── Phone Mask Formatter (+998 (XX) XXX-XX-XX) ──────────────────────
export function formatUzPhone(digitsOnly) {
  const clean = digitsOnly.replace(/\D/g, '').slice(0, 9);
  if (clean.length === 0) return '';
  if (clean.length <= 2) return `(${clean}`;
  if (clean.length <= 5) return `(${clean.slice(0, 2)}) ${clean.slice(2)}`;
  if (clean.length <= 7) return `(${clean.slice(0, 2)}) ${clean.slice(2, 5)}-${clean.slice(5)}`;
  return `(${clean.slice(0, 2)}) ${clean.slice(2, 5)}-${clean.slice(5, 7)}-${clean.slice(7, 9)}`;
}

// ─── Payment Methods Component ("Оплата / Способы оплаты") ────────────
export function PaymentMethodsCard({ selected, onSelect }) {
  const methods = [
    {
      id: 'cash',
      title: 'Наличные',
      icon: (
        <svg className="w-[27px] h-[22px] shrink-0" viewBox="0 0 32 26" fill="none">
          <rect x="1.5" y="2" width="23" height="15.5" rx="4" stroke="#68686E" strokeWidth="2.1" fill="none" />
          <line x1="6.5" y1="6.8" x2="6.5" y2="12.7" stroke="#68686E" strokeWidth="2.1" strokeLinecap="round" />
          <circle cx="13" cy="9.75" r="2.8" stroke="#68686E" strokeWidth="2.1" fill="none" />
          <line x1="19.5" y1="6.8" x2="19.5" y2="12.7" stroke="#68686E" strokeWidth="2.1" strokeLinecap="round" />
          <path
            d="M5.5 21H23.5C26.2614 21 28.5 18.7614 28.5 16V6.5"
            stroke="#68686E"
            strokeWidth="2.1"
            strokeLinecap="round"
          />
        </svg>
      ),
    },
    {
      id: 'payme',
      title: 'Payme',
      icon: (
        <svg className="w-[34px] h-[26px] shrink-0" viewBox="0 0 44 34" fill="none">
          <text
            x="1"
            y="12.5"
            fill="#2B2B30"
            fontSize="13.5"
            fontWeight="800"
            letterSpacing="-0.3"
            fontFamily="-apple-system, BlinkMacSystemFont, 'SF Pro Display', Inter, sans-serif"
          >
            Pay
          </text>
          <path
            d="M1 18C1 16.3431 2.34315 15 4 15H26.5C27.5 15 28.44 15.47 29.04 16.27L34.2 23.2C34.68 23.85 34.68 24.75 34.2 25.4L29.04 32.33C28.44 33.13 27.5 33.6 26.5 33.6H4C2.34315 33.6 1 32.2569 1 30.6V18Z"
            fill="#3CC4C7"
          />
          <text
            x="4.5"
            y="27.8"
            fill="#FFFFFF"
            fontSize="12.5"
            fontWeight="800"
            letterSpacing="-0.3"
            fontFamily="-apple-system, BlinkMacSystemFont, 'SF Pro Display', Inter, sans-serif"
          >
            me
          </text>
        </svg>
      ),
    },
    {
      id: 'click',
      title: 'Click',
      icon: (
        <svg className="w-[26px] h-[26px] shrink-0" viewBox="0 0 32 32" fill="none">
          <rect
            x="16"
            y="2.2"
            width="19.5"
            height="19.5"
            rx="6.2"
            transform="rotate(45 16 2.2)"
            fill="#0077FF"
          />
          <circle cx="16" cy="16" r="5" fill="#FFFFFF" />
        </svg>
      ),
    },
  ];

  return (
    <div className="bg-white rounded-[24px] px-5 py-5">
      <h3 className="text-[22px] font-bold tracking-[-0.02em] text-black leading-none">
        Оплата
      </h3>
      <p className="text-[15px] font-normal text-[#707070] mt-4 mb-3.5">
        Способы оплаты
      </p>

      <div className="grid grid-cols-2 gap-[12px]">
        {methods.map((m) => {
          const isActive = selected === m.id;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onSelect(m.id)}
              className={`h-[52px] px-[18px] rounded-[14px] bg-[#F5F5F5] flex items-center justify-between transition-all duration-150 active:scale-[0.98] ${
                isActive
                  ? 'border-[1.8px] border-[#E50914]'
                  : 'border-[1.8px] border-transparent'
              }`}
            >
              {m.icon}
              <span className="text-[15px] font-normal text-black tracking-[-0.01em]">{m.title}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Custom iOS Numeric Keypad for OTP ───────────────────────────────
export function NumericKeypad({ onDigit, onBackspace, onClear }) {
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
  const subLabels = {
    '2': 'ABC',
    '3': 'DEF',
    '4': 'GHI',
    '5': 'JKL',
    '6': 'MNO',
    '7': 'PQRS',
    '8': 'TUV',
    '9': 'WXYZ',
  };

  return (
    <div className="bg-neutral-100/95 backdrop-blur-xl pt-3 pb-5 px-4 rounded-t-3xl border-t border-neutral-200/80 shadow-[0_-10px_30px_rgba(0,0,0,0.05)] select-none">
      <div className="w-10 h-1 bg-neutral-300 rounded-full mx-auto mb-3" />
      <div className="grid grid-cols-3 gap-2.5 max-w-md mx-auto">
        {keys.map((digit) => (
          <button
            key={digit}
            type="button"
            onClick={() => onDigit(digit)}
            className="h-13 py-2 rounded-2xl bg-white hover:bg-neutral-50 active:bg-neutral-200 active:scale-95 transition-all duration-150 shadow-[0_1px_2px_rgba(0,0,0,0.08)] flex flex-col items-center justify-center"
          >
            <span className="text-[22px] font-semibold leading-none text-neutral-900">{digit}</span>
            <span className="text-[9px] font-bold tracking-[0.18em] text-neutral-400 mt-0.5 h-2.5">
              {subLabels[digit] || ''}
            </span>
          </button>
        ))}

        {/* Clear button */}
        <button
          type="button"
          onClick={onClear}
          className="h-13 py-2 rounded-2xl bg-neutral-200/70 hover:bg-neutral-200 active:scale-95 transition-all duration-150 flex items-center justify-center text-xs font-semibold text-neutral-600"
        >
          Очистить
        </button>

        {/* 0 button */}
        <button
          type="button"
          onClick={() => onDigit('0')}
          className="h-13 py-2 rounded-2xl bg-white hover:bg-neutral-50 active:bg-neutral-200 active:scale-95 transition-all duration-150 shadow-[0_1px_2px_rgba(0,0,0,0.08)] flex flex-col items-center justify-center"
        >
          <span className="text-[22px] font-semibold leading-none text-neutral-900">0</span>
          <span className="text-[9px] font-bold text-neutral-400 mt-0.5">+</span>
        </button>

        {/* Backspace button */}
        <button
          type="button"
          onClick={onBackspace}
          className="h-13 py-2 rounded-2xl bg-neutral-200/70 hover:bg-neutral-200 active:bg-[#E50914]/15 active:text-[#E50914] active:scale-95 transition-all duration-150 flex items-center justify-center text-neutral-800"
          aria-label="Удалить"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─── Bottom Navigation Bar (4 Tabs with Badge & Active Crimson State) ─
export function BottomNavBar({ activeTab, onChangeTab, cartCount = 1 }) {
  const navItems = [
    {
      id: 'home',
      label: 'Главная',
      icon: (active) => (
        <svg className="w-6 h-6" fill={active ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      id: 'cart',
      label: 'Корзина',
      badge: cartCount > 0 ? cartCount : 1,
      icon: (active) => (
        <svg className="w-6 h-6" fill={active ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      id: 'orders',
      label: 'Заказ',
      icon: (active) => (
        <svg className="w-6 h-6" fill={active ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
        </svg>
      ),
    },
    {
      id: 'profile',
      label: 'Профиль',
      icon: (active) => (
        <svg className="w-6 h-6" fill={active ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
    },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-xl border-t border-neutral-200/80 pb-safe">
      <div className="max-w-md mx-auto flex items-center justify-around h-16 px-2">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeTab(item.id)}
              className={`relative flex-1 flex flex-col items-center justify-center py-1.5 transition-all duration-200 active:scale-90 ${
                isActive ? 'text-[#E50914]' : 'text-neutral-400 hover:text-neutral-600'
              }`}
            >
              <div className="relative">
                {item.icon(isActive)}
                {item.badge ? (
                  <span className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] px-1 rounded-full bg-[#E50914] text-white text-[10px] font-extrabold flex items-center justify-center shadow-sm ring-2 ring-white">
                    {item.badge}
                  </span>
                ) : null}
              </div>
              <span className={`text-[11px] mt-1 tracking-tight ${isActive ? 'font-bold text-[#E50914]' : 'font-medium'}`}>
                {item.label}
              </span>
              {isActive && (
                <span className="absolute top-0 w-8 h-0.5 rounded-full bg-[#E50914]" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

// ─── Main App Component ──────────────────────────────────────────────
export default function App() {
  // Default active tab: 'profile' (Профиль - qizil rangdagi faol holat)
  const [activeTab, setActiveTab] = useState('profile');

  // Auth Flow State: 'phone' -> 'otp' -> 'authenticated'
  const [authStep, setAuthStep] = useState('phone');
  const [phoneDigits, setPhoneDigits] = useState('901234567');
  const [sendMethod, setSendMethod] = useState('telegram'); // 'telegram' | 'sms'
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [timer, setTimer] = useState(57);

  // Payment method state ('payme' active by default with Crimson Red border)
  const [paymentMethod, setPaymentMethod] = useState('payme');

  // Countdown timer for OTP screen
  useEffect(() => {
    if (authStep !== 'otp') return;
    if (timer <= 0) return;
    const id = setInterval(() => {
      setTimer((t) => (t > 0 ? t - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, [authStep, timer]);

  const handlePhoneInput = (e) => {
    const raw = e.target.value.replace(/\D/g, '');
    const stripped = raw.startsWith('998') ? raw.slice(3) : raw;
    setPhoneDigits(stripped.slice(0, 9));
  };

  const handleSendCode = () => {
    if (phoneDigits.length < 9) return;
    setOtpDigits(['', '', '', '', '', '']);
    setTimer(57);
    setAuthStep('otp');
  };

  const handleOtpDigit = useCallback((digit) => {
    setOtpDigits((prev) => {
      const idx = prev.findIndex((d) => d === '');
      if (idx === -1) return prev;
      const next = [...prev];
      next[idx] = digit;
      return next;
    });
  }, []);

  const handleOtpBackspace = useCallback(() => {
    setOtpDigits((prev) => {
      const reversedIdx = [...prev].reverse().findIndex((d) => d !== '');
      if (reversedIdx === -1) return prev;
      const actualIdx = 5 - reversedIdx;
      const next = [...prev];
      next[actualIdx] = '';
      return next;
    });
  }, []);

  const handleOtpClear = useCallback(() => {
    setOtpDigits(['', '', '', '', '', '']);
  }, []);

  const formattedPhone = `+998 ${formatUzPhone(phoneDigits)}`;
  const formattedTimer = `00:${String(timer).padStart(2, '0')}`;

  return (
    <div className="min-h-screen bg-[#F2F2F7] text-neutral-900 font-sans pb-24">
      <div className="max-w-md mx-auto px-4 pt-4 space-y-4">
        {/* Step 1: Phone Input & Method Selection */}
        {authStep === 'phone' && (
          <div className="bg-white rounded-3xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-neutral-100 space-y-5">
            <div>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E50914]/10 text-[#E50914] text-xs font-bold mb-2">
                🍔 Darxan Burger ID
              </span>
              <h1 className="text-2xl font-extrabold tracking-tight text-neutral-900">
                Авторизация
              </h1>
              <p className="text-sm text-neutral-500 mt-1">
                Введите номер телефона для быстрого входа и оформления заказа
              </p>
            </div>

            {/* +998 Phone Input with Mask */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-2">
                Номер телефона
              </label>
              <div className="flex items-center rounded-2xl border-2 border-neutral-200 focus-within:border-[#E50914] bg-neutral-50 px-4 py-3.5 transition-all">
                <span className="text-base font-bold text-neutral-900 pr-3 border-r border-neutral-200 select-none">
                  🇺🇿 +998
                </span>
                <input
                  type="tel"
                  value={formatUzPhone(phoneDigits)}
                  onChange={handlePhoneInput}
                  placeholder="(90) 123-45-67"
                  className="w-full pl-3 bg-transparent text-base font-semibold text-neutral-900 focus:outline-none"
                />
              </div>
            </div>

            {/* Куда отправить код? */}
            <div>
              <label className="block text-sm font-bold text-neutral-800 mb-2.5">
                Куда отправить код?
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => setSendMethod('telegram')}
                  className={`flex items-center justify-center gap-2 py-3 px-3 rounded-2xl border-2 font-semibold text-sm transition-all ${
                    sendMethod === 'telegram'
                      ? 'border-[#E50914] bg-[#E50914]/5 text-[#E50914]'
                      : 'border-neutral-200 bg-neutral-50 text-neutral-700'
                  }`}
                >
                  <span>✈️</span>
                  <span>Telegram</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSendMethod('sms')}
                  className={`flex items-center justify-center gap-2 py-3 px-3 rounded-2xl border-2 font-semibold text-sm transition-all ${
                    sendMethod === 'sms'
                      ? 'border-[#E50914] bg-[#E50914]/5 text-[#E50914]'
                      : 'border-neutral-200 bg-neutral-50 text-neutral-700'
                  }`}
                >
                  <span>💬</span>
                  <span>По SMS</span>
                </button>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2.5 pt-1">
              <button
                type="button"
                onClick={handleSendCode}
                className="w-full py-4 rounded-2xl bg-[#E50914] hover:bg-[#cc0812] active:scale-[0.98] text-white font-bold text-base shadow-[0_8px_20px_rgba(229,9,20,0.3)] transition-all"
              >
                Выслать код
              </button>

              <button
                type="button"
                className="w-full py-3.5 rounded-2xl bg-neutral-100 hover:bg-neutral-200/80 active:scale-[0.98] text-neutral-800 font-semibold text-sm flex items-center justify-center gap-2.5 transition-all"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.8C6.2 7.2 8.9 5 12 5z" />
                  <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.6l3.7 2.9c2.2-2 3.7-5 3.7-8.7z" />
                  <path fill="#FBBC05" d="M5.3 14.8c-.2-.8-.4-1.6-.4-2.5s.2-1.7.4-2.5L1.6 7C.6 9 0 11.2 0 13.5s.6 4.5 1.6 6.5l3.7-2.9z" />
                  <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.8-2.1-6.7-5l-3.7 2.9C3.5 21.4 7.4 24 12 24z" />
                </svg>
                <span>Войти через Google</span>
              </button>
            </div>
          </div>
        )}

        {/* Step 2: OTP Verification Screen */}
        {authStep === 'otp' && (
          <div className="bg-white rounded-3xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-neutral-100 space-y-5">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setAuthStep('phone')}
                className="text-sm font-semibold text-[#E50914] flex items-center gap-1"
              >
                ← Изменить номер
              </button>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-[#E50914]/10 text-[#E50914]">
                {sendMethod === 'telegram' ? 'Код отправлен в Telegram' : 'Код отправлен по SMS'}
              </span>
            </div>

            <div className="text-center space-y-1">
              <h2 className="text-xl font-extrabold text-neutral-900">Подтверждение кода</h2>
              <p className="text-sm font-medium text-neutral-500">{formattedPhone}</p>
            </div>

            {/* 6 Red-Bordered Square OTP Boxes */}
            <div className="grid grid-cols-6 gap-2 max-w-xs mx-auto">
              {otpDigits.map((digit, i) => (
                <div
                  key={i}
                  className={`aspect-square rounded-2xl border-2 border-[#E50914] flex items-center justify-center text-xl font-extrabold transition-all ${
                    digit ? 'bg-[#E50914]/10 text-[#E50914]' : 'bg-white text-neutral-900'
                  }`}
                >
                  {digit}
                </div>
              ))}
            </div>

            <div className="text-center">
              <p className="text-xs font-medium text-neutral-500">
                Повторить отправку можно через{' '}
                <span className="font-bold text-[#E50914]">{formattedTimer}</span>
              </p>
            </div>
          </div>
        )}

        {/* Payment Methods Component ("Способы оплаты") */}
        <PaymentMethodsCard selected={paymentMethod} onSelect={setPaymentMethod} />
      </div>

      {/* Custom Numeric Keypad (shown when on OTP step) */}
      {authStep === 'otp' && (
        <div className="fixed bottom-16 left-0 right-0 z-40">
          <NumericKeypad
            onDigit={handleOtpDigit}
            onBackspace={handleOtpBackspace}
            onClear={handleOtpClear}
          />
        </div>
      )}

      {/* Bottom Navigation Bar */}
      <BottomNavBar activeTab={activeTab} onChangeTab={setActiveTab} cartCount={1} />
    </div>
  );
}

