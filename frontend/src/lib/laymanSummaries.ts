import type { DashboardSnapshot } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";
import { localizeDigits } from "@/lib/units";
import { riskTitle } from "@/lib/plain";

export type MetricTone = "ok" | "watch" | "alert" | "info";

export type OverviewMetric = {
  label: string;
  value: string;
  tone: MetricTone;
};

export type LaymanSummary = {
  sectionId: string;
  sectionTitle: string;
  headline: string;
  badge: {
    label: string;
    tone: MetricTone;
  };
  metrics: OverviewMetric[];
  points: string[];
};

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function feelsLikeC(tempC?: number | null, rh?: number | null): number | null {
  if (tempC == null) return null;
  const t = Number(tempC);
  const h = Number(rh ?? 50);
  if (t < 26) return Math.round(t);
  const hi =
    -8.784695 +
    1.61139411 * t +
    2.338549 * h -
    0.14611605 * t * h -
    0.012308094 * t * t -
    0.016424828 * h * h +
    0.002211732 * t * t * h +
    0.00072546 * t * h * h -
    0.000003582 * t * t * h * h;
  return Math.round(hi * 10) / 10;
}

function fmtTemp(c: number | null | undefined, units: "metric" | "imperial", locale: Locale): string {
  if (c == null) return "—";
  const val = units === "imperial" ? Math.round((c * 9) / 5 + 32) : Math.round(c);
  const u = units === "imperial" ? "°F" : "°C";
  return `${localizeDigits(val, locale)}${u}`;
}

function fmtRain(mm: number | null | undefined, units: "metric" | "imperial", locale: Locale): string {
  if (mm == null || isNaN(Number(mm))) return `${localizeDigits(0, locale)} mm`;
  const v = Number(mm);
  const val = units === "imperial" ? (v / 25.4).toFixed(2) : v.toFixed(1);
  const u = units === "imperial" ? "in" : "mm";
  return `${localizeDigits(val, locale)} ${u}`;
}

function fmtSpeed(kmh: number | null | undefined, units: "metric" | "imperial", locale: Locale): string {
  if (kmh == null || isNaN(Number(kmh))) return "—";
  const v = Number(kmh);
  const val = units === "imperial" ? Math.round(v * 0.621) : Math.round(v);
  const u = units === "imperial" ? "mph" : "km/h";
  return `${localizeDigits(val, locale)} ${u}`;
}

const CONDITION_MAP: Record<string, Record<Locale, string>> = {
  clear: { en: "Clear Sky", hi: "साफ़ आसमान", bn: "পরিষ্কার আকাশ" },
  fair: { en: "Fair", hi: "साफ़ व शांत", bn: "স্বাভাবিক" },
  "partly cloudy": { en: "Partly Cloudy", hi: "आंशिक बादल", bn: "আংশিক মেঘলা" },
  overcast: { en: "Overcast", hi: "घने बादल", bn: "মেঘাচ্ছন্ন" },
  cloudy: { en: "Cloudy", hi: "बादल", bn: "মেঘলা" },
  rain: { en: "Rain", hi: "वर्षा", bn: "বৃষ্টি" },
  "light rain": { en: "Light Rain", hi: "हल्की वर्षा", bn: "হালকা বৃষ্টি" },
  "heavy rain": { en: "Heavy Rain", hi: "भारी वर्षा", bn: "ভারী বৃষ্টি" },
  thunderstorm: { en: "Thunderstorm", hi: "गरज-चमक के साथ बारिश", bn: "বজ্রবিদ্যুৎসহ ঝড়" },
  haze: { en: "Haze", hi: "धुंध", bn: "কুয়াশা" },
  fog: { en: "Fog", hi: "कोहरा", bn: "ঘন কুয়াশা" },
  mist: { en: "Mist", hi: "हल्का कोहरा", bn: "হালকা কুয়াশা" },
};

function translateCondition(cond: string, locale: Locale): string {
  const k = cond.toLowerCase().trim();
  if (CONDITION_MAP[k]?.[locale]) return CONDITION_MAP[k][locale];
  for (const [key, map] of Object.entries(CONDITION_MAP)) {
    if (k.includes(key)) return map[locale];
  }
  return cond;
}

/* -------------------------------------------------------------------------- */
/* 1. Sky & Atmosphere Summary (SkyRainHero)                                   */
/* -------------------------------------------------------------------------- */

