"use client";

import LocalPhoneOutlinedIcon from "@mui/icons-material/LocalPhoneOutlined";
import PlayCircleOutlineOutlinedIcon from "@mui/icons-material/PlayCircleOutlineOutlined";
import TextSnippetOutlinedIcon from "@mui/icons-material/TextSnippetOutlined";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Alert, Box, Button, Chip, LinearProgress, Stack, Typography } from "@mui/material";
import { EmptyState, PanelCard } from "../../ui";

export type CallLog = {
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

export default function CallHistory({ calls }: { calls: CallLog[] }) {
  const router = useRouter();
  const [loadingCallId, setLoadingCallId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function transcribe(callId: number) {
    setLoadingCallId(callId);
    setError("");
    try {
      await apiPost<CallLog>(`/calls/${callId}/transcribe`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not transcribe recording");
    } finally {
      setLoadingCallId(null);
    }
  }

  return (
    <PanelCard icon={<LocalPhoneOutlinedIcon color="primary" />} title="Call History">
      {error ? <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert> : null}
      {calls.length ? (
        <Stack spacing={1}>
          {calls.map((call) => (
            <Box
              key={call.id}
              sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.35 }}
            >
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={0.75}
                sx={{ alignItems: { xs: "flex-start", sm: "center" }, justifyContent: "space-between" }}
              >
                <Stack spacing={0.25}>
                  <Typography sx={{ fontWeight: 900 }}>{formatStatus(call.status)}</Typography>
                  <Typography color="text.secondary" variant="body2">
                    {formatDate(call.called_at)} / {call.agent_name || "Unassigned"} / {call.duration || 0}s
                  </Typography>
                </Stack>
                <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap", justifyContent: { sm: "flex-end" } }}>
                  <Chip label={call.call_mode === "questionnaire" ? "Voice Questions" : "Script Call"} size="small" variant="outlined" />
                  <Chip label={call.call_sid ? `SID ${call.call_sid.slice(-8)}` : "No SID"} size="small" variant="outlined" />
                  <Chip
                    label={recordingLabel(call)}
                    size="small"
                    sx={{
                      bgcolor: call.recording_url ? "#dbeafe" : call.recording_status === "failed" ? "#fdecea" : "#eef2f7",
                      color: call.recording_url ? "#1d4ed8" : call.recording_status === "failed" ? "#b42318" : "#42526a",
                      fontWeight: 850
                    }}
                  />
                  {call.transcript_status ? (
                    <Chip label={`Transcript ${formatStatus(call.transcript_status)}`} size="small" variant="outlined" />
                  ) : null}
                </Stack>
              </Stack>
              <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                {preview(call.error_message || call.script)}
              </Typography>
              {questionnaireAnswers(call).length ? (
                <Stack spacing={0.7} sx={{ mt: 1 }}>
                  {questionnaireAnswers(call).map((answer, index) => (
                    <Box key={`${call.id}-${answer.key || index}`} sx={{ bgcolor: "white", borderRadius: 1.5, p: 1 }}>
                      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
                        {String(answer.question || `Question ${index + 1}`)}
                      </Typography>
                      <Typography sx={{ fontWeight: 800 }}>{String(answer.answer || "-")}</Typography>
                    </Box>
                  ))}
                </Stack>
              ) : null}
              {call.recording_url ? (
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={0.75}
                  sx={{ alignItems: { xs: "flex-start", sm: "center" }, mt: 1 }}
                >
                  <Button
                    component="a"
                    href={call.recording_url}
                    rel="noreferrer"
                    size="small"
                    startIcon={<PlayCircleOutlineOutlinedIcon />}
                    target="_blank"
                    variant="outlined"
                  >
                    Open Recording
                  </Button>
                  <Button
                    disabled={loadingCallId === call.id || call.transcript_status === "processing"}
                    onClick={() => transcribe(call.id)}
                    size="small"
                    startIcon={<TextSnippetOutlinedIcon />}
                    variant="outlined"
                  >
                    {loadingCallId === call.id || call.transcript_status === "processing"
                      ? "Transcribing..."
                      : call.transcript_text
                        ? "Re-transcribe"
                        : "Transcribe Recording"}
                  </Button>
                  <Typography color="text.secondary" variant="caption">
                    Recording: {call.recording_duration || call.duration || 0}s
                    {call.recording_available_at ? ` / Ready ${formatDate(call.recording_available_at)}` : ""}
                  </Typography>
                </Stack>
              ) : null}
              {loadingCallId === call.id ? <LinearProgress sx={{ mt: 1 }} /> : null}
              {call.transcript_error ? (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  {call.transcript_error}
                </Alert>
              ) : null}
              {call.transcript_summary || call.transcript_text || call.transcript_next_action ? (
                <Box sx={{ bgcolor: "white", borderRadius: 1.5, mt: 1, p: 1 }}>
                  {call.transcript_next_action ? (
                    <Alert severity="info" sx={{ mb: 1 }}>
                      <Typography sx={{ fontWeight: 900 }} variant="body2">
                        Suggested next action
                      </Typography>
                      <Typography variant="body2">{call.transcript_next_action}</Typography>
                    </Alert>
                  ) : null}
                  {Object.keys(transcriptAnalysis(call)).length ? (
                    <Box sx={{ display: "grid", gap: 0.75, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, mb: 1 }}>
                      <AnalysisBlock label="Interest" value={field(transcriptAnalysis(call), "interest")} />
                      <AnalysisBlock label="Visit Intent" value={field(transcriptAnalysis(call), "visit_intent")} />
                      <AnalysisBlock label="Score" value={`${field(transcriptAnalysis(call), "score")} / ${field(transcriptAnalysis(call), "score_band")}`} />
                      <AnalysisBlock label="Budget" value={field(transcriptAnalysis(call), "budget")} />
                      <AnalysisBlock label="Location" value={field(transcriptAnalysis(call), "location")} />
                      <AnalysisBlock label="Timeline" value={field(transcriptAnalysis(call), "timeline")} />
                    </Box>
                  ) : null}
                  {objections(transcriptAnalysis(call)).length ? (
                    <Box sx={{ bgcolor: "#fff7ed", borderRadius: 1.5, mb: 1, p: 1 }}>
                      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
                        Objections
                      </Typography>
                      <Typography sx={{ fontWeight: 800 }}>{objections(transcriptAnalysis(call)).join("; ")}</Typography>
                    </Box>
                  ) : null}
                  {call.transcript_summary ? (
                    <>
                      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
                        AI Summary
                      </Typography>
                      <Typography sx={{ fontWeight: 800 }}>{call.transcript_summary}</Typography>
                    </>
                  ) : null}
                  {call.transcript_text ? (
                    <>
                      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, mt: 1, textTransform: "uppercase" }}>
                        Transcript
                      </Typography>
                      <Typography color="text.secondary" variant="body2">
                        {call.transcript_text}
                      </Typography>
                    </>
                  ) : null}
                  {call.transcribed_at ? (
                    <Typography color="text.secondary" sx={{ display: "block", mt: 0.75 }} variant="caption">
                      Transcribed {formatDate(call.transcribed_at)}
                      {call.transcript_model ? ` / ${call.transcript_model}` : ""}
                    </Typography>
                  ) : null}
                </Box>
              ) : null}
            </Box>
          ))}
        </Stack>
      ) : (
        <EmptyState title="No calls yet" description="Manual Twilio voice calls will appear here with delivery status." />
      )}
    </PanelCard>
  );
}

