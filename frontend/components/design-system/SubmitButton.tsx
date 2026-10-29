"use client";

import { useFormStatus } from "react-dom";
import { CandyButton, type CandyButtonProps } from "@/components/design-system/CandyButton";

/** Submit button for server-action forms: spins while the form's action is running. */
export function SubmitButton(props: Omit<CandyButtonProps, "type" | "loading">) {
  const { pending } = useFormStatus();
  return <CandyButton type="submit" loading={pending} {...props} />;
}
