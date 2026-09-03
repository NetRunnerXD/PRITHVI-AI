import type { DashboardSnapshot } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";

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

function fmtTemp(c: number | null | undefined, units: "metric" | "imperial"): string {
  if (c == null) return "—";
  if (units === "imperial") return `${Math.round((c * 9) / 5 + 32)}°F`;
  return `${Math.round(c)}°C`;
}

function fmtRain(mm: number | null | undefined, units: "metric" | "imperial"): string {
  if (mm == null || isNaN(Number(mm))) return "0 mm";
  const v = Number(mm);
  if (units === "imperial") return `${(v / 25.4).toFixed(2)} in`;
  return `${v.toFixed(1)} mm`;
}

function fmtSpeed(kmh: number | null | undefined, units: "metric" | "imperial"): string {
  if (kmh == null || isNaN(Number(kmh))) return "—";
  const v = Number(kmh);
  if (units === "imperial") return `${Math.round(v * 0.621)} mph`;
  return `${Math.round(v)} km/h`;
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
  const condition = sky.label || sky.kind || "Fair";

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
        value: `${fmtTemp(tempVal, units)} (Feels ${fmtTemp(feels, units)})`,
        tone: isHot || isCold ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "बादल" : locale === "bn" ? "মেঘের কভারেজ" : "Cloud Cover",
        value: `${cloudPct}%`,
        tone: cloudPct > 70 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "आर्द्रता" : locale === "bn" ? "আর্দ্রতা" : "Humidity",
        value: `${rhVal}%`,
        tone: rhVal > 80 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "दृश्यता" : locale === "bn" ? "দৃশ্যমানতা" : "Visibility",
        value: visKm != null ? `${visKm} km` : "Normal",
        tone: visKm != null && visKm < 3 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `वर्तमान आर्द्रता ${rhVal}% और बादल ${cloudPct}% दर्ज हैं।`
        : locale === "bn"
        ? `বর্তমান আর্দ্রতা ${rhVal}% এবং মেঘের আচ্ছাদন ${cloudPct}%।`
        : `Relative humidity sits at ${rhVal}% with cloud coverage at ${cloudPct}%.`,
      locale === "hi"
        ? uv != null ? `यूवी सूचकांक ${uv} स्तर पर है।` : "दृश्यता सामान्य सीमा में बनी हुई है।"
        : locale === "bn"
        ? uv != null ? `ইউভি সূচক ${uv} পরিমাপ করা হয়েছে।` : "দৃশ্যমানতা স্বাভাবিক পরিসরে রয়েছে।"
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

  return {
    sectionId: "rainfall",
    sectionTitle: locale === "hi" ? "वर्षा की स्थिति" : locale === "bn" ? "বৃষ্টিপাতের অবস্থা" : "Rainfall Overview",
    headline,
    badge: {
      label: isRainingNow ? "Active Rain" : isHeavyToday ? "Heavy Expected" : isDry ? "Dry" : "Light / Scattered",
      tone: isHeavyToday ? "alert" : isRainingNow ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "वर्तमान दर" : locale === "bn" ? "বর্তমান হার" : "Current Rate",
        value: `${fmtRain(precip1h, units)}/h`,
        tone: isRainingNow ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "आज की वर्षा" : locale === "bn" ? "আজকের মোট বৃষ্টি" : "Today Expected",
        value: fmtRain(todayMm, units),
        tone: isHeavyToday ? "alert" : todayMm > 3 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "संभावना" : locale === "bn" ? "সম্ভাবনা" : "Rain Chance",
        value: `${todayProb}%`,
        tone: todayProb > 60 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "7 दिनों का कुल" : locale === "bn" ? "৭ দিনের মোট" : "7-Day Total",
        value: fmtRain(total7d, units),
        tone: total7d > 50 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `आज कुल अनुमानित वर्षा ${fmtRain(todayMm, units)} और संभावना ${todayProb}% है।`
        : locale === "bn"
        ? `আজকের সম্ভাব্য বৃষ্টি ${fmtRain(todayMm, units)} এবং সম্ভাবনা ${todayProb}%।`
        : `Daily estimated precipitation is ${fmtRain(todayMm, units)} with a ${todayProb}% probability.`,
      locale === "hi"
        ? `आगामी 7 दिनों का संचयी वर्षा अनुमान ${fmtRain(total7d, units)} है।`
        : locale === "bn"
        ? `পরবর্তী ৭ দিনের মোট বৃষ্টিপাতের পূর্বাভাস ${fmtRain(total7d, units)}।`
        : `7-day cumulative rainfall projection stands at ${fmtRain(total7d, units)}.`,
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

  return {
    sectionId: "wind",
    sectionTitle: locale === "hi" ? "हवा की स्थिति" : locale === "bn" ? "বাতাসের অবস্থা" : "Wind Overview",
    headline,
    badge: {
      label: isStorm ? "Gale / Strong" : isBreezy ? "Breezy" : "Gentle",
      tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "सक्रिय गति" : locale === "bn" ? "গতিবেগ" : "Sustained Speed",
        value: fmtSpeed(speedKmh, units),
        tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "अधिकतम झोंका" : locale === "bn" ? "ঝড়ো দমকা" : "Peak Gust",
        value: fmtSpeed(gustKmh, units),
        tone: gustKmh > 40 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "दिशा" : locale === "bn" ? "দিক" : "Direction",
        value: compass,
        tone: "info",
      },
      {
        label: locale === "hi" ? "वर्ग" : locale === "bn" ? "মাত্রা" : "Category",
        value: speedKmh < 12 ? "Light" : speedKmh < 28 ? "Moderate" : speedKmh < 45 ? "Fresh" : "Strong",
        tone: isStorm ? "alert" : isBreezy ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `हवा की मुख्य दिशा ${compass} से ${fmtSpeed(speedKmh, units)} की गति से है।`
        : locale === "bn"
        ? `বাতাসের প্রবাহ ${compass} দিক থেকে ${fmtSpeed(speedKmh, units)} বেগে।`
        : `Dominant wind vector flows from ${compass} at ${fmtSpeed(speedKmh, units)}.`,
      locale === "hi"
        ? `अधिकतम झोंकों की गति ${fmtSpeed(gustKmh, units)} तक दर्ज की गई है।`
        : locale === "bn"
        ? `সর্বোচ্চ দমকা বাতাসের গতি ${fmtSpeed(gustKmh, units)} পর্যন্ত রেকর্ড করা হয়েছে।`
        : `Peak gust velocity is monitored up to ${fmtSpeed(gustKmh, units)}.`,
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

  let headline = "";
  if (locale === "hi") {
    headline = count === 0
      ? "कोई आपातकालीन सरकारी मौसम चेतावनी सक्रिय नहीं है।"
      : hasExtreme
      ? `${count} गंभीर मौसम बुलेटिन सक्रिय हैं।`
      : `${count} मौसम चेतावनी बुलेटिन जारी हैं।`;
  } else if (locale === "bn") {
    headline = count === 0
      ? "কোনো জরুরি সরকারি আবহাওয়া সতর্কতা সক্রিয় নেই।"
      : hasExtreme
      ? `${count}টি জরুরি আবহাওয়া সতর্কতা সক্রিয় রয়েছে।`
      : `${count}টি আবহাওয়া সতর্কতা জারি রয়েছে।`;
  } else {
    headline = count === 0
      ? "No severe weather bulletins active in this jurisdiction."
      : hasExtreme
      ? `${count} emergency weather bulletins currently in effect.`
      : `${count} meteorological advisories currently in effect.`;
  }

  return {
    sectionId: "alerts",
    sectionTitle: locale === "hi" ? "चेतावनी व जोखिम" : locale === "bn" ? "সতর্কতা ও ঝুঁকি" : "Alerts & Risk Overview",
    headline,
    badge: {
      label: count === 0 ? "Normal" : hasExtreme ? "Emergency" : "Advisory",
      tone: hasExtreme ? "alert" : count > 0 ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "सक्रिय बुलेटिन" : locale === "bn" ? "সক্রিয় সতর্কতা" : "Active Bulletins",
        value: count === 0 ? "0 Active" : `${count} Active`,
        tone: hasExtreme ? "alert" : count > 0 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "प्रमुख जोखिम" : locale === "bn" ? "প্রধান ঝুঁকি" : "Dominant Risk",
        value: topRisk?.label || "None",
        tone: (topRisk?.score_pct ?? 0) > 50 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "जोखिम सूचकांक" : locale === "bn" ? "ঝুঁকি সূচক" : "Risk Index",
        value: topRisk?.score_pct != null ? `${topRisk.score_pct}%` : "Low",
        tone: (topRisk?.score_pct ?? 0) > 50 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "निगरानी स्थिति" : locale === "bn" ? "নজরদারি স্থিতি" : "Watch Status",
        value: count > 0 ? "Active Monitor" : "Routine Scan",
        tone: count > 0 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? count === 0 ? "सभी सरकारी निगरानी चैनलों पर स्थिति सामान्य है।" : `${count} आधिकारिक मौसम चेतावनियां प्रभाव में हैं।`
        : locale === "bn"
        ? count === 0 ? "সকল সরকারি নজরদারি চ্যানেলে পরিস্থিতি স্বাভাবিক রয়েছে।" : `${count}টি সরকারি সতর্কতা কার্যকর রয়েছে।`
        : count === 0 ? "Multi-agency hazard scanning indicates normal baseline status." : `${count} official meteorological advisories remain active.`,
      locale === "hi"
        ? topRisk ? `क्षेत्रीय जोखिम सूचकांक में मुख्य प्रभाव '${topRisk.label}' का है।` : "भूकंप, बाढ़ व चक्रवात स्थिति स्थिर है।"
        : locale === "bn"
        ? topRisk ? `আঞ্চলিক ঝুঁকি সূচকে '${topRisk.label}' প্রধান স্থান দখল করেছে।` : "ভূমিকম্প, বন্যা ও ঘূর্ণিঝড় পরিস্থিতি স্বাভাবিক।"
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
  const aqiVal = Number(cpcb.value ?? dash.descriptive.current.aqi ?? air.us_aqi ?? 65);
  const pm25 = air.pm2_5 != null ? Number(air.pm2_5) : null;
  const pm10 = air.pm10 != null ? Number(air.pm10) : null;

  const isSevere = aqiVal > 250;
  const isPoor = aqiVal > 150;
  const isModerate = aqiVal > 80;

  let aqiLabel = "Good";
  if (isSevere) aqiLabel = "Severe";
  else if (isPoor) aqiLabel = "Poor";
  else if (isModerate) aqiLabel = "Moderate";

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

  return {
    sectionId: "air",
    sectionTitle: locale === "hi" ? "वायु गुणवत्ता" : locale === "bn" ? "বাতাসের মান" : "Air Quality Overview",
    headline,
    badge: {
      label: aqiLabel,
      tone: isSevere ? "alert" : isPoor ? "alert" : isModerate ? "watch" : "ok",
    },
    metrics: [
      {
        label: "AQI Index",
        value: `${aqiVal}`,
        tone: isPoor ? "alert" : isModerate ? "watch" : "ok",
      },
      {
        label: "Category",
        value: aqiLabel,
        tone: isPoor ? "alert" : isModerate ? "watch" : "ok",
      },
      {
        label: "PM2.5",
        value: pm25 != null ? `${Math.round(pm25)} µg/m³` : "Nominal",
        tone: pm25 != null && pm25 > 60 ? "watch" : "ok",
      },
      {
        label: "PM10",
        value: pm10 != null ? `${Math.round(pm10)} µg/m³` : "Nominal",
        tone: pm10 != null && pm10 > 100 ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `वर्तमान वायु सूचकांक ${aqiVal} (${aqiLabel}) दर्ज है।`
        : locale === "bn"
        ? `বর্তমান এয়ার কোয়ালিটি ইনডেক্স ${aqiVal} (${aqiLabel})।`
        : `Current air quality index reads ${aqiVal} under the ${aqiLabel} category.`,
      locale === "hi"
        ? pm25 != null ? `प्रमुख प्रदूषक कण PM2.5 की सांद्रता ${Math.round(pm25)} µg/m³ है।` : "गैस व परागकण सामान्य सीमा में हैं।"
        : locale === "bn"
        ? pm25 != null ? `প্রধান দূষক PM2.5 এর ঘনত্ব ${Math.round(pm25)} µg/m³।` : "গ্যাস ও পরাগরেণু স্বাভাবিক মাত্রায়।"
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

  return {
    sectionId: "soil",
    sectionTitle: locale === "hi" ? "भूमि व मिट्टी" : locale === "bn" ? "মাটি ও আর্দ্রতা" : "Soil & Moisture Overview",
    headline,
    badge: {
      label: isDry ? "Dry" : isWet ? "High Moisture" : "Balanced",
      tone: isDry ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "ऊपरी नमी" : locale === "bn" ? "উপরের আর্দ্রতা" : "Topsoil (0–1cm)",
        value: `${topsoil.toFixed(2)} m³/m³`,
        tone: isDry ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "वाष्पीकरण ET₀" : locale === "bn" ? "বাষ্পীভবন ET₀" : "Evaporation ET₀",
        value: et0 != null ? `${et0} mm` : "Normal",
        tone: "info",
      },
      {
        label: "VPD Deficit",
        value: vpd != null ? `${vpd} kPa` : "Normal",
        tone: "info",
      },
      {
        label: locale === "hi" ? "स्थिति" : locale === "bn" ? "স্থিতি" : "Condition",
        value: isDry ? "Depleted" : isWet ? "Saturated" : "Adequate",
        tone: isDry ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `ऊपरी मिट्टी में नमी की मात्रा ${topsoil.toFixed(3)} m³/m³ मापी गई है।`
        : locale === "bn"
        ? `মাটির উপরিভাগের আর্দ্রতা ${topsoil.toFixed(3)} m³/m³ রেকর্ড করা হয়েছে।`
        : `Topsoil moisture layer is recorded at ${topsoil.toFixed(3)} m³/m³.`,
      locale === "hi"
        ? et0 != null ? `दैनिक वाष्पीकरण दर लगभग ${et0} mm है।` : "भूमि वाष्पीकरण दर स्थिर है।"
        : locale === "bn"
        ? et0 != null ? `দৈনিক বাষ্পীভবন হার প্রায় ${et0} mm।` : "মাটির বাষ্পীভবন স্বাভাবিক রয়েছে।"
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

  return {
    sectionId: "marine",
    sectionTitle: locale === "hi" ? "समुद्री मौसम" : locale === "bn" ? "সামুদ্রিক অবস্থা" : "Marine Overview",
    headline,
    badge: {
      label: waveM == null ? "Inland" : isRough ? "Rough" : isModerate ? "Moderate" : "Calm",
      tone: isRough ? "alert" : isModerate ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "लहरों की ऊंचाई" : locale === "bn" ? "ঢেউয়ের উচ্চতা" : "Significant Wave",
        value: waveM != null ? `${waveM.toFixed(2)} m` : "Inland",
        tone: isRough ? "alert" : isModerate ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "लहर अवधि" : locale === "bn" ? "তরঙ্গ কাল" : "Wave Period",
        value: period != null ? `${period} s` : "Normal",
        tone: "info",
      },
      {
        label: "Sea Temp (SST)",
        value: sstC != null ? `${Math.round(sstC)}°C` : "—",
        tone: "info",
      },
      {
        label: locale === "hi" ? "समुद्री स्थिति" : locale === "bn" ? "সমুদ্রের স্থিতি" : "Sea State",
        value: waveM == null ? "Inland" : isRough ? "Rough" : isModerate ? "Moderate" : "Smooth",
        tone: isRough ? "alert" : isModerate ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? waveM != null ? `सार्थक तरंग ऊंचाई ${waveM.toFixed(1)} मीटर मापी गई है।` : "क्षेत्रीय जलस्तर और नदियां सामान्य प्रवाह में हैं।"
        : locale === "bn"
        ? waveM != null ? `তরঙ্গ উচ্চতা ${waveM.toFixed(1)} মিটার রেকর্ড হয়েছে।` : "আঞ্চলিক নদী ও জলাশয়ের প্রবাহ স্বাভাবিক।"
        : waveM != null ? `Significant wave height measures at ${waveM.toFixed(1)} meters.` : "Regional hydrological flow and rivers remain at normal baseline.",
      locale === "hi"
        ? sstC != null ? `समुद्र सतह का तापमान ${Math.round(sstC)}°C है।` : "तटीय ज्वार-भाटा सामान्य स्थिति में है।"
        : locale === "bn"
        ? sstC != null ? `সমুদ্রপৃষ্ঠের তাপমাত্রা ${Math.round(sstC)}°C।` : "উপকূলীয় জোয়ার-ভাটা স্বাভাবিক সীমার মধ্যে।"
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

  return {
    sectionId: "forecast7d",
    sectionTitle: locale === "hi" ? "7 दिनों का पूर्वानुमान" : locale === "bn" ? "৭ দিনের পূর্বাভাস" : "7-Day Outlook Overview",
    headline,
    badge: {
      label: isRainyWeek ? "Showers Expected" : totalRain > 5 ? "Variable" : "Predominantly Dry",
      tone: isRainyWeek ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "7 दिनों की बारिश" : locale === "bn" ? "৭ দিনের মোট বৃষ্টি" : "7-Day Precip",
        value: `${totalRain.toFixed(1)} mm`,
        tone: totalRain > 25 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "तापमान सीमा" : locale === "bn" ? "তাপমাত্রা পরিসীমা" : "Temp Range",
        value: `${Math.round(minTemp)}° – ${Math.round(maxTemp)}°C`,
        tone: "ok",
      },
      {
        label: locale === "hi" ? "सर्वाधिक बारिश का दिन" : locale === "bn" ? "সর্বোচ্চ বৃষ্টির দিন" : "Peak Rain Day",
        value: (maxDay.precip_mm || 0) > 0 ? `${maxDay.date.slice(5)} (${(maxDay.precip_mm || 0).toFixed(1)} mm)` : "None",
        tone: (maxDay.precip_mm || 0) > 10 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "सप्ताह का रुझान" : locale === "bn" ? "সাপ্তাহিক প্রবণতা" : "Weekly Trend",
        value: isRainyWeek ? "Wet" : totalRain > 5 ? "Normal" : "Dry",
        tone: isRainyWeek ? "watch" : "ok",
      },
    ],
    points: [
      locale === "hi"
        ? `सप्ताह में कुल अनुमानित वर्षा ${totalRain.toFixed(1)} mm और तापमान ${Math.round(minTemp)}°C से ${Math.round(maxTemp)}°C रहेगा।`
        : locale === "bn"
        ? `সপ্তাহে মোট বৃষ্টিপাত ${totalRain.toFixed(1)} mm এবং তাপমাত্রা ${Math.round(minTemp)}°C থেকে ${Math.round(maxTemp)}°C।`
        : `7-day cumulative precipitation is ${totalRain.toFixed(1)} mm with temperatures between ${Math.round(minTemp)}°C and ${Math.round(maxTemp)}°C.`,
      locale === "hi"
        ? (maxDay.precip_mm || 0) > 1
          ? `सप्ताह में सबसे अधिक वर्षा ${maxDay.date.slice(5)} को दर्ज होने का अनुमान है।`
          : "अधिकांश दिनों में वर्षा की संभावना 20% से कम है।"
        : locale === "bn"
        ? (maxDay.precip_mm || 0) > 1
          ? `সপ্তাহের সর্বোচ্চ বৃষ্টি ${maxDay.date.slice(5)} তারিখে প্রত্যাশিত।`
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

  let headline = "";
  if (locale === "hi") {
    headline = isRainy
      ? `अगले 6 घंटों में लगभग ${totalRain6h.toFixed(1)} मिमी बारिश का अनुमान है।`
      : "अगले 6 घंटों में मौसम शुष्क और स्थिर रहने की संभावना है।";
  } else if (locale === "bn") {
    headline = isRainy
      ? `পরবর্তী ৬ ঘণ্টায় প্রায় ${totalRain6h.toFixed(1)} মিমি বৃষ্টির সম্ভাবনা রয়েছে।`
      : "পরবর্তী ৬ ঘণ্টায় আবহাওয়া শুষ্ক ও স্থিতিশীল থাকবে।";
  } else {
    headline = isRainy
      ? `Approximately ${totalRain6h.toFixed(1)} mm of rain expected across the next 6 hours.`
      : "Stable conditions with dry weather expected across the next 6 hours.";
  }

  return {
    sectionId: "nowcast",
    sectionTitle: locale === "hi" ? "अगले 6 घंटे" : locale === "bn" ? "পরবর্তী ৬ ঘণ্টা" : "Next 6 Hours",
    headline,
    badge: {
      label: isRainy ? "Showers Ahead" : "Dry Window",
      tone: isRainy ? "watch" : "ok",
    },
    metrics: [
      {
        label: locale === "hi" ? "6 घंटे बारिश" : locale === "bn" ? "৬ ঘণ্টার বৃষ্টি" : "6h Rain",
        value: totalRain6h > 0 ? `${totalRain6h.toFixed(1)} mm` : "0 mm",
        tone: isRainy ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "तापमान दायरा" : locale === "bn" ? "তাপমাত্রা পরিসীমা" : "Temp Span",
        value: `${Math.round(minTemp)}° – ${Math.round(maxTemp)}°C`,
        tone: "ok",
      },
      {
        label: locale === "hi" ? "अधिकतम हवा" : locale === "bn" ? "সর্বোচ্চ বাতাস" : "Peak Wind",
        value: `${Math.round(maxWind)} km/h`,
        tone: maxWind > 35 ? "watch" : "ok",
      },
      {
        label: locale === "hi" ? "अनुमानित खिड़की" : locale === "bn" ? "পূর্বাভাস উইন্ডো" : "Nowcast Span",
        value: "0 – 6 Hours",
        tone: "info",
      },
    ],
    points: [
      locale === "hi"
        ? `तापमान ${Math.round(minTemp)}°C से ${Math.round(maxTemp)}°C के बीच रहेगा।`
        : locale === "bn"
        ? `তাপমাত্রা ${Math.round(minTemp)}°C থেকে ${Math.round(maxTemp)}°C-এর মধ্যে থাকবে।`
        : `Surface temperatures will track between ${Math.round(minTemp)}°C and ${Math.round(maxTemp)}°C.`,
      locale === "hi"
        ? isRainy ? "अगले कुछ घंटों में हल्की बारिश देखने को मिल सकती है।" : "निकट भविष्य में बारिश का कोई संकेत नहीं है।"
        : locale === "bn"
        ? isRainy ? "পরবর্তী কয়েক ঘণ্টায় হালকা বৃষ্টি হতে পারে।" : "নিকটবর্তী সময়ে বৃষ্টির কোনো সম্ভাবনা নেই।"
        : isRainy ? "Intermittent showers possible during the upcoming forecast window." : "Precipitation indices remain suppressed for this window.",
    ],
  };
}
