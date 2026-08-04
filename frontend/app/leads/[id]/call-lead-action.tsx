"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import LocalPhoneOutlinedIcon from "@mui/icons-material/LocalPhoneOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  TextField,
  Typography
} from "@mui/material";

type CallEligibility = {
  eligible: boolean;
  reasons: string[];
  minimum_score: number;
  cooldown_hours: number;
};

type ScriptResponse = {
  script: string;
  masked_phone: string;
  assigned_agent: string;
  eligibility: CallEligibility;
};

type StartCallResponse = {
  success: boolean;
  message: string;
  call_sid: string;
  status: string;
};

export default function CallLeadAction({
  leadId,
  leadName,
  maskedPhone,
  assignedAgent,
  eligibility
}: {
  leadId: number;
  leadName: string;
  maskedPhone: string;
  assignedAgent: string;
  eligibility?: CallEligibility;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [script, setScript] = useState("");
  const [loading, setLoading] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  if (!eligibility?.eligible) {
    return null;
  }

  async function openDialog() {
    setOpen(true);
    setStatus("");
    setError("");
    if (!script) {
      await generateScript();
    }
  }

  async function generateScript() {
    setLoading("script");
    setError("");
    try {
      const response = await apiPost<ScriptResponse>(`/${leadId}/call-script`);
      setScript(response.script || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate call script");
    } finally {
      setLoading("");
    }
  }

  async function startCall() {
    setLoading("call");
    setError("");
    setStatus("");
    try {
      const response = await apiPost<StartCallResponse>(`/${leadId}/calls`, { script });
      setStatus(`${response.message} Status: ${response.status}.`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start call");
    } finally {
      setLoading("");
    }
  }

  return (
    <>
      <Button onClick={openDialog} startIcon={<LocalPhoneOutlinedIcon />} sx={{ mb: 1.25, width: "100%" }} variant="contained">
        Call Lead
      </Button>

      <Dialog fullWidth maxWidth="sm" onClose={() => setOpen(false)} open={open}>
        <DialogTitle sx={{ pb: 1 }}>
          <Stack spacing={0.35}>
            <Typography sx={{ fontSize: 20, fontWeight: 900 }}>Call Lead</Typography>
            <Typography color="text.secondary" variant="body2">
              Review the text-to-speech script before starting the Twilio voice call.
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={1.4}>
            <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <InfoBlock label="Lead" value={leadName} />
              <InfoBlock label="Phone" value={maskedPhone} />
              <InfoBlock label="Assigned Agent" value={assignedAgent || "Unassigned"} />
              <InfoBlock label="Call Rule" value={`Minimum score ${eligibility.minimum_score}`} />
            </Box>

            <TextField
              label="Call script"
              maxRows={8}
              minRows={5}
              multiline
              onChange={(event) => setScript(event.target.value)}
              value={script}
            />
            {loading ? <LinearProgress /> : null}
            {error ? <Alert severity="error">{error}</Alert> : null}
            {status ? <Alert severity="success">{status}</Alert> : null}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ flexWrap: "wrap", gap: 1, p: 2 }}>
          <Button onClick={() => setOpen(false)} variant="outlined">
            Cancel
          </Button>
          <Button disabled={Boolean(loading)} onClick={generateScript} startIcon={<AutoAwesomeOutlinedIcon />} variant="outlined">
            {loading === "script" ? "Generating..." : "Generate AI Call Script"}
          </Button>
          <Button disabled={Boolean(loading) || !script.trim()} onClick={startCall} startIcon={<LocalPhoneOutlinedIcon />} variant="contained">
            {loading === "call" ? "Starting..." : "Start Call"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.2 }}>
      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 850, mt: 0.35, overflowWrap: "anywhere" }}>{value}</Typography>
    </Box>
  );
}
