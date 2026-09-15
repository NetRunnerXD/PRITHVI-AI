import type { Locale } from "@/i18n/copy";
import type { DashboardSnapshot, RiskCard } from "@/types/dashboard";
import { localizeDigits } from "./units";

export type Level = "ok" | "watch" | "alert";

export function levelOf(score?: number | null, high = 70, mid = 45): Level {
  const n = score ?? 0;
  if (n >= high) return "alert";
  if (n >= mid) return "watch";
  return "ok";
}

const LEVEL_WORD: Record<Locale, Record<Level, string>> = {
  en: { ok: "Low", watch: "Medium", alert: "High" },
  hi: { ok: "निम्न", watch: "मध्यम", alert: "उच्च" },
  bn: { ok: "কম", watch: "মাঝারি", alert: "উচ্চ" },
};

const RISK_NAME: Record<string, Record<Locale, string>> = {
  flood: { en: "Flood Risk", hi: "बाढ़ जोखिम", bn: "বন্যা ঝুঁকি" },
  drought: { en: "Drought Risk", hi: "सूखा जोखिम", bn: "খরা ঝুঁকি" },
  heat: { en: "Heatwave Risk", hi: "लू / गर्मी जोखिम", bn: "দাবদাহ ঝুঁকি" },
  irrigation_need: { en: "Irrigation Need", hi: "सिंचाई आवश्यकता", bn: "সেচের প্রয়োজনীয়তা" },
  air_quality: { en: "Air Quality Risk", hi: "वायु गुणवत्ता जोखिम", bn: "বায়ু দূষণ ঝুঁকি" },
  livelihood: { en: "Livelihood & Field Work", hi: "आजीविका एवं कृषि कार्य", bn: "জীবিকা ও কৃষিকাজ" },
  seismic: { en: "Earthquake Activity", hi: "भूकंपीय गतिविधि", bn: "ভূমিকম্পের ঝুঁকি" },
  tsunami: { en: "Tsunami Alert", hi: "सुनामी चेतावनी", bn: "সুনামি সতর্কতা" },
  cyclone: { en: "Cyclone Risk", hi: "चक्रवात जोखिम", bn: "ঘূর্ণিঝড় ঝুঁকি" },
  lightning: { en: "Lightning Risk", hi: "वज्रपात जोखिम", bn: "বজ্রপাত ঝুঁকি" },
  landslide: { en: "Landslide Risk", hi: "भूस्खलन जोखिम", bn: "ভূমিধস ঝুঁকি" },
  storm: { en: "Storm Surge Risk", hi: "तूफ़ान जोखिम", bn: "ঝড় ঝুঁকি" },
};

