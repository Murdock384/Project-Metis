import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CalendarScreen } from "./src/screens/CalendarScreen";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CalendarScreen />
      <StatusBar style="auto" />
    </QueryClientProvider>
  );
}
