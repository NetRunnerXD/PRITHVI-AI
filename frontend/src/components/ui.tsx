"use client";

import { useState, type ReactNode } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { Level } from "@/lib/plain";
import { levelWord } from "@/lib/plain";
import type { TabId } from "@/types/dashboard";

const EXTRA: Partial<Record<TabId, Record<Locale, string[]>>> = {
  alerts: {
    en: ["Alerts: IMD CAP, CPCB, INCOIS, USGS, plus local rule actions."],
    hi: ["चेतावनी: IMD CAP, CPCB, INCOIS, USGS और स्थानीय नियम।"],
    bn: ["সতর্কতা: IMD CAP, CPCB, INCOIS, USGS ও স্থানীয় নিয়ম।"],
  },
  settings: {
    en: ["Settings stay on this device (browser storage)."],
    hi: ["सेटिंग इस डिवाइस पर रहती हैं।"],
    bn: ["সেটিং এই ডিভাইসে থাকে।"],
  },
};

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
  overview: {
    en: [
      "Sky, rain, wind, soil: Open-Meteo (weather model, not a village rain-gauge).",
      "Next 6 hours: 0–2 h nowcast, 3–4 h blend, 5–6 h NWP. Past hours are model analysis, not a gauge.",
      "Air number: CPCB National AQI via data.gov.in when a station is near; otherwise the map says so.",
      "“Skip irrigation” litres: plot size × a small depth, not from the chat model.",
    ],
    hi: [
      "आकाश, बारिश, हवा, मिट्टी: Open-Meteo (मॉडल; गाँव का रेन-गेज नहीं)।",
      "अगले 6 घंटे: 0–2 नाउकास्ट, 3–4 मिश्रण, 5–6 NWP। बीते घंटे मॉडल हैं, गेज नहीं।",
      "हवा का अंक: पास हो तो CPCB / data.gov.in।",
      "सिंचाई रोकने के लीटर: खेत का क्षेत्र × गहराई — चैट मॉडल नहीं गिनता।",
    ],
    bn: [
      "আকাশ, বৃষ্টি, হাওয়া, মাটি: Open-Meteo (মডেল, গ্রামের বৃষ্টিমাপক নয়)।",
      "আগামী ৬ ঘণ্টা: ০–২ নাউকাস্ট, ৩–৪ মিশ্রণ, ৫–৬ NWP। গত ঘণ্টা মডেল, গেজ নয়।",
      "বাতাসের সংখ্যা: কাছে স্টেশন থাকলে CPCB / data.gov.in।",
      "সেচ না দেওয়ার লিটার: জমির আয়তন × গভীরতা — চ্যাট মডেল গণনা করে না।",
    ],
  },
  map: {
    en: ["Places: Indian gazetteer first, then Open-Meteo India search.", "Overlay: Bhuvan / NRSC geomorphology via our map proxy."],
    hi: ["जगह: पहले भारत गज़ेटियर, फिर Open-Meteo भारत खोज।", "परत: भूवन / NRSC, हमारे प्रॉक्सी से।"],
    bn: ["জায়গা: আগে ভারত গেজেটিয়ার, পরে Open-Meteo ভারত খোঁজ।", "স্তর: ভুবন / NRSC, আমাদের প্রক্সি দিয়ে।"],
  },
  forecast: {
    en: ["Seven-day rain and drying: Open-Meteo daily values.", "Soil day-to-day: wetting/drying memory (same rain runs off more if soil is already wet).", "Compare: two district snapshots, same method."],
    hi: ["7 दिन बारिश/सुखना: Open-Meteo दैनिक अंक।", "मिट्टी: गीली शाखा पर वही बारिश ज्यादा बहती है।", "तुलना: दो ज़िलों का एक जैसा स्नैपशॉट।"],
    bn: ["৭ দিন বৃষ্টি/শুকনো: Open-Meteo দৈনিক সংখ্যা।", "মাটি: ভেজা শাখায় একই বৃষ্টি বেশি বয়ে যায়।", "তুলনা: দুই জেলার একই পদ্ধতি।"],
  },
  predicted: {
    en: ["Weather service = published Open-Meteo.", "Rituchakra = same backbone, small local adjustment (never more than about 12%).", "Which to use: official warning first; otherwise the trust line on this page."],
    hi: ["मौसम सेवा = प्रकाशित Open-Meteo।", "ऋतुचक्र = वही आधार, छोटी स्थानीय मिलावट (लगभग 12% से अधिक नहीं)।", "क्या मानें: पहले सरकारी चेतावनी।"],
    bn: ["আবহাওয়া পরিষেবা = প্রকাশিত Open-Meteo।", "ঋতুচক্র = একই ভিত্তি, ছোট স্থানীয় মিল (প্রায় ১২%-এর বেশি নয়)।", "কী মানবেন: আগে সরকারি সতর্কতা।"],
  },
  risks: {
    en: ["Cards are traffic-lights, not fortune-telling.", "Flood factors follow a water budget (rain, runoff, soil store, river).", "Earthquake / sea cards only repeat official lists (USGS, INCOIS), they do not predict."],
    hi: ["कार्ड ट्रैफ़िक-लाइट हैं, भविष्यवाणी नहीं।", "बाढ़ कारक जल बजट से आते हैं।", "भूकंप/समुद्र केवल आधिकारिक सूची दोहराते हैं।"],
    bn: ["কার্ড ট্রাফিক-লাইট, ভাগ্যগণনা নয়।", "বন্যা কারণ আসে জল হিসাব থেকে।", "ভূমিকম্প/সমুদ্র শুধু সরকারি তালিকা বলে।"],
  },
  market: {
    en: ["Prices: Agmarknet via data.gov.in, rupees per quintal.", "Missing rows mean no arrival was filed for this district today."],
    hi: ["भाव: Agmarknet / data.gov.in, रुपये प्रति क्विंटल।", "खाली तालिका = आज इस ज़िले की आवक दर्ज नहीं।"],
    bn: ["দাম: Agmarknet / data.gov.in, টাকা প্রতি কুইন্টাল।", "খালি তালিকা = আজ এই জেলার আগমন নথি নেই।"],
  },
  advisor: {
    en: ["You may type any language. We translate to English for the model, then back.", "The model only reads tool numbers. It must not invent rain, litres, AQI or rupees."],
    hi: ["कोई भी भाषा लिखें। प्रश्न अंग्रेज़ी होकर मॉडल को जाता है, उत्तर आपकी भाषा में आता है।", "मॉडल केवल टूल के अंक पढ़ता है — बारिश/लीटर/AQI/रुपये नहीं गढ़ता।"],
    bn: ["যেকোনো ভাষায় লিখুন। প্রশ্ন ইংরেজি হয়ে মডেলে যায়, উত্তর আপনার ভাষায় ফেরে।", "মডেল শুধু টুলের সংখ্যা পড়ে — বৃষ্টি/লিটার/AQI/টাকা তৈরি করে না।"],
  },
};

export function SourcesBox({ tab, locale }: { tab: TabId; locale: Locale }) {
  const t = COPY[locale];
  const lines = (TAB_SOURCES[tab] || EXTRA[tab])?.[locale] || EXTRA[tab]?.[locale] || [];
  return (
    <Collapse title={t.sourcesAndMethods} subtitle={t.sourcesHint} defaultOpen={false}>
      <ul className="space-y-2 text-sm text-neo-muted">
        {lines.map((line) => (
          <li key={line}>• {line}</li>
        ))}
      </ul>
    </Collapse>
  );
}
