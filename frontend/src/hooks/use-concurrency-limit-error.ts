import { AxiosError } from "axios";

interface ConcurrencyLimitErrorDetail {
  error: "CONCURRENCY_LIMIT_REACHED";
  message: string;
  limit: number;
  current: number;
}

export function isConcurrencyLimitError(
  error: unknown,
): error is AxiosError<ConcurrencyLimitErrorDetail> {
  if (!(error instanceof AxiosError)) return false;
  if (error.response?.status !== 429) return false;
  return error.response?.data?.error === "CONCURRENCY_LIMIT_REACHED";
}

export function getConcurrencyLimit(
  error: AxiosError<ConcurrencyLimitErrorDetail>,
): number {
  return error.response?.data?.limit ?? 3;
}