function formatStatus(value?: string) {
  return String(value || "Queued")
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDate(value?: string) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("en-IN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function preview(value?: string) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  return clean.length > 180 ? `${clean.slice(0, 180)}...` : clean || "-";
}

function questionnaireAnswers(call: CallLog) {
  const raw = call.questionnaire_answers;
  if (Array.isArray(raw)) {
    return raw;
  }
  try {
    const parsed = JSON.parse(String(raw || "[]"));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function transcriptAnalysis(call: CallLog) {
  const raw = call.transcript_analysis;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  try {
    const parsed = JSON.parse(String(raw || "{}"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function field(analysis: Record<string, unknown>, key: string) {
  const value = analysis[key];
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function objections(analysis: Record<string, unknown>) {
  const value = analysis.objections;
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function AnalysisBlock({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ bgcolor: "#f8fafc", borderRadius: 1.5, p: 1 }}>
      <Typography color="text.secondary" sx={{ fontSize: 10, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 850, overflowWrap: "anywhere" }}>{value}</Typography>
    </Box>
  );
}

function recordingLabel(call: CallLog) {
  if (call.recording_url) {
    return "Recording Available";
  }
  if (call.recording_status) {
    return `Recording ${formatStatus(call.recording_status)}`;
  }
  if (["queued", "ringing", "answered"].includes(String(call.status || "").toLowerCase())) {
    return "Recording Pending";
  }
  return "No Recording";
}
