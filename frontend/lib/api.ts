export const API_BASE_URL = resolveApiBaseUrl();

export type LeadMessage = {
  id: number;
  channel?: string;
  subject: string;
  body: string;
  status: string;
  direction: string;
  sent_at: string;
};

export type LeadCall = {
  id: number;
  call_sid?: string;
  status: string;
  script: string;
  call_mode?: string;
  questionnaire_answers?: string | Array<Record<string, unknown>>;
  duration?: number;
  recording_sid?: string;
  recording_url?: string;
  recording_status?: string;
  recording_duration?: number;
  recording_available_at?: string;
  transcript_text?: string;
  transcript_status?: string;
  transcript_summary?: string;
  transcript_analysis?: string | Record<string, unknown>;
  transcript_next_action?: string;
  transcript_error?: string;
  transcript_model?: string;
  transcript_cost?: number;
  transcribed_at?: string;
  called_at?: string;
  agent_name?: string;
  error_message?: string;
};

export type Lead = {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  source?: string | null;
  property_type?: string | null;
  configuration?: string | null;
  location_preference?: string | null;
  budget?: string | null;
  timeline?: string | null;
  message?: string | null;
  score?: number | null;
  score_band?: string | null;
  validation_status?: string | null;
  validation_remarks?: string | null;
  enrichment_status?: string | null;
  enrichment_provider?: string | null;
  enrichment_confidence?: number | null;
  enrichment_score_delta?: number | null;
  enrichment_summary?: string | null;
  enrichment_data?: string | Record<string, unknown> | null;
  enrichment_full_name?: string | null;
  enrichment_company?: string | null;
  enrichment_title?: string | null;
  enrichment_location?: string | null;
  enrichment_profiles?: string | string[] | null;
  enriched_at?: string | null;
  duplicate_of?: number | null;
  assigned_agent_name?: string | null;
  assigned_agent_email?: string | null;
  assigned_agent_email_provider?: string | null;
  email_draft_subject?: string | null;
  email_draft_body?: string | null;
  email_sent_status?: string | null;
  email_status?: string | null;
  phone_status?: string | null;
  automation_status?: string | null;
  followup_step?: number | null;
  next_followup_at?: string | null;
  do_not_call?: boolean | number | null;
  call_consent?: boolean | number | null;
  call_eligibility?: Record<string, unknown> | null;
  messages?: LeadMessage[];
  calls?: LeadCall[];
  [key: string]: unknown;
};

type RequestOptions = {
  body?: BodyInit | object | null;
  headers?: HeadersInit;
  method?: string;
};

export async function apiGet<T>(path: string) {
  return request<T>(path, { method: "GET" });
}

export async function apiPost<T>(path: string, body?: BodyInit | object) {
  return request<T>(path, { method: "POST", body });
}

export async function apiPatch<T>(path: string, body?: BodyInit | object) {
  return request<T>(path, { method: "PATCH", body });
}

export async function apiDelete<T>(path: string, body?: BodyInit | object) {
  return request<T>(path, { method: "DELETE", body });
}

async function request<T>(path: string, options: RequestOptions): Promise<T> {
  const url = buildUrl(path);
  const headers = new Headers(options.headers ?? {});
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers,
    cache: "no-store",
  };

  if (options.body !== undefined && options.body !== null) {
    if (isBodyInit(options.body)) {
      init.body = options.body;
    } else {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function buildUrl(path: string) {
  const normalizedPath = path ? (path.startsWith("/") ? path : `/${path}`) : "";
  return `${API_BASE_URL}${normalizedPath}`;
}

function resolveApiBaseUrl() {
  const explicit = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (explicit) {
    return `${explicit.replace(/\/$/, "")}/api/v1/leads`.replace(/\/api\/v1\/leads\/api\/v1\/leads$/, "/api/v1/leads");
  }

  if (typeof window !== "undefined") {
    return "/api/v1/leads";
  }

  const productionUrl = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (productionUrl) {
    return `https://${productionUrl}/api/v1/leads`;
  }

  const vercelUrl = process.env.VERCEL_URL?.trim();
  if (vercelUrl) {
    return `https://${vercelUrl}/api/v1/leads`;
  }

  return "http://127.0.0.1:8000/api/v1/leads";
}

function isBodyInit(value: BodyInit | object): value is BodyInit {
  return (
    value instanceof FormData ||
    value instanceof URLSearchParams ||
    value instanceof Blob ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value) ||
    typeof value === "string"
  );
}

async function readErrorMessage(response: Response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      return data.detail;
    }
    if (typeof data?.message === "string") {
      return data.message;
    }
  } catch {
    // Fall through to status text when the response is not JSON.
  }

  return `Request failed: ${response.status} ${response.statusText}`.trim();
}
