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
    label: { en: "WB flood ranking", hi: "बंगाल बाढ़ रैंक", bn: "বন্যা র‌্যাঙ্ক" },
    text: {
      en: "Which districts in West Bengal are more likely to get flooded? List them.",
      hi: "पश्चिम बंगाल के कौन से जिले बाढ़ की दृष्टि से अधिक जोखिम में हैं? सूची दें।",
      bn: "পশ্চিমবঙ্গের কোন কোন জেলায় বন্যার সম্ভাবনা বেশি? তালিকা দিন।",
    },
  },
  {
    id: "nowcast",
    label: { en: "Next 2 hours?", hi: "अगले 2 घंटे?", bn: "আগামী ২ ঘণ্টা?" },
    text: {
      en: "Will it rain in the next 2 hours? Should I start the pump set now?",
      hi: "अगले 2 घंटे बारिश होगी? क्या अभी पंप सेट चलाऊँ?",
      bn: "আগামী ২ ঘণ্টায় বৃষ্টি হবে? এখন পাম্প সেট চালাব কি?",
    },
  },

  {
    id: "irrigate",
    label: { en: "Should I irrigate?", hi: "सिंचाई?", bn: "সেচ দেব?" },
    text: {
      en: "Rain in the next 3 days? Should I irrigate now?",
      hi: "अगले तीन दिन बारिश कैसी रहेगी? क्या अभी सिंचाई करूँ?",
      bn: "আগামী তিন দিনে বৃষ্টির সম্ভাবনা কেমন? এখন সেচ দেওয়া উচিত কি?",
    },
  },

  {
    id: "mandi",
    label: { en: "State mandi prices", hi: "मंडी भाव", bn: "মান্ডি দাম" },
    text: {
      en: "Mandi prices across West Bengal today.",
      hi: "आज पश्चिम बंगाल की मंडी कीमतें बताएँ।",
      bn: "আজ পশ্চিমবঙ্গের মান্ডি দাম কেমন?",
    },
  },
  {
    id: "outlook",
    label: { en: "7-day outlook", hi: "7-दिन पूर्वानुमान", bn: "৭ দিনের পূর্বাভাস" },
    text: {
      en: "Give the 7 day outlook and water balance.",
      hi: "7 दिन का आउटलुक और जल संतुलन दें।",
      bn: "৭ দিনের আউটলুক ও জল ভারসাম্য দিন।",
    },
  },

  {
    id: "aqi",
    label: { en: "Air quality", hi: "वायु गुणवत्ता", bn: "বায়ুর মান" },
    text: {
      en: "What is the air quality here and what should I do?",
      hi: "यहाँ वायु गुणवत्ता कैसी है और क्या करना चाहिए?",
      bn: "এখানে বায়ুর মান কেমন এবং কী করা উচিত?",
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
      en: "Any nearby earthquake or tsunami watch?",
      hi: "आसपास कोई भूकंप या सुनामी चेतावनी है क्या?",
      bn: "কাছাকাছি কোনো ভূমিকম্প বা সুনামি সতর্কতা আছে কি?",
    },
  },
];

const ASK_IDS = ["nowcast", "outlook", "irrigate", "aqi", "sky", "quake", "flood-wb"] as const;

export function presetsFor(locale: Locale): { id: string; label: string; text: string }[] {
  return PRESETS.map((p) => ({ id: p.id, label: p.label[locale], text: p.text[locale] }));
}

export function askChips(locale: Locale): { short: string; q: string }[] {
  return PRESETS.filter((p) => (ASK_IDS as readonly string[]).includes(p.id)).map((p) => ({
    short: p.label[locale],
    q: p.text[locale],
  }));
}
