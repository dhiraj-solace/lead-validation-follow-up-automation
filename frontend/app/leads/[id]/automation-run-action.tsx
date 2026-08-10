"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import PlayCircleOutlineOutlinedIcon from "@mui/icons-material/PlayCircleOutlineOutlined";
import { Alert, Box, Button, Chip, LinearProgress, Stack, Typography } from "@mui/material";

type AutomationStep = {
  action: string;
  status: string;
  message: string;
  call_id?: number | null;
};

type AutomationResponse = {
  success: boolean;
  message: string;
  lead_id: number;
  steps: AutomationStep[];
};

export default function AutomationRunAction({ leadId, validationStatus }: { leadId: number; validationStatus?: string | null }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AutomationResponse | null>(null);
  const [error, setError] = useState("");
  const valid = validationStatus === "Valid";

  async function runAutomation() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await apiPost<AutomationResponse>(`/${leadId}/run-automation`);
      setResult(response);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Automation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box sx={{ mb: 1.25 }}>
      <Button
        disabled={!valid || loading}
        fullWidth
        onClick={runAutomation}
        startIcon={<PlayCircleOutlineOutlinedIcon />}
        variant="contained"
      >
        {loading ? "Running Automation..." : "Run Automation"}
      </Button>
      <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
        One click sends the initial email, starts the voice-question call, and transcribes when a recording is available.
      </Typography>

      {loading ? <LinearProgress sx={{ mt: 1 }} /> : null}
      {!valid ? <Alert severity="info" sx={{ mt: 1 }}>Only valid leads can run automation.</Alert> : null}
      {error ? <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert> : null}

      {result ? (
        <Alert severity={result.success ? "success" : "warning"} sx={{ mt: 1 }}>
          <Typography sx={{ fontWeight: 850 }} variant="body2">{result.message}</Typography>
          <Stack spacing={0.7} sx={{ mt: 0.8 }}>
            {result.steps.map((step, index) => (
              <Box key={`${step.action}-${index}`} sx={{ display: "flex", gap: 0.75, alignItems: "flex-start" }}>
                <Chip color={statusColor(step.status)} label={label(step.action)} size="small" />
                <Typography variant="body2">
                  {label(step.status)}: {step.message}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Alert>
      ) : null}
    </Box>
  );
}

function label(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusColor(status: string): "default" | "success" | "warning" | "error" | "info" {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  if (status === "waiting") {
    return "warning";
  }
  if (status === "skipped") {
    return "info";
  }
  return "default";
}