const RISK_TIP: Record<string, Record<Locale, string>> = {
  flood: {
    en: "Low fields and drains may fill. Move seed, pumps and animals up.",
    hi: "निचले खेत और नाले भर सकते हैं। बीज, पंप, पशु ऊँचाई पर रखें।",
    bn: "নিচু জমি ও নালা ভরে যেতে পারে। বীজ, পাম্প, পশু উঁচুতে রাখুন।",
  },
  drought: {
    en: "Rain is short of normal. Save water; irrigate only the best plots.",
    hi: "बारिश सामान्य से कम है। पानी बचाएँ; सिर्फ अच्छे खेतों को दें।",
    bn: "বৃষ্টি স্বাভাবিকের চেয়ে কম। জল বাঁচান; ভালো জমিতেই সেচ দিন।",
  },
  heat: {
    en: "Avoid midday work. Drink water. Shade livestock.",
    hi: "दोपहर में काम न करें। पानी पिएँ। पशुओं को छाया दें।",
    bn: "দুপুরে কাজ এড়ান। জল খান। পশুকে ছায়া দিন।",
  },
  irrigation_need: {
    en: "Soil is thirsty and little rain is listed. A light watering may help.",
    hi: "मिट्टी सूखी है और बारिश कम दिख रही है। हल्की सिंचाई सोचें।",
    bn: "মাটি শুকনো, বৃষ্টি কম। হালকা সেচ ভাবা যায়।",
  },
  air_quality: {
    en: "Outdoor air is unhealthy. Keep children and anyone with asthma inside when you can.",
    hi: "बाहर की हवा खराब है। बच्चों और दमा वालों को जितना हो अंदर रखें।",
    bn: "বাইরের বাতাস খারাপ। শিশু ও হাঁপানিতে যারা আছেন, ভিতরে রাখুন।",
  },
  livelihood: {
    en: "Heat, flood or bad air may stop field work on some days.",
    hi: "गर्मी, बाढ़ या खराब हवा कुछ दिन खेत का काम रोक सकती है।",
    bn: "গরম, বন্যা বা খারাপ বাতাস কিছুদিন জমির কাজ আটকাতে পারে।",
  },
  seismic: {
    en: "A recent quake is on the official list. This is a notice, not a prediction.",
    hi: "सूची में हाल का भूकंप है। यह सूचना है, भविष्यवाणी नहीं।",
    bn: "তালিকায় সাম্প্রতিক ভূমিকম্প আছে। এটা নোটিশ, ভবিষ্যদ্বাণী নয়।",
  },
  tsunami: {
    en: "A sea bulletin is active. Follow district and INCOIS instructions on the coast.",
    hi: "समुद्री बुलेटिन सक्रिय है। तट पर जिला / INCOIS निर्देश मानें।",
    bn: "সমুদ্র বুলেটিন সক্রিয়। উপকূলে জেলা / INCOIS নির্দেশ মানুন।",
  },
  cyclone: {
    en: "Tropical disturbance or cyclonic depression monitored nearby. Secure loose structures.",
    hi: "आसपास चक्रवाती हवाओं का दबाव बना हुआ है। संरचनाओं को सुरक्षित करें।",
    bn: "নিকটবর্তী অঞ্চলে ঘূর্ণিঝড় বা নিম্নচাপ পর্যবেক্ষণাধীন। কাঠামো সুরক্ষিত রাখুন।",
  },
  lightning: {
    en: "Severe convective cloud activity and lightning strikes possible. Seek indoor shelter.",
    hi: "गंभीर गरज-चमक और वज्रपात की संभावना है। पक्के मकान में शरण लें।",
    bn: "বজ্রবিদ্যুৎ ও বজ্রপাতের আশঙ্কা রয়েছে। নিরাপদ আশ্রয়ে থাকুন।",
  },
  landslide: {
    en: "Steep slopes and heavy saturation present slide hazards in hilly terrain.",
    hi: "पहाड़ी ढलानों पर अत्यधिक पानी जमा होने से भूस्खलन का खतरा है।",
    bn: "পাহাড়ি ঢালে অতিরিক্ত বৃষ্টিপাতের কারণে ভূমিধসের ঝুঁকি রয়েছে।",
  },
  storm: {
    en: "Strong squally winds and torrential rain expected. Exercise high caution.",
    hi: "तेज हवाएं और भारी बारिश का अनुमान है। अत्यधिक सावधानी बरतें।",
    bn: "তীব্র ঝড়ো হাওয়া ও ভারী বৃষ্টিপাতের পূর্বাভাস। বিশেষ সতর্কতা অবলম্বন করুন।",
  },
};

const FACTOR_MAP: Record<string, Record<Locale, string>> = {
  precip_3d: { en: "3-Day Rainfall", hi: "3-दिवसीय वर्षा", bn: "৩ দিনের বৃষ্টিপাত" },
  precip_7d: { en: "7-Day Rainfall", hi: "7-दिवसीय वर्षा", bn: "৭ দিনের বৃষ্টিপাত" },
  soil_moisture: { en: "Soil Moisture", hi: "मृदा आर्द्रता (नमी)", bn: "মাটির আর্দ্রতা" },
  heat_index: { en: "Heat Index (Feels)", hi: "ताप सूचकांक (उमस)", bn: "তাপমাত্রা সূচক" },
  wind_gust: { en: "Wind Gust Velocity", hi: "हवा के झोंकों की गति", bn: "দমকা বাতাসের গতি" },
  deficit_rain: { en: "Rainfall Deficit", hi: "वर्षा की कमी", bn: "বৃষ্টির ঘাটতি" },
  aqi: { en: "Air Quality Index", hi: "वायु गुणवत्ता सूचकांक", bn: "বায়ু মান সূচক" },
  pm25: { en: "PM2.5 Particulate", hi: "PM2.5 प्रदूषक कण", bn: "PM2.5 দূষক কণা" },
  pm10: { en: "PM10 Particulate", hi: "PM10 प्रदूषक कण", bn: "PM10 দূষক কণা" },
  cyclone_dist: { en: "Cyclone Proximity", hi: "चक्रवात की दूरी", bn: "ঘূর্ণিঝড়ের নৈকট্য" },
  seismic_dist: { en: "Seismic Epicenter", hi: "भूकंपीय केंद्र", bn: "ভূমিকম্পের কেন্দ্রস্থল" },
  wave_height: { en: "Sea Wave Height", hi: "समुद्री लहरों की ऊंचाई", bn: "সমুদ্র তরঙ্গের উচ্চতা" },
  monsoon_gap: { en: "Monsoon Dry Spell", hi: "मानसून शुष्क अंतराल", bn: "বর্ষার শুষ্ক পর্যায়" },
  temp_max: { en: "Peak Daytime Temp", hi: "दिन का अधिकतम तापमान", bn: "সর্বোচ্চ দিনের তাপমাত্রা" },
  humidity: { en: "Relative Humidity", hi: "सापेक्ष आर्द्रता", bn: "আপেক্ষিক আর্দ্রতা" },
  dew_point: { en: "Dew Point", hi: "ओस बिंदु", bn: "শিশিরাঙ্ক" },
  cape: { en: "Atmospheric Instability", hi: "वातावरणीय अस्थिरता (CAPE)", bn: "বায়ুমণ্ডলীয় অস্থিরতা" },
};

