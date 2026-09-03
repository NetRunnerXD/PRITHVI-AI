import type { Locale } from "./copy";

export type Preset = {
  id: string;
  label: Record<Locale, string>;
  text: Record<Locale, string>;
};

/** Same questions in English / Hindi / Bengali. The backend MT layer turns any of these into English for the LLM. */
export const PRESETS: Preset[] = [
  {
    id: "flood-wb",
    label: { en: "Flood risk ranking", hi: "बाढ़ जोखिम रैंक", bn: "বন্যা ঝুঁকি র‌্যাঙ্ক" },
    text: {
      en: "Which areas in this state are currently at high risk of waterlogging or flooding?",
      hi: "इस राज्य के कौन से क्षेत्र वर्तमान में जलभराव या बाढ़ के उच्च जोखिम में हैं?",
      bn: "এই রাজ্যের কোন কোন অঞ্চল বর্তমানে জলাবদ্ধতা বা বন্যার উচ্চ ঝুঁকিতে রয়েছে?",
    },
  },
  {
    id: "nowcast",
    label: { en: "Next 2 hours?", hi: "अगले 2 घंटे?", bn: "আগামী ২ ঘণ্টা?" },
    text: {
      en: "Will it rain in the next 2 hours and what is the cloud movement direction?",
      hi: "क्या अगले 2 घंटे में बारिश होगी और बादलों की दिशा क्या है?",
      bn: "আগামী ২ ঘণ্টায় কি বৃষ্টি হবে এবং মেঘের গতিপ্রকৃতি কেমন?",
    },
  },
  {
    id: "wind-air",
    label: { en: "Wind & Air", hi: "पवन व वायु", bn: "বাতাস ও বায়ু" },
    text: {
      en: "What are the current wind speeds, gusts, and air quality index (AQI) levels?",
      hi: "वर्तमान हवा की गति, तेज झोंके और वायु गुणवत्ता (AQI) का स्तर क्या है?",
      bn: "বর্তমান বাতাসের গতিবেগ, দমকা হাওয়া এবং বায়ুর মান (AQI) কেমন?",
    },
  },
  {
    id: "outlook",
    label: { en: "7-day outlook", hi: "7-दिन पूर्वानुमान", bn: "৭ দিনের পূর্বাভাস" },
    text: {
      en: "Give the comprehensive 7-day weather outlook and temperature range.",
      hi: "विस्तृत 7-दिवसीय मौसम पूर्वानुमान और तापमान सीमा बताएं।",
      bn: "বিস্তারিত ৭ দিনের আবহাওয়া পূর্বাভাস এবং তাপমাত্রার বিস্তার জানান।",
    },
  },
  {
    id: "aqi",
    label: { en: "Air quality", hi: "वायु गुणवत्ता", bn: "বায়ুর মান" },
    text: {
      en: "What is the air quality here and are there any health advisories?",
      hi: "यहाँ वायु गुणवत्ता कैसी है और क्या कोई स्वास्थ्य सलाह लागू है?",
      bn: "এখানে বায়ুর মান কেমন এবং কোনো স্বাস্থ্য সংক্রান্ত সতর্কতা আছে কি?",
    },
  },
  {
    id: "sky",
    label: { en: "Today's sky", hi: "आज का मौसम", bn: "আজকের আকাশ" },
    text: {
      en: "What is the sky condition today and how much rain is expected?",
      hi: "आज आसमान कैसा है और कितनी बारिश होगी?",
      bn: "আজ আকাশ কেমন এবং কত বৃষ্টি হবে?",
    },
  },
  {
    id: "quake",
    label: { en: "Quake / tsunami", hi: "भूकंप", bn: "ভূমিকম্প" },
    text: {
      en: "Are there any nearby earthquake tremors or tsunami advisories?",
      hi: "क्या आसपास कोई भूकंपीय गतिविधि या सुनामी चेतावनी दर्ज है?",
      bn: "কাছাকাছি কোনো ভূকম্পন বা সুনামি সতর্কবার্তা রেকর্ড করা হয়েছে কি?",
    },
  },
];

const ASK_IDS = ["nowcast", "outlook", "wind-air", "aqi", "sky", "quake", "flood-wb"] as const;

export function presetsFor(locale: Locale): { id: string; label: string; text: string }[] {
  return PRESETS.map((p) => ({ id: p.id, label: p.label[locale], text: p.text[locale] }));
}

export function askChips(locale: Locale): { short: string; q: string }[] {
  return PRESETS.filter((p) => (ASK_IDS as readonly string[]).includes(p.id)).map((p) => ({
    short: p.label[locale],
    q: p.text[locale],
  }));
}
