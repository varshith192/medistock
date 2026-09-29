import "@fontsource-variable/inter";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import AgentDecisions from "./pages/AgentDecisions";
import DecisionHistory from "./pages/DecisionHistory";
import Demo from "./pages/Demo";
import Incidents from "./pages/Incidents";
import Inventory from "./pages/Inventory";
import Memory from "./pages/Memory";
import NotFound from "./pages/NotFound";
import Overview from "./pages/Overview";
import SettingsPage from "./pages/Settings";
import Suppliers from "./pages/Suppliers";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5000 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="agent" element={<AgentDecisions />} />
            <Route path="memory" element={<Memory />} />
            <Route path="suppliers" element={<Suppliers />} />
            <Route path="incidents" element={<Incidents />} />
            <Route path="decisions" element={<DecisionHistory />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="demo" element={<Demo />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" toastOptions={{ style: { fontSize: 13 } }} />
    </QueryClientProvider>
  </StrictMode>,
);