export function factorLabel(id: string, locale: Locale, fallback?: string): string {
  if (FACTOR_MAP[id]?.[locale]) return FACTOR_MAP[id][locale];
  const fb = fallback || id;
  if (locale === "hi") {
    if (fb.toLowerCase().includes("rain")) return "वर्षा कारक";
    if (fb.toLowerCase().includes("soil")) return "मिट्टी की स्थिति";
    if (fb.toLowerCase().includes("temp") || fb.toLowerCase().includes("heat")) return "तापमान कारक";
    if (fb.toLowerCase().includes("wind")) return "पवन गति";
    if (fb.toLowerCase().includes("air") || fb.toLowerCase().includes("aqi")) return "वायु गुणवत्ता";
  } else if (locale === "bn") {
    if (fb.toLowerCase().includes("rain")) return "বৃষ্টির প্রভাব";
    if (fb.toLowerCase().includes("soil")) return "মাটির অবস্থা";
    if (fb.toLowerCase().includes("temp") || fb.toLowerCase().includes("heat")) return "তাপমাত্রার প্রভাব";
    if (fb.toLowerCase().includes("wind")) return "বাতাসের গতি";
    if (fb.toLowerCase().includes("air") || fb.toLowerCase().includes("aqi")) return "বায়ুর মান";
  }
  return fb;
}

export function levelWord(locale: Locale, level: Level) {
  return LEVEL_WORD[locale][level];
}

export function riskTitle(id: string, locale: Locale, fallback: string) {
  return RISK_NAME[id]?.[locale] || fallback;
}

export function riskTip(id: string, locale: Locale) {
  return RISK_TIP[id]?.[locale] || "";
}

export function todayStory(dash: DashboardSnapshot, locale: Locale): string {
  const act = dash.prescriptive.actions[0];
  const sky = dash.live?.sky?.label || dash.descriptive.current.sky_label || "";
  const rawRain = dash.predictive.precip_next_3d_mm ?? 0;
  const rainNum = localizeDigits(rawRain, locale);
  const threeDays = localizeDigits(3, locale);

  if (locale === "hi") {
    if (act?.id === "hold_irrigation") return `आकाश ${sky || "साफ़"}. अगले ${threeDays} दिन लगभग ${rainNum} मिमी बारिश — आज सिंचाई रोकें।`;
    if (act?.id === "apply_irrigation") return `बारिश कम दिख रही है (${rainNum} मिमी / ${threeDays} दिन). हल्की सिंचाई सोची जा सकती है।`;
    if (act?.action) return act.action;
    return `${sky || "मौसम"} · अगले ${threeDays} दिन ${rainNum} मिमी बारिश।`;
  }
  if (locale === "bn") {
    if (act?.id === "hold_irrigation") return `আকাশ ${sky || "পরিষ্কার"}। আগামী ${threeDays} দিনে প্রায় ${rainNum} মিমি বৃষ্টি — আজ সেচ না দিলেই ভালো।`;
    if (act?.id === "apply_irrigation") return `বৃষ্টি কম (${rainNum} মিমি / ${threeDays} দিন)। হালকা সেচ ভাবা যায়।`;
    if (act?.action) return act.action;
    return `${sky || "আবহাওয়া"} · আগামী ${threeDays} দিন ${rainNum} মিমি বৃষ্টি।`;
  }
  if (act?.id === "hold_irrigation") return `${sky || "The sky"} · about ${rawRain} mm rain in 3 days — skip irrigation today.`;
  if (act?.id === "apply_irrigation") return `Little rain listed (${rawRain} mm / 3 days). A light watering may help.`;
  if (act?.action) return act.action;
  return `${sky || "Weather"} · ${rawRain} mm rain expected in the next 3 days.`;
}

export function worstWatch(risks: RiskCard[]): RiskCard | undefined {
  return [...risks].sort((a, b) => b.score_pct - a.score_pct)[0];
}
