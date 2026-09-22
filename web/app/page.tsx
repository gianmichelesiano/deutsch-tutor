"use client";

import { useEffect, useState } from "react";
import { Shell, type Screen } from "@/components/Shell";
import { HomeScreen } from "@/components/screens/Home";
import { ProgressScreen } from "@/components/screens/Progress";
import { VocabScreen } from "@/components/screens/Vocab";
import { LessonScreen } from "@/components/screens/Lesson";
import { api, type HomeData, type PathScenario, type ProgressData } from "@/lib/api";
import { ErrorBanner, LoadingDots } from "@/components/ui";

export default function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [startScenario, setStartScenario] = useState<PathScenario | undefined>(undefined);

  return (
    <Shell screen={screen} onNavigate={(s) => setScreen(s)}>
      {screen === "home" && <HomeRoute onStart={() => setScreen("lesson")} />}
      {screen === "lesson" && (
        <LessonScreen
          onExit={() => setScreen("home")}
          startScenario={startScenario}
          onConsumeStart={() => setStartScenario(undefined)}
        />
      )}
      {screen === "vocab" && <VocabScreen />}
      {screen === "progress" && (
        <ProgressRoute
          onSelectScenario={(scenario) => {
            setStartScenario(scenario);
            setScreen("lesson");
          }}
        />
      )}
    </Shell>
  );
}

function HomeRoute({ onStart }: { onStart: () => void }) {
  const [data, setData] = useState<HomeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setError(null);
    api.home().then(setData).catch((e) => setError(String(e.message)));
  };
  useEffect(load, []);
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (data === null) return <LoadingDots />;
  return <HomeScreen data={data} onStart={onStart} />;
}

function ProgressRoute({ onSelectScenario }: { onSelectScenario: (scenario: PathScenario) => void }) {
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setError(null);
    api.progress().then(setData).catch((e) => setError(String(e.message)));
  };
  useEffect(load, []);
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (data === null) return <LoadingDots />;
  return <ProgressScreen data={data} onSelectScenario={onSelectScenario} />;
}
