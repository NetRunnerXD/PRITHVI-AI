"use client";

import type { Locale } from "@/i18n/copy";

export const TRANSLATIONS = {
  hi: {
    alertsTab: "आपातकालीन चेतावनियां",
    risksTab: "जोखिम मेट्रिक्स",
    noAlerts: "कोई सक्रिय आपातकालीन बुलेटिन नहीं",
    noAlertsDesc: "पृथ्वी-नेत्र द्वारा बाढ़, वायु, समुद्री व भूकंपीय सुरक्षा स्कैन निरंतर सक्रिय हैं।",
    hazards: "खतरे",
    activeLoc: "सक्रिय स्थान",
    fromPin: "स्थान से दूरी",
    regScope: "क्षेत्रीय दायरा",
    viewModal: "आधिकारिक बुलेटिन विवरण देखें →",
    viewAllMatrix: "पूर्ण जोखिम मैट्रिक्स एवं विश्लेषण देखें →",
    confidence: "विश्वसनीयता",
    horizon: "अवधि",
    primaryDriver: "प्रमुख चालक",
    showFactors: "कारक दिखाएं ▼",
    hideFactors: "कारक छिपाएं ▲",
    contributingDrivers: "योगदान देने वाले कारक",
    weight: "प्रभाव",
    noIsolated: "कोई अलग जोखिम कारक नहीं।",
    nominalBase: "सामान्य स्थिति · कोई सक्रिय जोखिम चालक नहीं",
    good: "अच्छा",
    satisfactory: "संतोषजनक",
    moderate: "मध्यम",
    poor: "खराब",
    veryPoor: "बहुत खराब",
    severe: "गंभीर",
    extreme: "गंभीर",
    warning: "चेतावनी",
    alert: "सचेत",
    watch: "निगरानी",
    low: "निम्न",
    elevated: "बढ़ा हुआ",
    nominal: "सामान्य",
    inland: "अंतर्देशीय",
    calm: "शांत",
    smooth: "समतल",
    rough: "अशांत",
    veryRough: "अति अशांत",
    high: "ऊंची लहरें",
    switchPin: "स्थान बदलें",
    details: "विवरण",
  },
  bn: {
    alertsTab: "জরুরি সতর্কতা",
    risksTab: "ঝুঁকি মেট্রিক্স",
    noAlerts: "কোনো সক্রিয় জরুরি সতর্কতা নেই",
    noAlertsDesc: "পৃথিবী-নেত্র দ্বারা বন্যা, বায়ু, সামুদ্রিক ও ভূমিকম্প নজরদারি অবিরাম সক্রিয় রয়েছে।",
    hazards: "ঝুঁকি",
    activeLoc: "বর্তমান অবস্থান",
    fromPin: "স্থান থেকে দূরত্ব",
    regScope: "আঞ্চলিক পরিধি",
    viewModal: "সরকারি সতর্কতা বিবরণ দেখুন →",
    viewAllMatrix: "সম্পূর্ণ ঝুঁকি ম্যাট্রিক্স ও বিশ্লেষণ দেখুন →",
    confidence: "নির্ভরযোগ্যতা",
    horizon: "মেয়াদ",
    primaryDriver: "প্রধান চালক",
    showFactors: "ফ্যাক্টর দেখুন ▼",
    hideFactors: "ফ্যাক্টর লুকান ▲",
    contributingDrivers: "অবদানকারী প্রভাব ও ফ্যাক্টর",
    weight: "ওজন",
    noIsolated: "কোনো বিচ্ছিন্ন ঝুঁকি ফ্যাক্টর নেই।",
    nominalBase: "স্বাভাবিক অবস্থা · কোনো সক্রিয় ঝুঁকি চালক নেই",
    good: "ভালো",
    satisfactory: "সন্তোষজনক",
    moderate: "মাঝারি",
    poor: "খারাপ",
    veryPoor: "খুব খারাপ",
    severe: "মারাত্মক",
    extreme: "মারাত্মক",
    warning: "সতর্কতা",
    alert: "সচেতনতা",
    watch: "নজরদারি",
    low: "কম",
    elevated: "বর্ধিত",
    nominal: "স্বাভাবিক",
    inland: "অভ্যন্তরীণ",
    calm: "শান্ত",
    smooth: "মসৃণ",
    rough: "উত্তাল",
    veryRough: "অত্যন্ত উত্তাল",
    high: "উঁচু ঢেউ",
    switchPin: "পিন পরিবর্তন",
    details: "বিবরণ",
  },
};


export function tWord(key: string, locale: Locale, fallback?: string): string {
  if (locale === "hi" && (TRANSLATIONS.hi as any)[key]) return (TRANSLATIONS.hi as any)[key];
  if (locale === "bn" && (TRANSLATIONS.bn as any)[key]) return (TRANSLATIONS.bn as any)[key];
  return fallback || key;
}


export function translateSeverity(sev: string | undefined | null, locale: Locale): string {
  if (!sev) return "";
  const s = sev.toLowerCase().trim();
  if (s === "extreme" || s === "danger") return locale === "hi" ? "गंभीर" : locale === "bn" ? "মারাত্মক" : "Extreme";
  if (s === "warning" || s === "alert") return locale === "hi" ? "चेतावनी" : locale === "bn" ? "সতর্কতা" : "Warning";
  if (s === "watch" || s === "elevated") return locale === "hi" ? "निगरानी" : locale === "bn" ? "নজরদারি" : "Watch";
  if (s === "low" || s === "nominal" || s === "ok") return locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "Low";
  return sev;
}


export function translateAqiCategory(cat: string | undefined | null, locale: Locale): string {
  if (!cat) return locale === "hi" ? "अच्छा" : locale === "bn" ? "ভালো" : "Good";
  const c = cat.toLowerCase().trim();
  if (c.includes("good")) return locale === "hi" ? "अच्छा" : locale === "bn" ? "ভালো" : "Good";
  if (c.includes("satisfactory")) return locale === "hi" ? "संतोषजनक" : locale === "bn" ? "সন্তোষজনক" : "Satisfactory";
  if (c.includes("moderate")) return locale === "hi" ? "मध्यम" : locale === "bn" ? "মাঝারি" : "Moderate";
  if (c.includes("very poor")) return locale === "hi" ? "बहुत खराब" : locale === "bn" ? "খুব খারাপ" : "Very Poor";
  if (c.includes("poor")) return locale === "hi" ? "खराब" : locale === "bn" ? "খারাপ" : "Poor";
  if (c.includes("severe") || c.includes("hazard")) return locale === "hi" ? "गंभीर" : locale === "bn" ? "মারাত্মক" : "Severe";
  return cat;
}

