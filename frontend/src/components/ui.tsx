"use client";

import { useState, type ReactNode } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { Level } from "@/lib/plain";
import { levelWord } from "@/lib/plain";
import type { TabId } from "@/types/dashboard";

const EXTRA: Partial<Record<TabId, Record<Locale, string[]>>> = {};

export function Collapse({
  title,
  subtitle,
  defaultOpen = true,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="neo overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>
          <span className="block text-sm font-bold">{title}</span>
          {subtitle ? <span className="mt-0.5 block text-xs text-neo-muted">{subtitle}</span> : null}
        </span>
        <span className="text-lg text-neo-accent2">{open ? "–" : "+"}</span>
      </button>
      {open ? <div className="border-t border-neo-line px-4 py-3">{children}</div> : null}
    </section>
  );
}

export function Pill({ level, locale }: { level: Level; locale: Locale }) {
  return <span className={`chip ${level === "ok" ? "level-ok" : level === "watch" ? "level-watch" : "level-alert"}`}>{levelWord(locale, level)}</span>;
}

const TAB_SOURCES: Partial<Record<TabId, Record<Locale, string[]>>> = {
  home: {
    en: [
      "Sky, rain, wind, soil, 7-day outlook: Open-Meteo forecast (fetched on this device, assembled on the API). Not a village rain-gauge.",
      "Next 6 hours: 0–2 h nowcast, 3–4 h blend, 5–6 h NWP. Past hours are model analysis, not a gauge.",
      "Air: CPCB National AQI (data.gov.in) when a station is near; otherwise Open-Meteo CAMS US AQI.",
      "Alerts: IMD CAP bulletins plus model thunderstorm/nowcast rows for this pin. Tsunami all-clear is hidden.",
      "Marine waves only if the pin is coastal (Open-Meteo marine). Inland shows empty — no invented swell.",
      "Quakes: USGS FDSN. Tsunami: INCOIS ITEWS. NASA POWER daily and 8-year climate stay off unless enabled.",
      "Irrigation litres: plot size × a small depth. The chat model does not invent millimetres, AQI, or rupees.",
    ],
    hi: [
      "आकाश, बारिश, हवा, मिट्टी, 7-दिन: Open-Meteo पूर्वानुमान (इस डिवाइस से, API पर जोड़ा जाता है)। गाँव का रेन-गेज नहीं।",
      "अगले 6 घंटे: 0–2 नाउकास्ट, 3–4 मिश्रण, 5–6 NWP। बीते घंटे मॉडल विश्लेषण हैं, गेज नहीं।",
      "वायु: पास स्टेशन हो तो CPCB राष्ट्रीय AQI (data.gov.in); नहीं तो Open-Meteo CAMS US AQI।",
      "चेतावनी: IMD CAP बुलेटिन और इस पिन के मॉडल गरज-तूफान/नाउकास्ट पंक्तियाँ। सुनामी ऑल-क्लियर छिपाया जाता है।",
      "लहरें केवल तटीय पिन पर (Open-Meteo marine)। अंतर्देशीय खाली — काल्पनिक लहर नहीं।",
      "भूकंप: USGS FDSN। सुनामी: INCOIS ITEWS। NASA POWER दैनिक और 8-वर्ष जलवायु डिफ़ॉल्ट बंद।",
      "सिंचाई लीटर: खेत × गहराई। चैट मॉडल मिमी/AQI/₹ नहीं गढ़ता।",
    ],
    bn: [
      "আকাশ, বৃষ্টি, হাওয়া, মাটি, ৭-দিন: Open-Meteo পূর্বাভাস (এই ডিভাইস থেকে, API-তে জোড়া)। গ্রামের বৃষ্টিমাপক নয়।",
      "আগামী ৬ ঘণ্টা: ০–২ নাউকাস্ট, ৩–৪ মিশ্রণ, ৫–৬ NWP। গত ঘণ্টা মডেল বিশ্লেষণ, গেজ নয়।",
      "বায়ু: কাছে স্টেশন থাকলে CPCB জাতীয় AQI (data.gov.in); নাহলে Open-Meteo CAMS US AQI।",
      "সতর্কতা: IMD CAP বুলেটিন ও এই পিনের মডেল বজ্রঝড়/নাউকাস্ট সারি। সুনামি অল-ক্লিয়ার লুকানো।",
      "ঢেউ শুধু উপকূলীয় পিনে (Open-Meteo marine)। অভ্যন্তরে খালি — কাল্পনিক ঢেউ নয়।",
      "ভূকম্প: USGS FDSN। সুনামি: INCOIS ITEWS। NASA POWER দৈনিক ও ৮-বছর জলবায়ু ডিফল্ট বন্ধ।",
      "সেচ লিটার: জমি × গভীরতা। চ্যাট মডেল মিমি/AQI/₹ তৈরি করে না।",
    ],
  },
  analytics: {
    en: [
      "Charts use the same Open-Meteo hourly and daily series as Home.",
      "Nowcast: IMD INSAT-3D/3DS public IR JPEG, NASA GIBS IR + IMERG, Weatherbit lightning strokes. Cells are tracked; 15–60 min is Lagrangian nowcast. Kalman fills between IR scenes.",
      "Cloudburst = extreme-rain cell at the pin. Downburst = collapsing cell + gust/CAPE. Lightning is strokes when Weatherbit returns them.",
      "Locked hourly millimetres stay Open-Meteo. Satellite rain-rate is a separate estimate, not a gauge. Not MinuteCast / IMD Doppler millimetres.",
      "Optional member blend (ECMWF, GFS, GraphCast, ICON, UKMO) when this device seeds it. NASA POWER climate is off by default. Hugli tide / CWC only on the estuary.",
    ],
    hi: [
      "ग्राफ़ वही Open-Meteo घंटे/दिन श्रृंखला हैं जो होम पर है।",
      "नाउकास्ट: IMD INSAT-3D/3DS सार्वजनिक IR JPEG, NASA GIBS IR + IMERG, Weatherbit बिजली। सेल ट्रैक; 15–60 मिनट Lagrangian नाउकास्ट। Kalman IR दृश्यों के बीच भरता है।",
      "क्लाउडबर्स्ट = पिन पर अतिवृष्टि सेल। डाउनबर्स्ट = गिरता सेल + झोंका/CAPE। बिजली तब स्ट्रोक जब Weatherbit दे।",
      "लॉक घंटे के मिमी Open-Meteo रहते हैं। उपग्रह वर्षा-दर अलग अनुमान है, गेज नहीं। MinuteCast / IMD डॉपलर मिमी नहीं।",
      "वैकल्पिक सदस्य मिश्रण (ECMWF, GFS, GraphCast, ICON, UKMO) जब डिवाइस सीड करे। NASA POWER जलवायु डिफ़ॉल्ट बंद। हुगली ज्वार/CWC केवल मुहाने पर।",
    ],
    bn: [
      "গ্রাফ হোমের একই Open-Meteo ঘণ্টা/দিন সিরিজ।",
      "নাউকাস্ট: IMD INSAT-3D/3DS পাবলিক IR JPEG, NASA GIBS IR + IMERG, Weatherbit বজ্রপাত। সেল ট্র্যাক; ১৫–৬০ মিনিট Lagrangian নাউকাস্ট। Kalman IR দৃশ্যের মাঝে ভরে।",
      "ক্লাউডবার্স্ট = পিনে অতিবৃষ্টি সেল। ডাউনবার্স্ট = ভাঙা সেল + ঝোড়ো/CAPE। বজ্রপাত স্ট্রোক তখনই যখন Weatherbit দেয়।",
      "লক ঘণ্টার মিমি Open-Meteo থাকে। উপগ্রহ বৃষ্টিহার আলাদা অনুমান, গেজ নয়। MinuteCast / IMD ডপলার মিমি নয়।",
      "ঐচ্ছিক সদস্য মিশ্রণ (ECMWF, GFS, GraphCast, ICON, UKMO) ডিভাইস সিড করলে। NASA POWER জলবায়ু ডিফল্ট বন্ধ। হুগলি জোয়ার/CWC শুধু মোহনায়।",
    ],
  },
  data: {
    en: [
      "IMD CAP weather · CPCB air (data.gov.in) · INCOIS ITEWS tsunami · USGS seismic (NCS has no public JSON) · Open-Meteo flood (GloFAS), marine and air. Open-Meteo does not publish earthquakes or tsunami.",
      "Cards are traffic-lights from the snapshot, not fortune-telling. Local rule actions (pump, field access, storm watch) may sit beside official alerts.",
      "Flood factors follow a water budget (rain, runoff, soil store, river).",
      "Earthquake / sea cards only repeat official lists; they do not predict.",
      "Mandi prices: Agmarknet via data.gov.in, rupees per quintal. Empty mandi stays empty — no invented ₹.",
    ],
    hi: [
      "IMD CAP मौसम · CPCB वायु (data.gov.in) · INCOIS ITEWS सुनामी · USGS भूकंप (NCS सार्वजनिक JSON नहीं) · Open-Meteo बाढ़ (GloFAS), समुद्र और वायु। Open-Meteo भूकंप/सुनामी नहीं देता।",
      "कार्ड स्नैपशॉट के ट्रैफ़िक-लाइट हैं, भविष्यवाणी नहीं। स्थानीय नियम (पंप, खेत, तूफान निगरानी) सरकारी चेतावनी के साथ हो सकते हैं।",
      "बाढ़ कारक जल बजट से (बारिश, अपवाह, मिट्टी, नदी)।",
      "भूकंप/समुद्र कार्ड केवल आधिकारिक सूची दोहराते हैं; भविष्य नहीं कहते।",
      "मंडी भाव: Agmarknet / data.gov.in, ₹/क्विंटल। खाली मंडी खाली रहती है — गढ़े ₹ नहीं।",
    ],
    bn: [
      "IMD CAP আবহাওয়া · CPCB বায়ু (data.gov.in) · INCOIS ITEWS সুনামি · USGS ভূকম্প (NCS-এর পাবলিক JSON নেই) · Open-Meteo বন্যা (GloFAS), সমুদ্র ও বায়ু। Open-Meteo ভূকম্প/সুনামি দেয় না।",
      "কার্ড স্ন্যাপশটের ট্রাফিক-লাইট, ভাগ্যগণনা নয়। স্থানীয় নিয়ম (পাম্প, ক্ষেত, ঝড় নজর) সরকারি সতর্কতার পাশে থাকতে পারে।",
      "বন্যা কারণ জল বাজেট থেকে (বৃষ্টি, প্রবাহ, মাটি, নদী)।",
      "ভূকম্প/সমুদ্র কার্ড শুধু অফিসিয়াল তালিকা; পূর্বাভাস নয়।",
      "মান্ডির দাম: Agmarknet / data.gov.in, ₹/কুইন্টাল। খালি মান্ডি খালি থাকে — তৈরি ₹ নয়।",
    ],
  },
  map: {
    en: [
      "Places: India gazetteer first, then Open-Meteo India geocoding.",
      "Weather fields (wind, temperature, rain, pressure, clouds, humidity, CAPE): Open-Meteo 13×25 mesh from this device, not Render.",
      "Radar / satellite IR: RainViewer from this device. GIBS true color, Himawari IR, IMERG: NASA WMS from this device.",
      "Bhuvan geomorphology: API WMS proxy (TLS/CORS). Storm cells and past storm: /nowcast/storm-map (INSAT on the API). Past lightning: Weatherbit + Open-Meteo thunder hours.",
      "Storm cells and the forecast pin stay India-only.",
    ],
    hi: [
      "जगह: पहले भारत गज़ेटियर, फिर Open-Meteo भारत जियोकोड।",
      "मौसम क्षेत्र (पवन, ताप, वर्षा, दाब, बादल, आर्द्रता, CAPE): इस डिवाइस से Open-Meteo 13×25 जाल, Render नहीं।",
      "रडार / सैट IR: इस डिवाइस से RainViewer। GIBS true color, Himawari IR, IMERG: NASA WMS इस डिवाइस से।",
      "भूवन: API WMS प्रॉक्सी। तूफान सेल/पुराना तूफान: /nowcast/storm-map (INSAT API पर)। पुरानी बिजली: Weatherbit + Open-Meteo गरज घंटे।",
      "तूफान सेल और पूर्वानुमान पिन केवल भारत।",
    ],
    bn: [
      "জায়গা: আগে ভারত গেজেটিয়ার, পরে Open-Meteo ভারত জিওকোড।",
      "আবহাওয়া ক্ষেত্র (বাতাস, তাপ, বৃষ্টি, চাপ, মেঘ, আর্দ্রতা, CAPE): এই ডিভাইস থেকে Open-Meteo ১৩×২৫ জাল, Render নয়।",
      "রাডার / স্যাট IR: এই ডিভাইস থেকে RainViewer। GIBS true color, Himawari IR, IMERG: NASA WMS এই ডিভাইস থেকে।",
      "ভুবন: API WMS প্রক্সি। ঝড় সেল/পুরনো ঝড়: /nowcast/storm-map (INSAT API-তে)। পুরনো বজ্রপাত: Weatherbit + Open-Meteo বজ্র ঘণ্টা।",
      "ঝড় সেল ও পূর্বাভাস পিন শুধু ভারত।",
    ],
  },
  model: {
    en: [
      "Published members = Open-Meteo (ECMWF, GFS, ICON, UKMO, GraphCast/AIFS when seeded from this device).",
      "PRITHVI-AI / VERA = same backbone with a small local adjustment (never more than about 12%).",
      "Trust official warnings first; then the trust line on this page. NASA POWER daily and 8-year climate stay off unless enabled.",
    ],
    hi: [
      "प्रकाशित सदस्य = Open-Meteo (ECMWF, GFS, ICON, UKMO, GraphCast/AIFS जब डिवाइस सीड करे)।",
      "PRITHVI-AI / VERA = वही आधार, छोटी स्थानीय मिलावट (लगभग 12% से अधिक नहीं)।",
      "पहले सरकारी चेतावनी; फिर इस पृष्ठ की ट्रस्ट लाइन। NASA POWER दैनिक और 8-वर्ष जलवायु डिफ़ॉल्ट बंद।",
    ],
    bn: [
      "প্রকাশিত সদস্য = Open-Meteo (ECMWF, GFS, ICON, UKMO, GraphCast/AIFS ডিভাইস সিড করলে)।",
      "PRITHVI-AI / VERA = একই ভিত্তি, ছোট স্থানীয় মিল (প্রায় ১২%-এর বেশি নয়)।",
      "আগে সরকারি সতর্কতা; তারপর এই পাতার ট্রাস্ট লাইন। NASA POWER দৈনিক ও ৮-বছর জলবায়ু ডিফল্ট বন্ধ।",
    ],
  },
  chat: {
    en: [
      "Type any language. The question is translated to English for the model; the answer is translated back (on-device ML Kit on Android Indic, else server/MyMemory).",
      "The model only reads tool and snapshot numbers. It must not invent rain millimetres, AQI, or rupees.",
      "Hosted narrator on the API (Gemini, then Groq, when Ollama is not on this host).",
    ],
    hi: [
      "कोई भी भाषा लिखें। प्रश्न अंग्रेज़ी होकर मॉडल को जाता है; उत्तर आपकी भाषा में आता है (Android Indic पर डिवाइस ML Kit, नहीं तो सर्वर/MyMemory)।",
      "मॉडल केवल टूल/स्नैपशॉट के अंक पढ़ता है — बारिश मिमी, AQI या ₹ नहीं गढ़ता।",
      "API पर होस्टेड कथाकार (Gemini, फिर Groq, जब इस होस्ट पर Ollama नहीं)।",
    ],
    bn: [
      "যেকোনো ভাষায় লিখুন। প্রশ্ন ইংরেজি হয়ে মডেলে যায়; উত্তর আপনার ভাষায় ফেরে (Android Indic-এ ডিভাইস ML Kit, নাহলে সার্ভার/MyMemory)।",
      "মডেল শুধু টুল/স্ন্যাপশটের সংখ্যা পড়ে — বৃষ্টি মিমি, AQI বা ₹ তৈরি করে না।",
      "API-তে হোস্টেড বর্ণনাকারী (Gemini, তারপর Groq, এই হোস্টে Ollama না থাকলে)।",
    ],
  },
  settings: {
    en: [
      "Theme, language, and layout stay on this device (browser or app storage).",
      "Sign-in is optional (phone + password on the API) for SMS alerts at a saved pin.",
      "NASA POWER daily and 8-year climate stay off unless you enable them here. Keys for MOSDAC, data.gov.in, and LLMs stay on the server.",
    ],
    hi: [
      "थीम, भाषा और लेआउट इस डिवाइस पर रहते हैं।",
      "साइन-इन वैकल्पिक है (API पर फ़ोन + पासवर्ड) — सहेजे पिन पर SMS चेतावनी के लिए।",
      "NASA POWER दैनिक और 8-वर्ष जलवायु यहाँ चालू किए बिना बंद रहते हैं। MOSDAC, data.gov.in और LLM कुंजी सर्वर पर रहती हैं।",
    ],
    bn: [
      "থিম, ভাষা ও লেআউট এই ডিভাইসে থাকে।",
      "সাইন-ইন ঐচ্ছিক (API-তে ফোন + পাসওয়ার্ড) — সেভ করা পিনে SMS সতর্কতার জন্য।",
      "NASA POWER দৈনিক ও ৮-বছর জলবায়ু এখানে চালু না করলে বন্ধ থাকে। MOSDAC, data.gov.in ও LLM কি সার্ভারে থাকে।",
    ],
  },
};

export function SourcesBox({
  tab,
  locale,
  provenance,
}: {
  tab: TabId;
  locale: Locale;
  provenance?: Record<string, string>;
}) {
  const t = COPY[locale];
  const lines = (TAB_SOURCES[tab] || EXTRA[tab])?.[locale] || EXTRA[tab]?.[locale] || [];
  const prov = Object.entries(provenance || {}).filter(([k]) => k !== "as_of");
  return (
    <Collapse title={t.sourcesAndMethods} subtitle={t.sourcesHint} defaultOpen={false}>
      <ul className="space-y-2 text-sm text-neo-muted">
        {lines.map((line) => (
          <li key={line}>• {line}</li>
        ))}
      </ul>
      {prov.length ? (
        <div className="mt-3 border-t border-neo-line pt-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.provenance}</p>
          <ul className="mt-2 space-y-1 text-xs text-neo-muted">
            {prov.map(([k, v]) => (
              <li key={k}>
                <span className="font-semibold text-neo-text">{k}</span> — {v}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Collapse>
  );
}
