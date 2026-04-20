import { z } from 'zod';

import { apiClient } from './api-client';

export const medicineBatchQrSchema = z.object({
  batch_id: z.string().trim().min(1),
  batch_code: z.string().nullable().optional(),
  token: z.string().trim().min(1),
  public_url: z.string().trim().min(1),
  token_expires_at: z.string().nullable().optional(),
  generated_at: z.string().nullable().optional(),
  image_data_url: z.string().trim().min(1),
});

export const medicineBatchAttachmentSchema = z.object({
  batch_id: z.string().trim().min(1),
  filename: z.string().nullable().optional(),
  content_type: z.string().nullable().optional(),
  size_bytes: z.union([z.number(), z.string()]).nullable().optional(),
  storage_backend: z.string().trim().min(1),
});

export const publicMedicineBatchSchema = z.object({
  id: z.string().trim().min(1),
  batch_code: z.string().nullable().optional(),
  barcode: z.string().nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  arrived_on: z.string().nullable().optional(),
  received_quantity: z.union([z.string(), z.number()]).nullable().optional(),
  remaining_quantity: z.union([z.string(), z.number()]).nullable().optional(),
  unit: z.string().nullable().optional(),
  unit_cost: z.union([z.string(), z.number()]).nullable().optional(),
  currency: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
  token_expires_at: z.string().nullable().optional(),
  medicine_type: z.object({
    id: z.string().trim().min(1),
    name: z.string().nullable().optional(),
    code: z.string().nullable().optional(),
    description: z.string().nullable().optional(),
  }),
  department: z.object({
    id: z.string().trim().min(1),
    name: z.string().nullable().optional(),
    code: z.string().nullable().optional(),
  }),
  organization: z.object({
    id: z.string().trim().min(1),
    name: z.string().nullable().optional(),
    legal_name: z.string().nullable().optional(),
  }),
  supplier: z.object({
    id: z.string().nullable().optional(),
    name: z.string().nullable().optional(),
    email: z.string().nullable().optional(),
    phone: z.string().nullable().optional(),
  }),
  attachment: z
    .object({
      name: z.string().nullable().optional(),
      content_type: z.string().nullable().optional(),
      size_bytes: z.union([z.string(), z.number()]).nullable().optional(),
      url: z.string().trim().min(1),
    })
    .nullable()
    .optional(),
});

export type MedicineBatchQr = z.infer<typeof medicineBatchQrSchema>;
export type MedicineBatchAttachment = z.infer<typeof medicineBatchAttachmentSchema>;
export type PublicMedicineBatch = z.infer<typeof publicMedicineBatchSchema>;

export const generateMedicineBatchQr = (batchId: string) =>
  apiClient.post<MedicineBatchQr, Record<string, never>>(
    `/medicine/batches/${batchId}/qr`,
    {},
    medicineBatchQrSchema,
  );

export const getMedicineBatchQr = (batchId: string) =>
  apiClient.get<MedicineBatchQr>(`/medicine/batches/${batchId}/qr`, medicineBatchQrSchema);

export const uploadMedicineBatchAttachment = (batchId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<MedicineBatchAttachment, FormData>(
    `/medicine/batches/${batchId}/attachment`,
    formData,
    medicineBatchAttachmentSchema,
  );
};

export const getPublicMedicineBatch = (token: string) =>
  apiClient.get<PublicMedicineBatch>(
    `/medicine/public/batches/${token}`,
    publicMedicineBatchSchema,
    {
      skipAuth: true,
    },
  );

export const medicineConsumeRequestSchema = z.object({
  medicine_type_id: z.string().trim().min(1),
  quantity: z.union([z.number(), z.string()]),
  consumed_on: z.string().trim().min(1),
  unit: z.string().trim().min(1).optional(),
  department_id: z.string().trim().min(1).optional(),
  purpose: z.string().trim().optional(),
  poultry_type_id: z.string().trim().min(1).optional(),
  client_id: z.string().trim().min(1).optional(),
  factory_flock_id: z.string().trim().min(1).optional(),
});

const medicineConsumeAllocationSchema = z.object({
  batch_id: z.string(),
  batch_code: z.string().nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  quantity: z.union([z.number(), z.string()]),
  consumption_id: z.string(),
});

export const medicineConsumeResponseSchema = z.object({
  requested: z.union([z.number(), z.string()]),
  consumed_total: z.union([z.number(), z.string()]),
  allocations: z.array(medicineConsumeAllocationSchema),
});

export type MedicineConsumeRequest = z.infer<typeof medicineConsumeRequestSchema>;
export type MedicineConsumeAllocation = z.infer<typeof medicineConsumeAllocationSchema>;
export type MedicineConsumeResponse = z.infer<typeof medicineConsumeResponseSchema>;

export const consumeMedicine = (payload: MedicineConsumeRequest) =>
  apiClient.post<MedicineConsumeResponse, MedicineConsumeRequest>(
    `/medicine/consume`,
    payload,
    medicineConsumeResponseSchema,
  );