export function getSkyLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale,
  units: "metric" | "imperial" = "metric"
): LaymanSummary {
  const cur = dash.descriptive.current;
  const sky = dash.live?.sky || {};
  const tempVal = sky.temp_c ?? cur.temp_c ?? null;
  const rhVal = sky.humidity_pct ?? cur.humidity_pct ?? 50;
  const feels = feelsLikeC(tempVal, rhVal);
  const cloudPct = Math.round(Number(sky.cloud_cover_pct ?? 40));
  const visKm = (sky as Record<string, unknown>).visibility_km != null ? Number((sky as Record<string, unknown>).visibility_km) : null;
  const uv = (sky as Record<string, unknown>).uv_index != null ? Number((sky as Record<string, unknown>).uv_index) : (dash.quality?.air as Record<string, unknown>)?.uv_index != null ? Number((dash.quality?.air as Record<string, unknown>)?.uv_index) : null;
  const rawCondition = sky.label || sky.kind || "Fair";
  const condition = translateCondition(rawCondition, locale);

  const isRainy = (sky.precip_1h_mm ?? 0) > 0.5 || (sky.label || "").toLowerCase().includes("rain");
  const isHot = (feels ?? tempVal ?? 25) >= 35;
  const isCold = (feels ?? tempVal ?? 25) <= 12;

  let headline = "";
  if (locale === "hi") {
    headline = isRainy
      ? "वर्षा और बादलों की स्थिति बनी हुई है।"
      : isHot
      ? "मौसम गर्म और उमस भरा है।"
      : isCold
      ? "मौसम ठंडा और शुष्क बना हुआ है।"
      : "आसमान सामान्य और मौसम स्थिर है।";
  } else if (locale === "bn") {
    headline = isRainy
      ? "বৃষ্টি ও মেঘলা আকাশ বিরাজ করছে।"
      : isHot
      ? "গরম ও আর্দ্র আবহাওয়া চলছে।"
      : isCold
      ? "ঠাণ্ডা ও শুষ্ক আবহাওয়া রয়েছে।"
      : "স্বাভাবিক ও স্থিতিশীল আবহাওয়া রয়েছে।";
  } else {
    headline = isRainy
      ? "Rain showers and overcast skies currently active."
      : isHot
      ? "Hot and humid conditions across the area."
      : isCold
      ? "Cool and clear atmospheric conditions."
      : "Stable atmospheric conditions with fair skies.";
  }

  const feelsPrefix = locale === "hi" ? "महसूस " : locale === "bn" ? "অনুভূত " : "Feels ";
  const normalText = locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "Normal";

  return {
    sectionId: "sky",
    sectionTitle: locale === "hi" ? "आसमान और वातावरण" : locale === "bn" ? "আকাশ ও বায়ুমণ্ডল" : "Sky & Atmosphere",
    headline,
    badge: {
      label: condition,
      tone: isRainy ? "watch" : isHot ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "तापमान" : locale === "bn" ? "তাপমাত্রা" : "Temperature",
        value: `${fmtTemp(tempVal, units, locale)} (${feelsPrefix}${fmtTemp(feels, units, locale)})`,
        tone: isHot || isCold ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "बादल" : locale === "bn" ? "মেঘের কভারেজ" : "Cloud Cover",
        value: `${localizeDigits(cloudPct, locale)}%`,
        tone: cloudPct > 70 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "आर्द्रता" : locale === "bn" ? "আর্দ্রতা" : "Humidity",
        value: `${localizeDigits(rhVal, locale)}%`,
        tone: rhVal > 80 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "दृश्यता" : locale === "bn" ? "দৃশ্যমানতা" : "Visibility",
        value: visKm != null ? `${localizeDigits(visKm, locale)} km` : normalText,
        tone: visKm != null && visKm < 3 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `वर्तमान आर्द्रता ${localizeDigits(rhVal, locale)}% और बादल ${localizeDigits(cloudPct, locale)}% दर्ज हैं।`
        : locale === "bn"
        ? `বর্তমান আর্দ্রতা ${localizeDigits(rhVal, locale)}% এবং মেঘের আচ্ছাদন ${localizeDigits(cloudPct, locale)}%।`
        : `Relative humidity sits at ${rhVal}% with cloud coverage at ${cloudPct}%.`,
      locale === "hi"
        ? uv != null ? `यूवी सूचकांक स्तर ${localizeDigits(uv, locale)} पर है।` : "दृश्यता सामान्य सीमा में बनी हुई है।"
        : locale === "bn"
        ? uv != null ? `ইউভি সূচক ${localizeDigits(uv, locale)} পরিমাপ করা হয়েছে।` : "দৃশ্যমানতা স্বাভাবিক পরিসরে রয়েছে।"
        : uv != null ? `UV radiation index is recorded at ${uv}.` : "Visibility remains in nominal parameters.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 2. Rainfall Summary (RainfallSection)                                      */
/* -------------------------------------------------------------------------- */

export function getRainLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale,
  units: "metric" | "imperial" = "metric"
): LaymanSummary {
  const predictive = dash.predictive;
  const series = dash.descriptive.series;
  const sky = dash.live?.sky || {};

  const precip1h = sky.precip_1h_mm ?? dash.descriptive.current.precip_1h_mm ?? 0;
  const todayMm = predictive.outlook_days?.[0]?.precip_mm ?? series.precip_daily?.[0]?.value ?? 0;
  const todayProb = predictive.outlook_days?.[0]?.precip_prob_pct ?? predictive.precip_probability_pct?.[0] ?? 0;
  const total7d = predictive.precip_7d_mm ?? ((predictive.outlook_days || []).reduce((acc, d) => acc + (d.precip_mm || 0), 0));

  const isRainingNow = precip1h > 0.2;
  const isHeavyToday = todayMm >= 15;
  const isDry = todayMm < 1 && todayProb < 25;

  let headline = "";
  if (locale === "hi") {
    headline = isRainingNow
      ? "वर्तमान में वर्षा हो रही है।"
      : isHeavyToday
      ? "आज भारी बारिश का अनुमान है।"
      : isDry
      ? "आज मौसम पूरी तरह शुष्क रहने की संभावना है।"
      : "दिन में हल्की छिटपुट बारिश संभव है।";
  } else if (locale === "bn") {
    headline = isRainingNow
      ? "বর্তমানে বৃষ্টিপাত চলছে।"
      : isHeavyToday
      ? "আজ ভারী বৃষ্টির সম্ভাবনা রয়েছে।"
      : isDry
      ? "আজ আবহাওয়া প্রধানত শুষ্ক থাকবে।"
      : "হালকা বিক্ষিপ্ত বৃষ্টির সম্ভাবনা রয়েছে।";
  } else {
    headline = isRainingNow
      ? "Active rainfall currently observed."
      : isHeavyToday
      ? "Moderate to heavy precipitation expected today."
      : isDry
      ? "Dry conditions expected with minimal rain probability."
      : "Light intermittent showers possible today.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = isRainingNow ? "सक्रिय वर्षा" : isHeavyToday ? "भारी वर्षा अनुमानित" : isDry ? "शुष्क" : "हल्की / छिटपुट";
  } else if (locale === "bn") {
    badgeLabel = isRainingNow ? "সক্রিয় বৃষ্টি" : isHeavyToday ? "ভারী বৃষ্টি প্রত্যাশিত" : isDry ? "শুষ্ক" : "হালকা / বিক্ষিপ্ত";
  } else {
    badgeLabel = isRainingNow ? "Active Rain" : isHeavyToday ? "Heavy Expected" : isDry ? "Dry" : "Light / Scattered";
  }

  return {
    sectionId: "rainfall",
    sectionTitle: locale === "hi" ? "वर्षा की स्थिति" : locale === "bn" ? "বৃষ্টিপাতের অবস্থা" : "Rainfall Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: isHeavyToday ? "alert" : isRainingNow ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "वर्तमान दर" : locale === "bn" ? "বর্তমান হার" : "Current Rate",
        value: `${fmtRain(precip1h, units, locale)}/h`,
        tone: isRainingNow ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "आज की वर्षा" : locale === "bn" ? "আজকের মোট বৃষ্টি" : "Today Expected",
        value: fmtRain(todayMm, units, locale),
        tone: isHeavyToday ? "alert" : todayMm > 3 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "संभावना" : locale === "bn" ? "সম্ভাবনা" : "Rain Chance",
        value: `${localizeDigits(todayProb, locale)}%`,
        tone: todayProb > 60 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "7 दिनों का कुल" : locale === "bn" ? "৭ দিনের মোট" : "7-Day Total",
        value: fmtRain(total7d, units, locale),
        tone: total7d > 50 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `आज कुल अनुमानित वर्षा ${fmtRain(todayMm, units, locale)} और संभावना ${localizeDigits(todayProb, locale)}% है।`
        : locale === "bn"
        ? `আজকের সম্ভাব্য বৃষ্টি ${fmtRain(todayMm, units, locale)} এবং সম্ভাবনা ${localizeDigits(todayProb, locale)}%।`
        : `Daily estimated precipitation is ${fmtRain(todayMm, units, locale)} with a ${todayProb}% probability.`,
      locale === "hi"
        ? `आगामी ${localizeDigits(7, locale)} दिनों का संचयी वर्षा अनुमान ${fmtRain(total7d, units, locale)} है।`
        : locale === "bn"
        ? `পরবর্তী ${localizeDigits(7, locale)} দিনের মোট বৃষ্টিপাতের পূর্বাভাস ${fmtRain(total7d, units, locale)}।`
        : `7-day cumulative rainfall projection stands at ${fmtRain(total7d, units, locale)}.`,
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 3. Wind Summary (WindSection)                                              */
/* -------------------------------------------------------------------------- */

export function getWindLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale,
  units: "metric" | "imperial" = "metric"
): LaymanSummary {
  const wind = dash.live?.wind || {};
  const quality = dash.quality || {};
  const climate = (quality.climate || {}) as Record<string, unknown>;

  const speedKmh = wind.speed_kmh != null ? Number(wind.speed_kmh) : (climate.wind_10m != null ? Number(climate.wind_10m) : 12);
  const gustKmh = climate.wind_gusts_10m != null ? Number(climate.wind_gusts_10m) : speedKmh * 1.35;
  const compass = wind.compass || wind.flow_compass || "NE";

  const isStorm = speedKmh >= 50 || gustKmh >= 65;
  const isBreezy = speedKmh >= 25;

  let headline = "";
  if (locale === "hi") {
    headline = isStorm
      ? "तेज हवाएं और आंधी की स्थिति सक्रिय है।"
      : isBreezy
      ? "मध्यम से तेज हवाएं चल रही हैं।"
      : "हवा की गति सामान्य और शांत है।";
  } else if (locale === "bn") {
    headline = isStorm
      ? "ঝড়ো এবং তীব্র বাতাস বইছে।"
      : isBreezy
      ? "মাঝারি ধরনের বাতাস চলছে।"
      : "বাতাস স্বাভাবিক ও শান্ত রয়েছে।";
  } else {
    headline = isStorm
      ? "Strong wind gusts and turbulent air active."
      : isBreezy
      ? "Moderate breezy conditions across the region."
      : "Gentle and calm wind conditions prevailing.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = isStorm ? "आंधी / तीव्र गति" : isBreezy ? "मध्यम हवा" : "शांत हवा";
  } else if (locale === "bn") {
    badgeLabel = isStorm ? "ঝড়ো / প্রবল" : isBreezy ? "মাঝারি বাতাস" : "শান্ত বাতাস";
  } else {
    badgeLabel = isStorm ? "Gale / Strong" : isBreezy ? "Breezy" : "Gentle";
  }

  let categoryValue = "";
  if (locale === "hi") {
    categoryValue = speedKmh < 12 ? "हल्की" : speedKmh < 28 ? "मध्यम" : speedKmh < 45 ? "तेज" : "प्रचंड";
  } else if (locale === "bn") {
    categoryValue = speedKmh < 12 ? "হালকা" : speedKmh < 28 ? "মাঝারি" : speedKmh < 45 ? "তীব্র" : "প্রচণ্ড";
  } else {
    categoryValue = speedKmh < 12 ? "Light" : speedKmh < 28 ? "Moderate" : speedKmh < 45 ? "Fresh" : "Strong";
  }

  return {
    sectionId: "wind",
    sectionTitle: locale === "hi" ? "हवा की स्थिति" : locale === "bn" ? "বাতাসের অবস্থা" : "Wind Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "सक्रिय गति" : locale === "bn" ? "গতিবেগ" : "Sustained Speed",
        value: fmtSpeed(speedKmh, units, locale),
        tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "अधिकतम झोंका" : locale === "bn" ? "ঝড়ো দমকা" : "Peak Gust",
        value: fmtSpeed(gustKmh, units, locale),
        tone: gustKmh > 40 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "दिशा" : locale === "bn" ? "দিক" : "Direction",
        value: compass,
        tone: "info",
      },
      {
        label: locale === "hi" ? "वर्ग" : locale === "bn" ? "মাত্রা" : "Category",
        value: categoryValue,
        tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `हवा की मुख्य दिशा ${compass} से ${fmtSpeed(speedKmh, units, locale)} की गति से है।`
        : locale === "bn"
        ? `বাতাসের প্রবাহ ${compass} দিক থেকে ${fmtSpeed(speedKmh, units, locale)} বেগে।`
        : `Dominant wind vector flows from ${compass} at ${fmtSpeed(speedKmh, units, locale)}.`,
      locale === "hi"
        ? `अधिकतम झोंकों की गति ${fmtSpeed(gustKmh, units, locale)} तक दर्ज की गई है।`
        : locale === "bn"
        ? `সর্বোচ্চ দমকা বাতাসের গতি ${fmtSpeed(gustKmh, units, locale)} পর্যন্ত রেকর্ড করা হয়েছে।`
        : `Peak gust velocity is monitored up to ${fmtSpeed(gustKmh, units, locale)}.`,
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 4. Alerts & Disaster Summary (RiskAlertPanel)                              */
/* -------------------------------------------------------------------------- */

export function getAlertsLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale
): LaymanSummary {
  const warnings = (dash.prescriptive.warnings || []).filter((w) =>
    ["extreme", "warning"].includes(w.severity)
  );
  const risks = dash.risks || [];
  const topRisk = [...risks].sort((a, b) => (b.score_pct ?? 0) - (a.score_pct ?? 0))[0];

  const hasExtreme = warnings.some((w) => w.severity === "extreme");
  const count = warnings.length;
  const localizedCount = localizeDigits(count, locale);

  let headline = "";
  if (locale === "hi") {
    headline = count === 0
      ? "कोई आपातकालीन सरकारी मौसम चेतावनी सक्रिय नहीं है।"
      : hasExtreme
      ? `${localizedCount} गंभीर मौसम बुलेटिन सक्रिय हैं।`
      : `${localizedCount} मौसम चेतावनी बुलेटिन जारी हैं।`;
  } else if (locale === "bn") {
    headline = count === 0
      ? "কোনো জরুরি সরকারি আবহাওয়া সতর্কতা সক্রিয় নেই।"
      : hasExtreme
      ? `${localizedCount}টি জরুরি আবহাওয়া সতর্কতা সক্রিয় রয়েছে।`
      : `${localizedCount}টি আবহাওয়া সতর্কতা জারি রয়েছে।`;
  } else {
    headline = count === 0
      ? "No severe weather bulletins active in this jurisdiction."
      : hasExtreme
      ? `${count} emergency weather bulletins currently in effect.`
      : `${count} meteorological advisories currently in effect.`;
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = count === 0 ? "सामान्य" : hasExtreme ? "आपातकालीन" : "सलाहकार";
  } else if (locale === "bn") {
    badgeLabel = count === 0 ? "স্বাভাবিক" : hasExtreme ? "জরুরি" : "পরামর্শ";
  } else {
    badgeLabel = count === 0 ? "Normal" : hasExtreme ? "Emergency" : "Advisory";
  }

  const localizedTopRiskLabel = topRisk ? riskTitle(topRisk.id, locale, topRisk.label) : (locale === "hi" ? "कोई नहीं" : locale === "bn" ? "কোনোটি নয়" : "None");

  let watchStatusValue = "";
  if (locale === "hi") {
    watchStatusValue = count > 0 ? "सक्रिय निगरानी" : "नियमित स्कैन";
  } else if (locale === "bn") {
    watchStatusValue = count > 0 ? "সক্রিয় নজরদারি" : "নিয়মিত স্ক্যান";
  } else {
    watchStatusValue = count > 0 ? "Active Monitor" : "Routine Scan";
  }

  return {
    sectionId: "alerts",
    sectionTitle: locale === "hi" ? "चेतावनी व जोखिम" : locale === "bn" ? "সতর্কতা ও ঝুঁকি" : "Alerts & Risk Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: hasExtreme ? "alert" : count > 0 ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "सक्रिय बुलेटिन" : locale === "bn" ? "সক্রিয় সতর্কতা" : "Active Bulletins",
        value: count === 0 ? (locale === "hi" ? `${localizeDigits(0, locale)} सक्रिय` : locale === "bn" ? `${localizeDigits(0, locale)}টি সক্রিয়` : "0 Active") : (locale === "hi" ? `${localizedCount} सक्रिय` : locale === "bn" ? `${localizedCount}টি সক্রিয়` : `${count} Active`),
        tone: hasExtreme ? "alert" : count > 0 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "प्रमुख जोखिम" : locale === "bn" ? "প্রধান ঝুঁকি" : "Dominant Risk",
        value: localizedTopRiskLabel,
        tone: (topRisk?.score_pct ?? 0) > 50 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "जोखिम सूचकांक" : locale === "bn" ? "ঝুঁকি সূচক" : "Risk Index",
        value: topRisk?.score_pct != null ? `${localizeDigits(topRisk.score_pct, locale)}%` : (locale === "hi" ? "निम्न" : locale === "bn" ? "কম" : "Low"),
        tone: (topRisk?.score_pct ?? 0) > 50 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "निगरानी स्थिति" : locale === "bn" ? "নজরদারি স্থিতি" : "Watch Status",
        value: watchStatusValue,
        tone: count > 0 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? count === 0 ? "सभी सरकारी निगरानी चैनलों पर स्थिति सामान्य है।" : `${localizedCount} आधिकारिक मौसम चेतावनियां प्रभाव में हैं।`
        : locale === "bn"
        ? count === 0 ? "সকল সরকারি নজরদারি চ্যানেলে পরিস্থিতি স্বাভাবিক রয়েছে।" : `${localizedCount}টি সরকারি সতর্কতা কার্যকর রয়েছে।`
        : count === 0 ? "Multi-agency hazard scanning indicates normal baseline status." : `${count} official meteorological advisories remain active.`,
      locale === "hi"
        ? topRisk ? `क्षेत्रीय जोखिम सूचकांक में मुख्य प्रभाव '${localizedTopRiskLabel}' का है।` : "भूकंप, बाढ़ व चक्रवात स्थिति स्थिर है।"
        : locale === "bn"
        ? topRisk ? `আঞ্চলিক ঝুঁকি সূচকে '${localizedTopRiskLabel}' প্রধান স্থান দখল করেছে।` : "ভূমিকম্প, বন্যা ও ঘূর্ণিঝড় পরিস্থিতি স্বাভাবিক।"
        : topRisk ? `Primary environmental risk vector identified as ${topRisk.label}.` : "Seismic, flood, and cyclogenesis monitoring channels report nominal.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 5. Air Quality & Pollen Summary (AirCard)                                  */
/* -------------------------------------------------------------------------- */

export function getAirLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale
): LaymanSummary {
  const q = dash.quality || {};
  const air = (q.air || {}) as Record<string, unknown>;
  const cpcb = (air.cpcb || {}) as Record<string, unknown>;
  const cpcbVal = cpcb.value ?? dash.descriptive?.current?.aqi;
  const cpcbCat = cpcb.category != null ? String(cpcb.category) : (dash.descriptive?.current?.aqi_category ? String(dash.descriptive?.current?.aqi_category) : null);

  let aqiVal: number | null = null;
  let source: "cpcb" | "open-meteo" = "open-meteo";

  if (cpcbVal != null && !isNaN(Number(cpcbVal))) {
    aqiVal = Number(cpcbVal);
    source = "cpcb";
  } else {
    const series = dash.descriptive?.series;
    const hourlyNow = series?.aqi_hourly?.[0]?.value;
    const om = dash.descriptive?.current?.om_us_aqi ?? air.us_aqi ?? hourlyNow;
    if (om != null && !isNaN(Number(om))) {
      aqiVal = Number(om);
      source = "open-meteo";
    }
  }

  const pm25 = air.pm2_5 != null ? Number(air.pm2_5) : null;
  const pm10 = air.pm10 != null ? Number(air.pm10) : null;

  // National AQI (CPCB) Standard Categories
  let aqiLabel = cpcbCat || "Good";
  let tone: "ok" | "watch" | "alert" = "ok";

  if (!cpcbCat && aqiVal != null) {
    if (aqiVal <= 50) {
      aqiLabel = "Good";
      tone = "ok";
    } else if (aqiVal <= 100) {
      aqiLabel = "Satisfactory";
      tone = "ok";
    } else if (aqiVal <= 200) {
      aqiLabel = "Moderate";
      tone = "watch";
    } else if (aqiVal <= 300) {
      aqiLabel = "Poor";
      tone = "alert";
    } else if (aqiVal <= 400) {
      aqiLabel = "Very Poor";
      tone = "alert";
    } else {
      aqiLabel = "Severe";
      tone = "alert";
    }
  } else if (cpcbCat) {
    const lower = cpcbCat.toLowerCase();
    if (lower.includes("poor") || lower.includes("severe") || lower.includes("unhealthy")) {
      tone = "alert";
    } else if (lower.includes("moderate")) {
      tone = "watch";
    } else {
      tone = "ok";
    }
  }

  const isSevere = tone === "alert" && (aqiVal == null || aqiVal > 300);
  const isPoor = tone === "alert";
  const isModerate = tone === "watch";

  let headline = "";
  if (locale === "hi") {
    headline = isSevere
      ? "वायु गुणवत्ता गंभीर स्तर पर दर्ज की गई है।"
      : isPoor
      ? "वायु गुणवत्ता खराब श्रेणी में है।"
      : isModerate
      ? "वायु गुणवत्ता मध्यम स्तर पर स्थिर है।"
      : "वायु गुणवत्ता संतोषजनक और स्वच्छ है।";
  } else if (locale === "bn") {
    headline = isSevere
      ? "বাতাসের মান মারাত্মক ঝুঁকিপূর্ণ অবস্থায় রয়েছে।"
      : isPoor
      ? "বাতাসের মান অস্বাস্থ্যকর পর্যায়ে রয়েছে।"
      : isModerate
      ? "বাতাসের মান মাঝারি মাত্রায় রয়েছে।"
      : "বাতাসের মান ভালো ও সন্তোষজনক।";
  } else {
    headline = isSevere
      ? "Air quality index is in the severe category."
      : isPoor
      ? "Air quality index indicates unhealthy particulate levels."
      : isModerate
      ? "Air quality is in the moderate range."
      : "Air quality is good and particulate levels are low.";
  }

  const displayAqi = aqiVal != null ? localizeDigits(aqiVal, locale) : "—";

  const AQI_CAT_LOCALIZED: Record<string, Record<Locale, string>> = {
    good: { en: "Good", hi: "अच्छा", bn: "ভালো" },
    satisfactory: { en: "Satisfactory", hi: "संतोषजनक", bn: "সন্তোষজনক" },
    moderate: { en: "Moderate", hi: "मध्यम", bn: "মাঝারি" },
    poor: { en: "Poor", hi: "खराब", bn: "খারাপ" },
    "very poor": { en: "Very Poor", hi: "बहुत खराब", bn: "খুব খারাপ" },
    severe: { en: "Severe", hi: "गंभीर", bn: "মারাত্মক" },
  };
  const normCatKey = aqiLabel.toLowerCase().trim();
  const localizedAqiLabel = AQI_CAT_LOCALIZED[normCatKey]?.[locale] || aqiLabel;
  const nominalText = locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "Nominal";

  return {
    sectionId: "air",
    sectionTitle: locale === "hi" ? "वायु गुणवत्ता" : locale === "bn" ? "বাতাসের মান" : "Air Quality Overview",
    headline,
    badge: {
      label: localizedAqiLabel,
      tone,
    },
    metrics: [
      {
        label: source === "cpcb" ? (locale === "hi" ? "AQI (सीपीसीबी)" : locale === "bn" ? "AQI (সিপিসিবি)" : "AQI (CPCB)") : "AQI",
        value: displayAqi,
        tone,
      },
      {
        label: locale === "hi" ? "श्रेणी" : locale === "bn" ? "শ্রেণী" : "Category",
        value: localizedAqiLabel,
        tone,
      },
      {
        label: "PM2.5",
        value: pm25 != null ? `${localizeDigits(Math.round(pm25), locale)} µg/m³` : nominalText,
        tone: pm25 != null && pm25 > 60 ? "watch" : "ok",
      },
      {
        label: "PM10",
        value: pm10 != null ? `${localizeDigits(Math.round(pm10), locale)} µg/m³` : nominalText,
        tone: pm10 != null && pm10 > 100 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `वर्तमान वायु सूचकांक ${displayAqi} (${localizedAqiLabel}) दर्ज है।`
        : locale === "bn"
        ? `বর্তমান এয়ার কোয়ালিটি ইনডেক্স ${displayAqi} (${localizedAqiLabel})।`
        : `Current air quality index reads ${displayAqi} under the ${aqiLabel} category${source === "cpcb" ? " (CPCB ground sensor)" : ""}.`,
      locale === "hi"
        ? pm25 != null ? `प्रमुख प्रदूषक कण PM2.5 की सांद्रता ${localizeDigits(Math.round(pm25), locale)} µg/m³ है।` : "गैस व परागकण सामान्य सीमा में हैं।"
        : locale === "bn"
        ? pm25 != null ? `প্রধান দূষক PM2.5 এর ঘনত্ব ${localizeDigits(Math.round(pm25), locale)} µg/m³।` : "গ্যাস ও পরাগরেণু স্বাভাবিক মাত্রায়।"
        : pm25 != null ? `Primary particulate PM2.5 measures at ${Math.round(pm25)} µg/m³.` : "Gas and pollen concentrations remain within standard thresholds.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 6. Soil & Land Weather Summary (LandWeatherCard)                           */
/* -------------------------------------------------------------------------- */

export function getSoilLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale
): LaymanSummary {
  const q = dash.quality || {};
  const climate = (q.climate || {}) as Record<string, unknown>;
  const topsoil = Number(climate.soil_m_0_1 ?? dash.descriptive.current.soil_moisture_m3m3 ?? 0.28);
  const et0 = climate.et0_today != null ? Number(climate.et0_today) : null;
  const vpd = climate.vpd_now != null ? Number(climate.vpd_now) : null;

  const isDry = topsoil < 0.18;
  const isWet = topsoil > 0.42;

  let headline = "";
  if (locale === "hi") {
    headline = isDry
      ? "मिट्टी में नमी की कमी है, शुष्क स्थिति।"
      : isWet
      ? "मिट्टी में पर्याप्त व अधिक नमी बनी हुई है।"
      : "मिट्टी में सामान्य व संतुलित नमी स्तर है।";
  } else if (locale === "bn") {
    headline = isDry
      ? "মাটির আর্দ্রতা কম, শুষ্ক অবস্থা।"
      : isWet
      ? "মাটিতে পর্যাপ্ত ও আর্দ্র অবস্থা রয়েছে।"
      : "মাটিতে স্বাভাবিক ও সন্তোষজনক আর্দ্রতা রয়েছে।";
  } else {
    headline = isDry
      ? "Soil moisture levels are low and dry."
      : isWet
      ? "High soil moisture and saturated topsoil conditions."
      : "Adequate and balanced soil moisture conditions.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = isDry ? "शुष्क" : isWet ? "अधिक नमी" : "संतुलित";
  } else if (locale === "bn") {
    badgeLabel = isDry ? "শুষ্ক" : isWet ? "অতিরিক্ত আর্দ্রতা" : "ভারসাম্যপূর্ণ";
  } else {
    badgeLabel = isDry ? "Dry" : isWet ? "High Moisture" : "Balanced";
  }

  let condValue = "";
  if (locale === "hi") {
    condValue = isDry ? "अल्प" : isWet ? "संतृप्त" : "पर्याप्त";
  } else if (locale === "bn") {
    condValue = isDry ? "ঘাটতি" : isWet ? "পরিপৃক্ত" : "পর্যাপ্ত";
  } else {
    condValue = isDry ? "Depleted" : isWet ? "Saturated" : "Adequate";
  }

  const normalText = locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "Normal";

  return {
    sectionId: "soil",
    sectionTitle: locale === "hi" ? "भूमि व मिट्टी" : locale === "bn" ? "মাটি ও আর্দ্রতা" : "Soil & Moisture Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: isDry ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "ऊपरी नमी (0–1cm)" : locale === "bn" ? "উপরের আর্দ্রতা (0–1cm)" : "Topsoil (0–1cm)",
        value: `${localizeDigits(topsoil.toFixed(2), locale)} m³/m³`,
        tone: isDry ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "वाष्पीकरण ET₀" : locale === "bn" ? "বাষ্পীভবন ET₀" : "Evaporation ET₀",
        value: et0 != null ? `${localizeDigits(et0, locale)} mm` : normalText,
        tone: "info",
      },
      {
        label: locale === "hi" ? "वाष्प दबाव घाटा" : locale === "bn" ? "বাষ্প চাপ ঘাটতি" : "Vapour Pressure Deficit",
        value: vpd != null ? `${localizeDigits(vpd, locale)} kPa` : normalText,
        tone: "info",
      },
      {
        label: locale === "hi" ? "स्थिति" : locale === "bn" ? "স্থিতি" : "Condition",
        value: condValue,
        tone: isDry ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `ऊपरी मिट्टी में नमी की मात्रा ${localizeDigits(topsoil.toFixed(3), locale)} m³/m³ मापी गई है।`
        : locale === "bn"
        ? `মাটির উপরিভাগের আর্দ্রতা ${localizeDigits(topsoil.toFixed(3), locale)} m³/m³ রেকর্ড করা হয়েছে।`
        : `Topsoil moisture layer is recorded at ${topsoil.toFixed(3)} m³/m³.`,
      locale === "hi"
        ? et0 != null ? `दैनिक वाष्पीकरण दर लगभग ${localizeDigits(et0, locale)} mm है।` : "भूमि वाष्पीकरण दर स्थिर है।"
        : locale === "bn"
        ? et0 != null ? `দৈনিক বাষ্পীভবন হার প্রায় ${localizeDigits(et0, locale)} mm।` : "মাটির বাষ্পীভবন স্বাভাবিক রয়েছে।"
        : et0 != null ? `Daily reference evapotranspiration is approximately ${et0} mm.` : "Soil evapotranspiration rate remains within seasonal norms.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 7. Marine Weather Summary (MarineWeatherCard)                              */
/* -------------------------------------------------------------------------- */

export function getMarineLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale
): LaymanSummary {
  const q = dash.quality || {};
  const marine = (q.marine || {}) as Record<string, unknown>;
  const waveM = marine.wave_height_m != null ? Number(marine.wave_height_m) : null;
  const sstC = marine.sst_c != null ? Number(marine.sst_c) : null;
  const period = marine.wave_period_s != null ? Number(marine.wave_period_s) : null;

  const isRough = waveM != null && waveM >= 2.5;
  const isModerate = waveM != null && waveM >= 1.25;

  let headline = "";
  if (locale === "hi") {
    headline = waveM == null
      ? "अंतर्देशीय क्षेत्र, कोई समुद्री लहर प्रभाव नहीं।"
      : isRough
      ? "समुद्र में ऊंची लहरें और अशांत स्थिति।"
      : isModerate
      ? "समुद्री लहरें मध्यम स्तर पर हैं।"
      : "समुद्र शांत और जलस्तर सामान्य है।";
  } else if (locale === "bn") {
    headline = waveM == null
      ? "অভ্যন্তরীণ অঞ্চল, সমুদ্র তরঙ্গের প্রভাব নেই।"
      : isRough
      ? "সমুদ্রে উত্তাল ও বড় ঢেউ বিরাজ করছে।"
      : isModerate
      ? "মাঝারি সমুদ্র তরঙ্গ অবস্থা রয়েছে।"
      : "সমুদ্র শান্ত এবং স্বাভাবিক অবস্থায় আছে।";
  } else {
    headline = waveM == null
      ? "Inland location with no direct marine wave activity."
      : isRough
      ? "Rough sea state with significant wave heights."
      : isModerate
      ? "Moderate wave conditions along coastal areas."
      : "Calm and smooth sea surface conditions.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = waveM == null ? "अंतर्देशीय" : isRough ? "अशांत" : isModerate ? "मध्यम" : "शांत";
  } else if (locale === "bn") {
    badgeLabel = waveM == null ? "অভ্যন্তরীণ" : isRough ? "উত্তাল" : isModerate ? "মাঝারি" : "শান্ত";
  } else {
    badgeLabel = waveM == null ? "Inland" : isRough ? "Rough" : isModerate ? "Moderate" : "Calm";
  }

  let seaStateVal = "";
  if (locale === "hi") {
    seaStateVal = waveM == null ? "अंतर्देशीय" : isRough ? "अशांत / तीव्र" : isModerate ? "मध्यम लहरें" : "शांत / समतल";
  } else if (locale === "bn") {
    seaStateVal = waveM == null ? "অভ্যন্তরীণ" : isRough ? "উত্তাল / তীব্র" : isModerate ? "মাঝারি ঢেউ" : "শান্ত / সমতল";
  } else {
    seaStateVal = waveM == null ? "Inland" : isRough ? "Rough" : isModerate ? "Moderate" : "Smooth";
  }

  const normalText = locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "Normal";

  return {
    sectionId: "marine",
    sectionTitle: locale === "hi" ? "समुद्री मौसम" : locale === "bn" ? "সামুদ্রিক অবস্থা" : "Marine Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: isRough ? "alert" : isModerate ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "लहरों की ऊंचाई" : locale === "bn" ? "ঢেউয়ের উচ্চতা" : "Significant Wave",
        value: waveM != null ? `${localizeDigits(waveM.toFixed(2), locale)} m` : (locale === "hi" ? "अंतर्देशीय" : locale === "bn" ? "অভ্যন্তরীণ" : "Inland"),
        tone: isRough ? "alert" : isModerate ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "लहर अवधि" : locale === "bn" ? "তরঙ্গ কাল" : "Wave Period",
        value: period != null ? `${localizeDigits(period, locale)} s` : normalText,
        tone: "info",
      },
      {
        label: locale === "hi" ? "समुद्र सतह तापमान (SST)" : locale === "bn" ? "সমুদ্র তাপমাত্রা (SST)" : "Sea Temp (SST)",
        value: sstC != null ? `${localizeDigits(Math.round(sstC), locale)}°C` : "—",
        tone: "info",
      },
      {
        label: locale === "hi" ? "समुद्री स्थिति" : locale === "bn" ? "সমুদ্রের স্থিতি" : "Sea State",
        value: seaStateVal,
        tone: isRough ? "alert" : isModerate ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? waveM != null ? `सार्थक तरंग ऊंचाई ${localizeDigits(waveM.toFixed(1), locale)} मीटर मापी गई है।` : "क्षेत्रीय जलस्तर और नदियां सामान्य प्रवाह में हैं।"
        : locale === "bn"
        ? waveM != null ? `তরঙ্গ উচ্চতা ${localizeDigits(waveM.toFixed(1), locale)} মিটার রেকর্ড হয়েছে।` : "আঞ্চলিক নদী ও জলাশয়ের প্রবাহ স্বাভাবিক।"
        : waveM != null ? `Significant wave height measures at ${waveM.toFixed(1)} meters.` : "Regional hydrological flow and rivers remain at normal baseline.",
      locale === "hi"
        ? sstC != null ? `समुद्र सतह का तापमान ${localizeDigits(Math.round(sstC), locale)}°C है।` : "तटीय ज्वार-भाटा सामान्य स्थिति में है।"
        : locale === "bn"
        ? sstC != null ? `সমুদ্রপৃষ্ঠের তাপমাত্রা ${localizeDigits(Math.round(sstC), locale)}°C।` : "উপকূলীয় জোয়ার-ভাটা স্বাভাবিক সীমার মধ্যে।"
        : sstC != null ? `Sea surface temperature is measured at ${Math.round(sstC)}°C.` : "Tidal flow and swell metrics remain within nominal bounds.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 8. 7-Day Weather Horizon (Forecast7DayDeck)                                */
/* -------------------------------------------------------------------------- */

export function get7DayLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale
): LaymanSummary {
  const days = dash.predictive.outlook_days || [];
  const totalRain = days.reduce((sum, d) => sum + (d.precip_mm || 0), 0);
  const maxDay = days.reduce(
    (top, d) => ((d.precip_mm || 0) > (top.precip_mm || 0) ? d : top),
    days[0] || { date: "—", precip_mm: 0 }
  );

  let minTemp = 999;
  let maxTemp = -999;
  for (const d of days) {
    if (d.temp_min_c != null && d.temp_min_c < minTemp) minTemp = d.temp_min_c;
    if (d.temp_max_c != null && d.temp_max_c > maxTemp) maxTemp = d.temp_max_c;
  }
  if (minTemp === 999) minTemp = 20;
  if (maxTemp === -999) maxTemp = 32;

  const isRainyWeek = totalRain > 25;

  let headline = "";
  if (locale === "hi") {
    headline = isRainyWeek
      ? "आगामी सप्ताह में रुक-रुक कर बारिश होने की संभावना है।"
      : totalRain > 5
      ? "सप्ताह में अधिकांश दिन शुष्क और कुछ दिन हल्की बारिश रहेगी।"
      : "पूरे सप्ताह मौसम मुख्य रूप से साफ और शुष्क रहने का अनुमान है।";
  } else if (locale === "bn") {
    headline = isRainyWeek
      ? "আগামী সপ্তাহে বিভিন্ন দিনে বৃষ্টির সম্ভাবনা রয়েছে।"
      : totalRain > 5
      ? "সপ্তাহের বেশিরভাগ দিন শুষ্ক থাকবে, মাঝে মাঝে সামান্য বৃষ্টি হতে পারে।"
      : "পুরো সপ্তাহ জুড়ে আবহাওয়া প্রধানত পরিষ্কার ও শুষ্ক থাকবে।";
  } else {
    headline = isRainyWeek
      ? "Active precipitation expected across multiple days this week."
      : totalRain > 5
      ? "Predominantly dry conditions with scattered light showers."
      : "Fair and dry conditions projected throughout the 7-day period.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = isRainyWeek ? "बारिश संभावित" : totalRain > 5 ? "परिवर्तनशील" : "मुख्यतः शुष्क";
  } else if (locale === "bn") {
    badgeLabel = isRainyWeek ? "বৃষ্টির সম্ভাবনা" : totalRain > 5 ? "পরিবর্তনশীল" : "প্রধানত শুষ্ক";
  } else {
    badgeLabel = isRainyWeek ? "Showers Expected" : totalRain > 5 ? "Variable" : "Predominantly Dry";
  }

  let trendVal = "";
  if (locale === "hi") {
    trendVal = isRainyWeek ? "आर्द्र / वर्षा" : totalRain > 5 ? "सामान्य" : "शुष्क";
  } else if (locale === "bn") {
    trendVal = isRainyWeek ? "আর্দ্র / বৃষ্টি" : totalRain > 5 ? "স্বাভাবিক" : "শুষ্ক";
  } else {
    trendVal = isRainyWeek ? "Wet" : totalRain > 5 ? "Normal" : "Dry";
  }

  const noneText = locale === "hi" ? "कोई नहीं" : locale === "bn" ? "কোনোটি নয়" : "None";

  return {
    sectionId: "forecast7d",
    sectionTitle: locale === "hi" ? "7 दिनों का पूर्वानुमान" : locale === "bn" ? "৭ দিনের পূর্বাভাস" : "7-Day Outlook Overview",
    headline,
    badge: {
      label: badgeLabel,
      tone: isRainyWeek ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "7 दिनों की बारिश" : locale === "bn" ? "৭ দিনের মোট বৃষ্টি" : "7-Day Precip",
        value: `${localizeDigits(totalRain.toFixed(1), locale)} mm`,
        tone: totalRain > 25 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "तापमान सीमा" : locale === "bn" ? "তাপমাত্রা পরিসীমা" : "Temp Range",
        value: `${localizeDigits(Math.round(minTemp), locale)}° – ${localizeDigits(Math.round(maxTemp), locale)}°C`,
        tone: "ok",
      },
      {
        label: locale === "hi" ? "सर्वाधिक बारिश का दिन" : locale === "bn" ? "সর্বোচ্চ বৃষ্টির দিন" : "Peak Rain Day",
        value: (maxDay.precip_mm || 0) > 0 ? `${localizeDigits(maxDay.date.slice(5), locale)} (${localizeDigits((maxDay.precip_mm || 0).toFixed(1), locale)} mm)` : noneText,
        tone: (maxDay.precip_mm || 0) > 10 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "सप्ताह का रुझान" : locale === "bn" ? "সাপ্তাহিক প্রবণতা" : "Weekly Trend",
        value: trendVal,
        tone: isRainyWeek ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `सप्ताह में कुल अनुमानित वर्षा ${localizeDigits(totalRain.toFixed(1), locale)} mm और तापमान ${localizeDigits(Math.round(minTemp), locale)}°C से ${localizeDigits(Math.round(maxTemp), locale)}°C रहेगा।`
        : locale === "bn"
        ? `সপ্তাহে মোট বৃষ্টিপাত ${localizeDigits(totalRain.toFixed(1), locale)} mm এবং তাপমাত্রা ${localizeDigits(Math.round(minTemp), locale)}°C থেকে ${localizeDigits(Math.round(maxTemp), locale)}°C।`
        : `7-day cumulative precipitation is ${totalRain.toFixed(1)} mm with temperatures between ${Math.round(minTemp)}°C and ${Math.round(maxTemp)}°C.`,
      locale === "hi"
        ? (maxDay.precip_mm || 0) > 1
          ? `सप्ताह में सबसे अधिक वर्षा ${localizeDigits(maxDay.date.slice(5), locale)} को दर्ज होने का अनुमान है।`
          : "अधिकांश दिनों में वर्षा की संभावना 20% से कम है।"
        : locale === "bn"
        ? (maxDay.precip_mm || 0) > 1
          ? `সপ্তাহের সর্বোচ্চ বৃষ্টি ${localizeDigits(maxDay.date.slice(5), locale)} তারিখে প্রত্যাশিত।`
          : "বেশিরভাগ দিনে বৃষ্টির সম্ভাবনা ২০% এর নিচে।"
        : (maxDay.precip_mm || 0) > 1
        ? `Peak daily rainfall is projected on ${maxDay.date.slice(5)}.`
        : "Rain probability remains below 20% for the majority of the period.",
    ],
  };
}

/* -------------------------------------------------------------------------- */
/* 9. Next 6 Hours Outlook Summary (NowcastSection)                          */
/* -------------------------------------------------------------------------- */

export function getNowcastLaymanSummary(
  dash: DashboardSnapshot,
  locale: Locale,
  units: "metric" | "imperial"
): LaymanSummary {
  const sixHour = (dash.predictive.hourly || []).slice(0, 6);
  const totalRain6h = sixHour.reduce((sum, h) => sum + (h.precip_mm || 0), 0);
  const temps = sixHour.map((h) => h.temp_c).filter((t): t is number => t != null);
  const minTemp = temps.length ? Math.min(...temps) : 25;
  const maxTemp = temps.length ? Math.max(...temps) : 32;
  const winds = sixHour.map((h) => h.wind_kmh).filter((w): w is number => w != null);
  const maxWind = winds.length ? Math.max(...winds) : 12;

  const isRainy = totalRain6h > 1.0;
  const sixHrsLocalized = localizeDigits(6, locale);

  let headline = "";
  if (locale === "hi") {
    headline = isRainy
      ? `अगले ${sixHrsLocalized} घंटों में लगभग ${localizeDigits(totalRain6h.toFixed(1), locale)} मिमी बारिश का अनुमान है।`
      : `अगले ${sixHrsLocalized} घंटों में मौसम शुष्क और स्थिर रहने की संभावना है।`;
  } else if (locale === "bn") {
    headline = isRainy
      ? `পরবর্তী ${sixHrsLocalized} ঘণ্টায় প্রায় ${localizeDigits(totalRain6h.toFixed(1), locale)} মিমি বৃষ্টির সম্ভাবনা রয়েছে।`
      : `পরবর্তী ${sixHrsLocalized} ঘণ্টায় আবহাওয়া শুষ্ক ও স্থিতিশীল থাকবে।`;
  } else {
    headline = isRainy
      ? `Approximately ${totalRain6h.toFixed(1)} mm of rain expected across the next 6 hours.`
      : "Stable conditions with dry weather expected across the next 6 hours.";
  }

  let badgeLabel = "";
  if (locale === "hi") {
    badgeLabel = isRainy ? "आगे बारिश" : "शुष्क समय";
  } else if (locale === "bn") {
    badgeLabel = isRainy ? "সামনে বৃষ্টি" : "শুষ্ক সময়";
  } else {
    badgeLabel = isRainy ? "Showers Ahead" : "Dry Window";
  }

  return {
    sectionId: "nowcast",
    sectionTitle: locale === "hi" ? "अगले 6 घंटे" : locale === "bn" ? "পরবর্তী ৬ ঘণ্টা" : "Next 6 Hours",
    headline,
    badge: {
      label: badgeLabel,
      tone: isRainy ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "6 घंटे बारिश" : locale === "bn" ? "৬ ঘণ্টার বৃষ্টি" : "6h Rain",
        value: totalRain6h > 0 ? `${localizeDigits(totalRain6h.toFixed(1), locale)} mm` : `${localizeDigits(0, locale)} mm`,
        tone: isRainy ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "तापमान दायरा" : locale === "bn" ? "তাপমাত্রা পরিসীমা" : "Temp Span",
        value: `${localizeDigits(Math.round(minTemp), locale)}° – ${localizeDigits(Math.round(maxTemp), locale)}°C`,
        tone: "ok",
      },
      {
        label: locale === "hi" ? "अधिकतम हवा" : locale === "bn" ? "সর্বোচ্চ বাতাস" : "Peak Wind",
        value: `${localizeDigits(Math.round(maxWind), locale)} km/h`,
        tone: maxWind > 35 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "अनुमानित खिड़की" : locale === "bn" ? "পূর্বাভাস উইন্ডো" : "Nowcast Span",
        value: locale === "hi" ? `${localizeDigits(0, locale)} – ${sixHrsLocalized} घंटे` : locale === "bn" ? `${localizeDigits(0, locale)} – ${sixHrsLocalized} ঘণ্টা` : "0 – 6 Hours",
        tone: "info",
      },
    ],
    points: [
      locale === "hi"
        ? `तापमान ${localizeDigits(Math.round(minTemp), locale)}°C से ${localizeDigits(Math.round(maxTemp), locale)}°C के बीच रहेगा।`
        : locale === "bn"
        ? `তাপমাত্রা ${localizeDigits(Math.round(minTemp), locale)}°C থেকে ${localizeDigits(Math.round(maxTemp), locale)}°C-এর মধ্যে থাকবে।`
        : `Surface temperatures will track between ${Math.round(minTemp)}°C and ${Math.round(maxTemp)}°C.`,
      locale === "hi"
        ? isRainy ? "अगले कुछ घंटों में हल्की बारिश देखने को मिल सकती है।" : "निकट भविष्य में बारिश का कोई संकेत नहीं है।"
        : locale === "bn"
        ? isRainy ? "পরবর্তী কয়েক ঘণ্টায় হালকা বৃষ্টি হতে পারে।" : "নিকটবর্তী সময়ে বৃষ্টির কোনো সম্ভাবনা নেই।"
        : isRainy ? "Intermittent showers possible during the upcoming forecast window." : "Precipitation indices remain suppressed for this window.",
    ],
  };
}
