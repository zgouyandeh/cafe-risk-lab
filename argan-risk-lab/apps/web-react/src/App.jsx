import { ThemeProvider } from "./lib/theme.jsx";
import { Router, useRoute } from "./lib/router.jsx";
import Shell from "./components/Shell.jsx";
import Landing from "./pages/Landing.jsx";
import Simple from "./pages/Simple.jsx";
import Expert from "./pages/Expert.jsx";
import Data from "./pages/Data.jsx";
import { CompanyProvider } from "./lib/company.jsx";
import { StaticProvider } from "./lib/static.jsx";

function Routes() {
  const { path } = useRoute();
  if (path.startsWith("/data")) return <Shell subtitle="داده‌ی شرکت و برآورد پارامترها"><Data /></Shell>;
  if (path.startsWith("/expert")) return <Shell subtitle="نسخه‌ی متخصص (ریاضی)"><Expert /></Shell>;
  if (path.startsWith("/app")) return <Shell subtitle="مشاور خرید قهوه"><Simple /></Shell>;
  return <Shell><Landing /></Shell>;
}
export default function App() {
  return <ThemeProvider><Router><StaticProvider><CompanyProvider><Routes /></CompanyProvider></StaticProvider></Router></ThemeProvider>;
}
