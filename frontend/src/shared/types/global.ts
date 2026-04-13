export type AppError = {
  message: string;
  code?: string;
  details?: unknown;
};

export type ApiResponse<TData> = {
  data: TData;
};

export type Nullable<T> = T | null;
