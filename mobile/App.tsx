import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import MapView, { Marker } from "react-native-maps";
import * as Location from "expo-location";
import { api, apiBase } from "./src/api";

type Place = { id?: string; label?: string; district?: string; lat: number; lon: number; state?: string };

export default function App() {
  const [health, setHealth] = useState<string>("…");
  const [q, setQ] = useState("Haldia");
  const [loc, setLoc] = useState<Place | null>(null);
  const [dash, setDash] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [ask, setAsk] = useState("Should I irrigate today?");
  const [reply, setReply] = useState("");
  const [streaming, setStreaming] = useState(false);

  useEffect(() => {
    void api
      .health()
      .then((h) => setHealth(h.ok ? `API ${h.version || "ok"} @ ${apiBase()}` : "API not ok"))
      .catch((e) => setHealth(`API unreachable: ${String(e)}`));
  }, []);

  const loadDash = useCallback(async (place: Place) => {
    setBusy(true);
    try {
      const data = await api.dashboard(place);
      setDash(data);
    } catch (e) {
      Alert.alert("Dashboard", String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  async function search() {
    setBusy(true);
    try {
      const hits = await api.searchPlaces(q);
      const first = hits[0];
      if (!first) {
        Alert.alert("Search", "No India place matched.");
        return;
      }
      const place: Place = {
        id: first.id,
        label: first.label,
        district: first.district,
        lat: first.lat,
        lon: first.lon,
        state: first.state,
      };
      setLoc(place);
      await loadDash(place);
    } catch (e) {
      Alert.alert("Search", String(e));
    } finally {
      setBusy(false);
    }
  }

  async function useGps() {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== "granted") {
      Alert.alert("Location", "Permission denied. Search a district instead.");
      return;
    }
    const pos = await Location.getCurrentPositionAsync({});
    try {
      const rev = await api.reverseGeocode(pos.coords.latitude, pos.coords.longitude);
      const place: Place = {
        id: rev.id,
        label: rev.label,
        district: rev.district,
        lat: rev.lat,
        lon: rev.lon,
        state: rev.state,
      };
      setLoc(place);
      await loadDash(place);
    } catch (e) {
      Alert.alert("GPS", String(e));
    }
  }

  async function sendChat() {
    if (!ask.trim()) return;
    setStreaming(true);
    setReply("");
    try {
      await api.streamChat(
        {
          message: ask.trim(),
          locale_hint: "en",
          output_locale: "en",
          location: loc
            ? {
                id: loc.id || loc.district || "pin",
                label: loc.label || loc.district || "pin",
                state: loc.state || "",
                district: loc.district || "",
                lat: loc.lat,
                lon: loc.lon,
                place_name: loc.label,
              }
            : undefined,
        },
        (ev) => {
          if (ev.type === "token" && typeof ev.text === "string") {
            setReply((prev) => prev + ev.text);
          }
          if (ev.type === "final" && ev.message && typeof ev.message === "object") {
            const m = ev.message as { content?: string };
            if (m.content) setReply(m.content);
          }
        },
      );
    } catch (e) {
      setReply(String(e));
    } finally {
      setStreaming(false);
    }
  }

  const live = (dash?.live as { sky?: string } | undefined) || {};
  const pred = (dash?.predictive as { precip_next_3d_mm?: number } | undefined) || {};
  const locLabel = loc?.label || (dash?.location as { label?: string } | undefined)?.label;

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <StatusBar style="light" />
      <Text style={styles.brand}>Rituchakra</Text>
      <Text style={styles.muted}>{health}</Text>

      <View style={styles.row}>
        <TextInput style={styles.input} value={q} onChangeText={setQ} placeholder="District or town in India" />
        <Pressable style={styles.btn} onPress={() => void search()}>
          <Text style={styles.btnText}>Search</Text>
        </Pressable>
      </View>
      <Pressable style={styles.btnGhost} onPress={() => void useGps()}>
        <Text style={styles.btnGhostText}>Use GPS</Text>
      </Pressable>

      {loc ? (
        <View style={styles.mapWrap}>
          <MapView
            style={styles.map}
            initialRegion={{
              latitude: loc.lat,
              longitude: loc.lon,
              latitudeDelta: 1.2,
              longitudeDelta: 1.2,
            }}
            region={{
              latitude: loc.lat,
              longitude: loc.lon,
              latitudeDelta: 1.2,
              longitudeDelta: 1.2,
            }}
          >
            <Marker coordinate={{ latitude: loc.lat, longitude: loc.lon }} title={loc.label} />
          </MapView>
        </View>
      ) : null}

      {busy ? <ActivityIndicator color="#0d6e63" /> : null}
      {locLabel ? <Text style={styles.h}>{locLabel}</Text> : null}
      {live.sky ? <Text style={styles.body}>Sky: {live.sky}</Text> : null}
      {pred.precip_next_3d_mm != null ? (
        <Text style={styles.body}>Rain next 3 days: {pred.precip_next_3d_mm} mm</Text>
      ) : null}

      <Text style={styles.h}>Advisor</Text>
      <TextInput style={styles.input} value={ask} onChangeText={setAsk} multiline />
      <Pressable style={styles.btn} onPress={() => void sendChat()} disabled={streaming}>
        <Text style={styles.btnText}>{streaming ? "…" : "Ask"}</Text>
      </Pressable>
      {reply ? <Text style={styles.reply}>{reply}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 20, paddingTop: 56, backgroundColor: "#f4efe4", minHeight: "100%", gap: 10 },
  brand: { fontSize: 28, fontWeight: "800", color: "#0d6e63" },
  muted: { color: "#5c6570", fontSize: 12 },
  row: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: {
    flex: 1,
    backgroundColor: "#fffaf2",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "#ead9c2",
  },
  btn: { backgroundColor: "#0d6e63", borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10 },
  btnText: { color: "#fff", fontWeight: "700" },
  btnGhost: { alignSelf: "flex-start", paddingVertical: 6 },
  btnGhostText: { color: "#0d6e63", fontWeight: "700" },
  mapWrap: { height: 220, borderRadius: 16, overflow: "hidden" },
  map: { flex: 1 },
  h: { fontSize: 18, fontWeight: "700", marginTop: 8 },
  body: { fontSize: 15, color: "#1c2430" },
  reply: { fontSize: 15, lineHeight: 22, backgroundColor: "#fffaf2", padding: 12, borderRadius: 12 },
});
