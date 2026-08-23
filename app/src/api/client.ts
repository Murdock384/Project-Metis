import axios from "axios";
import { Platform } from "react-native";

// Phase 0 dev config only (no auth yet - single dev user on the backend).
// - Android emulator reaches the host machine via 10.0.2.2.
// - iOS simulator / web can use localhost.
// - A physical device (Expo Go) needs your computer's LAN IP instead,
//   e.g. "192.168.1.23" - update HOST below if testing on a real device.
const HOST = Platform.OS === "android" ? "10.0.2.2" : "localhost";
const BASE_URL = `http://${HOST}:8000/api/v1`;

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});
