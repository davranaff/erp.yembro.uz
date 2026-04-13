export const noop = () => undefined;

export const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const isNonNullish = <T>(value: T | null | undefined): value is T =>
  value !== null && value !== undefined;
