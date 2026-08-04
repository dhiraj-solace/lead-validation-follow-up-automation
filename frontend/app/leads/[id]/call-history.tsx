import LocalPhoneOutlinedIcon from "@mui/icons-material/LocalPhoneOutlined";
import PlayCircleOutlineOutlinedIcon from "@mui/icons-material/PlayCircleOutlineOutlined";
import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import { EmptyState, PanelCard } from "../../ui";

export type CallLog = {
  id: number;
  call_sid?: string;
  status: string;
  script: string;
  duration?: number;
  recording_sid?: string;
  recording_url?: string;
  recording_status?: string;
  recording_duration?: number;
  recording_available_at?: string;
  called_at?: string;
  agent_name?: string;
  error_message?: string;
};

export default function CallHistory({ calls }: { calls: CallLog[] }) {
  return (
    <PanelCard icon={<LocalPhoneOutlinedIcon color="primary" />} title="Call History">
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
                  <Chip label={call.call_sid ? `SID ${call.call_sid.slice(-8)}` : "No SID"} size="small" variant="outlined" />
                  <Chip
                    label={recordingLabel(call)}
                    size="small"
                    sx={{
                      bgcolor: call.recording_url ? "#dcfce7" : call.recording_status === "failed" ? "#fdecea" : "#eef2f7",
                      color: call.recording_url ? "#087443" : call.recording_status === "failed" ? "#b42318" : "#42526a",
                      fontWeight: 850
                    }}
                  />
                </Stack>
              </Stack>
              <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                {preview(call.error_message || call.script)}
              </Typography>
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
                  <Typography color="text.secondary" variant="caption">
                    Recording: {call.recording_duration || call.duration || 0}s
                    {call.recording_available_at ? ` / Ready ${formatDate(call.recording_available_at)}` : ""}
                  </Typography>
                </Stack>
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
