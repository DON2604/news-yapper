import { CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";

export default function NotFound() {
  return (
    <EmptyState
      title="Ei scene-ta khuje pelam na 🤷"
      mood="oops"
      className="mx-auto mt-10 max-w-xl"
      action={
        <CandyLink href="/" tone="mango">
          Back to today&apos;s edition
        </CandyLink>
      }
    >
      The page moved, was removed, or never existed. Today&apos;s cha is still hot though.
    </EmptyState>
  );
}
