/**
 * Application-form answers the pipeline does not model (applicant name, bank details, Udyam registration).
 * Stored in the case state (cleared by reset), only in masked form for phone / account / Aadhaar, after
 * `validateField` accepted them. The name falls back to what the user told the assistant.
 */
import { useCallback, useMemo } from "react";
import { useStore } from "../../state/store";

export interface Applicant {
  fullName?: string;
  phoneMasked?: string;
  ifsc?: string;
  accountMasked?: string;
  pincode?: string;
  enterpriseName?: string;
  aadhaarLast4?: string;
  udyamNumber?: string;
}

export function useApplicant(): [Applicant, (patch: Partial<Applicant>) => void] {
  const { state, set } = useStore();
  const chatName = useMemo(() => {
    const m = [...state.chat].reverse().find((x) => x.from === "user" && x.vars?.answered === "name" && x.vars?.name);
    return m ? String(m.vars!.name) : undefined;
  }, [state.chat]);
  const data = useMemo<Applicant>(() => ({ fullName: chatName, ...(state.applicant as Applicant) }), [state.applicant, chatName]);
  const update = useCallback((patch: Partial<Applicant>) => {
    const clean = Object.fromEntries(Object.entries(patch).filter(([, v]) => v !== undefined)) as Record<string, string>;
    set({ applicant: { ...state.applicant, ...clean } });
  }, [set, state.applicant]);
  return [data, update];
}

export const maskPhone = (digits: string) => `${digits.slice(0, 2)}${"•".repeat(Math.max(0, digits.length - 4))}${digits.slice(-2)}`;