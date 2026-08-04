"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPatch, apiPost } from "@/lib/api";
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
    const consentOnly =
      eligibility?.reasons?.length === 1 && eligibility.reasons[0] === "Lead has not consented to receive calls.";

    const markCallConsent = async () => {
      setLoading("consent");
      setError("");
      setStatus("");
      try {
        await apiPatch(`/${leadId}/call-preferences`, { call_consent: true, do_not_call: false });
        setStatus("Call consent marked. Refreshing call eligibility...");
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not update call consent");
      } finally {
        setLoading("");
      }
    };

    return (
      <Stack spacing={1.1} sx={{ mb: 1.25 }}>
        <Alert severity="info">
          <Typography sx={{ fontWeight: 850 }} variant="body2">
            Call is unavailable right now.
          </Typography>
          <Typography variant="body2">{eligibility?.reasons?.join(" ") || "Lead is not eligible for calling."}</Typography>
        </Alert>
        {consentOnly ? (
          <Button
            disabled={Boolean(loading)}
            onClick={markCallConsent}
            startIcon={<LocalPhoneOutlinedIcon />}
            variant="outlined"
          >
            {loading === "consent" ? "Updating..." : "Mark Call Consent"}
          </Button>
        ) : null}
        {error ? <Alert severity="error">{error}</Alert> : null}
        {status ? <Alert severity="success">{status}</Alert> : null}
      </Stack>
    );
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
