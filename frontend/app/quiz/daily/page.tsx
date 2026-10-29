import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { DailyQuiz } from "@/components/quiz/DailyQuiz";
import type { DailyQuiz as DailyQuizData } from "@/lib/api-types";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Daily quiz" };

export default async function DailyQuizPage() {
  const user = await requireUser("/quiz/daily");
  const data = await backendOrNull<DailyQuizData>("/quizzes/daily", { userId: user.id });
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle as="h1" kicker="Dopamine, but make it useful" title="Daily quiz" />
      {data ? (
        <DailyQuiz initial={data} />
      ) : (
        <EmptyState title="Quiz load hocchhe na" mood="oops">
          The API isn&apos;t reachable right now.
        </EmptyState>
      )}
    </div>
  );
}
