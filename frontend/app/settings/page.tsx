"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, apiGet, apiPatch } from "@/lib/api";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import CloudSyncOutlinedIcon from "@mui/icons-material/CloudSyncOutlined";
import DataObjectOutlinedIcon from "@mui/icons-material/DataObjectOutlined";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { Alert, Box, Button, CircularProgress, FormControlLabel, Stack, Switch, Typography } from "@mui/material";
import { PageHeader, PanelCard } from "../ui";

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box
      sx={{
        borderTop: "1px solid",
        borderColor: "divider",
        display: "grid",
        gap: 1.5,
        gridTemplateColumns: { xs: "1fr", sm: "150px minmax(0, 1fr)" },
        p: 1.75,
        "&:first-of-type": {
          borderTop: 0
        }
      }}
    >
      <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography color="text.primary">{value}</Typography>
    </Box>
  );
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="code"
      sx={{
        bgcolor: "#eef3f7",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        fontFamily: "monospace",
        fontSize: 12,
        px: 0.7,
        py: 0.2
      }}
    >
      {children}
    </Box>
  );
}

export default function SettingsPage() {
  const [autoEmailSendEnabled, setAutoEmailSendEnabled] = useState(false);
  const [callProvider, setCallProvider] = useState<"twilio" | "telnyx">("twilio");
  const [callProviderCredentials, setCallProviderCredentials] = useState<{
    configured: boolean;
    message: string;
    missing: string[];
    provider: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSettings() {
      setLoading(true);
      try {
        const data = await apiGet<{
          auto_email_send_enabled: boolean;
          call_provider: "twilio" | "telnyx";
          call_provider_credentials: {
            configured: boolean;
            message: string;
            missing: string[];
            provider: string;
          };
        }>("/settings");
        setAutoEmailSendEnabled(Boolean(data.auto_email_send_enabled));
        setCallProvider(data.call_provider || "twilio");
        setCallProviderCredentials(data.call_provider_credentials || null);
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load automation settings.");
      } finally {
        setLoading(false);
      }
    }
    loadSettings();
  }, []);

  async function toggleAutoEmailSend(nextValue: boolean) {
    const warning = nextValue
      ? "Auto Email Send will automatically send generated emails to valid Hot leads after upload. Only enable this when SMTP and templates are approved. Continue?"
      : "Auto Email Send will be turned off. Future uploads will generate drafts only and will not send automatically. Continue?";
    if (!window.confirm(warning)) {
      return;
    }

    setSaving(true);
    setNotice("");
    setError("");
    try {
      const data = await apiPatch<{ auto_email_send_enabled: boolean }>("/settings", {
        auto_email_send_enabled: nextValue
      });
      setAutoEmailSendEnabled(Boolean(data.auto_email_send_enabled));
      setNotice(nextValue ? "Auto Email Send is enabled." : "Auto Email Send is disabled.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update automation setting.");
    } finally {
      setSaving(false);
    }
  }

  async function updateCallProvider(nextProvider: "twilio" | "telnyx") {
    if (nextProvider === callProvider) {
      return;
    }
    const confirmed = window.confirm(
      `Switch voice and phone lookup provider to ${providerLabel(nextProvider)}? The server must have the required ${providerLabel(nextProvider)} environment credentials.`
    );
    if (!confirmed) {
      return;
    }

    setSaving(true);
    setNotice("");
    setError("");
    try {
      const data = await apiPatch<{
        call_provider: "twilio" | "telnyx";
        call_provider_credentials: {
          configured: boolean;
          message: string;
          missing: string[];
          provider: string;
        };
      }>("/settings", { call_provider: nextProvider });
      setCallProvider(data.call_provider || nextProvider);
      setCallProviderCredentials(data.call_provider_credentials || null);
      setNotice(`Call provider switched to ${providerLabel(data.call_provider || nextProvider)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update call provider.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        description="Confirm the frontend API target, upload schema, and service behavior for this local MVP."
        eyebrow="Settings"
        title="Runtime configuration"
      />

      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <PanelCard
          description="Control whether qualified uploaded leads are emailed automatically after AI draft generation."
          icon={<WarningAmberOutlinedIcon color="warning" />}
          title="Auto Email Send"
        >
          <Stack spacing={1.5}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            {notice ? <Alert severity="success">{notice}</Alert> : null}
            <Box
              sx={{
                alignItems: "center",
                bgcolor: "#f8fafc",
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 2,
                display: "flex",
                justifyContent: "space-between",
                gap: 1.5,
                p: 1.5
              }}
            >
              <Box>
                <Typography sx={{ fontWeight: 900 }}>
                  {autoEmailSendEnabled ? "Automatic sending is on" : "Automatic sending is off"}
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  When on, only valid Hot leads with generated drafts can be sent automatically during upload.
                </Typography>
              </Box>
              {loading ? (
                <CircularProgress size={24} />
              ) : (
                <FormControlLabel
                  control={
                    <Switch
                      checked={autoEmailSendEnabled}
                      disabled={saving}
                      onChange={(event) => toggleAutoEmailSend(event.target.checked)}
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
              )}
            </Box>
            <Alert severity="warning" sx={{ py: 0.75 }}>
              Keep this off unless SMTP, templates, and AI review rules are approved for live outreach.
            </Alert>
          </Stack>
        </PanelCard>

        <PanelCard
          description="Next.js sends lead workflow requests to this backend endpoint."
          icon={<CloudSyncOutlinedIcon color="primary" />}
          title="Frontend API target"
        >
          <Box
            component="pre"
            sx={{
              bgcolor: "#0f172a",
              borderRadius: 2,
              color: "#e5edf7",
              fontFamily: "monospace",
              fontSize: 13,
              m: 0,
              overflowX: "auto",
              p: 2
            }}
          >
            {API_BASE_URL}
          </Box>
        </PanelCard>

        <PanelCard
          description="Choose which server-side provider handles phone lookup and outbound calls."
          icon={<CloudSyncOutlinedIcon color="primary" />}
          title="Call provider"
        >
          <Stack spacing={1.5}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              {(["twilio", "telnyx"] as const).map((provider) => (
                <Button
                  disabled={loading || saving}
                  key={provider}
                  onClick={() => updateCallProvider(provider)}
                  variant={callProvider === provider ? "contained" : "outlined"}
                >
                  {providerLabel(provider)}
                </Button>
              ))}
            </Stack>
            <Alert severity={callProviderCredentials?.configured ? "success" : "warning"}>
              {callProviderCredentials?.message || "Loading provider credential status..."}
            </Alert>
            <Stack sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
              <DetailRow label="Selected" value={providerLabel(callProvider)} />
              <DetailRow
                label="Required env"
                value={
                  callProvider === "telnyx" ? (
                    <>
                      <InlineCode>TELNYX_API_KEY</InlineCode>{" "}
                      <InlineCode>TELNYX_PHONE_NUMBER</InlineCode>{" "}
                      <InlineCode>TELNYX_CONNECTION_ID</InlineCode>{" "}
                      <InlineCode>PUBLIC_BASE_URL</InlineCode>
                    </>
                  ) : (
                    <>
                      <InlineCode>TWILIO_ACCOUNT_SID</InlineCode>{" "}
                      <InlineCode>TWILIO_AUTH_TOKEN</InlineCode>{" "}
                      <InlineCode>TWILIO_PHONE_NUMBER</InlineCode>{" "}
                      <InlineCode>PUBLIC_BASE_URL</InlineCode>
                    </>
                  )
                }
              />
            </Stack>
          </Stack>
        </PanelCard>

        <PanelCard
          description="The importer expects fixed headers in row 1."
          icon={<FileUploadOutlinedIcon color="primary" />}
          title="Upload format"
        >
          <Box
            component="pre"
            sx={{
              bgcolor: "#0f172a",
              borderRadius: 2,
              color: "#e5edf7",
              fontFamily: "monospace",
              fontSize: 13,
              m: 0,
              overflowX: "auto",
              p: 2
            }}
          >
{`name
email
phone
source
property_type
configuration
location_preference
budget
timeline
message`}
          </Box>
        </PanelCard>

        <PanelCard
          description="Email and phone checks degrade gracefully when external keys are missing."
          icon={<DataObjectOutlinedIcon color="primary" />}
          title="Validation services"
        >
          <Stack sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
            <DetailRow label="Email" value="Format validation plus API deliverability when configured." />
            <DetailRow label="Phone" value="Format validation plus selected provider lookup when configured." />
            <DetailRow label="Fallback" value="Simple local validation keeps the upload flow usable." />
          </Stack>
        </PanelCard>

        <PanelCard
          description="OpenRouter generates drafts using lead context and saved templates."
          icon={<AutoAwesomeOutlinedIcon color="primary" />}
          title="AI email writer"
        >
          <Stack sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
            <DetailRow
              label="Provider"
              value={
                <>
                  OpenRouter when <InlineCode>OPENROUTER_API_KEY</InlineCode> is set in backend{" "}
                  <InlineCode>.env</InlineCode>.
                </>
              }
            />
            <DetailRow label="Fallback" value="Local demo writer creates a reviewable draft if the API is unavailable." />
            <DetailRow label="Sending" value="Reviewed drafts send through SMTP, or become demo-sent without SMTP." />
          </Stack>
        </PanelCard>
      </Box>
    </>
  );
}

function providerLabel(provider: string) {
  return provider === "telnyx" ? "Telnyx" : "Twilio";
}
