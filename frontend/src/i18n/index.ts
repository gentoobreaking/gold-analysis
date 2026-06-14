/**
 * i18n 配置入口
 * 使用 react-i18next
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zh from './locales/zh.json';
import en from './locales/en.json';

const resources = {
  zh: { translation: zh },
  en: { translation: en },
};

// 從 localStorage 讀取保存的語言，預設中文
const savedLang = localStorage.getItem('gold-analysis-lang') || 'zh';

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: savedLang,
    fallbackLng: 'zh',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;

/**
 * 切換語言
 */
export const setLanguage = (lang: 'zh' | 'en') => {
  localStorage.setItem('gold-analysis-lang', lang);
  i18n.changeLanguage(lang);
};

/**
 * 取得當前語言
 */
export const getCurrentLanguage = (): 'zh' | 'en' => {
  return (i18n.language || 'zh') as 'zh' | 'en';
};
